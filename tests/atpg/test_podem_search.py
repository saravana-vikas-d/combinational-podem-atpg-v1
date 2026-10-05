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


def test_podem_finds_test_for_not_output_sa0_after_activation_backtrace():
    """Output stem sa0: activation justifies PI, then implication observes D at PO."""
    circuit = _not_output_fault_circuit()

    result = podem(circuit, line_fault("z", 0))

    assert result.status == "success"
    assert result.pattern == (0,)


def test_podem_aborted_when_backtrack_limit_reached():
    circuit = parse_iscas_verilog(ISCAS / "c17.v")
    levelize(circuit)

    result = podem(circuit, line_fault("N3", 0), backtrack_limit=0)

    assert result.status == "aborted"
    assert result.pattern is None
    assert result.backtracks >= 1
