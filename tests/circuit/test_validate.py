from pathlib import Path

import pytest

from circuit.circuit import Circuit, Gate, GateType, Signal
from circuit.validate import ValidationError, validate
from parser.iscas_verilog import parse_iscas_verilog

ISCAS = Path(__file__).resolve().parents[2] / "ISCAS85_Circuits"


def test_validate_passes_for_parsed_c17():
    circuit = parse_iscas_verilog(ISCAS / "c17.v")
    validate(circuit)


def test_validate_passes_for_parsed_c432():
    circuit = parse_iscas_verilog(ISCAS / "c432.v")
    validate(circuit)


def test_undriven_primary_output():
    circuit = Circuit(name="m")
    output = Signal("out", is_po=True)
    circuit.signals["out"] = output
    circuit.primary_outputs.append(output)

    with pytest.raises(ValidationError, match="undriven primary output 'out'"):
        validate(circuit)


def test_undriven_internal_wire():
    circuit = Circuit(name="m")
    wire = Signal("w")
    circuit.signals["w"] = wire

    with pytest.raises(ValidationError, match="undriven internal wire 'w'"):
        validate(circuit)


def test_primary_input_must_not_be_driven():
    circuit = Circuit(name="m")
    pi = Signal("a", is_pi=True)
    wire = Signal("w")
    circuit.signals["a"] = pi
    circuit.signals["w"] = wire
    circuit.primary_inputs.append(pi)

    gate = Gate(
        id=0,
        instance_name="G1",
        type=GateType.BUF,
        inputs=[pi],
        output=wire,
    )
    wire.driver = gate
    pi.driver = gate
    circuit.gates.append(gate)

    with pytest.raises(ValidationError, match="primary input 'a' must not be driven"):
        validate(circuit)


def test_driver_output_mismatch():
    circuit = Circuit(name="m")
    wire_a = Signal("a")
    wire_b = Signal("b")
    circuit.signals["a"] = wire_a
    circuit.signals["b"] = wire_b

    gate = Gate(
        id=0,
        instance_name="G1",
        type=GateType.BUF,
        inputs=[wire_a],
        output=wire_a,
    )
    wire_b.driver = gate
    circuit.gates.append(gate)

    with pytest.raises(ValidationError, match="undriven internal wire 'a'"):
        validate(circuit)


def test_unused_internal_wire_when_enabled():
    circuit = Circuit(name="m")
    used = Signal("used")
    unused = Signal("unused")
    pi = Signal("a", is_pi=True)
    circuit.signals["used"] = used
    circuit.signals["unused"] = unused
    circuit.signals["a"] = pi
    circuit.primary_inputs.append(pi)

    gate = Gate(
        id=0,
        instance_name="G1",
        type=GateType.BUF,
        inputs=[pi],
        output=used,
    )
    used.driver = gate
    pi.fanouts.append((gate, 0))
    circuit.gates.append(gate)

    validate(circuit)
    with pytest.raises(ValidationError, match="unused internal wire 'unused'"):
        validate(circuit, check_unused=True)
