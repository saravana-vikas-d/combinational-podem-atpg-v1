"""Single stuck-at fault type and raw fault enumeration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from circuit.circuit import Circuit, Gate, Signal

StuckAt = Literal[0, 1]


@dataclass(frozen=True, slots=True)
class Fault:
    """A single stuck-at fault on a line or fanout branch."""

    signal_name: str
    stuck_at: StuckAt
    gate_instance: str | None = None
    input_index: int | None = None

    def __post_init__(self) -> None:
        if self.gate_instance is None:
            if self.input_index is not None:
                raise ValueError("branch fault requires gate_instance and input_index")
        elif self.input_index is None:
            raise ValueError("branch fault requires gate_instance and input_index")

    def __str__(self) -> str:
        return format_fault(self)

    @property
    def is_branch(self) -> bool:
        return self.gate_instance is not None


def format_fault(fault: Fault) -> str:
    """Format a fault as a line or branch encoded name."""
    if fault.is_branch:
        assert fault.gate_instance is not None
        assert fault.input_index is not None
        return (
            f"{fault.signal_name}__{fault.gate_instance}_"
            f"{fault.input_index}_sa{fault.stuck_at}"
        )
    return f"{fault.signal_name}_sa{fault.stuck_at}"


def fault_name(signal_name: str, stuck_at: StuckAt) -> str:
    """Format a line/stem fault as ``{signal_name}_sa{0|1}``."""
    return format_fault(line_fault(signal_name, stuck_at))


def line_fault(signal_name: str, stuck_at: StuckAt) -> Fault:
    """Line or stem fault on ``signal_name``."""
    return Fault(signal_name, stuck_at)


def branch_fault(
    signal_name: str,
    gate_instance: str,
    input_index: int,
    stuck_at: StuckAt,
) -> Fault:
    """Branch fault on one fanout edge."""
    return Fault(signal_name, stuck_at, gate_instance, input_index)


def fault_at_input(
    signal: Signal,
    gate: Gate,
    input_index: int,
    stuck_at: StuckAt,
) -> Fault:
    """Resolve the fault site on a gate input pin."""
    if len(signal.fanouts) >= 2:
        return branch_fault(signal.name, gate.instance_name, input_index, stuck_at)
    return line_fault(signal.name, stuck_at)


def fault_at_output(output: Signal, stuck_at: StuckAt) -> Fault:
    """Resolve the fault site on a gate output (line/stem)."""
    return line_fault(output.name, stuck_at)


def parse_fault_name(name: str) -> Fault:
    """Parse an encoded line or branch fault name."""
    base, stuck_at_str = name.rsplit("_sa", 1)
    if stuck_at_str not in {"0", "1"}:
        raise ValueError(f"invalid fault name: {name!r}")
    stuck_at: StuckAt = int(stuck_at_str)  # type: ignore[assignment]

    if "__" not in base:
        return line_fault(base, stuck_at)

    signal_name, branch_suffix = base.split("__", 1)
    gate_instance, input_index_str = branch_suffix.rsplit("_", 1)
    if not input_index_str.isdigit():
        raise ValueError(f"invalid branch fault name: {name!r}")
    return branch_fault(signal_name, gate_instance, int(input_index_str), stuck_at)


def generate_raw_faults(circuit: Circuit) -> list[Fault]:
    """Return SA0/SA1 faults for every line site and fanout branch site."""
    faults: list[Fault] = []
    for signal in circuit.signals.values():
        faults.append(line_fault(signal.name, 0))
        faults.append(line_fault(signal.name, 1))
        if len(signal.fanouts) >= 2:
            for gate, input_index in signal.fanouts:
                faults.append(branch_fault(signal.name, gate.instance_name, input_index, 0))
                faults.append(branch_fault(signal.name, gate.instance_name, input_index, 1))
    return faults
