#!/usr/bin/env python3
"""Run PODEM on each ISCAS .v and print a one-line summary table (no duplicate work)."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

from atpg.dump import run_podem_from_file  # noqa: E402
from podem_print import (  # noqa: E402
    BACKTRACK_LIMIT,
    ISCAS_DIR,
    RECURSION_LIMIT,
    CircuitCoverageRow,
    _discover_circuits,
    _ntotal_gates,
    _row_from_batch,
)


# Previous batch (pre D-frontier propagation fix + justification skip), same limits.
BASELINE: dict[str, tuple[float, int, int, int]] = {
    "c17": (100.00, 0, 0, 0),
    "c432": (74.07, 73, 72, 755521),
    "c499": (28.86, 120, 442, 1264754),
    "c880": (100.00, 0, 0, 1290),
    "c1908": (80.90, 310, 4, 3159313),
    "c1355": (16.53, 1050, 0, 10701456),
}


def main() -> None:
    paths = _discover_circuits()
    path_by_name = {path.stem: path for path in paths}
    rows: list[CircuitCoverageRow] = []
    for path in paths:
        print(f"Running {path.name} ...", flush=True)
        circuit, batch = run_podem_from_file(
            path,
            recursion_limit=RECURSION_LIMIT,
            backtrack_limit=BACKTRACK_LIMIT,
        )
        rows.append(_row_from_batch(circuit.name, batch))

    print()
    print(
        "Comparison vs earlier run (same backtrack_limit=10000, recursion_limit=200)"
    )
    print("-" * 110)
    print(
        f"{'Circuit':<10} {'Gates':>6}  "
        f"{'Cov% now':>9} {'Cov% was':>9} {'Δ cov':>7}  "
        f"{'Abort':>6} {'was':>6}  {'Untest':>7} {'was':>6}  "
        f"{'Backtracks':>12} {'was':>12}"
    )
    print("-" * 110)
    for row in rows:
        gates = _ntotal_gates(path_by_name[row.name])
        base = BASELINE.get(row.name)
        if base:
            bcov, bab, bun, bbt = base
            dcov = row.coverage_percent - bcov
            print(
                f"{row.name:<10} {gates:>6}  "
                f"{row.coverage_percent:>8.2f}% {bcov:>8.2f}% {dcov:>+6.2f}%  "
                f"{row.aborted:>6} {bab:>6}  "
                f"{row.untestable:>7} {bun:>6}  "
                f"{row.backtracks:>12} {bbt:>12}"
            )
        else:
            print(
                f"{row.name:<10} {gates:>6}  "
                f"{row.coverage_percent:>8.2f}% {'—':>9} {'—':>7}  "
                f"{row.aborted:>6} {'—':>6}  "
                f"{row.untestable:>7} {'—':>6}  "
                f"{row.backtracks:>12} {'—':>12}"
            )
    print("-" * 110)
    total_sites = sum(r.total_faults for r in rows)
    total_cov = sum(r.covered for r in rows)
    agg = 100.0 * total_cov / total_sites if total_sites else 0.0
    print(
        f"{'TOTAL':<10} {'':>6}  "
        f"{agg:>8.2f}% {'':>9} {'':>7}  "
        f"{sum(r.aborted for r in rows):>6} {'':>6}  "
        f"{sum(r.untestable for r in rows):>7} {'':>6}  "
        f"{sum(r.backtracks for r in rows):>12}"
    )


if __name__ == "__main__":
    main()
