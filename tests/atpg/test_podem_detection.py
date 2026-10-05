from pathlib import Path

import pytest

from atpg.podem import (
    PatternError,
    extract_pattern,
    fault_detected_at_po,
    find_d_frontier,
    pi_pattern_bit,
)
from circuit.circuit import Circuit, Gate, GateType, Signal
from circuit.levelize import levelize
from fault.fault import branch_fault, line_fault
from logic5 import Logic5
from parser.iscas_verilog import parse_iscas_verilog
from sim.implication import forward_imply, inject_fault

ISCAS = Path(__file__).resolve().parents[2] / "ISCAS85_Circuits"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Logic5.ZERO, 0),
        (Logic5.ONE, 1),
        (Logic5.X, None),
        (Logic5.D, 1),
        (Logic5.DBAR, 0),
    ],
)
def test_pi_pattern_bit(value, expected):
    assert pi_pattern_bit(value) == expected


def _and_d_frontier_circuit() -> Circuit:
    """AND(a, w) -> z with w=D and a=X leaves z=X (gate on D-frontier)."""
    a = Signal("a", is_pi=True)
    w = Signal("w", is_pi=True)
    z = Signal("z", is_po=True)
    gate = Gate(
        id=0,
        instance_name="AND1",
        type=GateType.AND,
        inputs=[a, w],
        output=z,
    )
    z.driver = gate
    a.fanouts.append((gate, 0))
    w.fanouts.append((gate, 1))

    circuit = Circuit(
        name="d_frontier",
        signals={"a": a, "w": w, "z": z},
        gates=[gate],
        primary_inputs=[a, w],
        primary_outputs=[z],
    )
    levelize(circuit)
    return circuit


def test_fault_detected_at_po_true_when_d_at_output():
    circuit = _and_d_frontier_circuit()
    circuit.signals["a"].value = Logic5.ONE
    circuit.signals["w"].value = Logic5.D
    forward_imply(circuit)

    assert fault_detected_at_po(circuit) is True


def test_fault_detected_at_po_false_when_output_not_d():
    circuit = _and_d_frontier_circuit()
    circuit.signals["a"].value = Logic5.X
    circuit.signals["w"].value = Logic5.D
    forward_imply(circuit)

    assert fault_detected_at_po(circuit) is False


def test_find_d_frontier_detects_gate_with_x_output_and_d_input():
    circuit = _and_d_frontier_circuit()
    circuit.signals["a"].value = Logic5.X
    circuit.signals["w"].value = Logic5.D
    forward_imply(circuit)

    frontier = find_d_frontier(circuit)
    assert len(frontier) == 1
    assert frontier[0].instance_name == "AND1"


def test_find_d_frontier_empty_when_fault_reaches_po():
    circuit = _and_d_frontier_circuit()
    circuit.signals["a"].value = Logic5.ONE
    circuit.signals["w"].value = Logic5.D
    forward_imply(circuit)

    assert find_d_frontier(circuit) == []


def test_find_d_frontier_branch_fault_uses_resolve_input_value():
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

    fault = branch_fault("s", "AND1", 0, 0)
    inject_fault(circuit, fault)
    forward_imply(circuit, active_fault=fault)

    assert fault_detected_at_po(circuit) is False
    frontier = find_d_frontier(circuit, active_fault=fault)
    assert [gate.instance_name for gate in frontier] == ["AND1"]


def test_find_d_frontier_on_c17_before_po_propagation():
    circuit = parse_iscas_verilog(ISCAS / "c17.v")
    levelize(circuit)

    fault = line_fault("N3", 0)
    inject_fault(circuit, fault)
    circuit.signals["N1"].value = Logic5.ONE
    circuit.signals["N6"].value = Logic5.ZERO
    circuit.signals["N7"].value = Logic5.ONE
    forward_imply(circuit, active_fault=fault)

    assert fault_detected_at_po(circuit) is False
    frontier = find_d_frontier(circuit, active_fault=fault)
    assert {gate.instance_name for gate in frontier} == {"NAND2_5"}


def test_extract_pattern_mixed_care_and_dont_care():
    circuit = parse_iscas_verilog(ISCAS / "c17.v")
    levelize(circuit)

    circuit.signals["N1"].value = Logic5.ONE
    circuit.signals["N2"].value = Logic5.X
    circuit.signals["N3"].value = Logic5.ZERO
    circuit.signals["N6"].value = Logic5.X
    circuit.signals["N7"].value = Logic5.ONE

    assert extract_pattern(circuit) == (1, None, 0, None, 1)


def test_extract_pattern_maps_faulted_pi_to_good_rail():
    circuit = parse_iscas_verilog(ISCAS / "c17.v")
    levelize(circuit)

    inject_fault(circuit, line_fault("N3", 0))
    circuit.signals["N1"].value = Logic5.ONE

    pattern = extract_pattern(circuit)
    assert pattern[2] == 1  # N3 = D -> good rail 1


def test_extract_pattern_requires_at_least_one_care_bit():
    circuit = parse_iscas_verilog(ISCAS / "c17.v")
    levelize(circuit)

    with pytest.raises(PatternError, match="at least one care bit"):
        extract_pattern(circuit)
