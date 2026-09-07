from circuit.circuit import Gate, GateType, Signal


def test_signal_defaults():
    signal = Signal("N10")
    assert signal.name == "N10"
    assert signal.is_pi is False
    assert signal.is_po is False
    assert signal.driver is None
    assert signal.fanouts == []
    assert signal.level == -1


def test_signal_primary_input():
    signal = Signal("N1", is_pi=True)
    assert signal.is_pi is True
    assert signal.driver is None


def test_signal_primary_output():
    signal = Signal("N22", is_po=True)
    assert signal.is_po is True


def test_signal_fanouts():
    n1 = Signal("N1", is_pi=True)
    n3 = Signal("N3", is_pi=True)
    n10 = Signal("N10")
    g1 = Gate(
        id=0,
        instance_name="NAND2_1",
        type=GateType.NAND,
        inputs=[n1, n3],
        output=n10,
    )
    n10.driver = g1
    n1.fanouts.append((g1, 0))
    n3.fanouts.append((g1, 1))

    assert n10.driver is g1
    assert n1.fanouts == [(g1, 0)]
    assert n3.fanouts == [(g1, 1)]
    assert g1.inputs[0] is n1
    assert g1.inputs[1] is n3


# def test_signal_value_default():
#     from logic5 import Logic5
#     signal = Signal("N10")
#     assert signal.value is Logic5.X
