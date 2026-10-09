#!/usr/bin/env python3
"""Print objective queue and decision stack for edge aborted and untestable faults."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT / "src"))

from atpg.stack_dump import write_edge_fault_objective_steps  # noqa: E402

ISCAS_DIR = _ROOT / "ISCAS85_Circuits"
OUTPUT_DIR = _ROOT / "Stack_prints"
RECURSION_LIMIT = 200
BACKTRACK_LIMIT = 10000
EDGE = 5


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run PODEM, then print the objective queue and decision stack "
            "at every search step for the first and last aborted and untestable faults."
        )
    )
    parser.add_argument(
        "verilog",
        nargs="?",
        type=Path,
        default=ISCAS_DIR / "c432.v",
        help="Path to a .v netlist (default: ISCAS85_Circuits/c432.v)",
    )
    parser.add_argument(
        "--edge",
        type=int,
        default=EDGE,
        help="How many faults to take from each end of the aborted and untestable lists",
    )
    args = parser.parse_args()

    if not args.verilog.is_file():
        raise SystemExit(f"file not found: {args.verilog}")

    path = write_edge_fault_objective_steps(
        args.verilog,
        output_dir=OUTPUT_DIR,
        edge=args.edge,
        recursion_limit=RECURSION_LIMIT,
        backtrack_limit=BACKTRACK_LIMIT,
    )
    print(path)


if __name__ == "__main__":
    main()
