#!/usr/bin/env python3
"""Run traced PODEM on an ISCAS .v netlist and write debug output to Podem_prints/."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT / "src"))

from atpg.trace_dump import print_podem_trace_from_file  # noqa: E402

# --- edit paths, then run: python podem_trace_print.py ---
VERILOG_PATH = _ROOT / "ISCAS85_Circuits" / "c17.v"
OUTPUT_DIR = _ROOT / "Podem_prints"
RECURSION_LIMIT = 500
MAX_EVENTS_PER_FAULT = 800
# None = all collapsed representatives; or list specific fault names:
FAULT_NAMES: list[str] | None = None


if __name__ == "__main__":
    if not VERILOG_PATH.is_file():
        raise SystemExit(f"file not found: {VERILOG_PATH}")

    path = print_podem_trace_from_file(
        VERILOG_PATH,
        FAULT_NAMES,
        OUTPUT_DIR,
        recursion_limit=RECURSION_LIMIT,
        max_events=MAX_EVENTS_PER_FAULT,
    )
    print(path)
