"""Host-side DSP configuration generators for JCALLY JM6 Pro (Conexant CX31993)
and universal software parametric equalizers.

Supports:
  1. PipeWire filter-chain configuration bound to Conexant CX31993 ALSA sink.
  2. EqualizerAPO .txt configuration.
  3. Wavelet GraphicEQ .txt and 9-band interpolated Wavelet JSON profiles for Android.

--------------------------------------------------------------------------------
ACKNOWLEDGMENTS & ATTRIBUTION:
  - PipeWire filter-chain graph specification and builtin DSP filter definitions:
    PipeWire project (Wim Taymans et al., https://pipewire.org)
  - EqualizerAPO text configuration format:
    EqualizerAPO project (Peter Verheet, https://sourceforge.net/projects/equalizerapo/)
  - Wavelet GraphicEQ 127-frequency format & AutoEq normalization conventions:
    AutoEq project (Jaakko Pasanen, https://github.com/jaakkopasanen/AutoEq)
    Wavelet app by Pitched Apps (https://wavelet.app/)
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List

from dac_peq.biquad import compute_composite_response, generate_log_frequencies


DEFAULT_CX31993_SINK = "alsa_output.usb-Conexant_CX31993*"


def format_pipewire_filter_chain(
    preset: Dict[str, Any],
    sink_target: str = DEFAULT_CX31993_SINK,
) -> str:
    """Generate PipeWire filter-chain configuration content."""
    preset_name = preset.get("name", "custom")
    preset_slug = preset_name.replace(" ", "_").replace("-", "_").lower()
    description = preset.get("description", f"JM6 Pro EQ Preset {preset_name}")
    preamp_db = float(preset.get("preamp", 0.0))
    linear_gain = round(10.0 ** (preamp_db / 20.0), 4)

    bands = preset.get("bands", [])
    if len(bands) < 1:
        raise ValueError("Preset must contain at least 1 band.")
    num_bands = len(bands)

    # Map filter types to PipeWire builtin labels
    type_map = {
        "PK": "bq_peaking",
        "PEAK": "bq_peaking",
        "PEAKING": "bq_peaking",
        "LSQ": "bq_lowshelf",
        "LOW_SHELF": "bq_lowshelf",
        "LOWSHELF": "bq_lowshelf",
        "HSQ": "bq_highshelf",
        "HIGH_SHELF": "bq_highshelf",
        "HIGHSHELF": "bq_highshelf",
    }

    # Generate node definitions for FL and FR channels
    nodes = []

    # 1. Preamp linear nodes
    nodes.append(f"""                    # Preamp Gain Stage ({preamp_db:+.1f} dB = linear {linear_gain})
                    {{
                        type   = builtin
                        name   = "preamp_fl"
                        label  = linear
                        control = {{
                            "Gain" = {linear_gain}
                        }}
                    }}
                    {{
                        type   = builtin
                        name   = "preamp_fr"
                        label  = linear
                        control = {{
                            "Gain" = {linear_gain}
                        }}
                    }}""")

    # 2. Biquad nodes for each band (FL and FR)
    for i in range(num_bands):
        b = bands[i]
        b_idx = i + 1
        ftype = type_map.get(str(b.get("type", "PK")).upper(), "bq_peaking")
        freq = float(b.get("freq", 1000.0))
        gain = float(b.get("gain", 0.0))
        q = float(b.get("q", 1.0))
        comment = b.get("comment", f"Band {b_idx}")

        nodes.append(f"""                    # Band {b_idx}: {b.get('type', 'PK')} {freq:.1f} Hz, {gain:+.1f} dB, Q={q:.2f} ({comment})
                    {{
                        type   = builtin
                        name   = "eq_band{b_idx}_fl"
                        label  = {ftype}
                        control = {{
                            "Freq" = {freq:.1f}
                            "Gain" = {gain:.2f}
                            "Q"    = {q:.2f}
                        }}
                    }}
                    {{
                        type   = builtin
                        name   = "eq_band{b_idx}_fr"
                        label  = {ftype}
                        control = {{
                            "Freq" = {freq:.1f}
                            "Gain" = {gain:.2f}
                            "Q"    = {q:.2f}
                        }}
                    }}""")

    # 3. Chained links
    links = [
        """                    # Route Preamp -> Band 1
                    { output = "preamp_fl:Out", input = "eq_band1_fl:In" }
                    { output = "preamp_fr:Out", input = "eq_band1_fr:In" }"""
    ]
    for i in range(1, num_bands):
        prev = i
        curr = i + 1
        links.append(f"""                    # Route Band {prev} -> Band {curr}
                    {{ output = "eq_band{prev}_fl:Out", input = "eq_band{curr}_fl:In" }}
                    {{ output = "eq_band{prev}_fr:Out", input = "eq_band{curr}_fr:In" }}""")

    nodes_block = "\n".join(nodes)
    links_block = "\n".join(links)

    conf = f"""# PipeWire filter-chain configuration for JCALLY JM6 Pro (Conexant CX31993)
# Preset: {preset_name}
# Description: {description}
# Generated by dac-peq-manager

context.modules = [
    {{
        name = libpipewire-module-filter-chain
        args = {{
            node.description = "JCALLY JM6 Pro DSP [{preset_name}]"
            media.name       = "JCALLY JM6 Pro DSP [{preset_name}]"
            filter.graph = {{
                nodes = [
{nodes_block}
                ]
                links = [
{links_block}
                ]
                inputs  = [ "preamp_fl:In", "preamp_fr:In" ]
                outputs = [ "eq_band{num_bands}_fl:Out", "eq_band{num_bands}_fr:Out" ]
            }}
            capture.props = {{
                node.name        = "effect_input.jm6pro_{preset_slug}"
                media.class      = "Audio/Sink"
                audio.position   = [ "FL", "FR" ]
                node.description = "JM6 Pro [{preset_name}] Virtual Sink"
            }}
            playback.props = {{
                node.name        = "effect_output.jm6pro_{preset_slug}"
                node.target      = "{sink_target}"
                audio.position   = [ "FL", "FR" ]
                node.passive     = true
            }}
        }}
    }}
]
"""
    return conf


def export_pipewire_conf(
    preset: Dict[str, Any],
    output_path: Optional[str | Path] = None,
    sink_target: str = DEFAULT_CX31993_SINK,
) -> Path:
    """Write PipeWire filter-chain configuration file."""
    preset_name = preset.get("name", "custom")
    preset_slug = preset_name.replace(" ", "_").replace("-", "_").lower()

    if output_path is None:
        pw_dir = Path.home() / ".config" / "pipewire" / "pipewire.conf.d"
        pw_dir.mkdir(parents=True, exist_ok=True)
        target = pw_dir / f"99-jm6pro-{preset_slug}.conf"
    else:
        target = Path(output_path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)

    content = format_pipewire_filter_chain(preset, sink_target=sink_target)
    target.write_text(content, encoding="utf-8")
    return target


def format_equalizer_apo(preset: Dict[str, Any]) -> str:
    """Generate standard EqualizerAPO .txt configuration."""
    preset_name = preset.get("name", "custom")
    description = preset.get("description", "")
    preamp_db = float(preset.get("preamp", 0.0))
    bands = preset.get("bands", [])

    lines = [
        "# EqualizerAPO Configuration",
        f"# Preset: {preset_name}",
        f"# Description: {description}",
        "# Generated by dac-peq-manager for JCALLY JM6 Pro & Universal Host DSP",
        "",
        f"Preamp: {preamp_db:+.1f} dB",
    ]

    type_map = {
        "PK": "PK",
        "PEAK": "PK",
        "PEAKING": "PK",
        "LSQ": "LSQ",
        "LOW_SHELF": "LSQ",
        "LOWSHELF": "LSQ",
        "HSQ": "HSQ",
        "HIGH_SHELF": "HSQ",
        "HIGHSHELF": "HSQ",
    }

    for i, b in enumerate(bands[:5]):
        idx = i + 1
        ftype = type_map.get(str(b.get("type", "PK")).upper(), "PK")
        freq = float(b.get("freq", 1000.0))
        gain = float(b.get("gain", 0.0))
        q = float(b.get("q", 1.0))
        lines.append(f"Filter {idx}: ON {ftype} Fc {freq:.1f} Hz Gain {gain:+.1f} dB Q {q:.2f}")

    return "\n".join(lines) + "\n"


def format_wavelet_graphiceq(preset: Dict[str, Any], points: int = 127) -> str:
    """Generate AutoEq-compatible GraphicEQ string for Wavelet import."""
    preamp_db = float(preset.get("preamp", 0.0))
    bands = preset.get("bands", [])

    frequencies = generate_log_frequencies(20.0, 20000.0, points)
    curve = compute_composite_response(bands, preamp_db, frequencies)

    # Format as: GraphicEQ: 20 -0.5; 21 -0.5; ...
    pairs = [f"{round(f)} {val:.1f}" for f, val in zip(frequencies, curve)]
    return "GraphicEQ: " + "; ".join(pairs) + "\n"


def format_wavelet_json(preset: Dict[str, Any]) -> Dict[str, Any]:
    """Generate Wavelet JSON profile with 9-band interpolated gains and GraphicEQ string."""
    preset_name = preset.get("name", "custom")
    description = preset.get("description", "")
    preamp_db = float(preset.get("preamp", 0.0))
    bands = preset.get("bands", [])

    # Standard Wavelet 9-band center frequencies (Hz)
    wavelet_9_bands = [53.8, 107.7, 215.3, 430.7, 861.3, 1722.7, 3445.3, 6890.6, 13781.3]
    gains_9 = compute_composite_response(bands, preamp_db, wavelet_9_bands)

    nine_band_dict = {}
    for f, g in zip(wavelet_9_bands, gains_9):
        nine_band_dict[f"{f:.1f}Hz"] = round(g, 1)

    graphiceq_str = format_wavelet_graphiceq(preset).strip()

    return {
        "name": preset_name,
        "description": description,
        "target": "JCALLY JM6 Pro (Conexant CX31993) / Android Wavelet",
        "preamp": preamp_db,
        "nine_band_gains": nine_band_dict,
        "graphiceq": graphiceq_str,
        "bands": [
            {
                "index": i + 1,
                "type": b.get("type", "PK"),
                "freq": b.get("freq", 1000.0),
                "gain": b.get("gain", 0.0),
                "q": b.get("q", 1.0),
            }
            for i, b in enumerate(bands[:5])
        ],
    }


def export_apo_suite(
    preset: Dict[str, Any],
    output_dir: str | Path = "./exports",
) -> Dict[str, Path]:
    """Export EqualizerAPO .txt, Wavelet GraphicEQ .txt, and Wavelet JSON files."""
    out_dir = Path(output_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    preset_name = preset.get("name", "custom")
    preset_slug = preset_name.replace(" ", "_").replace("-", "_").lower()

    apo_file = out_dir / f"{preset_slug}_equalizer_apo.txt"
    wavelet_txt = out_dir / f"{preset_slug}_wavelet_graphiceq.txt"
    wavelet_json = out_dir / f"{preset_slug}_wavelet.json"

    apo_file.write_text(format_equalizer_apo(preset), encoding="utf-8")
    wavelet_txt.write_text(format_wavelet_graphiceq(preset), encoding="utf-8")
    wavelet_json.write_text(json.dumps(format_wavelet_json(preset), indent=2), encoding="utf-8")

    return {
        "equalizer_apo": apo_file,
        "wavelet_txt": wavelet_txt,
        "wavelet_json": wavelet_json,
    }
