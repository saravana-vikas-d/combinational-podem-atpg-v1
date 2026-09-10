"""Topological level assignment for parsed circuits."""

from __future__ import annotations

from collections import deque

from circuit.circuit import Circuit, Signal


class LevelizeError(ValueError):
    """Raised when a circuit cannot be levelized."""


class CycleError(LevelizeError):
    """Raised when the circuit graph contains a cycle."""


def levelize(circuit: Circuit) -> None:
    """Assign signal/gate levels and populate ``circuit.levels`` using Kahn's algorithm.

    Primary inputs are level 0. Each gate is assigned
    ``max(input.level) + 1`` and its output signal receives the same level.
    ``circuit.levels[level - 1]`` lists gates at that level (1-based gate levels).
    """
    _reset_levels(circuit)

    for signal in circuit.primary_inputs:
        signal.level = 0

    indegree_by_id = _build_gate_indegrees(circuit)
    ready = deque(gate for gate in circuit.gates if indegree_by_id[gate.id] == 0)
    processed = 0
    max_level = 0

    while ready:
        gate = ready.popleft()
        if any(input_signal.level < 0 for input_signal in gate.inputs):
            raise LevelizeError(
                f"gate {gate.instance_name!r} has an input with unassigned level"
            )

        gate.level = max(input_signal.level for input_signal in gate.inputs) + 1
        gate.output.level = gate.level
        max_level = max(max_level, gate.level)
        processed += 1

        for fanout_gate, _input_index in gate.output.fanouts:
            indegree_by_id[fanout_gate.id] -= 1
            if indegree_by_id[fanout_gate.id] == 0:
                ready.append(fanout_gate)

    if processed != len(circuit.gates):
        raise CycleError("circuit contains a combinational loop")

    circuit.levels = [[] for _ in range(max_level)]
    for gate in circuit.gates:
        circuit.levels[gate.level - 1].append(gate)


def _reset_levels(circuit: Circuit) -> None:
    circuit.levels = []
    for signal in circuit.signals.values():
        signal.level = -1
    for gate in circuit.gates:
        gate.level = -1


def _build_gate_indegrees(circuit: Circuit) -> dict[int, int]:
    indegree = {gate.id: 0 for gate in circuit.gates}
    for gate in circuit.gates:
        for input_signal in gate.inputs:
            if input_signal.driver is not None:
                indegree[gate.id] += 1
    return indegree
