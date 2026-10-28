"""Tests for Review-II metrics collection (no PODEM)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from review2_metrics_lib import (  # noqa: E402
    collect_all,
    collect_one_circuit,
    reduction_percent,
    validate_collapse_stages,
    write_data_json,
)
from generate_review2_report import generate_markdown  # noqa: E402

ISCAS = ROOT / "ISCAS85_Circuits"
C17 = ISCAS / "c17.v"


def test_reduction_percent_normal():
    assert reduction_percent(100, 40) == 60.0


def test_reduction_percent_zero_raw():
    assert reduction_percent(0, 0) is None


def test_validate_collapse_stages_detects_inconsistency():
    warnings = validate_collapse_stages(100, 120, 80)
    assert any("exceed raw" in w for w in warnings)
    warnings2 = validate_collapse_stages(100, 80, 90)
    assert any("dominance" in w and "equivalence" in w for w in warnings2)


def test_c17_collect_structure():
    record = collect_one_circuit(C17, timing_repetitions=1)
    assert record.parse_ok is True
    assert record.name == "c17"
    assert record.total_gates == 6
    assert record.raw_total is not None and record.raw_total > 0
    assert record.representatives_after_dominance is not None
    assert record.representatives_after_dominance <= record.representatives_after_equivalence
    assert record.partition_check_passed is True
    assert record.internal_wires == 4


def test_collect_all_writes_json(tmp_path: Path):
    out = tmp_path / "review2_data.json"
    payload = collect_all(
        ISCAS,
        timing_repetitions=1,
        collection_command="pytest",
    )
    write_data_json(payload, out)
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["metadata"]["schema"] == "review2_metrics_v1"
    assert loaded["summary"]["circuits_requested"] == 11
    assert "circuits" in loaded
    assert len(loaded["circuits"]) == 11
    names = {c["name"] for c in loaded["circuits"]}
    assert "c17" in names
    assert "ex1" not in names


def test_missing_benchmark_recorded(tmp_path: Path):
    empty_dir = tmp_path / "empty_iscas"
    empty_dir.mkdir()
    payload = collect_all(empty_dir, timing_repetitions=1, collection_command="pytest")
    assert payload["summary"]["parse_failed"] == 11
    assert payload["metadata"]["benchmarks_missing_files"]
    for circuit in payload["circuits"]:
        assert circuit["parse_ok"] is False


def test_report_generator_from_c17_subset(tmp_path: Path):
    payload = collect_all(ISCAS, timing_repetitions=1, collection_command="pytest")
    md = generate_markdown(payload)
    assert "PODEM is work in progress" in md
    assert "c17" in md
    assert "fault-list reduction" in md.lower() or "Reduction" in md
