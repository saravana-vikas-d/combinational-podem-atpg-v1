"""Write fault simulation reports to Fault_sim_prints/."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from atpg.fault_sim import (
    FaultSimReport,
    format_fault_sim_report,
    parse_podem_report_patterns,
    validate_representative_patterns,
)
from circuit.levelize import levelize
from fault.collapsing import collapse_faults
from parser.iscas_verilog import parse_iscas_verilog

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_OUTPUT_DIR = _PROJECT_ROOT / "Fault_sim_prints"


def dump_fault_sim_report(
    report: FaultSimReport,
    output_dir: str | Path | None = None,
    *,
    timestamp: datetime | None = None,
) -> Path:
    target_dir = Path(output_dir) if output_dir is not None else _DEFAULT_OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    when = timestamp or datetime.now()
    stamp = when.strftime("%d%m%Y_%H%M")
    path = target_dir / f"{report.circuit_name}_fault_sim_{stamp}.txt"
    path.write_text(format_fault_sim_report(report), encoding="utf-8")
    return path


def run_fault_sim_from_podem_report(
    verilog_path: str | Path,
    podem_report_path: str | Path,
    output_dir: str | Path | None = None,
    *,
    timestamp: datetime | None = None,
) -> tuple[FaultSimReport, Path]:
    circuit = parse_iscas_verilog(verilog_path)
    levelize(circuit)
    collapsed = collapse_faults(circuit)
    entries = parse_podem_report_patterns(podem_report_path)
    report = validate_representative_patterns(
        circuit,
        entries,
        collapse_map=collapsed.collapse_map,
    )
    path = dump_fault_sim_report(report, output_dir, timestamp=timestamp)
    return report, path
