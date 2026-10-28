"""Serial fault simulation to validate PODEM patterns (single-vector, X on PIs)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

from atpg.podem import Pattern, fault_detected_at_po, format_pattern
from circuit.circuit import Circuit, Signal
from fault.collapsing import CollapseMap, collapse_map_keys
from fault.fault import Fault, parse_fault_name
from logic5 import Logic5
from sim.implication import forward_imply, inject_fault, reset_values

_PATTERN_LINE_RE = re.compile(
    r"^\s*\d+\.\s+([01Xx]+)\s+<-\s+(\S+)\s*$",
)


@dataclass(frozen=True, slots=True)
class PatternSimRow:
    """One PODEM pattern simulated on good and faulty circuits."""

    index: int
    rep: str
    fault: Fault
    pattern: Pattern
    pattern_text: str
    good_po: tuple[tuple[str, Logic5], ...]
    faulty_po: tuple[tuple[str, Logic5], ...]
    detected: bool
    imply_ok: bool


@dataclass(frozen=True, slots=True)
class FaultSimReport:
    circuit_name: str
    pi_order: tuple[str, ...]
    rows: tuple[PatternSimRow, ...]
    validation_ok: bool
    mismatches: tuple[str, ...]


def snapshot_values(circuit: Circuit) -> dict[str, Logic5]:
    return {name: signal.value for name, signal in circuit.signals.items()}


def restore_values(circuit: Circuit, saved: dict[str, Logic5]) -> None:
    for name, value in saved.items():
        circuit.signals[name].value = value


def parse_pattern(text: str) -> Pattern:
    """Parse a ``0``/``1``/``X`` string in primary-input order."""
    bits: list[int | None] = []
    for char in text.strip():
        if char == "0":
            bits.append(0)
        elif char == "1":
            bits.append(1)
        elif char.upper() == "X":
            bits.append(None)
        else:
            raise ValueError(f"invalid pattern character: {char!r}")
    return tuple(bits)


def apply_pattern(circuit: Circuit, pattern: Pattern) -> None:
    """Assign PI values; ``None`` in the pattern becomes ``Logic5.X``."""
    if len(pattern) != len(circuit.primary_inputs):
        raise ValueError(
            f"pattern length {len(pattern)} != PI count {len(circuit.primary_inputs)}"
        )
    for pi, bit in zip(circuit.primary_inputs, pattern, strict=True):
        if bit is None:
            pi.value = Logic5.X
        elif bit == 0:
            pi.value = Logic5.ZERO
        elif bit == 1:
            pi.value = Logic5.ONE
        else:
            raise ValueError(f"invalid pattern bit: {bit!r}")


def primary_output_values(circuit: Circuit) -> tuple[tuple[str, Logic5], ...]:
    return tuple((po.name, po.value) for po in circuit.primary_outputs)


def format_po_values(values: tuple[tuple[str, Logic5], ...]) -> str:
    return ", ".join(f"{name}={value.display}" for name, value in values)


def simulate_good_outputs(
    circuit: Circuit,
    pattern: Pattern,
) -> tuple[tuple[tuple[str, Logic5], ...], bool]:
    """Return PO values on the fault-free circuit and whether implication succeeded."""
    saved = snapshot_values(circuit)
    try:
        apply_pattern(circuit, pattern)
        reset_values(circuit, keep_pis=True)
        ok = forward_imply(circuit, active_fault=None)
        return primary_output_values(circuit), ok
    finally:
        restore_values(circuit, saved)


def simulate_faulty_outputs(
    circuit: Circuit,
    fault: Fault,
    pattern: Pattern,
) -> tuple[tuple[tuple[str, Logic5], ...], bool, bool]:
    """Return PO values with fault present, imply ok, and detected at PO."""
    from sim.implication import effective_fault_logic5, _good_rail

    saved = snapshot_values(circuit)
    try:
        apply_pattern(circuit, pattern)
        reset_values(circuit, keep_pis=True)
        if not forward_imply(circuit, active_fault=None):
            return primary_output_values(circuit), False, False
        if fault.is_branch:
            ok = forward_imply(circuit, active_fault=fault)
        else:
            pi_names = {pi.name for pi in circuit.primary_inputs}
            signal = circuit.signals[fault.signal_name]
            good_rail = _good_rail(signal.value)
            for sig in circuit.signals.values():
                if sig.name not in pi_names:
                    sig.value = Logic5.X
            signal.value = effective_fault_logic5(good_rail, fault.stuck_at)
            ok = forward_imply(circuit, active_fault=None)
        detected = ok and fault_detected_at_po(circuit)
        return primary_output_values(circuit), ok, detected
    finally:
        restore_values(circuit, saved)


def is_fault_detected(circuit: Circuit, fault: Fault, pattern: Pattern) -> bool:
    _, _, detected = simulate_faulty_outputs(circuit, fault, pattern)
    return detected


def simulate_pattern_row(
    circuit: Circuit,
    *,
    index: int,
    rep: str,
    pattern: Pattern,
) -> PatternSimRow:
    fault = parse_fault_name(rep)
    good_po, _good_ok = simulate_good_outputs(circuit, pattern)
    faulty_po, imply_ok, detected = simulate_faulty_outputs(circuit, fault, pattern)
    return PatternSimRow(
        index=index,
        rep=rep,
        fault=fault,
        pattern=pattern,
        pattern_text=format_pattern(pattern),
        good_po=good_po,
        faulty_po=faulty_po,
        detected=detected,
        imply_ok=imply_ok,
    )


def parse_podem_report_patterns(report_path: str | Path) -> list[tuple[str, Pattern]]:
    """Extract ``(rep, pattern)`` pairs from a ``Pattern_prints/*_podem_*.txt`` file."""
    path = Path(report_path)
    in_section = False
    entries: list[tuple[str, Pattern]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() == "TEST PATTERNS":
            in_section = True
            continue
        if not in_section:
            continue
        if line.startswith("UNTESTABLE") or line.startswith("ABORTED"):
            break
        if not line.strip() or set(line.strip()) <= {"-"}:
            continue
        match = _PATTERN_LINE_RE.match(line)
        if match is None:
            continue
        pattern_text, rep = match.group(1), match.group(2)
        entries.append((rep, parse_pattern(pattern_text)))
    if not entries:
        raise ValueError(f"no test patterns found in {path}")
    return entries


def validate_representative_patterns(
    circuit: Circuit,
    entries: list[tuple[str, Pattern]],
    *,
    collapse_map: CollapseMap | None = None,
) -> FaultSimReport:
    """Simulate each ``(rep, pattern)`` pair; reps should be detected."""
    if collapse_map is not None:
        valid_reps = set(collapse_map_keys(collapse_map))
        for rep, _ in entries:
            if rep not in valid_reps:
                raise ValueError(f"pattern rep {rep!r} is not a collapse representative")

    rows = [
        simulate_pattern_row(circuit, index=index, rep=rep, pattern=pattern)
        for index, (rep, pattern) in enumerate(entries, start=1)
    ]
    mismatches = tuple(
        row.rep for row in rows if not row.detected or not row.imply_ok
    )
    pi_order = tuple(pi.name for pi in circuit.primary_inputs)
    return FaultSimReport(
        circuit_name=circuit.name,
        pi_order=pi_order,
        rows=tuple(rows),
        validation_ok=len(mismatches) == 0,
        mismatches=mismatches,
    )


def format_fault_sim_report(report: FaultSimReport) -> str:
    out = StringIO()
    line = "=" * 80
    out.write(f"{line}\n")
    out.write(f"FAULT SIMULATION REPORT: {report.circuit_name}\n")
    out.write(f"{line}\n")
    out.write(f"Primary inputs (vector order): {', '.join(report.pi_order)}\n")
    out.write(f"Patterns simulated : {len(report.rows)}\n")
    out.write(
        f"PODEM validation   : "
        f"{'PASS' if report.validation_ok else 'FAIL'}\n"
    )
    if report.mismatches:
        out.write(f"Mismatches         : {', '.join(report.mismatches)}\n")
    out.write(f"{line}\n\n")

    for row in report.rows:
        out.write(f"[{row.index}] representative: {row.rep}\n")
        out.write(f"    test vector     : {row.pattern_text}\n")
        out.write(f"    fault-free POs  : {format_po_values(row.good_po)}\n")
        out.write(f"    faulty POs      : {format_po_values(row.faulty_po)}\n")
        out.write(
            f"    detected at PO  : {'yes' if row.detected else 'no'}"
            f"  (imply ok: {'yes' if row.imply_ok else 'no'})\n"
        )
        out.write("\n")
    return out.getvalue()
