"""Tests for KTMicro KT02H20 HID protocol, packet framing, and safety guards."""

import pytest
from dac_peq.ktmicro_hid import (
    CONEXANT_VID,
    KTMicroDSPDevice,
    DeviceSecurityException,
    is_conexant_cx31993,
    is_ktmicro_candidate,
)


def test_conexant_cx31993_detector():
    """Verify CX31993 detection across VID and USB descriptor strings."""
    # Match by VID
    assert is_conexant_cx31993({"vendor_id": CONEXANT_VID, "product_id": 0x1B08})
    # Match by Product string
    assert is_conexant_cx31993({"vendor_id": 0x1234, "product_string": "Conexant CX31993 USB Audio"})
    # Match by Manufacturer string
    assert is_conexant_cx31993({"vendor_id": 0x1234, "manufacturer_string": "Conexant"})
    # Non-Conexant
    assert not is_conexant_cx31993({"vendor_id": 0x31B2, "product_string": "Kiwi Ears-Allegro Mini"})


def test_ktmicro_candidate_detector():
    """Verify detection of known KTMicro / WalkPlay hardware."""
    assert is_ktmicro_candidate({"vendor_id": 0x31B2, "product_id": 0x0111})
    assert is_ktmicro_candidate({"vendor_id": 0x2972, "product_id": 0x0102})
    assert is_ktmicro_candidate({"vendor_id": 0x1234, "product_string": "Kiwi Ears Allegro Mini"})
    assert is_ktmicro_candidate({"vendor_id": 0x1234, "product_string": "BASN BmasterX 6 DSP"})
    assert not is_ktmicro_candidate({"vendor_id": 0x0572, "product_string": "CX31993"})


def test_cx31993_safety_guard_blocks_flashing():
    """Verify that attempting to connect to CX31993 immediately raises DeviceSecurityException."""
    dev = KTMicroDSPDevice(vendor_id=CONEXANT_VID, product_id=0x1B08)
    with pytest.raises(DeviceSecurityException) as excinfo:
        dev.connect()
    assert "SAFETY GUARD" in str(excinfo.value)
    assert "CX31993" in str(excinfo.value)
    assert "fixed mask ROM" in str(excinfo.value)


def test_mock_device_apply_and_read():
    """Verify live RAM write and readback using emulated KT02H20 hardware."""
    preset = {
        "name": "test_preset",
        "preamp": -2.0,
        "bands": [
            {"index": 1, "type": "LSQ", "freq": 55.0, "gain": 2.5, "q": 0.71},
            {"index": 2, "type": "PK", "freq": 220.0, "gain": -1.2, "q": 1.40},
            {"index": 3, "type": "PK", "freq": 2800.0, "gain": -1.8, "q": 2.00},
            {"index": 4, "type": "PK", "freq": 5200.0, "gain": -2.2, "q": 2.80},
            {"index": 5, "type": "HSQ", "freq": 10500.0, "gain": -1.5, "q": 0.71},
        ],
    }

    dev = KTMicroDSPDevice(use_mock=True)
    with dev:
        dev.apply_preset(preset, commit_flash=False)
        state = dev.read_current_peq()

        assert state["preamp"] == -2.0
        assert len(state["bands"]) == 5

        b1 = state["bands"][0]
        assert b1["type"] == "LSQ"
        assert b1["freq"] == 55.0
        assert b1["gain"] == 2.5
        assert b1["q"] == 0.71

        b5 = state["bands"][4]
        assert b5["type"] == "HSQ"
        assert b5["freq"] == 10500.0
        assert b5["gain"] == -1.5
        assert b5["q"] == 0.71


def test_mock_device_nvram_commit():
    """Verify NVRAM flash commit (command 0x53)."""
    preset = {
        "name": "commit_preset",
        "preamp": 0.0,
        "bands": [
            {"index": 1, "type": "PK", "freq": 1000.0, "gain": 0.0, "q": 1.0},
            {"index": 2, "type": "PK", "freq": 1000.0, "gain": 0.0, "q": 1.0},
            {"index": 3, "type": "PK", "freq": 1000.0, "gain": 0.0, "q": 1.0},
            {"index": 4, "type": "PK", "freq": 1000.0, "gain": 0.0, "q": 1.0},
            {"index": 5, "type": "PK", "freq": 1000.0, "gain": 0.0, "q": 1.0},
        ],
    }

    dev = KTMicroDSPDevice(use_mock=True)
    with dev:
        assert dev._dev.commit_count == 0
        dev.apply_preset(preset, commit_flash=True)
        assert dev._dev.commit_count == 1
