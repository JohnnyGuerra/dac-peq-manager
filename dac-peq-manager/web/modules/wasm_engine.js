/**
 * dac-peq-manager Rust WebAssembly Engine Bridge
 * Integrates compiled Rust core (crates/dac-peq-wasm) into the browser Web Flasher.
 */

import init, * as wasm from "../wasm/dac_peq_wasm.js";

let wasmReady = false;

export async function initWasmEngine() {
  if (wasmReady) return true;
  try {
    await init();
    wasmReady = true;
    console.log(`%c[WASM Engine] Rust Core v${wasm.wasm_version()} active`, "color: #10b981; font-weight: bold;");
    return true;
  } catch (err) {
    console.warn("[WASM Engine] Could not load WASM module, falling back to pure JavaScript math:", err);
    wasmReady = false;
    return false;
  }
}

export function isWasmReady() {
  return wasmReady;
}

export { wasm };
