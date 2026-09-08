"""ISCAS-style structural Verilog parser (direct clean-and-update)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from circuit.circuit import Circuit, Signal
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


@dataclass
class _ParseContext:
    circuit: Circuit | None = None
    module_ports: list[str] | None = None


def parse_iscas_declarations(path: str | Path) -> Circuit:
    """Parse module, input, output, and wire declarations into a Circuit.

    Gate instances are ignored in this phase and will be handled later.
    """
    path = Path(path)
    context = _ParseContext()

    with path.open(encoding="utf-8") as handle:
        for statement in iter_statements(handle):
            _apply_statement(context, statement)

    if context.circuit is None:
        raise ParseError(f"no module declaration found in {path}")

    _validate_module_ports(context.circuit, context.module_ports)
    return context.circuit


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

    first = stripped.split(None, 1)[0]
    if first in _GATE_KEYWORDS:
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
