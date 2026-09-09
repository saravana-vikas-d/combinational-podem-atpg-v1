from pathlib import Path

import pytest

from circuit.circuit import Gate, GateType, Signal
from logic5 import Logic5
from parser.iscas_verilog import _ParseContext, _apply_statement, parse_iscas_verilog
from parser.verilog_utils import ParseError

ISCAS = Path(__file__).resolve().parents[2] / "ISCAS85_Circuits"


def _assert_signal(
    signal: Signal,
    *,
    name: str,
    is_pi: bool = False,
    is_po: bool = False,
    driver: Gate | None = None,
    fanouts: list[tuple[Gate, int]] | None = None,
    level: int = -1,
    value: Logic5 = Logic5.X,
) -> None:
    assert signal.name == name
    assert signal.is_pi is is_pi
    assert signal.is_po is is_po
    assert signal.driver is driver
    assert signal.fanouts == (fanouts if fanouts is not None else [])
    assert signal.level == level
    assert signal.value is value


def _assert_gate(
    gate: Gate,
    circuit,
    *,
    gate_id: int,
    instance_name: str,
    gate_type: GateType,
    input_names: list[str],
    output_name: str,
    level: int = -1,
) -> None:
    assert gate.id == gate_id
    assert gate.instance_name == instance_name
    assert gate.type is gate_type
    assert gate.level == level
    assert [signal.name for signal in gate.inputs] == input_names
    assert gate.output.name == output_name
    assert gate.output is circuit.signals[output_name]
    for index, name in enumerate(input_names):
        assert gate.inputs[index] is circuit.signals[name]


def test_c17():
    circuit = parse_iscas_verilog(ISCAS / "c17.v")

    assert circuit.name == "c17"
    assert circuit.levels == []
    assert len(circuit.gates) == 6

    expected_pi_names = ["N1", "N2", "N3", "N6", "N7"]
    expected_po_names = ["N22", "N23"]
    expected_wire_names = ["N10", "N11", "N16", "N19"]
    expected_signal_names = expected_pi_names + expected_po_names + expected_wire_names

    assert len(circuit.signals) == len(expected_signal_names)
    assert set(circuit.signals) == set(expected_signal_names)
    assert list(circuit.signals.keys()) == expected_signal_names

    assert [signal.name for signal in circuit.primary_inputs] == expected_pi_names
    assert [signal.name for signal in circuit.primary_outputs] == expected_po_names

    g0, g1, g2, g3, g4, g5 = circuit.gates

    _assert_gate(
        g0,
        circuit,
        gate_id=0,
        instance_name="NAND2_1",
        gate_type=GateType.NAND,
        input_names=["N1", "N3"],
        output_name="N10",
    )
    _assert_gate(
        g1,
        circuit,
        gate_id=1,
        instance_name="NAND2_2",
        gate_type=GateType.NAND,
        input_names=["N3", "N6"],
        output_name="N11",
    )
    _assert_gate(
        g2,
        circuit,
        gate_id=2,
        instance_name="NAND2_3",
        gate_type=GateType.NAND,
        input_names=["N2", "N11"],
        output_name="N16",
    )
    _assert_gate(
        g3,
        circuit,
        gate_id=3,
        instance_name="NAND2_4",
        gate_type=GateType.NAND,
        input_names=["N11", "N7"],
        output_name="N19",
    )
    _assert_gate(
        g4,
        circuit,
        gate_id=4,
        instance_name="NAND2_5",
        gate_type=GateType.NAND,
        input_names=["N10", "N16"],
        output_name="N22",
    )
    _assert_gate(
        g5,
        circuit,
        gate_id=5,
        instance_name="NAND2_6",
        gate_type=GateType.NAND,
        input_names=["N16", "N19"],
        output_name="N23",
    )

    _assert_signal(circuit.signals["N1"], name="N1", is_pi=True, fanouts=[(g0, 0)])
    _assert_signal(circuit.signals["N2"], name="N2", is_pi=True, fanouts=[(g2, 0)])
    _assert_signal(
        circuit.signals["N3"],
        name="N3",
        is_pi=True,
        fanouts=[(g0, 1), (g1, 0)],
    )
    _assert_signal(circuit.signals["N6"], name="N6", is_pi=True, fanouts=[(g1, 1)])
    _assert_signal(circuit.signals["N7"], name="N7", is_pi=True, fanouts=[(g3, 1)])

    _assert_signal(
        circuit.signals["N10"],
        name="N10",
        driver=g0,
        fanouts=[(g4, 0)],
    )
    _assert_signal(
        circuit.signals["N11"],
        name="N11",
        driver=g1,
        fanouts=[(g2, 1), (g3, 0)],
    )
    _assert_signal(
        circuit.signals["N16"],
        name="N16",
        driver=g2,
        fanouts=[(g4, 1), (g5, 0)],
    )
    _assert_signal(
        circuit.signals["N19"],
        name="N19",
        driver=g3,
        fanouts=[(g5, 1)],
    )

    _assert_signal(
        circuit.signals["N22"],
        name="N22",
        is_po=True,
        driver=g4,
    )
    _assert_signal(
        circuit.signals["N23"],
        name="N23",
        is_po=True,
        driver=g5,
    )

    for index, name in enumerate(expected_pi_names):
        assert circuit.primary_inputs[index] is circuit.signals[name]
    for index, name in enumerate(expected_po_names):
        assert circuit.primary_outputs[index] is circuit.signals[name]


def test_c432():
    circuit = parse_iscas_verilog(ISCAS / "c432.v")

    assert circuit.name == "c432"
    assert len(circuit.primary_inputs) == 36
    assert len(circuit.primary_outputs) == 7
    assert len(circuit.gates) == 160
    assert len([name for name, signal in circuit.signals.items() if not signal.is_pi and not signal.is_po]) == 153


def test_c1355_compact_gate_syntax():
    circuit = parse_iscas_verilog(ISCAS / "c1355.v")

    assert circuit.name == "c1355"
    assert len(circuit.primary_inputs) == 41
    assert len(circuit.primary_outputs) == 32
    assert len(circuit.gates) == 546


def test_module_keyword_is_case_sensitive():
    context = _ParseContext()

    with pytest.raises(ParseError, match="statement before module declaration"):
        _apply_statement(context, "MODULE c17 (N1);")


def test_duplicate_identifier_in_input_declaration(tmp_path):
    verilog = """\
module m (a);
input a, a;
endmodule
"""
    path = tmp_path / "dup.v"
    path.write_text(verilog, encoding="utf-8")

    with pytest.raises(ParseError, match="duplicate identifier 'a' in input declaration"):
        parse_iscas_verilog(path)


def test_duplicate_input_across_statements(tmp_path):
    verilog = """\
module m (a);
input a;
input a;
endmodule
"""
    path = tmp_path / "dup_input.v"
    path.write_text(verilog, encoding="utf-8")

    with pytest.raises(ParseError, match="duplicate input declaration for 'a'"):
        parse_iscas_verilog(path)


def test_duplicate_wire_declaration(tmp_path):
    verilog = """\
module m (a, b);
input a;
output b;
wire w;
wire w;
endmodule
"""
    path = tmp_path / "dup_wire.v"
    path.write_text(verilog, encoding="utf-8")

    with pytest.raises(ParseError, match="duplicate wire declaration for 'w'"):
        parse_iscas_verilog(path)


def test_module_port_list_mismatch(tmp_path):
    verilog = """\
module m (a, b, extra);
input a;
output b;
endmodule
"""
    path = tmp_path / "mismatch.v"
    path.write_text(verilog, encoding="utf-8")

    with pytest.raises(
        ParseError,
        match="module port list does not match input/output declarations",
    ):
        parse_iscas_verilog(path)


def test_duplicate_module_port(tmp_path):
    verilog = """\
module m (a, a);
input a;
endmodule
"""
    path = tmp_path / "dup_port.v"
    path.write_text(verilog, encoding="utf-8")

    with pytest.raises(ParseError, match="duplicate identifier 'a' in module port list"):
        parse_iscas_verilog(path)


def test_endmodule_with_semicolon_is_error(tmp_path):
    verilog = """\
module m (a);
input a;
endmodule;
"""
    path = tmp_path / "bad_endmodule.v"
    path.write_text(verilog, encoding="utf-8")

    with pytest.raises(ParseError, match="endmodule must not be terminated with a semicolon"):
        parse_iscas_verilog(path)


def _mini_context() -> _ParseContext:
    context = _ParseContext()
    _apply_statement(context, "module m (a, b, w);")
    _apply_statement(context, "input a;")
    _apply_statement(context, "output b;")
    _apply_statement(context, "wire w;")
    return context


def test_gate_undeclared_signal():
    context = _mini_context()

    with pytest.raises(ParseError, match="undeclared signal 'missing'"):
        _apply_statement(context, "nand G1 (w, a, missing);")


def test_gate_multi_driver():
    context = _mini_context()
    _apply_statement(context, "nand G1 (w, a, b);")

    with pytest.raises(ParseError, match="signal 'w' is already driven"):
        _apply_statement(context, "nand G2 (w, a, b);")


def test_gate_primary_input_as_output():
    context = _mini_context()

    with pytest.raises(ParseError, match="primary input 'a' cannot be a gate output"):
        _apply_statement(context, "nand G1 (a, b, w);")


def test_gate_not_pin_count():
    context = _mini_context()

    with pytest.raises(ParseError, match="NOT1: not expects 2 pins"):
        _apply_statement(context, "not NOT1 (w, a, b);")


def test_gate_nand_requires_at_least_two_inputs():
    context = _mini_context()

    with pytest.raises(ParseError, match="G1: nand expects at least 3 pins"):
        _apply_statement(context, "nand G1 (w, a);")
