#!/usr/bin/env python3
"""Generate review2_analysis.md from artifacts/review2/review2_data.json."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "scripts"))

from review2_metrics_lib import load_data_json  # noqa: E402

DEFAULT_IN = _ROOT / "artifacts" / "review2" / "review2_data.json"
DEFAULT_OUT = _ROOT / "artifacts" / "review2" / "review2_analysis.md"


def _fmt_ms(stats: dict | None) -> str:
    if not stats or stats.get("median_ms") is None:
        return "—"
    med = stats["median_ms"]
    mn = stats.get("min_ms")
    mx = stats.get("max_ms")
    return f"{med:.3f} (min {mn:.3f}, max {mx:.3f})"


def _fmt_pct(value: float | None) -> str:
    return f"{value:.2f}%" if value is not None else "—"


def generate_markdown(data: dict) -> str:
    meta = data["metadata"]
    summary = data["summary"]
    circuits = data["circuits"]
    lines: list[str] = []

    lines.append("# Review-II — Parser and fault-collapsing metrics\n")
    lines.append(f"> {meta['podem_disclaimer']}\n")

    lines.append("## Presentation snapshot\n")
    lines.append(
        f"- **Parse success:** {summary['parse_succeeded']}/"
        f"{summary['circuits_requested']} canonical ISCAS'85 benchmarks\n"
    )
    lines.append(f"- **Total gates (parsed OK):** {summary['total_gates_all_ok']}\n")
    med_parse = summary.get("median_parse_ms_across_circuits")
    med_parse_s = f"{med_parse:.3f}" if med_parse is not None else "—"
    lines.append(
        f"- **Median parse time (across OK circuits):** {med_parse_s} ms\n"
    )
    lines.append(
        f"- **Mean fault-list reduction (OK circuits):** "
        f"{_fmt_pct(summary.get('mean_reduction_percent_ok'))}\n"
    )
    lines.append(
        f"- **Partition check passed:** {summary['partition_check_passed']} OK, "
        f"{summary['partition_check_failed']} failed\n"
    )

    lines.append("\n## Definitions\n")
    for key, text in meta["definitions"].items():
        lines.append(f"- **{key}:** {text}\n")

    lines.append("\n## Reduction formulas\n")
    lines.append(
        "- Equivalence reduction = `raw_total - representatives_after_equivalence`\n"
    )
    lines.append(
        "- Additional dominance reduction = "
        "`representatives_after_equivalence - representatives_after_dominance`\n"
    )
    lines.append(
        "- Overall reduction % = `(raw_total - representatives_after_dominance) / raw_total * 100`\n"
    )
    lines.append(
        "- This is **fault-list reduction**, not ATPG fault coverage.\n"
    )

    lines.append("\n## Circuit and parser metrics\n")
    lines.append(
        "| Circuit | Parse | PI | PO | Signals | Internal | Gates | Depth | "
        "Max fan-in | Max fanout | Parse ms (median) |\n"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n")
    for row in circuits:
        if not row["parse_ok"]:
            lines.append(
                f"| {row['name']} | FAIL | — | — | — | — | — | — | — | — | — |\n"
            )
            continue
        lines.append(
            f"| {row['name']} | OK | {row['primary_inputs']} | {row['primary_outputs']} | "
            f"{row['total_signals']} | {row['internal_wires']} | {row['total_gates']} | "
            f"{row['logic_depth']} | {row['max_gate_fanin']} | {row['max_signal_fanout']} | "
            f"{_fmt_ms(row['parse_time'])} |\n"
        )

    lines.append("\n## Fault generation and collapsing\n")
    lines.append(
        "| Circuit | Raw | Line SA0 | Line SA1 | Br SA0 | Br SA1 | "
        "After equiv | After dom | Removed eq | Removed dom+ | Reduction % | "
        "Partition | Collapse ms |\n"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|\n")
    for row in circuits:
        if not row["parse_ok"]:
            err = (row.get("parse_error") or "failed")[:40]
            lines.append(f"| {row['name']} | — | — | — | — | — | — | — | — | — | — | {err} | — |\n")
            continue
        part = "PASS" if row.get("partition_check_passed") else "FAIL"
        lines.append(
            f"| {row['name']} | {row['raw_total']} | {row['raw_line_sa0']} | "
            f"{row['raw_line_sa1']} | {row['raw_branch_sa0']} | {row['raw_branch_sa1']} | "
            f"{row['representatives_after_equivalence']} | {row['representatives_after_dominance']} | "
            f"{row['removed_by_equivalence']} | {row['removed_by_dominance_additional']} | "
            f"{_fmt_pct(row.get('overall_reduction_percent'))} | {part} | "
            f"{_fmt_ms(row['collapse_pipeline_time'])} |\n"
        )

    lines.append("\n## Gate type counts (per circuit)\n")
    for row in circuits:
        if not row["parse_ok"]:
            lines.append(f"\n### {row['name']}\n\nParse failed: {row.get('parse_error')}\n")
            continue
        lines.append(f"\n### {row['name']}\n\n")
        counts = row.get("gate_type_counts") or {}
        if not counts:
            lines.append("(no gates)\n")
            continue
        lines.append("| Gate type | Count |\n|---|---:|\n")
        for gtype in sorted(counts):
            lines.append(f"| {gtype} | {counts[gtype]} |\n")

    failed = [r for r in circuits if not r["parse_ok"]]
    if failed:
        lines.append("\n## Failed or missing benchmarks\n")
        for row in failed:
            lines.append(f"- **{row['name']}:** {row.get('parse_error', 'unknown')}\n")

    warnings_rows = [r for r in circuits if r.get("metrics_warnings")]
    if warnings_rows:
        lines.append("\n## Metric warnings\n")
        for row in warnings_rows:
            for warn in row["metrics_warnings"]:
                lines.append(f"- **{row['name']}:** {warn}\n")

    lines.append("\n## Chart-friendly series (for slides)\n")
    lines.append("Use `review2_data.json` → `circuits[]` fields:\n")
    lines.append("- Gate count: `total_gates`\n")
    lines.append("- Fault stages: `raw_total`, `representatives_after_equivalence`, `representatives_after_dominance`\n")
    lines.append("- Reduction: `overall_reduction_percent`\n")

    lines.append("\n## Run metadata\n")
    lines.append(f"- **Collected (UTC):** {meta.get('timestamp_utc')}\n")
    lines.append(f"- **Python:** {meta.get('python_version', '').split()[0]}\n")
    lines.append(f"- **Platform:** {meta.get('platform')}\n")
    git = meta.get("git") or {}
    lines.append(f"- **Git branch:** {git.get('branch')}\n")
    lines.append(f"- **Git commit:** {git.get('commit')}\n")
    lines.append(f"- **Timing repetitions:** {meta.get('timing_repetitions')}\n")
    lines.append(f"- **Collection command:** `{meta.get('collection_command')}`\n")

    lines.append("\n## Reproduce\n")
    lines.append("```bash\n")
    lines.append("python scripts/collect_review2_metrics.py\n")
    lines.append("python scripts/generate_review2_report.py\n")
    lines.append("```\n")
    lines.append(f"\nSingle data file: `artifacts/review2/review2_data.json`\n")

    return "".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_IN)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    if not args.input.is_file():
        raise SystemExit(f"data file not found: {args.input} (run collect_review2_metrics.py first)")

    data = load_data_json(args.input)
    report = generate_markdown(data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
