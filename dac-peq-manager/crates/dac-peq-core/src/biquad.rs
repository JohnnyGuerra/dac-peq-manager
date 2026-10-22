use std::f64::consts::PI;

use crate::models::{BiquadBand, FilterType};

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct BiquadCoeffs {
    pub b0: f64,
    pub b1: f64,
    pub b2: f64,
    pub a1: f64,
    pub a2: f64,
    pub fs: f64,
    pub freq: f64,
    pub gain_db: f64,
    pub q: f64,
    pub filter_type: FilterType,
}

impl BiquadCoeffs {
    /// Compute magnitude response in dB at frequency f (Hz).
    pub fn response_at(&self, f: f64) -> f64 {
        let w = 2.0 * PI * f / self.fs;
        let cos_w = w.cos();
        let sin_w = w.sin();
        let cos_2w = (2.0 * w).cos();
        let sin_2w = (2.0 * w).sin();

        let num_re = self.b0 + self.b1 * cos_w + self.b2 * cos_2w;
        let num_im = -self.b1 * sin_w - self.b2 * sin_2w;

        let den_re = 1.0 + self.a1 * cos_w + self.a2 * cos_2w;
        let den_im = -self.a1 * sin_w - self.a2 * sin_2w;

        let num_mag2 = num_re * num_re + num_im * num_im;
        let den_mag2 = den_re * den_re + den_im * den_im;

        if den_mag2 <= 1e-12 {
            return 0.0;
        }

        let mag2 = num_mag2 / den_mag2;
        if mag2 <= 1e-12 {
            return -120.0;
        }

        10.0 * mag2.log10()
    }
}

/// Calculate RBJ Audio EQ Cookbook normalized biquad coefficients.
pub fn calculate_rbj_biquad(
    filter_type: FilterType,
    freq: f64,
    gain_db: f64,
    q: f64,
    fs: f64,
) -> BiquadCoeffs {
    let freq_clamped = freq.max(10.0).min(fs * 0.499);
    let q_clamped = q.max(0.01);

    let w0 = 2.0 * PI * freq_clamped / fs;
    let cos_w0 = w0.cos();
    let sin_w0 = w0.sin();
    let a_amp = 10.0f64.powf(gain_db / 40.0);
    let alpha = sin_w0 / (2.0 * q_clamped);

    let (b0, b1, b2, a0, a1, a2) = match filter_type {
        FilterType::Peaking => {
            let b0 = 1.0 + alpha * a_amp;
            let b1 = -2.0 * cos_w0;
            let b2 = 1.0 - alpha * a_amp;
            let a0 = 1.0 + alpha / a_amp;
            let a1 = -2.0 * cos_w0;
            let a2 = 1.0 - alpha / a_amp;
            (b0, b1, b2, a0, a1, a2)
        }
        FilterType::LowShelf => {
            let two_sqrt_a_alpha = 2.0 * a_amp.sqrt() * alpha;
            let a_plus_1 = a_amp + 1.0;
            let a_minus_1 = a_amp - 1.0;

            let b0 = a_amp * (a_plus_1 - a_minus_1 * cos_w0 + two_sqrt_a_alpha);
            let b1 = 2.0 * a_amp * (a_minus_1 - a_plus_1 * cos_w0);
            let b2 = a_amp * (a_plus_1 - a_minus_1 * cos_w0 - two_sqrt_a_alpha);
            let a0 = a_plus_1 + a_minus_1 * cos_w0 + two_sqrt_a_alpha;
            let a1 = -2.0 * (a_minus_1 + a_plus_1 * cos_w0);
            let a2 = a_plus_1 + a_minus_1 * cos_w0 - two_sqrt_a_alpha;
            (b0, b1, b2, a0, a1, a2)
        }
        FilterType::HighShelf => {
            let two_sqrt_a_alpha = 2.0 * a_amp.sqrt() * alpha;
            let a_plus_1 = a_amp + 1.0;
            let a_minus_1 = a_amp - 1.0;

            let b0 = a_amp * (a_plus_1 + a_minus_1 * cos_w0 + two_sqrt_a_alpha);
            let b1 = -2.0 * a_amp * (a_minus_1 + a_plus_1 * cos_w0);
            let b2 = a_amp * (a_plus_1 - a_minus_1 * cos_w0 - two_sqrt_a_alpha);
            let a0 = a_plus_1 - a_minus_1 * cos_w0 + two_sqrt_a_alpha;
            let a1 = 2.0 * (a_minus_1 - a_plus_1 * cos_w0);
            let a2 = a_plus_1 - a_minus_1 * cos_w0 - two_sqrt_a_alpha;
            (b0, b1, b2, a0, a1, a2)
        }
        FilterType::Bypass => (1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
    };

    let norm_a0 = if a0.abs() < 1e-12 { 1.0 } else { a0 };

    BiquadCoeffs {
        b0: b0 / norm_a0,
        b1: b1 / norm_a0,
        b2: b2 / norm_a0,
        a1: a1 / norm_a0,
        a2: a2 / norm_a0,
        fs,
        freq: freq_clamped,
        gain_db,
        q: q_clamped,
        filter_type,
    }
}

/// Compute composite EQ curve (preamp + all band responses) at given frequencies.
pub fn compute_composite_response(
    bands: &[BiquadBand],
    preamp_db: f64,
    frequencies: &[f64],
    fs: f64,
) -> Vec<f64> {
    let filters: Vec<BiquadCoeffs> = bands
        .iter()
        .map(|b| calculate_rbj_biquad(b.filter_type, b.freq, b.gain, b.q, fs))
        .collect();

    frequencies
        .iter()
        .map(|&f| {
            let mut val = preamp_db;
            for filt in &filters {
                val += filt.response_at(f);
            }
            val
        })
        .collect()
}

/// Generate logarithmically spaced frequencies between f_min and f_max.
pub fn generate_log_frequencies(f_min: f64, f_max: f64, points: usize) -> Vec<f64> {
    if points <= 1 {
        return vec![f_min];
    }
    let log_min = f_min.log10();
    let log_max = f_max.log10();
    let step = (log_max - log_min) / (points as f64 - 1.0);
    (0..points)
        .map(|i| 10.0f64.powf(log_min + i as f64 * step))
        .collect()
}

/// Compute the maximum composite filter gain in dB across 20 Hz - 20 kHz (without preamp).
pub fn calculate_peak_composite_gain(bands: &[BiquadBand], fs: f64, points: usize) -> f64 {
    if bands.is_empty() {
        return 0.0;
    }
    let freqs = generate_log_frequencies(20.0, 20000.0, points);
    let curve = compute_composite_response(bands, 0.0, &freqs, fs);
    curve.into_iter().fold(f64::NEG_INFINITY, f64::max)
}

/// Calculate recommended negative preamp (dB) to prevent inter-sample DAC clipping.
pub fn calculate_recommended_preamp(bands: &[BiquadBand], headroom_db: f64, fs: f64) -> f64 {
    let peak = calculate_peak_composite_gain(bands, fs, 500);
    if peak <= 0.0 {
        return 0.0;
    }
    let rec = -(peak + headroom_db);
    (rec * 2.0).round() / 2.0
}

/// Inspect PEQ bands for acoustic pitfalls, coupler artifacts, and high-Q issues.
pub fn lint_acoustic_bands(bands: &[BiquadBand]) -> Vec<String> {
    let mut warnings = Vec::new();

    for (i, b) in bands.iter().enumerate() {
        let idx = i + 1;
        // 1. 711 coupler resonance spike check
        if (7400.0..=9600.0).contains(&b.freq) && b.q > 2.0 && b.gain <= -3.0 {
            warnings.push(format!(
                "Band {idx} ({:.0} Hz, {:+.1} dB, Q={:.2}) matches an IEC 60318-4 (711) coupler half-wave resonance artifact. Consider smoothing Q <= 1.4 or using a High-Shelf (HSQ).",
                b.freq, b.gain, b.q
            ));
        }

        // 2. Extreme boost check
        if b.gain > 6.0 {
            warnings.push(format!(
                "Band {idx} ({:.0} Hz, {:+.1} dB) exceeds +6.0 dB boost. Ensure adequate digital preamp attenuation to prevent delta-sigma modulator saturation.",
                b.freq, b.gain
            ));
        }

        // 3. High-Q ringing check
        if b.q > 5.0 && b.filter_type != FilterType::Bypass {
            warnings.push(format!(
                "Band {idx} ({:.0} Hz, Q={:.2}) has ultra-narrow Q > 5.0. Narrow IIR biquad filters produce significant phase shifts and group delay ringing.",
                b.freq, b.q
            ));
        }
    }

    warnings
}
