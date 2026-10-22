/**
 * dac-peq-manager Web Flasher & Host PEQ Suite
 * Modular UI Controller & Interactive SVG Curve Renderer.
 *
 * Imports DSP math, Host Exporters, WebHID Transport, and AutoEq Client
 * from `./modules/*.js`.
 */

import {
  computeCompositeCurve,
  generateLogFrequencies,
  calculatePeakCompositeGain,
  calculateRecommendedPreamp,
  lintAcousticBands,
  decimateBands,
} from "./modules/biquad_math.js";

import {
  formatPipeWireConf,
  formatEqualizerApo,
  formatWaveletGraphicEq,
} from "./modules/exporters.js";

import {
  KTMICRO_FILTERS,
  isMoondropFreeDsp,
  getFlashStats,
  recordFlashCommit,
  detectFirmwareQuirks,
  encodeKtMicroBandPackets,
  encodeMoondropReport,
  waitForUsbReenumeration,
  readKtMicroPeq,
  readMoondropReport,
  getStockBackup,
  saveStockBackup,
  hasStockBackup,
} from "./modules/hid_transport.js";

import {
  loadAutoEqDatabase,
  searchAutoEqEntries,
  fetchAndParseAutoEqPreset,
} from "./modules/autoeq_client.js";

import {
  initWasmEngine,
  isWasmReady,
  wasm,
} from "./modules/wasm_engine.js";

// ── Built-in Presets ───────────────────────────────────────────────────────────
const PRESETS = {
  bmasterx6: {
    name: "BASN BmasterX 6",
    slug: "bmasterx6",
    description: "1DD + 3BA + 2PZT - Tighten 8mm mid-bass warmth, pull vocals forward, tame 9.8kHz ceramic peak.",
    slot_id: 3,
    preamp: -2.5,
    bands: [
      { type: "LSQ", freq: 50.0, gain: 2.2, q: 0.71 },
      { type: "PK", freq: 195.0, gain: -2.4, q: 1.10 },
      { type: "PK", freq: 2200.0, gain: 1.6, q: 1.30 },
      { type: "PK", freq: 4500.0, gain: -1.8, q: 2.50 },
      { type: "PK", freq: 9800.0, gain: -3.2, q: 3.00 },
    ],
  },
  "ew300-silver": {
    name: "SIMGOT EW300 (Silver)",
    slug: "ew300_silver",
    description: "Silver Steel Nozzle (Simgot-Golden2023) - Add sub-bass punch and smooth upper-mid/PZT energy.",
    preamp: -2.8,
    bands: [
      { type: "LSQ", freq: 55.0, gain: 2.5, q: 0.71 },
      { type: "PK", freq: 220.0, gain: -1.2, q: 1.40 },
      { type: "PK", freq: 2800.0, gain: -1.8, q: 2.00 },
      { type: "PK", freq: 5200.0, gain: -2.2, q: 2.80 },
      { type: "HSQ", freq: 10500.0, gain: -1.5, q: 0.71 },
    ],
  },
  "ew300-gold": {
    name: "SIMGOT EW300 (Gold)",
    slug: "ew300_gold",
    description: "Gold Copper Nozzle (H-2019) - De-mud lower mids and restore top-end air and micro-detail.",
    preamp: -2.2,
    bands: [
      { type: "LSQ", freq: 45.0, gain: 1.5, q: 0.71 },
      { type: "PK", freq: 180.0, gain: -2.2, q: 1.20 },
      { type: "PK", freq: 2000.0, gain: 1.8, q: 1.40 },
      { type: "PK", freq: 4200.0, gain: -1.0, q: 2.20 },
      { type: "HSQ", freq: 9500.0, gain: 2.0, q: 0.71 },
    ],
  },
  flat: {
    name: "Flat Bypass (0 dB)",
    slug: "flat",
    description: "Hardware bypass / flat reset - Sets all bands to 1000 Hz 0 dB gain.",
    preamp: 0.0,
    bands: [
      { type: "PK", freq: 1000.0, gain: 0.0, q: 1.00 },
      { type: "PK", freq: 1000.0, gain: 0.0, q: 1.00 },
      { type: "PK", freq: 1000.0, gain: 0.0, q: 1.00 },
      { type: "PK", freq: 1000.0, gain: 0.0, q: 1.00 },
      { type: "PK", freq: 1000.0, gain: 0.0, q: 1.00 },
    ],
  },
  "jm-1": {
    name: "JM-1 Modern Target (Jaytiss)",
    slug: "jm_1",
    description: "Modern psychoacoustic target matching real human ear canal impedance. Warm sub-bass punch with a softened 3kHz pinna.",
    preamp: -3.5,
    bands: [
      { type: "LSQ", freq: 65.0, gain: 3.0, q: 0.71 },
      { type: "PK", freq: 220.0, gain: -1.2, q: 1.20 },
      { type: "PK", freq: 2700.0, gain: 1.8, q: 1.30 },
      { type: "PK", freq: 5200.0, gain: -1.5, q: 2.20 },
      { type: "HSQ", freq: 10500.0, gain: 1.0, q: 0.71 },
    ],
  },
  "ief-neutral": {
    name: "IEF Neutral Target (Crinacle)",
    slug: "ief_neutral",
    description: "Crinacle studio reference target curve. Linear bass with a non-fatiguing 2.8kHz ear gain peak.",
    preamp: -1.5,
    bands: [
      { type: "LSQ", freq: 80.0, gain: 0.0, q: 0.71 },
      { type: "PK", freq: 250.0, gain: 0.0, q: 1.00 },
      { type: "PK", freq: 2800.0, gain: 1.5, q: 1.50 },
      { type: "PK", freq: 5000.0, gain: -1.2, q: 2.00 },
      { type: "HSQ", freq: 10000.0, gain: 0.0, q: 0.71 },
    ],
  },
  "harman-2019v2": {
    name: "Harman In-Ear Target (2019 v2)",
    slug: "harman_in_ear_2019v2",
    description: "Samsung / Harman reference target by Dr. Sean Olive. Prominent +9dB sub-bass shelf and forward +12dB ear gain.",
    preamp: -3.5,
    bands: [
      { type: "LSQ", freq: 105.0, gain: 4.5, q: 0.71 },
      { type: "PK", freq: 200.0, gain: -1.5, q: 1.10 },
      { type: "PK", freq: 2850.0, gain: 2.5, q: 1.40 },
      { type: "PK", freq: 4800.0, gain: -1.0, q: 2.20 },
      { type: "HSQ", freq: 10000.0, gain: 0.0, q: 0.71 },
    ],
  },
};

// ── State ─────────────────────────────────────────────────────────────────────
let currentPreset = JSON.parse(JSON.stringify(PRESETS.bmasterx6));
let referenceTargetCurve = null;
let showTargetOverlay = true;
let connectedHidDevice = null;
let isDemoMode = false;
let isConexantBlocked = false;
let isRebootingPostCommit = false;
let autoApplyTimer = null;
let activeDragIndex = null;
let activeHardwareBands = 5; // 5 for KTMicro KT02H20, 9 for Moondrop FreeDSP

// ── SVG Curve Renderer ────────────────────────────────────────────────────────
const FREQ_TICKS = [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000];
const DB_TICKS = [6, 3, 0, -3, -6, -9, -12];
const F_MIN = 20.0, F_MAX = 20000.0;
const DB_TOP = 8.0, DB_BOTTOM = -14.0;

function xForFreq(f, width) {
  return ((Math.log10(f) - Math.log10(F_MIN)) / (Math.log10(F_MAX) - Math.log10(F_MIN))) * width;
}

function freqForX(x, width) {
  const norm = Math.max(0, Math.min(1, x / width));
  return Math.pow(10.0, Math.log10(F_MIN) + norm * (Math.log10(F_MAX) - Math.log10(F_MIN)));
}

function yForDb(db, height) {
  return ((DB_TOP - db) / (DB_TOP - DB_BOTTOM)) * height;
}

function dbForY(y, height) {
  const norm = Math.max(0, Math.min(1, y / height));
  return DB_TOP - norm * (DB_TOP - DB_BOTTOM);
}

function renderCurve() {
  const svg = document.getElementById("eqSvg");
  if (!svg) return;
  const width = svg.clientWidth || 800;
  const height = svg.clientHeight || 280;

  svg.innerHTML = "";

  // 1. Grid Lines (Horizontal dB)
  DB_TICKS.forEach((db) => {
    const y = yForDb(db, height);
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", 0);
    line.setAttribute("x2", width);
    line.setAttribute("y1", y);
    line.setAttribute("y2", y);
    line.setAttribute("class", db === 0 ? "zero-line" : "grid-line");
    svg.appendChild(line);

    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
    text.setAttribute("x", 8);
    text.setAttribute("y", y - 4);
    text.setAttribute("class", "axis-text");
    text.textContent = (db > 0 ? "+" : "") + db + " dB";
    svg.appendChild(text);
  });

  // 2. Grid Lines (Vertical Frequency)
  FREQ_TICKS.forEach((f) => {
    const x = xForFreq(f, width);
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", x);
    line.setAttribute("x2", x);
    line.setAttribute("y1", 0);
    line.setAttribute("y2", height);
    line.setAttribute("class", "grid-line");
    svg.appendChild(line);

    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
    text.setAttribute("x", x);
    text.setAttribute("y", height - 8);
    text.setAttribute("text-anchor", "middle");
    text.setAttribute("class", "axis-text");
    text.textContent = f >= 1000 ? f / 1000 + "k" : f;
    svg.appendChild(text);
  });

  // 3. Composite EQ Curve Path & Reference Target Overlay
  const frequencies = generateLogFrequencies(220);
  const responses = computeCompositeCurve(currentPreset.bands, currentPreset.preamp, frequencies);

  let rmsDiff = 0.0;
  let maxDelta = 0.0;
  let maxDeltaFreq = 1000.0;

  if (referenceTargetCurve && referenceTargetCurve.bands && referenceTargetCurve.bands.length > 0) {
    const refResponses = computeCompositeCurve(
      referenceTargetCurve.bands,
      referenceTargetCurve.preamp !== undefined ? referenceTargetCurve.preamp : currentPreset.preamp,
      frequencies
    );

    let sumSq = 0.0;
    for (let i = 0; i < frequencies.length; i++) {
      const delta = responses[i] - refResponses[i];
      sumSq += delta * delta;
      if (Math.abs(delta) > Math.abs(maxDelta)) {
        maxDelta = delta;
        maxDeltaFreq = frequencies[i];
      }
    }
    rmsDiff = Math.sqrt(sumSq / frequencies.length);

    if (showTargetOverlay) {
      let refPathD = "";
      frequencies.forEach((f, i) => {
        const x = xForFreq(f, width);
        const y = yForDb(refResponses[i], height);
        refPathD += (i === 0 ? "M " : "L ") + x.toFixed(1) + " " + y.toFixed(1) + " ";
      });

      const refCurvePath = document.createElementNS("http://www.w3.org/2000/svg", "path");
      refCurvePath.setAttribute("d", refPathD);
      refCurvePath.setAttribute("class", "reference-curve-path");
      svg.appendChild(refCurvePath);
    }
  }

  // Update Target Legend Header
  const targetLegend = document.getElementById("targetLegend");
  const lblTargetName = document.getElementById("lblTargetName");
  const lblTargetRms = document.getElementById("lblTargetRms");
  const lblToggleTarget = document.getElementById("lblToggleTarget");
  const chkShowTarget = document.getElementById("chkShowTarget");

  if (targetLegend && lblTargetName && lblTargetRms && lblToggleTarget) {
    if (referenceTargetCurve) {
      targetLegend.style.display = "inline-flex";
      lblToggleTarget.style.display = "inline-flex";
      lblTargetName.textContent = referenceTargetCurve.name || "Target Reference";
      if (showTargetOverlay) {
        const freqText = maxDeltaFreq >= 1000 ? (maxDeltaFreq / 1000).toFixed(1) + " kHz" : Math.round(maxDeltaFreq) + " Hz";
        lblTargetRms.textContent = `(RMS: ±${rmsDiff.toFixed(1)} dB | Peak Δ: ${maxDelta > 0 ? "+" : ""}${maxDelta.toFixed(1)} dB @ ${freqText})`;
      } else {
        lblTargetRms.textContent = "(Overlay Hidden)";
      }
      if (chkShowTarget) chkShowTarget.checked = showTargetOverlay;
    } else {
      targetLegend.style.display = "none";
      lblToggleTarget.style.display = "none";
    }
  }

  // Active Hardware Composite EQ Curve Path
  let pathD = "";
  frequencies.forEach((f, i) => {
    const x = xForFreq(f, width);
    const y = yForDb(responses[i], height);
    pathD += (i === 0 ? "M " : "L ") + x.toFixed(1) + " " + y.toFixed(1) + " ";
  });

  const curvePath = document.createElementNS("http://www.w3.org/2000/svg", "path");
  curvePath.setAttribute("d", pathD);
  curvePath.setAttribute("class", "curve-path");
  svg.appendChild(curvePath);

  // 4. Band Control Nodes
  currentPreset.bands.forEach((b, i) => {
    const x = xForFreq(b.freq, width);
    const y = yForDb(b.gain + currentPreset.preamp, height);

    const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
    group.setAttribute("data-index", i);

    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("cx", x);
    circle.setAttribute("cy", y);
    circle.setAttribute("r", 6);
    circle.setAttribute("fill", "#00d2ff");
    circle.setAttribute("stroke", "#ffffff");
    circle.setAttribute("stroke-width", 2);
    circle.setAttribute("class", "band-marker");

    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
    text.setAttribute("x", x);
    text.setAttribute("y", y - 10);
    text.setAttribute("text-anchor", "middle");
    text.setAttribute("fill", "#f8fafc");
    text.setAttribute("font-size", "11px");
    text.setAttribute("font-weight", "bold");
    text.textContent = i + 1;

    group.appendChild(circle);
    group.appendChild(text);
    svg.appendChild(group);

    group.addEventListener("mousedown", (e) => startDrag(e, i));
    group.addEventListener("touchstart", (e) => startDragTouch(e, i), { passive: false });
  });

  updateStats();
  updateWebAudioFilters();
}

function startDrag(e, index) {
  e.preventDefault();
  activeDragIndex = index;
  window.addEventListener("mousemove", onDragMove);
  window.addEventListener("mouseup", onDragEnd);
}

function startDragTouch(e, index) {
  e.preventDefault();
  activeDragIndex = index;
  window.addEventListener("touchmove", onDragTouchMove, { passive: false });
  window.addEventListener("touchend", onDragTouchEnd);
}

function onDragMove(e) {
  if (activeDragIndex === null) return;
  const svg = document.getElementById("eqSvg");
  const rect = svg.getBoundingClientRect();
  const width = rect.width;
  const height = rect.height;

  const mouseX = Math.max(0, Math.min(width, e.clientX - rect.left));
  const mouseY = Math.max(0, Math.min(height, e.clientY - rect.top));

  const newFreq = Math.round(freqForX(mouseX, width));
  const newGain = parseFloat((dbForY(mouseY, height) - currentPreset.preamp).toFixed(1));

  currentPreset.bands[activeDragIndex].freq = Math.max(20, Math.min(20000, newFreq));
  currentPreset.bands[activeDragIndex].gain = Math.max(-12, Math.min(12, newGain));

  syncBandControls(activeDragIndex);
  renderCurve();
  triggerAutoApply();
}

function onDragTouchMove(e) {
  if (activeDragIndex === null || !e.touches[0]) return;
  e.preventDefault();
  const touch = e.touches[0];
  const svg = document.getElementById("eqSvg");
  const rect = svg.getBoundingClientRect();
  const width = rect.width;
  const height = rect.height;

  const touchX = Math.max(0, Math.min(width, touch.clientX - rect.left));
  const touchY = Math.max(0, Math.min(height, touch.clientY - rect.top));

  const newFreq = Math.round(freqForX(touchX, width));
  const newGain = parseFloat((dbForY(touchY, height) - currentPreset.preamp).toFixed(1));

  currentPreset.bands[activeDragIndex].freq = Math.max(20, Math.min(20000, newFreq));
  currentPreset.bands[activeDragIndex].gain = Math.max(-12, Math.min(12, newGain));

  syncBandControls(activeDragIndex);
  renderCurve();
  triggerAutoApply();
}

function onDragEnd() {
  activeDragIndex = null;
  window.removeEventListener("mousemove", onDragMove);
  window.removeEventListener("mouseup", onDragEnd);
}

function onDragTouchEnd() {
  activeDragIndex = null;
  window.removeEventListener("touchmove", onDragTouchMove);
  window.removeEventListener("touchend", onDragTouchEnd);
}

// ── Flash Counter UI Badge ────────────────────────────────────────────────────
function updateFlashCounterBadge(dev) {
  const badge = document.getElementById("flashCounterBadge");
  const lbl = document.getElementById("lblFlashCount");
  if (!badge || !lbl) return;

  if (!dev && !isDemoMode) {
    badge.style.display = "none";
    return;
  }

  const stats = getFlashStats(dev);
  const oneDayAgo = Date.now() - 24 * 3600 * 1000;
  const burns24h = stats.timestamps.filter((t) => t > oneDayAgo).length;

  lbl.textContent = stats.total;
  badge.style.display = "inline-flex";

  if (stats.total >= 50 || burns24h >= 10) {
    lbl.style.color = "var(--accent-red)";
    badge.style.borderColor = "var(--accent-red)";
    badge.title = `⚠️ HIGH NVRAM FLASH WEAR! ${burns24h} burns in last 24h, ${stats.total} total burns. EEPROM wear limit approaching.`;
  } else if (burns24h >= 5) {
    lbl.style.color = "var(--accent-yellow)";
    badge.style.borderColor = "var(--accent-yellow)";
    badge.title = `Moderate flash wear: ${burns24h} burns in last 24h, ${stats.total} total burns.`;
  } else {
    lbl.style.color = "var(--accent-green)";
    badge.style.borderColor = "var(--border-color)";
    badge.title = `Flash commits: ${stats.total} total (${burns24h} in last 24h).`;
  }
}

// ── WebHID Hardware Lifecycle ─────────────────────────────────────────────────
function setHardwareBandArchitecture(bandCount) {
  activeHardwareBands = bandCount === 9 ? 9 : 5;
  const selHwBands = document.getElementById("selHardwareBandCount");
  if (selHwBands) selHwBands.value = String(activeHardwareBands);
  const lblTitle = document.getElementById("lblMatrixTitle");
  if (lblTitle) {
    lblTitle.textContent = `${activeHardwareBands}-Band Biquad Filter Matrix`;
  }

  const sourceBands =
    currentPreset.fullBands && currentPreset.fullBands.length >= activeHardwareBands
      ? currentPreset.fullBands
      : currentPreset.bands;
  currentPreset.bands = decimateBands(sourceBands, activeHardwareBands);
  buildControlsUI();
  renderCurve();
}

async function initializeDevice(dev, isSilent = false) {
  try {
    if (!dev.opened) {
      await dev.open();
    }
    connectedHidDevice = dev;

    const vidHex = "0x" + dev.vendorId.toString(16).toUpperCase().padStart(4, "0");
    const pidHex = "0x" + dev.productId.toString(16).toUpperCase().padStart(4, "0");
    const prodName = dev.productName || "USB Audio DSP";

    const dacMatch = findDacInDatabase(dev.vendorId, dev.productId, prodName);
    const dacDisplayName = dacMatch ? `${dacMatch.name} (${dacMatch.chipset})` : `${prodName} (${vidHex}:${pidHex})`;

    updateFlashCounterBadge(dev);

    // Switch between 9-band Moondrop FreeDSP vs 5-band KTMicro KT02H20
    if (isMoondropFreeDsp(dev) || (dacMatch && dacMatch.architecture === "moondrop_dsp")) {
      setHardwareBandArchitecture(9);
    } else if (activeHardwareBands !== 5) {
      setHardwareBandArchitecture(5);
    }

    const quirks = detectFirmwareQuirks(dev);
    const chkCompensate2X = document.getElementById("chkCompensate2X");
    if (chkCompensate2X) {
      chkCompensate2X.checked = quirks.requiresCompensate2X;
    }

    // Conexant Safety Check
    if (dev.vendorId === 0x0572 || prodName.toLowerCase().includes("cx31993") || (dacMatch && dacMatch.dac_type === "fixed_mask_rom")) {
      isConexantBlocked = true;
      updateDeviceBadge("blocked", `${dacDisplayName} - Fixed Mask ROM`);
      document.getElementById("safetyAlert").classList.add("visible");
      document.getElementById("btnApply").disabled = true;
      document.getElementById("btnReadDac").disabled = true;
      document.getElementById("btnFlash").disabled = true;
      if (!isSilent) {
        showToast(`${dacMatch ? dacMatch.name : "Conexant CX31993"}: Hardware flashing blocked for safety.`);
      }
      return;
    }

    isConexantBlocked = false;
    document.getElementById("safetyAlert").classList.remove("visible");
    document.getElementById("btnApply").disabled = false;
    document.getElementById("btnReadDac").disabled = false;
    document.getElementById("btnFlash").disabled = false;
    updateDeviceBadge("connected", `${dacDisplayName} - Ready`);

    const slotId = parseInt(document.getElementById("selHardwareSlot")?.value || "3", 10);
    const btnRestore = document.getElementById("btnRestoreStock");
    if (btnRestore) {
      btnRestore.style.display = hasStockBackup(dev, slotId) ? "inline-flex" : "none";
    }

    if (!isSilent) {
      showToast(`Connected to ${dacMatch ? dacMatch.name : prodName}! (${quirks.reason})`);
    }
  } catch (err) {
    console.error("Device init error:", err);
    if (!isSilent) {
      showToast(`Device error: ${err.message}`);
    }
  }
}

function handleDeviceDisconnect(reason = "DAC disconnected.") {
  if (isRebootingPostCommit) {
    console.log("Microcontroller rebooting after NVRAM commit, awaiting re-enumeration...");
    showToast("NVRAM commit in progress. Microcontroller restarting...");
    return;
  }
  connectedHidDevice = null;
  updateFlashCounterBadge(null);
  const btnRestore = document.getElementById("btnRestoreStock");
  if (btnRestore) btnRestore.style.display = "none";
  if (!isDemoMode) {
    updateDeviceBadge("disconnected", "No DAC Connected");
    document.getElementById("safetyAlert").classList.remove("visible");
    document.getElementById("btnApply").disabled = true;
    document.getElementById("btnReadDac").disabled = true;
    document.getElementById("btnFlash").disabled = true;
    showToast(reason);
  }
}

async function connectDac() {
  if (!navigator.hid) {
    showToast("WebHID API is not supported in this browser. Use Desktop Chrome/Edge/Brave, or export Wavelet on Android.");
    return;
  }

  try {
    const devices = await navigator.hid.requestDevice({
      filters: [
        ...KTMICRO_FILTERS,
        { vendorId: 0x0572 }, // Allow user to pick CX31993 to demonstrate safety guard
      ],
    });

    if (!devices || devices.length === 0) return;
    await initializeDevice(devices[0], false);
  } catch (err) {
    console.error("HID connection error:", err);
    showToast(`Connection failed: ${err.message}`);
  }
}

function updateDeviceBadge(type, text) {
  const badge = document.getElementById("deviceBadge");
  if (!badge) return;
  badge.className = `badge ${type}`;
  badge.innerHTML = `<span class="badge-dot"></span> <span>${text}</span>`;
}

async function sendHidReport(reportId, reg, cmd, d0 = 0, d1 = 0, d2 = 0, d3 = 0) {
  if (isDemoMode) {
    console.log(`[Demo Mode HID Tx] Report 0x${reportId.toString(16)}: Reg 0x${reg.toString(16)} CMD 0x${cmd.toString(16)} Data:`, [d0, d1, d2, d3]);
    return;
  }
  if (!connectedHidDevice) throw new Error("No DAC connected.");

  const payload = new Uint8Array([
    reg & 0xff, 0x00, 0x00, 0x00,
    cmd & 0xff, 0x00,
    d0 & 0xff, d1 & 0xff, d2 & 0xff, d3 & 0xff,
  ]);

  await connectedHidDevice.sendReport(reportId, payload);
  await new Promise((r) => setTimeout(r, 12));
}

async function applyToDevice(commitFlash = false) {
  if (isConexantBlocked) {
    showToast("Flash blocked: CX31993 has fixed mask ROM!");
    return;
  }
  if (!connectedHidDevice && !isDemoMode) {
    showToast("Please connect a USB DAC first (or enable Demo Mode).");
    return;
  }

  if (commitFlash && !isDemoMode) {
    const stats = getFlashStats(connectedHidDevice);
    const oneDayAgo = Date.now() - 24 * 3600 * 1000;
    const burns24h = stats.timestamps.filter((t) => t > oneDayAgo).length;

    let wearWarning = "";
    if (burns24h >= 10 || stats.total >= 50) {
      wearWarning =
        `⚠️ FLASH SILICON WEAR WARNING!\n` +
        `This DAC has received ${burns24h} flash burns in the last 24 hours (${stats.total} total burns).\n` +
        `Budget EEPROMs degrade after repeated flashing. Burning too frequently can permanently brick the DSP memory.\n\n`;
    }

    const ok = confirm(
      wearWarning +
        "⚠️ Burn to hardware NVRAM flash memory?\n\n" +
        `Flash memory has an endurance limit (~10k-100k write cycles). This permanently commits the ${activeHardwareBands}-band PEQ into onboard EEPROM so it persists across reboots and host swaps.\n\n` +
        "Do not disconnect the USB-C cable during the burn. Proceed?"
    );
    if (!ok) {
      showToast("NVRAM flash cancelled by user.");
      return;
    }
  }

  const compensate2X = document.getElementById("chkCompensate2X")?.checked || false;
  const selSlot = document.getElementById("selHardwareSlot");
  const slotId = selSlot ? parseInt(selSlot.value, 10) || 3 : 3;

  // Automatic First-Burn Stock Safety Snapshot
  if (commitFlash && connectedHidDevice && !isDemoMode) {
    if (!hasStockBackup(connectedHidDevice, slotId)) {
      try {
        const quirks = detectFirmwareQuirks(connectedHidDevice);
        const isMoondrop = activeHardwareBands === 9 || isMoondropFreeDsp(connectedHidDevice);
        let currentDacState;
        if (isMoondrop) {
          currentDacState = await readMoondropReport(connectedHidDevice, 300);
        } else {
          currentDacState = await readKtMicroPeq(connectedHidDevice, quirks.requiresCompensate2X);
        }
        if (currentDacState && currentDacState.bands && currentDacState.bands.length > 0) {
          saveStockBackup(connectedHidDevice, slotId, currentDacState);
          const btnRestore = document.getElementById("btnRestoreStock");
          if (btnRestore) btnRestore.style.display = "inline-flex";
          console.log(`[Safety Snapshot] Factory settings snapshotted for Slot ${slotId}`);
        }
      } catch (snapErr) {
        console.warn("Could not capture initial stock snapshot:", snapErr);
      }
    }
  }

  try {
    // Branch 1: Moondrop FreeDSP 9-Band Protocol
    if (activeHardwareBands === 9 || isMoondropFreeDsp(connectedHidDevice)) {
      const payload = encodeMoondropReport(currentPreset.bands, currentPreset.preamp, commitFlash);
      if (isDemoMode) {
        console.log("[Demo Mode Moondrop 9-Band Tx] 64-byte frame:", payload);
      } else {
        await connectedHidDevice.sendReport(0x00, payload);
      }
      if (commitFlash) {
        const stats = recordFlashCommit(connectedHidDevice);
        updateFlashCounterBadge(connectedHidDevice);
        showToast(`9-Band PEQ burned to Moondrop FreeDSP flash (Burn #${stats.total})!`);
      } else {
        showToast("9-Band PEQ written to Moondrop FreeDSP live RAM!");
      }
      return;
    }

    // Branch 2: KTMicro KT02H20 5-Band Protocol
    const REPORT_ID = 0x4b;
    const CMD_WRITE = 0x57;
    const CMD_COMMIT = 0x53;

    // 1. Enable selected EQ slot (Register 0x24: Slot 0x01-0x04, default 0x03)
    await sendHidReport(REPORT_ID, 0x24, CMD_WRITE, slotId & 0xff, 0, 0, 0);

    // 2. Write 5 bands
    for (let i = 0; i < 5; i++) {
      const b = currentPreset.bands[i] || { type: "PK", freq: 1000, gain: 0, q: 1.0 };
      const { regGf, regQ, gfData, qData } = encodeKtMicroBandPackets(i, b, compensate2X);
      await sendHidReport(REPORT_ID, regGf, CMD_WRITE, ...gfData);
      await sendHidReport(REPORT_ID, regQ, CMD_WRITE, ...qData);
    }

    // 3. Preamp (Register 0x66 in 0.5 dB steps)
    // Only write 0x66 if supported; Kiwi Ears Allegro Mini (0x31B2) uses unity gain (noPregain)
    const isKiwiMini = connectedHidDevice && (connectedHidDevice.vendorId === 0x31b2 || connectedHidDevice.vendorId === 12722);
    if (!isKiwiMini && currentPreset.preamp !== 0) {
      const preampByte = Math.round(currentPreset.preamp * 2.0) & 0xff;
      await sendHidReport(REPORT_ID, 0x66, CMD_WRITE, preampByte, 0, 0, 0);
    }

    // 3b. Hardware DAC reconstruction filter (Register 0x11)
    // Register 0x11 is strictly a FiiO JA11 (0x2972) feature; on KTMicro Allegro Mini, writing 0x11 corrupts volume registers!
    const isFiio = connectedHidDevice && (connectedHidDevice.vendorId === 0x2972 || connectedHidDevice.vendorId === 10610);
    const selDac = document.getElementById("selDacFilter");
    if (selDac && isFiio) {
      const filterVal = parseInt(selDac.value, 10) || 1;
      await sendHidReport(REPORT_ID, 0x11, CMD_WRITE, filterVal, 0, 0, 0);
    }

    // 4. NVRAM Flash Commit & Event-Driven Re-Enumeration Watcher
    if (commitFlash) {
      const stats = recordFlashCommit(connectedHidDevice);
      updateFlashCounterBadge(connectedHidDevice);
      isRebootingPostCommit = true;
      try {
        await sendHidReport(REPORT_ID, 0x00, CMD_COMMIT, 0, 0, 0, 0);
      } catch (commitErr) {
        console.warn("Soft-reboot USB drop on commit:", commitErr);
      }
      showToast(`PEQ burned to Slot ${slotId} NVRAM flash (Burn #${stats.total})! Awaiting USB re-enumeration...`);

      const reenumerated = await waitForUsbReenumeration(navigator.hid, KTMICRO_FILTERS, 4000, 200);
      isRebootingPostCommit = false;
      if (reenumerated) {
        await initializeDevice(reenumerated, true);
        showToast(`Microcontroller online! Slot ${slotId} NVRAM verified.`);
      }
    } else {
      showToast(`PEQ written to Slot ${slotId} live DSP RAM (Instant Audition)!`);
    }
  } catch (err) {
    isRebootingPostCommit = false;
    console.error("Apply error:", err);
    showToast(`Error communicating with DAC: ${err.message}`);
  }
}

async function readFromDevice(silent = false) {
  if (isConexantBlocked) {
    if (!silent) showToast("Read blocked: CX31993 has fixed mask ROM!");
    return;
  }
  if (!connectedHidDevice && !isDemoMode) {
    if (!silent) showToast("Please connect a USB DAC first (or enable Demo Mode).");
    return;
  }

  if (isDemoMode) {
    if (!silent) showToast("Demo Mode: Loaded active simulated DSP registers into editor.");
    buildControlsUI();
    renderCurve();
    return;
  }

  try {
    if (!silent) showToast("Reading registers from hardware DSP...");
    const isMoondrop = activeHardwareBands === 9 || isMoondropFreeDsp(connectedHidDevice);

    if (isMoondrop) {
      const res = await readMoondropReport(connectedHidDevice);
      if (res && res.bands && res.bands.length > 0) {
        currentPreset.preamp = res.preamp;
        currentPreset.bands = res.bands;
        activeHardwareBands = 9;
        saveStockBackup(connectedHidDevice, 1, res);
        const btnRestore = document.getElementById("btnRestoreStock");
        if (btnRestore) btnRestore.style.display = "inline-flex";
        buildControlsUI();
        renderCurve();
        if (!silent) showToast(`Successfully read ${res.bands.length} bands from Moondrop FreeDSP!`);
      }
    } else {
      const quirks = detectFirmwareQuirks(connectedHidDevice);
      const res = await readKtMicroPeq(connectedHidDevice, quirks.requiresCompensate2X);
      if (res && res.bands && res.bands.length > 0) {
        currentPreset.preamp = res.preamp;
        currentPreset.bands = res.bands;
        activeHardwareBands = 5;
        if (res.slotId) {
          const selSlot = document.getElementById("selHardwareSlot");
          if (selSlot) selSlot.value = String(res.slotId);
        }
        if (res.dacFilter) {
          const selDac = document.getElementById("selDacFilter");
          if (selDac) selDac.value = String(res.dacFilter);
        }
        saveStockBackup(connectedHidDevice, res.slotId || 3, res);
        const btnRestore = document.getElementById("btnRestoreStock");
        if (btnRestore) btnRestore.style.display = "inline-flex";
        buildControlsUI();
        renderCurve();
        if (!silent) {
          showToast(`Successfully read 5 bands from Slot ${res.slotId || 3} (Preamp: ${res.preamp > 0 ? "+" : ""}${res.preamp.toFixed(1)} dB)!`);
        }
      }
    }
  } catch (err) {
    console.error("Read error:", err);
    if (!silent) showToast(`Failed to read from DAC: ${err.message}`);
  }
}

function exportBackupPreset() {
  const slotId = parseInt(document.getElementById("selHardwareSlot")?.value || "3", 10);
  const out = {
    name: currentPreset.name || `Custom PEQ (Slot ${slotId})`,
    slug: (currentPreset.slug || "custom_peq").replace(/[^a-z0-9_-]/gi, "_"),
    description: currentPreset.description || `Hardware PEQ profile for Slot ${slotId}`,
    slot_id: slotId,
    preamp: Number(currentPreset.preamp) || 0.0,
    bands: currentPreset.bands.map((b, i) => ({
      index: i + 1,
      type: b.type || "PK",
      freq: Math.round(Number(b.freq) || 1000),
      gain: Math.round((Number(b.gain) || 0.0) * 10) / 10,
      q: Math.round((Number(b.q) || 1.0) * 100) / 100,
    })),
  };
  const dacFilterEl = document.getElementById("selDacFilter");
  if (dacFilterEl) out.dac_filter = dacFilterEl.options[dacFilterEl.selectedIndex]?.text || "FAST-LL";

  const jsonStr = JSON.stringify(out, null, 2);
  downloadFile(`${out.slug}_slot${slotId}.json`, jsonStr, "application/json");
  showToast(`Backup preset saved as ${out.slug}_slot${slotId}.json!`);
}

function restoreStockBackup() {
  const slotId = parseInt(document.getElementById("selHardwareSlot")?.value || "3", 10);
  if (!connectedHidDevice && !isDemoMode) {
    showToast("Please connect your DAC to restore stock backup.");
    return;
  }
  const stock = getStockBackup(connectedHidDevice, slotId);
  if (!stock || !stock.bands || stock.bands.length === 0) {
    showToast(`No stock backup found for Slot ${slotId}.`);
    return;
  }

  currentPreset = {
    name: `Stock Factory Backup (Slot ${slotId})`,
    slug: `stock_backup_slot${slotId}`,
    description: `Original factory DSP tuning captured prior to flash burn`,
    preamp: stock.preamp ?? 0.0,
    bands: stock.bands.map((b, i) => ({ ...b, index: i + 1 })),
  };

  buildControlsUI();
  renderCurve();
  triggerAutoApply();
  showToast(`Stock factory tuning for Slot ${slotId} restored into editor! Click 'Burn to NVRAM Flash' to make permanent.`);
}

async function clearDeviceFlash() {
  if (!connectedHidDevice && !isDemoMode) {
    showToast("Please connect your DAC first.");
    return;
  }
  const ok = confirm(
    "⚠️ Hardware Factory Reset (0x43 CLEAR)?\n\nThis will send the hardware CLEAR command to erase all custom NVRAM flash configurations and restore the Kiwi Ears factory default state.\n\nProceed?"
  );
  if (!ok) return;

  try {
    const REPORT_ID = 0x4b;
    const CMD_CLEAR = 0x43;
    await sendHidReport(REPORT_ID, 0x00, CMD_CLEAR, 0, 0, 0, 0);
    showToast("Factory CLEAR sent! Microcontroller resetting...");
    isRebootingPostCommit = true;
    const reenumerated = await waitForUsbReenumeration(navigator.hid, KTMICRO_FILTERS, 4000, 200);
    isRebootingPostCommit = false;
    if (reenumerated) {
      await initializeDevice(reenumerated, true);
    }
    showToast("Factory reset complete! Allegro Mini restored to stock defaults.");
  } catch (err) {
    isRebootingPostCommit = false;
    console.error("Clear error:", err);
    showToast(`Reset failed: ${err.message}`);
  }
}

function triggerAutoApply() {
  const autoApply = document.getElementById("chkAutoApply")?.checked;
  if (!autoApply) return;
  clearTimeout(autoApplyTimer);
  autoApplyTimer = setTimeout(() => {
    applyToDevice(false);
  }, 75);
}

// ── UI Controls & Sync ────────────────────────────────────────────────────────
function buildControlsUI() {
  const container = document.getElementById("controlsContainer");
  if (!container) return;
  container.innerHTML = "";

  currentPreset.bands.forEach((b, i) => {
    const card = document.createElement("div");
    card.className = "band-control";
    card.innerHTML = `
      <div class="band-header">
        <div class="band-num">
          <span class="band-pill">${i + 1}</span> Band ${i + 1}
        </div>
        <select id="type_${i}" style="width: 100px;">
          <option value="PK" ${b.type === "PK" ? "selected" : ""}>Peaking</option>
          <option value="LSQ" ${b.type === "LSQ" ? "selected" : ""}>Low-Shelf</option>
          <option value="HSQ" ${b.type === "HSQ" ? "selected" : ""}>High-Shelf</option>
        </select>
      </div>

      <div class="control-row">
        <div class="control-label">
          <span>Freq</span>
          <span id="lblFreq_${i}">${Math.round(b.freq)} Hz</span>
        </div>
        <input type="range" id="freq_${i}" min="20" max="20000" step="1" value="${b.freq}">
      </div>

      <div class="control-row">
        <div class="control-label">
          <span>Gain</span>
          <span id="lblGain_${i}">${(b.gain > 0 ? "+" : "") + b.gain.toFixed(1)} dB</span>
        </div>
        <input type="range" id="gain_${i}" min="-12" max="12" step="0.1" value="${b.gain}">
      </div>

      <div class="control-row">
        <div class="control-label">
          <span>Q Factor</span>
          <span id="lblQ_${i}">${b.q.toFixed(2)}</span>
        </div>
        <input type="range" id="q_${i}" min="0.1" max="10" step="0.05" value="${b.q}">
      </div>
    `;
    container.appendChild(card);

    document.getElementById(`type_${i}`).addEventListener("change", (e) => {
      currentPreset.bands[i].type = e.target.value;
      renderCurve();
      triggerAutoApply();
    });

    document.getElementById(`freq_${i}`).addEventListener("input", (e) => {
      currentPreset.bands[i].freq = parseFloat(e.target.value);
      document.getElementById(`lblFreq_${i}`).textContent = `${Math.round(currentPreset.bands[i].freq)} Hz`;
      renderCurve();
      triggerAutoApply();
    });

    document.getElementById(`gain_${i}`).addEventListener("input", (e) => {
      currentPreset.bands[i].gain = parseFloat(e.target.value);
      const val = currentPreset.bands[i].gain;
      document.getElementById(`lblGain_${i}`).textContent = `${val > 0 ? "+" : ""}${val.toFixed(1)} dB`;
      renderCurve();
      triggerAutoApply();
    });

    document.getElementById(`q_${i}`).addEventListener("input", (e) => {
      currentPreset.bands[i].q = parseFloat(e.target.value);
      document.getElementById(`lblQ_${i}`).textContent = currentPreset.bands[i].q.toFixed(2);
      renderCurve();
      triggerAutoApply();
    });
  });

  const preampInput = document.getElementById("sliderPreamp");
  if (preampInput) {
    preampInput.value = currentPreset.preamp;
    document.getElementById("lblPreamp").textContent = `${currentPreset.preamp > 0 ? "+" : ""}${currentPreset.preamp.toFixed(1)} dB`;

    preampInput.oninput = (e) => {
      currentPreset.preamp = parseFloat(e.target.value);
      document.getElementById("lblPreamp").textContent = `${currentPreset.preamp > 0 ? "+" : ""}${currentPreset.preamp.toFixed(1)} dB`;
      renderCurve();
      triggerAutoApply();
    };
  }
}

function syncBandControls(i) {
  const b = currentPreset.bands[i];
  const freqEl = document.getElementById(`freq_${i}`);
  const gainEl = document.getElementById(`gain_${i}`);
  const qEl = document.getElementById(`q_${i}`);
  const typeEl = document.getElementById(`type_${i}`);

  if (freqEl) freqEl.value = b.freq;
  if (gainEl) gainEl.value = b.gain;
  if (qEl) qEl.value = b.q;
  if (typeEl) typeEl.value = b.type;

  const lblFreq = document.getElementById(`lblFreq_${i}`);
  const lblGain = document.getElementById(`lblGain_${i}`);
  const lblQ = document.getElementById(`lblQ_${i}`);

  if (lblFreq) lblFreq.textContent = `${Math.round(b.freq)} Hz`;
  if (lblGain) lblGain.textContent = `${b.gain > 0 ? "+" : ""}${b.gain.toFixed(1)} dB`;
  if (lblQ) lblQ.textContent = b.q.toFixed(2);
}

function updateStats() {
  const statsEl = document.getElementById("graphStats");
  if (!statsEl) return;

  const peakGain = calculatePeakCompositeGain(currentPreset.bands);
  const totalPeak = peakGain + currentPreset.preamp;

  let peakStatus = "";
  if (totalPeak > 0.05) {
    peakStatus = ` | <span style="color: var(--accent-red); font-weight: 700;">⚠️ Intersample Clip Risk (+${totalPeak.toFixed(1)} dBFS)</span>`;
  } else {
    peakStatus = ` | <span style="color: var(--accent-green); font-weight: 600;">Peak: ${totalPeak.toFixed(1)} dBFS</span>`;
  }

  statsEl.innerHTML = `Preamp: ${currentPreset.preamp > 0 ? "+" : ""}${currentPreset.preamp.toFixed(1)} dB${peakStatus} | RBJ 48/96kHz`;

  const alertEl = document.getElementById("acousticAlert");
  const alertText = document.getElementById("acousticAlertText");
  if (alertEl && alertText) {
    const warnings = lintAcousticBands(currentPreset.bands);
    if (warnings.length > 0) {
      alertText.innerHTML = `<strong>Acoustic Advisory Notice:</strong><br>${warnings.join("<br>")}`;
      alertEl.classList.add("visible");
    } else {
      alertEl.classList.remove("visible");
    }
  }
}

function selectPreset(slug) {
  const p = PRESETS[slug];
  if (!p) return;
  currentPreset = JSON.parse(JSON.stringify(p));
  currentPreset.bands = decimateBands(currentPreset.bands, activeHardwareBands);
  currentPreset.fullBands = null;
  referenceTargetCurve = null;

  if (p.slot_id) {
    const selSlot = document.getElementById("selHardwareSlot");
    if (selSlot) selSlot.value = String(p.slot_id);
  }

  document.querySelectorAll(".preset-card").forEach((card) => {
    card.classList.toggle("active", card.getAttribute("data-preset") === slug);
  });

  buildControlsUI();
  renderCurve();
  showToast(`Loaded preset: ${p.name}`);
  triggerAutoApply();
}

// ── Host DSP File Exporters ───────────────────────────────────────────────────
function downloadFile(filename, text) {
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function getBandsForExport() {
  const sel = document.getElementById("selExportFidelity");
  const fidelity = sel ? sel.value : "hardware";
  if (fidelity === "full" && currentPreset.fullBands && currentPreset.fullBands.length > currentPreset.bands.length) {
    return { bands: currentPreset.fullBands, tag: `${currentPreset.fullBands.length}band_target`, isFull: true };
  }
  return { bands: currentPreset.bands, tag: `${currentPreset.bands.length}band_hw`, isFull: false };
}

function exportPipeWireConf() {
  const preset = currentPreset;
  const slug = preset.slug || "custom";
  const { bands, tag, isFull } = getBandsForExport();
  const conf = formatPipeWireConf(preset, bands, isFull);
  downloadFile(`99-jm6pro-${slug}-${tag}.conf`, conf);
  showToast(`Downloaded PipeWire configuration (${bands.length} bands)!`);
}

function exportEqualizerApo() {
  const preset = currentPreset;
  const { bands, tag, isFull } = getBandsForExport();
  const txt = formatEqualizerApo(preset, bands, isFull);
  downloadFile(`${preset.slug || "preset"}_${tag}_equalizer_apo.txt`, txt);
  showToast(`Downloaded EqualizerAPO profile (${bands.length} bands)!`);
}

function exportWaveletGraphicEq() {
  const { bands, tag } = getBandsForExport();
  const txt = formatWaveletGraphicEq(bands, currentPreset.preamp, 127);
  downloadFile(`${currentPreset.slug || "preset"}_${tag}_wavelet_graphiceq.txt`, txt);
  showToast(`Downloaded Wavelet GraphicEQ profile (${bands.length} bands)!`);
}

// ── Web Audio Test Tone Generator & Real-Time DSP Chain ──────────────────────
let audioCtx = null;
let noiseNode = null;
let preampGainNode = null;
let webAudioFiltNodes = [];
let isPlayingNoise = false;

function getWebAudioFilterType(ftype) {
  const t = String(ftype || "PK").toUpperCase();
  if (t === "LSQ" || t === "LOW_SHELF" || t === "LOWSHELF") return "lowshelf";
  if (t === "HSQ" || t === "HIGH_SHELF" || t === "HIGHSHELF") return "highshelf";
  return "peaking";
}

function updateWebAudioFilters() {
  if (!isPlayingNoise || !audioCtx) return;
  // Double-EQ Guard: If physical hardware DAC is connected, skip software biquad processing
  // to avoid double-EQing through the DAC's hardware DSP
  if (connectedHidDevice && !isDemoMode) return;

  const now = audioCtx.currentTime;
  if (preampGainNode) {
    const linearGain = Math.pow(10, (Number(currentPreset.preamp) || 0.0) / 20);
    preampGainNode.gain.setValueAtTime(linearGain, now);
  }

  const bands = currentPreset.bands || [];
  for (let i = 0; i < webAudioFiltNodes.length; i++) {
    const filt = webAudioFiltNodes[i];
    const b = bands[i];
    if (!b) {
      filt.gain.setValueAtTime(0.0, now);
      continue;
    }
    const typeStr = getWebAudioFilterType(b.type);
    if (filt.type !== typeStr) filt.type = typeStr;
    filt.frequency.setValueAtTime(Math.max(20, Math.min(20000, Number(b.freq) || 1000)), now);
    filt.gain.setValueAtTime(Number(b.gain) || 0.0, now);
    filt.Q.setValueAtTime(Math.max(0.1, Math.min(20, Number(b.q) || 1.0)), now);
  }
}

async function toggleTestNoise() {
  const btn = document.getElementById("btnTestNoise");
  if (!isPlayingNoise) {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    if (audioCtx.state === "suspended") {
      await audioCtx.resume();
    }

    const bufferSize = audioCtx.sampleRate * 2;
    const noiseBuffer = audioCtx.createBuffer(1, bufferSize, audioCtx.sampleRate);
    const output = noiseBuffer.getChannelData(0);

    let b0 = 0, b1 = 0, b2 = 0, b3 = 0, b4 = 0, b5 = 0, b6 = 0;
    for (let i = 0; i < bufferSize; i++) {
      const white = Math.random() * 2 - 1;
      b0 = 0.99886 * b0 + white * 0.0555179;
      b1 = 0.99332 * b1 + white * 0.0750759;
      b2 = 0.96900 * b2 + white * 0.1538520;
      b3 = 0.86650 * b3 + white * 0.3104856;
      b4 = 0.55000 * b4 + white * 0.5329522;
      b5 = -0.7616 * b5 - white * 0.0168980;
      output[i] = (b0 + b1 + b2 + b3 + b4 + b5 + b6 + white * 0.5362) * 0.04;
      b6 = white * 0.115926;
    }

    noiseNode = audioCtx.createBufferSource();
    noiseNode.buffer = noiseBuffer;
    noiseNode.loop = true;

    // Double-EQ Guard:
    // When a physical hardware DSP DAC is actively connected (and not in demo mode),
    // output flat noise directly so the hardware DSP performs the filtering.
    // In Demo Mode or Host-DSP mode, build the Web Audio BiquadFilterNode chain.
    if (connectedHidDevice && !isDemoMode) {
      noiseNode.connect(audioCtx.destination);
      showToast("Live auditioning via connected hardware DSP DAC (hardware-filtered).");
    } else {
      preampGainNode = audioCtx.createGain();
      const linearGain = Math.pow(10, (Number(currentPreset.preamp) || 0.0) / 20);
      preampGainNode.gain.setValueAtTime(linearGain, audioCtx.currentTime);

      noiseNode.connect(preampGainNode);
      let lastNode = preampGainNode;

      webAudioFiltNodes = [];
      const bands = currentPreset.bands || [];
      for (let i = 0; i < bands.length; i++) {
        const b = bands[i];
        const filt = audioCtx.createBiquadFilter();
        filt.type = getWebAudioFilterType(b.type);
        filt.frequency.setValueAtTime(Math.max(20, Math.min(20000, Number(b.freq) || 1000)), audioCtx.currentTime);
        filt.gain.setValueAtTime(Number(b.gain) || 0.0, audioCtx.currentTime);
        filt.Q.setValueAtTime(Math.max(0.1, Math.min(20, Number(b.q) || 1.0)), audioCtx.currentTime);
        lastNode.connect(filt);
        lastNode = filt;
        webAudioFiltNodes.push(filt);
      }

      lastNode.connect(audioCtx.destination);
      showToast("Live browser auditioning active via Web Audio API filter chain!");
    }

    noiseNode.start();
    isPlayingNoise = true;
    if (btn) {
      btn.textContent = "Stop Pink Noise";
      btn.classList.add("btn-burn");
    }
  } else {
    if (noiseNode) {
      try {
        noiseNode.stop();
        noiseNode.disconnect();
      } catch (_) {}
      noiseNode = null;
    }
    if (preampGainNode) {
      try { preampGainNode.disconnect(); } catch (_) {}
      preampGainNode = null;
    }
    for (const f of webAudioFiltNodes) {
      try { f.disconnect(); } catch (_) {}
    }
    webAudioFiltNodes = [];
    isPlayingNoise = false;
    if (btn) {
      btn.textContent = "Play Pink Noise";
      btn.classList.remove("btn-burn");
    }
  }
}

// ── Community Database Search & Pull ──────────────────────────────────────────
async function performDatabaseSearch() {
  const input = document.getElementById("dbSearchInput");
  const query = (input ? input.value : "").trim();
  const sourceFilter = document.getElementById("dbSourceFilter") ? document.getElementById("dbSourceFilter").value : "";
  const container = document.getElementById("dbResultsList");

  if (!query) {
    if (container) container.style.display = "none";
    return;
  }

  if (container) {
    container.style.display = "grid";
    container.innerHTML = `<div style="grid-column: 1/-1; padding: 0.8rem; text-align: center; color: var(--text-secondary); font-size: 0.85rem;">Searching community database...</div>`;
  }

  const entries = await loadAutoEqDatabase((msg) => showToast(msg));
  const matched = searchAutoEqEntries(entries, query, sourceFilter, 24);

  if (!container) return;

  if (matched.length === 0) {
    container.innerHTML = `<div style="grid-column: 1/-1; padding: 0.8rem; text-align: center; color: var(--accent-yellow); font-size: 0.85rem;">No matching models found for "${query}". Try broader search terms.</div>`;
    return;
  }

  container.innerHTML = "";
  matched.forEach((e) => {
    const card = document.createElement("div");
    card.className = "db-result-card";
    card.innerHTML = `
      <div class="db-result-name">${e.name}</div>
      <div class="db-result-meta">
        <span style="color: var(--accent-cyan);">${e.source}</span>
        <span style="color: var(--text-muted); font-family: var(--font-mono); font-size: 0.7rem;">AutoEq ${activeHardwareBands}-Band</span>
      </div>
    `;
    card.addEventListener("click", () => pullCommunityPreset(e));
    container.appendChild(card);
  });
}

async function pullCommunityPreset(entry) {
  showToast(`Fetching ${activeHardwareBands}-band PEQ profile for ${entry.name}...`);
  try {
    const { preamp, bands, isOfflineFallback } = await fetchAndParseAutoEqPreset(entry);
    const optimizedBands = decimateBands(bands, activeHardwareBands);

    currentPreset = {
      name: `${entry.name} (${entry.source})`,
      slug: entry.name.toLowerCase().replace(/[^a-z0-9]+/g, "_"),
      description: `AutoEq target optimization (source: ${entry.source}${isOfflineFallback ? " - Offline Snapshot" : ""})`,
      preamp: Math.round(preamp * 10) / 10,
      bands: optimizedBands,
      fullBands: JSON.parse(JSON.stringify(bands)),
    };

    referenceTargetCurve = {
      name: `${entry.name} (${bands.length}-Band Target)`,
      preamp: Math.round(preamp * 10) / 10,
      bands: JSON.parse(JSON.stringify(bands)),
    };

    document.querySelectorAll(".preset-card").forEach((c) => c.classList.remove("active"));

    buildControlsUI();
    renderCurve();
    triggerAutoApply();
    showToast(`Loaded ${entry.name}${isOfflineFallback ? " (Offline Snapshot)" : ""}! Ready to audition or flash.`);
  } catch (err) {
    console.error("Error pulling community preset:", err);
    showToast(`Failed to pull ${entry.name}: ${err.message}`);
  }
}

// ── Hardware DAC Directory & Compatibility Engine ─────────────────────────────
let dacCatalog = [];
let currentDacFilter = "all";

const DEFAULT_DACS = [
  {
    id: "allegro_mini",
    name: "Kiwi Ears Allegro Mini",
    brand: "Kiwi Ears",
    chipset: "KTMicro KT02H20 / CB1200AU",
    architecture: "ktmicro_dsp",
    dac_type: "hardware_dsp",
    flashable: true,
    vid: 12722, pid: 273,
    resolution: "32-bit / 384 kHz, DSD128",
    output_power: "30mW @ 32Ω (3.5mm) / 60mW @ 32Ω (4.4mm)",
    recommendation: "Direct hardware flash via WebHID. Settings persist across reboots and mobile devices.",
  },
  {
    id: "bmasterx6_plug",
    name: "BASN BmasterX 6 Modular Type-C DSP Plug",
    brand: "BASN",
    chipset: "KTMicro / WalkPlay OEM DSP",
    architecture: "ktmicro_dsp",
    dac_type: "hardware_dsp",
    flashable: true,
    vid: 12722, pid: 273,
    resolution: "32-bit / 384 kHz",
    output_power: "28mW @ 32Ω",
    recommendation: "Direct hardware flash into cable termination. Aligns the 1DD+3BA+2PZT acoustic profile.",
  },
  {
    id: "fiio_ja11",
    name: "FiiO / JadeAudio JA11",
    brand: "FiiO",
    chipset: "KTMicro KT02H20",
    architecture: "ktmicro_dsp",
    dac_type: "hardware_dsp",
    flashable: true,
    vid: 10610, pid: 258,
    resolution: "32-bit / 384 kHz, DSD128",
    output_power: "30mW @ 32Ω",
    recommendation: "Direct hardware flash via WebHID. Supports digital reconstruction filter customization.",
  },
  {
    id: "moondrop_freedsp",
    name: "Moondrop FreeDSP / May / Chu II DSP",
    brand: "Moondrop",
    chipset: "Moondrop Custom 9-Band DSP",
    architecture: "moondrop_dsp",
    dac_type: "hardware_dsp",
    flashable: true,
    vid: 12722, pid: 274,
    resolution: "24-bit / 96 kHz",
    output_power: "30mW @ 32Ω",
    recommendation: "Direct 9-Band hardware flash via WebHID.",
  },
  {
    id: "jcally_jm12",
    name: "JCALLY JM12",
    brand: "JCALLY",
    chipset: "KTMicro KT02H20",
    architecture: "ktmicro_dsp",
    dac_type: "hardware_dsp",
    flashable: true,
    vid: 12722, pid: 273,
    resolution: "32-bit / 384 kHz",
    output_power: "30mW @ 32Ω",
    recommendation: "Direct hardware flash via WebHID.",
  },
  {
    id: "jcally_jm6_pro",
    name: "JCALLY JM6 Pro",
    brand: "JCALLY",
    chipset: "Conexant CX31993 + Maxim MAX97220",
    architecture: "conexant_fixed",
    dac_type: "fixed_mask_rom",
    flashable: false,
    vid: 1394, pid: 6920,
    resolution: "32-bit / 384 kHz, DSD256",
    output_power: "60mW @ 32Ω",
    recommendation: "DO NOT FLASH. Fixed mask ROM with OTP registers. Use PipeWire or Wavelet export below.",
  },
  {
    id: "apple_dongle",
    name: "Apple USB-C to 3.5mm Adapter (A2049 / A2155)",
    brand: "Apple",
    chipset: "Cirrus Logic Custom",
    architecture: "generic_uac2",
    dac_type: "host_dsp_only",
    flashable: false,
    vid: 1452, pid: 4362,
    resolution: "24-bit / 48 kHz",
    output_power: "31mW @ 32Ω (US) / 15mW (EU)",
    recommendation: "Fixed-function UAC2. Clean measurements. Use host-side DSP (PipeWire/Wavelet).",
  },
  {
    id: "moondrop_dawn_pro",
    name: "Moondrop Dawn Pro",
    brand: "Moondrop",
    chipset: "Dual Cirrus Logic CS43131",
    architecture: "generic_uac2",
    dac_type: "host_dsp_only",
    flashable: false,
    vid: 12230, pid: 1,
    resolution: "32-bit / 384 kHz, DSD256",
    output_power: "120mW @ 32Ω (4.4mm)",
    recommendation: "Audiophile dual CS43131 flagship. High dynamic range. Use host-side PipeWire/EqualizerAPO.",
  },
  {
    id: "cablecreation_2in1",
    name: "CableCreation 2-in-1 USB-C Audio & PD 100W",
    brand: "CableCreation",
    chipset: "Generic UAC1 Codec + VIA Labs PD Switch",
    architecture: "generic_uac1_pd",
    dac_type: "host_dsp_only",
    flashable: false,
    vid: 3034, pid: 16448,
    resolution: "16-bit / 48 kHz",
    output_power: "20mW @ 32Ω",
    recommendation: "100W PD charging splitter. 16-bit/48kHz fixed codec. No hardware PEQ flash. Use host DSP.",
  },
];

async function loadDacDatabase() {
  dacCatalog = DEFAULT_DACS;
  renderDacDirectory();

  try {
    const res = await fetch("dacs.json");
    if (res.ok) {
      const fullList = await res.json();
      if (Array.isArray(fullList) && fullList.length > 0) {
        dacCatalog = fullList;
        renderDacDirectory();
      }
    }
  } catch (err) {
    console.warn("Could not fetch external dacs.json, using embedded catalog:", err);
  }
}

function findDacInDatabase(vid, pid, prodName = "") {
  const catalog = dacCatalog.length > 0 ? dacCatalog : DEFAULT_DACS;
  for (const d of catalog) {
    if (d.vid === vid && (d.pid === pid || !d.pid)) return d;
  }
  const pLower = (prodName || "").toLowerCase();
  for (const d of catalog) {
    if (pLower && (pLower.includes(d.name.toLowerCase()) || d.name.toLowerCase().includes(pLower))) {
      return d;
    }
  }
  return null;
}

function renderDacDirectory(filter = null, query = null) {
  if (filter !== null) currentDacFilter = filter;
  const container = document.getElementById("dacGrid");
  if (!container) return;

  const searchInput = document.getElementById("dacSearchInput");
  const q = (query !== null ? query : (searchInput ? searchInput.value : "")).trim().toLowerCase();

  const filtered = dacCatalog.filter((d) => {
    if (currentDacFilter === "flashable" && !d.flashable) return false;
    if (currentDacFilter === "blocked" && d.dac_type !== "fixed_mask_rom") return false;
    if (currentDacFilter === "host" && d.dac_type !== "host_dsp_only") return false;
    if (currentDacFilter === "splitter" && d.architecture !== "generic_uac1_pd") return false;

    if (q) {
      const haystack = `${d.name} ${d.brand} ${d.chipset} ${d.architecture} ${d.resolution}`.toLowerCase();
      if (!haystack.includes(q)) return false;
    }
    return true;
  });

  const countAll = document.getElementById("dacCountAll");
  if (countAll) countAll.textContent = dacCatalog.length;

  container.innerHTML = "";
  if (filtered.length === 0) {
    container.innerHTML = `<div style="grid-column: 1/-1; padding: 1.5rem; text-align: center; color: var(--text-secondary); font-size: 0.9rem;">No DACs found matching your search.</div>`;
    return;
  }

  filtered.forEach((d) => {
    const card = document.createElement("div");
    card.className = "dac-card";

    let badgeHtml = "";
    if (d.flashable) {
      badgeHtml = `<span class="dac-badge-flash">Hardware Flashable</span>`;
    } else if (d.dac_type === "fixed_mask_rom") {
      badgeHtml = `<span class="dac-badge-blocked">Fixed Mask ROM</span>`;
    } else {
      badgeHtml = `<span class="dac-badge-host">Host DSP Only</span>`;
    }

    card.innerHTML = `
      <div>
        <div class="dac-card-header">
          <div>
            <div class="dac-card-brand">${d.brand}</div>
            <div class="dac-card-title">${d.name}</div>
          </div>
          ${badgeHtml}
        </div>
        <div class="dac-card-meta" style="margin-top: 0.5rem;">
          <div><span class="dac-chipset-tag">${d.chipset}</span></div>
          <div style="margin-top: 0.35rem; font-size: 0.75rem;"><strong>Resolution:</strong> ${d.resolution}</div>
          <div style="font-size: 0.75rem;"><strong>Output Power:</strong> ${d.output_power}</div>
        </div>
      </div>
      <div class="dac-card-footer">
        ${d.recommendation}
      </div>
    `;
    container.appendChild(card);
  });
}

// ── Toast Notification ────────────────────────────────────────────────────────
function showToast(msg) {
  const toast = document.getElementById("toast");
  if (!toast) return;
  toast.textContent = msg;
  toast.classList.add("show");
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => {
    toast.classList.remove("show");
  }, 3200);
}

// ── Initialization ────────────────────────────────────────────────────────────
window.addEventListener("DOMContentLoaded", () => {
  // Initialize Rust WebAssembly DSP Core
  initWasmEngine().then((ready) => {
    if (ready) {
      const badge = document.getElementById("wasmBadge");
      if (badge) badge.style.display = "inline-flex";
    }
  });

  if (currentPreset.slot_id) {
    const selSlot = document.getElementById("selHardwareSlot");
    if (selSlot) selSlot.value = String(currentPreset.slot_id);
  }

  buildControlsUI();
  renderCurve();

  // Mobile Android WebHID Advisory Banner Check
  const mobileBanner = document.getElementById("mobileWebHidBanner");
  const isMobileUa = /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent || "");
  if (mobileBanner && !navigator.hid && isMobileUa) {
    mobileBanner.classList.add("visible");
  }
  const btnMobileWavelet = document.getElementById("btnMobileWaveletShortcut");
  if (btnMobileWavelet) {
    btnMobileWavelet.addEventListener("click", exportWaveletGraphicEq);
  }

  // Hardware Band Architecture Switcher (5-Band KT02H20 vs 9-Band Moondrop FreeDSP)
  const selHwBands = document.getElementById("selHardwareBandCount");
  if (selHwBands) {
    selHwBands.addEventListener("change", (e) => {
      const count = parseInt(e.target.value, 10) || 5;
      setHardwareBandArchitecture(count);
      showToast(`Switched DSP matrix to ${activeHardwareBands}-Band mode.`);
    });
  }

  // Preset clicks
  document.querySelectorAll(".preset-card").forEach((card) => {
    card.addEventListener("click", () => {
      selectPreset(card.getAttribute("data-preset"));
    });
  });

  // Community Database Search
  const dbInput = document.getElementById("dbSearchInput");
  const btnDbSearch = document.getElementById("btnDbSearch");
  const dbSourceFilter = document.getElementById("dbSourceFilter");

  let dbSearchTimer = null;
  if (dbInput) {
    dbInput.addEventListener("input", () => {
      clearTimeout(dbSearchTimer);
      dbSearchTimer = setTimeout(performDatabaseSearch, 300);
    });
    dbInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        clearTimeout(dbSearchTimer);
        performDatabaseSearch();
      }
    });
  }

  if (btnDbSearch) {
    btnDbSearch.addEventListener("click", performDatabaseSearch);
  }

  if (dbSourceFilter) {
    dbSourceFilter.addEventListener("change", performDatabaseSearch);
  }

  document.querySelectorAll(".quick-tag[data-query]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const q = btn.getAttribute("data-query");
      if (dbInput && q) {
        dbInput.value = q;
        performDatabaseSearch();
      }
    });
  });

  // Action Buttons
  document.getElementById("btnConnect")?.addEventListener("click", connectDac);
  document.getElementById("btnApply")?.addEventListener("click", () => applyToDevice(false));
  document.getElementById("btnReadDac")?.addEventListener("click", () => readFromDevice(false));
  document.getElementById("btnSavePreset")?.addEventListener("click", exportBackupPreset);
  document.getElementById("btnRestoreStock")?.addEventListener("click", restoreStockBackup);
  document.getElementById("btnClearFlash")?.addEventListener("click", clearDeviceFlash);
  document.getElementById("btnFlash")?.addEventListener("click", () => applyToDevice(true));

  // Load Preset File (.json)
  const fileInput = document.getElementById("fileInputPreset");
  document.getElementById("btnLoadPreset")?.addEventListener("click", () => fileInput?.click());
  document.getElementById("lblLoadPreset")?.addEventListener("click", () => fileInput?.click());
  fileInput?.addEventListener("change", async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      const parsed = JSON.parse(text);
      if (!parsed || !Array.isArray(parsed.bands)) {
        throw new Error("Invalid preset format: missing 'bands' array.");
      }
      currentPreset = {
        name: parsed.name || file.name.replace(/\.json$/i, ""),
        slug: (parsed.slug || file.name.replace(/[^a-z0-9_-]/gi, "_")).toLowerCase(),
        description: parsed.description || "Imported custom PEQ preset",
        preamp: typeof parsed.preamp === "number" ? parsed.preamp : 0.0,
        bands: parsed.bands.map((b, i) => ({
          type: b.type || "PK",
          freq: Number(b.freq) || 1000,
          gain: Number(b.gain) || 0,
          q: Number(b.q) || 1.0,
        })),
      };
      if (parsed.slot_id) {
        const selSlot = document.getElementById("selHardwareSlot");
        if (selSlot) selSlot.value = String(parsed.slot_id);
      }
      if (parsed.dac_filter) {
        const selDac = document.getElementById("selDacFilter");
        if (selDac) {
          for (let opt of selDac.options) {
            if (opt.text.toLowerCase().includes(String(parsed.dac_filter).toLowerCase()) || opt.value === String(parsed.dac_filter)) {
              selDac.value = opt.value;
              break;
            }
          }
        }
      }
      activeHardwareBands = Math.min(Math.max(currentPreset.bands.length, 5), 9);
      buildControlsUI();
      renderCurve();
      triggerAutoApply();
      showToast(`Loaded preset "${currentPreset.name}" (Slot ${parsed.slot_id || document.getElementById("selHardwareSlot")?.value || 3})`);
    } catch (err) {
      console.error("Load preset error:", err);
      showToast(`Failed to load preset: ${err.message}`);
    } finally {
      e.target.value = "";
    }
  });

  document.getElementById("btnExportPw")?.addEventListener("click", exportPipeWireConf);
  document.getElementById("btnExportApo")?.addEventListener("click", exportEqualizerApo);
  document.getElementById("btnExportWavelet")?.addEventListener("click", exportWaveletGraphicEq);

  document.getElementById("btnTestNoise")?.addEventListener("click", toggleTestNoise);

  document.getElementById("selDacFilter")?.addEventListener("change", () => triggerAutoApply());
  document.getElementById("selHardwareSlot")?.addEventListener("change", async (e) => {
    const slotId = parseInt(e.target.value, 10) || 3;
    const btnRestore = document.getElementById("btnRestoreStock");
    if (btnRestore && connectedHidDevice) {
      btnRestore.style.display = hasStockBackup(connectedHidDevice, slotId) ? "inline-flex" : "none";
    }
    if (connectedHidDevice && !isDemoMode && !isMoondropFreeDsp(connectedHidDevice)) {
      try {
        await sendHidReport(0x4b, 0x24, 0x57, slotId & 0xff, 0, 0, 0);
        showToast(`Hardware switched to Slot ${slotId}. Reading slot registers...`);
        await readFromDevice(true);
      } catch (err) {
        console.warn("Slot change error:", err);
      }
    } else {
      triggerAutoApply();
    }
  });

  // Auto Headroom Button
  const btnAutoPreamp = document.getElementById("btnAutoPreamp");
  if (btnAutoPreamp) {
    btnAutoPreamp.addEventListener("click", () => {
      const rec = calculateRecommendedPreamp(currentPreset.bands);
      currentPreset.preamp = rec;
      document.getElementById("sliderPreamp").value = rec;
      document.getElementById("lblPreamp").textContent = `${rec > 0 ? "+" : ""}${rec.toFixed(1)} dB`;
      renderCurve();
      triggerAutoApply();
      showToast(`Auto-Headroom set: ${rec > 0 ? "+" : ""}${rec.toFixed(1)} dB (0.5 dB intersample headroom)`);
    });
  }

  // Demo Mode Switch
  document.getElementById("chkDemoMode")?.addEventListener("change", (e) => {
    isDemoMode = e.target.checked;
    if (isDemoMode) {
      updateDeviceBadge("connected", "Virtual KT02H20 (Demo Simulation)");
      updateFlashCounterBadge(null);
      document.getElementById("btnApply").disabled = false;
      document.getElementById("btnReadDac").disabled = false;
      document.getElementById("btnFlash").disabled = false;
      showToast("Demo Mode enabled: Simulated register writes active.");
    } else if (!connectedHidDevice) {
      updateDeviceBadge("disconnected", "No DAC Connected");
      updateFlashCounterBadge(null);
      document.getElementById("btnApply").disabled = true;
      document.getElementById("btnReadDac").disabled = true;
      document.getElementById("btnFlash").disabled = true;
    }
  });

  // Target Curve Overlay Toggle
  const chkShowTarget = document.getElementById("chkShowTarget");
  if (chkShowTarget) {
    chkShowTarget.addEventListener("change", (e) => {
      showTargetOverlay = e.target.checked;
      renderCurve();
    });
  }

  // DAC Hardware Database Directory
  loadDacDatabase();

  const dacSearchInput = document.getElementById("dacSearchInput");
  if (dacSearchInput) {
    dacSearchInput.addEventListener("input", () => {
      renderDacDirectory(null, dacSearchInput.value);
    });
  }

  document.querySelectorAll(".dac-pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      document.querySelectorAll(".dac-pill").forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
      renderDacDirectory(pill.getAttribute("data-filter"));
    });
  });

  // ── WebHID Hotplug & "Remember Connected Devices" Lifecycle ───────────────
  const chkAutoReconnect = document.getElementById("chkAutoReconnect");
  if (chkAutoReconnect) {
    const savedPref = localStorage.getItem("dac_auto_reconnect");
    chkAutoReconnect.checked = savedPref === null ? true : savedPref === "true";
    chkAutoReconnect.addEventListener("change", (e) => {
      localStorage.setItem("dac_auto_reconnect", e.target.checked);
    });
  }

  if (navigator.hid) {
    const shouldAuto = localStorage.getItem("dac_auto_reconnect") !== "false";
    if (shouldAuto) {
      navigator.hid
        .getDevices()
        .then(async (paired) => {
          if (paired && paired.length > 0 && !connectedHidDevice) {
            const matched = paired.find(
              (d) => KTMICRO_FILTERS.some((f) => f.vendorId === d.vendorId) || d.vendorId === 0x0572
            );
            if (matched) {
              await initializeDevice(matched, true);
              showToast(`Auto-reconnected to ${matched.productName || "USB DAC"}`);
            }
          }
        })
        .catch((err) => {
          console.warn("Silent WebHID auto-connect error:", err);
        });
    }

    navigator.hid.addEventListener("connect", async (e) => {
      const allowAuto = localStorage.getItem("dac_auto_reconnect") !== "false";
      if (allowAuto && !connectedHidDevice && !isRebootingPostCommit) {
        await initializeDevice(e.device, false);
      }
    });

    navigator.hid.addEventListener("disconnect", (e) => {
      if (connectedHidDevice === e.device) {
        handleDeviceDisconnect("DAC unplugged from USB port.");
      }
    });
  }

  window.addEventListener("resize", () => renderCurve());
});
