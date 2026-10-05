"""Human-readable collapse map dumps for manual verification."""

from __future__ import annotations

from datetime import datetime
from io import StringIO
from pathlib import Path

from circuit.circuit import Circuit
from circuit.dump import format_circuit
from fault.collapsing import CollapseGateStep, CollapseMap, CollapseResult, collapse_faults

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_OUTPUT_DIR = _PROJECT_ROOT / "Collapse_prints"
_LINE = "=" * 80
_SUBLINE = "-" * 80


def format_collapse_map(
    collapse_map: CollapseMap,
    *,
    title: str,
    raw_count: int | None = None,
) -> str:
    """Return a formatted collapse map section."""
    out = StringIO()
    out.write(f"{_LINE}\n")
    out.write(f"{title}\n")
    out.write(f"{_LINE}\n")
    if raw_count is not None:
        out.write(f"Representatives : {len(collapse_map)}\n")
        out.write(f"Raw faults      : {raw_count}\n")
        out.write(f"{_LINE}\n")
    out.write("\n")

    if not collapse_map:
        out.write("  (empty)\n")
        return out.getvalue()

    for rep in sorted(collapse_map.keys()):
        equivalent, dominators = collapse_map[rep]
        out.write(f"  {rep}\n")
        if equivalent:
            out.write(f"    equivalent       : {', '.join(sorted(equivalent))}\n")
        if dominators:
            out.write(f"    dominator_faults : {', '.join(sorted(dominators))}\n")
        if not equivalent and not dominators:
            out.write("    (singleton)\n")
    out.write("\n")
    return out.getvalue()


def format_collapse_gate_steps(
    steps: list[CollapseGateStep],
    *,
    phase_title: str,
    raw_count: int | None = None,
) -> str:
    """Format per-gate collapse snapshots for one phase."""
    out = StringIO()
    out.write(f"{_LINE}\n")
    out.write(f"{phase_title}\n")
    out.write(f"{_LINE}\n\n")

    for index, step in enumerate(steps):
        gate_label = step.gate_instance
        if step.gate_level >= 0:
            gate_label = f"{gate_label} (L{step.gate_level})"
        title = f"[{index}] gate {gate_label}"
        out.write(format_collapse_map(
            step.collapse_map,
            title=title,
            raw_count=raw_count,
        ))
        out.write(f"{_SUBLINE}\n\n")

    return out.getvalue()


def format_collapse_per_gate_trace(circuit: Circuit, result: CollapseResult) -> str:
    """Format equivalence and dominance maps after each processed gate."""
    if result.equivalence_steps is None or result.dominance_steps is None:
        raise ValueError("CollapseResult has no gate steps; use store_gate_steps=True")

    out = StringIO()
    out.write(format_collapse_gate_steps(
        result.equivalence_steps,
        phase_title="EQUIVALENCE — AFTER EACH GATE (low → high)",
        raw_count=result.raw_count,
    ))
    out.write(format_collapse_gate_steps(
        result.dominance_steps,
        phase_title="DOMINANCE — AFTER EACH GATE (high → low)",
        raw_count=result.raw_count,
    ))
    return out.getvalue()


def format_collapse_debug(circuit: Circuit, result: CollapseResult) -> str:
    """Format equivalence and final collapse maps."""
    out = StringIO()
    out.write(format_collapse_map(
        result.equivalence_map or {},
        title="AFTER EQUIVALENCE",
        raw_count=result.raw_count,
    ))
    out.write(f"{_SUBLINE}\n\n")
    out.write(format_collapse_map(
        result.collapse_map,
        title="AFTER DOMINANCE",
        raw_count=result.raw_count,
    ))
    return out.getvalue()


def dump_collapse_per_gate_trace(
    circuit: Circuit,
    result: CollapseResult,
    output_dir: str | Path | None = None,
    *,
    print_circuit_enable: bool = False,
    timestamp: datetime | None = None,
) -> Path:
    """Write per-gate collapse trace to ``Collapse_prints/<name>_collapse_per_gate_<timestamp>.txt``."""
    target_dir = Path(output_dir) if output_dir is not None else _DEFAULT_OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    when = timestamp or datetime.now()
    filename = f"{circuit.name}_collapse_per_gate_{when.strftime('%d%m%Y_%H%M')}.txt"
    path = target_dir / filename

    parts: list[str] = []
    if print_circuit_enable:
        parts.append(format_circuit(circuit))
        parts.append(f"{_SUBLINE}\n\n")
    parts.append(format_collapse_per_gate_trace(circuit, result))

    path.write_text("".join(parts), encoding="utf-8")
    return path


def dump_collapse_result(
    circuit: Circuit,
    result: CollapseResult,
    output_dir: str | Path | None = None,
    *,
    print_circuit_enable: bool = False,
    timestamp: datetime | None = None,
) -> Path:
    """Write collapse debug output to ``Collapse_prints/<name>_collapse_<timestamp>.txt``."""
    target_dir = Path(output_dir) if output_dir is not None else _DEFAULT_OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    when = timestamp or datetime.now()
    filename = f"{circuit.name}_collapse_{when.strftime('%d%m%Y_%H%M')}.txt"
    path = target_dir / filename

    parts: list[str] = []
    if print_circuit_enable:
        parts.append(format_circuit(circuit))
        parts.append(f"{_SUBLINE}\n\n")
    parts.append(format_collapse_debug(circuit, result))

    path.write_text("".join(parts), encoding="utf-8")
    return path


def print_collapse_per_gate_from_file(
    verilog_path: str | Path,
    output_dir: str | Path | None = None,
    *,
    print_circuit_enable: bool = False,
    timestamp: datetime | None = None,
) -> Path:
    """Parse a netlist, collapse with per-gate snapshots, and write trace to disk."""
    from parser.iscas_verilog import parse_iscas_verilog

    circuit = parse_iscas_verilog(verilog_path)
    result = collapse_faults(circuit, store_gate_steps=True)
    return dump_collapse_per_gate_trace(
        circuit,
        result,
        output_dir,
        print_circuit_enable=print_circuit_enable,
        timestamp=timestamp,
    )


def print_collapse_from_file(
    verilog_path: str | Path,
    output_dir: str | Path | None = None,
    *,
    print_circuit_enable: bool = False,
    timestamp: datetime | None = None,
) -> Path:
    """Parse a netlist, collapse faults, and write debug output to disk."""
    from parser.iscas_verilog import parse_iscas_verilog

    circuit = parse_iscas_verilog(verilog_path)
    result = collapse_faults(circuit)
    return dump_collapse_result(
        circuit,
        result,
        output_dir,
        print_circuit_enable=print_circuit_enable,
        timestamp=timestamp,
    )
