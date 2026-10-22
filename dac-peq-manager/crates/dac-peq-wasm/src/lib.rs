use std::str::FromStr;
use wasm_bindgen::prelude::*;

use dac_peq_core::models::{BiquadBand, FilterType, PeqPreset};
use dac_peq_core::{
    calculate_curve_difference, calculate_rbj_biquad, compute_composite_response,
    decimate_bands, encode_factory_reset, encode_nvram_commit, encode_preset_payload,
    format_equalizer_apo, format_pipewire_filter_chain, format_wavelet_graphiceq,
    generate_log_frequencies, is_conexant_cx31993, DEFAULT_CX31993_SINK,
};

#[wasm_bindgen]
pub fn wasm_version() -> String {
    "0.2.0".to_string()
}

#[wasm_bindgen]
pub fn calculate_biquad(
    filter_type: &str,
    freq: f64,
    gain_db: f64,
    q: f64,
    fs: f64,
) -> Vec<f64> {
    let ftype = FilterType::from_str(filter_type).unwrap_or(FilterType::Peaking);
    let coeffs = calculate_rbj_biquad(ftype, freq, gain_db, q, fs);
    vec![coeffs.b0, coeffs.b1, coeffs.b2, coeffs.a1, coeffs.a2]
}

#[wasm_bindgen]
pub fn compute_composite_curve(
    bands_json: &str,
    preamp_db: f64,
    points: usize,
    fs: f64,
) -> std::result::Result<Vec<f64>, JsValue> {
    let bands: Vec<BiquadBand> = serde_json::from_str(bands_json)
        .map_err(|e| JsValue::from_str(&format!("Invalid bands JSON: {e}")))?;
    let freqs = generate_log_frequencies(20.0, 20000.0, points);
    Ok(compute_composite_response(&bands, preamp_db, &freqs, fs))
}

#[wasm_bindgen]
pub fn calculate_peak_gain(bands_json: &str, fs: f64) -> std::result::Result<f64, JsValue> {
    let bands: Vec<BiquadBand> = serde_json::from_str(bands_json)
        .map_err(|e| JsValue::from_str(&format!("Invalid bands JSON: {e}")))?;
    Ok(dac_peq_core::calculate_peak_composite_gain(&bands, fs, 500))
}

#[wasm_bindgen]
pub fn calculate_recommended_preamp(
    bands_json: &str,
    headroom_db: f64,
    fs: f64,
) -> std::result::Result<f64, JsValue> {
    let bands: Vec<BiquadBand> = serde_json::from_str(bands_json)
        .map_err(|e| JsValue::from_str(&format!("Invalid bands JSON: {e}")))?;
    Ok(dac_peq_core::calculate_recommended_preamp(&bands, headroom_db, fs))
}

#[wasm_bindgen]
pub fn decimate_bands_json(
    bands_json: &str,
    target_bands: usize,
    refit_gains: bool,
    fs: f64,
) -> std::result::Result<String, JsValue> {
    let bands: Vec<BiquadBand> = serde_json::from_str(bands_json)
        .map_err(|e| JsValue::from_str(&format!("Invalid bands JSON: {e}")))?;
    let decimated = decimate_bands(&bands, target_bands, refit_gains, fs);
    serde_json::to_string(&decimated)
        .map_err(|e| JsValue::from_str(&format!("Serialization error: {e}")))
}

#[wasm_bindgen]
pub fn calculate_curve_difference_json(
    bands_a_json: &str,
    preamp_a: f64,
    bands_b_json: &str,
    preamp_b: f64,
    fs: f64,
    points: usize,
) -> std::result::Result<String, JsValue> {
    let bands_a: Vec<BiquadBand> = serde_json::from_str(bands_a_json)
        .map_err(|e| JsValue::from_str(&format!("Invalid bands A JSON: {e}")))?;
    let bands_b: Vec<BiquadBand> = serde_json::from_str(bands_b_json)
        .map_err(|e| JsValue::from_str(&format!("Invalid bands B JSON: {e}")))?;
    let diff = calculate_curve_difference(&bands_a, preamp_a, &bands_b, preamp_b, fs, points);
    serde_json::to_string(&diff)
        .map_err(|e| JsValue::from_str(&format!("Serialization error: {e}")))
}

#[wasm_bindgen]
pub fn encode_ktmicro_payload(
    preset_json: &str,
    vid: u16,
    pid: u16,
    slot_id: u8,
    compensate_2x: bool,
    commit_nvram: bool,
) -> std::result::Result<js_sys::Array, JsValue> {
    let preset: PeqPreset = serde_json::from_str(preset_json)
        .map_err(|e| JsValue::from_str(&format!("Invalid preset JSON: {e}")))?;

    let reports = encode_preset_payload(&preset, vid, pid, slot_id, compensate_2x, commit_nvram)
        .map_err(|e| JsValue::from_str(&e.to_string()))?;

    let arr = js_sys::Array::new();
    for r in reports {
        let u8_arr = js_sys::Uint8Array::from(r.as_bytes());
        arr.push(&u8_arr);
    }
    Ok(arr)
}

#[wasm_bindgen]
pub fn encode_factory_reset_report() -> js_sys::Uint8Array {
    let rpt = encode_factory_reset();
    js_sys::Uint8Array::from(rpt.as_bytes())
}

#[wasm_bindgen]
pub fn encode_nvram_commit_report() -> js_sys::Uint8Array {
    let rpt = encode_nvram_commit();
    js_sys::Uint8Array::from(rpt.as_bytes())
}

#[wasm_bindgen]
pub fn check_is_conexant_cx31993(vid: u16, pid: u16, product_name: Option<String>) -> bool {
    is_conexant_cx31993(vid, pid, product_name.as_deref())
}

#[wasm_bindgen]
pub fn export_pipewire_conf(preset_json: &str, sink_target: Option<String>) -> std::result::Result<String, JsValue> {
    let preset: PeqPreset = serde_json::from_str(preset_json)
        .map_err(|e| JsValue::from_str(&format!("Invalid preset JSON: {e}")))?;
    let sink = sink_target.unwrap_or_else(|| DEFAULT_CX31993_SINK.to_string());
    format_pipewire_filter_chain(&preset, &sink).map_err(|e| JsValue::from_str(&e.to_string()))
}

#[wasm_bindgen]
pub fn export_apo_txt(preset_json: &str) -> std::result::Result<String, JsValue> {
    let preset: PeqPreset = serde_json::from_str(preset_json)
        .map_err(|e| JsValue::from_str(&format!("Invalid preset JSON: {e}")))?;
    Ok(format_equalizer_apo(&preset))
}

#[wasm_bindgen]
pub fn export_wavelet_txt(preset_json: &str) -> std::result::Result<String, JsValue> {
    let preset: PeqPreset = serde_json::from_str(preset_json)
        .map_err(|e| JsValue::from_str(&format!("Invalid preset JSON: {e}")))?;
    Ok(format_wavelet_graphiceq(&preset))
}
