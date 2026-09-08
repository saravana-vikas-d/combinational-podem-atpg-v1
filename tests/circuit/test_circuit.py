from circuit.circuit import Circuit, Gate, GateType, Signal


def _mini_circuit() -> Circuit:
    """Hand-built 2-input NAND → NOT, similar to a tiny slice of c17."""
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


def test_circuit_defaults():
    circuit = Circuit(name="empty")
    assert circuit.name == "empty"
    assert circuit.signals == {}
    assert circuit.gates == []
    assert circuit.primary_inputs == []
    assert circuit.primary_outputs == []
    assert circuit.levels == []


def test_circuit_mini_structure():
    circuit = _mini_circuit()

    assert circuit.name == "mini"
    assert len(circuit.signals) == 4
    assert len(circuit.gates) == 2
    assert len(circuit.primary_inputs) == 2
    assert len(circuit.primary_outputs) == 1
    assert circuit.levels == []


def test_circuit_primary_ports_are_same_signal_objects():
    circuit = _mini_circuit()

    assert circuit.primary_inputs[0] is circuit.signals["N1"]
    assert circuit.primary_inputs[1] is circuit.signals["N3"]
    assert circuit.primary_outputs[0] is circuit.signals["N22"]
    assert circuit.primary_inputs[0].is_pi is True
    assert circuit.primary_outputs[0].is_po is True


def test_circuit_primary_input_order_preserved():
    circuit = _mini_circuit()

    assert [s.name for s in circuit.primary_inputs] == ["N1", "N3"]
    assert [s.name for s in circuit.primary_outputs] == ["N22"]


def test_circuit_gates_reference_signals():
    circuit = _mini_circuit()
    g1, g2 = circuit.gates

    assert g1.output is circuit.signals["N10"]
    assert g2.inputs[0] is circuit.signals["N10"]
    assert g2.output is circuit.signals["N22"]
