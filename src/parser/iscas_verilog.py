"""ISCAS-style structural Verilog parser (direct clean-and-update)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from circuit.circuit import Circuit, Gate, GateType, Signal
from circuit.levelize import CycleError, LevelizeError, levelize
from circuit.validate import ValidationError, validate
from parser.verilog_utils import ParseError, iter_statements, split_identifiers

_MODULE_RE = re.compile(
    r"^\s*module\s+([A-Za-z_]\w*)\s*\((.*)\)\s*;\s*$",
    re.DOTALL,
)

# Non-greedy (.+?) stops at the first trailing ';' so the identifier list cannot
# swallow a later semicolon if statements were ever joined incorrectly.
#THIS IS A EXTRA DEFENSIVE MEASURE BUT SEMICOLON PASSED SPLITTING IS ALREADY DONE SO SWALLOWING A SEMICOLON IS NOT POSSIBLE
_DECL_RE = re.compile(
    r"^\s*(input|output|wire)\s+(.+?)\s*;\s*$",
    re.DOTALL,
)

_GATE_KEYWORDS = frozenset(
    {"and", "or", "nand", "nor", "not", "buf", "xor", "xnor"}
)


_GATE_RE = re.compile(
    r"^\s*(and|or|nand|nor|not|buf|xor|xnor)\s+"
    r"([A-Za-z_]\w*)\s*"
    r"\(\s*(.+?)\s*\)\s*;\s*$",
    re.IGNORECASE,
)

_SINGLE_INPUT_GATE_TYPES = frozenset({GateType.NOT, GateType.BUF})


@dataclass
class _ParseContext:
    circuit: Circuit | None = None
    module_ports: list[str] | None = None
    next_gate_id: int = 0


def parse_iscas_verilog(path: str | Path) -> Circuit:
    """Parse an ISCAS-style structural Verilog netlist into a Circuit."""
    path = Path(path)
    context = _ParseContext()

    with path.open(encoding="utf-8") as handle:
        for statement in iter_statements(handle):
            _apply_statement(context, statement)

    if context.circuit is None:
        raise ParseError(f"no module declaration found in {path}")

    _validate_module_ports(context.circuit, context.module_ports)
    try:
        validate(context.circuit, check_unused=True)
    except ValidationError as exc:
        raise ParseError(str(exc)) from exc
    try:
        levelize(context.circuit)
    except LevelizeError as exc:
        raise ParseError(str(exc)) from exc
    return context.circuit


def parse_iscas_declarations(path: str | Path) -> Circuit:
    """Backward-compatible alias for :func:`parse_iscas_verilog`."""
    return parse_iscas_verilog(path)


def _apply_statement(context: _ParseContext, statement: str) -> None:
    stripped = statement.strip()

    if stripped.startswith("module "):
        _apply_module(context, statement)
        return

    if context.circuit is None:
        raise ParseError(f"statement before module declaration: {statement!r}")

    if stripped.lower() == "endmodule":
        return

    if stripped.lower().startswith("endmodule"):
        raise ParseError(f"{stripped.lower()!r}: endmodule must not be terminated with a semicolon/ commmand after endmodule")

    circuit = context.circuit
    decl = _DECL_RE.match(statement)
    if decl:
        kind = decl.group(1)
        names = split_identifiers(decl.group(2))
        if kind == "input":
            _add_inputs(circuit, names)
        elif kind == "output":
            _add_outputs(circuit, names)
        else:
            _add_wires(circuit, names)
        return

    first = stripped.split(None, 1)[0].lower()
    if first in _GATE_KEYWORDS:
        _apply_gate(context, statement)
        return

    if stripped.startswith("assign "):
        raise ParseError(f"unsupported assign statement: {statement!r}")

    raise ParseError(f"unsupported statement: {statement!r}")


def _apply_module(context: _ParseContext, statement: str) -> None:
    if context.circuit is not None:
        raise ParseError("multiple module declarations are not supported")

    match = _MODULE_RE.match(statement)
    if not match:
        raise ParseError(f"invalid module declaration: {statement!r}")

    module_name = match.group(1)
    module_ports = split_identifiers(match.group(2))
    _ensure_unique(module_ports, "module port list")
    context.module_ports = module_ports
    context.circuit = Circuit(name=module_name)


def _ensure_unique(names: list[str], context: str) -> None:
    seen: set[str] = set()
    for name in names:
        if name in seen:
            raise ParseError(f"duplicate identifier {name!r} in {context}")
        seen.add(name)


def _validate_module_ports(circuit: Circuit, module_ports: list[str] | None) -> None:
    if module_ports is None:
        raise ParseError("module declaration is missing a port list")

    port_names = set(module_ports)
    declared_ports = {
        signal.name for signal in circuit.primary_inputs
    } | {signal.name for signal in circuit.primary_outputs}

    if port_names != declared_ports:
        missing = sorted(declared_ports - port_names)
        extra = sorted(port_names - declared_ports)
        details: list[str] = []
        if missing:
            details.append(f"missing from module port list: {missing}")
        if extra:
            details.append(f"extra in module port list: {extra}")
        raise ParseError(
            "module port list does not match input/output declarations: "
            + "; ".join(details)
        )


def _get_or_create_signal(circuit: Circuit, name: str) -> Signal:
    if name not in circuit.signals:
        circuit.signals[name] = Signal(name=name)
    return circuit.signals[name]


def _add_inputs(circuit: Circuit, names: list[str]) -> None:
    _ensure_unique(names, "input declaration")
    for name in names:
        signal = _get_or_create_signal(circuit, name)
        if signal.is_po:
            raise ParseError(f"signal {name!r} is already declared as output")
        if signal.is_pi:
            raise ParseError(f"duplicate input declaration for {name!r}")
        signal.is_pi = True
        circuit.primary_inputs.append(signal)


def _add_outputs(circuit: Circuit, names: list[str]) -> None:
    _ensure_unique(names, "output declaration")
    for name in names:
        signal = _get_or_create_signal(circuit, name)
        if signal.is_pi:
            raise ParseError(f"signal {name!r} is already declared as input")
        if signal.is_po:
            raise ParseError(f"duplicate output declaration for {name!r}")
        signal.is_po = True
        circuit.primary_outputs.append(signal)


def _add_wires(circuit: Circuit, names: list[str]) -> None:
    _ensure_unique(names, "wire declaration")
    for name in names:
        if name in circuit.signals:
            signal = circuit.signals[name]
            if signal.is_pi or signal.is_po:
                raise ParseError(
                    f"wire {name!r} conflicts with an existing port declaration"
                )
            raise ParseError(f"duplicate wire declaration for {name!r}")
        circuit.signals[name] = Signal(name=name)


def _get_signal_for_gate(circuit: Circuit, name: str, context: str) -> Signal:
    if name not in circuit.signals:
        raise ParseError(f"undeclared signal {name!r} in {context}")
    return circuit.signals[name]


def _validate_gate_pin_count(
    gate_type: GateType, instance_name: str, keyword: str, pin_count: int
) -> None:
    if gate_type in _SINGLE_INPUT_GATE_TYPES:
        if pin_count != 2:
            raise ParseError(
                f"{instance_name}: {keyword} expects 2 pins (out, in), got {pin_count}"
            )
        return

    if pin_count < 3:
        raise ParseError(
            f"{instance_name}: {keyword} expects at least 3 pins "
            f"(out, in1, in2, ...), got {pin_count}"
        )


def _apply_gate(context: _ParseContext, statement: str) -> None:
    circuit = context.circuit
    assert circuit is not None

    match = _GATE_RE.match(statement)
    if not match:
        raise ParseError(f"invalid gate instance: {statement!r}")

    keyword = match.group(1)
    instance_name = match.group(2)
    try:
        gate_type = GateType.from_v(keyword)
    except ValueError as exc:
        raise ParseError(str(exc)) from exc

    pins = split_identifiers(match.group(3))
    _validate_gate_pin_count(gate_type, instance_name, keyword, len(pins))

    output_name = pins[0]
    input_names = pins[1:]
    gate_context = f"gate {instance_name!r}"

    output_signal = _get_signal_for_gate(circuit, output_name, gate_context)
    if output_signal.is_pi:
        raise ParseError(
            f"{instance_name}: primary input {output_name!r} cannot be a gate output"
        )
    if output_signal.driver is not None:
        raise ParseError(
            f"{instance_name}: signal {output_name!r} is already driven by "
            f"{output_signal.driver.instance_name!r}"
        )

    input_signals = [
        _get_signal_for_gate(circuit, name, gate_context) for name in input_names
    ]

    gate = Gate(
        id=context.next_gate_id,
        instance_name=instance_name,
        type=gate_type,
        inputs=input_signals,
        output=output_signal,
    )
    context.next_gate_id += 1

    output_signal.driver = gate
    for index, input_signal in enumerate(input_signals):
        input_signal.fanouts.append((gate, index))

    circuit.gates.append(gate)
