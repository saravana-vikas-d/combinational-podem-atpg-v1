#!/usr/bin/env python3
"""Run strict compaction on PODEM batch circuits and print a summary table."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from atpg.compaction_dump import run_compaction_from_podem_report  # noqa: E402

ISCAS = _ROOT / "ISCAS85_Circuits"
PATTERN = _ROOT / "Pattern_prints"
OUTPUT = _ROOT / "Compact_prints"

CIRCUITS = (
    "c17",
    "c432",
    "c499",
    "c880",
    "c1355",
    "c1908",
    "c2670",
    "c3540",
    "c5315",
)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    print(f"{'circuit':<8} {'orig':>6} {'compact':>7} {'covered':>12} {'valid':>5} {'complete':>8}")
    print("-" * 56)
    failed = 0
    for name in CIRCUITS:
        verilog = ISCAS / f"{name}.v"
        reports = sorted(PATTERN.glob(f"{name}_podem_*.txt"))
        if not reports:
            print(f"{name:<8} SKIP (no PODEM report)")
            continue
        report_in = reports[-1]

        def progress(msg: str) -> None:
            if "Building strict coverage" in msg:
                print(f"  {name}: {msg}", flush=True)

        result, report_out, tp_out = run_compaction_from_podem_report(
            verilog,
            report_in,
            OUTPUT,
            progress=progress,
        )
        cov = f"{len(result.covered_reps)}/{len(result.universe_reps)}"
        valid = "PASS" if result.validation_ok else "FAIL"
        complete = "yes" if result.complete else "no"
        print(
            f"{name:<8} {result.original_count:>6} {result.compact_count:>7} "
            f"{cov:>12} {valid:>5} {complete:>8}"
        )
        print(f"         -> {report_out.name}")
        if not result.validation_ok:
            failed += 1
            for err in result.validation_errors[:3]:
                print(f"         ! {err}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
