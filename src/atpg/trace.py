"""PODEM search trace recording for debug dumps."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from circuit.circuit import Gate, Signal
from logic5 import Logic5

PodemTraceKind = Literal[
    "fault_excitation",
    "init_fail",
    "init",
    "po_detected",
    "no_frontier",
    "backtrace_skip",
    "try",
    "assign_fail",
    "imply_fail",
    "imply_ok",
    "backtrack",
    "recursion_limit",
    "backtrack_limit",
    "done",
]

PodemProcess = Literal[
    "fault_excitation",
    "forward_implication",
    "backtrace",
    "d_frontier_check",
    "success_check",
    "search_control",
]

PROCESS_BY_KIND: dict[PodemTraceKind, PodemProcess] = {
    "fault_excitation": "fault_excitation",
    "init_fail": "forward_implication",
    "init": "forward_implication",
    "po_detected": "success_check",
    "no_frontier": "d_frontier_check",
    "backtrace_skip": "backtrace",
    "try": "backtrace",
    "assign_fail": "backtrace",
    "imply_fail": "forward_implication",
    "imply_ok": "forward_implication",
    "backtrack": "search_control",
    "recursion_limit": "search_control",
    "backtrack_limit": "search_control",
    "done": "search_control",
}


def process_for_kind(kind: PodemTraceKind) -> PodemProcess:
    return PROCESS_BY_KIND[kind]


@dataclass(slots=True)
class PodemTraceEvent:
    """One recorded step in a PODEM search."""

    index: int
    depth: int
    kind: PodemTraceKind
    process: PodemProcess
    gate: str | None = None
    gate_level: int | None = None
    desired: str | None = None
    input_index: int | None = None
    assignments: tuple[tuple[str, str], ...] = ()
    frontier: tuple[str, ...] = ()
    primary_outputs: tuple[tuple[str, str], ...] = ()
    primary_inputs: tuple[tuple[str, str], ...] = ()
    pattern: str | None = None
    note: str | None = None


@dataclass
class PodemTrace:
    """Collected events for one fault run."""

    fault_name: str
    events: list[PodemTraceEvent] = field(default_factory=list)
    truncated: bool = False
    result_status: str | None = None
    backtracks: int = 0


class PodemTracer:
    """Append-only PODEM event logger with an optional size cap."""

    def __init__(self, fault_name: str, *, max_events: int | None = 2000) -> None:
        self.trace = PodemTrace(fault_name=fault_name)
        self._max_events = max_events
        self._next_index = 0

    def emit(
        self,
        depth: int,
        kind: PodemTraceKind,
        *,
        gate: Gate | None = None,
        desired: Logic5 | None = None,
        input_index: int | None = None,
        assignments: list[tuple[Signal, Logic5]] | None = None,
        frontier: tuple[str, ...] = (),
        primary_outputs: tuple[tuple[str, str], ...] = (),
        primary_inputs: tuple[tuple[str, str], ...] = (),
        pattern: str | None = None,
        note: str | None = None,
    ) -> None:
        if self._max_events is not None and len(self.trace.events) >= self._max_events:
            self.trace.truncated = True
            return

        event = PodemTraceEvent(
            index=self._next_index,
            depth=depth,
            kind=kind,
            process=process_for_kind(kind),
            gate=gate.instance_name if gate is not None else None,
            gate_level=gate.level if gate is not None else None,
            desired=desired.display if desired is not None else None,
            input_index=input_index,
            assignments=_format_assignments(assignments),
            frontier=frontier,
            primary_outputs=primary_outputs,
            primary_inputs=primary_inputs,
            pattern=pattern,
            note=note,
        )
        self.trace.events.append(event)
        self._next_index += 1

    def finish(self, status: str, backtracks: int) -> PodemTrace:
        self.trace.result_status = status
        self.trace.backtracks = backtracks
        if not self.trace.truncated:
            self.emit(
                0,
                "done",
                note=f"status={status} backtracks={backtracks}",
            )
        return self.trace


def _format_assignments(
    assignments: list[tuple[Signal, Logic5]] | None,
) -> tuple[tuple[str, str], ...]:
    if not assignments:
        return ()
    return tuple((signal.name, value.display) for signal, value in assignments)
