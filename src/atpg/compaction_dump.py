"""Write compaction reports and compact test pattern files."""

from __future__ import annotations

from datetime import datetime
from io import StringIO
from pathlib import Path

from atpg.compaction import (
    CompactionResult,
    PatternEntry,
    ProgressCallback,
    compact_patterns_strict,
    entries_from_podem_report,
    pattern_covers_pattern_strict,
)
from atpg.fault_sim import (
    format_po_values,
    simulate_faulty_outputs,
    simulate_good_outputs,
)
from atpg.podem import Pattern, format_pattern
from circuit.circuit import Circuit
from circuit.levelize import levelize
from fault.collapsing import collapse_faults
from fault.fault import parse_fault_name
from parser.iscas_verilog import parse_iscas_verilog

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_OUTPUT_DIR = _PROJECT_ROOT / "Compact_prints"


def format_pi_assignment(circuit: Circuit, pattern: Pattern) -> str:
    parts: list[str] = []
    for pi, bit in zip(circuit.primary_inputs, pattern, strict=True):
        label = "X" if bit is None else str(bit)
        parts.append(f"{pi.name}={label}")
    return ", ".join(parts)


def format_compaction_report(result: CompactionResult, circuit: Circuit) -> str:
    out = StringIO()
    line = "=" * 80
    out.write(f"{line}\n")
    out.write(f"PATTERN COMPACTION REPORT: {result.circuit_name}\n")
    out.write(f"{line}\n")
    pi_names = [pi.name for pi in circuit.primary_inputs]
    out.write(f"Primary inputs (pattern bit order): {', '.join(pi_names)}\n")
    out.write("Universe           : all collapsed representatives (Option B)\n")
    out.write(
        "Coverage rule      : strict fault sim per (pattern, rep); "
        "X on PIs = Logic5.X (safe — no structural subsumption)\n"
    )
    out.write(f"Collapse reps      : {len(result.universe_reps)}\n")
    out.write(f"Original patterns  : {result.original_count}\n")
    out.write(f"Compact patterns   : {result.compact_count}\n")
    out.write(
        f"Reps covered       : {len(result.covered_reps)} / {len(result.universe_reps)}\n"
    )
    out.write(f"Compaction complete: {'yes' if result.complete else 'no'}\n")
    out.write(
        f"Vector validation  : {'PASS' if result.validation_ok else 'FAIL'}\n"
    )
    if result.validation_errors:
        out.write(f"Validation errors  : {len(result.validation_errors)}\n")
    if result.uncovered_reps:
        out.write(f"Uncovered reps     : {len(result.uncovered_reps)}\n")
    out.write(f"{line}\n\n")

    if result.validation_errors:
        out.write("VALIDATION ERRORS\n")
        out.write("-" * 80 + "\n")
        for err in result.validation_errors:
            out.write(f"  {err}\n")
        out.write("\n")

    if result.uncovered_reps:
        out.write("UNCOVERED REPRESENTATIVES (no selected pattern detected them)\n")
        out.write("-" * 80 + "\n")
        for rep in sorted(result.uncovered_reps):
            out.write(f"  {rep}\n")
        out.write("\n")

    out.write("SELECTED PATTERNS (validated by strict re-simulation)\n")
    out.write("-" * 80 + "\n")
    for rank, entry in enumerate(result.selected, start=1):
        covers = result.coverage_by_index[entry.index]
        good_po, _good_ok = simulate_good_outputs(circuit, entry.pattern)
        out.write(f"  {rank:3d}. {entry.pattern_text}  <- origin {entry.origin_rep}\n")
        out.write(f"       PIs             : {format_pi_assignment(circuit, entry.pattern)}\n")
        out.write(f"       fault-free POs  : {format_po_values(good_po)}\n")
        out.write(f"       detects {len(covers)} rep(s):\n")
        for rep in sorted(covers):
            fault = parse_fault_name(rep)
            faulty_po, imply_ok, detected = simulate_faulty_outputs(
                circuit, fault, entry.pattern
            )
            out.write(f"         - {rep}\n")
            out.write(f"           faulty POs    : {format_po_values(faulty_po)}\n")
            out.write(
                f"           detected at PO: {'yes' if detected else 'no'}"
                f"  (imply ok: {'yes' if imply_ok else 'no'})\n"
            )
    out.write("\n")

    if result.dropped:
        out.write("DROPPED PATTERNS (redundant under strict coverage union)\n")
        out.write("-" * 80 + "\n")
        for entry in result.dropped:
            cov = result.coverage_by_index[entry.index]
            redundant_to = [
                sel.index
                for sel in result.selected
                if pattern_covers_pattern_strict(
                    result.coverage_by_index, sel.index, entry.index
                )
            ]
            out.write(
                f"  #{entry.index} {entry.pattern_text}  <- origin {entry.origin_rep}\n"
            )
            out.write(f"       strict coverage: {len(cov)} reps")
            if redundant_to:
                out.write(f"; subset of selected index(es) {redundant_to}")
            out.write("\n")
        out.write("\n")

    return out.getvalue()


def format_compact_tp(entries: tuple[PatternEntry, ...]) -> str:
    if not entries:
        return ""
    lines = [format_pattern(entry.pattern) for entry in entries]
    return "\n".join(lines) + "\n"


def dump_compaction_result(
    result: CompactionResult,
    circuit: Circuit,
    output_dir: str | Path | None = None,
    *,
    timestamp: datetime | None = None,
) -> tuple[Path, Path]:
    target_dir = Path(output_dir) if output_dir is not None else _DEFAULT_OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    when = timestamp or datetime.now()
    stamp = when.strftime("%d%m%Y_%H%M")
    report_path = target_dir / f"{result.circuit_name}_compact_{stamp}.txt"
    tp_path = target_dir / f"{result.circuit_name}_test_patterns_compact_{stamp}.tp"
    report_path.write_text(format_compaction_report(result, circuit), encoding="utf-8")
    tp_path.write_text(format_compact_tp(result.selected), encoding="utf-8")
    return report_path, tp_path


def run_compaction_from_podem_report(
    verilog_path: str | Path,
    podem_report_path: str | Path,
    output_dir: str | Path | None = None,
    *,
    timestamp: datetime | None = None,
    progress: ProgressCallback | None = None,
) -> tuple[CompactionResult, Path, Path]:
    circuit = parse_iscas_verilog(verilog_path)
    levelize(circuit)
    collapsed = collapse_faults(circuit)
    entries = entries_from_podem_report(podem_report_path)
    callback = progress if progress is not None else lambda _m: None
    result = compact_patterns_strict(
        circuit,
        collapsed.collapse_map,
        entries,
        progress=callback,
    )
    report_path, tp_path = dump_compaction_result(
        result, circuit, output_dir, timestamp=timestamp
    )
    return result, report_path, tp_path
