/**
 * dac-peq-manager Web Flasher & Host PEQ Suite
 * Client-side WebHID protocol handler, RBJ biquad math, and interactive SVG curve.
 */

// ── Built-in Presets ───────────────────────────────────────────────────────────
const PRESETS = {
  bmasterx6: {
    name: "BASN BmasterX 6",
    slug: "bmasterx6",
    description: "1DD + 3BA + 2PZT - Tighten 8mm mid-bass warmth, pull vocals forward, tame 9.8kHz ceramic peak.",
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
    description: "Hardware bypass / flat reset - Sets all 5 bands to 1000 Hz 0 dB gain.",
    preamp: 0.0,
    bands: [
      { type: "PK", freq: 1000.0, gain: 0.0, q: 1.00 },
      { type: "PK", freq: 1000.0, gain: 0.0, q: 1.00 },
      { type: "PK", freq: 1000.0, gain: 0.0, q: 1.00 },
      { type: "PK", freq: 1000.0, gain: 0.0, q: 1.00 },
      { type: "PK", freq: 1000.0, gain: 0.0, q: 1.00 },
    ],
  },
};

// ── State ─────────────────────────────────────────────────────────────────────
let currentPreset = JSON.parse(JSON.stringify(PRESETS.bmasterx6));
let connectedHidDevice = null;
let isDemoMode = false;
let isConexantBlocked = false;
let autoApplyTimer = null;
let activeDragIndex = null;

// ── RBJ Biquad Math ───────────────────────────────────────────────────────────
function calculateRBJCoeffs(type, freq, gainDb, q, fs = 48000.0) {
  const f = Math.max(10.0, Math.min(freq, fs * 0.499));
  const Q = Math.max(0.01, q);
  const w0 = (2.0 * Math.PI * f) / fs;
  const cosW0 = Math.cos(w0);
  const sinW0 = Math.sin(w0);
  const A = Math.pow(10.0, gainDb / 40.0);
  const alpha = sinW0 / (2.0 * Q);

  let b0 = 1.0, b1 = 0.0, b2 = 0.0, a0 = 1.0, a1 = 0.0, a2 = 0.0;

  if (type === "PK" || type === "PEAK") {
    b0 = 1.0 + alpha * A;
    b1 = -2.0 * cosW0;
    b2 = 1.0 - alpha * A;
    a0 = 1.0 + alpha / A;
    a1 = -2.0 * cosW0;
    a2 = 1.0 - alpha / A;
  } else if (type === "LSQ" || type === "LOW_SHELF") {
    const twoSqrtAAlpha = 2.0 * Math.sqrt(A) * alpha;
    b0 = A * (A + 1.0 - (A - 1.0) * cosW0 + twoSqrtAAlpha);
    b1 = 2.0 * A * (A - 1.0 - (A + 1.0) * cosW0);
    b2 = A * (A + 1.0 - (A - 1.0) * cosW0 - twoSqrtAAlpha);
    a0 = A + 1.0 + (A - 1.0) * cosW0 + twoSqrtAAlpha;
    a1 = -2.0 * (A - 1.0 + (A + 1.0) * cosW0);
    a2 = A + 1.0 + (A - 1.0) * cosW0 - twoSqrtAAlpha;
  } else if (type === "HSQ" || type === "HIGH_SHELF") {
    const twoSqrtAAlpha = 2.0 * Math.sqrt(A) * alpha;
    b0 = A * (A + 1.0 + (A - 1.0) * cosW0 + twoSqrtAAlpha);
    b1 = -2.0 * A * (A - 1.0 + (A + 1.0) * cosW0);
    b2 = A * (A + 1.0 + (A - 1.0) * cosW0 - twoSqrtAAlpha);
    a0 = A + 1.0 - (A - 1.0) * cosW0 + twoSqrtAAlpha;
    a1 = 2.0 * (A - 1.0 - (A + 1.0) * cosW0);
    a2 = A + 1.0 - (A - 1.0) * cosW0 - twoSqrtAAlpha;
  }

  return {
    b0: b0 / a0,
    b1: b1 / a0,
    b2: b2 / a0,
    a1: a1 / a0,
    a2: a2 / a0,
  };
}

function evaluateBiquadAt(coeffs, freq, fs = 48000.0) {
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

function computeCompositeCurve(bands, preampDb, frequencies) {
  const filters = bands.map((b) => calculateRBJCoeffs(b.type, b.freq, b.gain, b.q));
  return frequencies.map((f) => {
    let db = preampDb;
    for (const filt of filters) {
      db += evaluateBiquadAt(filt, f);
    }
    return db;
  });
}

function generateLogFrequencies(points = 180) {
  const fMin = 20.0, fMax = 20000.0;
  const logMin = Math.log10(fMin);
  const logMax = Math.log10(fMax);
  const step = (logMax - logMin) / (points - 1);
  return Array.from({ length: points }, (_, i) => Math.pow(10.0, logMin + i * step));
}

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
  const width = svg.clientWidth || 800;
  const height = svg.clientHeight || 280;

  // Clear previous elements
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

  // 3. Composite EQ Curve Path
  const frequencies = generateLogFrequencies(220);
  const responses = computeCompositeCurve(currentPreset.bands, currentPreset.preamp, frequencies);

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

    // Draggable point events
    group.addEventListener("mousedown", (e) => startDrag(e, i));
    group.addEventListener("touchstart", (e) => startDragTouch(e, i), { passive: false });
  });

  updateStats();
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

// ── WebHID Hardware Communication ─────────────────────────────────────────────
const KTMICRO_FILTERS = [
  { vendorId: 0x31b2 }, // KTMicro / Kiwi Ears Allegro Mini
  { vendorId: 0x2972 }, // FiiO JA11
  { vendorId: 0x0bda, productId: 0x0023 }, // WalkPlay OEM
  { vendorId: 0x0661 },
  { vendorId: 0x262a },
];

async function connectDac() {
  if (!navigator.hid) {
    showToast("WebHID API is not supported in this browser. Use Chrome/Edge/Brave.");
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

    const dev = devices[0];
    await dev.open();
    connectedHidDevice = dev;

    const vidHex = "0x" + dev.vendorId.toString(16).toUpperCase().padStart(4, "0");
    const pidHex = "0x" + dev.productId.toString(16).toUpperCase().padStart(4, "0");
    const prodName = dev.productName || "USB Audio DSP";

    // Conexant Safety Check
    if (dev.vendorId === 0x0572 || prodName.toLowerCase().includes("cx31993")) {
      isConexantBlocked = true;
      updateDeviceBadge("blocked", `Conexant CX31993 (${vidHex}:${pidHex}) - Fixed Mask ROM`);
      document.getElementById("safetyAlert").classList.add("visible");
      document.getElementById("btnApply").disabled = true;
      document.getElementById("btnFlash").disabled = true;
      showToast("Conexant CX31993: Hardware flashing blocked for safety.");
      return;
    }

    isConexantBlocked = false;
    document.getElementById("safetyAlert").classList.remove("visible");
    document.getElementById("btnApply").disabled = false;
    document.getElementById("btnFlash").disabled = false;
    updateDeviceBadge("connected", `${prodName} (${vidHex}:${pidHex}) - Ready`);
    showToast(`Connected to ${prodName}!`);

  } catch (err) {
    console.error("HID connection error:", err);
    showToast(`Connection failed: ${err.message}`);
  }
}

function updateDeviceBadge(type, text) {
  const badge = document.getElementById("deviceBadge");
  badge.className = `badge ${type}`;
  badge.innerHTML = `<span class="badge-dot"></span> <span>${text}</span>`;
}

async function sendHidReport(reportId, reg, cmd, d0 = 0, d1 = 0, d2 = 0, d3 = 0) {
  if (isDemoMode) {
    console.log(`[Demo Mode HID Tx] Report ${reportId}: Reg 0x${reg.toString(16)} CMD 0x${cmd.toString(16)} Data:`, [d0, d1, d2, d3]);
    return;
  }
  if (!connectedHidDevice) throw new Error("No DAC connected.");

  // 10 bytes payload after reportId
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

  const compensate2X = document.getElementById("chkCompensate2X").checked;
  const REPORT_ID = 0x4b;
  const CMD_WRITE = 0x57;
  const CMD_COMMIT = 0x53;

  try {
    // 1. Enable EQ slot (0x03)
    await sendHidReport(REPORT_ID, 0x24, CMD_WRITE, 0x03, 0, 0, 0);

    // 2. Write 5 bands
    const typeMap = { PK: 0, LSQ: 3, HSQ: 4 };
    for (let i = 0; i < 5; i++) {
      const b = currentPreset.bands[i];
      let freq = b.freq;
      if (compensate2X) freq = freq / 2.0;

      // Gain: signed int16 LE x 10
      let gainScaled = Math.round(b.gain * 10);
      if (gainScaled < 0) gainScaled += 0x10000;
      const gainLo = gainScaled & 0xff;
      const gainHi = (gainScaled >> 8) & 0xff;

      // Freq: uint16 LE
      const freqVal = Math.round(freq);
      const freqLo = freqVal & 0xff;
      const freqHi = (freqVal >> 8) & 0xff;

      // Q: uint16 LE x 1000
      const qScaled = Math.round(b.q * 1000);
      const qLo = qScaled & 0xff;
      const qHi = (qScaled >> 8) & 0xff;

      const typeVal = typeMap[b.type] || 0;

      const regGf = 0x26 + i * 2;
      const regQ = regGf + 1;

      await sendHidReport(REPORT_ID, regGf, CMD_WRITE, gainLo, gainHi, freqLo, freqHi);
      await sendHidReport(REPORT_ID, regQ, CMD_WRITE, qLo, qHi, typeVal, 0);
    }

    // 3. Preamp (Register 0x66 in 0.5 dB steps)
    const preampByte = Math.round(currentPreset.preamp * 2.0) & 0xff;
    await sendHidReport(REPORT_ID, 0x66, CMD_WRITE, preampByte, 0, 0, 0);

    // 3b. Hardware DAC reconstruction filter (Register 0x11)
    const selDac = document.getElementById("selDacFilter");
    if (selDac) {
      const filterVal = parseInt(selDac.value, 10) || 1;
      await sendHidReport(REPORT_ID, 0x11, CMD_WRITE, filterVal, 0, 0, 0);
    }

    // 4. NVRAM Flash Commit
    if (commitFlash) {
      await sendHidReport(REPORT_ID, 0x00, CMD_COMMIT, 0, 0, 0, 0);
      showToast("PEQ burned to hardware NVRAM flash! Settings will persist across host swaps.");
    } else {
      showToast("PEQ written to live DSP RAM (Instant Audition)!");
    }
  } catch (err) {
    console.error("Apply error:", err);
    showToast(`Error communicating with DAC: ${err.message}`);
  }
}

function triggerAutoApply() {
  const autoApply = document.getElementById("chkAutoApply").checked;
  if (!autoApply) return;
  clearTimeout(autoApplyTimer);
  autoApplyTimer = setTimeout(() => {
    applyToDevice(false);
  }, 75);
}

// ── UI Controls & Sync ────────────────────────────────────────────────────────
function buildControlsUI() {
  const container = document.getElementById("controlsContainer");
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

    // Event Listeners
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

  // Preamp slider listener
  const preampInput = document.getElementById("sliderPreamp");
  preampInput.value = currentPreset.preamp;
  document.getElementById("lblPreamp").textContent = `${currentPreset.preamp > 0 ? "+" : ""}${currentPreset.preamp.toFixed(1)} dB`;

  preampInput.oninput = (e) => {
    currentPreset.preamp = parseFloat(e.target.value);
    document.getElementById("lblPreamp").textContent = `${currentPreset.preamp > 0 ? "+" : ""}${currentPreset.preamp.toFixed(1)} dB`;
    renderCurve();
    triggerAutoApply();
  };
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
  statsEl.textContent = `Preamp: ${currentPreset.preamp > 0 ? "+" : ""}${currentPreset.preamp.toFixed(1)} dB | 5 Bands Active | RBJ RBJ Cookbook 48/96kHz`;
}

function selectPreset(slug) {
  const p = PRESETS[slug];
  if (!p) return;
  currentPreset = JSON.parse(JSON.stringify(p));

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

function exportPipeWireConf() {
  const preset = currentPreset;
  const slug = preset.slug || "custom";
  const linear = Math.pow(10.0, preset.preamp / 20.0).toFixed(4);
  const typeMap = { PK: "bq_peaking", LSQ: "bq_lowshelf", HSQ: "bq_highshelf" };

  let nodes = `                    # Preamp Gain Stage (${preset.preamp > 0 ? "+" : ""}${preset.preamp.toFixed(1)} dB)
                    { type = builtin, name = "preamp_fl", label = linear, control = { "Gain" = ${linear} } }
                    { type = builtin, name = "preamp_fr", label = linear, control = { "Gain" = ${linear} } }\n`;

  preset.bands.forEach((b, i) => {
    const idx = i + 1;
    const label = typeMap[b.type] || "bq_peaking";
    nodes += `                    # Band ${idx}: ${b.type} ${b.freq}Hz ${b.gain}dB Q=${b.q}
                    { type = builtin, name = "eq_band${idx}_fl", label = ${label}, control = { "Freq" = ${b.freq.toFixed(1)}, "Gain" = ${b.gain.toFixed(2)}, "Q" = ${b.q.toFixed(2)} } }
                    { type = builtin, name = "eq_band${idx}_fr", label = ${label}, control = { "Freq" = ${b.freq.toFixed(1)}, "Gain" = ${b.gain.toFixed(2)}, "Q" = ${b.q.toFixed(2)} } }\n`;
  });

  let links = `                    { output = "preamp_fl:Out", input = "eq_band1_fl:In" }
                    { output = "preamp_fr:Out", input = "eq_band1_fr:In" }\n`;

  for (let i = 1; i < 5; i++) {
    links += `                    { output = "eq_band${i}_fl:Out", input = "eq_band${i + 1}_fl:In" }
                    { output = "eq_band${i}_fr:Out", input = "eq_band${i + 1}_fr:In" }\n`;
  }

  const conf = `# PipeWire filter-chain configuration for JCALLY JM6 Pro (Conexant CX31993)
# Preset: ${preset.name}
# Generated by dac-peq-manager

context.modules = [
    {
        name = libpipewire-module-filter-chain
        args = {
            node.description = "JCALLY JM6 Pro DSP [${preset.name}]"
            media.name       = "JCALLY JM6 Pro DSP [${preset.name}]"
            filter.graph = {
                nodes = [
${nodes}                ]
                links = [
${links}                ]
                inputs  = [ "preamp_fl:In", "preamp_fr:In" ]
                outputs = [ "eq_band5_fl:Out", "eq_band5_fr:Out" ]
            }
            capture.props = {
                node.name        = "effect_input.jm6pro_${slug}"
                media.class      = "Audio/Sink"
                audio.position   = [ "FL", "FR" ]
            }
            playback.props = {
                node.name        = "effect_output.jm6pro_${slug}"
                node.target      = "alsa_output.usb-Conexant_CX31993*"
                audio.position   = [ "FL", "FR" ]
                node.passive     = true
            }
        }
    }
]
`;
  downloadFile(`99-jm6pro-${slug}.conf`, conf);
  showToast("Downloaded PipeWire configuration!");
}

function exportEqualizerApo() {
  const preset = currentPreset;
  let txt = `# EqualizerAPO Configuration\n# Preset: ${preset.name}\n\nPreamp: ${preset.preamp.toFixed(1)} dB\n`;
  preset.bands.forEach((b, i) => {
    txt += `Filter ${i + 1}: ON ${b.type} Fc ${b.freq.toFixed(1)} Hz Gain ${b.gain > 0 ? "+" : ""}${b.gain.toFixed(1)} dB Q ${b.q.toFixed(2)}\n`;
  });
  downloadFile(`${preset.slug || "preset"}_equalizer_apo.txt`, txt);
  showToast("Downloaded EqualizerAPO profile!");
}

function exportWaveletGraphicEq() {
  const frequencies = generateLogFrequencies(127);
  const curve = computeCompositeCurve(currentPreset.bands, currentPreset.preamp, frequencies);
  const pairs = frequencies.map((f, i) => `${Math.round(f)} ${curve[i].toFixed(1)}`);
  const txt = "GraphicEQ: " + pairs.join("; ") + "\n";
  downloadFile(`${currentPreset.slug || "preset"}_wavelet_graphiceq.txt`, txt);
  showToast("Downloaded Wavelet GraphicEQ profile!");
}

// ── Web Audio Test Tone Generator ─────────────────────────────────────────────
let audioCtx = null;
let noiseNode = null;
let isPlayingNoise = false;

function toggleTestNoise() {
  const btn = document.getElementById("btnTestNoise");
  if (!isPlayingNoise) {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const bufferSize = audioCtx.sampleRate * 2;
    const noiseBuffer = audioCtx.createBuffer(1, bufferSize, audioCtx.sampleRate);
    const output = noiseBuffer.getChannelData(0);

    // Pink noise approximation
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
    noiseNode.connect(audioCtx.destination);
    noiseNode.start();

    isPlayingNoise = true;
    btn.textContent = "Stop Pink Noise";
    btn.classList.add("btn-burn");
  } else {
    if (noiseNode) noiseNode.stop();
    isPlayingNoise = false;
    btn.textContent = "Play Pink Noise";
    btn.classList.remove("btn-burn");
  }
}

// ── Toast Notification ────────────────────────────────────────────────────────
function showToast(msg) {
  const toast = document.getElementById("toast");
  toast.textContent = msg;
  toast.classList.add("show");
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => {
    toast.classList.remove("show");
  }, 3200);
}

// ── Initialization ────────────────────────────────────────────────────────────
window.addEventListener("DOMContentLoaded", () => {
  buildControlsUI();
  renderCurve();

  // Preset clicks
  document.querySelectorAll(".preset-card").forEach((card) => {
    card.addEventListener("click", () => {
      selectPreset(card.getAttribute("data-preset"));
    });
  });

  // Action Buttons
  document.getElementById("btnConnect").addEventListener("click", connectDac);
  document.getElementById("btnApply").addEventListener("click", () => applyToDevice(false));
  document.getElementById("btnFlash").addEventListener("click", () => applyToDevice(true));

  document.getElementById("btnExportPw").addEventListener("click", exportPipeWireConf);
  document.getElementById("btnExportApo").addEventListener("click", exportEqualizerApo);
  document.getElementById("btnExportWavelet").addEventListener("click", exportWaveletGraphicEq);

  document.getElementById("btnTestNoise").addEventListener("click", toggleTestNoise);

  const selDac = document.getElementById("selDacFilter");
  if (selDac) {
    selDac.addEventListener("change", () => triggerAutoApply());
  }

  // Demo Mode Switch
  document.getElementById("chkDemoMode").addEventListener("change", (e) => {
    isDemoMode = e.target.checked;
    if (isDemoMode) {
      updateDeviceBadge("connected", "Virtual KT02H20 (Demo Simulation)");
      document.getElementById("btnApply").disabled = false;
      document.getElementById("btnFlash").disabled = false;
      showToast("Demo Mode enabled: Simulated register writes active.");
    } else {
      if (!connectedHidDevice) {
        updateDeviceBadge("disconnected", "No DAC Connected");
        document.getElementById("btnApply").disabled = true;
        document.getElementById("btnFlash").disabled = true;
      }
    }
  });

  // Window resize -> redraw SVG
  window.addEventListener("resize", () => renderCurve());
});
