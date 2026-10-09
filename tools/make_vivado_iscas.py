"""Generate ISCAS netlists that map each gate to a 7-series LUT.

Verilog built-in nand/nor/xnor are rewritten by Vivado as and/or/xor plus
an inverter. Instantiating LUT primitives with DONT_TOUCH keeps one cell
per original gate (wide gates with more than 6 inputs use a small LUT tree
inside a KEEP_HIERARCHY wrapper).
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "ISCAS85_Circuits"
DST = ROOT / "ISCAS85_Circuits_Vivado"

GATE_RE = re.compile(
    r"^\s*(and|or|nand|nor|not|buf|xor|xnor)\s+"
    r"([A-Za-z_]\w*)\s*"
    r"\(\s*(.+?)\s*\)\s*;\s*$",
    re.IGNORECASE | re.DOTALL,
)
MODULE_RE = re.compile(r"^\s*module\s+")
HEADER = (
    "// Vivado copy: each ISCAS gate is a DONT_TOUCH LUT, not a Verilog primitive.\n"
    "// Verilog nand/nor/xnor become and/or/xor + not unless mapped to LUTs.\n"
    "// Add this file AND iscas_vivado_gates.v to the Vivado project.\n"
    "// synth_design -flatten_hierarchy none -no_lc -resource_sharing off\n"
    "\n"
)


def _gate_fn(kind: str, inputs: list[int]) -> int:
    if kind == "and":
        return int(all(inputs))
    if kind == "nand":
        return int(not all(inputs))
    if kind == "or":
        return int(any(inputs))
    if kind == "nor":
        return int(not any(inputs))
    if kind == "xor":
        return sum(inputs) & 1
    if kind == "xnor":
        return int((sum(inputs) & 1) == 0)
    if kind == "not":
        return int(not inputs[0])
    if kind == "buf":
        return inputs[0]
    raise ValueError(kind)


def lut_init(kind: str, n_inputs: int) -> str:
    bits = 1 << n_inputs
    value = 0
    for addr in range(bits):
        inputs = [(addr >> bit) & 1 for bit in range(n_inputs)]
        if _gate_fn(kind, inputs):
            value |= 1 << addr
    return f"{bits}'h{value:X}"


def _ports(n_inputs: int) -> str:
    ins = ", ".join(f"I{i}" for i in range(n_inputs))
    return f"O, {ins}" if ins else "O"


def _lut_instance(kind: str, n_inputs: int, out: str, ins: list[str], inst: str) -> str:
    ports = [f".O({out})"] + [f".I{i}({name})" for i, name in enumerate(ins)]
    return (
        f'  (* DONT_TOUCH = "TRUE" *)\n'
        f"  LUT{n_inputs} #(.INIT({lut_init(kind, n_inputs)})) {inst} "
        f"({', '.join(ports)});\n"
    )


def _wide_kinds(kind: str) -> tuple[str, str]:
    """First-stage and second-stage functions for >6-input gates."""
    if kind == "and":
        return "and", "and"
    if kind == "nand":
        return "and", "nand"
    if kind == "or":
        return "or", "or"
    if kind == "nor":
        return "or", "nor"
    if kind == "xor":
        return "xor", "xor"
    if kind == "xnor":
        return "xor", "xnor"
    raise ValueError(kind)


def wrapper_module(kind: str, n_inputs: int) -> str:
    name = f"iscas_{kind}{n_inputs}"
    lines = [
        '(* DONT_TOUCH = "TRUE", KEEP_HIERARCHY = "TRUE" *)\n',
        f"module {name} ({_ports(n_inputs)});\n",
        "  output O;\n",
        f"  input {', '.join(f'I{i}' for i in range(n_inputs))};\n",
    ]
    if n_inputs <= 6:
        lines.append(
            _lut_instance(kind, n_inputs, "O", [f"I{i}" for i in range(n_inputs)], "_lut")
        )
    else:
        first_kind, second_kind = _wide_kinds(kind)
        rest = n_inputs - 5
        lines.append("  wire _partial;\n")
        lines.append(
            _lut_instance(
                first_kind,
                6,
                "_partial",
                [f"I{i}" for i in range(6)],
                "_lut0",
            )
        )
        lines.append(
            _lut_instance(
                second_kind,
                rest,
                "O",
                ["_partial"] + [f"I{i}" for i in range(6, n_inputs)],
                "_lut1",
            )
        )
    lines.append("endmodule\n")
    return "".join(lines)


def needed_wrappers(src_dir: Path) -> list[tuple[str, int]]:
    needed: set[tuple[str, int]] = set()
    for path in src_dir.glob("*.v"):
        for statement in _iter_statements(path.read_text(encoding="utf-8")):
            match = GATE_RE.match(statement)
            if not match:
                continue
            kind = match.group(1).lower()
            pins = [part.strip() for part in match.group(3).split(",") if part.strip()]
            needed.add((kind, len(pins) - 1))
    needed.add(("xnor", 2))
    return sorted(needed)


def write_gate_library(dest: Path, wrappers: list[tuple[str, int]]) -> None:
    parts = [
        "// 7-series LUT wrappers for ISCAS primitives.\n",
        "// nand/nor/xnor are LUT INIT values, not and/or/xor plus an inverter.\n",
        "// Add this file to every Vivado project that uses ISCAS85_Circuits_Vivado.\n",
        "\n",
    ]
    for kind, n_inputs in wrappers:
        parts.append(wrapper_module(kind, n_inputs))
        parts.append("\n")
    dest.write_text("".join(parts), encoding="utf-8")


def _iter_statements(text: str) -> list[str]:
    statements: list[str] = []
    buffer = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        buffer = f"{buffer} {line}".strip() if buffer else line
        if line.lower() == "endmodule" and ";" not in buffer.replace("endmodule", ""):
            statements.append("endmodule")
            buffer = ""
            continue
        while ";" in buffer:
            semicolon = buffer.index(";")
            statement = buffer[: semicolon + 1].strip()
            buffer = buffer[semicolon + 1 :].strip()
            if statement:
                statements.append(statement)
    if buffer.strip():
        statements.append(buffer.strip())
    return statements


def convert_circuit(text: str) -> str:
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    inserted_header = False
    for line in lines:
        stripped = line.lstrip()
        if not inserted_header and stripped and not stripped.startswith("//"):
            out.append(HEADER)
            inserted_header = True
        if MODULE_RE.match(line):
            out.append('(* DONT_TOUCH = "TRUE" *)\n')
            out.append(line)
            continue
        match = GATE_RE.match(line.strip() if line.strip().endswith(";") else "")
        if match:
            kind = match.group(1).lower()
            inst = match.group(2)
            pins = [part.strip() for part in match.group(3).split(",") if part.strip()]
            indent = re.match(r"^\s*", line).group(0)
            wrapper = f"iscas_{kind}{len(pins) - 1}"
            out.append(f"{indent}{wrapper} {inst} ({', '.join(pins)});\n")
            continue
        # Multi-line gates are uncommon in these files; statements are one line.
        out.append(line)
    if not inserted_header:
        out.insert(0, HEADER)
    return "".join(out)


def convert_circuit_from_statements(text: str) -> str:
    """Preserve comments/layout; replace only primitive gate statements."""
    out: list[str] = []
    inserted_header = False
    buffer = ""
    buffer_lines: list[str] = []

    def flush_non_gate() -> None:
        nonlocal buffer, buffer_lines
        out.extend(buffer_lines)
        buffer = ""
        buffer_lines = []

    lines = text.splitlines(keepends=True)
    for line in lines:
        stripped = line.lstrip()
        if not inserted_header and stripped and not stripped.startswith("//"):
            out.append(HEADER)
            inserted_header = True
        if MODULE_RE.match(line) and not buffer:
            out.append('(* DONT_TOUCH = "TRUE" *)\n')
            out.append(line)
            continue

        if not buffer:
            trial = line.strip()
            if GATE_RE.match(trial):
                match = GATE_RE.match(trial)
                kind = match.group(1).lower()
                inst = match.group(2)
                pins = [part.strip() for part in match.group(3).split(",") if part.strip()]
                indent = re.match(r"^\s*", line).group(0)
                wrapper = f"iscas_{kind}{len(pins) - 1}"
                out.append(f"{indent}{wrapper} {inst} ({', '.join(pins)});\n")
                continue
            if re.match(
                r"^\s*(and|or|nand|nor|not|buf|xor|xnor)\s+", line, re.IGNORECASE
            ):
                buffer = line.strip()
                buffer_lines = [line]
                if ";" in buffer:
                    match = GATE_RE.match(buffer)
                    if match:
                        kind = match.group(1).lower()
                        inst = match.group(2)
                        pins = [
                            part.strip()
                            for part in match.group(3).split(",")
                            if part.strip()
                        ]
                        indent = re.match(r"^\s*", buffer_lines[0]).group(0)
                        wrapper = f"iscas_{kind}{len(pins) - 1}"
                        out.append(f"{indent}{wrapper} {inst} ({', '.join(pins)});\n")
                    else:
                        flush_non_gate()
                    buffer = ""
                    buffer_lines = []
                continue
            out.append(line)
            continue

        buffer = f"{buffer} {line.strip()}"
        buffer_lines.append(line)
        if ";" in line:
            match = GATE_RE.match(buffer)
            if match:
                kind = match.group(1).lower()
                inst = match.group(2)
                pins = [part.strip() for part in match.group(3).split(",") if part.strip()]
                indent = re.match(r"^\s*", buffer_lines[0]).group(0)
                wrapper = f"iscas_{kind}{len(pins) - 1}"
                out.append(f"{indent}{wrapper} {inst} ({', '.join(pins)});\n")
            else:
                flush_non_gate()
            buffer = ""
            buffer_lines = []

    out.extend(buffer_lines)
    if not inserted_header:
        out.insert(0, HEADER)
    return "".join(out)


def main() -> None:
    DST.mkdir(exist_ok=True)
    wrappers = needed_wrappers(SRC)
    write_gate_library(DST / "iscas_vivado_gates.v", wrappers)
    print(f"wrote {DST / 'iscas_vivado_gates.v'} ({len(wrappers)} wrappers)")
    for path in sorted(SRC.glob("*.v")):
        converted = convert_circuit_from_statements(path.read_text(encoding="utf-8"))
        dest = DST / path.name
        dest.write_text(converted, encoding="utf-8")
        print(f"{path.name} -> {dest}")


if __name__ == "__main__":
    main()
