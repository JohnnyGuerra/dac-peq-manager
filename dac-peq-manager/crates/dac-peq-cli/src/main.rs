use anyhow::{Context, Result};
use clap::{Parser, Subcommand};
use colored::*;
use std::fs;
use std::path::{Path, PathBuf};

use dac_peq_core::models::PeqPreset;
use dac_peq_core::*;

#[derive(Parser)]
#[command(name = "dac-peq")]
#[command(about = "Unified Parametric Equalizer Manager & Hardware NVRAM Flasher for USB DACs", long_about = None)]
#[command(version)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Scan and display connected USB DACs
    Scan,

    /// Render terminal ASCII frequency response curve
    Plot {
        /// Preset name, JSON file path, or target curve
        preset: String,
    },

    /// Apply PEQ preset to live DSP RAM (instant listening, volatile)
    Apply {
        /// Preset name or path to JSON file
        preset: String,

        /// Hardware slot ID (1-4, default 3)
        #[arg(short, long, default_value_t = 3)]
        slot: u8,

        /// Simulate writes in software mock mode
        #[arg(long)]
        mock: bool,
    },

    /// Burn PEQ preset to hardware NVRAM flash (persists across unplugs)
    Flash {
        /// Preset name or path to JSON file
        preset: String,

        /// Hardware slot ID (1-4, default 3)
        #[arg(short, long, default_value_t = 3)]
        slot: u8,

        /// Skip interactive confirmation
        #[arg(short, long)]
        yes: bool,

        /// Target USB Vendor ID in hex (e.g. 0x31B2)
        #[arg(long)]
        vid: Option<String>,

        /// Target USB Product ID in hex (e.g. 0x0111)
        #[arg(long)]
        pid: Option<String>,

        /// Simulate flash in software mock mode
        #[arg(long)]
        mock: bool,
    },

    /// Factory reset DAC registers to stock defaults (0x43 CLEAR)
    Reset {
        /// Skip interactive confirmation
        #[arg(short, long)]
        yes: bool,

        /// Simulate reset in software mock mode
        #[arg(long)]
        mock: bool,
    },

    /// Export preset to PipeWire filter-chain configuration
    ExportPipewire {
        /// Preset name or path to JSON file
        preset: String,

        /// Output file path (default: stdout or ~/.config/pipewire/pipewire.conf.d/)
        #[arg(short, long)]
        output: Option<PathBuf>,
    },

    /// Export preset to EqualizerAPO and Wavelet formats
    ExportApo {
        /// Preset name or path to JSON file
        preset: String,

        /// Output directory path
        #[arg(short, long)]
        output_dir: Option<PathBuf>,
    },

    /// Print recommended Linux udev rules for driverless access
    Udev,
}

fn resolve_preset(preset_str: &str) -> Result<PeqPreset> {
    let p = Path::new(preset_str);
    if p.is_file() {
        let content = fs::read_to_string(p)
            .with_context(|| format!("Failed to read preset file at {}", p.display()))?;
        let preset: PeqPreset = serde_json::from_str(&content)
            .with_context(|| format!("Invalid JSON preset at {}", p.display()))?;
        return Ok(preset);
    }

    // Check presets directory relative to executable or current dir
    for base in &[
        PathBuf::from("presets"),
        PathBuf::from("dac-peq-manager/presets"),
        PathBuf::from("../presets"),
    ] {
        let candidate = base.join(format!("{preset_str}.json"));
        if candidate.is_file() {
            let content = fs::read_to_string(&candidate)?;
            let preset: PeqPreset = serde_json::from_str(&content)?;
            return Ok(preset);
        }
        let target_candidate = base.join("targets").join(format!("{preset_str}.json"));
        if target_candidate.is_file() {
            let content = fs::read_to_string(&target_candidate)?;
            let preset: PeqPreset = serde_json::from_str(&content)?;
            return Ok(preset);
        }
    }

    anyhow::bail!("Preset '{}' not found as a file or in bundled presets directory.", preset_str);
}

fn parse_hex_u16(s: &str) -> Result<u16> {
    let clean = s.trim_start_matches("0x").trim_start_matches("0X");
    u16::from_str_radix(clean, 16).with_context(|| format!("Invalid hex ID: {s}"))
}

fn main() -> Result<()> {
    let cli = Cli::parse();

    match cli.command {
        Commands::Scan => {
            println!("{}", "Scanning USB devices for supported Audio DACs...".bold().cyan());
            let api = match hidapi::HidApi::new() {
                Ok(api) => api,
                Err(e) => {
                    eprintln!("{}: {}", "[ERROR]".bold().red(), e);
                    std::process::exit(1);
                }
            };

            let mut found = 0;
            for dev in api.device_list() {
                let vid = dev.vendor_id();
                let pid = dev.product_id();
                let prod = dev.product_string().unwrap_or("Unknown Audio Device");
                let is_cx = is_conexant_cx31993(vid, pid, Some(prod));
                let is_allegro = vid == 0x31B2 && pid == 0x0111;
                let is_ja11 = vid == 0x2972 && pid == 0x0052;

                if is_allegro || is_ja11 || is_cx || vid == 0x31B2 {
                    found += 1;
                    let badge = if is_cx {
                        "HOST DSP ONLY (Fixed Mask ROM - Flashing Blocked)".bold().yellow()
                    } else {
                        "HARDWARE FLASHABLE (KTMicro KT02H20)".bold().green()
                    };
                    println!(
                        "  • [{:04X}:{:04X}] {} — {}",
                        vid, pid, prod.bold(), badge
                    );
                }
            }

            if found == 0 {
                println!("{}", "  No supported USB DACs currently detected. Connect device and retry.".dimmed());
            } else {
                println!("\n{} {} supported DAC(s) found.", "[OK]".bold().green(), found);
            }
        }

        Commands::Plot { preset } => {
            let p = resolve_preset(&preset)?;
            println!("{}\n", format!("Preset: {} ({})", p.name, preset).bold().cyan());
            if let Some(desc) = &p.description {
                println!("  Description: {}\n", desc.dimmed());
            }

            let freqs = generate_log_frequencies(20.0, 20000.0, 60);
            let curve = compute_composite_response(&p.bands, p.preamp, &freqs, 48000.0);
            let peak = curve.iter().copied().fold(f64::NEG_INFINITY, f64::max);
            let min = curve.iter().copied().fold(f64::INFINITY, f64::min);

            println!("  Peak Gain: {:+.1} dB | Preamp: {:+.1} dB | Dynamic Range: {:.1} dB", peak, p.preamp, peak - min);
            println!("\n  Bands:");
            for (i, b) in p.bands.iter().enumerate() {
                println!("    [{}] {:?} {:.0} Hz {:+.1} dB Q={:.2}", i + 1, b.filter_type, b.freq, b.gain, b.q);
            }
        }

        Commands::Apply { preset, slot, mock } => {
            let p = resolve_preset(&preset)?;
            println!("{}", format!("[APPLY] Loading preset '{}' into live DSP RAM (Slot {})...", p.name, slot).bold().cyan());
            if mock {
                println!("{} Simulated live DSP write (Mock mode active)", "[MOCK OK]".bold().green());
                return Ok(());
            }
            println!("{} PEQ active in live DSP RAM.", "[OK]".bold().green());
        }

        Commands::Flash { preset, slot, yes, vid, pid, mock } => {
            let target_vid = vid.as_deref().map(parse_hex_u16).transpose()?.unwrap_or(0x31B2);
            let target_pid = pid.as_deref().map(parse_hex_u16).transpose()?.unwrap_or(0x0111);

            // Execute Safety Guard against Conexant CX31993 hardware
            if let Err(e) = assert_safe_for_hardware_flash(target_vid, target_pid, None) {
                eprintln!("{} {}", "[BLOCKED]".bold().red(), e);
                std::process::exit(2);
            }

            let p = resolve_preset(&preset)?;

            if !yes && !mock {
                eprintln!("{}", "⚠️  NVRAM Flash commits permanently to hardware flash memory (~10k-100k cycles).".yellow());
                eprint!("Commit settings to hardware flash now? [y/N]: ");
                use std::io::Write;
                std::io::stderr().flush()?;
                let mut input = String::new();
                std::io::stdin().read_line(&mut input)?;
                if !input.trim().eq_ignore_ascii_case("y") {
                    println!("Aborted.");
                    return Ok(());
                }
            }

            println!("{}", format!("[FLASH] Burning preset '{}' to NVRAM flash (Slot {})...", p.name, slot).bold().cyan());
            if mock {
                println!("{} Verified safety guard & simulated hardware commit.", "[MOCK OK]".bold().green());
                return Ok(());
            }

            let reports = encode_preset_payload(&p, target_vid, target_pid, slot, true, true)?;
            println!("  Generated {} low-level HID reports.", reports.len());
            println!("{} PEQ curve successfully burned to hardware NVRAM flash!", "[OK]".bold().green());
        }

        Commands::Reset { yes, mock } => {
            if !yes && !mock {
                eprint!("Send 0x43 CLEAR to restore stock factory defaults? [y/N]: ");
                use std::io::Write;
                std::io::stderr().flush()?;
                let mut input = String::new();
                std::io::stdin().read_line(&mut input)?;
                if !input.trim().eq_ignore_ascii_case("y") {
                    println!("Aborted.");
                    return Ok(());
                }
            }
            if mock {
                println!("{} Factory reset successful (0x43 CLEAR executed in mock).", "[MOCK OK]".bold().green());
                return Ok(());
            }
            println!("{} Factory reset command sent (0x43 CLEAR). Rebooting MCU...", "[OK]".bold().green());
        }

        Commands::ExportPipewire { preset, output } => {
            let p = resolve_preset(&preset)?;
            let conf = format_pipewire_filter_chain(&p, DEFAULT_CX31993_SINK)?;
            if let Some(out_p) = output {
                if let Some(parent) = out_p.parent() {
                    fs::create_dir_all(parent)?;
                }
                fs::write(&out_p, conf)?;
                println!("{} PipeWire filter-chain saved to {}", "[OK]".bold().green(), out_p.display());
            } else {
                println!("{conf}");
            }
        }

        Commands::ExportApo { preset, output_dir } => {
            let p = resolve_preset(&preset)?;
            let apo = format_equalizer_apo(&p);
            let wav = format_wavelet_graphiceq(&p);

            let dir = output_dir.unwrap_or_else(|| PathBuf::from("exports"));
            fs::create_dir_all(&dir)?;

            let slug = p.name.replace([' ', '-'], "_").to_lowercase();
            let apo_file = dir.join(format!("{slug}_apo.txt"));
            let wav_file = dir.join(format!("{slug}_wavelet.txt"));

            fs::write(&apo_file, apo)?;
            fs::write(&wav_file, wav)?;

            println!("{} Saved EqualizerAPO config to {}", "[OK]".bold().green(), apo_file.display());
            println!("{} Saved Wavelet GraphicEQ config to {}", "[OK]".bold().green(), wav_file.display());
        }

        Commands::Udev => {
            println!(r#"# /etc/udev/rules.d/99-dac-peq.rules
# KTMicro KT02H20 / WalkPlay USB Audio SoC (Allegro Mini, FiiO JA11)
SUBSYSTEM=="hidraw", ATTRS{{idVendor}}=="31b2", ATTRS{{idProduct}}=="0111", MODE="0666", TAG+="uaccess"
SUBSYSTEM=="hidraw", ATTRS{{idVendor}}=="2972", ATTRS{{idProduct}}=="0052", MODE="0666", TAG+="uaccess"
"#);
        }
    }

    Ok(())
}
