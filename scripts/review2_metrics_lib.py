"""Review-II metrics: circuit parser and fault-collapsing measurements (no PODEM)."""

from __future__ import annotations

import json
import platform
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from circuit.circuit import Circuit, GateType
from fault.collapsing import (
    collapse_dominance,
    collapse_equivalence,
    collapse_map_keys,
    verify_collapse_partition,
)
from fault.fault import Fault, generate_raw_faults
from parser.iscas_verilog import parse_iscas_verilog
from parser.verilog_utils import ParseError

CANONICAL_BENCHMARKS = (
    "c17",
    "c432",
    "c499",
    "c880",
    "c1355",
    "c1908",
    "c2670",
    "c3540",
    "c5315",
    "c6288",
    "c7552",
)

PARSE_TIME_DEFINITION = (
    "Wall time for parse_iscas_verilog(path): read file, build circuit, "
    "validate(check_unused=True), and levelize. Does not include fault generation."
)
COLLAPSE_TIME_DEFINITION = (
    "Wall time for generate_raw_faults(circuit) + collapse_equivalence + "
    "collapse_dominance on a freshly parsed circuit each repetition."
)
INTERNAL_WIRES_DEFINITION = (
    "Signals where is_pi is False and is_po is False."
)
LOGIC_DEPTH_DEFINITION = "Maximum gate.level after levelization (0-based levels from PIs)."

PODEM_DISCLAIMER = (
    "PODEM is work in progress. This report evaluates parser and fault-collapsing "
    "measurements only; it does not establish end-to-end ATPG correctness or "
    "validated fault coverage."
)


@dataclass
class TimingStats:
    median_ms: float | None = None
    min_ms: float | None = None
    max_ms: float | None = None
    samples_ms: list[float] = field(default_factory=list)


@dataclass
class CircuitRecord:
    name: str
    input_file: str
    parse_ok: bool
    parse_error: str | None = None
    parse_time: TimingStats = field(default_factory=TimingStats)
    primary_inputs: int | None = None
    primary_outputs: int | None = None
    total_signals: int | None = None
    internal_wires: int | None = None
    total_gates: int | None = None
    gate_type_counts: dict[str, int] = field(default_factory=dict)
    max_gate_fanin: int | None = None
    max_signal_fanout: int | None = None
    logic_depth: int | None = None
    raw_line_sa0: int | None = None
    raw_line_sa1: int | None = None
    raw_branch_sa0: int | None = None
    raw_branch_sa1: int | None = None
    raw_total: int | None = None
    unique_fault_names: int | None = None
    duplicate_fault_names: int | None = None
    representatives_after_equivalence: int | None = None
    representatives_after_dominance: int | None = None
    removed_by_equivalence: int | None = None
    removed_by_dominance_additional: int | None = None
    overall_reduction_percent: float | None = None
    collapse_pipeline_time: TimingStats = field(default_factory=TimingStats)
    partition_check_passed: bool | None = None
    partition_check_error: str | None = None
    metrics_warnings: list[str] = field(default_factory=list)


def reduction_percent(raw: int, final: int) -> float | None:
    if raw <= 0:
        return None
    return 100.0 * (raw - final) / raw


def validate_collapse_stages(
    raw: int,
    after_equiv: int,
    after_dom: int,
) -> list[str]:
    warnings: list[str] = []
    if after_equiv > raw:
        warnings.append(
            f"representatives after equivalence ({after_equiv}) exceed raw count ({raw})"
        )
    if after_dom > after_equiv:
        warnings.append(
            f"representatives after dominance ({after_dom}) exceed "
            f"after equivalence ({after_equiv})"
        )
    if after_dom > raw:
        warnings.append(
            f"representatives after dominance ({after_dom}) exceed raw count ({raw})"
        )
    return warnings


def _timing_stats(samples: list[float]) -> TimingStats:
    if not samples:
        return TimingStats()
    return TimingStats(
        median_ms=statistics.median(samples),
        min_ms=min(samples),
        max_ms=max(samples),
        samples_ms=samples,
    )


def _classify_raw_faults(faults: list[Fault]) -> dict[str, int]:
    line_sa0 = line_sa1 = branch_sa0 = branch_sa1 = 0
    for fault in faults:
        if fault.is_branch:
            if fault.stuck_at == 0:
                branch_sa0 += 1
            else:
                branch_sa1 += 1
        else:
            if fault.stuck_at == 0:
                line_sa0 += 1
            else:
                line_sa1 += 1
    return {
        "raw_line_sa0": line_sa0,
        "raw_line_sa1": line_sa1,
        "raw_branch_sa0": branch_sa0,
        "raw_branch_sa1": branch_sa1,
        "raw_total": len(faults),
    }


def _circuit_metrics(circuit: Circuit) -> dict[str, Any]:
    gate_types: dict[str, int] = {}
    max_fanin = 0
    for gate in circuit.gates:
        key = gate.type.name
        gate_types[key] = gate_types.get(key, 0) + 1
        max_fanin = max(max_fanin, len(gate.inputs))

    max_fanout = 0
    internal = 0
    for signal in circuit.signals.values():
        max_fanout = max(max_fanout, len(signal.fanouts))
        if not signal.is_pi and not signal.is_po:
            internal += 1

    logic_depth = max((gate.level for gate in circuit.gates), default=-1)
    if logic_depth < 0 and circuit.gates:
        logic_depth = 0

    return {
        "primary_inputs": len(circuit.primary_inputs),
        "primary_outputs": len(circuit.primary_outputs),
        "total_signals": len(circuit.signals),
        "internal_wires": internal,
        "total_gates": len(circuit.gates),
        "gate_type_counts": gate_types,
        "max_gate_fanin": max_fanin,
        "max_signal_fanout": max_fanout,
        "logic_depth": logic_depth,
    }


def _run_collapse_pipeline(
    circuit: Circuit,
) -> tuple[list[Fault], int, int, int, Any]:
    faults = generate_raw_faults(circuit)
    raw_count = len(faults)
    equiv_map = collapse_equivalence(circuit, faults)
    after_equiv = len(collapse_map_keys(equiv_map))
    final_map = collapse_dominance(circuit, equiv_map)
    after_dom = len(collapse_map_keys(final_map))
    return faults, raw_count, after_equiv, after_dom, final_map


def collect_one_circuit(
    verilog_path: Path,
    *,
    timing_repetitions: int = 3,
) -> CircuitRecord:
    name = verilog_path.stem
    record = CircuitRecord(name=name, input_file=str(verilog_path.resolve()), parse_ok=False)

    parse_samples: list[float] = []
    last_circuit: Circuit | None = None
    last_error: str | None = None

    for _ in range(timing_repetitions):
        t0 = time.perf_counter()
        try:
            circuit = parse_iscas_verilog(verilog_path)
            elapsed = (time.perf_counter() - t0) * 1000.0
            parse_samples.append(elapsed)
            last_circuit = circuit
            last_error = None
        except (ParseError, OSError, ValueError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            break

    record.parse_time = _timing_stats(parse_samples)

    if last_circuit is None:
        record.parse_error = last_error or "parse failed"
        return record

    record.parse_ok = True
    cm = _circuit_metrics(last_circuit)
    record.primary_inputs = cm["primary_inputs"]
    record.primary_outputs = cm["primary_outputs"]
    record.total_signals = cm["total_signals"]
    record.internal_wires = cm["internal_wires"]
    record.total_gates = cm["total_gates"]
    record.gate_type_counts = cm["gate_type_counts"]
    record.max_gate_fanin = cm["max_gate_fanin"]
    record.max_signal_fanout = cm["max_signal_fanout"]
    record.logic_depth = cm["logic_depth"]

    collapse_samples: list[float] = []
    faults: list[Fault] | None = None
    raw_count = after_equiv = after_dom = 0
    final_map = None

    for _ in range(timing_repetitions):
        try:
            circuit = parse_iscas_verilog(verilog_path)
        except (ParseError, OSError, ValueError) as exc:
            record.metrics_warnings.append(f"collapse rep parse failed: {exc}")
            break
        t0 = time.perf_counter()
        try:
            faults, raw_count, after_equiv, after_dom, final_map = _run_collapse_pipeline(
                circuit
            )
            collapse_samples.append((time.perf_counter() - t0) * 1000.0)
        except Exception as exc:
            record.metrics_warnings.append(f"collapse pipeline failed: {exc}")
            break

    record.collapse_pipeline_time = _timing_stats(collapse_samples)

    if faults is None or final_map is None:
        return record

    classified = _classify_raw_faults(faults)
    record.raw_line_sa0 = classified["raw_line_sa0"]
    record.raw_line_sa1 = classified["raw_line_sa1"]
    record.raw_branch_sa0 = classified["raw_branch_sa0"]
    record.raw_branch_sa1 = classified["raw_branch_sa1"]
    record.raw_total = classified["raw_total"]

    names = [str(f) for f in faults]
    unique = set(names)
    record.unique_fault_names = len(unique)
    record.duplicate_fault_names = len(names) - len(unique)

    record.representatives_after_equivalence = after_equiv
    record.representatives_after_dominance = after_dom
    record.removed_by_equivalence = raw_count - after_equiv
    record.removed_by_dominance_additional = after_equiv - after_dom
    record.overall_reduction_percent = reduction_percent(raw_count, after_dom)

    record.metrics_warnings.extend(
        validate_collapse_stages(raw_count, after_equiv, after_dom)
    )

    try:
        verify_collapse_partition(faults, final_map)
        record.partition_check_passed = True
    except AssertionError as exc:
        record.partition_check_passed = False
        record.partition_check_error = str(exc)

    return record


def _git_metadata(repo_root: Path) -> dict[str, str | None]:
    def run(args: list[str]) -> str | None:
        try:
            result = subprocess.run(
                args,
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            return result.stdout.strip() or None
        except (subprocess.SubprocessError, OSError):
            return None

    return {
        "branch": run(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
        "commit": run(["git", "rev-parse", "HEAD"]),
    }


def collect_all(
    iscas_dir: Path,
    *,
    timing_repetitions: int = 3,
    collection_command: str,
) -> dict[str, Any]:
    circuits: list[CircuitRecord] = []
    missing: list[str] = []

    for stem in CANONICAL_BENCHMARKS:
        path = iscas_dir / f"{stem}.v"
        if not path.is_file():
            missing.append(stem)
            circuits.append(
                CircuitRecord(
                    name=stem,
                    input_file=str(path),
                    parse_ok=False,
                    parse_error="benchmark file not found",
                )
            )
            continue
        circuits.append(
            collect_one_circuit(path, timing_repetitions=timing_repetitions)
        )

    ok = [c for c in circuits if c.parse_ok]
    total_gates = sum(c.total_gates or 0 for c in ok)
    parse_medians = [
        c.parse_time.median_ms for c in ok if c.parse_time.median_ms is not None
    ]
    reductions = [
        c.overall_reduction_percent
        for c in ok
        if c.overall_reduction_percent is not None
    ]

    return {
        "metadata": {
            "schema": "review2_metrics_v1",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "python_version": sys.version,
            "platform": platform.platform(),
            "git": _git_metadata(iscas_dir.parent),
            "benchmarks_requested": list(CANONICAL_BENCHMARKS),
            "benchmarks_missing_files": missing,
            "timing_repetitions": timing_repetitions,
            "collection_command": collection_command,
            "definitions": {
                "parse_time": PARSE_TIME_DEFINITION,
                "collapse_pipeline_time": COLLAPSE_TIME_DEFINITION,
                "internal_wires": INTERNAL_WIRES_DEFINITION,
                "logic_depth": LOGIC_DEPTH_DEFINITION,
                "representative_count": (
                    "Number of keys in the collapse map after each stage "
                    "(distinct ATPG targets after collapsing)."
                ),
                "fault_description": (
                    "Each raw list entry is one SA0 or SA1 Fault object "
                    "(line/stem or branch), not a physical site count."
                ),
                "partition_check": (
                    "verify_collapse_partition: bookkeeping that every raw fault "
                    "name appears exactly once across representatives, equivalent, "
                    "and dominator sets. Not a proof of collapsing rule correctness."
                ),
            },
            "podem_disclaimer": PODEM_DISCLAIMER,
        },
        "summary": {
            "circuits_requested": len(CANONICAL_BENCHMARKS),
            "parse_succeeded": len(ok),
            "parse_failed": len(circuits) - len(ok),
            "partition_check_passed": sum(
                1 for c in ok if c.partition_check_passed is True
            ),
            "partition_check_failed": sum(
                1 for c in ok if c.partition_check_passed is False
            ),
            "total_gates_all_ok": total_gates,
            "median_parse_ms_across_circuits": (
                statistics.median(parse_medians) if parse_medians else None
            ),
            "mean_reduction_percent_ok": (
                statistics.mean(reductions) if reductions else None
            ),
        },
        "circuits": [_record_to_dict(c) for c in circuits],
    }


def _record_to_dict(record: CircuitRecord) -> dict[str, Any]:
    data = asdict(record)
    return data


def write_data_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")


def load_data_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
