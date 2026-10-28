from pathlib import Path

import pytest

from atpg.compaction import (
    PatternEntry,
    build_strict_rep_coverage,
    compact_patterns_strict,
    entries_from_podem_report,
    greedy_set_cover_reps,
    validate_selected_patterns_strict,
)
from atpg.compaction_dump import run_compaction_from_podem_report
from atpg.fault_sim import is_fault_detected
from circuit.levelize import levelize
from fault.collapsing import collapse_faults
from fault.fault import parse_fault_name
from parser.iscas_verilog import parse_iscas_verilog

ISCAS = Path(__file__).resolve().parents[2] / "ISCAS85_Circuits"
PATTERN = Path(__file__).resolve().parents[2] / "Pattern_prints"


def test_greedy_set_cover_toy():
    e1 = PatternEntry(index=1, origin_rep="a", pattern=(0,))
    e2 = PatternEntry(index=2, origin_rep="b", pattern=(1,))
    e3 = PatternEntry(index=3, origin_rep="c", pattern=(0,))
    entries = [e1, e2, e3]
    coverage = {1: {"r1", "r2"}, 2: {"r2"}, 3: {"r3"}}
    universe = {"r1", "r2", "r3"}
    selected, dropped = greedy_set_cover_reps(universe, entries, coverage)
    assert len(selected) == 2
    assert len(dropped) == 1
    covered = set()
    for entry in selected:
        covered |= coverage[entry.index]
    assert covered == universe


def test_c17_compaction_covers_all_reps(tmp_path):
    reports = sorted(PATTERN.glob("c17_podem_*.txt"))
    if not reports:
        pytest.skip("no c17 PODEM report")
    result, report_path, tp_path = run_compaction_from_podem_report(
        ISCAS / "c17.v",
        reports[-1],
        tmp_path,
    )
    assert result.complete
    assert result.validation_ok
    assert len(result.universe_reps) == 16
    assert result.compact_count <= result.original_count
    assert len(result.covered_reps) == 16
    assert report_path.is_file()
    assert tp_path.is_file()
    text = report_path.read_text(encoding="utf-8")
    assert "Vector validation  : PASS" in text
    assert "fault-free POs" in text
    assert "faulty POs" in text
    assert "Primary inputs (pattern bit order):" in text


def test_strict_coverage_and_validation_on_c17():
    reports = sorted(PATTERN.glob("c17_podem_*.txt"))
    if not reports:
        pytest.skip("no c17 PODEM report")
    circuit = parse_iscas_verilog(ISCAS / "c17.v")
    levelize(circuit)
    collapsed = collapse_faults(circuit)
    entries = entries_from_podem_report(reports[-1])
    universe = set(collapsed.collapse_map.keys())
    coverage = build_strict_rep_coverage(circuit, entries, universe)
    frozen = {index: frozenset(s) for index, s in coverage.items()}
    for entry in entries:
        assert entry.origin_rep in coverage[entry.index]
        assert is_fault_detected(
            circuit, parse_fault_name(entry.origin_rep), entry.pattern
        )
    result = compact_patterns_strict(circuit, collapsed.collapse_map, entries)
    ok, errors = validate_selected_patterns_strict(
        circuit, result.selected, result.coverage_by_index
    )
    assert ok
    assert not errors
    assert result.validation_ok
