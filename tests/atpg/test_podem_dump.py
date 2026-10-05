from pathlib import Path

from atpg.dump import format_test_patterns_tp, print_podem_from_file
from parser.iscas_verilog import parse_iscas_verilog

ISCAS = Path(__file__).resolve().parents[2] / "ISCAS85_Circuits"


def test_print_podem_from_file_writes_c17_patterns(tmp_path):
    report_path, tp_path = print_podem_from_file(
        ISCAS / "c17.v",
        tmp_path,
        recursion_limit=200,
        backtrack_limit=10000,
    )

    assert report_path.is_file()
    assert tp_path.is_file()
    assert report_path.name.startswith("c17_podem_")
    assert tp_path.name.startswith("c17_test_patterns_")

    tp_text = tp_path.read_text(encoding="utf-8")
    if tp_text:
        for line in tp_text.strip().splitlines():
            assert all(ch in "01X" for ch in line)

    report_text = report_path.read_text(encoding="utf-8")
    assert "Primary inputs (pattern bit order): N1, N2, N3, N6, N7" in report_text


def test_format_test_patterns_tp_empty():
    from atpg.podem import PodemBatchResult

    assert format_test_patterns_tp(PodemBatchResult([], [], [], {}, set())) == ""
