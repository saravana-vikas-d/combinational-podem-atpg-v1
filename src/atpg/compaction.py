"""Strict fault-simulation pattern compaction (greedy set cover over collapse reps)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from atpg.fault_sim import is_fault_detected, parse_podem_report_patterns
from atpg.podem import Pattern, format_pattern
from circuit.circuit import Circuit
from fault.collapsing import CollapseMap, collapse_map_keys
from fault.fault import parse_fault_name


@dataclass(frozen=True, slots=True)
class PatternEntry:
    index: int
    origin_rep: str
    pattern: Pattern

    @property
    def pattern_text(self) -> str:
        return format_pattern(self.pattern)


@dataclass(frozen=True, slots=True)
class CompactionResult:
    circuit_name: str
    universe_reps: tuple[str, ...]
    original_count: int
    compact_count: int
    selected: tuple[PatternEntry, ...]
    dropped: tuple[PatternEntry, ...]
    coverage_by_index: dict[int, frozenset[str]]
    covered_reps: frozenset[str]
    uncovered_reps: frozenset[str]
    complete: bool
    validation_ok: bool
    validation_errors: tuple[str, ...]


ProgressCallback = Callable[[str], None]


def _noop_progress(_message: str) -> None:
    return None


def entries_from_podem_report(
    report_path: str,
    *,
    start_index: int = 1,
) -> list[PatternEntry]:
    pairs = parse_podem_report_patterns(report_path)
    return [
        PatternEntry(index=start_index + offset, origin_rep=rep, pattern=pattern)
        for offset, (rep, pattern) in enumerate(pairs)
    ]


def build_strict_rep_coverage(
    circuit: Circuit,
    entries: list[PatternEntry],
    universe: set[str],
    *,
    progress: ProgressCallback = _noop_progress,
) -> dict[int, set[str]]:
    """For each pattern, reps detected via single-vector fault sim (X stays X)."""
    coverage: dict[int, set[str]] = {entry.index: set() for entry in entries}
    if not universe or not entries:
        return coverage
    total = len(entries) * len(universe)
    done = 0
    for entry in entries:
        for rep in universe:
            fault = parse_fault_name(rep)
            if is_fault_detected(circuit, fault, entry.pattern):
                coverage[entry.index].add(rep)
            done += 1
            if total >= 5000 and done % 5000 == 0:
                progress(
                    f"  coverage sim {done}/{total} "
                    f"(pattern index {entry.index})"
                )
    return coverage


def greedy_set_cover_reps(
    universe: set[str],
    entries: list[PatternEntry],
    coverage_by_index: dict[int, set[str]],
) -> tuple[list[PatternEntry], list[PatternEntry]]:
    """Pick patterns whose strict coverage union covers as much of *universe* as possible."""
    uncovered = set(universe)
    selected: list[PatternEntry] = []
    remaining = list(entries)

    while uncovered and remaining:
        best_entry: PatternEntry | None = None
        best_gain = 0
        best_covers: set[str] = set()
        for entry in remaining:
            gain_set = coverage_by_index[entry.index] & uncovered
            gain = len(gain_set)
            if gain > best_gain:
                best_gain = gain
                best_entry = entry
                best_covers = gain_set
        if best_entry is None or best_gain == 0:
            break
        selected.append(best_entry)
        remaining.remove(best_entry)
        uncovered -= best_covers

    selected_ids = {entry.index for entry in selected}
    dropped = [entry for entry in entries if entry.index not in selected_ids]
    return selected, dropped


def validate_selected_patterns_strict(
    circuit: Circuit,
    selected: tuple[PatternEntry, ...],
    coverage_by_index: dict[int, frozenset[str]],
) -> tuple[bool, tuple[str, ...]]:
    """Re-simulate: each selected pattern must detect every rep in its coverage set."""
    errors: list[str] = []
    for entry in selected:
        expected = coverage_by_index[entry.index]
        for rep in expected:
            fault = parse_fault_name(rep)
            if not is_fault_detected(circuit, fault, entry.pattern):
                errors.append(
                    f"pattern #{entry.index} ({entry.pattern_text}) "
                    f"does not detect {rep} on re-simulation"
                )
        if entry.origin_rep not in expected:
            errors.append(
                f"pattern #{entry.index} origin rep {entry.origin_rep!r} "
                f"missing from strict coverage set"
            )
        elif not is_fault_detected(
            circuit, parse_fault_name(entry.origin_rep), entry.pattern
        ):
            errors.append(
                f"pattern #{entry.index} origin rep {entry.origin_rep!r} "
                f"fails strict detection"
            )
    return len(errors) == 0, tuple(errors)


def pattern_covers_pattern_strict(
    coverage_by_index: dict[int, frozenset[str]],
    keeper_index: int,
    candidate_index: int,
) -> bool:
    """Safe X rule: drop *candidate* only if strict coverage(keeper) ⊇ coverage(candidate)."""
    return coverage_by_index[candidate_index] <= coverage_by_index[keeper_index]


def compact_patterns_strict(
    circuit: Circuit,
    collapse_map: CollapseMap,
    entries: list[PatternEntry],
    *,
    progress: ProgressCallback = _noop_progress,
) -> CompactionResult:
    """Compact using strict sim coverage over all collapse representatives (Option B)."""
    universe = set(collapse_map_keys(collapse_map))
    progress(
        f"Building strict coverage: {len(entries)} patterns x {len(universe)} reps ..."
    )
    coverage = build_strict_rep_coverage(
        circuit, entries, universe, progress=progress
    )
    frozen = {index: frozenset(s) for index, s in coverage.items()}
    selected, dropped = greedy_set_cover_reps(universe, entries, coverage)
    covered: set[str] = set()
    for entry in selected:
        covered |= coverage[entry.index]
    uncovered = universe - covered
    selected_tuple = tuple(selected)
    validation_ok, validation_errors = validate_selected_patterns_strict(
        circuit, selected_tuple, frozen
    )
    return CompactionResult(
        circuit_name=circuit.name,
        universe_reps=tuple(sorted(universe)),
        original_count=len(entries),
        compact_count=len(selected),
        selected=selected_tuple,
        dropped=tuple(dropped),
        coverage_by_index=frozen,
        covered_reps=frozenset(covered),
        uncovered_reps=frozenset(uncovered),
        complete=len(uncovered) == 0,
        validation_ok=validation_ok,
        validation_errors=validation_errors,
    )
