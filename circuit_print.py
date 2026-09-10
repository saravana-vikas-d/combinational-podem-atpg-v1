#!/usr/bin/env python3
"""Parse an ISCAS .v netlist and write a formatted circuit dump to Circuit_prints/."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT / "src"))

from circuit.dump import print_circuit_from_file  # noqa: E402

# --- edit this path, then run: python circuit_print.py ---
VERILOG_PATH = _ROOT / "ISCAS85_Circuits" / "c17.v"
OUTPUT_DIR = _ROOT / "Circuit_prints"


if __name__ == "__main__":
    if not VERILOG_PATH.is_file():
        raise SystemExit(f"file not found: {VERILOG_PATH}")

    path = print_circuit_from_file(VERILOG_PATH, OUTPUT_DIR)
    print(path)
