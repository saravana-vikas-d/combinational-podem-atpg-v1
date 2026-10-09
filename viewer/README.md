# Circuit viewer

Read-only browser view of a parsed combinational netlist. The exporter reads a `Circuit` object and writes JSON. It does not run fault collapsing or PODEM, and it does not modify the circuit.

Internet access is required when opening `viewer.html`. The page loads Cytoscape.js 3.28.1 from the cdnjs CDN:

`https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.28.1/cytoscape.min.js`

## Generate a snapshot

From the repository root:

```text
python -m viewer.export_graph ISCAS85_Circuits/c17.v -o viewer/output/circuit.json
```

The same call from Python, using the project's real parser entry point (`src` is on `PYTHONPATH`):

```python
import sys
sys.path.insert(0, "src")
from parser.iscas_verilog import parse_iscas_verilog
from viewer.export_graph import export_graph

circuit = parse_iscas_verilog("ISCAS85_Circuits/c17.v")
export_graph(circuit, "viewer/output/circuit.json")
```

`viewer/output/` is gitignored by `viewer/.gitignore`. Pass another path if you want the file elsewhere. The local server only serves files inside `viewer/`, so a snapshot opened by URL needs to live under `viewer/`. A file outside that directory can still be opened with **Open JSON** in the page.

Optional snapshot arguments:

```text
python -m viewer.export_graph ISCAS85_Circuits/c17.v -o viewer/output/circuit.json --fault "{\"kind\":\"stem\",\"signal\":\"N3\",\"stuck_at\":0}" --d-frontier NAND2_5
```

```python
export_graph(
    circuit,
    "viewer/output/circuit.json",
    fault={"kind": "branch", "signal": "N3", "gate": "NAND2_1", "input_index": 1, "stuck_at": 0},
    podem_values={"N3": "D", "N22": "D'"},
    d_frontier=["NAND2_5", 0, {"gate_id": 4}],
)
```

`podem_values` is displayed instead of `signal.value` for the names it contains. The circuit object is left unchanged. If the argument is omitted, each signal shows its current `signal.value` (`0`, `1`, `X`, `D`, `D'`).

## Open the viewer

From the repository root:

```text
python -m viewer.serve
```

Then open:

`http://127.0.0.1:8765/viewer.html?snapshot=output/circuit.json`

The server binds to `127.0.0.1` only and serves the `viewer/` directory. Stop it with Ctrl+C. Use `--port` to change the port. `--snapshot` only changes the URL that the command prints.

**Reload snapshot** fetches that URL again. **Open JSON** loads a file from disk and does not replace the circuit in memory.

## What the page shows

The graph is bipartite: one node per signal (`s:<name>`) and one node per gate (`g:<gate id>`). Each gate input pin is its own edge, including two pins driven by the same net. Gate-to-output edges point at the driven signal.

- Pan and zoom are the normal Cytoscape gestures. **Fit view** frames whatever is currently visible.
- Search accepts a signal name, a gate instance name, or a numeric gate ID.
- The side panel lists the selected signal, gate, or pin.
- **Show neighborhood** keeps the selection plus the chosen number of levels upstream and downstream. The status line says the view is filtered and how many nodes remain visible. **Show full circuit** restores every element. Filtering hides elements; it does not delete them.
- Gates, signals, and pin labels can be toggled. Pin labels also appear above zoom 1.4 and on a selected edge. Labels are off by default.
- A stem fault highlights that signal node. A branch fault highlights one input edge. The D-frontier highlight is taken from the snapshot; the page does not compute it.
- Layout is levelized from `Signal.level` and `Gate.level`, with lower levels on the left. It is computed once per snapshot load.

## Fault and D-frontier schema

These dictionaries are viewer input. They are not the ATPG fault classes.

Stem fault, highlighting signal `N11` only:

```json
{"kind": "stem", "signal": "N11", "stuck_at": 0}
```

Branch fault, highlighting the single pin where `N11` drives input 1 of instance `NAND2_3`:

```json
{"kind": "branch", "signal": "N11", "gate": "NAND2_3", "input_index": 1, "stuck_at": 0}
```

`gate` may be an instance name or a numeric gate ID. `input_index` is the position in `gate.inputs`.

`d_frontier` is a list. Each entry may be a gate ID, an instance name, or an object with `gate_id`, `id`, `instance_name`, or `gate`. An entry that matches nothing, or an instance name that matches more than one gate, is listed in `warnings` and is not highlighted.

## Large netlists

The exporter writes every signal, gate, and pin connection. The browser uses one deterministic level layout and does not run a force-directed layout. A full drawing of several thousand gates can be slow or tall. Use neighborhood view for inspection. Value and overlay toggles do not recompute positions.

This viewer is not attached to the PODEM loop. Take a snapshot when you want to look at a state.

## Tests

```text
python -m viewer.tests.test_export_graph
```

If pytest is installed, this also works. The project pytest config collects `tests/` by default, so pass the viewer path explicitly:

```text
python -m pytest viewer/tests -q
```
