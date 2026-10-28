#!/usr/bin/env python3
"""Compact PODEM patterns via strict fault-simulation set cover (Option B reps)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT / "src"))

from atpg.compaction_dump import run_compaction_from_podem_report  # noqa: E402

ISCAS_DIR = _ROOT / "ISCAS85_Circuits"
OUTPUT_DIR = _ROOT / "Compact_prints"
PATTERN_DIR = _ROOT / "Pattern_prints"


def _default_podem_report(circuit_name: str) -> Path:
    matches = sorted(PATTERN_DIR.glob(f"{circuit_name}_podem_*.txt"))
    if not matches:
        raise SystemExit(
            f"no PODEM report found under {PATTERN_DIR} for {circuit_name!r}"
        )
    return matches[-1]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Greedy set cover over collapsed representatives using strict "
            "fault simulation (single-vector, X = unknown)."
        )
    )
    parser.add_argument(
        "verilog",
        nargs="?",
        type=Path,
        help="Path to .v netlist (default: ISCAS85_Circuits/c17.v)",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="PODEM report .txt (default: latest Pattern_prints/<circuit>_podem_*.txt)",
    )
    args = parser.parse_args()

    verilog_path = args.verilog or (ISCAS_DIR / "c17.v")
    if not verilog_path.is_file():
        raise SystemExit(f"file not found: {verilog_path}")

    report_path = args.report or _default_podem_report(verilog_path.stem)
    if not report_path.is_file():
        raise SystemExit(f"file not found: {report_path}")

    def progress(message: str) -> None:
        print(message, flush=True)

    result, report_out, tp_out = run_compaction_from_podem_report(
        verilog_path,
        report_path,
        OUTPUT_DIR,
        progress=progress,
    )
    print(report_out)
    print(tp_out)
    print(
        f"Compacted {result.original_count} -> {result.compact_count} patterns; "
        f"reps covered {len(result.covered_reps)}/{len(result.universe_reps)}"
    )
    print(f"Vector validation: {'PASS' if result.validation_ok else 'FAIL'}")
    if not result.validation_ok:
        raise SystemExit(1)
    if not result.complete:
        print(f"Uncovered reps: {len(result.uncovered_reps)} (see report)")
    if result.validation_errors:
        for err in result.validation_errors[:10]:
            print(f"  {err}")
        if len(result.validation_errors) > 10:
            print(f"  ... and {len(result.validation_errors) - 10} more")


if __name__ == "__main__":
    main()
