/* tslint:disable */
/* eslint-disable */

export function calculate_biquad(filter_type: string, freq: number, gain_db: number, q: number, fs: number): Float64Array;

export function calculate_curve_difference_json(bands_a_json: string, preamp_a: number, bands_b_json: string, preamp_b: number, fs: number, points: number): string;

export function calculate_peak_gain(bands_json: string, fs: number): number;

export function calculate_recommended_preamp(bands_json: string, headroom_db: number, fs: number): number;

export function check_is_conexant_cx31993(vid: number, pid: number, product_name?: string | null): boolean;

export function compute_composite_curve(bands_json: string, preamp_db: number, points: number, fs: number): Float64Array;

export function decimate_bands_json(bands_json: string, target_bands: number, refit_gains: boolean, fs: number): string;

export function encode_factory_reset_report(): Uint8Array;

export function encode_ktmicro_payload(preset_json: string, vid: number, pid: number, slot_id: number, compensate_2x: boolean, commit_nvram: boolean): Array<any>;

export function encode_nvram_commit_report(): Uint8Array;

export function export_apo_txt(preset_json: string): string;

export function export_pipewire_conf(preset_json: string, sink_target?: string | null): string;

export function export_wavelet_txt(preset_json: string): string;

export function wasm_version(): string;

export type InitInput = RequestInfo | URL | Response | BufferSource | WebAssembly.Module;

export interface InitOutput {
    readonly memory: WebAssembly.Memory;
    readonly calculate_biquad: (a: number, b: number, c: number, d: number, e: number, f: number) => [number, number];
    readonly calculate_curve_difference_json: (a: number, b: number, c: number, d: number, e: number, f: number, g: number, h: number) => [number, number, number, number];
    readonly calculate_peak_gain: (a: number, b: number, c: number) => [number, number, number];
    readonly calculate_recommended_preamp: (a: number, b: number, c: number, d: number) => [number, number, number];
    readonly check_is_conexant_cx31993: (a: number, b: number, c: number, d: number) => number;
    readonly compute_composite_curve: (a: number, b: number, c: number, d: number, e: number) => [number, number, number, number];
    readonly decimate_bands_json: (a: number, b: number, c: number, d: number, e: number) => [number, number, number, number];
    readonly encode_factory_reset_report: () => any;
    readonly encode_ktmicro_payload: (a: number, b: number, c: number, d: number, e: number, f: number, g: number) => [number, number, number];
    readonly encode_nvram_commit_report: () => any;
    readonly export_apo_txt: (a: number, b: number) => [number, number, number, number];
    readonly export_pipewire_conf: (a: number, b: number, c: number, d: number) => [number, number, number, number];
    readonly export_wavelet_txt: (a: number, b: number) => [number, number, number, number];
    readonly wasm_version: () => [number, number];
    readonly __wbindgen_externrefs: WebAssembly.Table;
    readonly __wbindgen_malloc: (a: number, b: number) => number;
    readonly __wbindgen_realloc: (a: number, b: number, c: number, d: number) => number;
    readonly __wbindgen_free: (a: number, b: number, c: number) => void;
    readonly __externref_table_dealloc: (a: number) => void;
    readonly __wbindgen_start: () => void;
}

export type SyncInitInput = BufferSource | WebAssembly.Module;

/**
 * Instantiates the given `module`, which can either be bytes or
 * a precompiled `WebAssembly.Module`.
 *
 * @param {{ module: SyncInitInput }} module - Passing `SyncInitInput` directly is deprecated.
 *
 * @returns {InitOutput}
 */
export function initSync(module: { module: SyncInitInput } | SyncInitInput): InitOutput;

/**
 * If `module_or_path` is {RequestInfo} or {URL}, makes a request and
 * for everything else, calls `WebAssembly.instantiate` directly.
 *
 * @param {{ module_or_path: InitInput | Promise<InitInput> }} module_or_path - Passing `InitInput` directly is deprecated.
 *
 * @returns {Promise<InitOutput>}
 */
export default function __wbg_init (module_or_path?: { module_or_path: InitInput | Promise<InitInput> } | InitInput | Promise<InitInput>): Promise<InitOutput>;
