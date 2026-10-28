from pathlib import Path

import pytest

from atpg.fault_sim import (
    is_fault_detected,
    parse_pattern,
    parse_podem_report_patterns,
)
from atpg.fault_sim_dump import run_fault_sim_from_podem_report
from circuit.circuit import Circuit, Gate, GateType, Signal
from circuit.levelize import levelize
from fault.fault import line_fault
from logic5 import Logic5
from parser.iscas_verilog import parse_iscas_verilog

ISCAS = Path(__file__).resolve().parents[2] / "ISCAS85_Circuits"
PATTERN = Path(__file__).resolve().parents[2] / "Pattern_prints"


def test_parse_pattern():
    assert parse_pattern("10X1") == (1, 0, None, 1)


def test_is_fault_detected_on_inverter():
    inp = Signal("a", is_pi=True)
    out = Signal("z", is_po=True)
    gate = Gate(
        id=0,
        instance_name="NOT1",
        type=GateType.NOT,
        inputs=[inp],
        output=out,
    )
    out.driver = gate
    inp.fanouts.append((gate, 0))
    circuit = Circuit(
        name="inv",
        signals={"a": inp, "z": out},
        gates=[gate],
        primary_inputs=[inp],
        primary_outputs=[out],
    )
    levelize(circuit)

    fault = line_fault("a", 1)
    assert is_fault_detected(circuit, fault, (0,))


def test_c17_podem_report_validates(tmp_path):
    reports = sorted(PATTERN.glob("c17_podem_*.txt"))
    if not reports:
        pytest.skip("no c17 PODEM report in Pattern_prints/")
    report, path = run_fault_sim_from_podem_report(
        ISCAS / "c17.v",
        reports[-1],
        tmp_path,
    )
    assert report.validation_ok
    assert len(report.rows) == 16
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "fault-free POs" in text
    assert "faulty POs" in text


def test_redundant_branch_sa1_when_stem_is_one():
    from atpg.fault_sim import parse_pattern, simulate_faulty_outputs
    from fault.fault import parse_fault_name

    circuit = parse_iscas_verilog(ISCAS / "c17.v")
    levelize(circuit)
    fault = parse_fault_name("N16__NAND2_6_0_sa1")
    _, ok, detected = simulate_faulty_outputs(circuit, fault, parse_pattern("X0111"))
    assert ok
    assert not detected
    reports = sorted(PATTERN.glob("c17_podem_*.txt"))
    if not reports:
        pytest.skip("no c17 PODEM report")
    entries = parse_podem_report_patterns(reports[-1])
    assert entries[0][0] == "N10_sa1"
    assert entries[0][1] == parse_pattern("101XX")
