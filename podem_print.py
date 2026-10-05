#!/usr/bin/env python3
"""Run PODEM on an ISCAS .v netlist and write test patterns to Pattern_prints/."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT / "src"))

from atpg.dump import dump_podem_batch, run_podem_from_file  # noqa: E402

ISCAS_DIR = _ROOT / "ISCAS85_Circuits"
OUTPUT_DIR = _ROOT / "Pattern_prints"
RECURSION_LIMIT = 200
BACKTRACK_LIMIT = 10000


@dataclass(frozen=True, slots=True)
class CircuitCoverageRow:
    name: str
    total_faults: int
    covered: int
    coverage_percent: float
    patterns: int
    untestable: int
    aborted: int
    backtracks: int


def _row_from_batch(circuit_name: str, batch) -> CircuitCoverageRow:
    return CircuitCoverageRow(
        name=circuit_name,
        total_faults=batch.total_faults,
        covered=len(batch.covered),
        coverage_percent=batch.coverage_percent,
        patterns=len(batch.patterns),
        untestable=len(batch.untestable),
        aborted=len(batch.aborted),
        backtracks=batch.total_backtracks,
    )


def _run_circuit_once(verilog_path: Path) -> tuple[CircuitCoverageRow, Path, Path]:
    circuit, batch = run_podem_from_file(
        verilog_path,
        recursion_limit=RECURSION_LIMIT,
        backtrack_limit=BACKTRACK_LIMIT,
    )
    report_path, tp_path = dump_podem_batch(circuit, batch, OUTPUT_DIR)
    return _row_from_batch(circuit.name, batch), report_path, tp_path


def _print_coverage_table(rows: list[CircuitCoverageRow]) -> None:
    headers = (
        "Circuit",
        "Total",
        "Covered",
        "Coverage",
        "Patterns",
        "Untest",
        "Abort",
        "Backtracks",
    )
    print()
    print("PODEM fault coverage (collapsed fault sites)")
    print("-" * 88)
    print(
        f"{headers[0]:<10} {headers[1]:>7} {headers[2]:>8} {headers[3]:>10} "
        f"{headers[4]:>9} {headers[5]:>8} {headers[6]:>6} {headers[7]:>11}"
    )
    print("-" * 88)
    for row in rows:
        print(
            f"{row.name:<10} {row.total_faults:>7} {row.covered:>8} "
            f"{row.coverage_percent:>9.2f}% {row.patterns:>9} "
            f"{row.untestable:>8} {row.aborted:>6} {row.backtracks:>11}"
        )
    print("-" * 88)
    if rows:
        total_sites = sum(row.total_faults for row in rows)
        total_covered = sum(row.covered for row in rows)
        aggregate = 100.0 * total_covered / total_sites if total_sites else 0.0
        print(
            f"{'ALL':<10} {total_sites:>7} {total_covered:>8} "
            f"{aggregate:>9.2f}% {'':>9} {'':>8} {'':>6} {'':>11}"
        )
    print()


def _ntotal_gates(verilog_path: Path) -> int:
    for line in verilog_path.read_text(encoding="utf-8").splitlines()[:12]:
        if "NtotalGates" in line:
            return int(line.split()[-1])
    return 10**9


def _discover_circuits() -> list[Path]:
    paths = list(ISCAS_DIR.glob("*.v"))
    return sorted(paths, key=lambda path: (_ntotal_gates(path), path.name))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run PODEM and write patterns to Pattern_prints/."
    )
    parser.add_argument(
        "verilog",
        nargs="?",
        type=Path,
        help="Path to a .v netlist (default: ISCAS85_Circuits/c17.v)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run every .v file in ISCAS85_Circuits/ and print a coverage table",
    )
    args = parser.parse_args()

    if args.all:
        paths = _discover_circuits()
        if not paths:
            raise SystemExit(f"no .v files under {ISCAS_DIR}")
        rows: list[CircuitCoverageRow] = []
        for path in paths:
            print(f"Running PODEM on {path.name} ...", flush=True)
            row, _report, _tp = _run_circuit_once(path)
            rows.append(row)
            print(
                f"  {row.name}: {row.coverage_percent:.2f}% "
                f"({row.covered}/{row.total_faults} faults, "
                f"{row.patterns} patterns)"
            )
        _print_coverage_table(rows)
        return

    verilog_path = args.verilog or (ISCAS_DIR / "c17.v")
    if not verilog_path.is_file():
        raise SystemExit(f"file not found: {verilog_path}")

    row, report_path, tp_path = _run_circuit_once(verilog_path)
    print(report_path)
    print(tp_path)
    print(
        f"Fault coverage: {row.coverage_percent:.2f}% "
        f"({row.covered}/{row.total_faults} fault sites)"
    )


if __name__ == "__main__":
    main()
