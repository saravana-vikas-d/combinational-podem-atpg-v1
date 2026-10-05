from atpg.podem import AssignmentFrame, push_assignments, restore_frames
from circuit.circuit import Circuit, Signal
from logic5 import Logic5


def _circuit_with_signals(*signals: Signal) -> Circuit:
    return Circuit(
        name="bt",
        signals={signal.name: signal for signal in signals},
    )


def test_push_assignments_records_changed_signals_only():
    a = Signal("a", is_pi=True)
    b = Signal("b", is_pi=True)
    circuit = _circuit_with_signals(a, b)
    b.value = Logic5.ONE

    frames = push_assignments(
        circuit,
        [(a, Logic5.ZERO), (b, Logic5.ONE)],
        gate_instance="AND1",
        desired=Logic5.ONE,
        input_index=0,
    )

    assert frames is not None
    assert len(frames) == 1
    assert frames[0] == AssignmentFrame(
        signal_name="a",
        old_value=Logic5.X,
        new_value=Logic5.ZERO,
        gate_instance="AND1",
        desired=Logic5.ONE,
        input_index=0,
    )
    assert a.value is Logic5.ZERO
    assert b.value is Logic5.ONE


def test_push_assignments_returns_none_and_restores_on_conflict():
    a = Signal("a", is_pi=True)
    b = Signal("b", is_pi=True)
    circuit = _circuit_with_signals(a, b)
    a.value = Logic5.ONE

    frames = push_assignments(circuit, [(b, Logic5.ZERO), (a, Logic5.ZERO)])

    assert frames is None
    assert a.value is Logic5.ONE
    assert b.value is Logic5.X


def test_restore_frames_undoes_assignments_in_reverse_order():
    a = Signal("a", is_pi=True)
    b = Signal("b", is_pi=True)
    circuit = _circuit_with_signals(a, b)

    frames = push_assignments(circuit, [(a, Logic5.ONE), (b, Logic5.ZERO)])
    assert frames is not None

    restore_frames(circuit, frames)

    assert a.value is Logic5.X
    assert b.value is Logic5.X


def test_restore_frames_partial_stack():
    a = Signal("a", is_pi=True)
    b = Signal("b", is_pi=True)
    c = Signal("c", is_pi=True)
    circuit = _circuit_with_signals(a, b, c)

    first = push_assignments(circuit, [(a, Logic5.ONE)])
    second = push_assignments(circuit, [(b, Logic5.ZERO), (c, Logic5.ONE)])
    assert first is not None
    assert second is not None

    restore_frames(circuit, second)

    assert a.value is Logic5.ONE
    assert b.value is Logic5.X
    assert c.value is Logic5.X

    restore_frames(circuit, first)
    assert a.value is Logic5.X
