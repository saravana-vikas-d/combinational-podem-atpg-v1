# Circuit structure after parsing

This document explains the in-memory circuit that `parse_iscas_verilog()` builds from an ISCAS-style structural Verilog netlist. All later ATPG work (levelization is already done by the parser, then fault collapsing, implication, PODEM) reads this same object graph.

Entry point: `src/parser/iscas_verilog.py`  
Types: `src/circuit/circuit.py`  
Logic values: `src/logic5.py`

---

## What the parser does

`parse_iscas_verilog(path)` reads a `.v` file and returns one `Circuit`. It does three things in order:

1. **Build** `Signal` and `Gate` objects from `module` / `input` / `output` / `wire` / primitive gate statements.
2. **Validate** connectivity (every internal net and PO is driven, PIs are never driven, fanout lists match gate inputs).
3. **Levelize** the combinational graph (primary inputs at level 0, each gate at `max(input levels) + 1`).

Unsupported Verilog (`assign`, behavioral code, multiple modules) is rejected with `ParseError`. Combinational loops raise `CycleError`.

```text
ISCAS85_Circuits/c17.v
        |
        v
 parse_iscas_verilog()
        |
        +-- Circuit
              |-- name
              |-- signals: dict[str, Signal]
              |-- gates: list[Gate]
              |-- primary_inputs: list[Signal]
              |-- primary_outputs: list[Signal]
              |-- levels: list[list[Gate]]
```

---

## The three objects

### `Circuit`

The whole netlist.

| Field | Meaning |
| --- | --- |
| `name` | Module name (`c17`, `c432`, …). |
| `signals` | Every net, keyed by Verilog identifier. One object per name. |
| `gates` | Gate instances in parse order. `gate.id` is `0 .. n-1`. |
| `primary_inputs` | PI signals in `input` declaration order (this is also PODEM pattern bit order). |
| `primary_outputs` | PO signals in `output` declaration order. |
| `levels` | Gates grouped by gate level. `levels[0]` is all gates at level 1. |

`signals` holds the same objects that appear in `primary_inputs`, `primary_outputs`, and on gate pins. There is never a second copy of net `N3`.

### `Signal`

One net: a primary input, a primary output, or an internal wire. PODEM treats a signal as a **fault site** and as a **connectivity node**.

| Field | Meaning |
| --- | --- |
| `name` | Verilog net name (`N3`, `N11`, …). |
| `is_pi` | True if declared `input`. |
| `is_po` | True if declared `output`. |
| `driver` | The unique `Gate` whose output is this net, or `None` for a PI. |
| `fanouts` | List of `(gate, input_index)` where this net is used. |
| `level` | Topological level. PIs are `0`. After parse, never `-1`. |
| `value` | Five-valued logic. After parse this is `X` until simulation or PODEM writes it. |

A signal can be both a wire and a PO (`is_po=True` and `driver` set). It cannot be a PI and a PO. A PI never has a `driver`.

### `Gate`

One Verilog primitive instance, always one output.

| Field | Meaning |
| --- | --- |
| `id` | Parse-order index, starting at 0. |
| `instance_name` | Instance name from the netlist (`NAND2_1`). |
| `type` | `GateType`: AND, OR, NAND, NOR, NOT, BUF, XOR, XNOR. |
| `inputs` | Input pins in Verilog argument order after the output. |
| `output` | The driven `Signal`. |
| `level` | `max(input.level) + 1`. |

Verilog pin order is `(output, in0, in1, …)`. Example:

```verilog
nand NAND2_1 (N10, N1, N3);
```

becomes:

- `instance_name = "NAND2_1"`
- `type = NAND`
- `output` is signal `N10`
- `inputs[0]` is `N1`, `inputs[1]` is `N3`

`NOT` and `BUF` must have exactly two pins `(out, in)`. Other primitives need at least three pins `(out, in1, in2, …)`.

---

## How Verilog declarations become objects

Take this fragment of `c17.v`:

```verilog
module c17 (N1,N2,N3,N6,N7,N22,N23);
input N1,N2,N3,N6,N7;
output N22,N23;
wire N10,N11,N16,N19;
```

| Verilog | Parser result |
| --- | --- |
| `module c17 (...)` | `Circuit(name="c17")`. Port list must match the later `input`/`output` names exactly. |
| `input N1, ...` | Create or fetch each `Signal`, set `is_pi=True`, append to `primary_inputs`. |
| `output N22, N23` | Set `is_po=True`, append to `primary_outputs`. |
| `wire N10, ...` | Internal signals with `is_pi=False`, `is_po=False`. |

Then each gate statement wires `driver` and `fanouts`. After `nand NAND2_1 (N10, N1, N3)`:

- `N10.driver` is `NAND2_1`
- `N1.fanouts` contains `(NAND2_1, 0)`
- `N3.fanouts` contains `(NAND2_1, 1)`

`input_index` in a fanout is the pin index on **that gate**, not a global number. The same net can appear at different indices on different gates.

---

## Connectivity: driver vs fanout

Think of a signal as a wire with one source and zero or more sinks.

```text
  driver (one or none)          this signal            fanouts (zero or more)
  --------------------          -----------            ----------------------
  NAND2_2  --drives-->          N11          --feeds--> NAND2_3 pin 1
                                                 \----> NAND2_4 pin 0
```

Rules the validator enforces:

- A **PI** has `driver is None`. Nothing may drive it.
- An **internal wire** and a **PO** must have exactly one `driver`.
- For every `g.inputs[i] == s`, the pair `(g, i)` must be in `s.fanouts`.
- `g.output.driver` must be `g`.

**Fanout of 1 (stem only).** `N10` in c17 drives only `NAND2_5` pin 0. Stem stuck-at faults live on `N10`; there is no extra branch site.

**Fanout of 2+ (stem + branches).** `N3` and `N11` in c17 each feed two gates. Fault collapsing treats the stem and each branch pin as distinct sites (`N3_sa1` vs `N3__NAND2_1_1_sa1`).

---

## Levels

After parse, every signal and gate has a level.

- Primary inputs: **level 0**
- Gate and its output net: **max(input levels) + 1**
- `circuit.levels[k]` is the list of gates whose `gate.level == k + 1`

Implication in PODEM walks gates in this order so a gate is evaluated only after its inputs are known.

### Example: levels on c17

```text
L0  PIs: N1 N2 N3 N6 N7

L1  NAND2_1  (N1, N3) -> N10
    NAND2_2  (N3, N6) -> N11

L2  NAND2_3  (N2, N11) -> N16
    NAND2_4  (N11, N7) -> N19

L3  NAND2_5  (N10, N16) -> N22   (PO)
    NAND2_6  (N16, N19) -> N23   (PO)
```

`circuit.levels` has three groups. Max gate level is 3. POs `N22` and `N23` sit at level 3.

c432 uses the same rule: 36 PIs at level 0, 160 gates, **17 gate levels**. Deepest POs (`N430`, `N431`, `N432`) are level 17.

---

## Logic values (`Logic5`)

Each `Signal.value` is five-valued ATPG logic, not two-valued Verilog simulation:

| Display | Meaning |
| --- | --- |
| `0` | Good = 0, faulty = 0 |
| `1` | Good = 1, faulty = 1 |
| `X` | Unknown |
| `D` | Good = 1, faulty = 0 (fault effect) |
| `D'` | Good = 0, faulty = 1 (fault effect) |

Right after parsing, every signal is `X`. Values change only when implication or PODEM assigns them. A circuit dump of a freshly parsed netlist therefore always shows `value=X`.

---

## Worked example: full c17

Source: `ISCAS85_Circuits/c17.v`

```verilog
nand NAND2_1 (N10, N1, N3);
nand NAND2_2 (N11, N3, N6);
nand NAND2_3 (N16, N2, N11);
nand NAND2_4 (N19, N11, N7);
nand NAND2_5 (N22, N10, N16);
nand NAND2_6 (N23, N16, N19);
```

### Counts

| | |
| --- | ---: |
| Primary inputs | 5 (`N1`, `N2`, `N3`, `N6`, `N7`) |
| Primary outputs | 2 (`N22`, `N23`) |
| Internal wires | 4 (`N10`, `N11`, `N16`, `N19`) |
| Total signals | 11 |
| Gates | 6, all NAND |
| Level groups | 3 |

### Schematic in terms of parser objects

```text
 N1 ─────────────── NAND2_1 ── N10 ── NAND2_5 ── N22 (PO)
 N3 ──┬────────────┘                 /
      └──────────── NAND2_2 ── N11 ─┼── NAND2_3 ── N16 ─┬── NAND2_5
 N6 ───────────────┘                |                   └── NAND2_6 ── N23 (PO)
 N2 ────────────────────────────────┘
 N7 ──────────────────────────────── NAND2_4 ── N19 ────┘
```

### One PI in detail: `N3`

```text
name      = N3
is_pi     = True
is_po     = False
driver    = None          # PI, not driven
level     = 0
value     = X             # until ATPG
fanouts   = (NAND2_1, 1), (NAND2_2, 0)
```

So `N3` is pin 1 of `NAND2_1` and pin 0 of `NAND2_2`. That is why a circuit dump prints:

```text
PI  N3  L0  value=X  driver=-
    fanouts (2):
      NAND2_1[1]  nand -> N10
      NAND2_2[0]  nand -> N11
```

`NAND2_1[1]` means “this net is input index 1 of that gate”. `nand -> N10` is the gate type and the net that gate drives.

### One internal wire: `N11`

```text
name      = N11
is_pi     = False
is_po     = False
driver    = NAND2_2
level     = 1
fanouts   = (NAND2_3, 1), (NAND2_4, 0)
```

`N11` is a reconvergent fanout stem: it feeds both `NAND2_3` and `NAND2_4`, and those paths meet again at `NAND2_6`.

### One PO: `N22`

```text
name      = N22
is_pi     = False
is_po     = True
driver    = NAND2_5
level     = 3
fanouts   = []            # printed as (none)
```

POs are still `Signal` objects in `circuit.signals`. Detection in PODEM looks at `primary_outputs` for `D` or `D'`.

### One gate: `NAND2_3`

```text
id             = 2
instance_name  = NAND2_3
type           = NAND
inputs         = [N2, N11]
output         = N16
level          = 2
```

`N16.driver` is this same gate. `N2.fanouts` contains `(NAND2_3, 0)`. `N11.fanouts` contains `(NAND2_3, 1)`.

### `circuit.levels` for c17

```text
levels[0]  (L1): NAND2_1, NAND2_2
levels[1]  (L2): NAND2_3, NAND2_4
levels[2]  (L3): NAND2_5, NAND2_6
```

---

## Larger example: c432 (same structure, more nets)

`ISCAS85_Circuits/c432.v` parses to the same types. Only sizes change.

| | |
| --- | ---: |
| Primary inputs | 36 |
| Primary outputs | 7 (`N223`, `N329`, `N370`, `N421`, `N430`, `N431`, `N432`) |
| Internal wires | 153 |
| Total signals | 196 |
| Gates | 160 |
| Gate types | AND=4, NAND=79, NOR=19, NOT=40, XOR=18 |
| Gate levels | 17 |

Wide primitives are still one `Gate` with a longer `inputs` list. Example from the netlist:

```verilog
and AND9_46 (N199, N154, N159, N162, N165, N168, N171, N174, N177, N180);
nand NAND4_138 (N380, N4, N242, N334, N371);
```

- `AND9_46.inputs` has 9 signals; `output` is `N199`.
- `NAND4_138.inputs` has 4 signals. PI `N4` is `inputs[0]`, so `N4.fanouts` includes `(NAND4_138, 0)`.

A PI can fan out to both an inverter and a later wide gate:

```text
PI  N4  L0  value=X  driver=-
    fanouts (3):
      NOT1_2[0]  not -> N119
      NAND2_19[1]  nand -> N154
      NAND4_138[0]  nand -> N380
```

That is the same `Signal` object, with three `(gate, index)` pairs.

POs sit at different depths because their driving cones differ:

| PO | Level | Driver |
| --- | ---: | --- |
| N223 | 4 | NOT1_49 |
| N329 | 8 | NOT1_98 |
| N370 | 12 | NOT1_128 |
| N421 | 16 | NOR2_153 |
| N430, N431, N432 | 17 | NAND4_158, NAND4_159, NAND4_160 |

---

## How this object graph is used later

| Consumer | What it reads |
| --- | --- |
| Fault collapsing | Stem vs branch sites from `fanouts` and gate types |
| Implication / backtrace | `gate.inputs`, `gate.output`, `gate.type`, `signal.value` |
| PODEM | PI order in `primary_inputs` (pattern bits), POs for detection, `levels` for forward imply |
| Circuit dump | `format_circuit()` in `src/circuit/dump.py` |

A formatted dump for any netlist:

```text
python circuit_print.py
```

(or call `print_circuit_from_file("ISCAS85_Circuits/c432.v")`). Output goes under `Circuit_prints/`. The SIGNALS section is the human-readable form of `driver` and `fanouts` described above.

---

## Mental checklist when reading a dump

1. **PI** — `driver=-`, level `L0`, fanouts list every gate pin this input feeds.
2. **W** — one driver, level of that driver, fanouts of the stem (empty only if unused; unused internals are rejected at parse).
3. **PO** — one driver, often `fanouts: (none)` unless the PO net is also used as a gate input.
4. **Gate line** — `id`, instance, level, type, `output <= inputs`.
5. **LEVELS** — same gates grouped by depth; empty intermediate levels do not occur because `max_level` is the number of groups.
