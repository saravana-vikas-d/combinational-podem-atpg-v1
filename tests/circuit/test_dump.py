from datetime import datetime
from pathlib import Path

import pytest

from circuit.dump import dump_circuit, format_circuit, print_circuit_from_file
from parser.iscas_verilog import parse_iscas_verilog

ISCAS = Path(__file__).resolve().parents[2] / "ISCAS85_Circuits"
CIRCUIT_PRINTS_DIR = Path(__file__).resolve().parents[2] / "Circuit_prints"


def test_format_circuit_c17_contains_expected_sections():
    circuit = parse_iscas_verilog(ISCAS / "c17.v")
    text = format_circuit(circuit)

    assert "CIRCUIT: c17" in text
    assert "Primary inputs  : 5" in text
    assert "Primary outputs : 2" in text
    assert "Internal wires  : 4" in text
    assert "Total gates     : 6" in text
    assert "Gate types      : NAND=6" in text
    assert "Level groups    : 3 groups, max gate level 3" in text
    assert "[0] NAND2_1      L1  nand N10  <=  N1, N3" in text
    assert "PI  N3       L0  driver=-            fanouts=NAND2_1[1], NAND2_2[0]" in text
    assert "PO  N22      L3  driver=NAND2_5      fanouts=-" in text
    assert "W   N11      L1  driver=NAND2_2      fanouts=NAND2_3[1], NAND2_4[0]" in text
    assert "LEVELS\n  tier 0 (L1): NAND2_1(L1), NAND2_2(L1)" in text
    assert "  tier 2 (L3): NAND2_5(L3), NAND2_6(L3)" in text


def test_dump_circuit_writes_timestamped_file(tmp_path):
    circuit = parse_iscas_verilog(ISCAS / "c17.v")
    when = datetime(2026, 9, 10, 1, 2)

    path = dump_circuit(circuit, tmp_path, timestamp=when)

    assert path == tmp_path / "c17_10092026_0102.txt"
    assert path.read_text(encoding="utf-8") == format_circuit(circuit)


def test_print_circuit_from_file_writes_to_tests_circuit_prints(tmp_path):
    when = datetime(2026, 9, 10, 21, 38)
    path = print_circuit_from_file(
        ISCAS / "c17.v",
        output_dir=tmp_path,
        timestamp=when,
    )

    assert path == tmp_path / "c17_10092026_2138.txt"
    assert path.read_text(encoding="utf-8") == format_circuit(
        parse_iscas_verilog(ISCAS / "c17.v")
    )


@pytest.mark.parametrize(
    "verilog_path",
    [ISCAS / "c17.v"],
)
def test_print_circuit_from_file(verilog_path: Path):
    when = datetime(2026, 9, 10, 21, 38)
    path = print_circuit_from_file(verilog_path, timestamp=when)

    assert path.parent.resolve() == CIRCUIT_PRINTS_DIR.resolve()
    assert path.name == f"{verilog_path.stem}_{when.strftime('%d%m%Y_%H%M')}.txt"
    assert f"CIRCUIT: {verilog_path.stem}" in path.read_text(encoding="utf-8")
