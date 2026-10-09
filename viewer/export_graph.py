"""Serialize a Circuit object to a viewer JSON snapshot.

This module is a read-only adapter. It does not import the parser at import
time, and it does not mutate the circuit, its signals, or its gates.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


_LOGIC_TEXT = {
    "0": "0",
    "ZERO": "0",
    "1": "1",
    "ONE": "1",
    "X": "X",
    "D": "D",
    "D'": "D'",
    "DBAR": "D'",
    "D-BAR": "D'",
}


def export_graph(
    circuit: Any,
    output_path: str | Path,
    *,
    fault: dict[str, Any] | None = None,
    podem_values: dict[str, Any] | None = None,
    d_frontier: Any = None,
) -> dict[str, Any]:
    """Write a JSON snapshot of ``circuit`` and return the same structure.

    ``fault``, ``podem_values``, and ``d_frontier`` are display snapshots.
    They are not written back onto the circuit.
    """
    graph = build_graph(
        circuit,
        fault=fault,
        podem_values=podem_values,
        d_frontier=d_frontier,
    )
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")
    return graph


def build_graph(
    circuit: Any,
    *,
    fault: dict[str, Any] | None = None,
    podem_values: dict[str, Any] | None = None,
    d_frontier: Any = None,
) -> dict[str, Any]:
    """Return the viewer graph for ``circuit`` without touching its state."""
    warnings: list[str] = []
    values = _value_snapshot(circuit, podem_values, warnings)
    frontier_ids, frontier_report = _resolve_d_frontier(circuit, d_frontier, warnings)
    fault_copy, fault_targets = _resolve_fault(circuit, fault, warnings)

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for signal in circuit.signals.values():
        driver = signal.driver
        node_id = f"s:{signal.name}"
        _claim_id(seen_ids, node_id)
        nodes.append(
            {
                "data": {
                    "id": node_id,
                    "kind": "signal",
                    "name": signal.name,
                    "is_pi": bool(signal.is_pi),
                    "is_po": bool(signal.is_po),
                    "level": signal.level,
                    "value": values[signal.name],
                    "driver_gate_id": None if driver is None else driver.id,
                    "driver_instance": None if driver is None else driver.instance_name,
                    "fanout_count": len(signal.fanouts),
                    "fault_site": node_id in fault_targets["signals"],
                }
            }
        )

    for gate in circuit.gates:
        node_id = f"g:{gate.id}"
        _claim_id(seen_ids, node_id)
        nodes.append(
            {
                "data": {
                    "id": node_id,
                    "kind": "gate",
                    "gate_id": gate.id,
                    "instance_name": gate.instance_name,
                    "gate_type": _gate_type_name(gate),
                    "level": gate.level,
                    "inputs": [item.name for item in gate.inputs],
                    "output": gate.output.name,
                    "d_frontier": gate.id in frontier_ids,
                    "fault_site": False,
                }
            }
        )
        for index, source in enumerate(gate.inputs):
            edge_id = f"in:{gate.id}:{index}:{source.name}"
            _claim_id(seen_ids, edge_id)
            edges.append(
                {
                    "data": {
                        "id": edge_id,
                        "source": f"s:{source.name}",
                        "target": node_id,
                        "kind": "input",
                        "input_index": index,
                        "signal": source.name,
                        "gate_id": gate.id,
                        "instance_name": gate.instance_name,
                        "pin_label": f"[{index}]",
                        "fault_site": edge_id in fault_targets["edges"],
                    }
                }
            )
        output = gate.output
        edge_id = f"out:{gate.id}:{output.name}"
        _claim_id(seen_ids, edge_id)
        edges.append(
            {
                "data": {
                    "id": edge_id,
                    "source": node_id,
                    "target": f"s:{output.name}",
                    "kind": "output",
                    "input_index": None,
                    "signal": output.name,
                    "gate_id": gate.id,
                    "instance_name": gate.instance_name,
                    "pin_label": "",
                    "fault_site": False,
                }
            }
        )

    signal_count = sum(1 for node in nodes if node["data"]["kind"] == "signal")
    gate_count = sum(1 for node in nodes if node["data"]["kind"] == "gate")
    return {
        "schema_version": 1,
        "name": circuit.name,
        "counts": {
            "signals": signal_count,
            "gates": gate_count,
            "edges": len(edges),
        },
        "primary_inputs": [signal.name for signal in circuit.primary_inputs],
        "primary_outputs": [signal.name for signal in circuit.primary_outputs],
        "warnings": warnings,
        "fault": fault_copy,
        "d_frontier": frontier_report,
        "elements": {"nodes": nodes, "edges": edges},
    }


def _claim_id(seen: set[str], element_id: str) -> None:
    if element_id in seen:
        raise ValueError(f"duplicate graph element id: {element_id}")
    seen.add(element_id)


def _gate_type_name(gate: Any) -> str:
    gate_type = gate.type
    name = getattr(gate_type, "name", None)
    if isinstance(name, str) and name:
        return name
    return str(gate_type)


def _logic_text(value: Any) -> str | None:
    if isinstance(value, bool):
        return None
    display = getattr(value, "display", None)
    if isinstance(display, str):
        raw = display.strip()
    elif isinstance(value, int) and value in (0, 1):
        return str(value)
    else:
        raw = str(value).strip()
    if raw in _LOGIC_TEXT:
        return _LOGIC_TEXT[raw]
    return _LOGIC_TEXT.get(raw.upper())


def _value_snapshot(
    circuit: Any,
    podem_values: dict[str, Any] | None,
    warnings: list[str],
) -> dict[str, str]:
    overrides = dict(podem_values) if podem_values else {}
    known = set(circuit.signals)
    for name in overrides:
        if name not in known:
            warnings.append(f"PODEM value for unknown signal {name!r} was ignored")
    values: dict[str, str] = {}
    for name, signal in circuit.signals.items():
        if name in overrides:
            text = _logic_text(overrides[name])
            if text is None:
                warnings.append(
                    f"PODEM value for {name!r} is not five-valued; showing signal.value"
                )
                text = _logic_text(signal.value) or "X"
            values[name] = text
        else:
            text = _logic_text(signal.value)
            if text is None:
                warnings.append(
                    f"signal {name!r} value {signal.value!r} is not five-valued; showing X"
                )
                text = "X"
            values[name] = text
    return values


def _resolve_d_frontier(
    circuit: Any,
    d_frontier: Any,
    warnings: list[str],
) -> tuple[set[int], dict[str, list[Any]]]:
    if d_frontier is None:
        entries: list[Any] = []
    elif isinstance(d_frontier, (str, int, dict)):
        entries = [d_frontier]
    else:
        try:
            entries = list(d_frontier)
        except TypeError:
            warnings.append("D-frontier snapshot is not a list; nothing was highlighted")
            entries = []

    resolved: list[dict[str, Any]] = []
    unresolved: list[Any] = []
    ids: set[int] = set()
    for entry in entries:
        spec = _frontier_spec(entry)
        if spec is None:
            unresolved.append(entry)
            warnings.append(f"unresolved D-frontier entry: {entry!r}")
            continue
        matches = _match_gates(circuit.gates, spec)
        if len(matches) == 1:
            gate = matches[0]
            ids.add(gate.id)
            resolved.append({"gate_id": gate.id, "instance_name": gate.instance_name})
        elif len(matches) > 1:
            unresolved.append(entry)
            warnings.append(
                f"instance name {spec!r} matches multiple gates; "
                "D-frontier entry not applied"
            )
        else:
            unresolved.append(entry)
            warnings.append(f"unresolved D-frontier entry: {entry!r}")
    resolved.sort(key=lambda item: item["gate_id"])
    return ids, {"resolved": resolved, "unresolved": unresolved}


def _frontier_spec(entry: Any) -> Any:
    if isinstance(entry, dict):
        for key in ("gate_id", "id", "instance_name", "gate"):
            if key in entry:
                return entry[key]
        return None
    return entry


def _resolve_fault(
    circuit: Any,
    fault: dict[str, Any] | None,
    warnings: list[str],
) -> tuple[dict[str, Any] | None, dict[str, set[str]]]:
    targets: dict[str, set[str]] = {"signals": set(), "edges": set()}
    if fault is None:
        return None, targets
    if not isinstance(fault, dict):
        warnings.append("fault must be a dictionary; overlay skipped")
        return None, targets

    stored = dict(fault)
    kind = stored.get("kind")
    signal_name = stored.get("signal")
    if kind not in {"stem", "branch"}:
        warnings.append(f"unsupported fault kind: {kind!r}")
        return stored, targets
    signal = circuit.signals.get(signal_name)
    if signal is None:
        warnings.append(f"{kind} fault signal {signal_name!r} was not found")
        return stored, targets
    if kind == "stem":
        targets["signals"].add(f"s:{signal.name}")
        return stored, targets

    spec = stored.get("gate")
    if "input_index" not in stored:
        warnings.append("branch fault is missing input_index; overlay skipped")
        return stored, targets
    try:
        input_index = stored["input_index"]
        if isinstance(input_index, bool) or not isinstance(input_index, int):
            raise TypeError
    except TypeError:
        warnings.append(
            f"branch fault input_index {stored.get('input_index')!r} is not an integer"
        )
        return stored, targets

    matches = _match_gates(circuit.gates, spec)
    if len(matches) != 1:
        if len(matches) > 1:
            warnings.append(
                f"instance name {spec!r} matches multiple gates; "
                "branch fault overlay skipped"
            )
        else:
            warnings.append(
                "branch fault edge was not found: "
                f"signal {signal_name!r}, gate {spec!r}, input_index {input_index}"
            )
        return stored, targets

    gate = matches[0]
    if input_index < 0 or input_index >= len(gate.inputs):
        warnings.append(
            "branch fault edge was not found: "
            f"signal {signal_name!r}, gate {spec!r}, input_index {input_index}"
        )
        return stored, targets
    if gate.inputs[input_index].name != signal.name:
        warnings.append(
            "branch fault edge was not found: "
            f"signal {signal_name!r}, gate {spec!r}, input_index {input_index}"
        )
        return stored, targets
    targets["edges"].add(f"in:{gate.id}:{input_index}:{signal.name}")
    return stored, targets


def _match_gates(gates: list[Any], spec: Any) -> list[Any]:
    if spec is None or isinstance(spec, bool):
        return []
    if isinstance(spec, int):
        return [gate for gate in gates if gate.id == spec]
    text = str(spec)
    by_name = [gate for gate in gates if gate.instance_name == text]
    if by_name:
        return by_name
    if text.isdigit():
        gate_id = int(text)
        return [gate for gate in gates if gate.id == gate_id]
    return []


def main(argv: list[str] | None = None) -> int:
    """Export a netlist. The parser is imported here, not at module import."""
    parser = argparse.ArgumentParser(
        description="Export a circuit JSON snapshot for viewer/viewer.html"
    )
    parser.add_argument("netlist", help="Path to an ISCAS-style Verilog netlist")
    parser.add_argument("-o", "--output", required=True, help="JSON output path")
    parser.add_argument("--fault", help="Fault overlay as a JSON object")
    parser.add_argument(
        "--podem",
        help="PODEM value snapshot as a JSON object of signal name to 0, 1, X, D, or D'",
    )
    parser.add_argument(
        "--d-frontier",
        help="Comma-separated gate ids or instance names",
    )
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    from parser.iscas_verilog import parse_iscas_verilog

    fault = json.loads(args.fault) if args.fault else None
    podem_values = json.loads(args.podem) if args.podem else None
    frontier = (
        [part.strip() for part in args.d_frontier.split(",") if part.strip()]
        if args.d_frontier
        else None
    )
    graph = export_graph(
        parse_iscas_verilog(args.netlist),
        args.output,
        fault=fault,
        podem_values=podem_values,
        d_frontier=frontier,
    )
    counts = graph["counts"]
    print(
        f"wrote {args.output} "
        f"({counts['signals']} signals, {counts['gates']} gates, {counts['edges']} edges)"
    )
    for warning in graph["warnings"]:
        print(f"warning: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
