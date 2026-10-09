from io import StringIO
from pathlib import Path

from atpg.podem import podem
from atpg.stack_dump import (
    DecisionStackRecorder,
    select_edge_faults,
    write_edge_fault_objective_steps,
)
from circuit.levelize import levelize
from fault.fault import parse_fault_name
from parser.iscas_verilog import parse_iscas_verilog

ISCAS = Path(__file__).resolve().parents[2] / "ISCAS85_Circuits"


def test_select_edge_faults_merges_overlap():
    names = [f"f{index}" for index in range(7)]
    selected = select_edge_faults(names, edge=5)

    assert [name for name, _role in selected] == names
    roles = dict(selected)
    assert roles["f0"] == "first #1 of 7"
    assert roles["f2"] == "first #3 of 7; last #5 of 7"
    assert roles["f6"] == "last #1 of 7"


def test_select_edge_faults_keeps_batch_order():
    names = [f"f{index}" for index in range(12)]
    selected = select_edge_faults(names, edge=5)

    assert [name for name, _role in selected] == [
        "f0",
        "f1",
        "f2",
        "f3",
        "f4",
        "f7",
        "f8",
        "f9",
        "f10",
        "f11",
    ]
    assert dict(selected)["f11"] == "last #1 of 12"


def test_objective_step_log_prints_queue_and_stack():
    circuit = parse_iscas_verilog(ISCAS / "c17.v")
    levelize(circuit)
    sink = StringIO()
    recorder = DecisionStackRecorder(fault_name="N10_sa1")
    recorder.step_sink = sink

    result = podem(
        circuit,
        parse_fault_name("N10_sa1"),
        backtrack_limit=10000,
        recursion_limit=200,
        stack_recorder=recorder,
    )

    text = sink.getvalue()
    assert result.status == "success"
    assert recorder.step_count >= 1
    assert "STEP 1" in text
    assert "Objective queue (index 0 = current objective):" in text
    assert "Decision stack (bottom = oldest branch, top = current):" in text
    assert "N10=0" in text


def test_write_edge_fault_objective_steps_on_c17(tmp_path):
    path = write_edge_fault_objective_steps(
        ISCAS / "c17.v",
        tmp_path,
        edge=5,
        recursion_limit=200,
        backtrack_limit=10000,
    )

    text = path.read_text(encoding="utf-8")
    assert "PODEM objective-step debug: c17" in text
    assert "ABORTED  total=0  tracing=0" in text
    assert "UNTESTABLE  total=0  tracing=0" in text
    assert "(no aborted faults)" in text
    assert "(no untestable faults)" in text
