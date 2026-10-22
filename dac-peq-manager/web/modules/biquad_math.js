/**
 * Audio EQ Cookbook (Robert Bristow-Johnson) discrete biquad filter engine,
 * composite frequency response evaluator, acoustic coupler artifact linter,
 * and N-band psychoacoustic landmark decimation.
 *
 * Mathematically synchronized with Python `src/dac_peq/biquad.py` and verified
 * via `tests/test_cross_engine_parity.py`.
 */

export function calculateRBJCoeffs(type, freq, gainDb, q, fs = 48000.0) {
  const ftype = String(type || "PK").toUpperCase().replace(/[- ]/g, "_");
  const f = Math.max(10.0, Math.min(Number(freq), fs * 0.499));
  const Q = Math.max(0.01, Number(q));
  const w0 = (2.0 * Math.PI * f) / fs;
  const cosW0 = Math.cos(w0);
  const sinW0 = Math.sin(w0);
  const A = Math.pow(10.0, Number(gainDb) / 40.0);
  const alpha = sinW0 / (2.0 * Q);

  let b0 = 1.0, b1 = 0.0, b2 = 0.0, a0 = 1.0, a1 = 0.0, a2 = 0.0;

  if (ftype === "PK" || ftype === "PEAK" || ftype === "PEAKING") {
    b0 = 1.0 + alpha * A;
    b1 = -2.0 * cosW0;
    b2 = 1.0 - alpha * A;
    a0 = 1.0 + alpha / A;
    a1 = -2.0 * cosW0;
    a2 = 1.0 - alpha / A;
  } else if (ftype === "LSQ" || ftype === "LOW_SHELF" || ftype === "LOWSHELF") {
    const twoSqrtAAlpha = 2.0 * Math.sqrt(A) * alpha;
    const aPlus1 = A + 1.0;
    const aMinus1 = A - 1.0;
    b0 = A * (aPlus1 - aMinus1 * cosW0 + twoSqrtAAlpha);
    b1 = 2.0 * A * (aMinus1 - aPlus1 * cosW0);
    b2 = A * (aPlus1 - aMinus1 * cosW0 - twoSqrtAAlpha);
    a0 = aPlus1 + aMinus1 * cosW0 + twoSqrtAAlpha;
    a1 = -2.0 * (aMinus1 + aPlus1 * cosW0);
    a2 = aPlus1 + aMinus1 * cosW0 - twoSqrtAAlpha;
  } else if (ftype === "HSQ" || ftype === "HIGH_SHELF" || ftype === "HIGHSHELF") {
    const twoSqrtAAlpha = 2.0 * Math.sqrt(A) * alpha;
    const aPlus1 = A + 1.0;
    const aMinus1 = A - 1.0;
    b0 = A * (aPlus1 + aMinus1 * cosW0 + twoSqrtAAlpha);
    b1 = -2.0 * A * (aMinus1 + aPlus1 * cosW0);
    b2 = A * (aPlus1 + aMinus1 * cosW0 - twoSqrtAAlpha);
    a0 = aPlus1 - aMinus1 * cosW0 + twoSqrtAAlpha;
    a1 = 2.0 * (aMinus1 - aPlus1 * cosW0);
    a2 = aPlus1 - aMinus1 * cosW0 - twoSqrtAAlpha;
  }

  if (Math.abs(a0) < 1e-12) a0 = 1.0;

  return {
    b0: b0 / a0,
    b1: b1 / a0,
    b2: b2 / a0,
    a1: a1 / a0,
    a2: a2 / a0,
  };
}

export function evaluateBiquadAt(coeffs, freq, fs = 48000.0) {
  const w = (2.0 * Math.PI * freq) / fs;
  const cosW = Math.cos(w);
  const sinW = Math.sin(w);
  const cos2W = Math.cos(2.0 * w);
  const sin2W = Math.sin(2.0 * w);

  const numRe = coeffs.b0 + coeffs.b1 * cosW + coeffs.b2 * cos2W;
  const numIm = -coeffs.b1 * sinW - coeffs.b2 * sin2W;

  const denRe = 1.0 + coeffs.a1 * cosW + coeffs.a2 * cos2W;
  const denIm = -coeffs.a1 * sinW - coeffs.a2 * sin2W;

  const numMag2 = numRe * numRe + numIm * numIm;
  const denMag2 = denRe * denRe + denIm * denIm;

  if (denMag2 <= 1e-12) return 0.0;
  const mag2 = numMag2 / denMag2;
  return mag2 <= 1e-12 ? -120.0 : 10.0 * Math.log10(mag2);
}

export function computeCompositeCurve(bands, preampDb, frequencies, fs = 48000.0) {
  const filters = bands.map((b) => calculateRBJCoeffs(b.type, b.freq, b.gain, b.q, fs));
  return frequencies.map((f) => {
    let db = Number(preampDb);
    for (const filt of filters) {
      db += evaluateBiquadAt(filt, f, fs);
    }
    return db;
  });
}

export function generateLogFrequencies(points = 127, fMin = 20.0, fMax = 20000.0) {
  const logMin = Math.log10(fMin);
  const logMax = Math.log10(fMax);
  const step = (logMax - logMin) / (points - 1);
  return Array.from({ length: points }, (_, i) => Math.pow(10.0, logMin + i * step));
}

export function calculatePeakCompositeGain(bands, points = 500, fs = 48000.0) {
  if (!bands || bands.length === 0) return 0.0;
  const frequencies = generateLogFrequencies(points, 20.0, 20000.0);
  const responses = computeCompositeCurve(bands, 0.0, frequencies, fs);
  return Math.max(...responses);
}

export function calculateRecommendedPreamp(bands, headroom = 0.5, fs = 48000.0) {
  const peak = calculatePeakCompositeGain(bands, 500, fs);
  if (peak <= 0.0) return 0.0;
  const rec = -(peak + headroom);
  return Math.round(rec * 2.0) / 2.0;
}

export function calculateCurveDifference(bandsA, preampA, bandsB, preampB, fs = 48000.0, points = 220) {
  const frequencies = generateLogFrequencies(points, 20.0, 20000.0);
  const curveA = computeCompositeCurve(bandsA, preampA, frequencies, fs);
  const curveB = computeCompositeCurve(bandsB, preampB, frequencies, fs);

  let sumSq = 0.0;
  let pinnaSumSq = 0.0;
  let pinnaCount = 0;
  let maxDiff = 0.0;
  let maxFreq = 1000.0;

  for (let i = 0; i < frequencies.length; i++) {
    const f = frequencies[i];
    const diff = curveA[i] - curveB[i];
    sumSq += diff * diff;
    if (Math.abs(diff) > Math.abs(maxDiff)) {
      maxDiff = diff;
      maxFreq = f;
    }
    if (f >= 2000.0 && f <= 4000.0) {
      pinnaSumSq += diff * diff;
      pinnaCount += 1;
    }
  }

  const rms = frequencies.length > 0 ? Math.sqrt(sumSq / frequencies.length) : 0.0;
  const pinnaRms = pinnaCount > 0 ? Math.sqrt(pinnaSumSq / pinnaCount) : 0.0;

  return {
    rms_db: Number(rms.toFixed(2)),
    max_diff_db: Number(maxDiff.toFixed(2)),
    max_diff_freq: Number(maxFreq.toFixed(1)),
    pinna_rms_db: Number(pinnaRms.toFixed(2)),
  };
}

export function lintAcousticBands(bands) {
  const warnings = [];
  bands.forEach((b, i) => {
    const idx = i + 1;
    const freq = Number(b.freq ?? 1000);
    const gain = Number(b.gain ?? 0);
    const q = Number(b.q ?? 1.0);
    const ftype = String(b.type || "PK").toUpperCase();

    if (freq >= 7400 && freq <= 9600 && q > 2.0 && gain <= -3.0) {
      warnings.push(
        `Band ${idx} (${Math.round(freq)} Hz, ${gain > 0 ? "+" : ""}${gain.toFixed(1)} dB, Q=${q.toFixed(2)}) matches a common IEC 60318-4 (711) coupler artificial resonance spike. Deep, narrow cuts here can hollow out natural treble on real ears. Consider smoothing Q &le; 1.4 or using a High-Shelf.`
      );
    }

    if (gain > 6.0) {
      warnings.push(
        `Band ${idx} (${Math.round(freq)} Hz, +${gain.toFixed(1)} dB) exceeds +6 dB boost. Ensure digital preamp headroom to avoid clipping.`
      );
    }

    if (q > 5.0 && ftype !== "NOTCH") {
      warnings.push(
        `Band ${idx} (${Math.round(freq)} Hz, Q=${q.toFixed(2)}) has ultra-narrow Q > 5.0 which may cause audible phase ringing.`
      );
    }
  });
  return warnings;
}

export function refitDecimatedGains(originalBands, decimatedBands, fs = 48000.0) {
  if (!decimatedBands || decimatedBands.length === 0 || originalBands.length <= decimatedBands.length) {
    return decimatedBands.map((b) => ({ ...b }));
  }

  const freqs = generateLogFrequencies(64, 20.0, 20000.0);
  const targetCurve = computeCompositeCurve(originalBands, 0.0, freqs, fs);
  const currentBands = decimatedBands.map((b) => ({ ...b }));

  function getSse(bList) {
    const curve = computeCompositeCurve(bList, 0.0, freqs, fs);
    let sse = 0.0;
    for (let i = 0; i < freqs.length; i++) {
      const diff = curve[i] - targetCurve[i];
      sse += diff * diff;
    }
    return sse;
  }

  let currentSse = getSse(currentBands);
  const deltas = [-1.5, -1.0, -0.5, -0.2, 0.2, 0.5, 1.0, 1.5];

  for (let pass = 0; pass < 2; pass++) {
    for (let bi = 0; bi < currentBands.length; bi++) {
      const b = currentBands[bi];
      let bestGain = Number(b.gain ?? 0.0);
      let bestSse = currentSse;
      const origGain = bestGain;

      for (let di = 0; di < deltas.length; di++) {
        const d = deltas[di];
        const cand = Math.round((origGain + d) * 100) / 100;
        if (cand < -18.0 || cand > 18.0) continue;
        b.gain = cand;
        const candSse = getSse(currentBands);
        if (candSse < bestSse - 1e-6) {
          bestSse = candSse;
          bestGain = cand;
        }
      }
      b.gain = bestGain;
      currentSse = bestSse;
    }
  }

  return currentBands;
}

export function decimateBands(bands, targetBands = 5, refitGains = true, fs = 48000.0) {
  if (!bands || bands.length === 0) return [];
  const target = Math.max(1, targetBands);

  if (bands.length <= target) {
    const out = bands.map((b) => ({ ...b }));
    while (out.length < target) {
      out.push({ type: "PK", freq: 1000.0, gain: 0.0, q: 1.0 });
    }
    return out.map((b, i) => ({ ...b, index: i + 1 }));
  }

  function score(b) {
    const g = Math.abs(Number(b.gain ?? 0.0));
    const f = Number(b.freq ?? 1000.0);
    const t = String(b.type || "PK").toUpperCase();
    const q = Number(b.q ?? 1.0);

    if ((t === "LSQ" || t === "LOW_SHELF" || t === "LOWSHELF") && f <= 150) {
      return 100.0 + g * 3.0;
    }
    if ((t === "HSQ" || t === "HIGH_SHELF" || t === "HIGHSHELF") && f >= 7000) {
      return 90.0 + g * 3.0;
    }
    if (f >= 7000 && f <= 8500 && q >= 2.5) {
      return g * 0.35;
    }
    if (f >= 2000 && f <= 4000) {
      return g * 2.5;
    }
    if (f >= 150 && f <= 600) {
      return g * 1.8;
    }
    if (f >= 4000 && f <= 7000) {
      return g * 1.5;
    }
    return g;
  }

  const fMin = 20.0, fMax = 20000.0;
  const lMin = Math.log10(fMin), lMax = Math.log10(fMax);
  const bins = [];
  for (let i = 0; i < target; i++) {
    const bLo = Math.pow(10, lMin + (i * (lMax - lMin)) / target);
    const bHi = Math.pow(10, lMin + ((i + 1) * (lMax - lMin)) / target);
    bins.push({ lo: bLo, hi: bHi });
  }

  let selected = [];
  const used = new Set();

  for (const bin of bins) {
    const candidates = bands
      .map((b, idx) => ({ b, idx }))
      .filter(({ b, idx }) => !used.has(idx) && Number(b.freq ?? 0.0) >= bin.lo && Number(b.freq ?? 0.0) < bin.hi);
    if (candidates.length > 0) {
      candidates.sort((a, b) => score(b.b) - score(a.b));
      const best = candidates[0];
      selected.push({ ...best.b });
      used.add(best.idx);
    }
  }

  if (selected.length < target) {
    const remaining = bands
      .map((b, idx) => ({ b, idx }))
      .filter(({ idx }) => !used.has(idx))
      .sort((a, b) => score(b.b) - score(a.b));
    const needed = target - selected.length;
    for (let i = 0; i < needed; i++) {
      if (remaining[i]) {
        selected.push({ ...remaining[i].b });
        used.add(remaining[i].idx);
      }
    }
  }

  if (refitGains && bands.length > selected.length) {
    selected = refitDecimatedGains(bands, selected, fs);
  }

  selected.sort((a, b) => Number(a.freq ?? 1000.0) - Number(b.freq ?? 1000.0));
  return selected.map((b, i) => ({ ...b, index: i + 1 }));
}
