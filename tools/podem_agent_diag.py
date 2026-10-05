#!/usr/bin/env python3
"""Aggregate agent debug logs from a PODEM batch run."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

LOG = Path(__file__).resolve().parents[1] / ".cursor" / "debug-626127.log"


def main() -> None:
    if not LOG.is_file():
        print(f"No log at {LOG}", file=sys.stderr)
        raise SystemExit(1)

    terminal_u: Counter[str] = Counter()
    abort_kinds: Counter[str] = Counter()
    elapsed_abort: list[float] = []
    elapsed_success: list[float] = []
    batch_rows: list[dict] = []

    for line in LOG.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        msg = row.get("message")
        data = row.get("data") or {}
        if msg == "fault_finished":
            status = data.get("status")
            if status == "untestable":
                terminal_u[data.get("terminal_kind", "unknown")] += 1
            elif status == "aborted":
                abort_kinds[data.get("abort_kind", "unknown")] += 1
                elapsed_abort.append(float(data.get("elapsed_ms", 0)))
            elif status == "success":
                elapsed_success.append(float(data.get("elapsed_ms", 0)))
        elif msg == "batch_summary":
            batch_rows.append(data)

    print("=== Batch summaries ===")
    for data in batch_rows:
        print(
            f"{data.get('circuit')}: coverage={data.get('coverage_percent')}% "
            f"reps={data.get('reps_run')} "
            f"untestable={data.get('untestable_reps')} "
            f"aborted={data.get('aborted_reps')} "
            f"aborted_at_bt_limit={data.get('aborted_at_backtrack_limit')} "
            f"batch_ms={data.get('batch_elapsed_ms')} "
            f"total_backtracks={data.get('total_backtracks')}"
        )

    print("\n=== Untestable terminal_kind (reps) ===")
    for kind, count in terminal_u.most_common():
        print(f"  {kind}: {count}")

    print("\n=== Aborted abort_kind (reps) ===")
    for kind, count in abort_kinds.most_common():
        print(f"  {kind}: {count}")

    if elapsed_success:
        print(
            f"\nSuccess elapsed_ms: median={sorted(elapsed_success)[len(elapsed_success)//2]:.1f} "
            f"max={max(elapsed_success):.1f} n={len(elapsed_success)}"
        )
    if elapsed_abort:
        print(
            f"Aborted elapsed_ms: median={sorted(elapsed_abort)[len(elapsed_abort)//2]:.1f} "
            f"max={max(elapsed_abort):.1f} n={len(elapsed_abort)}"
        )


if __name__ == "__main__":
    main()
