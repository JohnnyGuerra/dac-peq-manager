"""Tests for the CLI interface using Typer CliRunner."""

from pathlib import Path
from typer.testing import CliRunner
from dac_peq.cli import app

runner = CliRunner()


def test_cli_help():
    """Verify root CLI help displays all commands."""
    res = runner.invoke(app, ["--help"])
    assert res.exit_code == 0
    assert "Hardware DSP Flasher & Host PEQ Suite" in res.output
    for cmd in ["scan", "apply", "flash", "read", "filter", "export-pipewire", "export-apo", "udev", "plot"]:
        assert cmd in res.output


def test_cli_scan():
    """Verify scan command executes cleanly."""
    res = runner.invoke(app, ["scan"])
    assert res.exit_code == 0
    assert "Scanning USB HID audio & DSP devices" in res.output


def test_cli_plot():
    """Verify plot command displays preset curve."""
    res = runner.invoke(app, ["plot", "bmasterx6"])
    assert res.exit_code == 0
    assert "bmasterx6" in res.output
    assert "Frequency Response" in res.output


def test_cli_apply_with_mock():
    """Verify apply command writes to live RAM using emulated device."""
    res = runner.invoke(app, ["apply", "ew300-silver", "--mock", "--compensate-2x"])
    assert res.exit_code == 0
    assert "successfully written to live DSP RAM" in res.output
    assert "Compensate" in res.output
    assert "2X Active" in res.output


def test_cli_flash_with_mock():
    """Verify flash command writes to NVRAM using emulated device."""
    res = runner.invoke(app, ["flash", "ew300-gold", "--mock"])
    assert res.exit_code == 0
    assert "burned to hardware NVRAM flash" in res.output


def test_cli_read_with_mock(tmp_path: Path):
    """Verify read command displays table and exports JSON."""
    out_json = tmp_path / "readback.json"
    res = runner.invoke(app, ["read", "--mock", "-o", str(out_json)])
    assert res.exit_code == 0
    assert "Hardware DSP State" in res.output
    assert out_json.is_file()


def test_cli_filter_command():
    """Verify setting DAC reconstruction filter."""
    res = runner.invoke(app, ["filter", "FAST-PC", "--mock"])
    assert res.exit_code == 0
    assert "FAST-PC" in res.output


def test_cli_safety_guard_blocks_flashing_cx31993():
    """Verify that CLI apply/flash explicitly fails when target VID is CX31993."""
    res = runner.invoke(app, ["flash", "bmasterx6", "--vid", "0x0572", "--pid", "0x1B08"])
    assert res.exit_code == 2
    assert "[BLOCKED]" in res.output
    assert "SAFETY GUARD" in res.output


def test_cli_export_pipewire(tmp_path: Path):
    """Verify PipeWire filter-chain export via CLI."""
    out_conf = tmp_path / "jm6pro.conf"
    res = runner.invoke(app, ["export-pipewire", "bmasterx6", "-o", str(out_conf)])
    assert res.exit_code == 0
    assert "PipeWire Filter-Chain Generated" in res.output
    assert out_conf.is_file()


def test_cli_export_apo(tmp_path: Path):
    """Verify EqualizerAPO & Wavelet suite export via CLI."""
    res = runner.invoke(app, ["export-apo", "ew300-silver", "-o", str(tmp_path)])
    assert res.exit_code == 0
    assert "Exported Host DSP Suite" in res.output
    assert (tmp_path / "ew300_silver_equalizer_apo.txt").is_file()
    assert (tmp_path / "ew300_silver_wavelet_graphiceq.txt").is_file()
    assert (tmp_path / "ew300_silver_wavelet.json").is_file()


def test_cli_udev_print():
    """Verify udev rules output."""
    res = runner.invoke(app, ["udev", "--print"])
    assert res.exit_code == 0
    assert "idVendor}==\"31b2\"" in res.output
    assert "idVendor}==\"2972\"" in res.output


def test_cli_db_help():
    """Verify db subcommands appear in help."""
    res = runner.invoke(app, ["db", "--help"])
    assert res.exit_code == 0
    assert "search" in res.output
    assert "pull" in res.output
    assert "sources" in res.output


def test_cli_db_sources():
    """Verify db sources executes and lists providers."""
    res = runner.invoke(app, ["db", "sources"])
    assert res.exit_code == 0
    assert "Community Measurement Sources" in res.output
    assert "crinacle" in res.output


def test_cli_db_search():
    """Verify db search finds models."""
    res = runner.invoke(app, ["db", "search", "Aria", "--limit", "5"])
    assert res.exit_code == 0
    assert "Aria" in res.output


def test_cli_db_pull_and_plot(tmp_path: Path):
    """Verify pulling a preset and saving locally."""
    res = runner.invoke(app, ["db", "pull", "Moondrop Aria", "--plot", "--no-save"])
    assert res.exit_code == 0
    assert "Selected" in res.output
    assert "Pulled Community Preset" in res.output


def test_cli_apply_with_auto_preamp():
    """Verify apply with --auto-preamp automatically calculates headroom."""
    res = runner.invoke(app, ["apply", "jm_1", "--auto-preamp", "--mock"])
    assert res.exit_code == 0
    assert "Auto-Preamp set to:" in res.output


def test_cli_flash_with_yes_flag():
    """Verify flash with -y / --yes executes without interactive confirmation."""
    res = runner.invoke(app, ["flash", "ief_neutral", "--mock", "-y"])
    assert res.exit_code == 0
    assert "burned to hardware NVRAM flash" in res.output


def test_cli_plot_target_curve():
    """Verify target curves in presets/targets/ can be loaded and plotted."""
    res = runner.invoke(app, ["plot", "harman_in_ear_2019v2"])
    assert res.exit_code == 0
    assert "Harman In-Ear Target" in res.output


def test_cli_plot_with_compare():
    """Verify comparing two presets via CLI displays acoustic delta metrics."""
    res = runner.invoke(app, ["plot", "ew300-silver", "--compare", "harman_in_ear_2019v2"])
    assert res.exit_code == 0
    assert "Acoustic Delta Comparison" in res.output
    assert "RMS Difference:" in res.output
    assert "Peak Δ:" in res.output


def test_cli_export_pipewire_full_target(tmp_path: Path):
    """Verify export-pipewire with --full-target flag."""
    out_conf = tmp_path / "jm6pro_full.conf"
    # Create mock preset with full_bands
    preset_file = tmp_path / "test_10band.json"
    import json
    preset_data = {
        "name": "Test10",
        "preamp": -2.0,
        "bands": [{"type": "PK", "freq": 1000.0, "gain": 0.0, "q": 1.0}] * 5,
        "full_bands": [{"type": "PK", "freq": 100.0 * (i + 1), "gain": 1.0, "q": 1.0} for i in range(10)],
    }
    preset_file.write_text(json.dumps(preset_data))

    res = runner.invoke(app, ["export-pipewire", str(preset_file), "-o", str(out_conf), "--full-target"])
    assert res.exit_code == 0
    assert "full-fidelity target profile (10 bands)" in res.output
    assert out_conf.is_file()
    content = out_conf.read_text()
    assert "eq_band10_fl" in content


def test_cli_multi_slot_and_moondrop_dispatch():
    """Verify CLI --slot flag (1-4, default 3) and automatic 9-band Moondrop FreeDSP dispatch."""
    # Test --slot 2 on KTMicro
    res_slot = runner.invoke(app, ["apply", "bmasterx6", "--slot", "2", "--mock"])
    assert res_slot.exit_code == 0
    assert "Slot: 2 (0x02)" in res_slot.output

    # Test Moondrop FreeDSP (0x31B2:0x0112) dispatch via get_dsp_device
    res_moon = runner.invoke(app, ["apply", "ew300-silver", "--vid", "0x31B2", "--pid", "0x0112", "--mock"])
    assert res_moon.exit_code == 0
    assert "successfully written to live DSP RAM" in res_moon.output




