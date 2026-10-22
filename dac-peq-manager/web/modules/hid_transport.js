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
