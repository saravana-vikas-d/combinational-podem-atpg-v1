# Add later (post-v1 / optimizations)

Items deferred from the core PODEM pipeline. Not required for correctness of v1.

---

## Controllability and observability (SCOAP-style)

**Status:** deferred  
**Suggested location:** `src/circuit/scoap.py` or `src/fault/scoap.py`  
**When to add:** after PODEM runs on c17 and larger benchmarks; consider if runtime/backtracks are too high.

### What it is

- **CC0 / CC1:** cost to control a signal to 0 or 1 from primary inputs  
- **CO:** cost to observe a signal change at a primary output  
- Computed once over the levelized circuit (bottom-up CC, top-down CO)



### Why it was deferred

Classic PODEM does **not** require precomputed CO metrics. Our v1 path is:

1. Parse + levelize
2. Collapse faults (equivalence + dominance)
3. Forward implication + backtrace
4. PODEM

Fault collapsing uses explicit gate rules, not CO-based merging.

### Where it could help later


| Use                        | Benefit                                                                 |
| -------------------------- | ----------------------------------------------------------------------- |
| Fault ordering             | Run easier collapsed faults first on large circuits (e.g. c6288, c7552) |
| PODEM heuristics           | Prefer PIs with lower CC when multiple justification choices exist      |
| Static untestability hints | CC0/CC1/CO = ∞ may flag redundant faults before PODEM                   |
| Reporting                  | Mark “hard” faults in summary output                                    |




### Where it does not replace existing work

- Does **not** replace equivalence/dominance collapsing (Module 2)  
- Does **not** replace PODEM for proving testable vs untestable  
- Weak on XOR-heavy logic (c499); PODEM/backtrace remains authoritative



### Integration hook

Run after `levelize(circuit)`, optionally annotate `Signal` with `cc0`, `cc1`, `co` (or a side table). Use for ordering/heuristics only unless extended for static redundancy detection.

### References in repo

- `plan.md` — Module 2 (collapse), Module 4 (PODEM); no CO in v1 scope  
- Discussion: 2026-09-12 — CO useful for performance, not required for v1

---

## Incremental forward implication (fanout-cone update)

**Status:** deferred  
**Suggested location:** `src/sim/implication.py` — e.g. `forward_imply_from(circuit, changed: list[Signal])`  
**When to add:** after v1 PODEM works on c17/c432; profile first — only worth it if `forward_imply()` is a hotspot on c6288/c7552.

### What it is

v1 runs a **full levelized scan** on every implication call: all gates in `circuit.levels`, low → high.

Incremental implication re-simulates only the **fanout cone** of signals whose values changed:

1. Seed a queue with changed signals (PI assignment, backtrace assignment, fault injection).
2. Process fanout gates in **level order** (inputs must be ready before outputs).
3. Recompute each gate with `eval_gate`; if the output changes, enqueue that output signal.
4. Stop when the queue is empty or a conflict is detected.

### Why it was deferred

- Full scan is simpler, easier to test, and correct with reset-and-re-imply PODEM.
- ISCAS'85 gate counts (even c7552 ~3.7k gates) are small for Python per-call cost.
- PODEM search/backtracking usually dominates runtime, not one full implication pass.
- Incremental imply complicates backtracking: undoing one assignment requires knowing which downstream values are stale, or falling back to full reset + full imply anyway.

### Not the same as D-frontier

| | Incremental implication | D-frontier (Module 4) |
|---|---|---|
| Purpose | Faster simulation | PODEM search — where to justify next |
| Gates | Downstream of **any** changed signal | Output `X`, at least one input `D` or `D'` |

### Where it could help later

- Large benchmarks with deep PODEM trees and many implication calls per fault.
- PODEM implementations that **do not** reset all signals to `X` on every backtrack (assignment stack + undo).

### Integration hook

Keep public `forward_imply(circuit)` as full scan. Add optional internal or overload:

```python
def forward_imply_from(circuit: Circuit, changed: list[Signal]) -> bool:
    ...
```

Same `_try_assign` and `eval_gate`; share gate-evaluation helper with full scan.

### References in repo

- `plan.md` — Module 3a (full levelized forward implication)
- Discussion: 2026-09-21 — full scan for v1; incremental deferred

---

## Backtrace: already-set input handling

**Status:** deferred  
**Suggested location:** `src/sim/implication.py` — extend `backtrace()` or add `apply_backtrace()`  
**When to add:** after v1 PODEM works on c17; consider if backtrack count is high due to redundant re-assignments on already-justified wires.

### What it is

v1 `backtrace(gate, desired, input_index)` always returns the full list of required input assignments (`0`/`1`), even when some inputs already have a non-`X` value. The caller assigns everything; `_try_assign` / `forward_imply` detect conflicts and PODEM backtracks at a higher level.

A smarter version would inspect current input values **before** assigning:

| Current input | Required by backtrace | v1 behavior | Smarter behavior |
|---------------|----------------------|-------------|------------------|
| `X` | `0` or `1` | assign | assign |
| same as required | `0` or `1` | assign (no-op) | skip (compatible) |
| different | `0` or `1` | assign → conflict on imply | **fail fast on this gate** — don't assign; signal impossibility without full PODEM backtrack |

### Why it was deferred

- v1 keeps backtrace as a pure controlling-value table with no circuit state awareness.
- Conflict detection via `_try_assign` + `forward_imply` is simpler and sufficient for correctness.
- Already-set compatible inputs are harmless no-ops when values match.
- Handling incompatible already-set inputs inside backtrace is an optimization / early-pruning, not required for a correct first PODEM.

### Desired behavior later

When an input required by backtrace conflicts with an existing assignment on that signal:

1. Detect at backtrace time (read `signal.value`, compare good rail to required `0`/`1`).
2. Return failure for **this gate justification** (e.g. `None` or raise `BacktraceConflict`) without writing assignments.
3. Let PODEM try another `input_index`, `desired`, or D-frontier gate — **not** recurse backtrace on the same gate with partial assigns.

Do **not** silently overwrite existing values; do **not** backtrack within `backtrace()` itself.

### Integration hook

```python
def backtrace(gate, desired, input_index) -> list[tuple[Signal, Logic5]] | None:
    # None = this justification branch is impossible given current assignments
    ...
```

Or split: `backtrace(...)` stays pure; `apply_backtrace(circuit, gate, desired, input_index) -> bool` checks existing values before `_try_assign`.

### References in repo

- `plan.md` — Module 3b (`backtrace`); v1 returns assignments unconditionally
- Discussion: 2026-09-22 — v1 defers already-set input conflict handling to imply/PODEM backtrack

---

## PODEM: D-frontier gate selection heuristic

**Status:** deferred  
**Suggested location:** `src/atpg/podem.py` — `select_d_frontier_gate()`  
**When to add:** after v1 PODEM works on c17; compare backtrack counts on c499/c6288 if runtime is high.

### What it is

v1 uses **highest-level** D-frontier gate (classic PODEM — closest to PO).

Alternative: **lowest-level** gate (justify near fault first, build propagation outward).

### Why it was deferred

Both orderings explore the same search space; correctness is unchanged. Choice affects backtrack count and runtime, not testability results.

### Desired behavior later

- Add CLI flag or config: `--d-frontier-policy highest|lowest` (default: `highest`).
- Log backtrack count per policy on benchmarks; pick winner per circuit family if needed.

### References in repo

- `plan.md` — Module 4 (PODEM heuristics)
- Discussion: 2026-09-23 — v1 locks `max(gate.level)`; flip to `min(gate.level)` if backtracks are high on c17+

---

## Pattern compaction: X-aware redundancy

**Status:** deferred  
**Suggested location:** `src/atpg/fault_sim.py` + compaction pass after batch PODEM  
**When to add:** Module 7 (after fault simulator exists).

### What it is

PODEM v1 keeps don't-cares as `X` in patterns (`Pattern = tuple[int | None, ...]`).

**Subsumption:** pattern V1 subsumes V2 if at every PI position V1 is `X` or V1 matches V2 (`0`/`0` or `1`/`1`). V1 then represents a set of concrete vectors (all `X` expansions).

### Rules

- Dropping V2 when V1 subsumes V2 is valid **only if** fault simulation shows some `X`-fill of V1 detects every fault V2 detects.
- Do **not** drop patterns based on structural subsumption alone.
- PODEM `X` on a PI means “not assigned during search” — not guaranteed don't-care until fault-sim confirms.
- Greedy set cover over **fault coverage sets**, not just vector count.

### Why it was deferred

Requires `fault_sim.py` (parallel fault simulation). v1 emits all per-rep patterns with `X` preserved; compaction is Phase 2.

### References in repo

- `plan.md` — Module 7 (pattern compaction)
- Discussion: 2026-09-23 — keep `X` in `.tp`; compaction after fault sim

---

## Explicit fault-to-fault dominance mapping

**Status:** deferred  
**When:** optional debug / audit; not required for PODEM or coverage.

### v1 behavior

`collapse_map[rep] = (equivalent_list, dominated_list)` only. We do **not** store
which gate or which fault dominated which.

### Possible extension

```python
dominance_edges: dict[str, str]  # dominated_fault -> immediate_dominator_fault
# or
dominance_edges: list[tuple[str, str, str]]  # (dominated, dominator, gate_instance)


## CollapseResult class vs plain dict

**Status:** deferred review  
**Current v1:** keep `CollapseResult` dataclass wrapping `collapse_map`.

### Question to revisit later

Is `CollapseResult` adding value over `CollapseMap = dict[str, tuple[list[str], list[str]]]` plus helper functions?

### Re-evaluate after

- Module 2 tests pass on c17
- CLI writes `collapsed_faults.txt` from the result
- If the class never gains fields (raw_count, stats, methods), consider removing it and using a typed dict alias only

