#!/usr/bin/env python3
"""Collect Review-II parser and fault-collapsing metrics into a single JSON file."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "scripts"))

from review2_metrics_lib import (  # noqa: E402
    CANONICAL_BENCHMARKS,
    collect_all,
    write_data_json,
)

DEFAULT_OUT = _ROOT / "artifacts" / "review2" / "review2_data.json"
ISCAS_DIR = _ROOT / "ISCAS85_Circuits"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--iscas-dir",
        type=Path,
        default=ISCAS_DIR,
        help="Directory containing canonical ISCAS .v netlists",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUT,
        help="Single JSON output path (all metrics)",
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        default=3,
        help="Timing repetitions per circuit (median/min/max reported)",
    )
    args = parser.parse_args()

    payload = collect_all(
        args.iscas_dir,
        timing_repetitions=max(1, args.repetitions),
        collection_command=" ".join(sys.argv),
    )
    write_data_json(payload, args.output)
    summary = payload["summary"]
    print(f"Wrote {args.output}")
    print(
        f"Parse OK: {summary['parse_succeeded']}/{summary['circuits_requested']} "
        f"(benchmarks: {', '.join(CANONICAL_BENCHMARKS)})"
    )
    if summary.get("mean_reduction_percent_ok") is not None:
        print(f"Mean fault-list reduction (OK circuits): {summary['mean_reduction_percent_ok']:.2f}%")
    print("Run: python scripts/generate_review2_report.py")


if __name__ == "__main__":
    main()
