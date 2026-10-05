"""Write PODEM search traces to Podem_prints/."""

from __future__ import annotations

from datetime import datetime
from io import StringIO
from pathlib import Path

from atpg.podem import podem
from atpg.trace import PodemTrace, PodemTraceEvent, PodemTracer
from circuit.circuit import Circuit
from circuit.levelize import levelize
from fault.collapsing import collapse_faults, collapse_map_keys
from fault.fault import Fault, format_fault, parse_fault_name
from parser.iscas_verilog import parse_iscas_verilog

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_OUTPUT_DIR = _PROJECT_ROOT / "Podem_prints"
_LINE = "=" * 80
_SUBLINE = "-" * 80


def format_podem_trace_event(event: PodemTraceEvent) -> str:
    """Format one trace line block."""
    out = StringIO()
    indent = "  " * event.depth
    header = (
        f"[{event.index:4d}] d={event.depth} "
        f"step={event.kind}  process={event.process}"
    )
    if event.gate is not None:
        level = f"L{event.gate_level}" if event.gate_level is not None else "L?"
        header += f"  gate={event.gate} ({level})"
    if event.desired is not None:
        header += f"  desired={event.desired}"
    if event.input_index is not None:
        header += f"  input_index={event.input_index}"
    out.write(f"{indent}{header}\n")

    if event.assignments:
        assigns = ", ".join(f"{name}={value}" for name, value in event.assignments)
        out.write(f"{indent}  assign: {assigns}\n")
    if event.frontier:
        out.write(f"{indent}  D-frontier: {', '.join(event.frontier)}\n")
    if event.primary_outputs:
        pos = ", ".join(f"{name}={value}" for name, value in event.primary_outputs)
        out.write(f"{indent}  PO: {pos}\n")
    if event.primary_inputs:
        pis = ", ".join(f"{name}={value}" for name, value in event.primary_inputs)
        out.write(f"{indent}  PI: {pis}\n")
    if event.pattern is not None:
        out.write(f"{indent}  pattern: {event.pattern}\n")
    if event.note:
        out.write(f"{indent}  note: {event.note}\n")
    return out.getvalue()


def format_podem_trace(trace: PodemTrace) -> str:
    """Format a full PODEM trace for one fault."""
    out = StringIO()
    out.write(f"{_LINE}\n")
    out.write(f"PODEM trace: {trace.fault_name}\n")
    out.write(f"{_LINE}\n")
    if trace.result_status is not None:
        out.write(f"Result     : {trace.result_status}\n")
        out.write(f"Backtracks : {trace.backtracks}\n")
    out.write(f"Events     : {len(trace.events)}\n")
    if trace.truncated:
        out.write("WARNING    : trace truncated (max_events reached)\n")
    out.write(f"{_LINE}\n\n")

    for event in trace.events:
        out.write(format_podem_trace_event(event))
        out.write("\n")
    return out.getvalue()


def format_podem_traces(traces: list[PodemTrace], *, circuit_name: str) -> str:
    """Format multiple fault traces into one report."""
    out = StringIO()
    out.write(f"{_LINE}\n")
    out.write(f"PODEM traces: {circuit_name}\n")
    out.write(f"Faults traced: {len(traces)}\n")
    out.write(f"{_LINE}\n\n")
    for trace in traces:
        out.write(format_podem_trace(trace))
        out.write(f"{_SUBLINE}\n\n")
    return out.getvalue()


def run_podem_with_trace(
    circuit: Circuit,
    fault: Fault,
    *,
    backtrack_limit: int | None = None,
    recursion_limit: int | None = 500,
    max_events: int | None = 2000,
):
    """Run PODEM with tracing enabled for one fault."""
    tracer = PodemTracer(format_fault(fault), max_events=max_events)
    result = podem(
        circuit,
        fault,
        backtrack_limit=backtrack_limit,
        recursion_limit=recursion_limit,
        tracer=tracer,
    )
    return tracer.trace, result


def dump_podem_traces(
    circuit: Circuit,
    traces: list[PodemTrace],
    output_dir: str | Path | None = None,
    *,
    timestamp: datetime | None = None,
) -> Path:
    """Write combined trace report to ``Podem_prints/<circuit>_podem_trace_<timestamp>.txt``."""
    target_dir = Path(output_dir) if output_dir is not None else _DEFAULT_OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    when = timestamp or datetime.now()
    filename = f"{circuit.name}_podem_trace_{when.strftime('%d%m%Y_%H%M')}.txt"
    path = target_dir / filename
    path.write_text(format_podem_traces(traces, circuit_name=circuit.name), encoding="utf-8")
    return path


def print_podem_trace_from_file(
    verilog_path: str | Path,
    fault_names: list[str] | None = None,
    output_dir: str | Path | None = None,
    *,
    recursion_limit: int | None = 500,
    backtrack_limit: int | None = None,
    max_events: int | None = 2000,
    timestamp: datetime | None = None,
) -> Path:
    """Parse netlist, run traced PODEM per fault, and write a combined trace file.

    When ``fault_names`` is None, traces every collapsed-fault representative.
    """
    circuit = parse_iscas_verilog(verilog_path)
    levelize(circuit)
    collapsed = collapse_faults(circuit)

    if fault_names is None:
        names = collapse_map_keys(collapsed.collapse_map)
    else:
        names = fault_names

    traces: list[PodemTrace] = []
    for name in names:
        run_circuit = parse_iscas_verilog(verilog_path)
        levelize(run_circuit)
        trace, _ = run_podem_with_trace(
            run_circuit,
            parse_fault_name(name),
            recursion_limit=recursion_limit,
            backtrack_limit=backtrack_limit,
            max_events=max_events,
        )
        traces.append(trace)

    return dump_podem_traces(circuit, traces, output_dir, timestamp=timestamp)
