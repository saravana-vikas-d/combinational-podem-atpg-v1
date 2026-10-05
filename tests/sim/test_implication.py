from pathlib import Path

import pytest

from circuit.circuit import Circuit, Gate, GateType, Signal
from circuit.levelize import levelize
from fault.fault import branch_fault, line_fault
from logic5 import Logic5
from parser.iscas_verilog import parse_iscas_verilog
from sim.implication import (
    ImplicationError,
    _try_assign,
    forward_imply,
    inject_fault,
    resolve_input_value,
    reset_values,
)

ISCAS = Path(__file__).resolve().parents[2] / "ISCAS85_Circuits"


def _mini_circuit() -> Circuit:
    n1 = Signal("N1", is_pi=True)
    n3 = Signal("N3", is_pi=True)
    n10 = Signal("N10")
    n22 = Signal("N22", is_po=True)

    g1 = Gate(
        id=0,
        instance_name="NAND2_1",
        type=GateType.NAND,
        inputs=[n1, n3],
        output=n10,
    )
    g2 = Gate(
        id=1,
        instance_name="NOT1_1",
        type=GateType.NOT,
        inputs=[n10],
        output=n22,
    )

    n10.driver = g1
    n22.driver = g2
    n1.fanouts.append((g1, 0))
    n3.fanouts.append((g1, 1))
    n10.fanouts.append((g2, 0))

    signals = {s.name: s for s in (n1, n3, n10, n22)}
    return Circuit(
        name="mini",
        signals=signals,
        gates=[g1, g2],
        primary_inputs=[n1, n3],
        primary_outputs=[n22],
    )


def test_forward_imply_requires_levelization():
    circuit = _mini_circuit()
    circuit.signals["N1"].value = Logic5.ONE
    circuit.signals["N3"].value = Logic5.ONE

    with pytest.raises(ImplicationError, match="not levelized"):
        forward_imply(circuit)


def test_forward_imply_mini_circuit():
    circuit = _mini_circuit()
    levelize(circuit)

    circuit.signals["N1"].value = Logic5.ONE
    circuit.signals["N3"].value = Logic5.ONE

    assert forward_imply(circuit) is True
    assert circuit.signals["N10"].value is Logic5.ZERO
    assert circuit.signals["N22"].value is Logic5.ONE


def test_forward_imply_c17_good_circuit():
    circuit = parse_iscas_verilog(ISCAS / "c17.v")
    levelize(circuit)

    circuit.signals["N1"].value = Logic5.ONE
    circuit.signals["N2"].value = Logic5.ZERO
    circuit.signals["N3"].value = Logic5.ONE
    circuit.signals["N6"].value = Logic5.ZERO
    circuit.signals["N7"].value = Logic5.ONE

    assert forward_imply(circuit) is True
    assert circuit.signals["N10"].value is Logic5.ZERO
    assert circuit.signals["N11"].value is Logic5.ONE
    assert circuit.signals["N16"].value is Logic5.ONE
    assert circuit.signals["N19"].value is Logic5.ZERO
    assert circuit.signals["N22"].value is Logic5.ONE
    assert circuit.signals["N23"].value is Logic5.ONE


def test_forward_imply_propagates_d_to_primary_output():
    circuit = parse_iscas_verilog(ISCAS / "c17.v")
    levelize(circuit)

    circuit.signals["N1"].value = Logic5.ONE
    circuit.signals["N2"].value = Logic5.ZERO
    circuit.signals["N3"].value = Logic5.D
    circuit.signals["N6"].value = Logic5.ZERO
    circuit.signals["N7"].value = Logic5.ONE

    assert forward_imply(circuit) is True
    assert circuit.signals["N10"].value is Logic5.DBAR
    assert circuit.signals["N22"].value is Logic5.D


def test_try_assign_accepts_good_rail_match_on_d():
    signal = Signal("n", is_pi=True)
    signal.value = Logic5.D

    assert _try_assign(signal, Logic5.ONE) is True
    assert signal.value is Logic5.D


def test_try_assign_rejects_conflicting_good_rail_on_d():
    signal = Signal("n", is_pi=True)
    signal.value = Logic5.D

    assert _try_assign(signal, Logic5.ZERO) is False
    assert signal.value is Logic5.D


def test_forward_imply_detects_conflict():
    circuit = _mini_circuit()
    levelize(circuit)

    circuit.signals["N1"].value = Logic5.ONE
    circuit.signals["N3"].value = Logic5.ONE
    circuit.signals["N10"].value = Logic5.ONE

    assert forward_imply(circuit) is False


def test_reset_values_clears_assignments():
    circuit = _mini_circuit()
    levelize(circuit)

    circuit.signals["N1"].value = Logic5.ONE
    circuit.signals["N3"].value = Logic5.ZERO
    circuit.signals["N10"].value = Logic5.ONE

    reset_values(circuit)

    assert circuit.signals["N1"].value is Logic5.X
    assert circuit.signals["N3"].value is Logic5.X
    assert circuit.signals["N10"].value is Logic5.X
    assert circuit.signals["N22"].value is Logic5.X


def _fanout2_and_circuit() -> Circuit:
    """Signal ``s`` fans out to two AND gates."""
    s = Signal("s", is_pi=True)
    z1 = Signal("z1", is_po=True)
    z2 = Signal("z2", is_po=True)

    g1 = Gate(id=0, instance_name="AND1", type=GateType.AND, inputs=[s, s], output=z1)
    g2 = Gate(id=1, instance_name="AND2", type=GateType.AND, inputs=[s, s], output=z2)

    z1.driver = g1
    z2.driver = g2
    s.fanouts.extend([(g1, 0), (g1, 1), (g2, 0), (g2, 1)])

    circuit = Circuit(
        name="fanout2",
        signals={"s": s, "z1": z1, "z2": z2},
        gates=[g1, g2],
        primary_inputs=[s],
        primary_outputs=[z1, z2],
    )
    levelize(circuit)
    return circuit


def test_inject_fault_stem_sets_signal_value():
    circuit = _fanout2_and_circuit()
    fault = line_fault("s", 0)

    inject_fault(circuit, fault)

    assert circuit.signals["s"].value is Logic5.D


def test_inject_fault_branch_does_not_set_stem_value():
    circuit = _fanout2_and_circuit()
    fault = branch_fault("s", "AND1", 0, 0)

    inject_fault(circuit, fault)

    assert circuit.signals["s"].value is Logic5.X


def test_resolve_input_value_applies_branch_only_on_matching_input():
    circuit = _fanout2_and_circuit()
    fault = branch_fault("s", "AND1", 0, 0)
    gate = circuit.gates[0]
    signal = circuit.signals["s"]
    signal.value = Logic5.ONE

    assert resolve_input_value(signal, gate, 0, fault) is Logic5.D
    assert resolve_input_value(signal, gate, 1, fault) is Logic5.ONE
    assert resolve_input_value(signal, circuit.gates[1], 0, fault) is Logic5.ONE


def test_forward_imply_stem_fault_affects_all_fanout_branches():
    circuit = _fanout2_and_circuit()
    fault = line_fault("s", 0)

    inject_fault(circuit, fault)
    assert forward_imply(circuit) is True
    assert circuit.signals["z1"].value is Logic5.D
    assert circuit.signals["z2"].value is Logic5.D


def test_forward_imply_branch_fault_affects_only_targeted_input():
    circuit = _fanout2_and_circuit()
    fault = branch_fault("s", "AND1", 0, 0)

    circuit.signals["s"].value = Logic5.ONE
    inject_fault(circuit, fault)

    assert forward_imply(circuit, active_fault=fault) is True
    assert circuit.signals["z1"].value is Logic5.D
    assert circuit.signals["z2"].value is Logic5.ONE


def _assign_c17_pis_for_n3_tests(circuit: Circuit) -> None:
    circuit.signals["N1"].value = Logic5.ONE
    circuit.signals["N2"].value = Logic5.ZERO
    circuit.signals["N6"].value = Logic5.ZERO
    circuit.signals["N7"].value = Logic5.ONE


def test_c17_stem_fault_sets_n3_and_propagates_to_both_fanouts():
    circuit = parse_iscas_verilog(ISCAS / "c17.v")
    levelize(circuit)
    _assign_c17_pis_for_n3_tests(circuit)

    inject_fault(circuit, line_fault("N3", 0))
    assert circuit.signals["N3"].value is Logic5.D
    assert forward_imply(circuit) is True
    assert circuit.signals["N10"].value is Logic5.DBAR
    assert circuit.signals["N11"].value is Logic5.ONE


def test_c17_branch_fault_requires_active_fault_and_only_affects_target_gate():
    without_branch = parse_iscas_verilog(ISCAS / "c17.v")
    levelize(without_branch)
    _assign_c17_pis_for_n3_tests(without_branch)
    without_branch.signals["N3"].value = Logic5.ONE
    inject_fault(without_branch, branch_fault("N3", "NAND2_1", 1, 0))

    assert forward_imply(without_branch) is True
    assert without_branch.signals["N10"].value is Logic5.ZERO

    with_branch = parse_iscas_verilog(ISCAS / "c17.v")
    levelize(with_branch)
    _assign_c17_pis_for_n3_tests(with_branch)
    with_branch.signals["N3"].value = Logic5.ONE
    fault = branch_fault("N3", "NAND2_1", 1, 0)
    inject_fault(with_branch, fault)

    assert forward_imply(with_branch, active_fault=fault) is True
    assert with_branch.signals["N10"].value is Logic5.DBAR
    assert with_branch.signals["N11"].value is Logic5.ONE


def test_reset_values_can_keep_primary_inputs():
    circuit = _mini_circuit()
    levelize(circuit)

    circuit.signals["N1"].value = Logic5.ONE
    circuit.signals["N3"].value = Logic5.ZERO
    circuit.signals["N10"].value = Logic5.ONE

    reset_values(circuit, keep_pis=True)

    assert circuit.signals["N1"].value is Logic5.ONE
    assert circuit.signals["N3"].value is Logic5.ZERO
    assert circuit.signals["N10"].value is Logic5.X
    assert circuit.signals["N22"].value is Logic5.X
