/**
 * AutoEq & Squiglink Community Measurement Database Client with Offline Fallback Snapshot.
 * Contains the top 15 Reddit r/iems & r/inearfidelity benchmark profiles so the Web UI
 * works 100% offline or when GitHub Raw is unreachable.
 */

export const AUTOEQ_INDEX_URL = "https://raw.githubusercontent.com/jaakkopasanen/AutoEq/master/results/INDEX.md";
export const AUTOEQ_RAW_BASE = "https://raw.githubusercontent.com/jaakkopasanen/AutoEq/master/results";

export const OFFLINE_AUTOEQ_FALLBACK = [
  {
    name: "Truthear x Crinacle Zero:RED",
    source: "crinacle",
    path: "crinacle/711 in-ear/Truthear x Crinacle Zero RED",
    preamp: -4.2,
    bands: [
      { index: 1, type: "LSQ", freq: 105.0, gain: 3.8, q: 0.70 },
      { index: 2, type: "PK", freq: 185.0, gain: -1.4, q: 1.35 },
      { index: 3, type: "PK", freq: 420.0, gain: 0.9, q: 1.40 },
      { index: 4, type: "PK", freq: 1350.0, gain: -1.2, q: 1.80 },
      { index: 5, type: "PK", freq: 2850.0, gain: 2.1, q: 1.60 },
      { index: 6, type: "PK", freq: 4300.0, gain: -1.6, q: 2.40 },
      { index: 7, type: "PK", freq: 6100.0, gain: 1.8, q: 2.20 },
      { index: 8, type: "PK", freq: 7800.0, gain: -2.5, q: 3.50 },
      { index: 9, type: "PK", freq: 9400.0, gain: 1.4, q: 2.80 },
      { index: 10, type: "HSQ", freq: 10500.0, gain: 1.5, q: 0.70 },
    ],
  },
  {
    name: "Truthear Hexa",
    source: "Super Review",
    path: "Super Review/in-ear/Truthear Hexa",
    preamp: -5.1,
    bands: [
      { index: 1, type: "LSQ", freq: 105.0, gain: 5.2, q: 0.70 },
      { index: 2, type: "PK", freq: 210.0, gain: -1.1, q: 1.40 },
      { index: 3, type: "PK", freq: 550.0, gain: 0.8, q: 1.30 },
      { index: 4, type: "PK", freq: 1450.0, gain: -1.5, q: 1.70 },
      { index: 5, type: "PK", freq: 2950.0, gain: 2.4, q: 1.50 },
      { index: 6, type: "PK", freq: 4600.0, gain: -1.2, q: 2.30 },
      { index: 7, type: "PK", freq: 6400.0, gain: -2.0, q: 2.60 },
      { index: 8, type: "PK", freq: 8100.0, gain: -3.1, q: 3.40 },
      { index: 9, type: "PK", freq: 9800.0, gain: 1.2, q: 2.50 },
      { index: 10, type: "HSQ", freq: 10500.0, gain: -1.0, q: 0.70 },
    ],
  },
  {
    name: "Moondrop Chu II",
    source: "Super Review",
    path: "Super Review/in-ear/Moondrop Chu 2",
    preamp: -3.6,
    bands: [
      { index: 1, type: "LSQ", freq: 105.0, gain: 1.8, q: 0.70 },
      { index: 2, type: "PK", freq: 195.0, gain: -2.1, q: 1.20 },
      { index: 3, type: "PK", freq: 480.0, gain: 1.2, q: 1.30 },
      { index: 4, type: "PK", freq: 1600.0, gain: -0.9, q: 1.90 },
      { index: 5, type: "PK", freq: 2700.0, gain: 2.3, q: 1.50 },
      { index: 6, type: "PK", freq: 4400.0, gain: -1.8, q: 2.40 },
      { index: 7, type: "PK", freq: 5900.0, gain: -2.4, q: 2.70 },
      { index: 8, type: "PK", freq: 7900.0, gain: -3.2, q: 3.50 },
      { index: 9, type: "PK", freq: 9600.0, gain: 1.6, q: 2.60 },
      { index: 10, type: "HSQ", freq: 10500.0, gain: 1.2, q: 0.70 },
    ],
  },
  {
    name: "Moondrop Aria",
    source: "crinacle",
    path: "crinacle/711 in-ear/Moondrop Aria",
    preamp: -4.4,
    bands: [
      { index: 1, type: "LSQ", freq: 105.0, gain: 2.4, q: 0.70 },
      { index: 2, type: "PK", freq: 190.0, gain: -2.5, q: 1.15 },
      { index: 3, type: "PK", freq: 520.0, gain: 1.3, q: 1.25 },
      { index: 4, type: "PK", freq: 1400.0, gain: -1.1, q: 1.85 },
      { index: 5, type: "PK", freq: 2900.0, gain: 3.1, q: 1.45 },
      { index: 6, type: "PK", freq: 4500.0, gain: -1.4, q: 2.30 },
      { index: 7, type: "PK", freq: 6100.0, gain: -2.1, q: 2.50 },
      { index: 8, type: "PK", freq: 8000.0, gain: -3.4, q: 3.60 },
      { index: 9, type: "PK", freq: 9500.0, gain: 1.8, q: 2.70 },
      { index: 10, type: "HSQ", freq: 10500.0, gain: 2.0, q: 0.70 },
    ],
  },
  {
    name: "Moondrop Blessing 3",
    source: "Super Review",
    path: "Super Review/in-ear/Moondrop Blessing 3",
    preamp: -5.6,
    bands: [
      { index: 1, type: "LSQ", freq: 105.0, gain: 5.8, q: 0.70 },
      { index: 2, type: "PK", freq: 220.0, gain: -0.8, q: 1.40 },
      { index: 3, type: "PK", freq: 580.0, gain: 0.7, q: 1.35 },
      { index: 4, type: "PK", freq: 1500.0, gain: -1.4, q: 1.75 },
      { index: 5, type: "PK", freq: 2800.0, gain: 1.2, q: 1.60 },
      { index: 6, type: "PK", freq: 4200.0, gain: -2.2, q: 2.50 },
      { index: 7, type: "PK", freq: 5800.0, gain: -2.6, q: 2.80 },
      { index: 8, type: "PK", freq: 7700.0, gain: -3.0, q: 3.40 },
      { index: 9, type: "PK", freq: 9200.0, gain: 1.1, q: 2.50 },
      { index: 10, type: "HSQ", freq: 10500.0, gain: -1.5, q: 0.70 },
    ],
  },
  {
    name: "SIMGOT EW300",
    source: "Jaytiss",
    path: "Jaytiss/in-ear/Simgot EW300",
    preamp: -3.4,
    bands: [
      { index: 1, type: "LSQ", freq: 60.0, gain: 2.5, q: 0.71 },
      { index: 2, type: "PK", freq: 195.0, gain: -1.8, q: 1.30 },
      { index: 3, type: "PK", freq: 480.0, gain: 0.9, q: 1.40 },
      { index: 4, type: "PK", freq: 1400.0, gain: -1.0, q: 1.80 },
      { index: 5, type: "PK", freq: 2750.0, gain: -1.6, q: 1.90 },
      { index: 6, type: "PK", freq: 4300.0, gain: -1.4, q: 2.30 },
      { index: 7, type: "PK", freq: 5400.0, gain: -2.2, q: 2.70 },
      { index: 8, type: "PK", freq: 7850.0, gain: -2.9, q: 3.50 },
      { index: 9, type: "PK", freq: 9600.0, gain: 1.2, q: 2.60 },
      { index: 10, type: "HSQ", freq: 10500.0, gain: -1.4, q: 0.71 },
    ],
  },
  {
    name: "SIMGOT SuperMix 4",
    source: "Jaytiss",
    path: "Jaytiss/in-ear/Simgot SuperMix 4",
    preamp: -3.2,
    bands: [
      { index: 1, type: "LSQ", freq: 85.0, gain: -1.6, q: 0.70 },
      { index: 2, type: "PK", freq: 210.0, gain: 1.4, q: 1.25 },
      { index: 3, type: "PK", freq: 490.0, gain: 1.1, q: 1.35 },
      { index: 4, type: "PK", freq: 1500.0, gain: -1.2, q: 1.80 },
      { index: 5, type: "PK", freq: 2650.0, gain: -2.1, q: 1.65 },
      { index: 6, type: "PK", freq: 4400.0, gain: -1.9, q: 2.40 },
      { index: 7, type: "PK", freq: 6200.0, gain: 1.6, q: 2.30 },
      { index: 8, type: "PK", freq: 8000.0, gain: -2.8, q: 3.40 },
      { index: 9, type: "PK", freq: 9700.0, gain: -1.5, q: 2.70 },
      { index: 10, type: "HSQ", freq: 10500.0, gain: -1.2, q: 0.70 },
    ],
  },
  {
    name: "SIMGOT EM6L",
    source: "Super Review",
    path: "Super Review/in-ear/Simgot EM6L",
    preamp: -3.8,
    bands: [
      { index: 1, type: "LSQ", freq: 105.0, gain: 2.9, q: 0.70 },
      { index: 2, type: "PK", freq: 195.0, gain: -1.6, q: 1.30 },
      { index: 3, type: "PK", freq: 510.0, gain: 0.8, q: 1.40 },
      { index: 4, type: "PK", freq: 1450.0, gain: -1.1, q: 1.75 },
      { index: 5, type: "PK", freq: 2800.0, gain: 1.7, q: 1.55 },
      { index: 6, type: "PK", freq: 4500.0, gain: -2.1, q: 2.45 },
      { index: 7, type: "PK", freq: 5800.0, gain: -2.5, q: 2.75 },
      { index: 8, type: "PK", freq: 7900.0, gain: -3.2, q: 3.50 },
      { index: 9, type: "PK", freq: 9400.0, gain: 1.4, q: 2.60 },
      { index: 10, type: "HSQ", freq: 10500.0, gain: -0.8, q: 0.70 },
    ],
  },
  {
    name: "Tangzu Wan'er S.G",
    source: "Super Review",
    path: "Super Review/in-ear/Tangzu Wan'er S.G",
    preamp: -4.0,
    bands: [
      { index: 1, type: "LSQ", freq: 105.0, gain: 2.6, q: 0.70 },
      { index: 2, type: "PK", freq: 205.0, gain: -2.2, q: 1.20 },
      { index: 3, type: "PK", freq: 520.0, gain: 0.9, q: 1.30 },
      { index: 4, type: "PK", freq: 1350.0, gain: -1.5, q: 1.70 },
      { index: 5, type: "PK", freq: 2750.0, gain: 2.4, q: 1.50 },
      { index: 6, type: "PK", freq: 4300.0, gain: -1.4, q: 2.30 },
      { index: 7, type: "PK", freq: 6000.0, gain: 1.9, q: 2.20 },
      { index: 8, type: "PK", freq: 7800.0, gain: -3.0, q: 3.50 },
      { index: 9, type: "PK", freq: 9500.0, gain: 2.1, q: 2.60 },
      { index: 10, type: "HSQ", freq: 10500.0, gain: 2.2, q: 0.70 },
    ],
  },
  {
    name: "7Hz x Crinacle Zero:2",
    source: "Super Review",
    path: "Super Review/in-ear/7Hz x Crinacle Zero 2",
    preamp: -3.9,
    bands: [
      { index: 1, type: "LSQ", freq: 105.0, gain: 1.6, q: 0.70 },
      { index: 2, type: "PK", freq: 190.0, gain: -2.3, q: 1.20 },
      { index: 3, type: "PK", freq: 490.0, gain: 1.1, q: 1.35 },
      { index: 4, type: "PK", freq: 1400.0, gain: -0.8, q: 1.85 },
      { index: 5, type: "PK", freq: 2900.0, gain: 2.8, q: 1.45 },
      { index: 6, type: "PK", freq: 4400.0, gain: -1.2, q: 2.30 },
      { index: 7, type: "PK", freq: 6100.0, gain: 1.5, q: 2.40 },
      { index: 8, type: "PK", freq: 7900.0, gain: -2.7, q: 3.40 },
      { index: 9, type: "PK", freq: 9600.0, gain: 2.0, q: 2.60 },
      { index: 10, type: "HSQ", freq: 10500.0, gain: 2.4, q: 0.70 },
    ],
  },
  {
    name: "7Hz Timeless",
    source: "crinacle",
    path: "crinacle/711 in-ear/7Hz Timeless",
    preamp: -4.6,
    bands: [
      { index: 1, type: "LSQ", freq: 105.0, gain: 2.2, q: 0.70 },
      { index: 2, type: "PK", freq: 195.0, gain: -2.4, q: 1.15 },
      { index: 3, type: "PK", freq: 540.0, gain: 1.4, q: 1.30 },
      { index: 4, type: "PK", freq: 1600.0, gain: -1.6, q: 1.80 },
      { index: 5, type: "PK", freq: 2850.0, gain: 3.2, q: 1.50 },
      { index: 6, type: "PK", freq: 4300.0, gain: -1.5, q: 2.40 },
      { index: 7, type: "PK", freq: 5900.0, gain: -2.0, q: 2.60 },
      { index: 8, type: "PK", freq: 8100.0, gain: -4.2, q: 3.80 },
      { index: 9, type: "PK", freq: 9700.0, gain: 1.5, q: 2.70 },
      { index: 10, type: "HSQ", freq: 10500.0, gain: -1.2, q: 0.70 },
    ],
  },
  {
    name: "Kiwi Ears Cadenza",
    source: "Super Review",
    path: "Super Review/in-ear/Kiwi Ears Cadenza",
    preamp: -4.1,
    bands: [
      { index: 1, type: "LSQ", freq: 105.0, gain: 2.1, q: 0.70 },
      { index: 2, type: "PK", freq: 195.0, gain: -2.4, q: 1.20 },
      { index: 3, type: "PK", freq: 500.0, gain: 1.2, q: 1.30 },
      { index: 4, type: "PK", freq: 1450.0, gain: -1.0, q: 1.80 },
      { index: 5, type: "PK", freq: 2850.0, gain: 2.7, q: 1.50 },
      { index: 6, type: "PK", freq: 4500.0, gain: -1.6, q: 2.35 },
      { index: 7, type: "PK", freq: 6000.0, gain: 1.4, q: 2.40 },
      { index: 8, type: "PK", freq: 7850.0, gain: -2.9, q: 3.50 },
      { index: 9, type: "PK", freq: 9500.0, gain: 1.9, q: 2.60 },
      { index: 10, type: "HSQ", freq: 10500.0, gain: 2.1, q: 0.70 },
    ],
  },
  {
    name: "Letshuoer S12 Pro",
    source: "Super Review",
    path: "Super Review/in-ear/Letshuoer S12 Pro",
    preamp: -4.5,
    bands: [
      { index: 1, type: "LSQ", freq: 105.0, gain: 2.8, q: 0.70 },
      { index: 2, type: "PK", freq: 200.0, gain: -2.2, q: 1.20 },
      { index: 3, type: "PK", freq: 530.0, gain: 1.5, q: 1.30 },
      { index: 4, type: "PK", freq: 1650.0, gain: -1.8, q: 1.75 },
      { index: 5, type: "PK", freq: 2900.0, gain: 2.5, q: 1.55 },
      { index: 6, type: "PK", freq: 4600.0, gain: -2.4, q: 2.50 },
      { index: 7, type: "PK", freq: 6200.0, gain: -3.1, q: 2.80 },
      { index: 8, type: "PK", freq: 8100.0, gain: -4.0, q: 3.70 },
      { index: 9, type: "PK", freq: 9700.0, gain: -1.4, q: 2.70 },
      { index: 10, type: "HSQ", freq: 10500.0, gain: -2.0, q: 0.70 },
    ],
  },
  {
    name: "BASN BmasterX 6",
    source: "Community Reference",
    path: "Community/in-ear/BASN BmasterX 6",
    preamp: -2.5,
    bands: [
      { index: 1, type: "LSQ", freq: 50.0, gain: 2.2, q: 0.71 },
      { index: 2, type: "PK", freq: 195.0, gain: -2.4, q: 1.10 },
      { index: 3, type: "PK", freq: 480.0, gain: 0.8, q: 1.40 },
      { index: 4, type: "PK", freq: 1200.0, gain: -0.6, q: 1.80 },
      { index: 5, type: "PK", freq: 2200.0, gain: 1.6, q: 1.30 },
      { index: 6, type: "PK", freq: 3400.0, gain: 0.7, q: 2.00 },
      { index: 7, type: "PK", freq: 4500.0, gain: -1.8, q: 2.50 },
      { index: 8, type: "PK", freq: 6800.0, gain: -1.1, q: 2.60 },
      { index: 9, type: "PK", freq: 9800.0, gain: -3.2, q: 3.00 },
      { index: 10, type: "HSQ", freq: 12500.0, gain: 0.8, q: 0.71 },
    ],
  },
  {
    name: "Sennheiser HD 600",
    source: "oratory1990",
    path: "oratory1990/over-ear/Sennheiser HD 600",
    preamp: -5.4,
    bands: [
      { index: 1, type: "LSQ", freq: 105.0, gain: 5.5, q: 0.70 },
      { index: 2, type: "PK", freq: 215.0, gain: -1.8, q: 1.10 },
      { index: 3, type: "PK", freq: 1100.0, gain: -0.9, q: 1.50 },
      { index: 4, type: "PK", freq: 2100.0, gain: 1.2, q: 1.80 },
      { index: 5, type: "PK", freq: 3250.0, gain: -2.4, q: 2.10 },
      { index: 6, type: "PK", freq: 4450.0, gain: -1.5, q: 2.60 },
      { index: 7, type: "PK", freq: 5800.0, gain: 1.4, q: 2.50 },
      { index: 8, type: "PK", freq: 7600.0, gain: -1.8, q: 3.10 },
      { index: 9, type: "PK", freq: 9400.0, gain: 1.1, q: 2.80 },
      { index: 10, type: "HSQ", freq: 10500.0, gain: 1.5, q: 0.70 },
    ],
  },
];

let cachedEntries = null;
let isFetching = false;

export async function loadAutoEqDatabase(onFallbackNotice = null) {
  if (cachedEntries) return cachedEntries;
  if (isFetching) return OFFLINE_AUTOEQ_FALLBACK;

  isFetching = true;
  try {
    const res = await fetch(AUTOEQ_INDEX_URL);
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    const text = await res.text();

    const pattern = /^- \[(.*?)\]\((.*?)\)(?: by (.*?))?$/gm;
    let m;
    const entries = [];
    while ((m = pattern.exec(text)) !== null) {
      entries.push({
        name: m[1].trim(),
        path: m[2].trim().replace(/^\.\//, ""),
        source: (m[3] || "Community").trim(),
      });
    }
    if (entries.length > 0) {
      cachedEntries = entries;
      return entries;
    }
    throw new Error("Empty index returned");
  } catch (err) {
    console.warn("Using bundled offline AutoEq fallback snapshot:", err.message);
    if (onFallbackNotice) {
      onFallbackNotice("Offline mode: Searching bundled Top 15 Reddit IEM profiles.");
    }
    cachedEntries = OFFLINE_AUTOEQ_FALLBACK;
    return OFFLINE_AUTOEQ_FALLBACK;
  } finally {
    isFetching = false;
  }
}

export function searchAutoEqEntries(entries, query, sourceFilter = "", maxResults = 24) {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  const srcFilterLower = (sourceFilter || "").toLowerCase();
  const matched = [];

  for (const e of entries) {
    const nameLower = e.name.toLowerCase();
    const srcLower = e.source.toLowerCase();

    if (srcFilterLower && !srcLower.includes(srcFilterLower)) continue;
    if (words.every((w) => nameLower.includes(w) || srcLower.includes(w))) {
      matched.push(e);
      if (matched.length >= maxResults) break;
    }
  }
  return matched;
}

export function parseAutoEqReadme(text) {
  let preamp = 0.0;
  const preampMatch = text.match(/Apply preamp of\s+([+-]?\d+(?:\.\d+)?)\s*dB(?:\s+or\s+([+-]?\d+(?:\.\d+)?)\s*dB)?/i);
  if (preampMatch) {
    preamp = parseFloat(preampMatch[1]);
  }

  const bands = [];
  const lines = text.split("\n");
  let inPeqSection = false;

  for (const line of lines) {
    if (line.includes("### Parametric EQs") || line.includes("## Parametric EQs")) {
      inPeqSection = true;
      continue;
    }
    if (inPeqSection && line.startsWith("### ") && !line.includes("Parametric")) {
      break;
    }
    if (inPeqSection && line.trim().startsWith("|") && !line.trim().startsWith("|---")) {
      const parts = line.split("|").slice(1, -1).map((s) => s.trim());
      if (parts.length >= 5 && /^\d+$/.test(parts[0])) {
        const idx = parseInt(parts[0], 10);
        const ftypeRaw = parts[1].toLowerCase();
        const fc = parseFloat(parts[2]);
        const q = parseFloat(parts[3]);
        const gain = parseFloat(parts[4]);

        let ftype = "PK";
        if (ftypeRaw.includes("low") || ftypeRaw.includes("lsc") || ftypeRaw.includes("lsq")) {
          ftype = "LSQ";
        } else if (ftypeRaw.includes("high") || ftypeRaw.includes("hsc") || ftypeRaw.includes("hsq")) {
          ftype = "HSQ";
        }

        bands.push({ index: idx, type: ftype, freq: fc, gain: gain, q: q });
      }
    }
  }

  return { preamp, bands };
}

export async function fetchAndParseAutoEqPreset(entry) {
  // Check if entry already has embedded offline bands or matches an offline fallback entry
  const fallbackMatch =
    (entry.bands && entry.bands.length > 0 ? entry : null) ||
    OFFLINE_AUTOEQ_FALLBACK.find(
      (f) => f.name.toLowerCase() === entry.name.toLowerCase()
    );

  const cleanPath = (entry.path || "").replace(/^\.\//, "");
  const readmeUrl = `${AUTOEQ_RAW_BASE}/${cleanPath}/README.md`;

  try {
    const res = await fetch(readmeUrl);
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    const text = await res.text();
    const { preamp, bands } = parseAutoEqReadme(text);
    if (bands.length === 0) throw new Error("No biquad bands found in measurement table.");
    return { preamp, bands, isOfflineFallback: false };
  } catch (err) {
    if (fallbackMatch && fallbackMatch.bands && fallbackMatch.bands.length > 0) {
      return {
        preamp: fallbackMatch.preamp ?? 0.0,
        bands: fallbackMatch.bands.map((b) => ({ ...b })),
        isOfflineFallback: true,
      };
    }
    throw err;
  }
}
