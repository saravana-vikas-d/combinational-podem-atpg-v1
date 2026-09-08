"""Five-valued logic for ATPG: 0, 1, X, D, D'.

Each value encodes good-circuit and faulty-circuit logic:
  0   good=0, faulty=0
  1   good=1, faulty=1
  X   unknown on one or both rails
  D   good=1, faulty=0
  D'  good=0, faulty=1
"""

from __future__ import annotations

from enum import Enum, auto

from circuit.circuit import GateType

# Ternary rail: 0, 1, or unknown (None)
_Rail = int | None


class Logic5(Enum):
    ZERO = auto()
    ONE = auto()
    X = auto()
    D = auto()
    DBAR = auto()  # D'

    def __str__(self) -> str:
        return _DISPLAY[self]

    @property
    def display(self) -> str:
        return _DISPLAY[self]


_DISPLAY = {
    Logic5.ZERO: "0",
    Logic5.ONE: "1",
    Logic5.X: "X",
    Logic5.D: "D",
    Logic5.DBAR: "D'",
}


def _split(value: Logic5) -> tuple[_Rail, _Rail]:
    """Decode a Logic5 value into (good, faulty) rails."""
    match value:
        case Logic5.ZERO:
            return 0, 0
        case Logic5.ONE:
            return 1, 1
        case Logic5.X:
            return None, None
        case Logic5.D:
            return 1, 0
        case Logic5.DBAR:
            return 0, 1
    raise AssertionError(f"unhandled Logic5 value: {value}")


def _merge(good: _Rail, faulty: _Rail) -> Logic5:
    """Encode (good, faulty) rails back into Logic5."""
    if good == 0 and faulty == 0:
        return Logic5.ZERO
    if good == 1 and faulty == 1:
        return Logic5.ONE
    if good == 1 and faulty == 0:
        return Logic5.D
    if good == 0 and faulty == 1:
        return Logic5.DBAR
    return Logic5.X


def _and_rail(a: _Rail, b: _Rail) -> _Rail:
    if a == 0 or b == 0:
        return 0
    if a == 1 and b == 1:
        return 1
    return None


def _or_rail(a: _Rail, b: _Rail) -> _Rail:
    if a == 1 or b == 1:
        return 1
    if a == 0 and b == 0:
        return 0
    return None


def _not_rail(a: _Rail) -> _Rail:
    if a == 0:
        return 1
    if a == 1:
        return 0
    return None


def _xor_rail(a: _Rail, b: _Rail) -> _Rail:
    if a is None or b is None:
        return None
    return a ^ b


def eval_and(a: Logic5, b: Logic5) -> Logic5:
    good_a, faulty_a = _split(a)
    good_b, faulty_b = _split(b)
    return _merge(_and_rail(good_a, good_b), _and_rail(faulty_a, faulty_b))


def eval_or(a: Logic5, b: Logic5) -> Logic5:
    good_a, faulty_a = _split(a)
    good_b, faulty_b = _split(b)
    return _merge(_or_rail(good_a, good_b), _or_rail(faulty_a, faulty_b))


def eval_nand(a: Logic5, b: Logic5) -> Logic5:
    return eval_not(eval_and(a, b))


def eval_nor(a: Logic5, b: Logic5) -> Logic5:
    return eval_not(eval_or(a, b))


def eval_not(a: Logic5) -> Logic5:
    good, faulty = _split(a)
    return _merge(_not_rail(good), _not_rail(faulty))


def eval_buf(a: Logic5) -> Logic5:
    return a


def eval_xor(a: Logic5, b: Logic5) -> Logic5:
    good_a, faulty_a = _split(a)
    good_b, faulty_b = _split(b)
    return _merge(_xor_rail(good_a, good_b), _xor_rail(faulty_a, faulty_b))


def eval_xnor(a: Logic5, b: Logic5) -> Logic5:
    return eval_not(eval_xor(a, b))


def _fold(base_fn, inputs: list[Logic5]) -> Logic5:
    result = inputs[0]
    for value in inputs[1:]:
        result = base_fn(result, value)
    return result


def eval_gate(gate_type: GateType, inputs: list[Logic5]) -> Logic5:
    """Evaluate a primitive gate over five-valued inputs.

    Multi-input AND/OR/XOR fold associatively. NAND/NOR/XNOR fold the
    non-inverting primitive first, then invert once (cascading eval_nand
    would apply multiple inversions incorrectly).
    NOT and BUF require exactly one input.
    """
    if not inputs:
        raise ValueError("gate evaluation requires at least one input")

    if gate_type is GateType.NOT:
        if len(inputs) != 1:
            raise ValueError("NOT gate requires exactly one input")
        return eval_not(inputs[0])

    if gate_type is GateType.BUF:
        if len(inputs) != 1:
            raise ValueError("BUF gate requires exactly one input")
        return eval_buf(inputs[0])

    if gate_type is GateType.AND:
        return _fold(eval_and, inputs)
    if gate_type is GateType.OR:
        return _fold(eval_or, inputs)
    if gate_type is GateType.NAND:
        return eval_not(_fold(eval_and, inputs))
    if gate_type is GateType.NOR:
        return eval_not(_fold(eval_or, inputs))
    if gate_type is GateType.XOR:
        return _fold(eval_xor, inputs)
    if gate_type is GateType.XNOR:
        return eval_not(_fold(eval_xor, inputs))

    raise ValueError(f"unsupported gate type for evaluation: {gate_type}")
