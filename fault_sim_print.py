#!/usr/bin/env python3
"""Validate PODEM patterns via fault simulation and write Fault_sim_prints/."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT / "src"))

from atpg.fault_sim_dump import run_fault_sim_from_podem_report  # noqa: E402

ISCAS_DIR = _ROOT / "ISCAS85_Circuits"
OUTPUT_DIR = _ROOT / "Fault_sim_prints"
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
            "Simulate each PODEM pattern on the fault-free and faulty circuit; "
            "write PO values and validation status."
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

    report, out_path = run_fault_sim_from_podem_report(
        verilog_path,
        report_path,
        OUTPUT_DIR,
    )
    print(out_path)
    print(
        f"Validation: {'PASS' if report.validation_ok else 'FAIL'} "
        f"({len(report.rows)} patterns)"
    )
    if report.mismatches:
        print(f"Mismatches: {', '.join(report.mismatches)}")


if __name__ == "__main__":
    main()
