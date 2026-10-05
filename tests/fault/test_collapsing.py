from pathlib import Path

from circuit.circuit import Circuit, Gate, GateType, Signal
from circuit.levelize import levelize
from fault.collapsing import (
    collapse_dominance,
    collapse_equivalence,
    collapse_faults,
    verify_collapse_partition,
)
from fault.fault import (
    branch_fault,
    fault_at_input,
    fault_name,
    format_fault,
    generate_raw_faults,
    line_fault,
    parse_fault_name,
)
from parser.iscas_verilog import parse_iscas_verilog

ISCAS = Path(__file__).resolve().parents[2] / "ISCAS85_Circuits"


def _and_circuit() -> Circuit:
    a = Signal("a", is_pi=True)
    b = Signal("b", is_pi=True)
    z = Signal("z", is_po=True)

    gate = Gate(
        id=0,
        instance_name="AND1",
        type=GateType.AND,
        inputs=[a, b],
        output=z,
    )

    z.driver = gate
    a.fanouts.append((gate, 0))
    b.fanouts.append((gate, 1))

    circuit = Circuit(
        name="and2",
        signals={"a": a, "b": b, "z": z},
        gates=[gate],
        primary_inputs=[a, b],
        primary_outputs=[z],
    )
    levelize(circuit)
    return circuit


def _fanout2_and_circuit() -> Circuit:
    """Signal ``s`` fans out to two AND gates (stem + 2 branches)."""
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


def test_generate_raw_faults_and_gate():
    circuit = _and_circuit()
    raw = generate_raw_faults(circuit)

    assert len(raw) == 6
    assert {str(fault) for fault in raw} == {
        "a_sa0",
        "a_sa1",
        "b_sa0",
        "b_sa1",
        "z_sa0",
        "z_sa1",
    }


def test_generate_raw_faults_fanout2_stem_and_branches():
    circuit = _fanout2_and_circuit()
    raw = generate_raw_faults(circuit)

    assert len(raw) == 14
    assert {str(fault) for fault in raw} == {
        "s_sa0",
        "s_sa1",
        "s__AND1_0_sa0",
        "s__AND1_0_sa1",
        "s__AND1_1_sa0",
        "s__AND1_1_sa1",
        "s__AND2_0_sa0",
        "s__AND2_0_sa1",
        "s__AND2_1_sa0",
        "s__AND2_1_sa1",
        "z1_sa0",
        "z1_sa1",
        "z2_sa0",
        "z2_sa1",
    }


def test_fault_at_input_uses_branch_when_fanout_ge_2():
    circuit = _fanout2_and_circuit()
    gate = circuit.gates[0]
    signal = circuit.signals["s"]

    fault = fault_at_input(signal, gate, 0, 0)
    assert str(fault) == "s__AND1_0_sa0"


def test_parse_fault_name_line_and_branch():
    line = parse_fault_name("N3_sa0")
    assert line == line_fault("N3", 0)

    branch = parse_fault_name("N3__NAND2_1_1_sa1")
    assert branch == branch_fault("N3", "NAND2_1", 1, 1)
    assert format_fault(branch) == "N3__NAND2_1_1_sa1"


def test_and_gate_equivalence_sa0():
    circuit = _and_circuit()
    raw = generate_raw_faults(circuit)
    eq_map = collapse_equivalence(circuit, raw)

    assert "z_sa0" in eq_map
    equivalent, dominators = eq_map["z_sa0"]
    assert equivalent == {"a_sa0", "b_sa0"}
    assert dominators == set()


def test_and_gate_dominance_sa1():
    circuit = _and_circuit()
    raw = generate_raw_faults(circuit)
    eq_map = collapse_equivalence(circuit, raw)
    final_map = collapse_dominance(circuit, eq_map)

    assert set(final_map.keys()) == {"a_sa1", "b_sa1", "z_sa0"}
    assert final_map["a_sa1"][1] == {"z_sa1"}
    assert final_map["b_sa1"][1] == {"z_sa1"}
    assert "z_sa1" not in final_map


def test_and_gate_full_collapse():
    circuit = _and_circuit()
    result = collapse_faults(circuit)

    assert result.raw_count == 6
    assert len(result.collapse_map) == 3
    assert result.equivalence_map is not None
    verify_collapse_partition(generate_raw_faults(circuit), result.collapse_map)


def test_fanout2_stem_not_equivalent_to_branch():
    circuit = _fanout2_and_circuit()
    eq_map = collapse_equivalence(circuit, generate_raw_faults(circuit))

    assert eq_map["s_sa0"] == (set(), set())
    assert "s__AND1_0_sa0" in eq_map["z1_sa0"][0]
    assert "s_sa0" not in eq_map["z1_sa0"][0]


def test_c17_raw_fault_count():
    circuit = parse_iscas_verilog(ISCAS / "c17.v")
    raw = generate_raw_faults(circuit)
    assert len(raw) == 34


def test_c17_branch_fault_names_for_n3():
    circuit = parse_iscas_verilog(ISCAS / "c17.v")
    raw = {str(fault) for fault in generate_raw_faults(circuit)}

    assert "N3_sa0" in raw
    assert "N3__NAND2_1_1_sa0" in raw
    assert "N3__NAND2_2_0_sa1" in raw


def test_c17_collapse_partition_invariants():
    circuit = parse_iscas_verilog(ISCAS / "c17.v")
    raw = generate_raw_faults(circuit)
    result = collapse_faults(circuit, raw)

    assert result.raw_count == 34
    assert len(result.collapse_map) < 34
    assert result.equivalence_map is not None
    verify_collapse_partition(raw, result.collapse_map)


def test_c17_equivalence_map_has_empty_dominators():
    circuit = parse_iscas_verilog(ISCAS / "c17.v")
    result = collapse_faults(circuit)

    assert result.equivalence_map is not None
    for _, (_, dominators) in result.equivalence_map.items():
        assert dominators == set()


def test_c17_gate_step_trace():
    circuit = parse_iscas_verilog(ISCAS / "c17.v")
    result = collapse_faults(circuit, store_gate_steps=True)

    assert result.equivalence_steps is not None
    assert result.dominance_steps is not None
    assert len(result.equivalence_steps) == 1 + len(circuit.gates)
    assert len(result.dominance_steps) == 1 + len(circuit.gates) + 1
    assert result.equivalence_steps[0].gate_instance == "START"
    assert len(result.equivalence_steps[0].collapse_map) == 34
    assert result.dominance_steps[-1].collapse_map == result.collapse_map


def test_and_gate_equivalence_steps_merge_sa0():
    circuit = _and_circuit()
    result = collapse_faults(circuit, store_gate_steps=True)

    assert result.equivalence_steps is not None
    assert len(result.equivalence_steps[0].collapse_map) == 6
    assert result.equivalence_steps[-1].collapse_map["z_sa0"][0] == {"a_sa0", "b_sa0"}


def test_fault_name_formatter():
    assert fault_name("N10", 0) == "N10_sa0"
    assert fault_name("N10", 1) == "N10_sa1"
    assert str(line_fault("N10", 1)) == "N10_sa1"
