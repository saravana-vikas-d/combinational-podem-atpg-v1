"""Objective-queue justification for PODEM (activation and propagation)."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product

from circuit.circuit import Circuit, Gate, GateType, Signal
from fault.fault import Fault
from logic5 import Logic5
from sim.implication import _assign_compatible, resolve_input_value


@dataclass(frozen=True, slots=True)
class Objective:
    """Justify ``desired`` on ``signal`` (typically a gate output wire)."""

    signal: Signal
    desired: Logic5
    gate: Gate | None = None
    input_index: int | None = None


def _good_activation_value(fault: Fault) -> Logic5:
    """Good-circuit value opposite stuck-at (controllability for activation)."""
    return Logic5.ONE if fault.stuck_at == 0 else Logic5.ZERO


def _is_protected_fault_stem(signal: Signal, fault: Fault) -> bool:
    """Stem fault site keeps ``D``/``D'`` — do not add upstream objectives on it."""
    return not fault.is_branch and signal.name == fault.signal_name


def activation_objectives(circuit: Circuit, fault: Fault) -> list[Objective]:
    """Build the initial objective queue after ``inject_fault``.

    Stem fault: justify the driver gate output (or PI line) to the good activation rail.
    Branch fault: justify the stem to the good rail; ``D``/``D'`` stays on the branch pin
    during ``forward_imply(..., active_fault=fault)``.
    """
    signal = circuit.signals[fault.signal_name]
    good = _good_activation_value(fault)

    if signal.driver is None:
        return [Objective(signal=signal, desired=good, gate=None)]

    return [Objective(signal=signal, desired=good, gate=signal.driver)]


def propagation_objective(gate: Gate, desired: Logic5, input_index: int) -> Objective:
    """Single objective to justify a D-frontier gate output (binary backtrace)."""
    return Objective(
        signal=gate.output,
        desired=desired,
        gate=gate,
        input_index=input_index,
    )


def _is_d_effective(value: Logic5) -> bool:
    return value in (Logic5.D, Logic5.DBAR)


def _non_controlling_side_value(gate_type: GateType) -> Logic5:
    """Good-circuit value on non-D inputs so D/D' propagates through ``gate_type``."""
    match gate_type:
        case GateType.AND | GateType.NAND | GateType.BUF | GateType.NOT:
            return Logic5.ONE
        case GateType.OR | GateType.NOR:
            return Logic5.ZERO
        case GateType.XOR | GateType.XNOR:
            raise ValueError(
                f"{gate_type.name} has no single non-controlling value; "
                "use both 0 and 1 side-input branches"
            )
    raise AssertionError(f"unhandled gate type: {gate_type}")


def _side_input_objective(signal: Signal, desired: Logic5) -> Objective:
    if signal.is_pi or signal.driver is None:
        return Objective(signal=signal, desired=desired, gate=None)
    return Objective(signal=signal, desired=desired, gate=signal.driver)


def d_frontier_propagation_branches(
    gate: Gate,
    fault: Fault,
) -> list[tuple[str, list[Objective]]]:
    """Build objective queues that set side inputs to non-controlling values.

    Unlike binary ``propagation_objective`` (justify gate output to 0/1), this lets
    forward implication derive ``D``/``D'`` on the gate output from the existing
    fault effect input.
    """
    if not any(
        _is_d_effective(
            resolve_input_value(input_signal, gate, index, fault)
        )
        for index, input_signal in enumerate(gate.inputs)
    ):
        return []

    if gate.type in (GateType.XOR, GateType.XNOR):
        return _xor_xnor_propagation_branches(gate, fault)

    side_value = _non_controlling_side_value(gate.type)
    objectives: list[Objective] = []
    side_notes: list[str] = []

    for index, input_signal in enumerate(gate.inputs):
        effective = resolve_input_value(input_signal, gate, index, fault)
        if _is_d_effective(effective):
            continue

        current = input_signal.value
        if current is not Logic5.X:
            if not _assign_compatible(current, side_value):
                return []
            continue

        side_notes.append(f"{input_signal.name}={side_value.display}")
        objectives.append(_side_input_objective(input_signal, side_value))

    branch_note = (
        f"propagation {gate.instance_name} "
        f"side_inputs={','.join(side_notes) if side_notes else 'none'}"
    )
    return [(branch_note, objectives)]


def _xor_xnor_propagation_branches(
    gate: Gate,
    fault: Fault,
) -> list[tuple[str, list[Objective]]]:
    """D/D' propagates through XOR/XNOR for either 0 or 1 on every other input."""
    x_pins: list[Signal] = []

    for index, input_signal in enumerate(gate.inputs):
        effective = resolve_input_value(input_signal, gate, index, fault)
        if _is_d_effective(effective):
            continue
        current = input_signal.value
        if current is Logic5.X:
            x_pins.append(input_signal)
            continue
        if current not in (Logic5.ZERO, Logic5.ONE):
            return []

    if not x_pins:
        return [
            (
                f"propagation {gate.instance_name} side_inputs=none",
                [],
            )
        ]

    branches: list[tuple[str, list[Objective]]] = []
    for polarities in product((Logic5.ZERO, Logic5.ONE), repeat=len(x_pins)):
        objectives = [
            _side_input_objective(signal, value)
            for signal, value in zip(x_pins, polarities, strict=True)
        ]
        side_notes = ",".join(
            f"{signal.name}={value.display}"
            for signal, value in zip(x_pins, polarities, strict=True)
        )
        branches.append(
            (
                f"propagation {gate.instance_name} side_inputs={side_notes}",
                objectives,
            )
        )
    return branches


def upstream_objectives(
    assignments: list[tuple[Signal, Logic5]],
    fault: Fault,
) -> list[Objective]:
    """Create objectives for gate outputs that must justify backtrace input assignments."""
    objectives: list[Objective] = []
    for signal, value in assignments:
        if signal.is_pi:
            continue
        if _is_protected_fault_stem(signal, fault):
            continue
        driver = signal.driver
        if driver is not None:
            objectives.append(Objective(signal=signal, desired=value, gate=driver))
    return objectives
