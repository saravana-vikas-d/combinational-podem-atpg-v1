"""Write PODEM test patterns and batch reports to Pattern_prints/."""

from __future__ import annotations

from datetime import datetime
from io import StringIO
from pathlib import Path

from atpg.podem import PodemBatchResult, format_pattern
from circuit.circuit import Circuit
from circuit.levelize import levelize
from fault.collapsing import collapse_faults
from parser.iscas_verilog import parse_iscas_verilog

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_OUTPUT_DIR = _PROJECT_ROOT / "Pattern_prints"
_LINE = "=" * 80
_SUBLINE = "-" * 80


def format_podem_batch(circuit: Circuit, batch: PodemBatchResult) -> str:
    """Return a human-readable PODEM batch report."""
    pi_names = [pi.name for pi in circuit.primary_inputs]
    out = StringIO()

    out.write(f"{_LINE}\n")
    out.write(f"PODEM batch report: {circuit.name}\n")
    out.write(f"{_LINE}\n")
    out.write(f"Primary inputs (pattern bit order): {', '.join(pi_names)}\n")
    out.write(f"Patterns generated : {len(batch.patterns)}\n")
    out.write(f"Total fault sites  : {batch.total_faults}\n")
    out.write(f"Faults covered     : {len(batch.covered)}\n")
    out.write(f"Fault coverage     : {batch.coverage_percent:.2f}%\n")
    out.write(f"Untestable reps    : {len(batch.untestable)}\n")
    out.write(f"Aborted reps       : {len(batch.aborted)}\n")
    out.write(f"Total backtracks   : {batch.total_backtracks}\n")
    out.write(f"{_LINE}\n\n")

    out.write("TEST PATTERNS\n")
    out.write(f"{_SUBLINE}\n")
    if not batch.patterns:
        out.write("  (none)\n")
    else:
        for index, entry in enumerate(batch.patterns, start=1):
            out.write(f"  {index:3d}. {entry.formatted}  <- {entry.rep}\n")
    out.write("\n")

    if batch.untestable:
        out.write("UNTESTABLE\n")
        out.write(f"{_SUBLINE}\n")
        for name in sorted(batch.untestable):
            out.write(f"  {name}\n")
        out.write("\n")

    if batch.aborted:
        out.write("ABORTED\n")
        out.write(f"{_SUBLINE}\n")
        for name in sorted(batch.aborted):
            out.write(f"  {name}\n")
        out.write("\n")

    return out.getvalue()


def format_test_patterns_tp(batch: PodemBatchResult) -> str:
    """Return ``test_patterns.tp`` content: one vector per line."""
    if not batch.patterns:
        return ""
    lines = [entry.formatted for entry in batch.patterns]
    return "\n".join(lines) + "\n"


def dump_podem_batch(
    circuit: Circuit,
    batch: PodemBatchResult,
    output_dir: str | Path | None = None,
    *,
    timestamp: datetime | None = None,
) -> tuple[Path, Path]:
    """Write report ``.txt`` and ``test_patterns.tp`` for a PODEM batch run."""
    target_dir = Path(output_dir) if output_dir is not None else _DEFAULT_OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    when = timestamp or datetime.now()
    stamp = when.strftime("%d%m%Y_%H%M")
    report_path = target_dir / f"{circuit.name}_podem_{stamp}.txt"
    tp_path = target_dir / f"{circuit.name}_test_patterns_{stamp}.tp"

    report_path.write_text(format_podem_batch(circuit, batch), encoding="utf-8")
    tp_path.write_text(format_test_patterns_tp(batch), encoding="utf-8")
    return report_path, tp_path


def run_podem_from_file(
    verilog_path: str | Path,
    *,
    recursion_limit: int | None = 5000,
    backtrack_limit: int | None = None,
) -> tuple[Circuit, PodemBatchResult]:
    """Parse, levelize, collapse, and run PODEM on a netlist file."""
    from atpg.podem import run_podem_on_collapsed

    circuit = parse_iscas_verilog(verilog_path)
    levelize(circuit)
    collapsed = collapse_faults(circuit)
    batch = run_podem_on_collapsed(
        circuit,
        collapsed.collapse_map,
        backtrack_limit=backtrack_limit,
        recursion_limit=recursion_limit,
    )
    return circuit, batch


def print_podem_from_file(
    verilog_path: str | Path,
    output_dir: str | Path | None = None,
    *,
    recursion_limit: int | None = 5000,
    backtrack_limit: int | None = None,
    timestamp: datetime | None = None,
) -> tuple[Path, Path]:
    """Parse a netlist, run PODEM, and write pattern files to disk."""
    circuit, batch = run_podem_from_file(
        verilog_path,
        recursion_limit=recursion_limit,
        backtrack_limit=backtrack_limit,
    )
    return dump_podem_batch(circuit, batch, output_dir, timestamp=timestamp)
