#!/usr/bin/env python3
"""Run PODEM on c17 and write decision-stack snapshots before each restore."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT / "src"))

from atpg.stack_dump import print_podem_stack_combined_from_file  # noqa: E402

VERILOG_PATH = _ROOT / "ISCAS85_Circuits" / "c17.v"
OUTPUT_DIR = _ROOT / "Stack_prints"
RECURSION_LIMIT = 200
BACKTRACK_LIMIT = 10000
MAX_RESTORE_EVENTS = 500


if __name__ == "__main__":
    if not VERILOG_PATH.is_file():
        raise SystemExit(f"file not found: {VERILOG_PATH}")

    path = print_podem_stack_combined_from_file(
        VERILOG_PATH,
        output_dir=OUTPUT_DIR,
        recursion_limit=RECURSION_LIMIT,
        backtrack_limit=BACKTRACK_LIMIT,
        max_restore_events=MAX_RESTORE_EVENTS,
    )
    print(path)
