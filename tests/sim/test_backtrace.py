import pytest

from circuit.circuit import Circuit, Gate, GateType, Signal
from circuit.levelize import levelize
from logic5 import Logic5
from sim.implication import BacktraceError, apply_backtrace, backtrace


def _two_input_gate(gate_type: GateType, instance_name: str = "G1") -> Gate:
    a = Signal("a", is_pi=True)
    b = Signal("b", is_pi=True)
    z = Signal("z", is_po=True)
    gate = Gate(
        id=0,
        instance_name=instance_name,
        type=gate_type,
        inputs=[a, b],
        output=z,
    )
    z.driver = gate
    a.fanouts.append((gate, 0))
    b.fanouts.append((gate, 1))
    return gate


def _single_input_gate(gate_type: GateType) -> Gate:
    a = Signal("a", is_pi=True)
    z = Signal("z", is_po=True)
    gate = Gate(
        id=0,
        instance_name="G1",
        type=gate_type,
        inputs=[a],
        output=z,
    )
    z.driver = gate
    a.fanouts.append((gate, 0))
    return gate


def _circuit_for_gate(gate: Gate) -> Circuit:
    signals = {signal.name: signal for signal in gate.inputs}
    signals[gate.output.name] = gate.output
    circuit = Circuit(
        name="bt",
        signals=signals,
        gates=[gate],
        primary_inputs=[signal for signal in gate.inputs if signal.is_pi],
        primary_outputs=[gate.output],
    )
    levelize(circuit)
    return circuit


@pytest.mark.parametrize(
    ("gate_type", "desired", "input_index", "expected"),
    [
        (GateType.AND, Logic5.ZERO, 0, [("a", Logic5.ZERO)]),
        (GateType.AND, Logic5.ZERO, 1, [("b", Logic5.ZERO)]),
        (GateType.AND, Logic5.ONE, 0, [("a", Logic5.ONE), ("b", Logic5.ONE)]),
        (GateType.OR, Logic5.ZERO, 0, [("a", Logic5.ZERO), ("b", Logic5.ZERO)]),
        (GateType.OR, Logic5.ONE, 1, [("b", Logic5.ONE)]),
        (GateType.NAND, Logic5.ZERO, 0, [("a", Logic5.ONE), ("b", Logic5.ONE)]),
        (GateType.NAND, Logic5.ONE, 1, [("b", Logic5.ZERO)]),
        (GateType.NOR, Logic5.ZERO, 0, [("a", Logic5.ONE)]),
        (GateType.NOR, Logic5.ONE, 0, [("a", Logic5.ZERO), ("b", Logic5.ZERO)]),
    ],
)
def test_backtrace_two_input_gates(gate_type, desired, input_index, expected):
    gate = _two_input_gate(gate_type)
    assignments = backtrace(gate, desired, input_index)
    assert [(signal.name, value) for signal, value in assignments] == expected


def test_backtrace_not_and_buf():
    not_gate = _single_input_gate(GateType.NOT)
    assert backtrace(not_gate, Logic5.ZERO, 0) == [(not_gate.inputs[0], Logic5.ONE)]
    assert backtrace(not_gate, Logic5.ONE, 0) == [(not_gate.inputs[0], Logic5.ZERO)]

    buf_gate = _single_input_gate(GateType.BUF)
    assert backtrace(buf_gate, Logic5.ZERO, 0) == [(buf_gate.inputs[0], Logic5.ZERO)]
    assert backtrace(buf_gate, Logic5.ONE, 0) == [(buf_gate.inputs[0], Logic5.ONE)]


def test_backtrace_xor_with_known_other_input():
    gate = _two_input_gate(GateType.XOR)
    gate.inputs[1].value = Logic5.ZERO

    assert backtrace(gate, Logic5.ZERO, 0) == [(gate.inputs[0], Logic5.ZERO)]
    assert backtrace(gate, Logic5.ONE, 0) == [(gate.inputs[0], Logic5.ONE)]


def test_backtrace_xor_with_d_on_other_input():
    gate = _two_input_gate(GateType.XOR)
    gate.inputs[1].value = Logic5.D

    assert backtrace(gate, Logic5.ZERO, 0) == [(gate.inputs[0], Logic5.ONE)]
    assert backtrace(gate, Logic5.ONE, 0) == [(gate.inputs[0], Logic5.ZERO)]


def test_backtrace_xor_with_unknown_other_input_assigns_both():
    gate = _two_input_gate(GateType.XOR)

    assert backtrace(gate, Logic5.ZERO, 0) == [
        (gate.inputs[0], Logic5.ZERO),
        (gate.inputs[1], Logic5.ZERO),
    ]
    assert backtrace(gate, Logic5.ONE, 1) == [
        (gate.inputs[1], Logic5.ZERO),
        (gate.inputs[0], Logic5.ONE),
    ]


def test_backtrace_xnor_inverts_xor_desired():
    gate = _two_input_gate(GateType.XNOR)
    gate.inputs[1].value = Logic5.ONE

    assert backtrace(gate, Logic5.ONE, 0) == [(gate.inputs[0], Logic5.ONE)]
    assert backtrace(gate, Logic5.ZERO, 0) == [(gate.inputs[0], Logic5.ZERO)]


def test_backtrace_rejects_non_binary_desired():
    gate = _two_input_gate(GateType.AND)
    with pytest.raises(BacktraceError, match="ZERO or Logic5.ONE"):
        backtrace(gate, Logic5.X, 0)


def test_backtrace_rejects_invalid_input_index():
    gate = _two_input_gate(GateType.AND)
    with pytest.raises(BacktraceError, match="out of range"):
        backtrace(gate, Logic5.ZERO, 2)


def test_backtrace_not_rejects_nonzero_input_index():
    gate = _single_input_gate(GateType.NOT)
    with pytest.raises(BacktraceError, match="out of range"):
        backtrace(gate, Logic5.ZERO, 1)


def test_apply_backtrace_justifies_and_gate_output():
    gate = _two_input_gate(GateType.AND)
    circuit = _circuit_for_gate(gate)

    assert apply_backtrace(circuit, gate, Logic5.ONE, 0) is True
    assert circuit.signals["a"].value is Logic5.ONE
    assert circuit.signals["b"].value is Logic5.ONE
    assert circuit.signals["z"].value is Logic5.ONE


def test_apply_backtrace_detects_assignment_conflict():
    gate = _two_input_gate(GateType.AND)
    circuit = _circuit_for_gate(gate)
    circuit.signals["a"].value = Logic5.ZERO

    assert apply_backtrace(circuit, gate, Logic5.ONE, 0) is False
