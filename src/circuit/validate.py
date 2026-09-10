"""Post-parse validation for built circuit models."""

from __future__ import annotations

from circuit.circuit import Circuit, Gate, GateType, Signal


class ValidationError(ValueError):
    """Raised when a circuit model violates netlist rules."""


def validate(circuit: Circuit, *, check_unused: bool = False) -> None:
    """Validate a parsed circuit before levelization.

    Raises :class:`ValidationError` on the first violation found.
    """
    _validate_primary_inputs(circuit)
    _validate_gate_connectivity(circuit)
    _validate_drivers(circuit)
    if check_unused:
        _validate_no_unused_internal_wires(circuit)


def _validate_primary_inputs(circuit: Circuit) -> None:
    for signal in circuit.primary_inputs:
        if signal.driver is not None:
            raise ValidationError(
                f"primary input {signal.name!r} must not be driven by "
                f"{signal.driver.instance_name!r}"
            )


def _validate_gate_connectivity(circuit: Circuit) -> None:
    for gate in circuit.gates:
        if gate.output.name not in circuit.signals:
            raise ValidationError(
                f"gate {gate.instance_name!r} output {gate.output.name!r} is not declared"
            )
        if gate.output is not circuit.signals[gate.output.name]:
            raise ValidationError(
                f"gate {gate.instance_name!r} output signal object mismatch for "
                f"{gate.output.name!r}"
            )

        for index, input_signal in enumerate(gate.inputs):
            if input_signal.name not in circuit.signals:
                raise ValidationError(
                    f"gate {gate.instance_name!r} input {input_signal.name!r} "
                    "is not declared"
                )
            if input_signal is not circuit.signals[input_signal.name]:
                raise ValidationError(
                    f"gate {gate.instance_name!r} input signal object mismatch for "
                    f"{input_signal.name!r}"
                )

        if gate.output.driver is not gate:
            raise ValidationError(
                f"gate {gate.instance_name!r} is not recorded as driver of "
                f"{gate.output.name!r}"
            )

        for index, input_signal in enumerate(gate.inputs):
            if (gate, index) not in input_signal.fanouts:
                raise ValidationError(
                    f"gate {gate.instance_name!r} missing fanout edge on input "
                    f"{input_signal.name!r}[{index}]"
                )


def _validate_drivers(circuit: Circuit) -> None:
    for name, signal in circuit.signals.items():
        if signal.is_pi:
            continue

        if signal.driver is None:
            role = "primary output" if signal.is_po else "internal wire"
            raise ValidationError(f"undriven {role} {name!r}")

        if signal.driver.output is not signal:
            raise ValidationError(
                f"signal {name!r} driver {signal.driver.instance_name!r} "
                f"does not drive {name!r}"
            )


def _validate_no_unused_internal_wires(circuit: Circuit) -> None:
    referenced: set[str] = set()
    for gate in circuit.gates:
        referenced.add(gate.output.name)
        referenced.update(input_signal.name for input_signal in gate.inputs)

    for name, signal in circuit.signals.items():
        if signal.is_pi or signal.is_po:
            continue
        if name not in referenced:
            raise ValidationError(f"unused internal wire {name!r}")
