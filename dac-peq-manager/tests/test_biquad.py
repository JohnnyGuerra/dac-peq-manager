"""Tests for RBJ biquad coefficient calculations and frequency response plotting."""

import math
import pytest
from dac_peq.biquad import (
    calculate_peak_composite_gain,
    calculate_rbj_biquad,
    calculate_recommended_preamp,
    compute_composite_response,
    generate_log_frequencies,
    lint_acoustic_bands,
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


def test_calculate_peak_composite_gain_and_recommended_preamp():
    """Verify peak detection and recommended negative preamp with headroom."""
    bands = [
        {"type": "PK", "freq": 1000.0, "gain": 3.0, "q": 1.0},
        {"type": "LSQ", "freq": 100.0, "gain": 2.0, "q": 0.71},
    ]
    peak = calculate_peak_composite_gain(bands)
    assert pytest.approx(peak, abs=0.05) == 3.0

    rec_preamp = calculate_recommended_preamp(bands, headroom_db=0.5)
    # rec_preamp should be <= -(peak + 0.5)
    assert rec_preamp <= -3.5


def test_lint_acoustic_bands_coupler_resonance():
    """Verify detection of 711 coupler artifact spikes."""
    bands = [
        {"type": "PK", "freq": 8500.0, "gain": -5.0, "q": 3.0},  # Coupler artifact!
        {"type": "PK", "freq": 1000.0, "gain": 1.0, "q": 1.0},
    ]
    warnings = lint_acoustic_bands(bands)
    assert len(warnings) == 1
    assert "IEC 60318-4 (711)" in warnings[0]


def test_lint_acoustic_bands_boost_and_high_q():
    """Verify detection of excessive boost (>+6dB) and ultra-high Q (>5.0)."""
    bands = [
        {"type": "PK", "freq": 2000.0, "gain": 8.5, "q": 1.0},   # Excessive boost
        {"type": "PK", "freq": 5000.0, "gain": 1.0, "q": 6.5},   # High Q phase ringing
    ]
    warnings = lint_acoustic_bands(bands)
    assert len(warnings) == 2
    assert "exceeds +6.0 dB boost" in warnings[0]
    assert "ultra-narrow Q > 5.0" in warnings[1]


def test_decimate_bands_landmark_selection():
    """Verify 10-band AutoEq reduction to 5 acoustic landmark bands."""
    from dac_peq.biquad import decimate_bands

    input_10_bands = [
        {"type": "LSQ", "freq": 105.0, "gain": 6.5, "q": 0.7},
        {"type": "PK", "freq": 125.0, "gain": -2.7, "q": 0.55},
        {"type": "PK", "freq": 350.0, "gain": -1.5, "q": 1.8},
        {"type": "PK", "freq": 522.0, "gain": 0.7, "q": 1.02},
        {"type": "PK", "freq": 1298.0, "gain": -1.2, "q": 2.14},
        {"type": "PK", "freq": 2800.0, "gain": 2.4, "q": 1.5},
        {"type": "PK", "freq": 4500.0, "gain": -2.0, "q": 2.2},
        {"type": "PK", "freq": 7100.0, "gain": -3.2, "q": 4.0},  # Coupler artifact
        {"type": "PK", "freq": 8445.0, "gain": 3.3, "q": 1.61},
        {"type": "HSQ", "freq": 10500.0, "gain": -2.0, "q": 0.7},
    ]

    decimated = decimate_bands(input_10_bands, target_bands=5)
    assert len(decimated) == 5

    # Band indices are strictly monotonic 1..5
    assert [b["index"] for b in decimated] == [1, 2, 3, 4, 5]

    # Frequencies are monotonic
    freqs = [b["freq"] for b in decimated]
    assert freqs == sorted(freqs)

    # Sub-bass low shelf is preserved
    assert decimated[0]["type"] == "LSQ"
    assert decimated[0]["freq"] == 105.0

    # High shelf is preserved
    assert decimated[4]["type"] == "HSQ"
    assert decimated[4]["freq"] == 10500.0

    # Coupler artifact (7100Hz Q=4.0) should be avoided in favor of broader landmark filters
    assert not any(b["freq"] == 7100.0 for b in decimated)


def test_decimate_bands_padding():
    """Verify small band lists are padded to target band quantity with neutral bypass filters."""
    from dac_peq.biquad import decimate_bands

    two_bands = [
        {"type": "LSQ", "freq": 80.0, "gain": 3.0, "q": 0.7},
        {"type": "PK", "freq": 3000.0, "gain": 2.0, "q": 1.5},
    ]
    padded = decimate_bands(two_bands, target_bands=5)
    assert len(padded) == 5
    assert padded[0]["freq"] == 80.0
    assert padded[1]["freq"] == 3000.0
    # Remaining bands are flat bypass
    for b in padded[2:]:
        assert b["gain"] == 0.0


def test_validate_hardware_bands():
    """Verify hardware architecture constraint validation."""
    from dac_peq.biquad import validate_hardware_bands

    # KTMicro KT02H20 (max 5)
    allowed, warn = validate_hardware_bands(10, "ktmicro_dsp")
    assert allowed == 5
    assert warn is not None
    assert "physically limited to 5 biquads" in warn

    # KTMicro within limits
    allowed, warn = validate_hardware_bands(5, "ktmicro_dsp")
    assert allowed == 5
    assert warn is None

    # Moondrop FreeDSP (max 9)
    allowed, warn = validate_hardware_bands(10, "moondrop_dsp")
    assert allowed == 9
    assert warn is not None

    # Host DSP (PipeWire / APO / Wavelet)
    allowed, warn = validate_hardware_bands(10, "pipewire")
    assert allowed == 10
    assert warn is None


def test_calculate_curve_difference():
    """Verify acoustic difference metrics between two PEQ curves."""
    from dac_peq.biquad import calculate_curve_difference

    bands_a = [
        {"type": "PK", "freq": 1000.0, "gain": 3.0, "q": 1.0},
        {"type": "LSQ", "freq": 100.0, "gain": 2.0, "q": 0.71},
    ]

    # Identical curves -> 0 RMS, 0 peak diff
    diff_same = calculate_curve_difference(bands_a, -1.0, bands_a, -1.0)
    assert diff_same["rms_db"] == 0.0
    assert diff_same["max_diff_db"] == 0.0
    assert diff_same["pinna_rms_db"] == 0.0

    # 3 dB uniform gain shift across all frequencies
    diff_shift = calculate_curve_difference(bands_a, 0.0, bands_a, -3.0)
    assert pytest.approx(diff_shift["rms_db"], abs=0.05) == 3.0
    assert pytest.approx(diff_shift["max_diff_db"], abs=0.05) == 3.0

    # Peak discrepancy at 3000 Hz
    bands_b = [
        {"type": "PK", "freq": 1000.0, "gain": 3.0, "q": 1.0},
        {"type": "LSQ", "freq": 100.0, "gain": 2.0, "q": 0.71},
        {"type": "PK", "freq": 3000.0, "gain": 4.0, "q": 2.0},
    ]
    diff_peak = calculate_curve_difference(bands_b, 0.0, bands_a, 0.0)
    assert diff_peak["rms_db"] > 0.0
    assert diff_peak["pinna_rms_db"] > 0.0
    assert 2800 <= diff_peak["max_diff_freq"] <= 3200


def test_decimate_bands_coordinate_descent_refit():
    """Verify coordinate-descent gain refitting reduces or maintains curve RMS difference."""
    from dac_peq.biquad import decimate_bands, calculate_curve_difference

    bands_10 = [
        {"type": "PK", "freq": 28.0, "gain": 3.4, "q": 1.7},
        {"type": "PK", "freq": 160.0, "gain": -1.2, "q": 0.8},
        {"type": "PK", "freq": 450.0, "gain": 0.9, "q": 1.5},
        {"type": "PK", "freq": 1250.0, "gain": -2.1, "q": 2.0},
        {"type": "PK", "freq": 2400.0, "gain": 4.5, "q": 1.4},
        {"type": "PK", "freq": 3200.0, "gain": -1.8, "q": 3.0},
        {"type": "PK", "freq": 4800.0, "gain": 2.2, "q": 2.5},
        {"type": "PK", "freq": 6100.0, "gain": -3.0, "q": 2.0},
        {"type": "PK", "freq": 8000.0, "gain": -2.5, "q": 4.0},
        {"type": "HSQ", "freq": 10000.0, "gain": 1.5, "q": 0.71},
    ]

    dec_unfitted = decimate_bands(bands_10, target_bands=5, refit_gains=False)
    dec_fitted = decimate_bands(bands_10, target_bands=5, refit_gains=True)

    diff_unfitted = calculate_curve_difference(bands_10, 0.0, dec_unfitted, 0.0)
    diff_fitted = calculate_curve_difference(bands_10, 0.0, dec_fitted, 0.0)

    # Refitting should reduce or equal RMS and pinna RMS error
    assert diff_fitted["rms_db"] <= diff_unfitted["rms_db"]
    assert diff_fitted["pinna_rms_db"] <= diff_unfitted["pinna_rms_db"]



