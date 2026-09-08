from pathlib import Path

import pytest

from parser.verilog_utils import ParseError, iter_statements, split_identifiers, strip_comment_lines

ISCAS = Path(__file__).resolve().parents[2] / "ISCAS85_Circuits"


def test_strip_comment_lines():
    lines = ["// Ninputs 5\n", "input N1;\n", "\n", "// tail\n"]
    assert list(strip_comment_lines(lines)) == ["input N1;\n", "\n"]


def test_split_identifiers_multiline():
    text = "N1,N8,N15,\n      N141,N148"
    assert split_identifiers(text) == ["N1", "N8", "N15", "N141", "N148"]


def test_split_identifiers_underscore_names():
    assert split_identifiers("N241_I,N241_O") == ["N241_I", "N241_O"]


def test_iter_statements_joins_until_semicolon():
    lines = [
        "input N1,N8,N15,\n",
        "      N141,N148;\n",
        "wire N10;\n",
    ]
    assert list(iter_statements(lines)) == [
        "input N1,N8,N15,N141,N148;",
        "wire N10;",
    ]


def test_iter_statements_c17():
    lines = (ISCAS / "c17.v").read_text(encoding="utf-8").splitlines(keepends=True)
    statements = list(iter_statements(lines))
    assert statements[0].lower().startswith("module c17")
    assert "input N1,N2,N3,N6,N7;" in statements
    assert "output N22,N23;" in statements
    assert "wire N10,N11,N16,N19;" in statements
    assert statements[-1] == "endmodule"


def test_iter_statements_rejects_endmodule_with_semicolon():
    with pytest.raises(ParseError, match="endmodule must not be terminated with a semicolon"):
        list(iter_statements(["endmodule;"]))


def test_iter_statements_unterminated():
    with pytest.raises(ParseError, match="unterminated statement"):
        list(iter_statements(["input N1\n"]))
