from circuit.circuit import Circuit, Gate, GateType, Signal
from circuit.levelize import levelize
from fault.fault import branch_fault, line_fault
from logic5 import Logic5
from sim.objective_search import activation_objectives, upstream_objectives


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
