use crate::biquad::{compute_composite_response, generate_log_frequencies};
use crate::models::PeqPreset;

/// Generate Wavelet GraphicEQ formatted string across 127 log frequencies.
pub fn format_wavelet_graphiceq(preset: &PeqPreset) -> String {
    let freqs = generate_log_frequencies(20.0, 20000.0, 127);
    let curve = compute_composite_response(&preset.bands, preset.preamp, &freqs, 48000.0);

    let pairs: Vec<String> = freqs
        .iter()
        .zip(curve.iter())
        .map(|(&f, &db)| format!("{:.1} {:.1}", f, db))
        .collect();

    format!("GraphicEQ: {}\n", pairs.join("; "))
}
