"""Human-readable circuit dumps for manual verification."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from io import StringIO
from pathlib import Path

from circuit.circuit import Circuit, Signal

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_OUTPUT_DIR = _PROJECT_ROOT / "Circuit_prints"
_LINE = "=" * 80
_SUBLINE = "-" * 80


def _signal_role(signal: Signal) -> str:
    if signal.is_pi:
        return "PI"
    if signal.is_po:
        return "PO"
    return "W"


def _format_driver(signal: Signal) -> str:
    if signal.driver is None:
        return "-"
    return signal.driver.instance_name


def _format_fanouts(signal: Signal) -> str:
    if not signal.fanouts:
        return "-"
    return ", ".join(f"{gate.instance_name}[{index}]" for gate, index in signal.fanouts)


def _gate_type_summary(circuit: Circuit) -> str:
    counts = Counter(gate.type.name for gate in circuit.gates)
    if not counts:
        return "-"
    return ", ".join(f"{name}={count}" for name, count in sorted(counts.items()))


def _internal_wire_count(circuit: Circuit) -> int:
    return sum(1 for signal in circuit.signals.values() if not signal.is_pi and not signal.is_po)


def _write_summary(out: StringIO, circuit: Circuit) -> None:
    level_groups = len(circuit.levels)
    level_note = str(level_groups) if level_groups else "0 (not levelized)"

    out.write(f"{_LINE}\n")
    out.write(f"CIRCUIT: {circuit.name}\n")
    out.write(f"{_LINE}\n")
    out.write(f"Primary inputs  : {len(circuit.primary_inputs)}\n")
    out.write(f"Primary outputs : {len(circuit.primary_outputs)}\n")
    out.write(f"Internal wires  : {_internal_wire_count(circuit)}\n")
    out.write(f"Total signals   : {len(circuit.signals)}\n")
    out.write(f"Total gates     : {len(circuit.gates)}\n")
    out.write(f"Level groups    : {level_note}\n")
    out.write(f"Gate types      : {_gate_type_summary(circuit)}\n")
    out.write(f"{_LINE}\n\n")


def _write_ports(out: StringIO, circuit: Circuit) -> None:
    out.write("PRIMARY INPUTS (declaration order)\n")
    for index, signal in enumerate(circuit.primary_inputs):
        out.write(f"  [{index}] {signal.name}\n")
    out.write("\n")

    out.write("PRIMARY OUTPUTS (declaration order)\n")
    for index, signal in enumerate(circuit.primary_outputs):
        out.write(f"  [{index}] {signal.name}\n")
    out.write("\n")


def _write_gates(out: StringIO, circuit: Circuit) -> None:
    out.write("GATES (parse order, id=0..n-1)\n")
    for gate in circuit.gates:
        inputs = ", ".join(signal.name for signal in gate.inputs)
        gate_type = gate.type.name.lower()
        out.write(
            f"  [{gate.id}] {gate.instance_name:<12} {gate_type:<4} "
            f"{gate.output.name}  <=  {inputs}\n"
        )
    out.write("\n")


def _write_signals(out: StringIO, circuit: Circuit) -> None:
    out.write("SIGNALS\n")
    out.write(f"{_SUBLINE}\n")

    current_role: str | None = None
    for signal in circuit.signals.values():
        role = _signal_role(signal)
        if role != current_role:
            if current_role is not None:
                out.write("\n")
            current_role = role

        out.write(
            f"{role:<3} {signal.name:<8} driver={_format_driver(signal):<12} "
            f"fanouts={_format_fanouts(signal)}\n"
        )
    out.write("\n")


def _write_levels(out: StringIO, circuit: Circuit) -> None:
    out.write("LEVELS\n")
    if not circuit.levels:
        out.write("  (not levelized)\n")
        return

    for level_index, gates in enumerate(circuit.levels):
        gate_names = ", ".join(gate.instance_name for gate in gates)
        out.write(f"  level {level_index}: {gate_names}\n")


def format_circuit(circuit: Circuit) -> str:
    """Return a human-readable text representation of a parsed circuit."""
    out = StringIO()
    _write_summary(out, circuit)
    _write_ports(out, circuit)
    _write_gates(out, circuit)
    _write_signals(out, circuit)
    _write_levels(out, circuit)
    return out.getvalue()


def dump_circuit(
    circuit: Circuit,
    output_dir: str | Path | None = None,
    *,
    timestamp: datetime | None = None,
) -> Path:
    """Write :func:`format_circuit` output to ``Circuit_prints/<name>_<timestamp>.txt``."""
    target_dir = Path(output_dir) if output_dir is not None else _DEFAULT_OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    when = timestamp or datetime.now()
    filename = f"{circuit.name}_{when.strftime('%d%m%Y_%H%M')}.txt"
    path = target_dir / filename
    path.write_text(format_circuit(circuit), encoding="utf-8")
    return path


def print_circuit_from_file(
    verilog_path: str | Path,
    output_dir: str | Path | None = None,
    *,
    timestamp: datetime | None = None,
) -> Path:
    """Parse a Verilog netlist and write a formatted circuit dump to disk."""
    from parser.iscas_verilog import parse_iscas_verilog

    circuit = parse_iscas_verilog(verilog_path)
    return dump_circuit(circuit, output_dir, timestamp=timestamp)
