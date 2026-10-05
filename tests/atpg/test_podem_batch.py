from pathlib import Path

import pytest

from atpg.podem import format_pattern, run_podem_on_collapsed
from circuit.levelize import levelize
from fault.collapsing import all_collapsed_members, collapse_faults, collapse_map_keys
from parser.iscas_verilog import parse_iscas_verilog

ISCAS = Path(__file__).resolve().parents[2] / "ISCAS85_Circuits"


@pytest.mark.parametrize(
    ("pattern", "expected"),
    [
        ((1, 0, 1), "101"),
        ((1, None, 0), "1X0"),
        ((None, None, 1), "XX1"),
    ],
)
def test_format_pattern(pattern, expected):
    assert format_pattern(pattern) == expected


def test_format_pattern_rejects_invalid_bits():
    with pytest.raises(ValueError, match="invalid pattern bit"):
        format_pattern((2,))


def test_run_podem_on_collapsed_c17_skips_covered_reps():
    circuit = parse_iscas_verilog(ISCAS / "c17.v")
    levelize(circuit)
    collapsed = collapse_faults(circuit)
    reps = collapse_map_keys(collapsed.collapse_map)

    batch = run_podem_on_collapsed(
        circuit,
        collapsed.collapse_map,
        recursion_limit=200,
        backtrack_limit=10000,
    )

    assert len(batch.patterns) > 0
    assert len(batch.results) <= len(reps)
    assert batch.covered
    assert all(entry.formatted == format_pattern(entry.pattern) for entry in batch.patterns)

    for entry in batch.patterns:
        members = all_collapsed_members(collapsed.collapse_map, entry.rep)
        assert members <= batch.covered

    assert len(batch.results) <= len(reps)
    assert len(batch.patterns) + len(batch.untestable) + len(batch.aborted) == len(batch.results)
    assert batch.total_backtracks == sum(result.backtracks for result in batch.results.values())
