from pathlib import Path

import pytest

from parser.iscas_verilog import _ParseContext, _apply_statement, parse_iscas_declarations
from parser.verilog_utils import ParseError

ISCAS = Path(__file__).resolve().parents[2] / "ISCAS85_Circuits"


def test_c17_declarations():
    circuit = parse_iscas_declarations(ISCAS / "c17.v")

    assert circuit.name == "c17"
    assert len(circuit.primary_inputs) == 5
    assert len(circuit.primary_outputs) == 2
    assert [signal.name for signal in circuit.primary_inputs] == [
        "N1",
        "N2",
        "N3",
        "N6",
        "N7",
    ]
    assert [signal.name for signal in circuit.primary_outputs] == ["N22", "N23"]
    assert len(circuit.signals) == 11
    assert set(circuit.signals) == {
        "N1",
        "N2",
        "N3",
        "N6",
        "N7",
        "N22",
        "N23",
        "N10",
        "N11",
        "N16",
        "N19",
    }
    assert circuit.gates == []
    assert circuit.primary_inputs[0] is circuit.signals["N1"]
    assert circuit.signals["N10"].is_pi is False
    assert circuit.signals["N10"].is_po is False
    assert circuit.signals["N1"].driver is None


def test_c432_declarations():
    circuit = parse_iscas_declarations(ISCAS / "c432.v")

    assert circuit.name == "c432"
    assert len(circuit.primary_inputs) == 36
    assert len(circuit.primary_outputs) == 7
    assert len([name for name, signal in circuit.signals.items() if not signal.is_pi and not signal.is_po]) == 153


def test_c1355_declarations_without_header():
    circuit = parse_iscas_declarations(ISCAS / "c1355.v")

    assert circuit.name == "c1355"
    assert len(circuit.primary_inputs) == 41
    assert len(circuit.primary_outputs) == 32


def test_gate_lines_are_ignored_for_now():
    circuit = parse_iscas_declarations(ISCAS / "c17.v")
    assert circuit.gates == []


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
        parse_iscas_declarations(path)


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
        parse_iscas_declarations(path)


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
        parse_iscas_declarations(path)


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
        parse_iscas_declarations(path)


def test_duplicate_module_port(tmp_path):
    verilog = """\
module m (a, a);
input a;
endmodule
"""
    path = tmp_path / "dup_port.v"
    path.write_text(verilog, encoding="utf-8")

    with pytest.raises(ParseError, match="duplicate identifier 'a' in module port list"):
        parse_iscas_declarations(path)


def test_endmodule_with_semicolon_is_error(tmp_path):
    verilog = """\
module m (a);
input a;
endmodule;
"""
    path = tmp_path / "bad_endmodule.v"
    path.write_text(verilog, encoding="utf-8")

    with pytest.raises(ParseError, match="endmodule must not be terminated with a semicolon"):
        parse_iscas_declarations(path)
