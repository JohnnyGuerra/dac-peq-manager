"""Tests for RBJ biquad coefficient calculations and frequency response plotting."""

import math
import pytest
from dac_peq.biquad import (
    calculate_rbj_biquad,
    compute_composite_response,
    generate_log_frequencies,
    render_ascii_frequency_response,
)


def test_biquad_peaking_response():
    """Verify peaking filter response at center frequency equals specified gain."""
    f0 = 1000.0
    gain_db = 4.0
    q = 1.41
    fs = 48000.0

    coeffs = calculate_rbj_biquad("PK", freq=f0, gain_db=gain_db, q=q, fs=fs)
    res_at_f0 = coeffs.response_at(f0)
    assert pytest.approx(res_at_f0, abs=0.1) == gain_db

    # Far away from center frequency, gain should approach 0 dB
    res_far_low = coeffs.response_at(50.0)
    res_far_high = coeffs.response_at(18000.0)
    assert abs(res_far_low) < 0.2
    assert abs(res_far_high) < 0.2


def test_biquad_lowshelf_response():
    """Verify low-shelf filter response."""
    f0 = 100.0
    gain_db = 3.0
    q = 0.71
    fs = 48000.0

    coeffs = calculate_rbj_biquad("LSQ", freq=f0, gain_db=gain_db, q=q, fs=fs)
    # Deep in the bass shelf (e.g. 20 Hz)
    res_low = coeffs.response_at(20.0)
    assert pytest.approx(res_low, abs=0.2) == gain_db

    # High frequencies should be unaffected (near 0 dB)
    res_high = coeffs.response_at(5000.0)
    assert abs(res_high) < 0.1


def test_biquad_highshelf_response():
    """Verify high-shelf filter response."""
    f0 = 8000.0
    gain_db = -3.0
    q = 0.71
    fs = 48000.0

    coeffs = calculate_rbj_biquad("HSQ", freq=f0, gain_db=gain_db, q=q, fs=fs)
    # Deep in the high shelf (e.g. 16000 Hz)
    res_high = coeffs.response_at(16000.0)
    assert pytest.approx(res_high, abs=0.3) == gain_db

    # Low frequencies should be unaffected (near 0 dB)
    res_low = coeffs.response_at(200.0)
    assert abs(res_low) < 0.1


def test_biquad_96khz_sample_rate():
    """Verify calculation at 96 kHz sample rate."""
    coeffs = calculate_rbj_biquad("PK", freq=2000.0, gain_db=2.5, q=1.0, fs=96000.0)
    assert pytest.approx(coeffs.response_at(2000.0), abs=0.1) == 2.5


def test_composite_response_with_preamp():
    """Verify combined response of multiple bands plus global preamp."""
    bands = [
        {"type": "LSQ", "freq": 50.0, "gain": 2.0, "q": 0.71},
        {"type": "PK", "freq": 1000.0, "gain": -2.0, "q": 1.0},
    ]
    preamp_db = -2.5
    freqs = [20.0, 1000.0, 15000.0]

    curve = compute_composite_response(bands, preamp_db, freqs)
    assert len(curve) == 3

    # At 20 Hz: preamp (-2.5) + bass boost (~2.0) = ~ -0.5 dB
    assert pytest.approx(curve[0], abs=0.3) == -0.5

    # At 1000 Hz: preamp (-2.5) + cut (-2.0) = ~ -4.5 dB
    assert pytest.approx(curve[1], abs=0.3) == -4.5

    # At 15000 Hz: preamp (-2.5) + flat (0.0) = ~ -2.5 dB
    assert pytest.approx(curve[2], abs=0.2) == -2.5


def test_log_frequencies_monotonic():
    """Verify generate_log_frequencies produces strictly increasing values."""
    freqs = generate_log_frequencies(20.0, 20000.0, 50)
    assert len(freqs) == 50
    assert pytest.approx(freqs[0], abs=0.01) == 20.0
    assert pytest.approx(freqs[-1], abs=0.01) == 20000.0
    for i in range(len(freqs) - 1):
        assert freqs[i] < freqs[i + 1]


def test_ascii_plot_output():
    """Verify ASCII frequency response graph format."""
    bands = [
        {"index": 1, "type": "LSQ", "freq": 50.0, "gain": 2.2, "q": 0.71},
        {"index": 2, "type": "PK", "freq": 195.0, "gain": -2.4, "q": 1.10},
        {"index": 3, "type": "PK", "freq": 2200.0, "gain": 1.6, "q": 1.30},
        {"index": 4, "type": "PK", "freq": 4500.0, "gain": -1.8, "q": 2.50},
        {"index": 5, "type": "PK", "freq": 9800.0, "gain": -3.2, "q": 3.00},
    ]
    plot = render_ascii_frequency_response(bands, -2.5, width=60, height=12)
    assert "Frequency Response (-2.5 dB Preamp)" in plot
    assert "dB |" in plot
    assert "Hz:" in plot
    assert "Bands:" in plot
    assert "[1]" in plot
    assert "[5]" in plot
