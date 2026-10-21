"""Unit tests for Moondrop FreeDSP transport and device factory."""

from dac_peq.moondrop import MoondropFreeDSPDevice
from dac_peq.transport import get_dsp_device


def test_moondrop_freedsp_device_init():
    dev = MoondropFreeDSPDevice(use_mock=True)
    assert dev.max_bands == 9
    assert dev.architecture_name == "moondrop_dsp"

    with dev:
        preset = {
            "name": "Moondrop Test Preset",
            "preamp": -2.0,
            "bands": [
                {"index": i + 1, "type": "PK", "freq": 100 * (i + 1), "gain": 1.0, "q": 1.0}
                for i in range(9)
            ],
        }
        dev.apply_preset(preset, commit_flash=False)
        assert len(dev._dev.written_reports) == 1
        report = dev._dev.written_reports[0]
        # Command byte 0x20 for live apply
        assert report[0] == 0x20
        # 9 bands count
        assert report[1] == 9


def test_moondrop_freedsp_commit_flash():
    dev = MoondropFreeDSPDevice(use_mock=True)
    with dev:
        preset = {
            "name": "Commit Test",
            "preamp": -1.5,
            "bands": [
                {"index": 1, "type": "LSQ", "freq": 100.0, "gain": 3.0, "q": 0.71},
            ],
        }
        dev.apply_preset(preset, commit_flash=True)
        report = dev._dev.written_reports[0]
        # Command byte 0x21 for flash commit
        assert report[0] == 0x21


def test_moondrop_freedsp_auto_decimates_over_9_bands():
    dev = MoondropFreeDSPDevice(use_mock=True)
    with dev:
        preset = {
            "name": "12-Band Test",
            "preamp": -1.0,
            "bands": [
                {"index": i + 1, "type": "PK", "freq": 50 * (i + 1), "gain": 1.0, "q": 1.0}
                for i in range(12)
            ],
        }
        dev.apply_preset(preset)
        report = dev._dev.written_reports[0]
        # Max bands clamped to 9
        assert report[1] == 9


def test_get_dsp_device_factory():
    # KTMicro default
    kt_dev = get_dsp_device(vendor_id=0x31B2, product_id=0x0111, use_mock=True)
    assert kt_dev.architecture_name == "ktmicro_dsp"
    assert kt_dev.max_bands == 5

    # Moondrop FreeDSP
    moon_dev = get_dsp_device(vendor_id=0x31B2, product_id=0x0112, use_mock=True)
    assert moon_dev.architecture_name == "moondrop_dsp"
    assert moon_dev.max_bands == 9
