/**
 * WebHID Transport, Register Framing (KTMicro KT02H20 & Moondrop FreeDSP),
 * Firmware Clock Quirk Detection, NVRAM Wear Tracker, and Event-Driven USB Re-Enumeration.
 */

export const KTMICRO_FILTERS = [
  { vendorId: 0x31b2 }, // KTMicro / Kiwi Ears Allegro Mini / Moondrop FreeDSP
  { vendorId: 0x2972 }, // FiiO JA11
  { vendorId: 0x0bda, productId: 0x0023 }, // WalkPlay OEM
  { vendorId: 0x0661 },
  { vendorId: 0x262a },
];

export function isMoondropFreeDsp(dev) {
  if (!dev) return false;
  const prod = (dev.productName || "").toLowerCase();
  return (
    (dev.vendorId === 0x31b2 && dev.productId === 0x0112) ||
    prod.includes("freedsp") ||
    prod.includes("may dsp") ||
    prod.includes("chu ii dsp")
  );
}

// ── NVRAM Flash Wear-Out Health Tracker ───────────────────────────────────────
export function getFlashWearKey(dev) {
  if (!dev) return "dac_flash_history_generic";
  const vid = (dev.vendorId || 0).toString(16).toLowerCase().padStart(4, "0");
  const pid = (dev.productId || 0).toString(16).toLowerCase().padStart(4, "0");
  return `dac_flash_history_${vid}_${pid}`;
}

export function getFlashStats(dev, storage = globalThis.localStorage) {
  if (!storage) return { total: 0, timestamps: [] };
  const key = getFlashWearKey(dev);
  try {
    const raw = storage.getItem(key);
    if (!raw) return { total: 0, timestamps: [] };
    const parsed = JSON.parse(raw);
    const total = typeof parsed.total === "number" ? parsed.total : (typeof parsed === "number" ? parsed : 0);
    const timestamps = Array.isArray(parsed.timestamps) ? parsed.timestamps : [];
    return { total, timestamps };
  } catch {
    return { total: 0, timestamps: [] };
  }
}

export function recordFlashCommit(dev, storage = globalThis.localStorage) {
  const key = getFlashWearKey(dev);
  const stats = getFlashStats(dev, storage);
  const now = Date.now();
  stats.total += 1;
  stats.timestamps.push(now);
  const oneDayAgo = now - 24 * 3600 * 1000;
  stats.timestamps = stats.timestamps.filter((t) => t > oneDayAgo);
  if (storage) {
    try {
      storage.setItem(key, JSON.stringify(stats));
    } catch (e) {
      console.warn("Could not save flash stats to localStorage:", e);
    }
  }
  return stats;
}

// ── Factory Stock Backup Tracker ──────────────────────────────────────────────
export function getStockBackupKey(dev, slotId = 3) {
  if (!dev) return `dac_stock_backup_generic_slot${slotId}`;
  const vid = (dev.vendorId || 0).toString(16).toLowerCase().padStart(4, "0");
  const pid = (dev.productId || 0).toString(16).toLowerCase().padStart(4, "0");
  return `dac_stock_backup_${vid}_${pid}_slot${slotId}`;
}

export function getStockBackup(dev, slotId = 3, storage = globalThis.localStorage) {
  if (!storage) return null;
  const key = getStockBackupKey(dev, slotId);
  try {
    const raw = storage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function saveStockBackup(dev, slotId = 3, preset, storage = globalThis.localStorage) {
  if (!storage || !preset) return false;
  const key = getStockBackupKey(dev, slotId);
  try {
    if (!storage.getItem(key)) {
      storage.setItem(key, JSON.stringify(preset));
      return true;
    }
  } catch (e) {
    console.warn("Could not save stock backup to localStorage:", e);
  }
  return false;
}

export function hasStockBackup(dev, slotId = 3, storage = globalThis.localStorage) {
  if (!storage) return false;
  const key = getStockBackupKey(dev, slotId);
  return Boolean(storage.getItem(key));
}

// ── Firmware Clock Divisor Quirk Prober ───────────────────────────────────────
export function detectFirmwareQuirks(dev) {
  if (!dev) return { requiresCompensate2X: false, reason: "No device" };
  const vid = dev.vendorId || 0;
  const pid = dev.productId || 0;
  const version = typeof dev.deviceVersion === "number" ? dev.deviceVersion : 0x0100;
  const prodName = (dev.productName || "").toLowerCase();

  if (isMoondropFreeDsp(dev)) {
    return {
      requiresCompensate2X: false,
      reason: "Moondrop FreeDSP 9-Band Architecture: Standard clocking",
    };
  }

  // FiiO JA11 firmware v1.8+ (deviceVersion >= 0x0180) has 2X clock divisor bug patched upstream
  if (vid === 0x2972 && version >= 0x0180) {
    return {
      requiresCompensate2X: false,
      reason: `FiiO JA11 firmware v${(version / 256).toFixed(1)}: Native clocking (no 2X divisor needed)`,
    };
  }

  // Generic KT02H20 / WalkPlay (VID 0x31b2, 0x0bda) or older bcdDevice <= 0x0100
  if (vid === 0x31b2 || (vid === 0x0bda && pid === 0x0023) || version <= 0x0100 || prodName.includes("allegro")) {
    return {
      requiresCompensate2X: true,
      reason: `KT02H20 v${(version / 256).toFixed(1)} quirk: 48kHz clock requires 2X divisor compensation`,
    };
  }

  return { requiresCompensate2X: false, reason: "Standard clocking" };
}

// ── Packet Encoders ───────────────────────────────────────────────────────────
export function encodeKtMicroBandPackets(bandIndex, band, compensate2X = false) {
  const typeMap = { PK: 0, LSQ: 3, HSQ: 4 };
  let freq = Number(band.freq ?? 1000.0);
  if (compensate2X) freq = freq / 2.0;

  let gainScaled = Math.round(Number(band.gain ?? 0.0) * 10);
  if (gainScaled < 0) gainScaled += 0x10000;
  const gainLo = gainScaled & 0xff;
  const gainHi = (gainScaled >> 8) & 0xff;

  const freqVal = Math.round(freq);
  const freqLo = freqVal & 0xff;
  const freqHi = (freqVal >> 8) & 0xff;

  const qScaled = Math.round(Number(band.q ?? 1.0) * 1000);
  const qLo = qScaled & 0xff;
  const qHi = (qScaled >> 8) & 0xff;

  const typeVal = typeMap[String(band.type || "PK").toUpperCase()] ?? 0;

  const regGf = 0x26 + bandIndex * 2;
  const regQ = regGf + 1;

  return {
    regGf,
    regQ,
    gfData: [gainLo, gainHi, freqLo, freqHi],
    qData: [qLo, qHi, typeVal, 0],
  };
}

export function encodeMoondropReport(bands, preampDb, commitFlash = false) {
  const typeMap = { PK: 0, LSQ: 1, HSQ: 2 };
  const cmdByte = commitFlash ? 0x21 : 0x20;
  const payload = new Uint8Array(64);
  const activeBands = bands.slice(0, 9);

  payload[0] = cmdByte;
  payload[1] = activeBands.length & 0xff;

  let preampScaled = Math.round(Number(preampDb ?? 0.0) * 100.0);
  if (preampScaled < 0) preampScaled += 0x10000;
  payload[2] = preampScaled & 0xff;
  payload[3] = (preampScaled >> 8) & 0xff;

  let offset = 4;
  for (const b of activeBands) {
    const ftype = typeMap[String(b.type || "PK").toUpperCase()] ?? 0;
    const freq = Math.round(Number(b.freq ?? 1000.0));
    let gain = Math.round(Number(b.gain ?? 0.0) * 10.0);
    if (gain < 0) gain += 256;
    const qVal = Math.round(Number(b.q ?? 1.0) * 10.0) & 0xff;

    payload[offset] = ftype & 0xff;
    payload[offset + 1] = freq & 0xff;
    payload[offset + 2] = (freq >> 8) & 0xff;
    payload[offset + 3] = gain & 0xff;
    payload[offset + 4] = qVal & 0xff;
    offset += 5;
  }

  return payload;
}

// ── Event-Driven Post-Commit USB Re-Enumeration Watcher ───────────────────────
export function waitForUsbReenumeration(hidApi, filters = KTMICRO_FILTERS, timeoutMs = 4000, pollIntervalMs = 200) {
  if (!hidApi) return Promise.resolve(null);

  return new Promise((resolve) => {
    let settled = false;
    let pollTimer = null;
    let timeoutTimer = null;

    const cleanup = () => {
      settled = true;
      if (pollTimer) clearInterval(pollTimer);
      if (timeoutTimer) clearTimeout(timeoutTimer);
      if (typeof hidApi.removeEventListener === "function") {
        hidApi.removeEventListener("connect", onConnect);
      }
    };

    const onConnect = (e) => {
      if (settled) return;
      const dev = e && e.device;
      if (dev && filters.some((f) => f.vendorId === dev.vendorId)) {
        cleanup();
        resolve(dev);
      }
    };

    if (typeof hidApi.addEventListener === "function") {
      hidApi.addEventListener("connect", onConnect);
    }

    // Also poll getDevices() every 200ms after a 250ms initial reboot grace window
    setTimeout(() => {
      if (settled) return;
      pollTimer = setInterval(async () => {
        if (settled) return;
        try {
          const paired = await hidApi.getDevices();
          if (paired && paired.length > 0) {
            const matched = paired.find((d) => filters.some((f) => f.vendorId === d.vendorId));
            if (matched) {
              cleanup();
              resolve(matched);
            }
          }
        } catch {
          // Ignore transient USB bus enumeration errors during reboot
        }
      }, pollIntervalMs);
    }, 250);

    timeoutTimer = setTimeout(async () => {
      if (settled) return;
      let fallbackDevice = null;
      try {
        const paired = await hidApi.getDevices();
        if (paired && paired.length > 0) {
          fallbackDevice = paired.find((d) => filters.some((f) => f.vendorId === d.vendorId)) || null;
        }
      } catch {
        // Ignore
      }
      cleanup();
      resolve(fallbackDevice);
    }, timeoutMs);
  });
}

// ── Two-Way WebHID Register Readback ──────────────────────────────────────────

export function decodeKtMicroBandRegisters(gfResp, qResp, compensate2X = false) {
  const typeRevMap = { 0: "PK", 3: "LSQ", 4: "HSQ" };
  const gainRaw = gfResp[6] | (gfResp[7] << 8);
  const gainSigned = gainRaw > 0x7fff ? gainRaw - 0x10000 : gainRaw;
  const gainDb = Math.round((gainSigned / 10.0) * 10) / 10;

  let freqHz = gfResp[8] | (gfResp[9] << 8);
  if (compensate2X) freqHz = freqHz * 2.0;

  const qRaw = qResp[6] | (qResp[7] << 8);
  const qVal = Math.round((qRaw / 1000.0) * 100) / 100;
  const typeVal = qResp[8];
  const ftype = typeRevMap[typeVal] || "PK";

  return {
    type: ftype,
    freq: freqHz,
    gain: gainDb,
    q: qVal,
  };
}

export function readKtMicroRegister(dev, reg, timeoutMs = 500) {
  if (!dev) return Promise.reject(new Error("No device provided."));

  return new Promise((resolve, reject) => {
    let timer = null;

    const onInputReport = (event) => {
      const dv = event.data;
      if (!dv || dv.byteLength < 6) return;
      const respReg = dv.getUint8(0);
      const respCmd = dv.getUint8(4);

      if (respReg === reg && respCmd === 0x52) {
        cleanup();
        const bytes = [];
        for (let i = 0; i < dv.byteLength; i++) {
          bytes.push(dv.getUint8(i));
        }
        resolve(bytes);
      }
    };

    const cleanup = () => {
      if (timer) clearTimeout(timer);
      try {
        dev.removeEventListener("inputreport", onInputReport);
      } catch (_) {}
    };

    timer = setTimeout(() => {
      cleanup();
      reject(new Error(`Timeout reading register 0x${reg.toString(16).toUpperCase().padStart(2, "0")}`));
    }, timeoutMs);

    try {
      dev.addEventListener("inputreport", onInputReport);
      const REPORT_ID = 0x4b;
      const CMD_READ = 0x52;
      const payload = new Uint8Array([
        reg & 0xff, 0x00, 0x00, 0x00,
        CMD_READ, 0x00,
        0x00, 0x00, 0x00, 0x00,
      ]);
      dev.sendReport(REPORT_ID, payload).catch((err) => {
        cleanup();
        reject(err);
      });
    } catch (err) {
      cleanup();
      reject(err);
    }
  });
}

export async function readKtMicroPeq(dev, compensate2X = false) {
  // 1. Slot (0x24)
  let slotId = 3;
  try {
    const slotResp = await readKtMicroRegister(dev, 0x24);
    if (slotResp && slotResp.length > 6) slotId = slotResp[6];
  } catch (err) {
    console.warn("Could not read slot ID register 0x24:", err);
  }

  // 2. Preamp (0x66)
  let preampDb = 0.0;
  try {
    const preampResp = await readKtMicroRegister(dev, 0x66);
    if (preampResp && preampResp.length > 6) {
      const raw = preampResp[6];
      const signed = raw > 127 ? raw - 256 : raw;
      preampDb = Math.round((signed / 2.0) * 10) / 10;
    }
  } catch (err) {
    console.warn("Could not read preamp register 0x66:", err);
  }

  // 3. DAC filter (0x11)
  let dacFilter = 1;
  try {
    const filtResp = await readKtMicroRegister(dev, 0x11, 200);
    if (filtResp && filtResp.length > 6) dacFilter = filtResp[6];
  } catch (_) {}

  // 4. Five bands (0x26 - 0x2F)
  const bands = [];
  for (let i = 0; i < 5; i++) {
    const regGf = 0x26 + i * 2;
    const regQ = regGf + 1;
    const gfResp = await readKtMicroRegister(dev, regGf);
    const qResp = await readKtMicroRegister(dev, regQ);
    const bandData = decodeKtMicroBandRegisters(gfResp, qResp, compensate2X);
    bandData.index = i + 1;
    bands.push(bandData);
  }

  return {
    slotId,
    preamp: preampDb,
    dacFilter,
    bands,
  };
}

export function decodeMoondropReport(raw) {
  const typeRevMap = { 0: "PK", 1: "LSQ", 2: "HSQ" };
  const numBands = Math.min(9, Math.max(1, raw[1] || 1));
  let preampRaw = raw[2] | (raw[3] << 8);
  if (preampRaw > 32767) preampRaw -= 65536;
  const preampDb = Math.round((preampRaw / 100.0) * 10) / 10;

  const bands = [];
  let offset = 4;
  for (let i = 0; i < numBands; i++) {
    if (offset + 5 > raw.length) break;
    const typeVal = raw[offset];
    const ftype = typeRevMap[typeVal] || "PK";
    const freqHz = raw[offset + 1] | (raw[offset + 2] << 8);
    let gainRaw = raw[offset + 3];
    if (gainRaw > 127) gainRaw -= 256;
    const gainDb = Math.round((gainRaw / 10.0) * 10) / 10;
    const qRaw = raw[offset + 4];
    const qVal = Math.round((qRaw / 10.0) * 100) / 100;
    bands.push({
      index: i + 1,
      type: ftype,
      freq: freqHz,
      gain: gainDb,
      q: qVal,
    });
    offset += 5;
  }
  while (bands.length < 9) {
    bands.push({
      index: bands.length + 1,
      type: "PK",
      freq: 1000.0,
      gain: 0.0,
      q: 1.0,
    });
  }
  return { preamp: preampDb, bands };
}

export function readMoondropReport(dev, timeoutMs = 500) {
  if (!dev) return Promise.reject(new Error("No device provided."));

  return new Promise((resolve, reject) => {
    let timer = null;

    const onInputReport = (event) => {
      const dv = event.data;
      if (!dv || dv.byteLength < 4) return;
      cleanup();
      const bytes = [];
      for (let i = 0; i < dv.byteLength; i++) {
        bytes.push(dv.getUint8(i));
      }
      resolve(decodeMoondropReport(bytes));
    };

    const cleanup = () => {
      if (timer) clearTimeout(timer);
      try {
        dev.removeEventListener("inputreport", onInputReport);
      } catch (_) {}
    };

    timer = setTimeout(() => {
      cleanup();
      reject(new Error("Timeout reading Moondrop FreeDSP status report."));
    }, timeoutMs);

    try {
      dev.addEventListener("inputreport", onInputReport);
      const req = new Uint8Array(64);
      req[0] = 0x22;
      dev.sendReport(0x00, req).catch((err) => {
        cleanup();
        reject(err);
      });
    } catch (err) {
      cleanup();
      reject(err);
    }
  });
}
