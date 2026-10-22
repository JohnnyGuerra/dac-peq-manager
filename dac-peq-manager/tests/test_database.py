"""Unit tests for the AutoEq & community measurement database module."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from dac_peq.database import (
    AutoEqDatabase,
    DatabaseEntry,
    parse_index_markdown,
    parse_parametric_eq_text,
    parse_readme_peq,
)

SAMPLE_INDEX_MD = """# Index
This is a list of all equalization profiles.

- [Sennheiser HD 600](./oratory1990/over-ear/Sennheiser%20HD%20600) by oratory1990
- [Sennheiser HD 600](./crinacle/GRAS%2043AG-7%20over-ear/Sennheiser%20HD%20600) by crinacle on GRAS 43AG-7
- [Moondrop Aria](./Super%20Review/in-ear/Moondrop%20Aria) by Super Review
- [Simgot Audio EW300 (gold)](./Fahryst/in-ear/Simgot%20Audio%20EW300%20(gold)) by Fahryst
- [7Hz Salnotes Zero](./crinacle/711%20in-ear/7Hz%20Salnotes%20Zero) by crinacle on 711
"""

SAMPLE_README_MD = """# Test IEM
See usage instructions for more info.

### Parametric EQs
You can use filters 1-5 or 1-10. Apply preamp of -5.4 dB or -5.2 dB, respectively.

|   # | Type      |   Fc (Hz) |    Q |   Gain (dB) |
|-----|-----------|-----------|------|-------------|
|   1 | LowShelf  |       105 | 0.7  |         4.2 |
|   2 | Peaking   |       210 | 1.10 |        -2.5 |
|   3 | Peaking   |      2250 | 1.35 |         2.1 |
|   4 | Peaking   |      4800 | 2.50 |        -1.8 |
|   5 | HighShelf |      9500 | 0.71 |        -3.0 |
|   6 | Peaking   |       350 | 1.80 |         0.5 |
|   7 | Peaking   |      7500 | 4.00 |        -1.2 |

### Graphs
![](./Test%20IEM.png)
"""

SAMPLE_PARAMETRIC_EQ_TXT = """Preamp: -4.5 dB
Filter 1: ON LSC Fc 80 Hz Gain 3.5 dB Q 0.71
Filter 2: ON PK Fc 220 Hz Gain -1.5 dB Q 1.20
Filter 3: ON PK Fc 2500 Hz Gain 2.0 dB Q 1.50
Filter 4: ON PK Fc 5000 Hz Gain -2.0 dB Q 2.00
Filter 5: ON HSC Fc 10000 Hz Gain -1.0 dB Q 0.71
Filter 6: ON PK Fc 7000 Hz Gain -1.2 dB Q 3.00
"""


def test_parse_index_markdown():
    entries = parse_index_markdown(SAMPLE_INDEX_MD)
    assert len(entries) == 5

    assert entries[0].name == "Sennheiser HD 600"
    assert entries[0].source == "oratory1990"
    assert entries[0].path == "./oratory1990/over-ear/Sennheiser%20HD%20600"
    assert entries[0].clean_path == "oratory1990/over-ear/Sennheiser%20HD%20600"

    assert entries[2].name == "Moondrop Aria"
    assert entries[2].source == "Super Review"


def test_parse_readme_peq():
    preamp, bands = parse_readme_peq(SAMPLE_README_MD)
    assert preamp == -5.4
    assert len(bands) == 5

    # Band 1: LowShelf -> LSQ
    assert bands[0]["type"] == "LSQ"
    assert bands[0]["freq"] == 105.0
    assert bands[0]["gain"] == 4.2
    assert bands[0]["q"] == 0.7

    # Band 2: Peaking -> PK
    assert bands[1]["type"] == "PK"
    assert bands[1]["freq"] == 210.0
    assert bands[1]["gain"] == -2.5
    assert bands[1]["q"] == 1.10

    # Band 5: HighShelf -> HSQ
    assert bands[4]["type"] == "HSQ"
    assert bands[4]["freq"] == 9500.0
    assert bands[4]["gain"] == -3.0
    assert bands[4]["q"] == 0.71


def test_parse_parametric_eq_text():
    preamp, bands = parse_parametric_eq_text(SAMPLE_PARAMETRIC_EQ_TXT)
    assert preamp == -4.5
    assert len(bands) == 5

    assert bands[0]["type"] == "LSQ"
    assert bands[0]["freq"] == 80.0
    assert bands[0]["gain"] == 3.5
    assert bands[0]["q"] == 0.71

    assert bands[4]["type"] == "HSQ"
    assert bands[4]["freq"] == 10000.0


def test_database_search_and_sources(tmp_path: Path):
    db = AutoEqDatabase(cache_dir=tmp_path)
    entries = parse_index_markdown(SAMPLE_INDEX_MD)
    db._entries = entries

    # Multi-word search
    res = db.search("HD 600")
    assert len(res) == 2
    assert all("HD 600" in r.name for r in res)

    # Source filtered search
    res_oratory = db.search("HD 600", source="oratory1990")
    assert len(res_oratory) == 1
    assert res_oratory[0].source == "oratory1990"

    # Source listing
    sources = db.list_sources()
    sources_dict = dict(sources)
    assert sources_dict["oratory1990"] == 1
    assert sources_dict["Super Review"] == 1
    assert sources_dict["Fahryst"] == 1


def test_database_save_preset(tmp_path: Path):
    db = AutoEqDatabase(cache_dir=tmp_path)
    preset_data = {
        "name": "Test Model (Super Review)",
        "slug": "test_model_super_review",
        "description": "AutoEq target",
        "preamp": -3.5,
        "bands": [
            {"type": "LSQ", "freq": 100.0, "gain": 2.0, "q": 0.71},
            {"type": "PK", "freq": 1000.0, "gain": 0.0, "q": 1.0},
            {"type": "PK", "freq": 2000.0, "gain": 1.0, "q": 1.0},
            {"type": "PK", "freq": 4000.0, "gain": -1.0, "q": 1.5},
            {"type": "HSQ", "freq": 10000.0, "gain": -2.0, "q": 0.71},
        ],
    }

    saved_file = db.save_preset(preset_data, dest_dir=tmp_path)
    assert saved_file.is_file()
    assert saved_file.name == "test_model_super_review.json"

    loaded = json.loads(saved_file.read_text(encoding="utf-8"))
    assert loaded["preamp"] == -3.5
    assert len(loaded["bands"]) == 5


def test_offline_fallback_snapshot_when_network_unreachable(tmp_path: Path):
    """Verify bundled Top 15 Reddit IEM offline snapshot works when GitHub Raw is unreachable."""
    from urllib.error import URLError
    from dac_peq.database import load_offline_fallback

    fallback_entries = load_offline_fallback()
    assert len(fallback_entries) >= 15

    # Verify top Reddit IEM favorites are present
    names = [e.name for e in fallback_entries]
    assert "Truthear x Crinacle Zero:RED" in names
    assert "Truthear Hexa" in names
    assert "Moondrop Chu II" in names
    assert "SIMGOT EW300" in names
    assert "7Hz Timeless" in names

    # Simulate total network failure (URLError)
    db = AutoEqDatabase(cache_dir=tmp_path)
    with patch("urllib.request.urlopen", side_effect=URLError("Network unreachable")):
        results = db.search("Zero:RED")
        assert len(results) == 1
        assert results[0].name == "Truthear x Crinacle Zero:RED"

        preset = db.pull_preset(results[0], target_bands=5)
        assert preset["preamp"] == -4.2
        assert len(preset["bands"]) == 5
        assert len(preset["full_bands"]) == 10

