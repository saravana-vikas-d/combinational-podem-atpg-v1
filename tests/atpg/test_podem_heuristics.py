import pytest

from atpg.podem import iter_input_indices, select_d_frontier_gate
from circuit.circuit import Circuit, Gate, GateType, Signal
from circuit.levelize import levelize
from fault.fault import branch_fault
from logic5 import Logic5


def _gate(
    gate_id: int,
    instance_name: str,
    gate_type: GateType,
    inputs: list[Signal],
    output: Signal,
    *,
    level: int = 0,
) -> Gate:
    gate = Gate(
        id=gate_id,
        instance_name=instance_name,
        type=gate_type,
        inputs=inputs,
        output=output,
        level=level,
    )
    output.driver = gate
    for index, input_signal in enumerate(inputs):
        input_signal.fanouts.append((gate, index))
    return gate


def test_select_d_frontier_gate_picks_highest_level():
    low = Gate(id=0, instance_name="G_LOW", type=GateType.AND, inputs=[], output=Signal("z0"), level=2)
    high = Gate(id=1, instance_name="G_HIGH", type=GateType.AND, inputs=[], output=Signal("z1"), level=5)

    assert select_d_frontier_gate([low, high]) is high


def test_select_d_frontier_gate_tie_breaks_on_gate_id():
    first = Gate(id=0, instance_name="G_A", type=GateType.AND, inputs=[], output=Signal("z0"), level=3)
    second = Gate(id=1, instance_name="G_B", type=GateType.AND, inputs=[], output=Signal("z1"), level=3)

    assert select_d_frontier_gate([first, second]) is second


def test_select_d_frontier_gate_rejects_empty_frontier():
    with pytest.raises(ValueError, match="D-frontier is empty"):
        select_d_frontier_gate([])


def test_iter_input_indices_prefers_primary_input():
    pi = Signal("a", is_pi=True, level=0)
    internal = Signal("w", level=2)
    output = Signal("z", is_po=True)
    gate = _gate(0, "AND1", GateType.AND, [internal, pi], output)

    assert iter_input_indices(gate) == [1, 0]


def test_iter_input_indices_prefers_lower_level():
    low = Signal("a", level=1)
    high = Signal("b", level=4)
    output = Signal("z", is_po=True)
    gate = _gate(0, "AND1", GateType.AND, [high, low], output)

    assert iter_input_indices(gate) == [1, 0]


def test_iter_input_indices_prefers_x_over_assigned_values():
    assigned = Signal("a", level=1)
    unknown = Signal("b", level=1)
    output = Signal("z", is_po=True)
    assigned.value = Logic5.ONE
    unknown.value = Logic5.X
    gate = _gate(0, "AND1", GateType.AND, [assigned, unknown], output)

    assert iter_input_indices(gate) == [1, 0]


def test_iter_input_indices_prefers_d_over_zero_or_one():
    fixed = Signal("a", level=1)
    sensitized = Signal("b", level=1)
    output = Signal("z", is_po=True)
    fixed.value = Logic5.ZERO
    sensitized.value = Logic5.D
    gate = _gate(0, "AND1", GateType.AND, [fixed, sensitized], output)

    assert iter_input_indices(gate) == [1, 0]


def test_iter_input_indices_full_priority_chain():
    pi_x = Signal("pi", is_pi=True, level=0)
    low_x = Signal("low", level=1)
    low_d = Signal("mid", level=1)
    high_one = Signal("high", level=3)
    output = Signal("z", is_po=True)

    pi_x.value = Logic5.X
    low_x.value = Logic5.X
    low_d.value = Logic5.D
    high_one.value = Logic5.ONE

    gate = _gate(0, "AND1", GateType.AND, [high_one, low_d, low_x, pi_x], output)

    assert iter_input_indices(gate) == [3, 2, 1, 0]


def test_iter_input_indices_uses_branch_fault_at_targeted_input():
    stem = Signal("s", is_pi=True, level=0)
    output = Signal("z", is_po=True)
    gate = _gate(0, "AND1", GateType.AND, [stem, stem], output)

    stem.value = Logic5.ONE
    fault = branch_fault("s", "AND1", 0, 0)

    assert iter_input_indices(gate, active_fault=fault) == [0, 1]
