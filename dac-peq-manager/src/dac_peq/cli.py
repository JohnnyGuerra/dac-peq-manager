"""CLI Interface for dac-peq-manager.

Provides commands:
  - scan: Enumerate and identify USB audio DACs (KTMicro, Conexant CX31993, etc.)
  - apply: Write 5-band PEQ and preamp into live DSP RAM (instant listening)
  - flash: Write 5-band PEQ and preamp to RAM and commit to NVRAM (permanent)
  - read: Read active 5-band PEQ and preamp registers from hardware
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

from dac_peq.biquad import render_ascii_frequency_response
from dac_peq.exporters import (
    DEFAULT_CX31993_SINK,
    export_apo_suite,
    export_pipewire_conf,
    format_pipewire_filter_chain,
)
from dac_peq.ktmicro_hid import (
    DeviceCommunicationError,
    DeviceSecurityException,
    KTMicroDSPDevice,
    scan_devices,
)

app = typer.Typer(
    name="dac-peq-manager",
    help="Hardware DSP Flasher & Host PEQ Suite for Portable USB-C DACs & Tribrid IEMs",
    add_completion=False,
)
console = Console()


def get_presets_dir() -> Path:
    """Return path to presets directory."""
    # Check package location or workspace location
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
    """Load preset by name (e.g. 'bmasterx6', 'ew300-silver') or from JSON file."""
    p_path = Path(preset_name_or_path)
    if p_path.is_file():
        try:
            return json.loads(p_path.read_text(encoding="utf-8"))
        except Exception as e:
            console.print(f"[bold red]Error reading preset file {p_path}:[/bold red] {e}")
            raise typer.Exit(code=1)

    # Normalize name variations
    norm = preset_name_or_path.lower().replace("_", "-")
    presets_dir = get_presets_dir()

    candidates = [
        presets_dir / f"{preset_name_or_path}.json",
        presets_dir / f"{norm}.json",
        presets_dir / f"{norm.replace('-', '_')}.json",
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

    if not devices:
        console.print("[yellow]No USB HID devices detected on this system.[/yellow]")
        return

    table = Table(title="Detected USB HID Audio & DSP Endpoints", title_style="bold magenta")
    table.add_column("VID:PID", style="cyan", no_wrap=True)
    table.add_column("Manufacturer", style="white")
    table.add_column("Product", style="bold white")
    table.add_column("Serial / Path", style="dim")
    table.add_column("Capabilities & Action", style="green")

    for d in devices:
        status_color = "green" if d.is_ktmicro else ("yellow" if d.is_conexant else "dim")
        table.add_row(
            d.vid_pid_hex,
            d.manufacturer_string or "-",
            d.product_string or "Unknown",
            d.serial_number or str(d.path[:12] if isinstance(d.path, bytes) else d.path),
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
    mock: bool = typer.Option(False, "--mock", help="Use software-emulated KT02H20 device for testing"),
):
    """Write 5-band PEQ and preamp into live DSP RAM (instant listening, temporary)."""
    preset = load_preset_data(preset_name)
    v_id = parse_hex_id(vid)
    p_id = parse_hex_id(pid)

    console.print(
        Panel(
            f"[bold green]Applying Preset:[/bold green] [bold cyan]{preset.get('name')}[/bold cyan]\n"
            f"[dim]{preset.get('description', '')}[/dim]\n"
            f"Global Preamp: [yellow]{preset.get('preamp', 0.0):+.1f} dB[/yellow] | Mode: [bold]Live RAM Write[/bold] (Instant listen)",
            title="KTMicro Live DSP Config",
            border_style="green",
        )
    )

    # Display ASCII frequency response plot
    plot_str = render_ascii_frequency_response(preset.get("bands", []), float(preset.get("preamp", 0.0)))
    console.print(plot_str + "\n")

    try:
        dev = KTMicroDSPDevice(vendor_id=v_id, product_id=p_id, use_mock=mock)
        with dev:
            dev.apply_preset(preset, commit_flash=False)

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
    mock: bool = typer.Option(False, "--mock", help="Use software-emulated KT02H20 device for testing"),
):
    """Write 5-band PEQ and commit directly to onboard NVRAM (permanent flash)."""
    preset = load_preset_data(preset_name)
    v_id = parse_hex_id(vid)
    p_id = parse_hex_id(pid)

    console.print(
        Panel(
            f"[bold magenta]Flashing Preset to NVRAM:[/bold magenta] [bold cyan]{preset.get('name')}[/bold cyan]\n"
            f"[dim]{preset.get('description', '')}[/dim]\n"
            f"Global Preamp: [yellow]{preset.get('preamp', 0.0):+.1f} dB[/yellow] | Mode: [bold red]NVRAM Burn (0x53 Commit)[/bold red]",
            title="KTMicro Hardware NVRAM Flasher",
            border_style="magenta",
        )
    )

    plot_str = render_ascii_frequency_response(preset.get("bands", []), float(preset.get("preamp", 0.0)))
    console.print(plot_str + "\n")

    try:
        dev = KTMicroDSPDevice(vendor_id=v_id, product_id=p_id, use_mock=mock)
        with dev:
            dev.apply_preset(preset, commit_flash=True)

        console.print(
            "[bold green][OK] PEQ curve successfully burned to hardware NVRAM flash![/bold green]\n"
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
    mock: bool = typer.Option(False, "--mock", help="Use software-emulated KT02H20 device for testing"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Optional path to save read PEQ state as JSON"),
):
    """Read active 5-band PEQ, preamp, and slot registers directly from hardware."""
    v_id = parse_hex_id(vid)
    p_id = parse_hex_id(pid)

    console.print("[bold cyan]Reading active DSP registers from hardware...[/bold cyan]")

    try:
        dev = KTMicroDSPDevice(vendor_id=v_id, product_id=p_id, use_mock=mock)
        with dev:
            state = dev.read_current_peq()

        preamp = state.get("preamp", 0.0)
        slot = state.get("slot_id", 3)
        bands = state.get("bands", [])

        # Display Table
        table = Table(title=f"Hardware DSP State (Active Slot: {slot}, Preamp: {preamp:+.1f} dB)", title_style="bold green")
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


@app.command("export-pipewire")
def cmd_export_pipewire(
    preset_name: str = typer.Argument(..., help="Preset name or JSON file path"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Custom output path for PipeWire conf"),
    sink: str = typer.Option(DEFAULT_CX31993_SINK, "--sink", "-s", help="Target ALSA sink name"),
    install: bool = typer.Option(False, "--install", "-i", help="Install directly to ~/.config/pipewire/pipewire.conf.d/"),
):
    """Generate host-side PipeWire filter-chain configuration bound to JCALLY JM6 Pro (CX31993)."""
    preset = load_preset_data(preset_name)
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
            f"Preset: [bold]{preset.get('name')}[/bold] | Target Sink: [yellow]{sink}[/yellow]\n\n"
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
):
    """Generate EqualizerAPO .txt and Wavelet (Android) profiles for JCALLY JM6 Pro."""
    preset = load_preset_data(preset_name)
    results = export_apo_suite(preset, output_dir=output_dir)

    console.print(
        Panel(
            f"[bold green]Exported Host DSP Suite for:[/bold green] [bold cyan]{preset.get('name')}[/bold cyan]\n\n"
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
            # Try writing directly
            target_rule.write_text(rules_content, encoding="utf-8")
        except PermissionError:
            # Use sudo
            proc = subprocess.run(
                ["sudo", "tee", str(target_rule)],
                input=rules_content.encode("utf-8"),
                capture_output=True,
            )
            if proc.returncode != 0:
                console.print(f"[bold red]Failed to install udev rules:[/bold red] {proc.stderr.decode()}")
                raise typer.Exit(code=1)

        console.print("[green][OK] Rules file written successfully.[/green]")

        # Reload udev rules
        console.print("[dim]Reloading udev rules with udevadm...[/dim]")
        subprocess.run(["sudo", "udevadm", "control", "--reload-rules"], check=False)
        subprocess.run(["sudo", "udevadm", "trigger"], check=False)
        console.print("[bold green][OK] udev rules reloaded. Re-plug your DAC to apply new permissions.[/bold green]")


@app.command("plot")
def cmd_plot(
    preset_name: str = typer.Argument(..., help="Preset name or JSON file path to visualize"),
):
    """Render an ASCII/Unicode frequency response curve for a preset."""
    preset = load_preset_data(preset_name)
    console.print(
        Panel(
            f"[bold cyan]{preset.get('name')}[/bold cyan]: {preset.get('description', '')}\n"
            f"Preamp: [yellow]{preset.get('preamp', 0.0):+.1f} dB[/yellow]",
            title="Preset Response Plot",
            border_style="cyan",
        )
    )
    plot_str = render_ascii_frequency_response(preset.get("bands", []), float(preset.get("preamp", 0.0)))
    console.print(plot_str)


def main():
    app()


if __name__ == "__main__":
    main()
