#!/usr/bin/env python3
"""Parse an ISCAS .v netlist and write collapse debug output to Collapse_prints/."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT / "src"))

from fault.dump import print_collapse_from_file, print_collapse_per_gate_from_file  # noqa: E402

# --- edit this path, then run: python collapse_print.py ---
VERILOG_PATH = _ROOT / "ISCAS85_Circuits" / "c17.v"
OUTPUT_DIR = _ROOT / "Collapse_prints"
PRINT_CIRCUIT_ENABLE = False
PRINT_PER_GATE_TRACE = True


if __name__ == "__main__":
    if not VERILOG_PATH.is_file():
        raise SystemExit(f"file not found: {VERILOG_PATH}")

    if PRINT_PER_GATE_TRACE:
        path = print_collapse_per_gate_from_file(
            VERILOG_PATH,
            OUTPUT_DIR,
            print_circuit_enable=PRINT_CIRCUIT_ENABLE,
        )
    else:
        path = print_collapse_from_file(
            VERILOG_PATH,
            OUTPUT_DIR,
            print_circuit_enable=PRINT_CIRCUIT_ENABLE,
        )
    print(path)
