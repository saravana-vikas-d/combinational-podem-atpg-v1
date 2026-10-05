"""Levelized forward implication and PODEM backtrace."""

from __future__ import annotations

from circuit.circuit import Circuit, Gate, GateType, Signal
from fault.fault import Fault, StuckAt
from logic5 import Logic5, eval_gate


class ImplicationError(ValueError):
    """Raised when implication preconditions are not met."""


class BacktraceError(ValueError):
    """Raised when backtrace arguments are invalid."""


def activated_fault_value(stuck_at: StuckAt) -> Logic5:
    """Return the five-valued activation for a stuck-at fault."""
    return Logic5.D if stuck_at == 0 else Logic5.DBAR


def inject_fault(circuit: Circuit, fault: Fault) -> None:
    """Activate a line/stem or branch fault.

    Line/stem faults set ``signals[fault.signal_name].value`` to ``D`` or ``D'``.
    Branch faults are applied during ``forward_imply`` via ``active_fault``.
    """
    if fault.is_branch:
        return
    circuit.signals[fault.signal_name].value = activated_fault_value(fault.stuck_at)


def resolve_input_value(
    signal: Signal,
    gate: Gate,
    input_index: int,
    active_fault: Fault | None,
) -> Logic5:
    """Return the effective five-valued value seen at a gate input."""
    if active_fault is not None and active_fault.is_branch:
        if (
            active_fault.signal_name == signal.name
            and active_fault.gate_instance == gate.instance_name
            and active_fault.input_index == input_index
        ):
            return activated_fault_value(active_fault.stuck_at)
    return signal.value


def reset_values(circuit: Circuit, *, keep_pis: bool = False) -> None:
    """Set signal values to X, optionally preserving primary inputs."""
    pi_names = {signal.name for signal in circuit.primary_inputs} if keep_pis else set()
    for signal in circuit.signals.values():
        if signal.name not in pi_names:
            signal.value = Logic5.X


def _assign_compatible(current: Logic5, assigned: Logic5) -> bool:
    """Return True when ``assigned`` matches the good-circuit rail of ``current``."""
    current_rail = _good_rail(current)
    assigned_rail = _good_rail(assigned)
    if current_rail is None or assigned_rail is None:
        return False
    return current_rail == assigned_rail


def _try_assign(signal: Signal, value: Logic5) -> bool:
    """Assign value to a signal unless it conflicts with an existing assignment."""
    if signal.value is Logic5.X:
        signal.value = value
        return True
    if signal.value is value:
        return True
    if _assign_compatible(signal.value, value):
        return True
    return False


def forward_imply(circuit: Circuit, active_fault: Fault | None = None) -> bool:
    """Propagate signal values through every gate in level order.

    When ``active_fault`` is a branch fault, the stuck value is applied only at the
    matching gate input; all other fanout paths use the stem ``signal.value``.

    Returns False if any gate output conflicts with an existing assignment.
    """
    if not circuit.levels:
        raise ImplicationError("circuit is not levelized; call levelize(circuit) first")

    for level_gates in circuit.levels:
        for gate in level_gates:
            input_values = [
                resolve_input_value(input_signal, gate, index, active_fault)
                for index, input_signal in enumerate(gate.inputs)
            ]
            computed = eval_gate(gate.type, input_values)
            if not _try_assign(gate.output, computed):
                return False
    return True


def _validate_backtrace_desired(desired: Logic5) -> None:
    if desired not in (Logic5.ZERO, Logic5.ONE):
        raise BacktraceError("backtrace desired output must be Logic5.ZERO or Logic5.ONE")


def _validate_input_index(gate: Gate, input_index: int) -> None:
    if input_index < 0 or input_index >= len(gate.inputs):
        raise BacktraceError(
            f"input_index {input_index} out of range for gate {gate.instance_name!r} "
            f"with {len(gate.inputs)} input(s)"
        )


def _validate_single_input_gate(gate: Gate, input_index: int) -> None:
    _validate_input_index(gate, input_index)
    if len(gate.inputs) != 1:
        raise BacktraceError(
            f"gate {gate.instance_name!r} requires exactly one input for backtrace"
        )
    if input_index != 0:
        raise BacktraceError(
            f"gate {gate.instance_name!r} requires input_index 0 for backtrace"
        )


def _good_rail(value: Logic5) -> int | None:
    """Return the good-circuit 0/1 rail when known."""
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


def _logic5_from_rail(bit: int) -> Logic5:
    return Logic5.ZERO if bit == 0 else Logic5.ONE


def _backtrace_and(
    gate: Gate,
    desired: Logic5,
    input_index: int,
) -> list[tuple[Signal, Logic5]]:
    if desired is Logic5.ZERO:
        return [(gate.inputs[input_index], Logic5.ZERO)]
    return [(input_signal, Logic5.ONE) for input_signal in gate.inputs]


def _backtrace_or(
    gate: Gate,
    desired: Logic5,
    input_index: int,
) -> list[tuple[Signal, Logic5]]:
    if desired is Logic5.ONE:
        return [(gate.inputs[input_index], Logic5.ONE)]
    return [(input_signal, Logic5.ZERO) for input_signal in gate.inputs]


def _backtrace_nand(
    gate: Gate,
    desired: Logic5,
    input_index: int,
) -> list[tuple[Signal, Logic5]]:
    if desired is Logic5.ZERO:
        return _backtrace_and(gate, Logic5.ONE, input_index)
    return _backtrace_and(gate, Logic5.ZERO, input_index)


def _backtrace_nor(
    gate: Gate,
    desired: Logic5,
    input_index: int,
) -> list[tuple[Signal, Logic5]]:
    if desired is Logic5.ZERO:
        return _backtrace_or(gate, Logic5.ONE, input_index)
    return _backtrace_or(gate, Logic5.ZERO, input_index)


def _backtrace_not(
    gate: Gate,
    desired: Logic5,
    input_index: int,
) -> list[tuple[Signal, Logic5]]:
    _validate_single_input_gate(gate, input_index)
    if desired is Logic5.ZERO:
        return [(gate.inputs[0], Logic5.ONE)]
    return [(gate.inputs[0], Logic5.ZERO)]


def _backtrace_buf(
    gate: Gate,
    desired: Logic5,
    input_index: int,
) -> list[tuple[Signal, Logic5]]:
    _validate_single_input_gate(gate, input_index)
    return [(gate.inputs[0], desired)]


def _backtrace_xor(
    gate: Gate,
    desired: Logic5,
    input_index: int,
) -> list[tuple[Signal, Logic5]]:
    if len(gate.inputs) != 2:
        raise BacktraceError(
            f"XOR backtrace supports exactly two inputs in v1; "
            f"gate {gate.instance_name!r} has {len(gate.inputs)}"
        )

    chosen = gate.inputs[input_index]
    other = gate.inputs[1 - input_index]
    other_rail = _good_rail(other.value)
    want_same = desired is Logic5.ZERO

    if other_rail is not None:
        chosen_rail = other_rail if want_same else 1 - other_rail
        return [(chosen, _logic5_from_rail(chosen_rail))]

    chosen_rail = 0
    other_rail = chosen_rail if want_same else 1 - chosen_rail
    return [
        (chosen, _logic5_from_rail(chosen_rail)),
        (other, _logic5_from_rail(other_rail)),
    ]


def _backtrace_xnor(
    gate: Gate,
    desired: Logic5,
    input_index: int,
) -> list[tuple[Signal, Logic5]]:
    xor_desired = Logic5.ONE if desired is Logic5.ZERO else Logic5.ZERO
    return _backtrace_xor(gate, xor_desired, input_index)


def _input_good_rails(
    gate: Gate,
    active_fault: Fault | None = None,
) -> list[int | None]:
    return [
        _good_rail(resolve_input_value(input_signal, gate, index, active_fault))
        for index, input_signal in enumerate(gate.inputs)
    ]


def justification_already_satisfied(
    gate: Gate,
    desired: Logic5,
    active_fault: Fault | None = None,
) -> bool:
    """Return True when existing inputs already justify ``desired`` on ``gate.output``.

    Uses good-circuit rails at each input (including branch-fault overlays). For
    gates where one controlling input suffices, any such input is enough; where
    backtrace sets all inputs, every input must already match.
    """
    _validate_backtrace_desired(desired)
    rails = _input_good_rails(gate, active_fault)

    match gate.type:
        case GateType.AND:
            if desired is Logic5.ZERO:
                return any(rail == 0 for rail in rails)
            return bool(rails) and all(rail == 1 for rail in rails)
        case GateType.OR:
            if desired is Logic5.ONE:
                return any(rail == 1 for rail in rails)
            return bool(rails) and all(rail == 0 for rail in rails)
        case GateType.NAND:
            if desired is Logic5.ZERO:
                return bool(rails) and all(rail == 1 for rail in rails)
            return any(rail == 0 for rail in rails)
        case GateType.NOR:
            if desired is Logic5.ZERO:
                return bool(rails) and all(rail == 1 for rail in rails)
            return any(rail == 0 for rail in rails)
        case GateType.NOT | GateType.BUF:
            if len(gate.inputs) != 1:
                return False
            rail = rails[0]
            target = 0 if desired is Logic5.ZERO else 1
            return rail == target
        case GateType.XOR | GateType.XNOR:
            input_values = [
                resolve_input_value(input_signal, gate, index, active_fault)
                for index, input_signal in enumerate(gate.inputs)
            ]
            computed = eval_gate(gate.type, input_values)
            if computed is Logic5.X:
                return False
            if computed is desired:
                return True
            return _assign_compatible(computed, desired)
    return False


def backtrace(
    gate: Gate,
    desired: Logic5,
    input_index: int,
) -> list[tuple[Signal, Logic5]]:
    """Return input assignments that justify ``desired`` on a gate output.

    PODEM chooses ``input_index`` when multiple controlling inputs exist.
    Returns one justification branch; the search loop tries other combinations.
    """
    _validate_backtrace_desired(desired)
    _validate_input_index(gate, input_index)

    match gate.type:
        case GateType.AND:
            return _backtrace_and(gate, desired, input_index)
        case GateType.OR:
            return _backtrace_or(gate, desired, input_index)
        case GateType.NAND:
            return _backtrace_nand(gate, desired, input_index)
        case GateType.NOR:
            return _backtrace_nor(gate, desired, input_index)
        case GateType.NOT:
            return _backtrace_not(gate, desired, input_index)
        case GateType.BUF:
            return _backtrace_buf(gate, desired, input_index)
        case GateType.XOR:
            return _backtrace_xor(gate, desired, input_index)
        case GateType.XNOR:
            return _backtrace_xnor(gate, desired, input_index)

    raise BacktraceError(f"unsupported gate type for backtrace: {gate.type}")


def apply_backtrace(
    circuit: Circuit,
    gate: Gate,
    desired: Logic5,
    input_index: int,
    active_fault: Fault | None = None,
) -> bool:
    """Assign backtrace results and run forward implication (test helper)."""
    for signal, value in backtrace(gate, desired, input_index):
        if not _try_assign(signal, value):
            return False
    return forward_imply(circuit, active_fault)
