"""Equivalence and dominance fault collapsing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from circuit.circuit import Circuit, Gate, GateType, Signal

from fault.fault import (
    Fault,
    fault_at_input,
    fault_at_output,
    format_fault,
    generate_raw_faults,
    parse_fault_name,
)

CollapseMap = dict[str, tuple[set[str], set[str]]]
# rep -> (equivalent_others, dominator_faults)

CollapsePhase = Literal["equivalence", "dominance"]


@dataclass
class CollapseGateStep:
    """Snapshot of the collapse map after one gate is processed in a phase."""

    phase: CollapsePhase
    gate_instance: str
    gate_level: int
    collapse_map: CollapseMap


@dataclass
class CollapseResult:
    """Final collapsed fault map plus optional debug state after equivalence."""

    collapse_map: CollapseMap
    raw_count: int
    equivalence_map: CollapseMap | None = None
    equivalence_steps: list[CollapseGateStep] | None = None
    dominance_steps: list[CollapseGateStep] | None = None


class _UnionFind:
    def __init__(self, items: list[str]) -> None:
        self._parent = {item: item for item in items}

    def find(self, item: str) -> str:
        parent = self._parent[item]
        if parent != item:
            self._parent[item] = self.find(parent)
        return self._parent[item]

    def union(self, left: str, right: str) -> None:
        root_left = self.find(left)
        root_right = self.find(right)
        if root_left != root_right:
            self._parent[root_right] = root_left

    def components(self) -> dict[str, set[str]]:
        grouped: dict[str, set[str]] = {}
        for item in self._parent:
            root = self.find(item)
            grouped.setdefault(root, set()).add(item)
        return grouped


def _signal_role_rank(signal: Signal) -> int:
    if signal.is_po:
        return 2
    if signal.is_pi:
        return 0
    return 1


def _fault_rep_rank(circuit: Circuit, name: str) -> tuple[int, int, str, int]:
    fault = parse_fault_name(name)
    signal = circuit.signals[fault.signal_name]
    return (
        -signal.level,
        _signal_role_rank(signal),
        fault.signal_name,
        fault.stuck_at,
    )


def _pick_rep(circuit: Circuit, members: set[str]) -> str:
    return min(members, key=lambda name: _fault_rep_rank(circuit, name))


def _equivalence_pairs(gate: Gate) -> list[tuple[Fault, Fault]]:
    pairs: list[tuple[Fault, Fault]] = []

    match gate.type:
        case GateType.AND:
            for index, inp in enumerate(gate.inputs):
                pairs.append((
                    fault_at_input(inp, gate, index, 0),
                    fault_at_output(gate.output, 0),
                ))
        case GateType.OR:
            for index, inp in enumerate(gate.inputs):
                pairs.append((
                    fault_at_input(inp, gate, index, 1),
                    fault_at_output(gate.output, 1),
                ))
        case GateType.NAND:
            for index, inp in enumerate(gate.inputs):
                pairs.append((
                    fault_at_input(inp, gate, index, 0),
                    fault_at_output(gate.output, 1),
                ))
        case GateType.NOR:
            for index, inp in enumerate(gate.inputs):
                pairs.append((
                    fault_at_input(inp, gate, index, 1),
                    fault_at_output(gate.output, 0),
                ))
        case GateType.NOT:
            inp = gate.inputs[0]
            pairs.extend([
                (fault_at_input(inp, gate, 0, 0), fault_at_output(gate.output, 1)),
                (fault_at_input(inp, gate, 0, 1), fault_at_output(gate.output, 0)),
            ])
        case GateType.BUF:
            inp = gate.inputs[0]
            pairs.extend([
                (fault_at_input(inp, gate, 0, 0), fault_at_output(gate.output, 0)),
                (fault_at_input(inp, gate, 0, 1), fault_at_output(gate.output, 1)),
            ])
        case GateType.XOR | GateType.XNOR:
            pass

    return pairs


def _dominance_pairs(gate: Gate) -> list[tuple[Fault, Fault]]:
    """Return ``(dominator, dominated)`` pairs for one gate instance."""
    pairs: list[tuple[Fault, Fault]] = []

    match gate.type:
        case GateType.AND:
            for index, inp in enumerate(gate.inputs):
                pairs.append((
                    fault_at_output(gate.output, 1),
                    fault_at_input(inp, gate, index, 1),
                ))
        case GateType.OR:
            for index, inp in enumerate(gate.inputs):
                pairs.append((
                    fault_at_output(gate.output, 0),
                    fault_at_input(inp, gate, index, 0),
                ))
        case GateType.NAND:
            for index, inp in enumerate(gate.inputs):
                pairs.append((
                    fault_at_output(gate.output, 0),
                    fault_at_input(inp, gate, index, 1),
                ))
        case GateType.NOR:
            for index, inp in enumerate(gate.inputs):
                pairs.append((
                    fault_at_output(gate.output, 1),
                    fault_at_input(inp, gate, index, 0),
                ))
        case GateType.NOT | GateType.BUF | GateType.XOR | GateType.XNOR:
            pass

    return pairs


def _copy_collapse_map(collapse_map: CollapseMap) -> CollapseMap:
    return {
        rep: (set(equivalent), set(dominators))
        for rep, (equivalent, dominators) in collapse_map.items()
    }


def _initial_collapse_map(faults: list[Fault]) -> CollapseMap:
    return {str(fault): (set(), set()) for fault in faults}


def _record_gate_step(
    steps: list[CollapseGateStep],
    *,
    phase: CollapsePhase,
    gate: Gate,
    collapse_map: CollapseMap,
) -> None:
    steps.append(
        CollapseGateStep(
            phase=phase,
            gate_instance=gate.instance_name,
            gate_level=gate.level,
            collapse_map=_copy_collapse_map(collapse_map),
        )
    )


def _build_map_from_components(
    circuit: Circuit,
    components: dict[str, set[str]],
) -> CollapseMap:
    collapse_map: CollapseMap = {}
    for members in components.values():
        rep = _pick_rep(circuit, members)
        equivalent = members - {rep}
        collapse_map[rep] = (equivalent, set())
    return collapse_map


def collapse_equivalence(
    circuit: Circuit,
    faults: list[Fault],
    *,
    record_steps: list[CollapseGateStep] | None = None,
) -> CollapseMap:
    """Merge equivalent faults and return ``rep -> (equivalent, dominator_faults)``."""
    names = [str(fault) for fault in faults]
    union_find = _UnionFind(names)

    if record_steps is not None:
        _record_gate_step(
            record_steps,
            phase="equivalence",
            gate=_initial_step_gate(circuit, "START"),
            collapse_map=_initial_collapse_map(faults),
        )

    gates_low_to_high = sorted(circuit.gates, key=lambda gate: (gate.level, gate.id))
    for gate in gates_low_to_high:
        for left, right in _equivalence_pairs(gate):
            union_find.union(str(left), str(right))

        if record_steps is not None:
            step_map = _build_map_from_components(circuit, union_find.components())
            _record_gate_step(
                record_steps,
                phase="equivalence",
                gate=gate,
                collapse_map=step_map,
            )

    return _build_map_from_components(circuit, union_find.components())


def _initial_step_gate(circuit: Circuit, label: str) -> Gate:
    """Placeholder gate metadata for pre-processing snapshots."""
    if circuit.gates:
        template = circuit.gates[0]
        return Gate(
            id=-1,
            instance_name=label,
            type=template.type,
            inputs=[],
            output=template.output,
            level=-1,
        )
    dummy = next(iter(circuit.signals.values()))
    return Gate(
        id=-1,
        instance_name=label,
        type=GateType.BUF,
        inputs=[],
        output=dummy,
        level=-1,
    )


def _class_rep(fault: str, collapse_map: CollapseMap) -> str:
    if fault in collapse_map:
        return fault
    for rep, (equivalent, _) in collapse_map.items():
        if fault in equivalent:
            return rep
    raise KeyError(f"fault {fault!r} is not a representative or equivalent member")


def collapse_dominance(
    circuit: Circuit,
    equivalence_map: CollapseMap,
    *,
    record_steps: list[CollapseGateStep] | None = None,
) -> CollapseMap:
    """Apply dominance rules to an equivalence-collapsed map."""
    collapse_map: CollapseMap = {
        rep: (set(equivalent), set(dominators))
        for rep, (equivalent, dominators) in equivalence_map.items()
    }
    remove: set[str] = set()

    if record_steps is not None:
        _record_gate_step(
            record_steps,
            phase="dominance",
            gate=_initial_step_gate(circuit, "START"),
            collapse_map=collapse_map,
        )

    gates_high_to_low = sorted(
        circuit.gates,
        key=lambda gate: (-gate.level, gate.id),
    )
    for gate in gates_high_to_low:
        for dominator, dominated in _dominance_pairs(gate):
            dominator_name = str(dominator)
            dominated_name = str(dominated)

            rep_dominator = _class_rep(dominator_name, collapse_map)
            rep_dominated = _class_rep(dominated_name, collapse_map)

            eq_d, dom_d = collapse_map[rep_dominator]
            dominator_class = {rep_dominator} | eq_d | dom_d

            eq_f, dom_f = collapse_map[rep_dominated]
            collapse_map[rep_dominated] = (eq_f, dom_f | dominator_class)
            remove.add(rep_dominator)

        if record_steps is not None:
            _record_gate_step(
                record_steps,
                phase="dominance",
                gate=gate,
                collapse_map=collapse_map,
            )

    for rep in remove:
        collapse_map.pop(rep, None)

    if record_steps is not None:
        _record_gate_step(
            record_steps,
            phase="dominance",
            gate=_initial_step_gate(circuit, "FINAL"),
            collapse_map=collapse_map,
        )

    return collapse_map


def collapse_faults(
    circuit: Circuit,
    faults: list[Fault] | None = None,
    *,
    store_equivalence_map: bool = True,
    store_gate_steps: bool = False,
) -> CollapseResult:
    """Run equivalence then dominance collapsing."""
    raw_faults = faults if faults is not None else generate_raw_faults(circuit)

    equivalence_steps: list[CollapseGateStep] | None = [] if store_gate_steps else None
    dominance_steps: list[CollapseGateStep] | None = [] if store_gate_steps else None

    equivalence_map = collapse_equivalence(
        circuit,
        raw_faults,
        record_steps=equivalence_steps,
    )

    final_map = collapse_dominance(
        circuit,
        equivalence_map,
        record_steps=dominance_steps,
    )

    return CollapseResult(
        collapse_map=final_map,
        raw_count=len(raw_faults),
        equivalence_map=equivalence_map if store_equivalence_map else None,
        equivalence_steps=equivalence_steps,
        dominance_steps=dominance_steps,
    )


def collapse_map_keys(collapse_map: CollapseMap) -> list[str]:
    """Return representative fault names in sorted order."""
    return sorted(collapse_map.keys())


def all_collapsed_members(collapse_map: CollapseMap, rep: str) -> set[str]:
    """Return the rep and every fault collapsed into it."""
    equivalent, dominators = collapse_map[rep]
    return {rep} | equivalent | dominators


def count_fault_sites(collapse_map: CollapseMap) -> int:
    """Return the number of distinct fault sites after collapsing."""
    sites: set[str] = set()
    for rep in collapse_map:
        sites |= all_collapsed_members(collapse_map, rep)
    return len(sites)


def verify_collapse_partition(
    raw_faults: list[Fault],
    collapse_map: CollapseMap,
) -> None:
    """Raise ``AssertionError`` when the collapsed map violates partition rules."""
    raw_names = {str(fault) for fault in raw_faults}
    reps = set(collapse_map.keys())
    equivalent_members: set[str] = set()
    dominator_members: set[str] = set()

    for rep, (equivalent, dominators) in collapse_map.items():
        assert rep not in equivalent
        overlap = equivalent & dominators
        assert not overlap, f"rep {rep!r} shares equivalent/dominator faults: {overlap}"
        equivalent_members.update(equivalent)
        dominator_members.update(dominators)

    assert reps.isdisjoint(equivalent_members)
    assert reps.isdisjoint(dominator_members)
    assert equivalent_members.isdisjoint(dominator_members)

    covered = reps | equivalent_members | dominator_members
    assert covered == raw_names, (
        f"missing={raw_names - covered}, extra={covered - raw_names}"
    )

    for left_rep, (left_eq, _) in collapse_map.items():
        for right_rep, (right_eq, _) in collapse_map.items():
            if left_rep == right_rep:
                continue
            overlap = left_eq & right_eq
            assert not overlap, (
                f"reps {left_rep!r} and {right_rep!r} share equivalent members: {overlap}"
            )
