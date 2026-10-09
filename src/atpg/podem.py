"""PODEM test pattern generation."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from atpg.trace import PodemTracer
from atpg.stack_dump import DecisionStackRecorder
from circuit.circuit import Circuit, Gate, Signal
from fault.collapsing import (
    CollapseMap,
    all_collapsed_members,
    collapse_map_keys,
    count_fault_sites,
)
from fault.fault import Fault, parse_fault_name
from logic5 import Logic5
from sim.implication import (
    BacktraceError,
    _try_assign,
    backtrace,
    forward_imply,
    inject_fault,
    reset_values,
    resolve_input_value,
)
from sim.objective_search import (
    Objective,
    activation_objectives,
    d_frontier_propagation_branches,
    upstream_objectives,
)

# PI bit vector in circuit.primary_inputs order; None = don't-care (X).
Pattern = tuple[int | None, ...]

PodemStatus = Literal["success", "untestable", "aborted"]

# #region agent log
_AGENT_DEBUG_LOG = (
    Path(__file__).resolve().parents[2] / ".cursor" / "debug-626127.log"
)
_AGENT_SESSION = "626127"


def _agent_debug_log(
    hypothesis_id: str,
    location: str,
    message: str,
    data: dict,
    *,
    run_id: str = "pre-fix",
) -> None:
    payload = {
        "sessionId": _AGENT_SESSION,
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    try:
        _AGENT_DEBUG_LOG.parent.mkdir(parents=True, exist_ok=True)
        with _AGENT_DEBUG_LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, default=str) + "\n")
    except OSError:
        pass


# #endregion


class PatternError(ValueError):
    """Raised when a PI pattern cannot be extracted from the current assignment."""


def _is_d_effective(value: Logic5) -> bool:
    return value in (Logic5.D, Logic5.DBAR)


def fault_detected_at_po(circuit: Circuit) -> bool:
    """Return True when fault effect (D or D') reaches any primary output."""
    return any(_is_d_effective(po.value) for po in circuit.primary_outputs)


def find_d_frontier(circuit: Circuit, active_fault: Fault | None = None) -> list[Gate]:
    """Return gates on the D-frontier: output X and at least one input D/D'.

    Branch faults use ``resolve_input_value`` so only the targeted fanout branch
    contributes D/D' at the gate input.
    """
    frontier: list[Gate] = []
    for gate in circuit.gates:
        if gate.output.value is not Logic5.X:
            continue
        for index, input_signal in enumerate(gate.inputs):
            value = resolve_input_value(input_signal, gate, index, active_fault)
            if _is_d_effective(value):
                frontier.append(gate)
                break
    return frontier


def pi_pattern_bit(value: Logic5) -> int | None:
    """Map a PI five-valued assignment to a pattern bit.

    ``0``/``1`` map directly. ``D``/``D'`` map to the good-circuit rail.
    ``X`` maps to don't-care (``None``).
    """
    match value:
        case Logic5.ZERO:
            return 0
        case Logic5.ONE:
            return 1
        case Logic5.D:
            return 1
        case Logic5.DBAR:
            return 0
        case Logic5.X:
            return None
    raise AssertionError(f"unhandled Logic5 value: {value}")


def extract_pattern(circuit: Circuit) -> Pattern:
    """Build a test pattern from current PI values in port order."""
    pattern = tuple(pi_pattern_bit(pi.value) for pi in circuit.primary_inputs)
    if not any(bit in (0, 1) for bit in pattern):
        raise PatternError("pattern requires at least one care bit (0 or 1)")
    return pattern


def format_pattern(pattern: Pattern) -> str:
    """Format a pattern as a ``0``/``1``/``X`` string in PI port order."""
    chars: list[str] = []
    for bit in pattern:
        if bit is None:
            chars.append("X")
        elif bit == 0:
            chars.append("0")
        elif bit == 1:
            chars.append("1")
        else:
            raise ValueError(f"invalid pattern bit: {bit!r}")
    return "".join(chars)


def select_d_frontier_gate(frontier: list[Gate]) -> Gate:
    """Pick the D-frontier gate closest to primary outputs (classic PODEM)."""
    if not frontier:
        raise ValueError("D-frontier is empty")
    return max(frontier, key=lambda gate: (gate.level, gate.id))


def _input_index_priority(
    gate: Gate,
    index: int,
    active_fault: Fault | None,
) -> tuple[int, int, int, int, int]:
    """Sort key for justification input order (lower = try first)."""
    signal = gate.inputs[index]
    value = resolve_input_value(signal, gate, index, active_fault)
    is_x = value is Logic5.X
    is_d = _is_d_effective(value)
    return (
        0 if signal.is_pi else 1,
        signal.level,
        0 if is_x else 1,
        0 if is_d else 1,
        index,
    )


def iter_input_indices(gate: Gate, active_fault: Fault | None = None) -> list[int]:
    """Return input indices in PODEM justification priority order.

    Priority: PI first → lowest ``signal.level`` → ``X`` → ``D``/``D'`` → port index.
    """
    return sorted(range(len(gate.inputs)), key=lambda index: _input_index_priority(gate, index, active_fault))


@dataclass(slots=True)
class AssignmentFrame:
    """One signal assignment made during PODEM search (for backtrack restore)."""

    signal_name: str
    old_value: Logic5
    new_value: Logic5
    gate_instance: str | None = None
    desired: Logic5 | None = None
    input_index: int | None = None


def push_assignments(
    circuit: Circuit,
    assignments: list[tuple[Signal, Logic5]],
    *,
    gate_instance: str | None = None,
    desired: Logic5 | None = None,
    input_index: int | None = None,
) -> list[AssignmentFrame] | None:
    """Apply backtrace assignments and record frames for changed signals.

    Returns the assignment frames on success. On conflict, restores any partial
    assignments from this call and returns ``None``.
    """
    frames: list[AssignmentFrame] = []
    for signal, value in assignments:
        old_value = signal.value
        if not _try_assign(signal, value):
            restore_frames(circuit, frames)
            return None
        if signal.value is not old_value:
            frames.append(
                AssignmentFrame(
                    signal_name=signal.name,
                    old_value=old_value,
                    new_value=signal.value,
                    gate_instance=gate_instance,
                    desired=desired,
                    input_index=input_index,
                )
            )
    return frames


def restore_frames(circuit: Circuit, frames: list[AssignmentFrame]) -> None:
    """Undo assignments recorded in ``frames`` (last frame restored first)."""
    for frame in reversed(frames):
        circuit.signals[frame.signal_name].value = frame.old_value


def _snapshot_values(circuit: Circuit) -> dict[str, Logic5]:
    """Capture every signal value (used before imply/recurse branches)."""
    return {name: signal.value for name, signal in circuit.signals.items()}


def _restore_snapshot(circuit: Circuit, snapshot: dict[str, Logic5]) -> None:
    """Restore all signal values from a snapshot."""
    for name, value in snapshot.items():
        circuit.signals[name].value = value


DEFAULT_RECURSION_LIMIT = 500
# Stay below CPython's default recursion limit (~1000 frames).
_MAX_RECURSION_DEPTH = 900


def _effective_recursion_limit(recursion_limit: int | None) -> int | None:
    if recursion_limit is None:
        return None
    return min(recursion_limit, _MAX_RECURSION_DEPTH)


@dataclass
class _PodemSearchState:
    backtracks: int = 0
    aborted: bool = False
    abort_kind: str | None = None
    terminal_kind: str | None = None


def _trace_pis(circuit: Circuit) -> tuple[tuple[str, str], ...]:
    return tuple((pi.name, pi.value.display) for pi in circuit.primary_inputs)


def _trace_pos(circuit: Circuit) -> tuple[tuple[str, str], ...]:
    return tuple((po.name, po.value.display) for po in circuit.primary_outputs)


def _trace_frontier(circuit: Circuit, fault: Fault) -> tuple[str, ...]:
    return tuple(gate.instance_name for gate in find_d_frontier(circuit, fault))


def _fault_activation_note(circuit: Circuit, fault: Fault) -> str:
    if fault.is_branch:
        return (
            f"branch fault: stem {fault.signal_name} unchanged; "
            f"overlay at {fault.gate_instance} input {fault.input_index}"
        )
    value = circuit.signals[fault.signal_name].value.display
    return f"stem fault: {fault.signal_name}={value}"


def _emit_trace(
    tracer: PodemTracer | None,
    depth: int,
    kind: str,
    circuit: Circuit,
    fault: Fault,
    **kwargs,
) -> None:
    if tracer is None:
        return
    tracer.emit(
        depth,
        kind,
        frontier=_trace_frontier(circuit, fault),
        primary_outputs=_trace_pos(circuit),
        primary_inputs=_trace_pis(circuit),
        **kwargs,
    )


def _record_backtrack(
    state: _PodemSearchState,
    backtrack_limit: int | None,
    *,
    tracer: PodemTracer | None = None,
    circuit: Circuit | None = None,
    fault: Fault | None = None,
    depth: int = 0,
) -> bool:
    """Increment backtracks; return True when the search should abort."""
    state.backtracks += 1
    if backtrack_limit is not None and state.backtracks >= backtrack_limit:
        state.aborted = True
        state.abort_kind = "backtrack_limit"
        if tracer is not None and circuit is not None and fault is not None:
            _emit_trace(tracer, depth, "backtrack_limit", circuit, fault)
        return True
    return False


def _expand_objective_combos(
    objective: Objective,
    fault: Fault,
) -> list[tuple[Gate, Logic5, int, list[tuple[Signal, Logic5]]]]:
    """Return backtrace branches for one queue objective."""
    if objective.gate is None:
        return []

    gate = objective.gate
    desired = objective.desired
    if objective.input_index is not None:
        indices = [objective.input_index]
    else:
        indices = iter_input_indices(gate, fault)

    branches: list[tuple[Gate, Logic5, int, list[tuple[Signal, Logic5]]]] = []
    for input_index in indices:
        try:
            assignments = backtrace(gate, desired, input_index)
        except BacktraceError:
            continue
        branches.append((gate, desired, input_index, assignments))
    return branches


def _restore_search_branch(
    circuit: Circuit,
    snapshot: dict[str, Logic5],
    stack_recorder: DecisionStackRecorder | None,
    *,
    depth: int,
    reason: str,
    state: _PodemSearchState,
    queue_context: str = "",
) -> None:
    if stack_recorder is not None:
        stack_recorder.emit_before_restore(
            circuit,
            depth=depth,
            reason=reason,
            backtracks=state.backtracks,
            queue_context=queue_context,
        )
        stack_recorder.pop_branch()
    _restore_snapshot(circuit, snapshot)


def _objective_search(
    circuit: Circuit,
    fault: Fault,
    queue: list[Objective],
    state: _PodemSearchState,
    backtrack_limit: int | None,
    recursion_limit: int | None,
    tracer: PodemTracer | None = None,
    depth: int = 0,
    *,
    after_activation: bool = False,
    stack_recorder: DecisionStackRecorder | None = None,
) -> Pattern | None:
    if stack_recorder is not None:
        stack_recorder.note_objective_step(
            depth=depth,
            backtracks=state.backtracks,
            queue=queue,
        )

    if recursion_limit is not None and depth >= recursion_limit:
        state.aborted = True
        state.abort_kind = "recursion_depth_limit"
        state.terminal_kind = "recursion_depth_limit"
        _emit_trace(tracer, depth, "recursion_limit", circuit, fault)
        return None

    if not queue:
        if not forward_imply(circuit, active_fault=fault):
            _emit_trace(
                tracer,
                depth,
                "imply_fail",
                circuit,
                fault,
                note="forward_implication conflict",
            )
            if after_activation and depth == 0:
                _emit_trace(
                    tracer,
                    0,
                    "init_fail",
                    circuit,
                    fault,
                    note="activation forward_implication conflict",
                )
            state.terminal_kind = "imply_conflict"
            return None

        if not after_activation:
            _emit_trace(
                tracer,
                depth,
                "init",
                circuit,
                fault,
                note="activation forward_implication ok",
            )
            after_activation = True
        else:
            _emit_trace(
                tracer,
                depth,
                "imply_ok",
                circuit,
                fault,
                note="forward_implication ok",
            )

        if fault_detected_at_po(circuit):
            pattern = extract_pattern(circuit)
            _emit_trace(
                tracer,
                depth,
                "po_detected",
                circuit,
                fault,
                pattern=format_pattern(pattern),
            )
            return pattern

        frontier = find_d_frontier(circuit, fault)
        if not frontier:
            _emit_trace(tracer, depth, "no_frontier", circuit, fault)
            state.terminal_kind = "no_d_frontier"
            return None

        gate = select_d_frontier_gate(frontier)
        for branch_note, prop_queue in d_frontier_propagation_branches(gate, fault):
            if stack_recorder is not None:
                stack_recorder.push_branch(
                    depth=depth,
                    kind="propagation",
                    branch_note=branch_note,
                    queue=prop_queue,
                    backtracks=state.backtracks,
                )
            snapshot = _snapshot_values(circuit)
            pattern = _objective_search(
                circuit,
                fault,
                prop_queue,
                state,
                backtrack_limit,
                recursion_limit,
                tracer,
                depth + 1,
                after_activation=after_activation,
                stack_recorder=stack_recorder,
            )
            if pattern is not None:
                return pattern
            _restore_search_branch(
                circuit,
                snapshot,
                stack_recorder,
                depth=depth,
                reason=f"propagation subtree failed ({branch_note})",
                state=state,
                queue_context=f"D-frontier gate={gate.instance_name}",
            )
            _emit_trace(tracer, depth, "backtrack", circuit, fault, gate=gate)
            if _record_backtrack(
                state,
                backtrack_limit,
                tracer=tracer,
                circuit=circuit,
                fault=fault,
                depth=depth,
            ):
                return None
        state.terminal_kind = "propagation_branches_exhausted"
        return None

    objective = queue[0]
    rest = queue[1:]

    if objective.gate is None:
        branch_note = (
            f"line objective {objective.signal.name}={objective.desired.display}"
        )
        snapshot = _snapshot_values(circuit)
        frames = push_assignments(
            circuit,
            [(objective.signal, objective.desired)],
        )
        if frames is None:
            _emit_trace(
                tracer,
                depth,
                "assign_fail",
                circuit,
                fault,
                note="line objective assignment conflict",
            )
            state.terminal_kind = "line_objective_conflict"
            return None

        if stack_recorder is not None:
            stack_recorder.push_branch(
                depth=depth,
                kind="line_objective",
                branch_note=branch_note,
                queue=queue,
                backtracks=state.backtracks,
            )

        pattern = _objective_search(
            circuit,
            fault,
            rest,
            state,
            backtrack_limit,
            recursion_limit,
            tracer,
            depth + 1,
            after_activation=after_activation,
            stack_recorder=stack_recorder,
        )
        if pattern is not None:
            return pattern
        _restore_search_branch(
            circuit,
            snapshot,
            stack_recorder,
            depth=depth,
            reason=f"line objective subtree failed ({branch_note})",
            state=state,
            queue_context=f"remaining={len(rest)}",
        )
        _emit_trace(tracer, depth, "backtrack", circuit, fault)
        if _record_backtrack(
            state,
            backtrack_limit,
            tracer=tracer,
            circuit=circuit,
            fault=fault,
            depth=depth,
        ):
            return None
        return None

    branches = _expand_objective_combos(objective, fault)
    if not branches:
        _emit_trace(
            tracer,
            depth,
            "backtrace_skip",
            circuit,
            fault,
            gate=objective.gate,
            desired=objective.desired,
            note="no valid backtrace branch",
        )
        state.terminal_kind = "no_backtrace_branch"
        return None

    for gate, desired, input_index, assignments in branches:
        _emit_trace(
            tracer,
            depth,
            "try",
            circuit,
            fault,
            gate=gate,
            desired=desired,
            input_index=input_index,
            assignments=assignments,
            note="objective backtrace",
        )

        branch_note = (
            f"gate {gate.instance_name} desired={desired.display} "
            f"input_index={input_index} assigns="
            f"{','.join(f'{s.name}={v.display}' for s, v in assignments)}"
        )

        snapshot = _snapshot_values(circuit)
        frames = push_assignments(
            circuit,
            assignments,
            gate_instance=gate.instance_name,
            desired=desired,
            input_index=input_index,
        )
        if frames is None:
            _emit_trace(
                tracer,
                depth,
                "assign_fail",
                circuit,
                fault,
                gate=gate,
                note="backtrace assignment conflict",
            )
            if _record_backtrack(
                state,
                backtrack_limit,
                tracer=tracer,
                circuit=circuit,
                fault=fault,
                depth=depth,
            ):
                return None
            continue

        if stack_recorder is not None:
            stack_recorder.push_branch(
                depth=depth,
                kind="gate_objective",
                branch_note=branch_note,
                queue=queue,
                backtracks=state.backtracks,
            )

        new_queue = upstream_objectives(assignments, fault) + rest
        pattern = _objective_search(
            circuit,
            fault,
            new_queue,
            state,
            backtrack_limit,
            recursion_limit,
            tracer,
            depth + 1,
            after_activation=after_activation,
            stack_recorder=stack_recorder,
        )
        if pattern is not None:
            return pattern

        _emit_trace(tracer, depth, "backtrack", circuit, fault, gate=gate)
        _restore_search_branch(
            circuit,
            snapshot,
            stack_recorder,
            depth=depth,
            reason=f"gate objective subtree failed ({branch_note})",
            state=state,
            queue_context=f"new_queue={len(new_queue)} rest={len(rest)}",
        )
        if _record_backtrack(
            state,
            backtrack_limit,
            tracer=tracer,
            circuit=circuit,
            fault=fault,
            depth=depth,
        ):
            return None

    state.terminal_kind = "gate_objective_branches_exhausted"
    return None


def podem(
    circuit: Circuit,
    fault: Fault,
    *,
    backtrack_limit: int | None = None,
    recursion_limit: int | None = DEFAULT_RECURSION_LIMIT,
    tracer: PodemTracer | None = None,
    stack_recorder: DecisionStackRecorder | None = None,
) -> PodemResult:
    """Run PODEM for a single stuck-at fault."""
    active_tracer = tracer
    reset_values(circuit)
    inject_fault(circuit, fault)
    _emit_trace(
        active_tracer,
        0,
        "fault_excitation",
        circuit,
        fault,
        note=_fault_activation_note(circuit, fault),
    )

    state = _PodemSearchState()
    activation_queue = activation_objectives(circuit, fault)
    depth_limit = _effective_recursion_limit(recursion_limit)
    t0 = time.perf_counter()
    try:
        pattern = _objective_search(
            circuit,
            fault,
            activation_queue,
            state,
            backtrack_limit,
            depth_limit,
            active_tracer,
            after_activation=False,
            stack_recorder=stack_recorder,
        )
    except RecursionError:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        # #region agent log
        _agent_debug_log(
            "A3",
            "podem.py:RecursionError",
            "fault_finished",
            {
                "fault": fault.format_name() if hasattr(fault, "format_name") else str(fault),
                "status": "aborted",
                "abort_kind": "python_recursion_error",
                "terminal_kind": state.terminal_kind,
                "backtracks": state.backtracks,
                "elapsed_ms": round(elapsed_ms, 2),
                "recursion_limit": depth_limit,
                "backtrack_limit": backtrack_limit,
            },
        )
        # #endregion
        if active_tracer is not None:
            active_tracer.finish("aborted", state.backtracks)
        return PodemResult(status="aborted", backtracks=state.backtracks)

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    fault_label = (
        fault.format_name() if hasattr(fault, "format_name") else f"{fault.signal_name}_sa{fault.stuck_at}"
    )

    if pattern is not None:
        if active_tracer is not None:
            active_tracer.finish("success", state.backtracks)
        # #region agent log
        _agent_debug_log(
            "T3",
            "podem.py:success",
            "fault_finished",
            {
                "fault": fault_label,
                "status": "success",
                "backtracks": state.backtracks,
                "elapsed_ms": round(elapsed_ms, 2),
            },
        )
        # #endregion
        return PodemResult(
            status="success",
            pattern=pattern,
            backtracks=state.backtracks,
        )
    if state.aborted:
        # #region agent log
        _agent_debug_log(
            "A1",
            "podem.py:aborted",
            "fault_finished",
            {
                "fault": fault_label,
                "status": "aborted",
                "abort_kind": state.abort_kind or "unknown",
                "terminal_kind": state.terminal_kind,
                "backtracks": state.backtracks,
                "elapsed_ms": round(elapsed_ms, 2),
                "recursion_limit": depth_limit,
                "backtrack_limit": backtrack_limit,
            },
        )
        # #endregion
        if active_tracer is not None:
            active_tracer.finish("aborted", state.backtracks)
        return PodemResult(status="aborted", backtracks=state.backtracks)
    # #region agent log
    _agent_debug_log(
        "U1",
        "podem.py:untestable",
        "fault_finished",
        {
            "fault": fault_label,
            "status": "untestable",
            "terminal_kind": state.terminal_kind or "unknown",
            "backtracks": state.backtracks,
            "elapsed_ms": round(elapsed_ms, 2),
        },
    )
    # #endregion
    if active_tracer is not None:
        active_tracer.finish("untestable", state.backtracks)
    return PodemResult(status="untestable", backtracks=state.backtracks)


@dataclass(slots=True)
class PodemPattern:
    """A generated test pattern for one collapsed-fault representative."""

    rep: str
    pattern: Pattern

    @property
    def formatted(self) -> str:
        return format_pattern(self.pattern)


@dataclass(slots=True)
class PodemBatchResult:
    """Outcomes of PODEM over collapsed fault representatives."""

    patterns: list[PodemPattern]
    untestable: list[str]
    aborted: list[str]
    results: dict[str, PodemResult]
    covered: set[str]
    total_faults: int = 0
    total_backtracks: int = 0

    @property
    def coverage_percent(self) -> float:
        if self.total_faults == 0:
            return 0.0
        return 100.0 * len(self.covered) / self.total_faults


def run_podem_on_collapsed(
    circuit: Circuit,
    collapse_map: CollapseMap,
    *,
    backtrack_limit: int | None = None,
    recursion_limit: int | None = DEFAULT_RECURSION_LIMIT,
) -> PodemBatchResult:
    """Run PODEM on each uncovered collapse representative.

    When a representative succeeds, every member returned by
    ``all_collapsed_members`` is marked covered and skipped.
    """
    covered: set[str] = set()
    patterns: list[PodemPattern] = []
    untestable: list[str] = []
    aborted: list[str] = []
    results: dict[str, PodemResult] = {}
    total_backtracks = 0
    batch_t0 = time.perf_counter()

    for rep in collapse_map_keys(collapse_map):
        if rep in covered:
            continue

        result = podem(
            circuit,
            parse_fault_name(rep),
            backtrack_limit=backtrack_limit,
            recursion_limit=recursion_limit,
        )
        results[rep] = result
        total_backtracks += result.backtracks

        if result.status == "success":
            assert result.pattern is not None
            patterns.append(PodemPattern(rep=rep, pattern=result.pattern))
            covered |= all_collapsed_members(collapse_map, rep)
        elif result.status == "untestable":
            untestable.append(rep)
        else:
            aborted.append(rep)

    # #region agent log
    from collections import Counter

    status_counts = Counter(r.status for r in results.values())
    abort_kinds = Counter(
        r.backtracks
        for name, r in results.items()
        if r.status == "aborted"
    )
    slowest = sorted(
        (
            (name, results[name].backtracks, results[name].status)
            for name in results
        ),
        key=lambda row: row[1],
        reverse=True,
    )[:8]
    _agent_debug_log(
        "T1",
        "podem.py:run_podem_on_collapsed",
        "batch_summary",
        {
            "circuit": circuit.name,
            "signal_count": len(circuit.signals),
            "gate_count": len(circuit.gates),
            "pi_count": len(circuit.primary_inputs),
            "reps_run": len(results),
            "total_fault_sites": count_fault_sites(collapse_map),
            "covered_sites": len(covered),
            "coverage_percent": round(
                100.0 * len(covered) / count_fault_sites(collapse_map)
                if count_fault_sites(collapse_map)
                else 0.0,
                2,
            ),
            "status_counts": dict(status_counts),
            "untestable_reps": len(untestable),
            "aborted_reps": len(aborted),
            "total_backtracks": total_backtracks,
            "batch_elapsed_ms": round((time.perf_counter() - batch_t0) * 1000.0, 2),
            "limits": {
                "recursion_limit": recursion_limit,
                "backtrack_limit": backtrack_limit,
            },
            "aborted_at_backtrack_limit": sum(
                1
                for name in aborted
                if results[name].backtracks >= (backtrack_limit or 10**18)
            ),
            "slowest_by_backtracks": slowest,
        },
    )
    # #endregion

    return PodemBatchResult(
        patterns=patterns,
        untestable=untestable,
        aborted=aborted,
        results=results,
        covered=covered,
        total_faults=count_fault_sites(collapse_map),
        total_backtracks=total_backtracks,
    )


@dataclass(slots=True)
class PodemResult:
    """Outcome of PODEM for a single fault."""

    status: PodemStatus
    backtracks: int = 0
    pattern: Pattern | None = None

    def __post_init__(self) -> None:
        if self.backtracks < 0:
            raise ValueError("backtracks must be non-negative")
        if self.status == "success":
            if self.pattern is None:
                raise ValueError("success result requires a pattern")
            if not any(bit in (0, 1) for bit in self.pattern):
                raise ValueError("success pattern requires at least one care bit (0 or 1)")
            for bit in self.pattern:
                if bit is not None and bit not in (0, 1):
                    raise ValueError(f"invalid pattern bit: {bit!r}")
        elif self.pattern is not None:
            raise ValueError(f"{self.status!r} result must not include a pattern")
