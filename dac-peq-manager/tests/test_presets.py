"""Tests validating all bundled JSON acoustic presets."""

import json
from pathlib import Path
import pytest


PRESETS_DIR = Path(__file__).resolve().parent.parent / "presets"


@pytest.mark.parametrize("preset_filename", [
    "bmasterx6.json",
    "ew300_silver.json",
    "ew300_gold.json",
    "flat.json",
    "targets/harman_in_ear_2019v2.json",
    "targets/ief_neutral.json",
    "targets/jm_1.json",
])
def test_preset_validity(preset_filename: str):
    """Verify that each bundled preset adheres to schema, band limits, and frequency rules."""
    p_path = PRESETS_DIR / preset_filename
    assert p_path.is_file(), f"Preset file {preset_filename} missing!"

    data = json.loads(p_path.read_text(encoding="utf-8"))
    assert "name" in data
    assert "preamp" in data
    assert "bands" in data

    # Must contain exactly 5 bands for KT02H20 hardware PEQ
    bands = data["bands"]
    assert len(bands) == 5, f"{preset_filename} must have exactly 5 bands"

    # Preamp bounds: -12 dB to +12 dB
    assert -12.0 <= data["preamp"] <= 12.0

    valid_types = {"PK", "LSQ", "HSQ"}
    for b in bands:
        assert b["type"] in valid_types
        # Frequencies between 20 Hz and 20 kHz
        assert 20.0 <= b["freq"] <= 20000.0
        # Gains between -12 dB and +12 dB
        assert -12.0 <= b["gain"] <= 12.0
        # Q factor between 0.1 and 10.0
        assert 0.1 <= b["q"] <= 10.0


def test_bmasterx6_parameters():
    """Verify specific acoustic parameters for BASN BmasterX 6 preset."""
    data = json.loads((PRESETS_DIR / "bmasterx6.json").read_text())
    assert data["preamp"] == -2.5
    b = data["bands"]
    assert b[0]["type"] == "LSQ" and b[0]["freq"] == 50.0 and b[0]["gain"] == 2.2
    assert b[1]["type"] == "PK" and b[1]["freq"] == 195.0 and b[1]["gain"] == -2.4
    assert b[2]["type"] == "PK" and b[2]["freq"] == 2200.0 and b[2]["gain"] == 1.6
    assert b[3]["type"] == "PK" and b[3]["freq"] == 4500.0 and b[3]["gain"] == -1.8
    assert b[4]["type"] == "PK" and b[4]["freq"] == 9800.0 and b[4]["gain"] == -3.2


def test_ew300_silver_parameters():
    """Verify specific acoustic parameters for SIMGOT EW300 Silver Nozzle preset."""
    data = json.loads((PRESETS_DIR / "ew300_silver.json").read_text())
    assert data["preamp"] == -2.8
    b = data["bands"]
    assert b[0]["type"] == "LSQ" and b[0]["freq"] == 55.0 and b[0]["gain"] == 2.5
    assert b[1]["type"] == "PK" and b[1]["freq"] == 220.0 and b[1]["gain"] == -1.2
    assert b[2]["type"] == "PK" and b[2]["freq"] == 2800.0 and b[2]["gain"] == -1.8
    assert b[3]["type"] == "PK" and b[3]["freq"] == 5200.0 and b[3]["gain"] == -2.2
    assert b[4]["type"] == "HSQ" and b[4]["freq"] == 10500.0 and b[4]["gain"] == -1.5


def test_ew300_gold_parameters():
    """Verify specific acoustic parameters for SIMGOT EW300 Gold Nozzle preset."""
    data = json.loads((PRESETS_DIR / "ew300_gold.json").read_text())
    assert data["preamp"] == -2.2
    b = data["bands"]
    assert b[0]["type"] == "LSQ" and b[0]["freq"] == 45.0 and b[0]["gain"] == 1.5
    assert b[1]["type"] == "PK" and b[1]["freq"] == 180.0 and b[1]["gain"] == -2.2
    assert b[2]["type"] == "PK" and b[2]["freq"] == 2000.0 and b[2]["gain"] == 1.8
    assert b[3]["type"] == "PK" and b[3]["freq"] == 4200.0 and b[3]["gain"] == -1.0
    assert b[4]["type"] == "HSQ" and b[4]["freq"] == 9500.0 and b[4]["gain"] == 2.0


def test_flat_parameters():
    """Verify flat bypass reset preset."""
    data = json.loads((PRESETS_DIR / "flat.json").read_text())
    assert data["preamp"] == 0.0
    for b in data["bands"]:
        assert b["gain"] == 0.0
        assert b["freq"] == 1000.0
        assert b["q"] == 1.00
