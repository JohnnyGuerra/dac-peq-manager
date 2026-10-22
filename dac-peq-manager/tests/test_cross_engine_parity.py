"""Cross-Engine Mathematical Parity Test Suite (Python vs. ES6 JavaScript).

Executes `web/modules/biquad_math.js`, `web/modules/exporters.js`, and
`web/modules/hid_transport.js` directly inside Node.js and asserts bit-accurate /
IEEE-754 floating-point parity (< 1e-9 tolerance) against Python `dac_peq`.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from dac_peq.biquad import (
    calculate_curve_difference,
    calculate_peak_composite_gain,
    calculate_rbj_biquad,
    calculate_recommended_preamp,
    compute_composite_response,
    decimate_bands,
    generate_log_frequencies,
)
from dac_peq.exporters import format_wavelet_graphiceq

ROOT_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT_DIR / "web"
FIXTURES_FILE = Path(__file__).resolve().parent / "fixtures" / "dsp_test_vectors.json"


def run_node_eval(js_code: str) -> dict:
    """Run an ES6 module snippet in Node.js with working directory set to `web/`."""
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", js_code],
        cwd=str(WEB_DIR),
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout.strip())


def test_rbj_biquad_coefficients_parity():
    """Verify Python `calculate_rbj_biquad` and JS `calculateRBJCoeffs` match within 1e-9."""
    vectors = json.loads(FIXTURES_FILE.read_text(encoding="utf-8"))
    cases = vectors["biquad_cases"]

    js_script = f"""
    import {{ calculateRBJCoeffs, evaluateBiquadAt }} from './modules/biquad_math.js';
    const cases = {json.dumps(cases)};
    const out = cases.map(c => {{
      const coeffs = calculateRBJCoeffs(c.type, c.freq, c.gain, c.q, c.fs);
      const resp1k = evaluateBiquadAt(coeffs, 1000.0, c.fs);
      const respFc = evaluateBiquadAt(coeffs, c.freq, c.fs);
      return {{ coeffs, resp1k, respFc }};
    }});
    console.log(JSON.stringify({{ results: out }}));
    """
    js_results = run_node_eval(js_script)["results"]

    for case, js_res in zip(cases, js_results):
        py_c = calculate_rbj_biquad(
            filter_type=case["type"],
            freq=case["freq"],
            gain_db=case["gain"],
            q=case["q"],
            fs=case["fs"],
        )
        js_c = js_res["coeffs"]

        assert abs(py_c.b0 - js_c["b0"]) < 1e-9
        assert abs(py_c.b1 - js_c["b1"]) < 1e-9
        assert abs(py_c.b2 - js_c["b2"]) < 1e-9
        assert abs(py_c.a1 - js_c["a1"]) < 1e-9
        assert abs(py_c.a2 - js_c["a2"]) < 1e-9
        assert abs(py_c.response_at(1000.0) - js_res["resp1k"]) < 1e-9
        assert abs(py_c.response_at(case["freq"]) - js_res["respFc"]) < 1e-9


def test_composite_curve_and_auto_preamp_parity():
    """Verify 127-point composite response curve and auto-preamp match identically."""
    vectors = json.loads(FIXTURES_FILE.read_text(encoding="utf-8"))
    preset = vectors["preset_10_band"]
    bands = preset["bands"]
    preamp = preset["preamp"]

    py_freqs = generate_log_frequencies(20.0, 20000.0, 127)
    py_curve = compute_composite_response(bands, preamp, py_freqs)
    py_peak = calculate_peak_composite_gain(bands)
    py_rec_preamp = calculate_recommended_preamp(bands)

    js_script = f"""
    import {{
      generateLogFrequencies,
      computeCompositeCurve,
      calculatePeakCompositeGain,
      calculateRecommendedPreamp
    }} from './modules/biquad_math.js';
    const bands = {json.dumps(bands)};
    const preamp = {json.dumps(preamp)};
    const freqs = generateLogFrequencies(127, 20.0, 20000.0);
    const curve = computeCompositeCurve(bands, preamp, freqs);
    const peak = calculatePeakCompositeGain(bands, 500);
    const recPreamp = calculateRecommendedPreamp(bands, 0.5);
    console.log(JSON.stringify({{ freqs, curve, peak, recPreamp }}));
    """
    js_out = run_node_eval(js_script)

    for pf, jf in zip(py_freqs, js_out["freqs"]):
        assert abs(pf - jf) < 1e-7

    for pc, jc in zip(py_curve, js_out["curve"]):
        assert abs(pc - jc) < 1e-9

    assert abs(py_peak - js_out["peak"]) < 1e-9
    assert py_rec_preamp == js_out["recPreamp"]


def test_landmark_decimation_and_rms_delta_parity():
    """Verify 10->5 and 10->9 landmark decimation and RMS delta metrics match identically."""
    vectors = json.loads(FIXTURES_FILE.read_text(encoding="utf-8"))
    bands_10 = vectors["preset_10_band"]["bands"]
    preamp = vectors["preset_10_band"]["preamp"]

    py_dec5 = decimate_bands(bands_10, target_bands=5)
    py_dec9 = decimate_bands(bands_10, target_bands=9)
    py_diff = calculate_curve_difference(py_dec5, preamp, bands_10, preamp)

    js_script = f"""
    import {{ decimateBands, calculateCurveDifference }} from './modules/biquad_math.js';
    const bands10 = {json.dumps(bands_10)};
    const preamp = {json.dumps(preamp)};
    const dec5 = decimateBands(bands10, 5);
    const dec9 = decimateBands(bands10, 9);
    const diff = calculateCurveDifference(dec5, preamp, bands10, preamp);
    console.log(JSON.stringify({{ dec5, dec9, diff }}));
    """
    js_out = run_node_eval(js_script)

    assert len(py_dec5) == len(js_out["dec5"]) == 5
    for pb, jb in zip(py_dec5, js_out["dec5"]):
        assert pb["index"] == jb["index"]
        assert pb["type"] == jb["type"]
        assert pb["freq"] == jb["freq"]
        assert pb["gain"] == jb["gain"]
        assert pb["q"] == jb["q"]

    assert len(py_dec9) == len(js_out["dec9"]) == 9
    for pb, jb in zip(py_dec9, js_out["dec9"]):
        assert pb["freq"] == jb["freq"]
        assert pb["gain"] == jb["gain"]

    assert py_diff["rms_db"] == js_out["diff"]["rms_db"]
    assert py_diff["max_diff_db"] == js_out["diff"]["max_diff_db"]
    assert py_diff["max_diff_freq"] == js_out["diff"]["max_diff_freq"]
    assert py_diff["pinna_rms_db"] == js_out["diff"]["pinna_rms_db"]


def test_wavelet_graphiceq_exporter_parity():
    """Verify Python `format_wavelet_graphiceq` and JS `formatWaveletGraphicEq` produce identical strings."""
    vectors = json.loads(FIXTURES_FILE.read_text(encoding="utf-8"))
    preset = vectors["preset_10_band"]

    py_geq = format_wavelet_graphiceq(preset, points=127)

    js_script = f"""
    import {{ formatWaveletGraphicEq }} from './modules/exporters.js';
    const bands = {json.dumps(preset["bands"])};
    const preamp = {json.dumps(preset["preamp"])};
    const geq = formatWaveletGraphicEq(bands, preamp, 127);
    console.log(JSON.stringify({{ geq }}));
    """
    js_out = run_node_eval(js_script)
    assert py_geq == js_out["geq"]


def test_dac_catalog_and_autoeq_fallback_parity():
    """Verify that Python and Web dacs.json catalogs and offline AutoEq fallbacks are in sync."""
    py_dacs = (ROOT_DIR / "src" / "dac_peq" / "data" / "dacs.json").read_text(encoding="utf-8")
    web_dacs = (ROOT_DIR / "web" / "dacs.json").read_text(encoding="utf-8")
    assert json.loads(py_dacs) == json.loads(web_dacs)

    py_fallback = json.loads((ROOT_DIR / "src" / "dac_peq" / "data" / "autoeq_fallback.json").read_text(encoding="utf-8"))
    js_script = """
    import { OFFLINE_AUTOEQ_FALLBACK } from './modules/autoeq_client.js';
    console.log(JSON.stringify({ fallback: OFFLINE_AUTOEQ_FALLBACK }));
    """
    js_fallback = run_node_eval(js_script)["fallback"]
    assert len(py_fallback) == len(js_fallback)
    py_names = [m["name"] for m in py_fallback]
    js_names = [m["name"] for m in js_fallback]
    assert py_names == js_names


def test_hid_register_decode_parity():
    """Verify that WebHID decoders match Python register framing for both KTMicro and Moondrop."""
    # 1. KTMicro band register decode
    # Gain: +3.5 dB -> 35 -> 0x0023
    # Freq: 2400 Hz -> 0x0960
    # Q: 1.4 -> 1400 -> 0x0578
    # Type: PK -> 0
    gf_resp = [0x26, 0x00, 0x00, 0x00, 0x52, 0x00, 0x23, 0x00, 0x60, 0x09]
    q_resp = [0x27, 0x00, 0x00, 0x00, 0x52, 0x00, 0x78, 0x05, 0x00, 0x00]

    js_script = f"""
    import {{ decodeKtMicroBandRegisters }} from './modules/hid_transport.js';
    const gfResp = {json.dumps(gf_resp)};
    const qResp = {json.dumps(q_resp)};
    const band = decodeKtMicroBandRegisters(gfResp, qResp, false);
    console.log(JSON.stringify({{ band }}));
    """
    js_band = run_node_eval(js_script)["band"]
    assert js_band["type"] == "PK"
    assert js_band["freq"] == 2400.0
    assert js_band["gain"] == 3.5
    assert js_band["q"] == 1.4

    # 2. Moondrop FreeDSP 64-byte payload decode
    from dac_peq.moondrop import MoondropFreeDSPDevice
    moondrop = MoondropFreeDSPDevice(use_mock=True)
    test_preset = {
        "preamp": -2.5,
        "bands": [
            {"index": 1, "type": "LSQ", "freq": 80.0, "gain": 4.0, "q": 0.7},
            {"index": 2, "type": "PK", "freq": 3200.0, "gain": -2.0, "q": 2.0},
        ],
    }
    with moondrop:
        moondrop.apply_preset(test_preset)
        raw_payload = list(moondrop._dev.last_payload)
        py_read = moondrop.read_current_peq()

    js_script_moon = f"""
    import {{ decodeMoondropReport }} from './modules/hid_transport.js';
    const raw = {json.dumps(raw_payload)};
    const decoded = decodeMoondropReport(raw);
    console.log(JSON.stringify({{ decoded }}));
    """
    js_moon = run_node_eval(js_script_moon)["decoded"]
    assert py_read["preamp"] == js_moon["preamp"]
    assert len(py_read["bands"]) == len(js_moon["bands"]) == 9
    for pb, jb in zip(py_read["bands"][:2], js_moon["bands"][:2]):
        assert pb["type"] == jb["type"]
        assert pb["freq"] == jb["freq"]
        assert pb["gain"] == jb["gain"]
        assert pb["q"] == jb["q"]


