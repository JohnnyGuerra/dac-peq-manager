"""CLI Interface for dac-peq-manager.

Provides commands:
  - scan: Enumerate and identify USB audio DACs (KTMicro, Conexant CX31993, etc.)
  - apply: Write 5-band PEQ and preamp into live DSP RAM (instant listening)
  - flash: Write 5-band PEQ and preamp to RAM and commit to NVRAM (permanent)
  - read: Read active 5-band PEQ and preamp registers from hardware
  - filter: Configure hardware DAC digital reconstruction filter (FAST-LL, etc.)
  - export-pipewire: Generate PipeWire filter-chain configuration for JCALLY JM6 Pro
  - export-apo: Generate EqualizerAPO .txt and Wavelet profile suite
  - udev: Install or print Linux udev rules for non-root USB HID access
  - plot: Display ASCII/Unicode frequency response curve for a preset
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from dac_peq.biquad import (
    calculate_curve_difference,
    calculate_peak_composite_gain,
    calculate_recommended_preamp,
    decimate_bands,
    lint_acoustic_bands,
    render_ascii_frequency_response,
    validate_hardware_bands,
)
from dac_peq.dac_database import DACDatabase, DACInfo
from dac_peq.database import AutoEqDatabase, DatabaseEntry
from dac_peq.exporters import (
    DEFAULT_CX31993_SINK,
    export_apo_suite,
    export_pipewire_conf,
    format_pipewire_filter_chain,
)
from dac_peq.flash_tracker import FlashWearTracker
from dac_peq.ktmicro_hid import (
    DeviceCommunicationError,
    DeviceSecurityException,
    KTMicroDSPDevice,
    detect_firmware_quirks,
    scan_devices,
)
from dac_peq.transport import get_dsp_device

app = typer.Typer(
    name="dac-peq-manager",
    help="Hardware DSP Flasher & Host PEQ Suite for Portable USB-C DACs & Tribrid IEMs",
    add_completion=False,
)
console = Console()


def get_presets_dir() -> Path:
    """Return path to presets directory."""
    cur = Path(__file__).resolve().parent
    candidates = [
        cur.parent.parent / "presets",
        Path.cwd() / "presets",
        Path("/home/ubuntu/iem/dac-peq-manager/presets"),
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return candidates[0]


def load_preset_data(preset_name_or_path: str) -> Dict[str, Any]:
    """Load preset by name (e.g. 'bmasterx6', 'ew300-silver'), from JSON file, or auto-pull from AutoEq."""
    # Check if querying online database directly
    if preset_name_or_path.startswith(("autoeq:", "db:")):
        query = preset_name_or_path.split(":", 1)[1].strip()
        console.print(f"[dim]Searching AutoEq database for '{query}'...[/dim]")
        db = AutoEqDatabase()
        results = db.search(query, limit=5)
        if not results:
            console.print(f"[bold red]No models found in AutoEq database matching '{query}'.[/bold red]")
            raise typer.Exit(code=1)
        selected = results[0]
        console.print(f"[green]Found [bold]{selected.name}[/bold] ({selected.source}). Pulling 5-band PEQ profile...[/green]")
        preset_data = db.pull_preset(selected)
        return preset_data

    p_path = Path(preset_name_or_path)
    if p_path.is_file():
        try:
            return json.loads(p_path.read_text(encoding="utf-8"))
        except Exception as e:
            console.print(f"[bold red]Error reading preset file {p_path}:[/bold red] {e}")
            raise typer.Exit(code=1)

    norm = preset_name_or_path.lower().replace("_", "-")
    presets_dir = get_presets_dir()

    candidates = [
        presets_dir / f"{preset_name_or_path}.json",
        presets_dir / f"{norm}.json",
        presets_dir / f"{norm.replace('-', '_')}.json",
        presets_dir / "targets" / f"{preset_name_or_path}.json",
        presets_dir / "targets" / f"{norm}.json",
        presets_dir / "targets" / f"{norm.replace('-', '_')}.json",
    ]

    for cand in candidates:
        if cand.is_file():
            try:
                return json.loads(cand.read_text(encoding="utf-8"))
            except Exception as e:
                console.print(f"[bold red]Error reading preset {cand}:[/bold red] {e}")
                raise typer.Exit(code=1)

    available = [p.stem for p in presets_dir.glob("*.json")]
    console.print(
        f"[bold red]Preset '{preset_name_or_path}' not found.[/bold red]\n"
        f"Available presets in {presets_dir}: [cyan]{', '.join(sorted(set(available))) if available else 'none'}[/cyan]"
    )
    raise typer.Exit(code=1)


def parse_hex_id(val: Optional[str]) -> Optional[int]:
    """Parse hex string (e.g. '0x31B2' or '31B2') to integer."""
    if not val:
        return None
    try:
        return int(val, 16) if val.lower().startswith("0x") else int(val, 16)
    except ValueError:
        try:
            return int(val)
        except ValueError:
            console.print(f"[bold red]Invalid hex value:[/bold red] {val}")
            raise typer.Exit(code=1)


@app.command("scan")
def cmd_scan():
    """Scan and list connected USB HID devices with DSP capabilities."""
    console.print("[bold cyan]Scanning USB HID audio & DSP devices...[/bold cyan]\n")
    devices = scan_devices()
    dac_db = DACDatabase()

    if not devices:
        console.print("[yellow]No USB HID devices detected on this system.[/yellow]")
        return

    table = Table(title="Detected USB HID Audio & DSP Endpoints", title_style="bold magenta")
    table.add_column("VID:PID", style="cyan", no_wrap=True)
    table.add_column("Manufacturer", style="white")
    table.add_column("Product", style="bold white")
    table.add_column("Matched DAC Profile", style="magenta")
    table.add_column("Capabilities & Action", style="green")

    for d in devices:
        matched = dac_db.lookup(d.vendor_id, d.product_id) or dac_db.lookup_by_string(d.product_string or "")
        matched_str = f"{matched.name} ({matched.chipset})" if matched else "-"

        status_color = "green" if d.is_ktmicro else ("yellow" if d.is_conexant else "dim")
        table.add_row(
            d.vid_pid_hex,
            d.manufacturer_string or "-",
            d.product_string or "Unknown",
            matched_str,
            f"[{status_color}]{d.status_description}[/{status_color}]",
        )

    console.print(table)
    console.print(
        "\n[bold]Legend:[/bold]\n"
        "  [green]* KTMicro KT02H20 / WalkPlay SoC:[/green] 5-Band hardware biquad NVRAM flasher available.\n"
        "  [yellow]* Conexant CX31993 (JM6 Pro):[/yellow] Fixed mask ROM. Flashing blocked. Use 'export-pipewire' or 'export-apo'."
    )


@app.command("apply")
def cmd_apply(
    preset_name: str = typer.Argument(..., help="Preset name (bmasterx6, ew300-silver, ew300-gold, flat) or JSON file path"),
    vid: Optional[str] = typer.Option(None, "--vid", help="Target device Vendor ID (hex, e.g. 0x31B2)"),
    pid: Optional[str] = typer.Option(None, "--pid", help="Target device Product ID (hex, e.g. 0x0111)"),
    slot: int = typer.Option(3, "--slot", "-s", min=1, max=4, help="Hardware EQ memory slot (1-4, default 3 for factory compatibility)"),
    auto_preamp: bool = typer.Option(False, "--auto-preamp", help="Automatically calculate negative preamp with 0.5dB intersample headroom"),
    compensate_2x: Optional[bool] = typer.Option(None, "--compensate-2x", help="Compensate for older generic KT02H20 firmwares with 2x frequency offset (auto-detected if omitted)"),
    mock: bool = typer.Option(False, "--mock", help="Use software-emulated KT02H20 device for testing"),
):
    """Write PEQ and preamp into live DSP RAM (instant listening, temporary)."""
    preset = dict(load_preset_data(preset_name))
    preset["slot_id"] = slot
    v_id = parse_hex_id(vid)
    p_id = parse_hex_id(pid)

    bands = preset.get("bands", [])
    if auto_preamp:
        rec_preamp = calculate_recommended_preamp(bands)
        preset["preamp"] = rec_preamp
        console.print(f"[cyan]Auto-Preamp set to:[/cyan] [bold yellow]{rec_preamp:+.1f} dB[/bold yellow] (0.5 dB intersample headroom)")
    else:
        peak_gain = calculate_peak_composite_gain(bands)
        total_peak = peak_gain + float(preset.get("preamp", 0.0))
        if total_peak > 0.0:
            rec = calculate_recommended_preamp(bands)
            console.print(
                f"[bold yellow][WARNING][/bold yellow] Peak composite gain is [bold red]{total_peak:+.1f} dB[/bold red] (exceeds 0 dBFS).\n"
                f"[dim]Intersample clipping may occur during DAC reconstruction. Use '--auto-preamp' to apply recommended preamp ({rec:+.1f} dB).[/dim]"
            )

    # Acoustic Coupler Artifact Linter
    acoustic_warnings = lint_acoustic_bands(bands)
    for w in acoustic_warnings:
        console.print(f"[bold yellow][ACOUSTIC ADVICE][/bold yellow] {w}")

    console.print(
        Panel(
            f"[bold green]Applying Preset:[/bold green] [bold cyan]{preset.get('name')}[/bold cyan]\n"
            f"[dim]{preset.get('description', '')}[/dim]\n"
            f"Global Preamp: [yellow]{preset.get('preamp', 0.0):+.1f} dB[/yellow] | Slot: [cyan]{slot} (0x0{slot})[/cyan] | Mode: [bold]Live RAM Write[/bold] (Instant listen)"
            + (" | [yellow]Compensate 2X Active[/yellow]" if compensate_2x else ""),
            title="Live Hardware DSP Config",
            border_style="green",
        )
    )

    plot_str = render_ascii_frequency_response(preset.get("bands", []), float(preset.get("preamp", 0.0)))
    console.print(plot_str + "\n")

    try:
        dev = get_dsp_device(vendor_id=v_id, product_id=p_id, use_mock=mock)
        with dev:
            if dev.max_bands == 9 and preset.get("full_bands") and len(preset.get("full_bands")) > len(preset.get("bands", [])):
                preset["bands"] = decimate_bands(preset["full_bands"], target_bands=9)
            quirks = getattr(dev, "firmware_quirks", None)
            is_comp = compensate_2x if compensate_2x is not None else (quirks.get("requires_compensate_2x", False) if quirks else False)
            if compensate_2x is None and is_comp and quirks:
                console.print(f"[cyan]Auto-detected firmware ({quirks.get('firmware_version', '1.0')}): 2X clock divisor compensation active.[/cyan]")
            dev.apply_preset(preset, commit_flash=False, compensate_2x=is_comp)

        console.print(
            "[bold green][OK] PEQ curve successfully written to live DSP RAM![/bold green]\n"
            "[dim]Note: Live RAM adjustments take effect immediately. To persist across reboots, run 'flash'.[/dim]"
        )
    except DeviceSecurityException as e:
        console.print(f"[bold red][BLOCKED][/bold red] {e}")
        raise typer.Exit(code=2)
    except Exception as e:
        console.print(f"[bold red][ERROR][/bold red] Communication failed: {e}")
        raise typer.Exit(code=1)


@app.command("flash")
def cmd_flash(
    preset_name: str = typer.Argument(..., help="Preset name (bmasterx6, ew300-silver, ew300-gold, flat) or JSON file path"),
    vid: Optional[str] = typer.Option(None, "--vid", help="Target device Vendor ID (hex, e.g. 0x31B2)"),
    pid: Optional[str] = typer.Option(None, "--pid", help="Target device Product ID (hex, e.g. 0x0111)"),
    slot: int = typer.Option(3, "--slot", "-s", min=1, max=4, help="Hardware EQ memory slot (1-4, default 3 for factory compatibility)"),
    auto_preamp: bool = typer.Option(False, "--auto-preamp", help="Automatically calculate negative preamp with 0.5dB intersample headroom"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Confirm writing to hardware NVRAM flash without interactive prompt"),
    compensate_2x: Optional[bool] = typer.Option(None, "--compensate-2x", help="Compensate for older generic KT02H20 firmwares with 2x frequency offset (auto-detected if omitted)"),
    mock: bool = typer.Option(False, "--mock", help="Use software-emulated KT02H20 device for testing"),
):
    """Write PEQ and commit directly to onboard NVRAM (permanent flash)."""
    preset = dict(load_preset_data(preset_name))
    preset["slot_id"] = slot
    v_id = parse_hex_id(vid)
    p_id = parse_hex_id(pid)

    bands = preset.get("bands", [])
    if auto_preamp:
        rec_preamp = calculate_recommended_preamp(bands)
        preset["preamp"] = rec_preamp
        console.print(f"[cyan]Auto-Preamp set to:[/cyan] [bold yellow]{rec_preamp:+.1f} dB[/bold yellow] (0.5 dB intersample headroom)")
    else:
        peak_gain = calculate_peak_composite_gain(bands)
        total_peak = peak_gain + float(preset.get("preamp", 0.0))
        if total_peak > 0.0:
            rec = calculate_recommended_preamp(bands)
            console.print(
                f"[bold yellow][WARNING][/bold yellow] Peak composite gain is [bold red]{total_peak:+.1f} dB[/bold red] (exceeds 0 dBFS).\n"
                f"[dim]Intersample clipping may occur during DAC reconstruction. Use '--auto-preamp' to apply recommended preamp ({rec:+.1f} dB).[/dim]"
            )

    # Acoustic Coupler Artifact Linter
    acoustic_warnings = lint_acoustic_bands(bands)
    for w in acoustic_warnings:
        console.print(f"[bold yellow][ACOUSTIC ADVICE][/bold yellow] {w}")

    # NVRAM Flash Endurance Protection Check
    dev_key = f"0x{v_id:04X}:0x{p_id:04X}" if (v_id and p_id) else "0x31B2:0x0111"
    tracker = FlashWearTracker()
    warn, warn_msg = tracker.should_warn(dev_key)
    if warn:
        console.print(f"\n[bold red][FLASH WEAR WARNING][/bold red] {warn_msg}\n")

    stats = tracker.get_stats(dev_key)

    # NVRAM Flash Endurance Protection Confirmation
    if not yes and not mock:
        burn_stats_str = f" ({stats['total_commits']} total burns, {stats['last_24h_commits']} today)" if stats["total_commits"] > 0 else ""
        confirm = typer.confirm(
            f"⚠️  NVRAM Flash commits permanently to onboard physical flash memory (~10k-100k cycle endurance){burn_stats_str}. Commit settings now?",
            default=True,
        )
        if not confirm:
            console.print("[dim]Flash commit cancelled by user.[/dim]")
            raise typer.Exit(code=0)

    console.print(
        Panel(
            f"[bold magenta]Flashing Preset to NVRAM:[/bold magenta] [bold cyan]{preset.get('name')}[/bold cyan]\n"
            f"[dim]{preset.get('description', '')}[/dim]\n"
            f"Global Preamp: [yellow]{preset.get('preamp', 0.0):+.1f} dB[/yellow] | Slot: [cyan]{slot} (0x0{slot})[/cyan] | Mode: [bold red]NVRAM Burn (0x53 Commit)[/bold red]"
            + (" | [yellow]Compensate 2X Active[/yellow]" if compensate_2x else ""),
            title="Hardware NVRAM Flasher",
            border_style="magenta",
        )
    )

    plot_str = render_ascii_frequency_response(preset.get("bands", []), float(preset.get("preamp", 0.0)))
    console.print(plot_str + "\n")

    try:
        dev = get_dsp_device(vendor_id=v_id, product_id=p_id, use_mock=mock)
        with dev:
            if dev.max_bands == 9 and preset.get("full_bands") and len(preset.get("full_bands")) > len(preset.get("bands", [])):
                preset["bands"] = decimate_bands(preset["full_bands"], target_bands=9)
            quirks = getattr(dev, "firmware_quirks", None)
            is_comp = compensate_2x if compensate_2x is not None else (quirks.get("requires_compensate_2x", False) if quirks else False)
            if compensate_2x is None and is_comp and quirks:
                console.print(f"[cyan]Auto-detected firmware ({quirks.get('firmware_version', '1.0')}): 2X clock divisor compensation active.[/cyan]")
            dev.apply_preset(preset, commit_flash=True, compensate_2x=is_comp)

        total_burns = tracker.record_commit(dev_key, preset_name=preset.get("name"))
        console.print(
            f"[bold green][OK] PEQ curve successfully burned to hardware NVRAM flash![/bold green] (Commit #{total_burns})\n"
            "[cyan]Settings are now non-volatile and will persist across unplugging, host swaps, and mobile devices.[/cyan]"
        )
    except DeviceSecurityException as e:
        console.print(f"[bold red][BLOCKED][/bold red] {e}")
        raise typer.Exit(code=2)
    except Exception as e:
        console.print(f"[bold red][ERROR][/bold red] Flashing failed: {e}")
        raise typer.Exit(code=1)


@app.command("read")
def cmd_read(
    vid: Optional[str] = typer.Option(None, "--vid", help="Target device Vendor ID (hex, e.g. 0x31B2)"),
    pid: Optional[str] = typer.Option(None, "--pid", help="Target device Product ID (hex, e.g. 0x0111)"),
    slot: Optional[int] = typer.Option(None, "--slot", "-s", min=1, max=4, help="Switch active hardware EQ memory slot (1-4) before reading"),
    compensate_2x: bool = typer.Option(False, "--compensate-2x", help="Compensate for older generic KT02H20 firmwares"),
    mock: bool = typer.Option(False, "--mock", help="Use software-emulated KT02H20 device for testing"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Optional path to save read PEQ state as JSON"),
):
    """Read active PEQ, preamp, and slot registers directly from hardware."""
    v_id = parse_hex_id(vid)
    p_id = parse_hex_id(pid)

    console.print("[bold cyan]Reading active DSP registers from hardware...[/bold cyan]")

    try:
        dev = get_dsp_device(vendor_id=v_id, product_id=p_id, use_mock=mock)
        with dev:
            if slot is not None and hasattr(dev, "_send_packet"):
                dev._send_packet(reg=dev.REG_SLOT, cmd=dev.CMD_WRITE, d0=slot)
            state = dev.read_current_peq(compensate_2x=compensate_2x)

        preamp = state.get("preamp", 0.0)
        slot = state.get("slot_id", 3)
        dac_filter = state.get("dac_filter", "FAST-LL")
        bands = state.get("bands", [])

        # Display Table
        table = Table(
            title=f"Hardware DSP State (Active Slot: {slot}, Preamp: {preamp:+.1f} dB, Filter: {dac_filter})",
            title_style="bold green",
        )
        table.add_column("Band", justify="center", style="cyan")
        table.add_column("Type", justify="center", style="magenta")
        table.add_column("Frequency (Hz)", justify="right", style="white")
        table.add_column("Gain (dB)", justify="right", style="yellow")
        table.add_column("Q Factor", justify="right", style="cyan")

        for b in bands:
            table.add_row(
                str(b["index"]),
                b["type"],
                f"{b['freq']:.1f}",
                f"{b['gain']:+.1f}",
                f"{b['q']:.2f}",
            )

        console.print(table)

        # Plot ASCII curve
        plot_str = render_ascii_frequency_response(bands, preamp)
        console.print(plot_str + "\n")

        if output:
            out_p = Path(output).expanduser()
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(json.dumps(state, indent=2), encoding="utf-8")
            console.print(f"[green]Saved hardware configuration to {out_p}[/green]")

    except DeviceSecurityException as e:
        console.print(f"[bold red][BLOCKED][/bold red] {e}")
        raise typer.Exit(code=2)
    except Exception as e:
        console.print(f"[bold red][ERROR][/bold red] Read failed: {e}")
        raise typer.Exit(code=1)


@app.command("filter")
def cmd_filter(
    filter_name: str = typer.Argument(
        ...,
        help="Reconstruction filter name: FAST-LL, FAST-PC, SLOW-LL, SLOW-PC, NON-OS",
    ),
    flash: bool = typer.Option(False, "--flash", "-f", help="Permanently commit filter selection to NVRAM"),
    vid: Optional[str] = typer.Option(None, "--vid", help="Target device Vendor ID (hex, e.g. 0x31B2)"),
    pid: Optional[str] = typer.Option(None, "--pid", help="Target device Product ID (hex, e.g. 0x0111)"),
    mock: bool = typer.Option(False, "--mock", help="Use software-emulated KT02H20 device for testing"),
):
    """Set the KT02H20 hardware DAC digital reconstruction filter."""
    v_id = parse_hex_id(vid)
    p_id = parse_hex_id(pid)
    filter_upper = filter_name.upper()

    try:
        dev = KTMicroDSPDevice(vendor_id=v_id, product_id=p_id, use_mock=mock)
        with dev:
            dev.set_dac_filter(filter_upper, commit_flash=flash)

        target_desc = "burned to NVRAM" if flash else "set in RAM"
        console.print(f"[bold green][OK] DAC reconstruction filter '{filter_upper}' successfully {target_desc}![/bold green]")
    except DeviceSecurityException as e:
        console.print(f"[bold red][BLOCKED][/bold red] {e}")
        raise typer.Exit(code=2)
    except Exception as e:
        console.print(f"[bold red][ERROR][/bold red] Setting filter failed: {e}")
        raise typer.Exit(code=1)


@app.command("flash-history")
def cmd_flash_history(
    clear: bool = typer.Option(False, "--clear", help="Clear flash commit wear-history log"),
    device_id: Optional[str] = typer.Option(None, "--device", "-d", help="Filter by device ID (e.g. 0x31B2:0x0111)"),
):
    """Inspect NVRAM flash endurance statistics and wear metrics."""
    tracker = FlashWearTracker()
    if clear:
        tracker.clear(device_id)
        target = f"for {device_id}" if device_id else "across all devices"
        console.print(f"[green]Flash commit history cleared {target}.[/green]")
        return

    devices = tracker.get_all_devices()
    if device_id:
        devices = [d for d in devices if d["device_id"] == device_id.lower()]

    if not devices:
        console.print("[yellow]No NVRAM flash commits logged yet.[/yellow]")
        return

    table = Table(title="Hardware NVRAM Flash Health & Wear Log", title_style="bold magenta")
    table.add_column("Device ID", style="cyan", no_wrap=True)
    table.add_column("Total Burns", justify="center", style="bold white")
    table.add_column("Burns (Last 24h)", justify="center")
    table.add_column("Last Preset", style="magenta")
    table.add_column("Last Flashed", style="dim")
    table.add_column("Silicon Status", justify="center")

    for d in devices:
        b_24h = d["last_24h_commits"]
        total = d["total_commits"]

        if b_24h >= 10 or total >= 50:
            status_style = "bold red"
            status_text = "⚠️ Wear Warning"
        elif b_24h >= 5:
            status_style = "yellow"
            status_text = "Moderate Wear"
        else:
            status_style = "green"
            status_text = "Healthy (Low Wear)"

        table.add_row(
            d["device_id"],
            str(total),
            f"[{ 'bold red' if b_24h >= 10 else ('yellow' if b_24h >= 5 else 'green') }]{b_24h}[/]",
            d["last_preset"] or "-",
            d["last_commit_time"] or "-",
            f"[{status_style}]{status_text}[/{status_style}]",
        )

    console.print(table)
    console.print(
        "\n[dim]Guidelines: Budget EEPROM chips typically guarantee 10k-100k cycles. "
        "Keep daily burns <10 to prevent premature sector fatigue.[/dim]"
    )


@app.command("export-pipewire")
def cmd_export_pipewire(
    preset_name: str = typer.Argument(..., help="Preset name or JSON file path"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Custom output path for PipeWire conf"),
    sink: str = typer.Option(DEFAULT_CX31993_SINK, "--sink", "-s", help="Target ALSA sink name"),
    install: bool = typer.Option(False, "--install", "-i", help="Install directly to ~/.config/pipewire/pipewire.conf.d/"),
    full_target: bool = typer.Option(False, "--full-target", "--10-band", help="Export full 10-band target profile instead of decimated hardware profile"),
):
    """Generate host-side PipeWire filter-chain configuration bound to JCALLY JM6 Pro (CX31993)."""
    preset = load_preset_data(preset_name)
    if full_target and preset.get("full_bands") and len(preset.get("full_bands")) > 5:
        preset = dict(preset)
        preset["bands"] = preset["full_bands"]
        console.print(f"[cyan]Exporting full-fidelity target profile ({len(preset['bands'])} bands).[/cyan]")

    preset_slug = preset.get("name", "custom").replace(" ", "_").replace("-", "_").lower()

    if install:
        dest_dir = Path.home() / ".config" / "pipewire" / "pipewire.conf.d"
        dest_dir.mkdir(parents=True, exist_ok=True)
        out_file = dest_dir / f"99-jm6pro-{preset_slug}.conf"
    elif output:
        out_file = Path(output).expanduser()
    else:
        out_file = Path(f"99-jm6pro-{preset_slug}.conf")

    written = export_pipewire_conf(preset, output_path=out_file, sink_target=sink)

    console.print(
        Panel(
            f"[bold green]PipeWire Filter-Chain Generated:[/bold green] [bold cyan]{written}[/bold cyan]\n"
            f"Preset: [bold]{preset.get('name')}[/bold] ({len(preset.get('bands', []))} Bands) | Target Sink: [yellow]{sink}[/yellow]\n\n"
            "[bold white]To activate with PipeWire:[/bold white]\n"
            f"  1. Ensure config is placed in [cyan]~/.config/pipewire/pipewire.conf.d/[/cyan]\n"
            "  2. Reload PipeWire: [cyan]systemctl --user restart pipewire[/cyan]\n"
            f"  3. Connect output or select [green]'JCALLY JM6 Pro DSP [{preset.get('name')}]'[/green] in Pavucontrol / WirePlumber.",
            title="JCALLY JM6 Pro Host DSP",
            border_style="green",
        )
    )


@app.command("export-apo")
def cmd_export_apo(
    preset_name: str = typer.Argument(..., help="Preset name or JSON file path"),
    output_dir: str = typer.Option("./exports", "--output-dir", "-o", help="Directory to save export files"),
    full_target: bool = typer.Option(False, "--full-target", "--10-band", help="Export full 10-band target profile instead of decimated hardware profile"),
):
    """Generate EqualizerAPO .txt and Wavelet (Android) profiles for JCALLY JM6 Pro."""
    preset = load_preset_data(preset_name)
    if full_target and preset.get("full_bands") and len(preset.get("full_bands")) > 5:
        preset = dict(preset)
        preset["bands"] = preset["full_bands"]
        console.print(f"[cyan]Exporting full-fidelity target profile ({len(preset['bands'])} bands).[/cyan]")

    results = export_apo_suite(preset, output_dir=output_dir)

    console.print(
        Panel(
            f"[bold green]Exported Host DSP Suite for:[/bold green] [bold cyan]{preset.get('name')}[/bold cyan] ({len(preset.get('bands', []))} Bands)\n\n"
            f"  * [bold]EqualizerAPO (.txt):[/bold] [cyan]{results['equalizer_apo']}[/cyan]\n"
            f"  * [bold]Wavelet GraphicEQ (.txt):[/bold] [cyan]{results['wavelet_txt']}[/cyan]\n"
            f"  * [bold]Wavelet JSON Profile:[/bold] [cyan]{results['wavelet_json']}[/cyan]\n\n"
            "[dim]EqualizerAPO: Import or Include in config.txt on Windows.\n"
            "Wavelet (Android): Import the GraphicEQ.txt via AutoEq -> Import in Wavelet.[/dim]",
            title="Universal Host DSP Exporter",
            border_style="green",
        )
    )


@app.command("udev")
def cmd_udev(
    install: bool = typer.Option(False, "--install", "-i", help="Install rules to /etc/udev/rules.d/ (requires sudo)"),
    print_rules: bool = typer.Option(False, "--print", "-p", help="Print rules to standard output"),
):
    """Manage Linux udev rules granting plugdev/uaccess to KTMicro DACs without sudo."""
    rules_content = """# /etc/udev/rules.d/99-ktmicro-dac.rules
# USB HID access permissions for KTMicro KT02H20 & WalkPlay DSP DACs
# (Kiwi Ears Allegro Mini, BASN BmasterX 6 Type-C Plug, FiiO JA11, JM12, etc.)
# Generated by dac-peq-manager

# KTMicro / Kiwi Ears Allegro Mini / JCALLY (0x31B2)
SUBSYSTEM=="usb", ATTR{idVendor}=="31b2", MODE="0666", TAG+="uaccess", GROUP="plugdev"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="31b2", MODE="0666", TAG+="uaccess", GROUP="plugdev"

# FiiO / JadeAudio JA11 (0x2972)
SUBSYSTEM=="usb", ATTR{idVendor}=="2972", MODE="0666", TAG+="uaccess", GROUP="plugdev"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="2972", MODE="0666", TAG+="uaccess", GROUP="plugdev"

# Realtek / WalkPlay OEM (0x0BDA:0x0023)
SUBSYSTEM=="usb", ATTR{idVendor}=="0bda", ATTR{idProduct}=="0023", MODE="0666", TAG+="uaccess", GROUP="plugdev"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="0023", MODE="0666", TAG+="uaccess", GROUP="plugdev"

# KTMicro OEM (0x0661)
SUBSYSTEM=="usb", ATTR{idVendor}=="0661", MODE="0666", TAG+="uaccess", GROUP="plugdev"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="0661", MODE="0666", TAG+="uaccess", GROUP="plugdev"

# WalkPlay OEM (0x262A)
SUBSYSTEM=="usb", ATTR{idVendor}=="262a", MODE="0666", TAG+="uaccess", GROUP="plugdev"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="262a", MODE="0666", TAG+="uaccess", GROUP="plugdev"
"""

    if print_rules or not install:
        console.print(rules_content)
        if not install:
            console.print("[dim]Use --install to write to /etc/udev/rules.d/99-ktmicro-dac.rules[/dim]")
            return

    if install:
        target_rule = Path("/etc/udev/rules.d/99-ktmicro-dac.rules")
        console.print(f"[bold cyan]Installing udev rules to {target_rule}...[/bold cyan]")
        try:
            target_rule.write_text(rules_content, encoding="utf-8")
        except PermissionError:
            proc = subprocess.run(
                ["sudo", "tee", str(target_rule)],
                input=rules_content.encode("utf-8"),
                capture_output=True,
            )
            if proc.returncode != 0:
                console.print(f"[bold red]Failed to install udev rules:[/bold red] {proc.stderr.decode()}")
                raise typer.Exit(code=1)

        console.print("[green][OK] Rules file written successfully.[/green]")
        console.print("[dim]Reloading udev rules with udevadm...[/dim]")
        subprocess.run(["sudo", "udevadm", "control", "--reload-rules"], check=False)
        subprocess.run(["sudo", "udevadm", "trigger"], check=False)
        console.print("[bold green][OK] udev rules reloaded. Re-plug your DAC to apply new permissions.[/bold green]")


@app.command("plot")
def cmd_plot(
    preset_name: str = typer.Argument(..., help="Preset name or JSON file path to visualize"),
    compare: Optional[str] = typer.Option(None, "--compare", "-c", help="Secondary preset name or JSON file to compare against"),
):
    """Render an ASCII/Unicode frequency response curve for a preset with optional acoustic delta comparison."""
    preset = load_preset_data(preset_name)
    bands = preset.get("bands", [])
    preamp_val = float(preset.get("preamp", 0.0))
    peak_gain = calculate_peak_composite_gain(bands)
    total_peak = peak_gain + preamp_val

    console.print(
        Panel(
            f"[bold cyan]{preset.get('name')}[/bold cyan]: {preset.get('description', '')}\n"
            f"Preamp: [yellow]{preamp_val:+.1f} dB[/yellow] | Peak Output: [{ 'bold red' if total_peak > 0 else 'green' }]{total_peak:+.1f} dBFS[/{ 'bold red' if total_peak > 0 else 'green' }]",
            title="Preset Response Plot",
            border_style="cyan",
        )
    )

    if total_peak > 0.0:
        rec = calculate_recommended_preamp(bands)
        console.print(
            f"[bold yellow][WARNING][/bold yellow] Peak output exceeds 0 dBFS ([bold red]{total_peak:+.1f} dB[/bold red]). "
            f"Intersample clipping may occur. Recommended preamp: [yellow]{rec:+.1f} dB[/yellow]."
        )

    # Acoustic Coupler Artifact Linter
    for w in lint_acoustic_bands(bands):
        console.print(f"[bold yellow][ACOUSTIC ADVICE][/bold yellow] {w}")

    # Optional Comparison with Secondary Preset / Target
    if compare:
        comp_preset = load_preset_data(compare)
        comp_bands = comp_preset.get("bands", [])
        comp_preamp = float(comp_preset.get("preamp", 0.0))
        diff = calculate_curve_difference(bands, preamp_val, comp_bands, comp_preamp)

        console.print(
            Panel(
                f"[bold]Reference Target:[/bold] [cyan]{comp_preset.get('name')}[/cyan]\n"
                f"RMS Difference: [bold yellow]±{diff['rms_db']:.1f} dB[/bold yellow] | "
                f"Peak Δ: [bold]{diff['max_diff_db']:+.1f} dB[/bold] @ {diff['max_diff_freq']:.0f} Hz | "
                f"Pinna Ear-Gain (2-4 kHz) RMS: [cyan]±{diff['pinna_rms_db']:.1f} dB[/cyan]",
                title="Acoustic Delta Comparison",
                border_style="yellow",
            )
        )

    plot_str = render_ascii_frequency_response(bands, preamp_val)
    console.print(plot_str)


# ── Database Command Group ────────────────────────────────────────────────────
db_app = typer.Typer(
    name="db",
    help="Query, search, and pull from 8,800+ community measurement databases (AutoEq & Squiglink)",
)
app.add_typer(db_app, name="db")


@db_app.command("search")
def cmd_db_search(
    query: str = typer.Argument(..., help="Search query (e.g. 'Aria', 'HD 600', 'EW300', 'Blessing')"),
    source: Optional[str] = typer.Option(None, "--source", "-s", help="Filter by measurement source/measurer"),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum number of results to display"),
    refresh: bool = typer.Option(False, "--refresh", "-r", help="Force refresh index from GitHub"),
):
    """Search 8,800+ headphone & IEM models in the community measurement database."""
    db = AutoEqDatabase()
    with console.status("[bold cyan]Searching community databases...[/bold cyan]"):
        try:
            results = db.search(query, source=source, limit=limit)
        except Exception as e:
            console.print(f"[bold red]Failed to fetch database index:[/bold red] {e}")
            raise typer.Exit(code=1)

    if not results:
        console.print(f"[yellow]No models found matching '[bold]{query}[/bold]'. Try broader terms.[/yellow]")
        return

    table = Table(title=f"AutoEq & Squiglink Database Search: '{query}' ({len(results)} shown)")
    table.add_column("#", style="dim", width=4)
    table.add_column("Model Name", style="bold cyan")
    table.add_column("Measurer / Rig", style="magenta")
    table.add_column("Repository Path", style="dim")

    for i, r in enumerate(results, 1):
        table.add_row(str(i), r.name, r.source, r.clean_path)

    console.print(table)
    console.print("\n[dim]To pull and audition a preset: [cyan]dac-peq-manager db pull \"<Model Name>\" --plot[/cyan][/dim]")


@db_app.command("sources")
def cmd_db_sources(
    refresh: bool = typer.Option(False, "--refresh", "-r", help="Force refresh index from GitHub"),
):
    """List all measurement sources (Crinacle, Oratory1990, Super Review, Rtings) and counts."""
    db = AutoEqDatabase()
    with console.status("[bold cyan]Querying measurement sources...[/bold cyan]"):
        try:
            db.fetch_index(force_refresh=refresh)
            sources = db.list_sources()
        except Exception as e:
            console.print(f"[bold red]Failed to load sources:[/bold red] {e}")
            raise typer.Exit(code=1)

    table = Table(title=f"Community Measurement Sources ({len(sources)} labs/reviewers)")
    table.add_column("Measurement Source / Lab", style="bold cyan")
    table.add_column("Indexed Profiles", justify="right", style="green")

    for src, count in sources:
        table.add_row(src, str(count))

    console.print(table)


@db_app.command("update")
def cmd_db_update():
    """Force download and cache the latest AutoEq & Squiglink measurement database index."""
    db = AutoEqDatabase()
    with console.status("[bold cyan]Updating local measurement index cache from GitHub...[/bold cyan]"):
        try:
            entries = db.fetch_index(force_refresh=True)
            console.print(
                f"[bold green][OK] Successfully updated database cache.[/bold green] "
                f"[cyan]{len(entries):,}[/cyan] headphone/IEM profiles indexed."
            )
        except Exception as e:
            console.print(f"[bold red]Update failed:[/bold red] {e}")
            raise typer.Exit(code=1)


@db_app.command("pull")
def cmd_db_pull(
    query: str = typer.Argument(..., help="Model name or search query (e.g. 'Moondrop Aria', 'HD 600')"),
    source: Optional[str] = typer.Option(None, "--source", "-s", help="Filter by measurement source"),
    apply: bool = typer.Option(False, "--apply", "-a", help="Immediately write PEQ to live DSP RAM on connected DAC"),
    flash: bool = typer.Option(False, "--flash", "-f", help="Immediately commit PEQ to persistent NVRAM flash"),
    bands_qty: int = typer.Option(5, "--bands", "-b", help="Target number of PEQ bands (e.g. 5 for KTMicro, 9 for FreeDSP, or 10 for Host DSP)"),
    auto_preamp: bool = typer.Option(False, "--auto-preamp", help="Automatically calculate negative preamp with 0.5dB intersample headroom"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Confirm writing to hardware NVRAM flash without interactive prompt"),
    save: bool = typer.Option(True, "--save/--no-save", help="Save preset JSON file locally to presets/ directory"),
    plot: bool = typer.Option(True, "--plot/--no-plot", help="Render ASCII frequency response curve"),
    compensate_2x: bool = typer.Option(False, "--compensate-2x", help="Compensate for 2x clock divisor bug on older KT02H20 firmwares"),
    vid: Optional[str] = typer.Option(None, "--vid", help="Optional USB Vendor ID in hex"),
    pid: Optional[str] = typer.Option(None, "--pid", help="Optional USB Product ID in hex"),
):
    """Pull PEQ profile directly from AutoEq into live RAM, NVRAM flash, or presets."""
    db = AutoEqDatabase()
    with console.status(f"[bold cyan]Searching database for '{query}'...[/bold cyan]"):
        results = db.search(query, source=source, limit=5)

    if not results:
        console.print(f"[bold red]No matching model found for '{query}'.[/bold red]")
        raise typer.Exit(code=1)

    selected = results[0]
    console.print(f"[green]Selected: [bold]{selected.name}[/bold] by [magenta]{selected.source}[/magenta][/green]")

    # Hardware Band Limit Validation
    target_bands = bands_qty
    if apply or flash:
        allowed, warn_msg = validate_hardware_bands(target_bands, "ktmicro_dsp")
        if warn_msg:
            console.print(f"[bold yellow][HARDWARE BAND LIMIT][/bold yellow] {warn_msg}")
        target_bands = allowed

    with console.status(f"[bold cyan]Downloading and processing {target_bands}-band PEQ parameters...[/bold cyan]"):
        try:
            preset_data = db.pull_preset(selected, target_bands=target_bands)
        except Exception as e:
            console.print(f"[bold red]Failed to parse preset for '{selected.name}':[/bold red] {e}")
            raise typer.Exit(code=1)

    bands = preset_data.get("bands", [])
    if auto_preamp:
        rec_preamp = calculate_recommended_preamp(bands)
        preset_data["preamp"] = rec_preamp
        console.print(f"[cyan]Auto-Preamp set to:[/cyan] [bold yellow]{rec_preamp:+.1f} dB[/bold yellow] (0.5 dB intersample headroom)")
    else:
        peak_gain = calculate_peak_composite_gain(bands)
        total_peak = peak_gain + float(preset_data.get("preamp", 0.0))
        if total_peak > 0.0:
            rec = calculate_recommended_preamp(bands)
            console.print(
                f"[bold yellow][WARNING][/bold yellow] Peak composite gain is [bold red]{total_peak:+.1f} dB[/bold red] (exceeds 0 dBFS).\n"
                f"[dim]Intersample clipping may occur during DAC reconstruction. Use '--auto-preamp' to apply recommended preamp ({rec:+.1f} dB).[/dim]"
            )

    # Acoustic Coupler Artifact Linter
    acoustic_warnings = lint_acoustic_bands(bands)
    for w in acoustic_warnings:
        console.print(f"[bold yellow][ACOUSTIC ADVICE][/bold yellow] {w}")

    # 1. Save if requested
    saved_path = None
    if save:
        saved_path = db.save_preset(preset_data)
        console.print(f"[dim]Saved local preset to: {saved_path}[/dim]")

    # 2. Render plot if requested
    if plot:
        preamp_val = float(preset_data.get("preamp", 0.0))
        peak_gain = calculate_peak_composite_gain(bands)
        total_peak = peak_gain + preamp_val
        console.print(
            Panel(
                f"[bold cyan]{preset_data.get('name')}[/bold cyan]: {preset_data.get('description', '')}\n"
                f"Preamp: [yellow]{preamp_val:+.1f} dB[/yellow] | Peak Output: [{ 'bold red' if total_peak > 0 else 'green' }]{total_peak:+.1f} dBFS[/{ 'bold red' if total_peak > 0 else 'green' }]",
                title="Pulled Community Preset",
                border_style="cyan",
            )
        )

        full_bands = preset_data.get("full_bands", [])
        if len(full_bands) > len(bands):
            diff = calculate_curve_difference(bands, preamp_val, full_bands, preamp_val)
            console.print(
                f"[cyan]Landmark Decimation Fidelity ({len(full_bands)} -> {len(bands)} bands):[/cyan] "
                f"RMS Difference: [green]±{diff['rms_db']:.1f} dB[/green] "
                f"(Peak Δ: {diff['max_diff_db']:+.1f} dB @ {diff['max_diff_freq']:.0f} Hz | Pinna 2-4kHz RMS: ±{diff['pinna_rms_db']:.1f} dB)\n"
            )

        plot_str = render_ascii_frequency_response(bands, preamp_val)
        console.print(plot_str)

    # 3. Apply to live RAM or Flash if requested
    if apply or flash:
        vid_int = parse_hex_id(vid)
        pid_int = parse_hex_id(pid)

        if flash and not yes:
            confirm = typer.confirm(
                "⚠️  NVRAM Flash commits permanently to onboard physical flash memory (~10k-100k cycle endurance). Commit settings now?",
                default=True,
            )
            if not confirm:
                console.print("[dim]Flash commit cancelled by user.[/dim]")
                raise typer.Exit(code=0)

        dev = get_dsp_device(vendor_id=vid_int, product_id=pid_int)

        try:
            with dev:
                if flash:
                    console.print(f"[bold yellow]Burning {len(preset_data.get('bands', []))}-band PEQ directly into NVRAM flash...[/bold yellow]")
                    dev.apply_preset(preset_data, commit_flash=True, compensate_2x=compensate_2x)
                    console.print("[bold green][OK] PEQ burned to hardware NVRAM! Settings will persist across host swaps.[/bold green]")
                else:
                    console.print(f"[bold cyan]Applying {len(preset_data.get('bands', []))}-band PEQ to live DSP RAM (instant listening)...[/bold cyan]")
                    dev.apply_preset(preset_data, commit_flash=False, compensate_2x=compensate_2x)
                    console.print("[bold green][OK] PEQ active in live DSP RAM.[/bold green]")
        except DeviceSecurityException as sec_err:
            console.print(f"\n[bold red][BLOCKED][/bold red] {sec_err}")
            raise typer.Exit(code=1)
        except DeviceCommunicationError as comm_err:
            console.print(f"[bold red]Communication error:[/bold red] {comm_err}")
            raise typer.Exit(code=1)


# ── DAC Directory & Hardware Compatibility Database ───────────────────────────
dacs_app = typer.Typer(
    name="dacs",
    help="Catalog of known USB DAC dongles, chipsets, and hardware flash compatibility",
)
app.add_typer(dacs_app, name="dacs")


@dacs_app.command("list")
def cmd_dacs_list(
    flashable_only: bool = typer.Option(False, "--flashable", "-f", help="List only hardware-flashable KTMicro/WalkPlay DSP devices"),
):
    """List all catalogued USB audio DAC dongles and their architecture."""
    db = DACDatabase()
    dacs = db.list_flashable() if flashable_only else db.all()

    title = "Hardware Flashable DACs (KTMicro / WalkPlay)" if flashable_only else f"USB DAC Hardware Compatibility Database ({len(dacs)} devices)"
    table = Table(title=title, title_style="bold cyan")
    table.add_column("Device Name", style="bold white")
    table.add_column("Brand", style="cyan")
    table.add_column("Internal Chipset", style="magenta")
    table.add_column("Resolution", style="dim")
    table.add_column("HW Flash?", justify="center")
    table.add_column("Recommended DSP Action", style="green")

    for d in dacs:
        if d.is_hardware_flashable:
            flash_badge = "[bold green]YES[/bold green]"
            action_desc = "[green]Direct 5-band NVRAM flash (apply / flash)[/green]"
        elif d.is_fixed_mask_rom:
            flash_badge = "[bold red]BLOCKED[/bold red]"
            action_desc = "[yellow]Fixed Mask ROM. Host DSP (PipeWire / Wavelet)[/yellow]"
        else:
            flash_badge = "[dim]No[/dim]"
            action_desc = "[cyan]Host DSP Only (PipeWire / Wavelet / APO)[/cyan]"

        table.add_row(
            d.name,
            d.brand,
            d.chipset,
            d.resolution,
            flash_badge,
            action_desc,
        )

    console.print(table)
    console.print("\n[dim]To inspect a specific DAC: [cyan]dac-peq-manager dacs info <model_id>[/cyan][/dim]")


@dacs_app.command("search")
def cmd_dacs_search(
    query: str = typer.Argument(..., help="Search query (e.g. 'CableCreation', 'CX31993', 'Allegro', 'JA11', 'CS43131')"),
    flashable_only: bool = typer.Option(False, "--flashable", "-f", help="List only hardware-flashable devices"),
):
    """Search catalogued DAC devices by name, brand, or chipset."""
    db = DACDatabase()
    results = db.search(query, flashable_only=flashable_only)

    if not results:
        console.print(f"[yellow]No DACs found matching '[bold]{query}[/bold]'.[/yellow]")
        return

    table = Table(title=f"DAC Database Search: '{query}' ({len(results)} found)", title_style="bold cyan")
    table.add_column("ID", style="dim")
    table.add_column("Device Name", style="bold white")
    table.add_column("Brand", style="cyan")
    table.add_column("Internal Chipset", style="magenta")
    table.add_column("HW Flash?", justify="center")

    for d in results:
        flash_badge = "[bold green]YES[/bold green]" if d.is_hardware_flashable else ("[bold red]BLOCKED[/bold red]" if d.is_fixed_mask_rom else "[dim]No[/dim]")
        table.add_row(d.id, d.name, d.brand, d.chipset, flash_badge)

    console.print(table)


@dacs_app.command("info")
def cmd_dacs_info(
    model_id_or_query: str = typer.Argument(..., help="DAC model ID or search term (e.g. 'allegro_mini', 'jcally_jm6_pro', 'cablecreation_2in1')"),
):
    """Display comprehensive technical specifications and DSP guidance for a DAC."""
    db = DACDatabase()
    matched = None
    for d in db.all():
        if d.id.lower() == model_id_or_query.lower():
            matched = d
            break

    if not matched:
        results = db.search(model_id_or_query)
        if results:
            matched = results[0]

    if not matched:
        console.print(f"[bold red]DAC '{model_id_or_query}' not found in database.[/bold red]")
        raise typer.Exit(code=1)

    flash_status = "[bold green]Supported (5-Band Hardware Biquad NVRAM)[/bold green]" if matched.is_hardware_flashable else (
        "[bold red]BLOCKED (Fixed Mask ROM / OTP Descriptors)[/bold red]" if matched.is_fixed_mask_rom else "[dim]Host DSP Only[/dim]"
    )

    quirks_str = ", ".join(matched.quirks) if matched.quirks else "None"
    outputs_str = ", ".join(matched.outputs) if matched.outputs else "-"

    panel_text = (
        f"[bold cyan]Device:[/bold cyan] {matched.name} ([magenta]{matched.brand}[/magenta])\n"
        f"[bold cyan]Internal Chipset:[/bold cyan] {matched.chipset}\n"
        f"[bold cyan]Architecture:[/bold cyan] {matched.architecture}\n"
        f"[bold cyan]USB VID:PID:[/bold cyan] {matched.vid_hex or '-'}:{matched.pid_hex or '-'}\n"
        f"[bold cyan]Max Resolution:[/bold cyan] {matched.resolution}\n"
        f"[bold cyan]Output Power:[/bold cyan] {matched.output_power}\n"
        f"[bold cyan]Physical Outputs:[/bold cyan] {outputs_str}\n"
        f"[bold cyan]TRRS Inline Mic:[/bold cyan] {'Supported' if matched.trrs_mic else 'No'}\n"
        f"[bold cyan]Hardware PEQ Flash:[/bold cyan] {flash_status}\n"
        f"[bold cyan]Known Quirks:[/bold cyan] {quirks_str}\n\n"
        f"[bold yellow]Recommendation:[/bold yellow]\n{matched.recommendation}"
    )

    console.print(Panel(panel_text, title=f"DAC Hardware Profile: {matched.name}", border_style="cyan"))


def main():
    app()


if __name__ == "__main__":
    main()
