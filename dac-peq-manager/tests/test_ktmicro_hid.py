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
    assert is_conexant_cx31993({"vendor_id": CONEXANT_VID, "product_id": 0x1B08})
    assert is_conexant_cx31993({"vendor_id": 0x1234, "product_string": "Conexant CX31993 USB Audio"})
    assert is_conexant_cx31993({"vendor_id": 0x1234, "manufacturer_string": "Conexant"})
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
    """Verify live RAM write and readback with 0.5 dB preamp precision."""
    preset = {
        "name": "test_preset",
        "preamp": -2.5,
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

        # Check 0.5 dB precision preserved exactly
        assert state["preamp"] == -2.5
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


def test_compensate_2x_option():
    """Verify 2x frequency compensation scaling."""
    preset = {
        "name": "comp_preset",
        "preamp": 0.0,
        "bands": [
            {"index": 1, "type": "PK", "freq": 200.0, "gain": 0.0, "q": 1.0},
            {"index": 2, "type": "PK", "freq": 1000.0, "gain": 0.0, "q": 1.0},
            {"index": 3, "type": "PK", "freq": 1000.0, "gain": 0.0, "q": 1.0},
            {"index": 4, "type": "PK", "freq": 1000.0, "gain": 0.0, "q": 1.0},
            {"index": 5, "type": "PK", "freq": 1000.0, "gain": 0.0, "q": 1.0},
        ],
    }

    dev = KTMicroDSPDevice(use_mock=True)
    with dev:
        # When writing with compensate_2x=True, freq in RAM is halved (100 Hz)
        dev.apply_preset(preset, commit_flash=False, compensate_2x=True)
        raw_state = dev.read_current_peq(compensate_2x=False)
        assert raw_state["bands"][0]["freq"] == 100.0

        # When reading back with compensate_2x=True, reported frequency is restored (200 Hz)
        comp_state = dev.read_current_peq(compensate_2x=True)
        assert comp_state["bands"][0]["freq"] == 200.0


def test_set_dac_filter():
    """Verify setting DAC digital filter (FAST-PC, etc.)."""
    dev = KTMicroDSPDevice(use_mock=True)
    with dev:
        dev.set_dac_filter("FAST-PC", commit_flash=False)
        state = dev.read_current_peq()
        assert state["dac_filter"] == "FAST-PC"


def test_detect_firmware_quirks():
    """Verify firmware heuristic and 2X clock divisor bug detection."""
    from dac_peq.ktmicro_hid import detect_firmware_quirks

    # Generic KT02H20 v1.0 (release_number 0x0100) -> 2X divisor quirk active
    q_v1 = detect_firmware_quirks(0x31B2, 0x0111, release_number=0x0100)
    assert q_v1["requires_compensate_2x"] is True
    assert q_v1["firmware_version"] == "1.0"
    assert "2X clock divisor quirk active" in q_v1["description"]

    # FiiO JA11 v1.8 (release_number 0x0180) -> Patched native clocking
    q_ja11 = detect_firmware_quirks(0x2972, 0x0102, release_number=0x0180)
    assert q_ja11["requires_compensate_2x"] is False
    assert q_ja11["firmware_version"] == "1.8"
    assert "no 2X divisor needed" in q_ja11["description"]

    # Modern firmware v2.0 (release_number 0x0200) -> Native clocking
    q_v2 = detect_firmware_quirks(0x31B2, 0x0111, release_number=0x0200)
    assert q_v2["requires_compensate_2x"] is False
    assert q_v2["firmware_version"] == "2.0"


def test_wait_for_reenumeration_polling():
    """Verify event-driven USB re-enumeration watcher polls until device re-attaches."""
    dev = KTMicroDSPDevice(vendor_id=0x31B2, product_id=0x0111, use_mock=True)
    call_count = 0

    def fake_enumerate(vid, pid):
        nonlocal call_count
        call_count += 1
        # Simulate device detached for first 2 polls, then re-enumerated on 3rd poll
        if call_count < 3:
            return []
        return [{"vendor_id": vid, "product_id": pid, "path": b"/dev/hidraw99"}]

    ok = dev._wait_for_reenumeration(timeout_s=1.0, poll_interval_s=0.01, enumerate_fn=fake_enumerate)
    assert ok is True
    assert call_count == 3


def test_multi_slot_selection():
    """Verify writing to hardware memory slots 1 through 4 (default 3)."""
    dev = KTMicroDSPDevice(use_mock=True)
    bands = [{"index": i + 1, "type": "PK", "freq": 1000.0, "gain": 0.0, "q": 1.0} for i in range(5)]

    with dev:
        # Default slot is 3 (0x03) for backward compatibility
        dev.apply_preset({"name": "default_slot", "preamp": 0.0, "bands": bands})
        assert dev.read_current_peq()["slot_id"] == 3

        # Explicit slot 1..4
        for slot in (1, 2, 3, 4):
            dev.apply_preset({"name": f"slot_{slot}", "slot_id": slot, "preamp": 0.0, "bands": bands})
            assert dev.read_current_peq()["slot_id"] == slot


