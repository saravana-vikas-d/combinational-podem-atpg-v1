import pytest

from circuit.circuit import GateType


def test_from_v_nand():
    assert GateType.from_v("nand") is GateType.NAND


def test_from_v_case_insensitive():
    assert GateType.from_v("NAND") is GateType.NAND
    assert GateType.from_v("And") is GateType.AND


@pytest.mark.parametrize(
    ("keyword", "expected"),
    [
        ("and", GateType.AND),
        ("or", GateType.OR),
        ("nand", GateType.NAND),
        ("nor", GateType.NOR),
        ("not", GateType.NOT),
        ("buf", GateType.BUF),
        ("xor", GateType.XOR),
        ("xnor", GateType.XNOR),
    ],
)
def test_from_v_all_keywords(keyword, expected):
    assert GateType.from_v(keyword) is expected


def test_from_v_unknown():
    with pytest.raises(ValueError, match="unsupported gate type: 'flipflop'"):
        GateType.from_v("flipflop")
