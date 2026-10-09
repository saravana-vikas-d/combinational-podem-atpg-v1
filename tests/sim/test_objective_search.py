from circuit.circuit import Circuit, Gate, GateType, Signal
from circuit.levelize import levelize
from fault.fault import branch_fault, line_fault
from logic5 import Logic5
from sim.objective_search import (
    activation_objectives,
    d_frontier_propagation_branches,
    upstream_objectives,
)


def _fanout2_and_circuit() -> Circuit:
    s = Signal("s", is_pi=True)
    z1 = Signal("z1", is_po=True)
    z2 = Signal("z2", is_po=True)
    g1 = Gate(id=0, instance_name="AND1", type=GateType.AND, inputs=[s, s], output=z1)
    g2 = Gate(id=1, instance_name="AND2", type=GateType.AND, inputs=[s, s], output=z2)
    z1.driver = g1
    z2.driver = g2
    s.fanouts.extend([(g1, 0), (g1, 1), (g2, 0), (g2, 1)])
    circuit = Circuit(
        name="fanout2",
        signals={"s": s, "z1": z1, "z2": z2},
        gates=[g1, g2],
        primary_inputs=[s],
        primary_outputs=[z1, z2],
    )
    levelize(circuit)
    return circuit


def test_activation_objectives_pi_stem_fault():
    circuit = _fanout2_and_circuit()
    objectives = activation_objectives(circuit, line_fault("s", 0))
    assert len(objectives) == 1
    assert objectives[0].gate is None
    assert objectives[0].signal.name == "s"
    assert objectives[0].desired is Logic5.ONE


def test_activation_objectives_branch_uses_stem_driver():
    circuit = _fanout2_and_circuit()
    objectives = activation_objectives(circuit, branch_fault("s", "AND1", 0, 0))
    assert len(objectives) == 1
    assert objectives[0].gate is None  # PI stem
    assert objectives[0].desired is Logic5.ONE


def test_upstream_skips_fault_stem():
    circuit = _fanout2_and_circuit()
    fault = line_fault("s", 0)
    upstream = upstream_objectives([(circuit.signals["s"], Logic5.ONE)], fault)
    assert upstream == []


def _two_input_frontier_gate(gate_type: GateType):
    a = Signal("a", is_pi=True)
    b = Signal("b", is_pi=True)
    z = Signal("z", is_po=True)
    gate = Gate(id=0, instance_name="G1", type=gate_type, inputs=[a, b], output=z)
    z.driver = gate
    a.fanouts.append((gate, 0))
    b.fanouts.append((gate, 1))
    a.value = Logic5.D
    b.value = Logic5.X
    z.value = Logic5.X
    fault = line_fault("a", 0)
    return gate, fault


def test_and_d_frontier_propagation_is_single_ncv_branch():
    gate, fault = _two_input_frontier_gate(GateType.AND)
    branches = d_frontier_propagation_branches(gate, fault)

    assert len(branches) == 1
    _note, objectives = branches[0]
    assert len(objectives) == 1
    assert objectives[0].signal.name == "b"
    assert objectives[0].desired is Logic5.ONE
    assert objectives[0].gate is None


def test_xor_d_frontier_propagation_tries_both_side_polarities():
    gate, fault = _two_input_frontier_gate(GateType.XOR)
    branches = d_frontier_propagation_branches(gate, fault)

    assert len(branches) == 2
    desired = [objectives[0].desired for _note, objectives in branches]
    assert desired == [Logic5.ZERO, Logic5.ONE]
    for _note, objectives in branches:
        assert len(objectives) == 1
        assert objectives[0].signal.name == "b"
        assert objectives[0].gate is None


def test_xnor_d_frontier_propagation_tries_both_side_polarities():
    gate, fault = _two_input_frontier_gate(GateType.XNOR)
    branches = d_frontier_propagation_branches(gate, fault)

    assert [objectives[0].desired for _note, objectives in branches] == [
        Logic5.ZERO,
        Logic5.ONE,
    ]


def test_xor_d_frontier_side_already_binary_needs_no_objective():
    gate, fault = _two_input_frontier_gate(GateType.XOR)
    gate.inputs[1].value = Logic5.ZERO
    branches = d_frontier_propagation_branches(gate, fault)

    assert len(branches) == 1
    assert branches[0][1] == []
