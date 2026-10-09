"""Tests for the read-only circuit graph exporter."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from circuit.circuit import Circuit, Gate, GateType, Signal
from logic5 import Logic5
from viewer.export_graph import build_graph, export_graph


def test_exporter_does_not_import_parser_at_module_level():
    source = Path(ROOT / "viewer" / "export_graph.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("parser")
        elif isinstance(node, ast.Import):
            assert not any(alias.name.startswith("parser") for alias in node.names)


def _circuit(name, signals, gates, primary_inputs, primary_outputs):
    return Circuit(
        name=name,
        signals=signals,
        gates=gates,
        primary_inputs=primary_inputs,
        primary_outputs=primary_outputs,
    )


def test_duplicate_pins_are_preserved_and_export_is_read_only():
    source = Signal(name="A", is_pi=True, level=0, value=Logic5.D)
    output = Signal(name="Y", is_po=True, level=1, value=Logic5.X)
    gate = Gate(
        id=0,
        instance_name="AND2_0",
        type=GateType.AND,
        inputs=[source, source],
        output=output,
        level=1,
    )
    source.fanouts = [(gate, 0), (gate, 1)]
    output.driver = gate
    circuit = _circuit("dup", {"A": source, "Y": output}, [gate], [source], [output])
    fanouts_before = list(source.fanouts)

    graph = build_graph(circuit, podem_values={"A": "0", "missing": "1"})

    assert source.value is Logic5.D
    assert source.fanouts == fanouts_before
    assert output.value is Logic5.X
    input_edges = [
        edge["data"]
        for edge in graph["elements"]["edges"]
        if edge["data"]["kind"] == "input"
    ]
    assert [edge["input_index"] for edge in input_edges] == [0, 1]
    assert {edge["id"] for edge in input_edges} == {
        "in:0:0:A",
        "in:0:1:A",
    }
    values = {
        node["data"]["name"]: node["data"]["value"]
        for node in graph["elements"]["nodes"]
        if node["data"]["kind"] == "signal"
    }
    assert values == {"A": "0", "Y": "X"}
    assert any("missing" in warning for warning in graph["warnings"])
    gate_node = next(
        node["data"]
        for node in graph["elements"]["nodes"]
        if node["data"]["kind"] == "gate"
    )
    assert gate_node["gate_type"] == "AND"
    assert gate_node["inputs"] == ["A", "A"]
    assert gate_node["output"] == "Y"
    assert gate_node["instance_name"] == "AND2_0"
    assert gate_node["gate_id"] == 0


def test_stem_branch_and_d_frontier_overlays():
    stem = Signal(name="N3", is_pi=True, level=0)
    other = Signal(name="N1", is_pi=True, level=0)
    n10 = Signal(name="N10", level=1)
    first = Gate(0, "NAND2_1", GateType.NAND, [other, stem], n10, level=1)
    second = Gate(1, "NAND2_1", GateType.NAND, [stem], n10, level=1)
    stem.fanouts = [(first, 1), (second, 0)]
    other.fanouts = [(first, 0)]
    n10.driver = first
    circuit = _circuit(
        "fan",
        {"N3": stem, "N1": other, "N10": n10},
        [first, second],
        [stem, other],
        [],
    )

    stem_graph = build_graph(
        circuit, fault={"kind": "stem", "signal": "N3", "stuck_at": 0}
    )
    fault_nodes = [
        node["data"]["id"]
        for node in stem_graph["elements"]["nodes"]
        if node["data"]["fault_site"]
    ]
    fault_edges = [
        edge["data"]["id"]
        for edge in stem_graph["elements"]["edges"]
        if edge["data"]["fault_site"]
    ]
    assert fault_nodes == ["s:N3"]
    assert fault_edges == []

    missing = build_graph(
        circuit,
        fault={
            "kind": "branch",
            "signal": "N3",
            "gate": "NAND2_1",
            "input_index": 1,
            "stuck_at": 1,
        },
    )
    assert not any(
        edge["data"]["fault_site"] for edge in missing["elements"]["edges"]
    )
    assert any("multiple gates" in warning for warning in missing["warnings"])

    unique = Gate(2, "NAND2_2", GateType.NAND, [stem], n10, level=1)
    circuit.gates.append(unique)
    stem.fanouts.append((unique, 0))
    branch = build_graph(
        circuit,
        fault={
            "kind": "branch",
            "signal": "N3",
            "gate": "NAND2_2",
            "input_index": 0,
            "stuck_at": 0,
        },
        d_frontier=["NAND2_2", 99, {"gate_id": 0}],
    )
    marked = [
        edge["data"]
        for edge in branch["elements"]["edges"]
        if edge["data"]["fault_site"]
    ]
    assert len(marked) == 1
    assert marked[0]["signal"] == "N3"
    assert marked[0]["instance_name"] == "NAND2_2"
    assert marked[0]["input_index"] == 0
    frontier = {
        node["data"]["gate_id"]: node["data"]["d_frontier"]
        for node in branch["elements"]["nodes"]
        if node["data"]["kind"] == "gate"
    }
    assert frontier[0] is True
    assert frontier[1] is False
    assert frontier[2] is True
    assert any("unresolved D-frontier entry" in warning for warning in branch["warnings"])
    assert stem.value is Logic5.X


def test_c17_export_matches_parsed_circuit(tmp_path):
    from parser.iscas_verilog import parse_iscas_verilog

    circuit = parse_iscas_verilog(ROOT / "ISCAS85_Circuits" / "c17.v")
    before = {
        name: (signal.value, list(signal.fanouts), signal.level, signal.is_pi, signal.is_po)
        for name, signal in circuit.signals.items()
    }
    output = tmp_path / "c17.json"
    graph = export_graph(
        circuit,
        output,
        fault={
            "kind": "branch",
            "signal": "N3",
            "gate": "NAND2_1",
            "input_index": 1,
            "stuck_at": 0,
        },
        d_frontier=["NAND2_5"],
    )

    after = {
        name: (signal.value, list(signal.fanouts), signal.level, signal.is_pi, signal.is_po)
        for name, signal in circuit.signals.items()
    }
    assert before == after
    assert graph["name"] == "c17"
    assert graph["counts"] == {"signals": 11, "gates": 6, "edges": 18}
    nodes = [node["data"] for node in graph["elements"]["nodes"]]
    edges = [edge["data"] for edge in graph["elements"]["edges"]]
    assert len({node["id"] for node in nodes}) == 17
    assert len({edge["id"] for edge in edges}) == 18

    by_signal = {node["name"]: node for node in nodes if node["kind"] == "signal"}
    assert by_signal["N3"]["is_pi"] is True
    assert by_signal["N3"]["is_po"] is False
    assert by_signal["N3"]["fanout_count"] == 2
    assert by_signal["N3"]["value"] == "X"
    assert by_signal["N22"]["is_po"] is True
    assert by_signal["N22"]["driver_instance"] == "NAND2_5"
    assert [name for name, node in by_signal.items() if node["is_pi"]] == [
        "N1",
        "N2",
        "N3",
        "N6",
        "N7",
    ]

    n3_edges = [
        edge
        for edge in edges
        if edge["kind"] == "input" and edge["signal"] == "N3"
    ]
    assert {(edge["instance_name"], edge["input_index"]) for edge in n3_edges} == {
        ("NAND2_1", 1),
        ("NAND2_2", 0),
    }
    fault_edges = [edge for edge in edges if edge["fault_site"]]
    assert len(fault_edges) == 1
    assert fault_edges[0]["instance_name"] == "NAND2_1"
    assert fault_edges[0]["input_index"] == 1
    assert not any(node["fault_site"] for node in nodes if node["kind"] == "signal")

    gates = {node["instance_name"]: node for node in nodes if node["kind"] == "gate"}
    assert gates["NAND2_1"]["gate_id"] == 0
    assert gates["NAND2_1"]["gate_type"] == "NAND"
    assert gates["NAND2_1"]["inputs"] == ["N1", "N3"]
    assert gates["NAND2_1"]["output"] == "N10"
    assert gates["NAND2_1"]["level"] == 1
    assert gates["NAND2_5"]["d_frontier"] is True
    assert gates["NAND2_1"]["d_frontier"] is False
    assert output.is_file()


if __name__ == "__main__":
    import tempfile

    test_exporter_does_not_import_parser_at_module_level()
    test_duplicate_pins_are_preserved_and_export_is_read_only()
    test_stem_branch_and_d_frontier_overlays()
    with tempfile.TemporaryDirectory() as directory:
        test_c17_export_matches_parsed_circuit(Path(directory))
    print("viewer tests passed")
