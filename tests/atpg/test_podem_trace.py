from pathlib import Path

from atpg.trace_dump import format_podem_trace, print_podem_trace_from_file, run_podem_with_trace
from circuit.levelize import levelize
from fault.fault import line_fault
from parser.iscas_verilog import parse_iscas_verilog

ISCAS = Path(__file__).resolve().parents[2] / "ISCAS85_Circuits"


def test_run_podem_with_trace_success_contains_po_detected():
    circuit = parse_iscas_verilog(ISCAS / "c17.v")
    levelize(circuit)

    trace, result = run_podem_with_trace(circuit, line_fault("N3", 0), max_events=500)

    assert result.status == "success"
    kinds = [event.kind for event in trace.events]
    assert "fault_excitation" in kinds
    assert "init" in kinds
    assert "po_detected" in kinds
    assert any(event.process == "forward_implication" for event in trace.events)
    assert trace.result_status == "success"


def test_print_podem_trace_from_file_writes_c17(tmp_path):
    path = print_podem_trace_from_file(
        ISCAS / "c17.v",
        ["N3_sa0", "N1_sa1"],
        tmp_path,
        recursion_limit=200,
        backtrack_limit=10000,
        max_events=400,
    )

    text = path.read_text(encoding="utf-8")
    assert path.name.startswith("c17_podem_trace_")
    assert "N3_sa0" in text
    assert "N1_sa1" in text
    assert "process=forward_implication" in text
    assert "process=backtrace" in text
    assert "step=fault_excitation" in text
