# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2018.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Pass manager for optimization level 2, providing medium optimization.

Level 2 pass manager: medium optimization by noise adaptive qubit mapping and
gate cancellation using commutativity rules.
"""
from __future__ import annotations
from qiskit.transpiler.passmanager_config import PassManagerConfig
from qiskit.transpiler.passmanager import StagedPassManager
from qiskit.transpiler.preset_passmanagers import common
from qiskit.transpiler.preset_passmanagers.plugin import (
    PassManagerStagePluginManager,
)


def level_2_pass_manager(pass_manager_config: PassManagerConfig) -> StagedPassManager:
    """Level 2 pass manager: medium optimization by initial layout selection and
    gate cancellation using commutativity rules.

    This pass manager applies the user-given initial layout. If none is given, a search
    for a perfect layout (i.e. one that satisfies all 2-qubit interactions) is conducted.
    If no such layout is found, qubits are laid out on the most densely connected subset
    which also exhibits the best gate fidelities.

    The pass manager then transforms the circuit to match the coupling constraints.
    It is then unrolled to the basis, and any flipped cx directions are fixed.
    Finally, optimizations in the form of commutative gate cancellation and redundant
    reset removal are performed.

    Args:
        pass_manager_config: configuration of the pass manager.

    Returns:
        a level 2 pass manager.

    Raises:
        TranspilerError: if the passmanager config is invalid.
    """
    plugin_manager = PassManagerStagePluginManager()
    basis_gates = pass_manager_config.basis_gates
    coupling_map = pass_manager_config.coupling_map
    initial_layout = pass_manager_config.initial_layout
    init_method = pass_manager_config.init_method
    layout_method = pass_manager_config.layout_method or "default"
    routing_method = pass_manager_config.routing_method or "sabre"
    translation_method = pass_manager_config.translation_method or "translator"
    optimization_method = pass_manager_config.optimization_method or "default"
    scheduling_method = pass_manager_config.scheduling_method or "default"
    approximation_degree = pass_manager_config.approximation_degree
    unitary_synthesis_method = pass_manager_config.unitary_synthesis_method
    unitary_synthesis_plugin_config = pass_manager_config.unitary_synthesis_plugin_config
    target = pass_manager_config.target
    hls_config = pass_manager_config.hls_config

    # Choose routing pass
    routing_pm = plugin_manager.get_passmanager_stage(
        "routing", routing_method, pass_manager_config, optimization_level=2
    )

    unroll_3q = None
    # Build pass manager
    if coupling_map or initial_layout:
        unroll_3q = common.generate_unroll_3q(
            target,
            basis_gates,
            approximation_degree,
            unitary_synthesis_method,
            unitary_synthesis_plugin_config,
            hls_config,
        )
        layout = plugin_manager.get_passmanager_stage(
            "layout", layout_method, pass_manager_config, optimization_level=2
        )
        routing = routing_pm
    else:
        layout = None
        routing = None
    translation = plugin_manager.get_passmanager_stage(
        "translation", translation_method, pass_manager_config, optimization_level=2
    )

    if (coupling_map and not coupling_map.is_symmetric) or (
        target is not None and target.get_non_global_operation_names(strict_direction=True)
    ):
        pre_optimization = common.generate_pre_op_passmanager(target, coupling_map, True)
    else:
        pre_optimization = common.generate_pre_op_passmanager(remove_reset_in_zero=True)

    optimization = plugin_manager.get_passmanager_stage(
        "optimization", optimization_method, pass_manager_config, optimization_level=2
    )

    sched = plugin_manager.get_passmanager_stage(
        "scheduling", scheduling_method, pass_manager_config, optimization_level=2
    )

    init = common.generate_control_flow_options_check(
        layout_method=layout_method,
        routing_method=routing_method,
        translation_method=translation_method,
        optimization_method=optimization_method,
        scheduling_method=scheduling_method,
        basis_gates=basis_gates,
        target=target,
    )
    if init_method is not None:
        init += plugin_manager.get_passmanager_stage(
            "init", init_method, pass_manager_config, optimization_level=2
        )
    elif unroll_3q is not None:
        init += unroll_3q

    return StagedPassManager(
        init=init,
        layout=layout,
        routing=routing,
        translation=translation,
        pre_optimization=pre_optimization,
        optimization=optimization,
        scheduling=sched,
    )
