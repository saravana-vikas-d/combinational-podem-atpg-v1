from pathlib import Path

from atpg.podem import fault_detected_at_po, podem
from circuit.circuit import Circuit, Gate, GateType, Signal
from circuit.levelize import levelize
from fault.fault import line_fault
from logic5 import Logic5
from parser.iscas_verilog import parse_iscas_verilog
from sim.implication import forward_imply, inject_fault, reset_values

ISCAS = Path(__file__).resolve().parents[2] / "ISCAS85_Circuits"


def _not_output_fault_circuit() -> Circuit:
    """NOT(a)->z; stem sa0 on z conflicts with forward implication after inject."""
    a = Signal("a", is_pi=True)
    z = Signal("z", is_po=True)
    gate = Gate(id=0, instance_name="NOT1", type=GateType.NOT, inputs=[a], output=z)
    z.driver = gate
    a.fanouts.append((gate, 0))

    circuit = Circuit(
        name="not_po_fault",
        signals={"a": a, "z": z},
        gates=[gate],
        primary_inputs=[a],
        primary_outputs=[z],
    )
    levelize(circuit)
    return circuit


def _apply_pattern(circuit: Circuit, pattern: tuple[int | None, ...]) -> None:
    for pi, bit in zip(circuit.primary_inputs, pattern, strict=True):
        if bit is None:
            pi.value = Logic5.X
        else:
            pi.value = Logic5.ONE if bit == 1 else Logic5.ZERO


def test_podem_finds_test_for_c17_n10_sa1():
    circuit = parse_iscas_verilog(ISCAS / "c17.v")
    levelize(circuit)
    fault = line_fault("N10", 1)

    result = podem(circuit, fault)

    assert result.status == "success"
    assert result.pattern is not None
    assert result.backtracks == 0

    verify = parse_iscas_verilog(ISCAS / "c17.v")
    levelize(verify)
    reset_values(verify)
    _apply_pattern(verify, result.pattern)
    inject_fault(verify, fault)
    assert forward_imply(verify, active_fault=fault) is True
    assert fault_detected_at_po(verify) is True


def test_podem_finds_test_for_c17_n3_sa0():
    circuit = parse_iscas_verilog(ISCAS / "c17.v")
    levelize(circuit)
    fault = line_fault("N3", 0)

    result = podem(circuit, fault)

    assert result.status == "success"
    assert result.pattern is not None
    assert result.pattern[2] == 1  # N3 = D -> good rail 1 for sa0

    verify = parse_iscas_verilog(ISCAS / "c17.v")
    levelize(verify)
    reset_values(verify)
    _apply_pattern(verify, result.pattern)
    inject_fault(verify, fault)
    assert forward_imply(verify, active_fault=fault) is True
    assert fault_detected_at_po(verify) is True


def _xor_po_circuit() -> Circuit:
    a = Signal("a", is_pi=True)
    b = Signal("b", is_pi=True)
    z = Signal("z", is_po=True)
    gate = Gate(id=0, instance_name="XOR1", type=GateType.XOR, inputs=[a, b], output=z)
    z.driver = gate
    a.fanouts.append((gate, 0))
    b.fanouts.append((gate, 1))
    circuit = Circuit(
        name="xor_po",
        signals={"a": a, "b": b, "z": z},
        gates=[gate],
        primary_inputs=[a, b],
        primary_outputs=[z],
    )
    levelize(circuit)
    return circuit


def test_podem_finds_test_for_xor_input_sa0():
    """XOR D-frontier must try both side polarities; either 0 or 1 on b propagates D."""
    circuit = _xor_po_circuit()
    fault = line_fault("a", 0)

    result = podem(circuit, fault)

    assert result.status == "success"
    assert result.pattern is not None
    assert result.pattern[0] == 1  # a = D for sa0

    verify = _xor_po_circuit()
    reset_values(verify)
    _apply_pattern(verify, result.pattern)
    inject_fault(verify, fault)
    assert forward_imply(verify, active_fault=fault) is True
    assert fault_detected_at_po(verify) is True


def test_podem_finds_test_for_not_output_sa0_after_activation_backtrace():
    """Output stem sa0: activation justifies PI, then implication observes D at PO."""
    circuit = _not_output_fault_circuit()

    result = podem(circuit, line_fault("z", 0))

    assert result.status == "success"
    assert result.pattern == (0,)


def test_podem_second_xor_polarity_propagates_through_and():
    a = Signal("a", is_pi=True)
    b = Signal("b", is_pi=True)
    t = Signal("t")
    z = Signal("z", is_po=True)
    xor_gate = Gate(id=0, instance_name="XOR1", type=GateType.XOR, inputs=[a, b], output=t)
    and_gate = Gate(id=1, instance_name="AND1", type=GateType.AND, inputs=[t, b], output=z)
    t.driver = xor_gate
    z.driver = and_gate
    a.fanouts.append((xor_gate, 0))
    b.fanouts.extend([(xor_gate, 1), (and_gate, 1)])
    t.fanouts.append((and_gate, 0))
    circuit = Circuit(
        name="xor_and",
        signals={"a": a, "b": b, "t": t, "z": z},
        gates=[xor_gate, and_gate],
        primary_inputs=[a, b],
        primary_outputs=[z],
    )
    levelize(circuit)
    fault = line_fault("a", 0)

    result = podem(circuit, fault)

    assert result.status == "success"
    assert result.pattern is not None
    assert result.pattern[1] == 1  # b must be 1; b=0 blocks the AND


def test_podem_aborted_when_backtrack_limit_reached():
    """First XOR polarity (b=0) kills the AND path; limit 0 aborts on that backtrack."""
    a = Signal("a", is_pi=True)
    b = Signal("b", is_pi=True)
    t = Signal("t")
    z = Signal("z", is_po=True)
    xor_gate = Gate(id=0, instance_name="XOR1", type=GateType.XOR, inputs=[a, b], output=t)
    and_gate = Gate(id=1, instance_name="AND1", type=GateType.AND, inputs=[t, b], output=z)
    t.driver = xor_gate
    z.driver = and_gate
    a.fanouts.append((xor_gate, 0))
    b.fanouts.extend([(xor_gate, 1), (and_gate, 1)])
    t.fanouts.append((and_gate, 0))
    circuit = Circuit(
        name="xor_and",
        signals={"a": a, "b": b, "t": t, "z": z},
        gates=[xor_gate, and_gate],
        primary_inputs=[a, b],
        primary_outputs=[z],
    )
    levelize(circuit)

    result = podem(circuit, line_fault("a", 0), backtrack_limit=0)

    assert result.status == "aborted"
    assert result.pattern is None
    assert result.backtracks >= 1
