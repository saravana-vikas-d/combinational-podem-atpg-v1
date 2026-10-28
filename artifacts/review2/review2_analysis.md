# Review-II — Parser and fault-collapsing metrics
> PODEM is work in progress. This report evaluates parser and fault-collapsing measurements only; it does not establish end-to-end ATPG correctness or validated fault coverage.
## Presentation snapshot
- **Parse success:** 11/11 canonical ISCAS'85 benchmarks
- **Total gates (parsed OK):** 13351
- **Median parse time (across OK circuits):** 9.573 ms
- **Mean fault-list reduction (OK circuits):** 53.77%
- **Partition check passed:** 11 OK, 0 failed

## Definitions
- **parse_time:** Wall time for parse_iscas_verilog(path): read file, build circuit, validate(check_unused=True), and levelize. Does not include fault generation.
- **collapse_pipeline_time:** Wall time for generate_raw_faults(circuit) + collapse_equivalence + collapse_dominance on a freshly parsed circuit each repetition.
- **internal_wires:** Signals where is_pi is False and is_po is False.
- **logic_depth:** Maximum gate.level after levelization (0-based levels from PIs).
- **representative_count:** Number of keys in the collapse map after each stage (distinct ATPG targets after collapsing).
- **fault_description:** Each raw list entry is one SA0 or SA1 Fault object (line/stem or branch), not a physical site count.
- **partition_check:** verify_collapse_partition: bookkeeping that every raw fault name appears exactly once across representatives, equivalent, and dominator sets. Not a proof of collapsing rule correctness.

## Reduction formulas
- Equivalence reduction = `raw_total - representatives_after_equivalence`
- Additional dominance reduction = `representatives_after_equivalence - representatives_after_dominance`
- Overall reduction % = `(raw_total - representatives_after_dominance) / raw_total * 100`
- This is **fault-list reduction**, not ATPG fault coverage.

## Circuit and parser metrics
| Circuit | Parse | PI | PO | Signals | Internal | Gates | Depth | Max fan-in | Max fanout | Parse ms (median) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| c17 | OK | 5 | 2 | 11 | 4 | 6 | 3 | 2 | 2 | 0.308 (min 0.275, max 0.418) |
| c432 | OK | 36 | 7 | 196 | 153 | 160 | 17 | 9 | 9 | 3.217 (min 2.908, max 4.073) |
| c499 | OK | 41 | 32 | 243 | 170 | 202 | 11 | 5 | 12 | 2.621 (min 2.127, max 2.627) |
| c880 | OK | 60 | 26 | 443 | 357 | 383 | 24 | 4 | 8 | 4.317 (min 3.647, max 4.703) |
| c1355 | OK | 41 | 32 | 587 | 514 | 546 | 24 | 5 | 12 | 6.666 (min 5.670, max 9.502) |
| c1908 | OK | 33 | 25 | 913 | 855 | 880 | 40 | 8 | 16 | 9.573 (min 8.780, max 9.782) |
| c2670 | OK | 233 | 140 | 1502 | 1129 | 1269 | 32 | 5 | 11 | 13.044 (min 12.804, max 13.795) |
| c3540 | OK | 50 | 22 | 1719 | 1647 | 1669 | 47 | 8 | 16 | 17.166 (min 16.351, max 17.248) |
| c5315 | OK | 178 | 123 | 2485 | 2184 | 2307 | 49 | 9 | 15 | 25.659 (min 22.877, max 26.885) |
| c6288 | OK | 32 | 32 | 2448 | 2384 | 2416 | 124 | 2 | 16 | 26.034 (min 25.156, max 34.599) |
| c7552 | OK | 207 | 108 | 3720 | 3405 | 3513 | 43 | 5 | 15 | 36.943 (min 35.748, max 43.147) |

## Fault generation and collapsing
| Circuit | Raw | Line SA0 | Line SA1 | Br SA0 | Br SA1 | After equiv | After dom | Removed eq | Removed dom+ | Reduction % | Partition | Collapse ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| c17 | 34 | 11 | 11 | 6 | 6 | 22 | 16 | 12 | 6 | 52.94% | PASS | 0.299 (min 0.274, max 0.336) |
| c432 | 864 | 196 | 196 | 236 | 236 | 524 | 449 | 340 | 75 | 48.03% | PASS | 6.557 (min 5.294, max 7.089) |
| c499 | 998 | 243 | 243 | 256 | 256 | 758 | 706 | 240 | 52 | 29.26% | PASS | 5.981 (min 5.201, max 6.112) |
| c880 | 1760 | 443 | 443 | 437 | 437 | 942 | 745 | 818 | 197 | 57.67% | PASS | 16.884 (min 16.104, max 17.546) |
| c1355 | 2710 | 587 | 587 | 768 | 768 | 1574 | 1210 | 1136 | 364 | 55.35% | PASS | 27.300 (min 27.156, max 27.673) |
| c1908 | 3816 | 913 | 913 | 995 | 995 | 1879 | 1566 | 1937 | 313 | 58.96% | PASS | 39.457 (min 39.214, max 46.668) |
| c2670 | 5492 | 1502 | 1502 | 1244 | 1244 | 2747 | 2317 | 2745 | 430 | 57.81% | PASS | 96.404 (min 96.401, max 107.265) |
| c3540 | 7080 | 1719 | 1719 | 1821 | 1821 | 3428 | 2786 | 3652 | 642 | 60.65% | PASS | 134.873 (min 134.027, max 137.795) |
| c5315 | 10630 | 2485 | 2485 | 2830 | 2830 | 5350 | 4492 | 5280 | 858 | 57.74% | PASS | 358.658 (min 347.196, max 360.133) |
| c6288 | 12576 | 2448 | 2448 | 3840 | 3840 | 7744 | 5824 | 4832 | 1920 | 53.69% | PASS | 407.932 (min 390.925, max 412.755) |
| c7552 | 15106 | 3720 | 3720 | 3833 | 3833 | 7550 | 6132 | 7556 | 1418 | 59.41% | PASS | 809.213 (min 609.776, max 850.398) |

## Gate type counts (per circuit)

### c17

| Gate type | Count |
|---|---:|
| NAND | 6 |

### c432

| Gate type | Count |
|---|---:|
| AND | 4 |
| NAND | 79 |
| NOR | 19 |
| NOT | 40 |
| XOR | 18 |

### c499

| Gate type | Count |
|---|---:|
| AND | 56 |
| NOT | 40 |
| OR | 2 |
| XOR | 104 |

### c880

| Gate type | Count |
|---|---:|
| AND | 117 |
| BUF | 26 |
| NAND | 87 |
| NOR | 61 |
| NOT | 63 |
| OR | 29 |

### c1355

| Gate type | Count |
|---|---:|
| AND | 56 |
| BUF | 32 |
| NAND | 416 |
| NOT | 40 |
| OR | 2 |

### c1908

| Gate type | Count |
|---|---:|
| AND | 63 |
| BUF | 162 |
| NAND | 377 |
| NOR | 1 |
| NOT | 277 |

### c2670

| Gate type | Count |
|---|---:|
| AND | 333 |
| BUF | 272 |
| NAND | 254 |
| NOR | 12 |
| NOT | 321 |
| OR | 77 |

### c3540

| Gate type | Count |
|---|---:|
| AND | 498 |
| BUF | 223 |
| NAND | 298 |
| NOR | 68 |
| NOT | 490 |
| OR | 92 |

### c5315

| Gate type | Count |
|---|---:|
| AND | 718 |
| BUF | 313 |
| NAND | 454 |
| NOR | 27 |
| NOT | 581 |
| OR | 214 |

### c6288

| Gate type | Count |
|---|---:|
| AND | 256 |
| NOR | 2128 |
| NOT | 32 |

### c7552

| Gate type | Count |
|---|---:|
| AND | 776 |
| BUF | 535 |
| NAND | 1028 |
| NOR | 54 |
| NOT | 876 |
| OR | 244 |

## Chart-friendly series (for slides)
Use `review2_data.json` → `circuits[]` fields:
- Gate count: `total_gates`
- Fault stages: `raw_total`, `representatives_after_equivalence`, `representatives_after_dominance`
- Reduction: `overall_reduction_percent`

## Run metadata
- **Collected (UTC):** 2026-10-12T15:01:54.000443+00:00
- **Python:** 3.12.3
- **Platform:** Windows-11-10.0.26200-SP0
- **Git branch:** wip/podem-coverage_i1
- **Git commit:** 86cf0b2e42f8c232fbcbd1d8b6b40b3eb00edf91
- **Timing repetitions:** 3
- **Collection command:** `scripts/collect_review2_metrics.py`

## Reproduce
```bash
python scripts/collect_review2_metrics.py
python scripts/generate_review2_report.py
```

Single data file: `artifacts/review2/review2_data.json`
