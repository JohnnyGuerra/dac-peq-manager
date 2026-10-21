"""Tests for NVRAM FlashWearTracker and CLI flash wear monitoring."""

from pathlib import Path
from typer.testing import CliRunner

from dac_peq.cli import app
from dac_peq.flash_tracker import FlashWearTracker

runner = CliRunner()


def test_flash_tracker_record_and_get_stats(tmp_path: Path):
    cache_file = tmp_path / "flash_history.json"
    tracker = FlashWearTracker(cache_file=cache_file)

    dev_id = "0x31B2:0x0111"
    assert tracker.get_stats(dev_id)["total_commits"] == 0

    c1 = tracker.record_commit(dev_id, preset_name="bmasterx6")
    assert c1 == 1

    stats = tracker.get_stats(dev_id)
    assert stats["total_commits"] == 1
    assert stats["last_24h_commits"] == 1
    assert stats["last_preset"] == "bmasterx6"
    assert stats["last_commit_time"] is not None

    # Record second commit
    c2 = tracker.record_commit(dev_id, preset_name="ew300_silver")
    assert c2 == 2
    assert tracker.get_stats(dev_id)["last_preset"] == "ew300_silver"


def test_flash_tracker_warning_thresholds(tmp_path: Path):
    cache_file = tmp_path / "flash_history.json"
    tracker = FlashWearTracker(cache_file=cache_file)
    dev_id = "0x31B2:0x0111"

    # Initially safe
    warn, _ = tracker.should_warn(dev_id, daily_threshold=5, cumulative_threshold=10)
    assert not warn

    # Simulate 5 commits today
    for i in range(5):
        tracker.record_commit(dev_id, preset_name=f"test_{i}")

    warn, msg = tracker.should_warn(dev_id, daily_threshold=5, cumulative_threshold=10)
    assert warn
    assert "5 times in the last 24 hours" in msg


def test_flash_tracker_clear(tmp_path: Path):
    cache_file = tmp_path / "flash_history.json"
    tracker = FlashWearTracker(cache_file=cache_file)

    tracker.record_commit("0x31b2:0x0111", preset_name="preset_a")
    tracker.record_commit("0x2972:0x0102", preset_name="preset_b")
    assert len(tracker.get_all_devices()) == 2

    tracker.clear("0x31b2:0x0111")
    assert len(tracker.get_all_devices()) == 1
    assert tracker.get_stats("0x31b2:0x0111")["total_commits"] == 0

    tracker.clear()
    assert len(tracker.get_all_devices()) == 0


def test_cli_flash_history_command(tmp_path: Path, monkeypatch):
    test_cache = tmp_path / "flash_history.json"
    monkeypatch.setattr("dac_peq.flash_tracker.get_default_cache_file", lambda: test_cache)

    # Empty initially
    res = runner.invoke(app, ["flash-history"])
    assert res.exit_code == 0
    assert "No NVRAM flash commits logged yet" in res.output

    # Flash once with mock
    res_flash = runner.invoke(app, ["flash", "bmasterx6", "--mock"])
    assert res_flash.exit_code == 0

    # Inspect history table
    res_table = runner.invoke(app, ["flash-history"])
    assert res_table.exit_code == 0
    assert "Hardware NVRAM Flash Health & Wear Log" in res_table.output
    assert "0x31b2" in res_table.output.lower()
    assert "bmasterx6" in res_table.output

    # Clear history
    res_clear = runner.invoke(app, ["flash-history", "--clear"])
    assert res_clear.exit_code == 0
    assert "Flash commit history cleared" in res_clear.output
