# Visualizer Implementation Plan for Cursor

## 1. Objective

Implement a **standalone, interactive gate-level circuit visualizer** for the existing Python ATPG project.

The visualizer is for inspecting the circuit graph produced by the current parser and for debugging:
- gate and signal connectivity;
- primary inputs (PIs) and primary outputs (POs);
- signal fanout and gate input pins;
- stem and branch stuck-at fault sites;
- five-valued signal states used by PODEM (`0`, `1`, `X`, `D`, `D'`);
- PODEM assignments and D-frontier, when supplied to the viewer.

The visualizer must handle small circuits such as `c17`, medium circuits such as `c432`, and be designed to scale toward 1,000–10,000+ gates.

## 2. Non-negotiable scope boundary: do not modify existing modules

**Do not edit, rename, move, reformat, or refactor any existing project files. Do not change any existing module, class, function, parser, circuit data structure, fault-collapsing code, implication code, PODEM code, tests, configuration, or dependencies.**

This is an additive feature only.

1. Before coding, inspect the repository to understand its structure and read-only interfaces.
2. Create new files only, inside a new `viewer/` directory at the repository root.
3. Do not edit `pyproject.toml`, `requirements.txt`, setup files, lockfiles, CI files, or any existing README.
4. Do not add imports from the existing codebase into existing modules.
5. Do not alter the behavior of any existing command or test.
6. Do not run formatters or automated refactoring across the repository.
7. If integration would require changing an existing file, **do not make that change**. Instead, document the manual command or one-line invocation the user can run separately.
8. Do not install packages or modify the Python environment automatically. Use the Python standard library for export/server code. The browser visualization may load Cytoscape.js from a CDN; document that internet access is needed. If the user later requests an offline viewer, make that a separate change confined to `viewer/`.

Before finishing, run `git status --short` and verify that every changed or untracked path belongs to `viewer/`. If any existing file was changed, revert only your own unintended change and report it. Do not overwrite or discard pre-existing user changes.

## 3. Repository inspection requirements

Read the existing code before writing the adapter. Use the circuit structure documented by the project:

### Circuit
- `circuit.name`
- `circuit.signals`: `dict[str, Signal]`
- `circuit.gates`: `list[Gate]`
- `circuit.primary_inputs`: list of `Signal` objects
- `circuit.primary_outputs`: list of `Signal` objects
- `circuit.levels`: levelized gate groups

### Signal
- `signal.name`
- `signal.is_pi`
- `signal.is_po`
- `signal.driver`: driving `Gate` or `None` for a PI
- `signal.fanouts`: list of `(gate, input_index)` pairs
- `signal.level`
- `signal.value`: five-valued logic state, initially `X`

### Gate
- `gate.id`: parse-order integer ID
- `gate.instance_name`
- `gate.type`: `GateType` enum
- `gate.inputs`: ordered list of `Signal` objects
- `gate.output`: output `Signal`
- `gate.level`

The parser's documented gate pin order is output first in Verilog syntax, but in the in-memory object, `gate.inputs` contains the input signals only and `gate.output` is the output signal.

Do not assume undocumented attributes. Inspect the source definitions read-only and adapt only in new viewer files. If an attribute differs from this plan, use the actual existing interface without modifying its owner module.

## 4. New files to create

Create only these files, unless a small additional file is necessary and remains inside `viewer/`:

```text
viewer/
├── visualizer_plan.md       # this specification, if placed in repository
├── export_graph.py          # adapts Circuit objects to JSON
├── viewer.html              # browser UI using Cytoscape.js
├── serve.py                 # optional standard-library local server
└── README.md                # usage and integration instructions
```

If Cursor is writing this plan into the repository, it may treat `visualizer_plan.md` as the plan file itself. Do not create a duplicate.

Do not generate or commit circuit-specific JSON files by default. JSON snapshots should be created under `viewer/output/` at runtime, and that directory should be ignored by the viewer's own documented workflow or otherwise kept out of version control without editing root ignore files. Prefer writing outputs to a user-specified path.

## 5. Data flow

The visualizer must be a read-only consumer of the ATPG project:

```text
Existing parser and ATPG modules (read only)
        |
        | Circuit object passed by the user
        v
viewer/export_graph.py
        |
        | JSON snapshot
        v
viewer/viewer.html
        |
        v
Interactive browser visualization
```

The adapter must not mutate `Circuit`, `Signal`, `Gate`, `Signal.value`, fanouts, levels, or any ATPG state. It must not run fault collapsing or PODEM itself. It only serializes the current state that the caller passes in.

The adapter must not import the parser at module import time. Its main API should accept a `circuit` object, allowing the caller to parse a circuit using their existing entry point and then pass the result into the exporter.

Suggested API (adapt names if needed, but only in new files):

```python
export_graph(
    circuit,
    output_path,
    *,
    fault=None,
    podem_values=None,
    d_frontier=None,
)
```

The optional debug inputs are snapshots only:
- `fault`: a serializable description of the selected target fault;
- `podem_values`: optional mapping of signal names to `0`, `1`, `X`, `D`, or `D'`. If omitted, read `signal.value` without changing it;
- `d_frontier`: optional collection identifying gates in the D-frontier. The adapter must translate these to stable gate IDs using the actual supplied representation; if unclear, support documented IDs and instance names and explain the expected format.

Do not guess the project's fault-object schema. Define a small viewer-specific schema in `viewer/README.md` and accept a dictionary supplied by the caller. At minimum, document:
- stem fault: `{"kind": "stem", "signal": "N11", "stuck_at": 0}`;
- branch fault: `{"kind": "branch", "signal": "N11", "gate": "NAND2_3", "input_index": 1, "stuck_at": 0}`.

A branch fault must highlight the exact signal-to-gate-input connection, not every use of the signal. A stem fault highlights the signal node itself. Keep this viewer schema local to the viewer; do not change ATPG fault classes.

## 6. Graph representation

Use Cytoscape.js via a pinned CDN URL in `viewer.html`. Clearly state in `viewer/README.md` that internet access is required to load the library unless an offline copy is later configured.

Use a **bipartite directed graph**:
- one node per signal, with ID `s:<signal-name>`;
- one node per gate, with ID based on stable `gate.id`, such as `g:<gate-id>`;
- one edge from each input signal to the consuming gate;
- one edge from each gate to its output signal.

The graph must preserve exact connectivity, including multi-input gates and fanout:
- signal-to-gate edges include `input_index`, signal name, gate ID and instance name;
- gate-to-signal edges identify the driven output signal;
- do not collapse multiple connections from the same signal to the same gate if the netlist legitimately connects the signal to multiple pins;
- use stable IDs and ensure they are unique even if instance names overlap;
- keep actual gate `instance_name` visible in the details panel.

Each signal node should expose:
- signal name;
- PI/PO flags;
- level;
- current logic value;
- driver gate identity if present;
- fanout count.

Each gate node should expose:
- numeric gate ID;
- instance name;
- gate type;
- level;
- ordered input names;
- output name;
- D-frontier membership if supplied.

Use the actual `Signal` and `Gate` fields from the inspected code, not a second reimplementation of the circuit.

## 7. Required viewer interactions

Implement a usable first version with the following controls:

1. **Pan and zoom** over the circuit.
2. **Search** for a signal name, gate instance name, or numeric gate ID.
3. **Select an element** and show its properties in a side panel.
4. **Fit circuit** button to frame the current graph.
5. **Show neighborhood** control: for a selected signal or gate, display its direct neighbors or a configurable number of levels upstream/downstream. If full subgraph filtering is too large for the first pass, at least provide a button to focus the selected element and its immediate neighborhood.
6. **Layer visibility controls** for gates, signals and connection labels, if feasible without complicating the first version.
7. **Fault selection/overlay** using the viewer-specific fault schema above.
8. **PODEM value overlay** on signal nodes, displaying `0`, `1`, `X`, `D`, or `D'`.
9. **D-frontier overlay** on matching gate nodes.
10. **Readable status area** showing circuit name and counts of signals, gates, and edges.

Use safe DOM APIs such as `textContent` for displaying file-derived values; do not insert netlist names into `innerHTML`.

## 8. Layout and performance

The viewer must be designed for large graphs; do not assume a single force-directed layout will scale to 10,000+ gates.

Implement in stages:

### Initial layout
- Prefer a levelized layout using `Signal.level` and `Gate.level`, placing lower levels left and higher levels right.
- Use a deterministic layout when practical, so the same netlist renders consistently.
- Keep PIs at level 0 and output signals at their actual signal levels.
- Do not assume all POs share the same level.

### Large-circuit behavior
- Avoid showing every edge label by default; show pin labels on selection or at high zoom.
- Provide a neighborhood/focus view so users do not need to inspect all 10,000 gates simultaneously.
- Avoid recomputing the entire layout for every selection or PODEM value update.
- Keep rendering separate from graph export so JSON snapshots can be inspected independently.
- If full rendering of 10,000+ gates is slow, implement a documented focused-subgraph mode rather than promising smooth rendering for the entire graph.
- Never silently drop gates or connections to improve performance. If a filtered view is active, clearly label it as filtered and provide a way to return to the full circuit.

## 9. PODEM and fault-debugging semantics

This visualizer must be a display layer only. Do not implement or change the ATPG algorithms.

### Logic values
Use the project's documented five-valued logic:
- `0`: good circuit 0, faulty circuit 0;
- `1`: good circuit 1, faulty circuit 1;
- `X`: unknown;
- `D`: good 1, faulty 0;
- `D'`: good 0, faulty 1.

Read values from `signal.value` by default. If a separate `podem_values` snapshot is supplied, display that snapshot without writing values back to the circuit.

### Fault overlays
- Stem fault: highlight the named signal.
- Branch fault: highlight the precise input edge identified by signal, gate/instance, and input index.
- Display fault kind and stuck-at value in the details panel.
- Do not infer fault equivalence or dominance from the viewer data.

### D-frontier
- Highlight gates listed in the supplied D-frontier snapshot.
- Do not calculate the D-frontier inside the viewer.
- If a gate cannot be resolved, report it in a warning/status area rather than silently highlighting another gate.

### Snapshot updates
The first version may load one JSON snapshot per page load. Add a **Reload snapshot** button if practical. Do not add a live server, WebSocket, or polling dependency unless it remains fully inside `viewer/` and does not require changes to existing modules.

## 10. Running the viewer

The caller should be able to invoke the exporter without modifying the existing parser or ATPG modules. Document a manual integration example in `viewer/README.md` using the project's real parser entry point, for example:

```python
from src.parser.iscas_verilog import parse_iscas_verilog
from viewer.export_graph import export_graph

circuit = parse_iscas_verilog("ISCAS85_Circuits/c17.v")
export_graph(circuit, "viewer/output/circuit.json")
```

This is an example only: verify the actual import path and function signature read-only before documenting it as exact. Do not insert this invocation into any existing module or command.

Provide a standard-library local server if necessary for browser `fetch()` to load the JSON. It must bind to `127.0.0.1` by default and serve only the viewer/project files needed. Do not expose the server to the network by default.

Document the run commands and output path. Do not claim the viewer is integrated into PODEM automatically; it is a manually invoked read-only snapshot viewer unless the user explicitly asks for a separate, non-invasive integration mechanism.

## 11. Testing and acceptance criteria

Add tests only under `viewer/` if needed. Do not modify existing tests.

Create a small synthetic test circuit using minimal fake objects inside the viewer tests, or use a real benchmark only if it can be run without changing project files.

Acceptance criteria:
- [ ] Existing project modules are unchanged.
- [ ] Existing tests and commands are not modified.
- [ ] Exporting a parsed `c17` produces 6 gate nodes, 11 signal nodes, and the expected directed connections.
- [ ] `N3` fanout resolves to the two expected gate input pins in the documented `c17` example.
- [ ] PI and PO flags match the circuit object.
- [ ] Gate types, IDs, levels, instance names, ordered inputs, and outputs match the parsed objects.
- [ ] Signal values are read-only and do not change during export.
- [ ] Stem fault highlights only its signal node.
- [ ] Branch fault highlights only the specified input edge.
- [ ] D-frontier highlighting uses supplied data and does not run ATPG logic.
- [ ] Search supports signal names, instance names, and numeric gate IDs.
- [ ] Full graph and focused-neighborhood views are clearly distinguished.
- [ ] Missing or unresolved debug identifiers generate a useful warning.
- [ ] The viewer does not silently omit graph elements.
- [ ] Runtime JSON output is not committed by default.
- [ ] `git status --short` confirms all implementation changes are confined to `viewer/`.

## 12. Implementation sequence

Follow this sequence; keep each step inside `viewer/`:

1. Inspect the existing `Circuit`, `Signal`, `Gate`, `GateType`, and parser definitions without editing them.
2. Implement the pure read-only graph exporter.
3. Add exporter tests using synthetic objects under `viewer/`.
4. Implement the browser graph, details panel, search, pan/zoom, and fit.
5. Add level-based positioning and focused-neighborhood mode.
6. Add stem/branch fault overlays.
7. Add five-valued logic and D-frontier overlays.
8. Add usage documentation and local serving instructions.
9. Run only viewer-specific tests plus relevant existing tests as read-only validation.
10. Check `git status --short`; verify no path outside `viewer/` has been modified.

If a requirement conflicts with the existing project structure, preserve the existing project and adapt the new viewer files. Do not make a change outside `viewer/` without asking the user first.

## 13. Final report required from Cursor

At completion, report:
- new files created under `viewer/`;
- exact manual command to generate a snapshot;
- exact command/URL to open the viewer;
- tests run and results;
- any unsupported feature or performance limitation;
- confirmation that no existing modules or project configuration files were changed.
