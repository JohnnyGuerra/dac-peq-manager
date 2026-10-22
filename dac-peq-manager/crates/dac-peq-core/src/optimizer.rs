use crate::biquad::{compute_composite_response, generate_log_frequencies};
use crate::models::{BiquadBand, CurveDifference, FilterType};

pub fn score_band(b: &BiquadBand) -> f64 {
    let g = b.gain.abs();
    let f = b.freq;
    let q = b.q;

    // Core anchor shelves receive top priority
    if b.filter_type == FilterType::LowShelf && f <= 150.0 {
        return 100.0 + g * 3.0;
    }
    if b.filter_type == FilterType::HighShelf && f >= 7000.0 {
        return 90.0 + g * 3.0;
    }

    // Penalize narrow IEC 60318-4 coupler insertion artifacts
    if (7000.0..=8500.0).contains(&f) && q >= 2.5 {
        return g * 0.35;
    }

    // Weighted by human ear sensitivity landmarks
    if (2000.0..=4000.0).contains(&f) {
        return g * 2.5;
    }
    if (150.0..=600.0).contains(&f) {
        return g * 1.8;
    }
    if (4000.0..=7000.0).contains(&f) {
        return g * 1.5;
    }

    g
}

pub fn refit_decimated_gains(
    original_bands: &[BiquadBand],
    decimated_bands: &[BiquadBand],
    fs: f64,
) -> Vec<BiquadBand> {
    if decimated_bands.is_empty() || original_bands.len() <= decimated_bands.len() {
        return decimated_bands.to_vec();
    }

    let freqs = generate_log_frequencies(20.0, 20000.0, 64);
    let target_curve = compute_composite_response(original_bands, 0.0, &freqs, fs);
    let mut current_bands = decimated_bands.to_vec();

    let get_sse = |bands: &[BiquadBand]| -> f64 {
        let curve = compute_composite_response(bands, 0.0, &freqs, fs);
        curve
            .iter()
            .zip(target_curve.iter())
            .map(|(c, t)| {
                let diff = c - t;
                diff * diff
            })
            .sum()
    };

    let mut current_sse = get_sse(&current_bands);
    let deltas = [-1.5, -1.0, -0.5, -0.2, 0.2, 0.5, 1.0, 1.5];

    for _ in 0..2 {
        for i in 0..current_bands.len() {
            let mut best_gain = current_bands[i].gain;
            let mut best_sse = current_sse;
            let orig_gain = best_gain;

            for &d in &deltas {
                let cand = (orig_gain + d * 100.0).round() / 100.0;
                if !(-18.0..=18.0).contains(&cand) {
                    continue;
                }
                current_bands[i].gain = cand;
                let cand_sse = get_sse(&current_bands);
                if cand_sse < best_sse - 1e-6 {
                    best_sse = cand_sse;
                    best_gain = cand;
                }
            }
            current_bands[i].gain = best_gain;
            current_sse = best_sse;
        }
    }

    current_bands
}

pub fn decimate_bands(
    bands: &[BiquadBand],
    target_bands: usize,
    refit_gains: bool,
    fs: f64,
) -> Vec<BiquadBand> {
    if bands.is_empty() {
        return Vec::new();
    }

    let target_count = target_bands.max(1);

    if bands.len() <= target_count {
        let mut out = bands.to_vec();
        while out.len() < target_count {
            out.push(BiquadBand::new(FilterType::Peaking, 1000.0, 0.0, 1.0));
        }
        for (i, b) in out.iter_mut().enumerate() {
            b.index = Some(i + 1);
        }
        return out;
    }

    // Build logarithmic frequency bins across 20 Hz - 20000 Hz
    let f_min = 20.0f64;
    let f_max = 20000.0f64;
    let l_min = f_min.log10();
    let l_max = f_max.log10();

    let mut bins = Vec::new();
    for i in 0..target_count {
        let b_lo = 10.0f64.powf(l_min + i as f64 * (l_max - l_min) / target_count as f64);
        let b_hi = 10.0f64.powf(l_min + (i + 1) as f64 * (l_max - l_min) / target_count as f64);
        bins.push((b_lo, b_hi));
    }

    let mut selected: Vec<BiquadBand> = Vec::new();
    let mut used_indices = std::collections::HashSet::new();

    for (b_lo, b_hi) in bins {
        let candidates: Vec<(usize, &BiquadBand)> = bands
            .iter()
            .enumerate()
            .filter(|(idx, b)| !used_indices.contains(idx) && (b_lo..b_hi).contains(&b.freq))
            .collect();

        if let Some((best_idx, best_b)) = candidates.into_iter().max_by(|a, b| {
            score_band(a.1)
                .partial_cmp(&score_band(b.1))
                .unwrap_or(std::cmp::Ordering::Equal)
        }) {
            selected.push(best_b.clone());
            used_indices.insert(best_idx);
        }
    }

    // Fill remaining unfilled bins from highest-scoring global candidates
    if selected.len() < target_count {
        let mut remaining: Vec<(usize, &BiquadBand)> = bands
            .iter()
            .enumerate()
            .filter(|(idx, _)| !used_indices.contains(idx))
            .collect();

        remaining.sort_by(|a, b| {
            score_band(b.1)
                .partial_cmp(&score_band(a.1))
                .unwrap_or(std::cmp::Ordering::Equal)
        });

        for (idx, b) in remaining.into_iter().take(target_count - selected.len()) {
            selected.push(b.clone());
            used_indices.insert(idx);
        }
    }

    if refit_gains && bands.len() > selected.len() {
        selected = refit_decimated_gains(bands, &selected, fs);
    }

    selected.sort_by(|a, b| {
        a.freq
            .partial_cmp(&b.freq)
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    for (i, b) in selected.iter_mut().enumerate() {
        b.index = Some(i + 1);
    }

    selected
}

pub fn calculate_curve_difference(
    bands_a: &[BiquadBand],
    preamp_a: f64,
    bands_b: &[BiquadBand],
    preamp_b: f64,
    fs: f64,
    points: usize,
) -> CurveDifference {
    let freqs = generate_log_frequencies(20.0, 20000.0, points);
    let curve_a = compute_composite_response(bands_a, preamp_a, &freqs, fs);
    let curve_b = compute_composite_response(bands_b, preamp_b, &freqs, fs);

    let mut sum_sq: f64 = 0.0;
    let mut pinna_sum_sq: f64 = 0.0;
    let mut pinna_count: usize = 0;
    let mut max_diff: f64 = 0.0;
    let mut max_freq: f64 = 1000.0;

    for (i, (&a, &b)) in curve_a.iter().zip(curve_b.iter()).enumerate() {
        let diff = a - b;
        sum_sq += diff * diff;
        if diff.abs() > max_diff.abs() {
            max_diff = diff;
            max_freq = freqs[i];
        }
        if (2000.0..=4000.0).contains(&freqs[i]) {
            pinna_sum_sq += diff * diff;
            pinna_count += 1;
        }
    }

    let rms = if !freqs.is_empty() {
        (sum_sq / freqs.len() as f64).sqrt()
    } else {
        0.0
    };

    let pinna_rms = if pinna_count > 0 {
        (pinna_sum_sq / pinna_count as f64).sqrt()
    } else {
        0.0
    };

    CurveDifference {
        rms_db: (rms * 100.0).round() / 100.0,
        max_diff_db: (max_diff * 100.0).round() / 100.0,
        max_diff_freq: (max_freq * 10.0).round() / 10.0,
        pinna_rms_db: (pinna_rms * 100.0).round() / 100.0,
    }
}
