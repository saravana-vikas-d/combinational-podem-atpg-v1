import pytest

from circuit.circuit import GateType
from logic5 import Logic5, eval_and, eval_gate, eval_not, eval_or, eval_xor


def test_logic5_display():
    assert str(Logic5.ZERO) == "0"
    assert str(Logic5.DBAR) == "D'"


def test_and_basic():
    assert eval_and(Logic5.ONE, Logic5.ONE) is Logic5.ONE
    assert eval_and(Logic5.ZERO, Logic5.ONE) is Logic5.ZERO
    assert eval_and(Logic5.ONE, Logic5.X) is Logic5.X


def test_and_with_d():
    assert eval_and(Logic5.D, Logic5.ONE) is Logic5.D
    assert eval_and(Logic5.D, Logic5.ZERO) is Logic5.ZERO
    assert eval_and(Logic5.D, Logic5.D) is Logic5.D


def test_or_with_d():
    assert eval_or(Logic5.D, Logic5.ZERO) is Logic5.D
    assert eval_or(Logic5.D, Logic5.ONE) is Logic5.ONE


def test_not_d():
    assert eval_not(Logic5.D) is Logic5.DBAR
    assert eval_not(Logic5.DBAR) is Logic5.D


def test_xor_with_d():
    assert eval_xor(Logic5.D, Logic5.ZERO) is Logic5.D
    assert eval_xor(Logic5.D, Logic5.ONE) is Logic5.DBAR


@pytest.mark.parametrize(
    ("gate_type", "inputs", "expected"),
    [
        (GateType.AND, [Logic5.ONE, Logic5.D], Logic5.D),
        (GateType.NAND, [Logic5.ONE, Logic5.D], Logic5.DBAR),
        (GateType.OR, [Logic5.ZERO, Logic5.D], Logic5.D),
        (GateType.NOR, [Logic5.ZERO, Logic5.D], Logic5.DBAR),
        (GateType.BUF, [Logic5.D], Logic5.D),
        (GateType.NOT, [Logic5.D], Logic5.DBAR),
        (GateType.XNOR, [Logic5.D, Logic5.ZERO], Logic5.DBAR),
    ],
)
def test_eval_gate(gate_type, inputs, expected):
    assert eval_gate(gate_type, inputs) is expected


def test_eval_gate_multi_input_and():
    assert eval_gate(GateType.AND, [Logic5.ONE, Logic5.ONE, Logic5.D]) is Logic5.D
    assert eval_gate(GateType.OR, [Logic5.ZERO, Logic5.ZERO, Logic5.D]) is Logic5.D


def test_eval_gate_multi_input_nine_and():
    inputs = [Logic5.ONE] * 8 + [Logic5.D]
    assert eval_gate(GateType.AND, inputs) is Logic5.D


def test_eval_gate_multi_input_inverting_gates():
    # NAND(1,1,1) = 0 — cascading eval_nand would incorrectly yield 1
    assert eval_gate(GateType.NAND, [Logic5.ONE, Logic5.ONE, Logic5.ONE]) is Logic5.ZERO
    # NOR(0,0,0) = 1
    assert eval_gate(GateType.NOR, [Logic5.ZERO, Logic5.ZERO, Logic5.ZERO]) is Logic5.ONE
    # XNOR(1,1,1) = 1 (odd number of ones → xor=1 → xnor=0)... XOR(1,1,1)=1, NOT=0
    assert eval_gate(GateType.XNOR, [Logic5.ONE, Logic5.ONE, Logic5.ONE]) is Logic5.ZERO


def test_eval_gate_multi_input_nand_with_d():
    assert eval_gate(GateType.NAND, [Logic5.D, Logic5.ONE, Logic5.ONE]) is Logic5.DBAR
    assert eval_gate(GateType.NAND, [Logic5.ONE, Logic5.D, Logic5.ONE]) is Logic5.DBAR


def test_eval_gate_empty_inputs():
    with pytest.raises(ValueError, match="at least one input"):
        eval_gate(GateType.AND, [])


def test_eval_gate_not_requires_one_input():
    with pytest.raises(ValueError, match="exactly one input"):
        eval_gate(GateType.NOT, [Logic5.ZERO, Logic5.ONE])
