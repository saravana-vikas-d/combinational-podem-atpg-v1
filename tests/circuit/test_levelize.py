from pathlib import Path

import pytest

from circuit.circuit import Circuit, Gate, GateType, Signal
from circuit.levelize import CycleError, levelize
from parser.iscas_verilog import parse_iscas_verilog

ISCAS = Path(__file__).resolve().parents[2] / "ISCAS85_Circuits"


def _assert_level_monotonicity(circuit: Circuit) -> None:
    for level_gates in circuit.levels:
        for gate in level_gates:
            assert all(input_signal.level < gate.level for input_signal in gate.inputs)


def test_c17_max_level_and_partition():
    circuit = parse_iscas_verilog(ISCAS / "c17.v")
    levelize(circuit)

    assert all(signal.level == 0 for signal in circuit.primary_inputs)
    assert circuit.signals["N22"].level == 3
    assert circuit.signals["N23"].level == 3
    assert max(gate.level for gate in circuit.gates) == 3
    assert sum(len(level_gates) for level_gates in circuit.levels) == len(circuit.gates)
    assert [len(level_gates) for level_gates in circuit.levels] == [2, 2, 2]
    assert [gate.instance_name for gate in circuit.levels[0]] == [
        "NAND2_1",
        "NAND2_2",
    ]
    _assert_level_monotonicity(circuit)


def test_levelize_c432():
    circuit = parse_iscas_verilog(ISCAS / "c432.v")
    levelize(circuit)

    assert all(signal.level == 0 for signal in circuit.primary_inputs)
    assert sum(len(level_gates) for level_gates in circuit.levels) == len(circuit.gates)
    _assert_level_monotonicity(circuit)


def test_cycle_detection():
    n1 = Signal("N1", is_pi=True)
    n2 = Signal("N2")
    n3 = Signal("N3")

    g1 = Gate(id=0, instance_name="G1", type=GateType.BUF, inputs=[n2], output=n3)
    g2 = Gate(id=1, instance_name="G2", type=GateType.BUF, inputs=[n3], output=n2)

    n2.driver = g2
    n3.driver = g1
    n2.fanouts = [(g1, 0)]
    n3.fanouts = [(g2, 0)]

    circuit = Circuit(
        name="loop",
        signals={"N1": n1, "N2": n2, "N3": n3},
        gates=[g1, g2],
        primary_inputs=[n1],
    )

    with pytest.raises(CycleError, match="combinational loop"):
        levelize(circuit)


def test_c6288_max_depth():
    circuit = parse_iscas_verilog(ISCAS / "c6288.v")
    levelize(circuit)

    max_level = max(gate.level for gate in circuit.gates)
    assert max_level == 124
    assert sum(len(level_gates) for level_gates in circuit.levels) == len(circuit.gates)
