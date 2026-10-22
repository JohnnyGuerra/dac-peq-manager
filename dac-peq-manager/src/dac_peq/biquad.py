"""Audio EQ Cookbook (Robert Bristow-Johnson) biquad coefficient calculator
and terminal ASCII frequency response plotter.

--------------------------------------------------------------------------------
ACKNOWLEDGMENTS & MATHEMATICAL ATTRIBUTION:
  - Biquad filter coefficient equations are based on the standard
    "Cookbook formulae for audio equalizer biquad filter coefficients"
    by Robert Bristow-Johnson (RBJ):
    https://www.w3.org/TR/audio-eq-cookbook/
  - Frequency response evaluation evaluates H(e^{j*w}) complex polynomial division:
    H(e^{j*w}) = (b0 + b1*e^{-jw} + b2*e^{-2jw}) / (1 + a1*e^{-jw} + a2*e^{-2jw})
  - 127-point logarithmic frequency curve sampling follows the conventions
    established by Jaakko Pasanen in AutoEq (https://github.com/jaakkopasanen/AutoEq).
  - Acoustic linter & 5-band landmark decimation incorporate coupler resonance
    insights (IEC 60318-4 / 711 insertion depth half-wave resonance) researched
    by Crinacle (In-Ear Fidelity) and Oratory1990.
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Sequence, Tuple


@dataclass
class BiquadCoeffs:
    """Normalized RBJ Biquad coefficients (normalized by a0 so a0=1.0)."""
    b0: float
    b1: float
    b2: float
    a1: float
    a2: float
    fs: float
    freq: float
    gain_db: float
    q: float
    filter_type: str

    def response_at(self, f: float) -> float:
        """Compute magnitude response in dB at frequency f (Hz)."""
        w = 2.0 * math.pi * f / self.fs
        # z^-1 = e^(-j*w) = cos(w) - j*sin(w)
        # z^-2 = e^(-2j*w) = cos(2*w) - j*sin(2*w)
        cos_w = math.cos(w)
        sin_w = math.sin(w)
        cos_2w = math.cos(2.0 * w)
        sin_2w = math.sin(2.0 * w)

        num_re = self.b0 + self.b1 * cos_w + self.b2 * cos_2w
        num_im = -self.b1 * sin_w - self.b2 * sin_2w

        den_re = 1.0 + self.a1 * cos_w + self.a2 * cos_2w
        den_im = -self.a1 * sin_w - self.a2 * sin_2w

        num_mag2 = num_re * num_re + num_im * num_im
        den_mag2 = den_re * den_re + den_im * den_im

        if den_mag2 <= 1e-12:
            return 0.0

        mag2 = num_mag2 / den_mag2
        if mag2 <= 1e-12:
            return -120.0
        return 10.0 * math.log10(mag2)


def calculate_rbj_biquad(
    filter_type: str,
    freq: float,
    gain_db: float,
    q: float,
    fs: float = 48000.0,
) -> BiquadCoeffs:
    """Calculate RBJ biquad coefficients for given filter parameters.

    Supported filter types:
      - 'PK', 'PEAKING', 'PEAK'
      - 'LSQ', 'LOW_SHELF', 'LOWSHELF'
      - 'HSQ', 'HIGH_SHELF', 'HIGHSHELF'
    """
    ftype = filter_type.upper().replace("-", "_").replace(" ", "_")

    # Clamping
    freq = max(10.0, min(freq, fs * 0.499))
    q = max(0.01, q)

    w0 = 2.0 * math.pi * freq / fs
    cos_w0 = math.cos(w0)
    sin_w0 = math.sin(w0)
    a_amp = 10.0 ** (gain_db / 40.0)  # sqrt(10^(gain/20))
    alpha = sin_w0 / (2.0 * q)

    if ftype in ("PK", "PEAK", "PEAKING"):
        b0 = 1.0 + alpha * a_amp
        b1 = -2.0 * cos_w0
        b2 = 1.0 - alpha * a_amp
        a0 = 1.0 + alpha / a_amp
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha / a_amp

    elif ftype in ("LSQ", "LOW_SHELF", "LOWSHELF"):
        two_sqrt_a_alpha = 2.0 * math.sqrt(a_amp) * alpha
        a_plus_1 = a_amp + 1.0
        a_minus_1 = a_amp - 1.0

        b0 = a_amp * (a_plus_1 - a_minus_1 * cos_w0 + two_sqrt_a_alpha)
        b1 = 2.0 * a_amp * (a_minus_1 - a_plus_1 * cos_w0)
        b2 = a_amp * (a_plus_1 - a_minus_1 * cos_w0 - two_sqrt_a_alpha)
        a0 = a_plus_1 + a_minus_1 * cos_w0 + two_sqrt_a_alpha
        a1 = -2.0 * (a_minus_1 + a_plus_1 * cos_w0)
        a2 = a_plus_1 + a_minus_1 * cos_w0 - two_sqrt_a_alpha

    elif ftype in ("HSQ", "HIGH_SHELF", "HIGHSHELF"):
        two_sqrt_a_alpha = 2.0 * math.sqrt(a_amp) * alpha
        a_plus_1 = a_amp + 1.0
        a_minus_1 = a_amp - 1.0

        b0 = a_amp * (a_plus_1 + a_minus_1 * cos_w0 + two_sqrt_a_alpha)
        b1 = -2.0 * a_amp * (a_minus_1 + a_plus_1 * cos_w0)
        b2 = a_amp * (a_plus_1 + a_minus_1 * cos_w0 - two_sqrt_a_alpha)
        a0 = a_plus_1 - a_minus_1 * cos_w0 + two_sqrt_a_alpha
        a1 = 2.0 * (a_minus_1 - a_plus_1 * cos_w0)
        a2 = a_plus_1 - a_minus_1 * cos_w0 - two_sqrt_a_alpha

    else:
        # Default bypass / identity
        b0, b1, b2 = 1.0, 0.0, 0.0
        a0, a1, a2 = 1.0, 0.0, 0.0

    # Normalize by a0
    if abs(a0) < 1e-12:
        a0 = 1.0

    return BiquadCoeffs(
        b0=b0 / a0,
        b1=b1 / a0,
        b2=b2 / a0,
        a1=a1 / a0,
        a2=a2 / a0,
        fs=fs,
        freq=freq,
        gain_db=gain_db,
        q=q,
        filter_type=ftype,
    )


def compute_composite_response(
    bands: Sequence[dict],
    preamp_db: float,
    frequencies: Sequence[float],
    fs: float = 48000.0,
) -> List[float]:
    """Compute the combined EQ curve (preamp + all band responses) at given frequencies."""
    filters = [
        calculate_rbj_biquad(
            filter_type=b["type"],
            freq=b["freq"],
            gain_db=b["gain"],
            q=b["q"],
            fs=fs,
        )
        for b in bands
    ]

    curve: List[float] = []
    for f in frequencies:
        val = preamp_db
        for filt in filters:
            val += filt.response_at(f)
        curve.append(val)
    return curve


def generate_log_frequencies(f_min: float = 20.0, f_max: float = 20000.0, points: int = 127) -> List[float]:
    """Generate logarithmically spaced frequencies between f_min and f_max."""
    log_min = math.log10(f_min)
    log_max = math.log10(f_max)
    step = (log_max - log_min) / (points - 1)
    return [10.0 ** (log_min + i * step) for i in range(points)]


def calculate_peak_composite_gain(
    bands: Sequence[dict],
    fs: float = 48000.0,
    points: int = 500,
) -> float:
    """Compute the maximum composite filter gain in dB across 20 Hz - 20 kHz (without preamp)."""
    if not bands:
        return 0.0
    frequencies = generate_log_frequencies(20.0, 20000.0, points)
    curve = compute_composite_response(bands, 0.0, frequencies, fs=fs)
    return max(curve)


def calculate_recommended_preamp(
    bands: Sequence[dict],
    headroom_db: float = 0.5,
    fs: float = 48000.0,
) -> float:
    """Calculate recommended negative preamp (dB) to prevent DAC inter-sample clipping.

    Formula: recommended_preamp = - (max_composite_gain + headroom_db).
    Rounded to 0.5 dB precision matching KT02H20 register 0x66 resolution.
    """
    peak = calculate_peak_composite_gain(bands, fs=fs)
    if peak <= 0.0:
        return 0.0
    rec = -(peak + headroom_db)
    # Round to nearest 0.5 dB
    return round(rec * 2.0) / 2.0


def lint_acoustic_bands(bands: Sequence[dict]) -> List[str]:
    """Inspect PEQ bands for acoustic pitfalls, coupler artifacts, and high-Q issues.

    Checks:
      1. 711 artificial coupler resonance artifact (7.5 kHz - 9.5 kHz, high Q, deep cut).
      2. Excessive boost (> +6 dB) which strains drivers and causes DAC distortion.
      3. Ultra-high Q (> 5.0) which introduces audible phase ringing in minimum-phase IIR filters.
    """
    warnings: List[str] = []

    for i, b in enumerate(bands, 1):
        freq = float(b.get("freq", 1000.0))
        gain = float(b.get("gain", 0.0))
        q = float(b.get("q", 1.0))
        ftype = str(b.get("type", "PK")).upper()

        # 1. 711 coupler resonance spike check
        if 7400.0 <= freq <= 9600.0:
            if q > 2.0 and gain <= -3.0:
                warnings.append(
                    f"Band {i} ({freq:.0f} Hz, {gain:+.1f} dB, Q={q:.2f}) matches an IEC 60318-4 (711) "
                    "coupler half-wave resonance artifact. Deep, high-Q cuts here can hollow out natural treble "
                    "on real human ear canals. Consider smoothing Q <= 1.4 or using a High-Shelf (HSQ)."
                )

        # 2. Extreme boost check
        if gain > 6.0:
            warnings.append(
                f"Band {i} ({freq:.0f} Hz, {gain:+.1f} dB) exceeds +6.0 dB boost. Ensure adequate digital "
                "preamp attenuation to prevent delta-sigma modulator saturation."
            )

        # 3. High-Q ringing check
        if q > 5.0 and ftype not in ("NOTCH",):
            warnings.append(
                f"Band {i} ({freq:.0f} Hz, Q={q:.2f}) has ultra-narrow Q > 5.0. Narrow IIR biquad filters "
                "produce significant phase shifts and group delay ringing."
            )

    return warnings


def render_ascii_frequency_response(
    bands: Sequence[dict],
    preamp_db: float,
    width: int = 70,
    height: int = 15,
    min_db: float | None = None,
    max_db: float | None = None,
) -> str:
    """Render an ASCII/Unicode frequency response graph in logarithmic scale.

    Shows composite EQ response, 0 dB baseline, and band center frequency markers.
    """
    f_min, f_max = 20.0, 20000.0
    frequencies = generate_log_frequencies(f_min, f_max, width)
    curve = compute_composite_response(bands, preamp_db, frequencies)

    # Determine vertical dB scale bounds
    auto_min = min(-6.0, min(curve) - 1.0)
    auto_max = max(4.0, max(curve) + 1.0)
    db_bottom = min_db if min_db is not None else math.floor(auto_min)
    db_top = max_db if max_db is not None else math.ceil(auto_max)

    # Make sure 0.0 is cleanly inside range
    if db_bottom > -1.0:
        db_bottom = -2.0
    if db_top < 1.0:
        db_top = 2.0

    db_range = db_top - db_bottom
    if db_range <= 0:
        db_range = 10.0

    # Grid buffer: rows x cols
    grid = [[" " for _ in range(width)] for _ in range(height)]

    # Row corresponding to 0 dB line
    zero_row = int(round((db_top - 0.0) / db_range * (height - 1)))
    zero_row = max(0, min(height - 1, zero_row))

    # Draw 0 dB dashed baseline
    for col in range(width):
        grid[zero_row][col] = "┄"

    # Map curve points to grid
    for col, db_val in enumerate(curve):
        row = int(round((db_top - db_val) / db_range * (height - 1)))
        row = max(0, min(height - 1, row))
        grid[row][col] = "█"

    # Calculate band positions on logarithmic x-axis
    band_markers: List[Tuple[int, int, str]] = []  # (col, band_index, label)
    for b in bands:
        bfreq = b["freq"]
        if f_min <= bfreq <= f_max:
            col = int(round((math.log10(bfreq) - math.log10(f_min)) / (math.log10(f_max) - math.log10(f_min)) * (width - 1)))
            col = max(0, min(width - 1, col))
            idx = b.get("index", len(band_markers) + 1)
            band_markers.append((col, idx, f"[{idx}]"))

    # Overlay band markers onto graph
    for col, idx, label in band_markers:
        # Check current row of curve at this column
        db_val = curve[col]
        row = int(round((db_top - db_val) / db_range * (height - 1)))
        row = max(0, min(height - 1, row))
        grid[row][col] = f"{idx}"

    # Build formatted string with left Y-axis labels
    lines: List[str] = []
    lines.append(f"  +-- Frequency Response ({preamp_db:+.1f} dB Preamp) -----------------------------+")
    for r in range(height):
        # Calculate approximate dB for this row
        row_db = db_top - (r / (height - 1)) * db_range
        label_db = f"{row_db:+5.1f}dB |" if r % 3 == 0 or r == zero_row else "       |"
        row_str = "".join(grid[r])
        lines.append(f"{label_db}{row_str}|")

    lines.append(f"       +{'-' * width}+")

    # X-axis frequency markers
    # Standard log frequencies: 20, 50, 100, 200, 500, 1k, 2k, 5k, 10k, 20k
    freq_ticks = [
        (20, "20"),
        (50, "50"),
        (100, "100"),
        (200, "200"),
        (500, "500"),
        (1000, "1k"),
        (2000, "2k"),
        (5000, "5k"),
        (10000, "10k"),
        (20000, "20k"),
    ]

    axis_chars = [" "] * width
    for f, text in freq_ticks:
        c = int(round((math.log10(f) - math.log10(f_min)) / (math.log10(f_max) - math.log10(f_min)) * (width - 1)))
        if c + len(text) <= width:
            for i, ch in enumerate(text):
                axis_chars[c + i] = ch

    lines.append(" Hz:   " + "".join(axis_chars))

    # Band legends summary
    legend_parts = []
    for b in bands:
        idx = b.get("index", "?")
        t = b.get("type", "PK")
        f = b.get("freq", 0)
        g = b.get("gain", 0)
        q = b.get("q", 0)
        legend_parts.append(f"[{idx}] {t} {f:.0f}Hz {g:+.1f}dB Q={q:.2f}")

    lines.append(" Bands: " + " | ".join(legend_parts[:3]))
    if len(legend_parts) > 3:
        lines.append("        " + " | ".join(legend_parts[3:]))

    return "\n".join(lines)


def refit_decimated_gains(
    original_bands: Sequence[Dict[str, Any]],
    decimated_bands: Sequence[Dict[str, Any]],
    fs: float = 48000.0,
) -> List[Dict[str, Any]]:
    """Fine-tune the gains of surviving decimated bands via coordinate descent to minimize RMS error."""
    if not decimated_bands or len(original_bands) <= len(decimated_bands):
        return [dict(b) for b in decimated_bands]

    freqs = generate_log_frequencies(20.0, 20000.0, 64)
    target_curve = compute_composite_response(original_bands, 0.0, freqs, fs=fs)
    current_bands = [dict(b) for b in decimated_bands]

    def _get_sse(b_list: Sequence[Dict[str, Any]]) -> float:
        curve = compute_composite_response(b_list, 0.0, freqs, fs=fs)
        return sum((c - t) * (c - t) for c, t in zip(curve, target_curve))

    current_sse = _get_sse(current_bands)
    deltas = [-1.5, -1.0, -0.5, -0.2, 0.2, 0.5, 1.0, 1.5]

    for _ in range(2):
        for b in current_bands:
            best_gain = float(b.get("gain", 0.0))
            best_sse = current_sse
            orig_gain = best_gain
            for d in deltas:
                cand = round(orig_gain + d, 2)
                if cand < -18.0 or cand > 18.0:
                    continue
                b["gain"] = cand
                cand_sse = _get_sse(current_bands)
                if cand_sse < best_sse - 1e-6:
                    best_sse = cand_sse
                    best_gain = cand
            b["gain"] = best_gain
            current_sse = best_sse

    return current_bands


def decimate_bands(
    bands: List[Dict[str, Any]],
    target_bands: int = 5,
    refit_gains: bool = True,
    fs: float = 48000.0,
) -> List[Dict[str, Any]]:
    """Intelligently reduce an arbitrary N-band PEQ curve to `target_bands` landmark filters.

    Preserves critical acoustic landmark regions:
      - Sub-bass shelf (<= 150 Hz)
      - Ear-gain presence / vocal pinna peak (2000 - 4000 Hz)
      - Mid-bass warmth / lower midrange (150 - 600 Hz)
      - Concha / lower treble presence (4000 - 7000 Hz)
      - Treble air high-shelf (>= 7000 Hz)
    Actively penalizes narrow 711 coupler insertion resonance artifacts (7-8.5 kHz).
    If `refit_gains` is True, runs coordinate-descent gain optimization to minimize RMS error.
    """
    if not bands:
        return []

    target_bands = max(1, target_bands)

    if len(bands) <= target_bands:
        out = [dict(b) for b in bands]
        while len(out) < target_bands:
            out.append({
                "type": "PK",
                "freq": 1000.0,
                "gain": 0.0,
                "q": 1.0,
            })
        for i, b in enumerate(out, 1):
            b["index"] = i
        return out

    def score(b: Dict[str, Any]) -> float:
        g = abs(float(b.get("gain", 0.0)))
        f = float(b.get("freq", 1000.0))
        t = str(b.get("type", "PK")).upper()
        q = float(b.get("q", 1.0))

        # Core anchor shelves receive top priority
        if t in ("LSQ", "LOW_SHELF", "LOWSHELF") and f <= 150:
            return 100.0 + g * 3.0
        if t in ("HSQ", "HIGH_SHELF", "HIGHSHELF") and f >= 7000:
            return 90.0 + g * 3.0

        # Penalize narrow IEC 60318-4 coupler insertion artifacts
        if 7000 <= f <= 8500 and q >= 2.5:
            return g * 0.35

        # Weighted by human ear sensitivity landmarks
        if 2000 <= f <= 4000:
            return g * 2.5
        if 150 <= f <= 600:
            return g * 1.8
        if 4000 <= f <= 7000:
            return g * 1.5

        return g

    # Build logarithmic frequency bins across human audible spectrum (20 Hz - 20000 Hz)
    f_min, f_max = 20.0, 20000.0
    l_min, l_max = math.log10(f_min), math.log10(f_max)
    bins = []
    for i in range(target_bands):
        b_lo = 10 ** (l_min + i * (l_max - l_min) / target_bands)
        b_hi = 10 ** (l_min + (i + 1) * (l_max - l_min) / target_bands)
        bins.append((b_lo, b_hi))

    selected: List[Dict[str, Any]] = []
    used_indices = set()

    for b_lo, b_hi in bins:
        candidates = [
            (idx, b) for idx, b in enumerate(bands)
            if idx not in used_indices and b_lo <= float(b.get("freq", 0.0)) < b_hi
        ]
        if candidates:
            best_idx, best_b = max(candidates, key=lambda pair: score(pair[1]))
            selected.append(dict(best_b))
            used_indices.add(best_idx)

    # Fill remaining unfilled bins from highest-scoring global candidates
    if len(selected) < target_bands:
        remaining = [
            (idx, b) for idx, b in enumerate(bands)
            if idx not in used_indices
        ]
        remaining.sort(key=lambda pair: score(pair[1]), reverse=True)
        for idx, b in remaining[: target_bands - len(selected)]:
            selected.append(dict(b))
            used_indices.add(idx)

    if refit_gains and len(bands) > len(selected):
        selected = refit_decimated_gains(bands, selected, fs=fs)

    selected.sort(key=lambda x: float(x.get("freq", 1000.0)))
    for i, b in enumerate(selected, 1):
        b["index"] = i
    return selected


def calculate_curve_difference(
    bands_a: Sequence[Dict[str, Any]],
    preamp_a: float,
    bands_b: Sequence[Dict[str, Any]],
    preamp_b: float,
    fs: float = 48000.0,
    points: int = 220,
) -> Dict[str, float]:
    """Calculate acoustic difference metrics between two PEQ curves across the audible spectrum.

    Evaluates both curves across log-spaced frequencies from 20 Hz to 20,000 Hz.

    Returns:
        {
            'rms_db': Root-mean-square difference in dB across 20Hz-20kHz,
            'max_diff_db': Peak difference in dB (signed: curve_a - curve_b),
            'max_diff_freq': Frequency in Hz where peak difference occurs,
            'pinna_rms_db': RMS error in the critical ear-gain pinna region (2kHz-4kHz),
        }
    """
    frequencies = generate_log_frequencies(20.0, 20000.0, points)
    curve_a = compute_composite_response(bands_a, preamp_a, frequencies, fs=fs)
    curve_b = compute_composite_response(bands_b, preamp_b, frequencies, fs=fs)

    sum_sq = 0.0
    pinna_sum_sq = 0.0
    pinna_count = 0
    max_diff = 0.0
    max_freq = 1000.0

    for f, a, b in zip(frequencies, curve_a, curve_b):
        diff = a - b
        sum_sq += diff * diff
        if abs(diff) > abs(max_diff):
            max_diff = diff
            max_freq = f
        if 2000.0 <= f <= 4000.0:
            pinna_sum_sq += diff * diff
            pinna_count += 1

    rms = math.sqrt(sum_sq / len(frequencies)) if frequencies else 0.0
    pinna_rms = math.sqrt(pinna_sum_sq / pinna_count) if pinna_count > 0 else 0.0

    return {
        "rms_db": round(rms, 2),
        "max_diff_db": round(max_diff, 2),
        "max_diff_freq": round(max_freq, 1),
        "pinna_rms_db": round(pinna_rms, 2),
    }


def validate_hardware_bands(target_bands: int, architecture: str) -> Tuple[int, Optional[str]]:
    """Validate target band quantity against hardware architecture constraints.

    Returns:
        (allowed_bands, warning_message_or_None)
    """
    arch = architecture.lower()
    if arch == "ktmicro_dsp" and target_bands > 5:
        return 5, f"KTMicro KT02H20 hardware is physically limited to 5 biquads. Target clamped from {target_bands} to 5 bands."
    if arch == "moondrop_dsp" and target_bands > 9:
        return 9, f"Moondrop FreeDSP hardware supports a maximum of 9 biquads. Target clamped from {target_bands} to 9 bands."
    return target_bands, None

