"""Audio EQ Cookbook (Robert Bristow-Johnson) biquad coefficient calculator
and terminal ASCII frequency response plotter.
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
