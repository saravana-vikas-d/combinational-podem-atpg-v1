"""Record and print the PODEM decision stack immediately before snapshot restore."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from io import StringIO, TextIOBase
from pathlib import Path

from circuit.circuit import Circuit, Gate
from fault.fault import Fault, format_fault
from logic5 import Logic5
from sim.objective_search import Objective

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_OUTPUT_DIR = _PROJECT_ROOT / "Stack_prints"
_LINE = "=" * 80
_SUBLINE = "-" * 80


def _format_objective(objective: Objective) -> str:
    gate_name = objective.gate.instance_name if objective.gate is not None else "-"
    idx = objective.input_index if objective.input_index is not None else "-"
    return (
        f"{objective.signal.name}={objective.desired.display} "
        f"gate={gate_name} input_index={idx}"
    )


def _format_queue(queue: list[Objective]) -> str:
    if not queue:
        return "(empty)"
    return " -> ".join(_format_objective(obj) for obj in queue)


def _format_queue_lines(queue: list[Objective]) -> str:
    if not queue:
        return "  (empty)\n"
    lines: list[str] = []
    for index, objective in enumerate(queue):
        lines.append(f"  [{index}] {_format_objective(objective)}\n")
    return "".join(lines)


def _format_stack_lines(frames: list[DecisionStackFrame] | tuple[DecisionStackFrame, ...]) -> str:
    if not frames:
        return "  (empty)\n"
    lines: list[str] = []
    for level, frame in enumerate(frames):
        lines.append(
            f"  [{level}] d={frame.depth} kind={frame.kind} "
            f"bt@{frame.backtracks_at_push}  {frame.branch_note}\n"
        )
        lines.append(f"       queue@entry: {frame.queue_at_entry}\n")
    return "".join(lines)


def _format_pis(circuit: Circuit) -> str:
    return ", ".join(f"{pi.name}={pi.value.display}" for pi in circuit.primary_inputs)


def _format_non_x_signals(circuit: Circuit, *, limit: int = 24) -> str:
    items = [
        f"{signal.name}={signal.value.display}"
        for signal in circuit.signals.values()
        if signal.value is not Logic5.X
    ]
    items.sort()
    if len(items) > limit:
        extra = len(items) - limit
        items = items[:limit]
        items.append(f"... (+{extra} more non-X)")
    return ", ".join(items) if items else "(all X except fault site)"


@dataclass(slots=True)
class DecisionStackFrame:
    """One search branch pushed before a recursive objective step."""

    depth: int
    kind: str
    branch_note: str
    queue_at_entry: str
    backtracks_at_push: int


@dataclass
class RestoreEvent:
    """Snapshot of the decision stack immediately before restore."""

    index: int
    depth: int
    reason: str
    backtracks: int
    stack_depth: int
    stack_frames: tuple[DecisionStackFrame, ...]
    primary_inputs: str
    assigned_signals: str
    queue_context: str = ""


@dataclass
class DecisionStackRecorder:
    """Collects decision-stack snapshots at each restore."""

    fault_name: str
    max_events: int | None = 2000
    frames: list[DecisionStackFrame] = field(default_factory=list)
    events: list[RestoreEvent] = field(default_factory=list)
    truncated: bool = False
    step_sink: TextIOBase | None = None
    step_count: int = 0

    def push_branch(
        self,
        *,
        depth: int,
        kind: str,
        branch_note: str,
        queue: list[Objective],
        backtracks: int,
    ) -> None:
        self.frames.append(
            DecisionStackFrame(
                depth=depth,
                kind=kind,
                branch_note=branch_note,
                queue_at_entry=_format_queue(queue),
                backtracks_at_push=backtracks,
            )
        )

    def pop_branch(self) -> None:
        if self.frames:
            self.frames.pop()

    def note_objective_step(
        self,
        *,
        depth: int,
        backtracks: int,
        queue: list[Objective],
    ) -> None:
        """Write the current objective queue and decision stack for one search step."""
        if self.step_sink is None:
            return
        self.step_count += 1
        self.step_sink.write(
            format_objective_step(
                self.step_count,
                depth=depth,
                backtracks=backtracks,
                queue=queue,
                frames=self.frames,
            )
        )

    def emit_before_restore(
        self,
        circuit: Circuit,
        *,
        depth: int,
        reason: str,
        backtracks: int,
        queue_context: str = "",
    ) -> None:
        if self.max_events is not None and len(self.events) >= self.max_events:
            self.truncated = True
            return

        self.events.append(
            RestoreEvent(
                index=len(self.events),
                depth=depth,
                reason=reason,
                backtracks=backtracks,
                stack_depth=len(self.frames),
                stack_frames=tuple(self.frames),
                primary_inputs=_format_pis(circuit),
                assigned_signals=_format_non_x_signals(circuit),
                queue_context=queue_context,
            )
        )


def format_objective_step(
    index: int,
    *,
    depth: int,
    backtracks: int,
    queue: list[Objective],
    frames: list[DecisionStackFrame] | tuple[DecisionStackFrame, ...],
) -> str:
    """Format one objective-search step: queue head-first, stack oldest-first."""
    out = StringIO()
    out.write(f"{_SUBLINE}\n")
    out.write(
        f"STEP {index}  depth={depth}  backtracks={backtracks}  "
        f"queue_len={len(queue)}  stack_depth={len(frames)}\n"
    )
    out.write("Objective queue (index 0 = current objective):\n")
    out.write(_format_queue_lines(queue))
    out.write("Decision stack (bottom = oldest branch, top = current):\n")
    out.write(_format_stack_lines(frames))
    return out.getvalue()


def select_edge_faults(names: list[str], edge: int = 5) -> list[tuple[str, str]]:
    """Pick the first and last ``edge`` names, keeping batch order and merging overlaps.

    Each result is ``(fault_name, role)`` where ``role`` records first/last positions.
    """
    if edge < 1:
        raise ValueError("edge must be at least 1")
    if not names:
        return []

    roles: dict[str, list[str]] = {}
    total = len(names)
    for index in range(min(edge, total)):
        roles.setdefault(names[index], []).append(f"first #{index + 1} of {total}")
    for index in range(max(0, total - edge), total):
        from_end = total - index
        roles.setdefault(names[index], []).append(f"last #{from_end} of {total}")

    selected: list[tuple[str, str]] = []
    seen: set[str] = set()
    for name in names[:edge] + names[-edge:]:
        if name in seen:
            continue
        seen.add(name)
        selected.append((name, "; ".join(roles[name])))
    return selected


def format_restore_event(event: RestoreEvent) -> str:
    out = StringIO()
    out.write(f"{_SUBLINE}\n")
    out.write(
        f"RESTORE #{event.index}  depth={event.depth}  "
        f"backtracks={event.backtracks}  stack_depth={event.stack_depth}\n"
    )
    out.write(f"Reason: {event.reason}\n")
    if event.queue_context:
        out.write(f"Queue context: {event.queue_context}\n")
    out.write(f"PI: {event.primary_inputs}\n")
    out.write(f"Non-X signals: {event.assigned_signals}\n")
    out.write("Decision stack (bottom = oldest branch, top = current):\n")
    if not event.stack_frames:
        out.write("  (empty)\n")
    else:
        for level, frame in enumerate(event.stack_frames):
            out.write(
                f"  [{level}] d={frame.depth} kind={frame.kind} "
                f"bt@{frame.backtracks_at_push}  {frame.branch_note}\n"
            )
            out.write(f"       queue@entry: {frame.queue_at_entry}\n")
    return out.getvalue()


def format_stack_report(
    circuit_name: str,
    recorder: DecisionStackRecorder,
    *,
    result_status: str | None = None,
    result_backtracks: int = 0,
) -> str:
    out = StringIO()
    out.write(f"{_LINE}\n")
    out.write(f"PODEM decision stack restores: {circuit_name}  fault={recorder.fault_name}\n")
    out.write(f"{_LINE}\n")
    if result_status is not None:
        out.write(f"Result     : {result_status}\n")
        out.write(f"Backtracks : {result_backtracks}\n")
    out.write(f"Restore events: {len(recorder.events)}\n")
    if recorder.truncated:
        out.write("WARNING    : restore log truncated (max_events reached)\n")
    out.write(f"{_LINE}\n\n")

    for event in recorder.events:
        out.write(format_restore_event(event))
        out.write("\n")
    return out.getvalue()


def dump_stack_report(
    circuit_name: str,
    recorder: DecisionStackRecorder,
    output_dir: str | Path | None = None,
    *,
    result_status: str | None = None,
    result_backtracks: int = 0,
    timestamp: datetime | None = None,
) -> Path:
    target_dir = Path(output_dir) if output_dir is not None else _DEFAULT_OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    when = timestamp or datetime.now()
    stamp = when.strftime("%d%m%Y_%H%M")
    safe_fault = recorder.fault_name.replace("/", "_").replace("__", "_")
    path = target_dir / f"{circuit_name}_stack_{safe_fault}_{stamp}.txt"
    path.write_text(
        format_stack_report(
            circuit_name,
            recorder,
            result_status=result_status,
            result_backtracks=result_backtracks,
        ),
        encoding="utf-8",
    )
    return path


def run_podem_with_stack(
    circuit: Circuit,
    fault: Fault,
    *,
    backtrack_limit: int | None = None,
    recursion_limit: int | None = 500,
    max_restore_events: int | None = 2000,
):
    """Run PODEM and record the decision stack before each snapshot restore."""
    from atpg.podem import podem

    recorder = DecisionStackRecorder(
        fault_name=format_fault(fault),
        max_events=max_restore_events,
    )
    result = podem(
        circuit,
        fault,
        backtrack_limit=backtrack_limit,
        recursion_limit=recursion_limit,
        stack_recorder=recorder,
    )
    return recorder, result


def print_podem_stack_from_file(
    verilog_path: str | Path,
    fault_names: list[str] | None = None,
    output_dir: str | Path | None = None,
    *,
    recursion_limit: int | None = 200,
    backtrack_limit: int | None = 10000,
    max_restore_events: int | None = 2000,
    timestamp: datetime | None = None,
) -> list[Path]:
    """Run PODEM with stack recording for each fault and write Stack_prints/*.txt."""
    from fault.collapsing import collapse_faults, collapse_map_keys
    from parser.iscas_verilog import parse_iscas_verilog
    from circuit.levelize import levelize
    from fault.fault import parse_fault_name

    verilog_path = Path(verilog_path)
    circuit = parse_iscas_verilog(verilog_path)
    levelize(circuit)
    collapsed = collapse_faults(circuit)

    if fault_names is None:
        names = collapse_map_keys(collapsed.collapse_map)
    else:
        names = fault_names

    written: list[Path] = []
    for name in names:
        run_circuit = parse_iscas_verilog(verilog_path)
        levelize(run_circuit)
        recorder, result = run_podem_with_stack(
            run_circuit,
            parse_fault_name(name),
            backtrack_limit=backtrack_limit,
            recursion_limit=recursion_limit,
            max_restore_events=max_restore_events,
        )
        path = dump_stack_report(
            run_circuit.name,
            recorder,
            output_dir,
            result_status=result.status,
            result_backtracks=result.backtracks,
            timestamp=timestamp,
        )
        written.append(path)
    return written


def print_podem_stack_combined_from_file(
    verilog_path: str | Path,
    fault_names: list[str] | None = None,
    output_dir: str | Path | None = None,
    *,
    recursion_limit: int | None = 200,
    backtrack_limit: int | None = 10000,
    max_restore_events: int | None = 500,
    timestamp: datetime | None = None,
) -> Path:
    """Run stack recording for all faults and write one combined report."""
    from fault.collapsing import collapse_faults, collapse_map_keys
    from parser.iscas_verilog import parse_iscas_verilog
    from circuit.levelize import levelize
    from fault.fault import parse_fault_name

    verilog_path = Path(verilog_path)
    circuit = parse_iscas_verilog(verilog_path)
    levelize(circuit)
    collapsed = collapse_faults(circuit)

    if fault_names is None:
        names = collapse_map_keys(collapsed.collapse_map)
    else:
        names = fault_names

    target_dir = Path(output_dir) if output_dir is not None else _DEFAULT_OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    when = timestamp or datetime.now()
    stamp = when.strftime("%d%m%Y_%H%M")
    out_path = target_dir / f"{circuit.name}_stack_restore_{stamp}.txt"

    sections: list[str] = []
    sections.append(f"{_LINE}\n")
    sections.append(f"PODEM stack-restore log (combined): {circuit.name}\n")
    sections.append(
        f"limits: recursion={recursion_limit} backtrack={backtrack_limit} "
        f"max_restore_events/fault={max_restore_events}\n"
    )
    sections.append(f"{_LINE}\n\n")

    for name in names:
        run_circuit = parse_iscas_verilog(verilog_path)
        levelize(run_circuit)
        recorder, result = run_podem_with_stack(
            run_circuit,
            parse_fault_name(name),
            backtrack_limit=backtrack_limit,
            recursion_limit=recursion_limit,
            max_restore_events=max_restore_events,
        )
        sections.append(
            format_stack_report(
                run_circuit.name,
                recorder,
                result_status=result.status,
                result_backtracks=result.backtracks,
            )
        )
        sections.append(f"{_SUBLINE}\n\n")

    out_path.write_text("".join(sections), encoding="utf-8")
    return out_path


def write_edge_fault_objective_steps(
    verilog_path: str | Path,
    output_dir: str | Path | None = None,
    *,
    edge: int = 5,
    recursion_limit: int | None = 200,
    backtrack_limit: int | None = 10000,
    timestamp: datetime | None = None,
) -> Path:
    """Trace objective queue and decision stack for edge aborted and untestable faults.

    Runs a batch to collect fault outcomes in search order, then re-runs the first
    and last ``edge`` aborted faults and the first and last ``edge`` untestable faults.
    Each objective-search entry is appended as it happens.
    """
    from circuit.levelize import levelize
    from fault.collapsing import collapse_faults
    from fault.fault import parse_fault_name
    from parser.iscas_verilog import parse_iscas_verilog
    from atpg.podem import podem, run_podem_on_collapsed

    verilog_path = Path(verilog_path)
    circuit = parse_iscas_verilog(verilog_path)
    levelize(circuit)
    collapsed = collapse_faults(circuit)
    batch = run_podem_on_collapsed(
        circuit,
        collapsed.collapse_map,
        backtrack_limit=backtrack_limit,
        recursion_limit=recursion_limit,
    )

    target_dir = Path(output_dir) if output_dir is not None else _DEFAULT_OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    when = timestamp or datetime.now()
    stamp = when.strftime("%d%m%Y_%H%M")
    out_path = target_dir / f"{circuit.name}_objective_steps_{stamp}.txt"

    groups = (
        ("aborted", batch.aborted),
        ("untestable", batch.untestable),
    )

    with out_path.open("w", encoding="utf-8") as handle:
        handle.write(f"{_LINE}\n")
        handle.write(f"PODEM objective-step debug: {circuit.name}\n")
        handle.write(f"{_LINE}\n")
        handle.write(f"Netlist    : {verilog_path}\n")
        handle.write(
            f"Limits     : recursion={recursion_limit} backtrack={backtrack_limit}\n"
        )
        handle.write(f"Edge count : first {edge} and last {edge} of each outcome\n")
        handle.write(f"Aborted    : {len(batch.aborted)}\n")
        handle.write(f"Untestable : {len(batch.untestable)}\n")
        handle.write(f"{_LINE}\n\n")

        for status_name, names in groups:
            selected = select_edge_faults(names, edge)
            handle.write(f"{_LINE}\n")
            handle.write(
                f"{status_name.upper()}  total={len(names)}  tracing={len(selected)}\n"
            )
            handle.write(f"{_LINE}\n")
            if not selected:
                handle.write(f"  (no {status_name} faults)\n\n")
                continue
            for fault_name, role in selected:
                handle.write(f"\n{_LINE}\n")
                handle.write(f"FAULT {fault_name}\n")
                handle.write(f"Role  : {role}\n")
                handle.write(f"Group : {status_name}\n")
                handle.write(f"{_LINE}\n")
                handle.flush()

                run_circuit = parse_iscas_verilog(verilog_path)
                levelize(run_circuit)
                recorder = DecisionStackRecorder(fault_name=fault_name)
                recorder.step_sink = handle
                result = podem(
                    run_circuit,
                    parse_fault_name(fault_name),
                    backtrack_limit=backtrack_limit,
                    recursion_limit=recursion_limit,
                    stack_recorder=recorder,
                )
                handle.write(f"{_SUBLINE}\n")
                handle.write(
                    f"RESULT {fault_name}  status={result.status}  "
                    f"backtracks={result.backtracks}  steps={recorder.step_count}\n\n"
                )
                handle.flush()

    return out_path
