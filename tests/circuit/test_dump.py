from datetime import datetime
from pathlib import Path

from circuit.dump import dump_circuit, format_circuit
from parser.iscas_verilog import parse_iscas_verilog

ISCAS = Path(__file__).resolve().parents[2] / "ISCAS85_Circuits"


def test_format_circuit_c17_contains_expected_sections():
    circuit = parse_iscas_verilog(ISCAS / "c17.v")
    text = format_circuit(circuit)

    assert "CIRCUIT: c17" in text
    assert "Primary inputs  : 5" in text
    assert "Primary outputs : 2" in text
    assert "Internal wires  : 4" in text
    assert "Total gates     : 6" in text
    assert "Gate types      : NAND=6" in text
    assert "[0] NAND2_1      nand N10  <=  N1, N3" in text
    assert "PI  N3       driver=-            fanouts=NAND2_1[1], NAND2_2[0]" in text
    assert "PO  N22      driver=NAND2_5      fanouts=-" in text
    assert "W   N11      driver=NAND2_2      fanouts=NAND2_3[1], NAND2_4[0]" in text
    assert "LEVELS\n  (not levelized)" in text


def test_dump_circuit_writes_timestamped_file(tmp_path):
    circuit = parse_iscas_verilog(ISCAS / "c17.v")
    when = datetime(2026, 9, 10, 1, 2)

    path = dump_circuit(circuit, tmp_path, timestamp=when)

    assert path == tmp_path / "c17_10092026_0102.txt"
    assert path.read_text(encoding="utf-8") == format_circuit(circuit)
