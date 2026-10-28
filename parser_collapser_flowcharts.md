# Parser and fault collapser flowcharts

Sources: `src/parser/iscas_verilog.py`, `src/parser/verilog_utils.py`, `src/fault/collapsing.py`, `src/fault/fault.py`.

---

## 1. ISCAS Verilog parser (`parse_iscas_verilog`)

```mermaid
flowchart TD
    START([Open .v file]) --> ITER[iter_statements: strip // comments, join lines on ;]
    ITER --> LOOP{More statements?}
    LOOP -->|yes| APPLY[_apply_statement]
    LOOP -->|no| CHECK_MOD{circuit created?}
    CHECK_MOD -->|no| ERR_NO_MOD[[ParseError: no module]]
    CHECK_MOD -->|yes| VAL_PORTS[_validate_module_ports]
    VAL_PORTS --> VAL_CIRC[validate circuit check_unused=True]
    VAL_CIRC -->|ValidationError| ERR_VAL[[ParseError]]
    VAL_CIRC --> LEVEL[levelize Kahn]
    LEVEL -->|LevelizeError / CycleError| ERR_LVL[[ParseError]]
    LEVEL --> RETURN([Return Circuit])

    APPLY --> S_STRIP[strip statement]
    S_STRIP --> S_MOD{starts with module ?}
    S_MOD -->|yes| APPLY_MOD[_apply_module: Circuit name, port list]
    S_MOD -->|no| S_CTX{circuit exists?}
    S_CTX -->|no| ERR_BEFORE[[ParseError: before module]]
    S_CTX -->|yes| S_END{endmodule?}
    S_END -->|clean endmodule| LOOP
    S_END -->|endmodule;| ERR_END[[ParseError]]
    S_END -->|no| S_DECL{input / output / wire decl?}
    S_DECL -->|input| ADD_IN[_add_inputs: Signal is_pi, primary_inputs]
    S_DECL -->|output| ADD_OUT[_add_outputs: Signal is_po, primary_outputs]
    S_DECL -->|wire| ADD_W[_add_wires: internal Signal]
    S_DECL -->|no| S_GATE{primitive keyword?}
    S_GATE -->|yes| APPLY_GATE[_apply_gate]
    S_GATE -->|assign| ERR_ASSIGN[[ParseError: unsupported]]
    S_GATE -->|other| ERR_STMT[[ParseError: unsupported]]
    ADD_IN --> LOOP
    ADD_OUT --> LOOP
    ADD_W --> LOOP
    APPLY_MOD --> LOOP

    APPLY_GATE --> G_MATCH[_GATE_RE match type, instance, pins]
    G_MATCH -->|fail| ERR_GATE[[ParseError: invalid gate]]
    G_MATCH --> G_PINS[output = pin0, inputs = pin1..n]
    G_PINS --> G_CHK[validate pin count NOT/BUF=2 else >=3]
    G_CHK --> G_OUT[out signal: not PI, no prior driver]
    G_OUT --> G_IN[resolve input signals]
    G_IN --> G_NEW[Gate id++, wire driver + fanouts]
    G_NEW --> LOOP
```

### Statement lexer (`iter_statements`)

```mermaid
flowchart LR
    L1[Read line] --> L2{// comment line?}
    L2 -->|yes| L1
    L2 -->|no| L3[Append to buffer]
    L3 --> L4{; in buffer?}
    L4 -->|yes| L5[Yield statement up to ;]
    L5 --> L4
    L4 -->|no| L1
    L6[EOF buffer] --> L7{endmodule only?}
    L7 -->|yes| L8[yield endmodule]
    L7 -->|no| L9[[ParseError unterminated]]
```

---

## 2. Fault collapser (`collapse_faults`)

```mermaid
flowchart TD
    START([collapse_faults circuit]) --> RAW{faults list given?}
    RAW -->|no| GEN[generate_raw_faults]
    RAW -->|yes| USE[use provided faults]
    GEN --> EQ
    USE --> EQ

    GEN --> GEN_DETAIL["Per signal: line sa0/sa1<br/>If fanout >= 2: branch sa0/sa1 per (gate, pin)"]

    EQ[collapse_equivalence] --> EQ_INIT[Union-Find on all fault names]
    EQ_INIT --> EQ_GATES[For each gate: level low to high]
    EQ_GATES --> EQ_PAIR[_equivalence_pairs gate]
    EQ_PAIR --> EQ_UNION[union left, right for each pair]
    EQ_UNION --> EQ_NEXT{more gates?}
    EQ_NEXT -->|yes| EQ_GATES
    EQ_NEXT -->|no| EQ_MAP[_build_map_from_components: pick rep per class]

    EQ_MAP --> DOM[collapse_dominance]
    DOM --> DOM_COPY[Copy equivalence map]
    DOM_COPY --> DOM_GATES[For each gate: level high to low]
    DOM_GATES --> DOM_PAIR[_dominance_pairs gate]
    DOM_PAIR --> DOM_LOOP{each dominator, dominated}
    DOM_LOOP --> DOM_REP[Map both to class reps]
    DOM_REP --> DOM_MERGE[Add dominator class to dominated rep dominators set]
    DOM_MERGE --> DOM_REM[Mark dominator rep for removal]
    DOM_REM --> DOM_NEXT{more gates?}
    DOM_NEXT -->|yes| DOM_GATES
    DOM_NEXT -->|no| DOM_POP[Remove dominated reps from map keys]
    DOM_POP --> RESULT([CollapseResult: final collapse_map])

    subgraph equiv_rules [Equivalence pairs per gate type]
        E_AND[AND: input sa0 ~ output sa0 each pin]
        E_OR[OR: input sa1 ~ output sa1]
        E_NAND[NAND: input sa0 ~ output sa1]
        E_NOR[NOR: input sa1 ~ output sa0]
        E_NOT[NOT/BUF: input/output sa pairs]
        E_XOR[XOR/XNOR: none]
    end

    subgraph dom_rules [Dominance pairs dominator to dominated]
        D_AND[AND: out sa1 dominates input sa1]
        D_OR[OR: out sa0 dominates input sa0]
        D_NAND[NAND: out sa0 dominates input sa1]
        D_NOR[NOR: out sa1 dominates input sa0]
        D_OTHER[NOT/BUF/XOR/XNOR: none]
    end
```

### Representative selection (`_pick_rep`)

```mermaid
flowchart LR
    R1[Each equivalence class] --> R2[min by rank]
    R2 --> R3["Higher signal level first<br/>then PI before wire before PO<br/>then name, then stuck_at"]
```

### Collapse map shape

```mermaid
flowchart LR
    M1["rep fault name"] --> M2["equivalent: set of merged eq faults"]
    M1 --> M3["dominators: set of faults dominated into this class"]
```

PODEM uses **representative keys** only (`collapse_map_keys`); a successful test on a rep marks covered via `all_collapsed_members(rep)`.
