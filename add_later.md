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

