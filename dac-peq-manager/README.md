# `dac-peq-manager` (Hardware DSP Flasher & Host PEQ Suite)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://www.python.org/)
[![Hardware: KTMicro KT02H20](https://img.shields.io/badge/SoC-KTMicro%20KT02H20-orange.svg)](#hardware-support-matrix)
[![Host DSP: PipeWire & Wavelet](https://img.shields.io/badge/DSP-PipeWire%20%7C%20Wavelet%20%7C%20EqualizerAPO-purple.svg)](#host-side-dsp-suite)

A modular command-line tool, hardware DSP configuration suite, and host-side equalizer bridge that manages 5-band Parametric EQ (PEQ) across portable USB-C DACs and Tribrid In-Ear Monitors (IEMs).

---

## 1. Overview & Hardware Support Matrix

`dac-peq-manager` addresses the dual-architecture reality of portable USB-C DAC dongles:

1. **Hardware Flashable SoC DACs (KTMicro KT02H20 / WalkPlay HID):**
   * **Devices:** **Kiwi Ears Allegro Mini**, **BASN BmasterX 6 Modular Type-C DSP Plug**, **FiiO / JadeAudio JA11**, **JCALLY JM12**.
   * **Action:** Direct USB HID register programming via `hidapi`. Modifies live DSP RAM registers (`apply`) or permanently commits to onboard non-volatile flash memory (`flash` with command `0x53`).
   * **Result:** Settings persist across host swaps (Linux PC, Android smartphone, iPhone 15/16, Mac, iPad, handheld consoles).
2. **Fixed-Function UAC2 DACs (Conexant CX31993 + Maxim MAX97220):**
   * **Devices:** **JCALLY JM6 Pro**.
   * **Hardware Reality:** The CX31993 uses fixed mask ROM and one-time programmable (OTP) descriptors. It has no user-writable DSP NVRAM. Attempting vendor HID register writes will brick or corrupt USB descriptors.
   * **Action:** Automatically generates host-side DSP configurations:
     * **Linux:** Linux PipeWire `filter-chain` (`.conf`) bound directly to the `alsa_output.usb-Conexant_CX31993*` hardware sink.
     * **Windows:** **EqualizerAPO** `.txt` configuration.
     * **Android:** **Wavelet** 9-band JSON profiles and 127-point AutoEq-compatible `GraphicEQ.txt`.

### Hardware Compatibility Table

| Device | Chipset / Architecture | USB VID:PID | DSP Capability | Managed By |
| :--- | :--- | :--- | :--- | :--- |
| **Kiwi Ears Allegro Mini** | KTMicro `KT02H20` / `CB1200AU` | `0x31B2:0x0111` | 5-Band Hardware Biquad PEQ + Preamp in NVRAM | `dac-peq-manager apply / flash` |
| **BASN BmasterX 6 Modular Type-C DSP Plug** | OEM KTMicro / WalkPlay DSP Termination | Dynamic HID Scan | 5-Band Hardware Biquad PEQ in NVRAM | `dac-peq-manager apply / flash` |
| **FiiO / JadeAudio JA11** | KTMicro `KT02H20` | `0x2972:0x0102` | 5-Band Hardware Biquad PEQ in NVRAM | `dac-peq-manager apply / flash` |
| **JCALLY JM6 Pro** | Conexant `CX31993` + `MAX97220` | `0x0572:0x1B08` | Fixed 32-bit/384kHz UAC2 (No onboard flash) | `dac-peq-manager export-pipewire / export-apo` |

---

## 2. Production-Hardening & Reliability Features

`dac-peq-manager` incorporates four production-hardening pillars designed to eliminate guesswork, protect hardware silicon, and preserve acoustic fidelity:

### 1. Dual-Curve Visual Target vs. Decimated Hardware Comparison
* **Web Flasher Dual SVG Overlay:** When pulling AutoEq profiles or reference targets, the original uncompressed 10-band target curve is rendered as a dashed reference line alongside the active 5-band hardware curve.
* **Acoustic Delta & RMS Tracking:** Displays real-time Root-Mean-Square (RMS) error and peak frequency deviation (e.g. `RMS: ±0.7 dB | Peak Δ: +1.4 dB @ 3.2 kHz`) directly above the SVG graph.
* **CLI Delta Comparison:** Use `plot --compare` to evaluate the acoustic delta between any two presets:
  ```bash
  dac-peq-manager plot ew300-silver --compare harman_in_ear_2019v2
  ```

### 2. Physical NVRAM Flash Health & Wear-Out Tracker
* **Endurance Protection:** Microcontroller EEPROMs lack wear leveling (~10k-100k cycle limit).
* **Wear Log & Alerts:** Persists timestamped write commits keyed by USB VID:PID in `~/.cache/dac-peq-manager/flash_history.json` and browser `localStorage`.
* **Warning Safeguards:** Triggers cautionary alerts if flash writes exceed **10 burns in 24 hours** or **50 cumulative burns**, prompting users to audition in live RAM first.
* **CLI Flash Audit:** Inspect device write history anytime:
  ```bash
  dac-peq-manager flash-history
  ```

### 3. Automated Firmware Clock Divisor Quirk Detection
* **Zero Guesswork:** Automatically detects the KTMicro 2X clock divisor bug by probing USB release numbers (`bcdDevice`).
* **Auto-Compensation:** Generic KT02H20 firmwares (`bcdDevice <= 0x0100`) automatically enable 2X compensation; modern patched firmwares (FiiO JA11 v1.8+, Allegro Mini v2) operate with native 1X clocking.
* **Manual Override:** Users can still manually toggle `--compensate-2x` if desired.

### 4. Full-Fidelity 10-Band Host DSP Export Pipeline
* **Target Fidelity Preservation:** Physical 5-band constraints apply only to hardware registers. Software equalizers (PipeWire, EqualizerAPO, Wavelet) can process arbitrary filter counts.
* **Full-Fidelity Exports:** Export full 10-band target profiles without decimation:
  ```bash
  dac-peq-manager export-pipewire "autoeq:Moondrop Aria" --full-target
  dac-peq-manager export-apo "autoeq:Moondrop Aria" --full-target
  ```
* **Web Flasher Export Selector:** Choose between "Hardware 5-Band Match" or "Full 10-Band Target Fidelity" with one click.

### 5. Cross-Engine Python/JS Mathematical Parity & Modular ES6 Architecture
* **Zero-Build Native ES6 Modules:** The Web Flasher is cleanly decomposed into [`web/modules/biquad_math.js`](file:///home/ubuntu/iem/dac-peq-manager/web/modules/biquad_math.js), [`web/modules/exporters.js`](file:///home/ubuntu/iem/dac-peq-manager/web/modules/exporters.js), [`web/modules/hid_transport.js`](file:///home/ubuntu/iem/dac-peq-manager/web/modules/hid_transport.js), and [`web/modules/autoeq_client.js`](file:///home/ubuntu/iem/dac-peq-manager/web/modules/autoeq_client.js)—running natively in browsers and Node.js without any build step.
* **Cross-Engine Parity Verification:** [`tests/test_cross_engine_parity.py`](file:///home/ubuntu/iem/dac-peq-manager/tests/test_cross_engine_parity.py) executes the JavaScript DSP modules inside Node.js and asserts `< 1e-9` floating-point parity against Python (`dac_peq.biquad` and `dac_peq.exporters`).

### 6. Event-Driven USB Re-Enumeration, Multi-Slot (`0x01`–`0x04`) & 9-Band FreeDSP
* **Event-Driven Post-Commit Recovery:** Replaces fixed sleep delays after `0x53` NVRAM flash commits with active USB bus re-enumeration polling (`_wait_for_reenumeration` in Python and `waitForUsbReenumeration` in WebHID).
* **Multi-Slot Hardware Memory (`0x01`–`0x04`):** Select between onboard KT02H20 memory slots `1` through `4` via `--slot / -s` in the CLI or the Memory Slot dropdown in the Web UI (defaulting to **Slot 3 (`0x03`)** for full backward compatibility).
* **9-Band Moondrop FreeDSP Support:** Automatic hardware dispatch (`0x31B2:0x0112`) and interactive 5-Band / 9-Band matrix switching in the Web Flasher.

### 7. Offline AutoEq Snapshot (Top 15 Reddit IEMs) & Mobile Android Advisory
* **100% Offline Resilience:** Bundles [`data/autoeq_fallback.json`](file:///home/ubuntu/iem/dac-peq-manager/data/autoeq_fallback.json) (and mirrors in [`web/modules/autoeq_client.js`](file:///home/ubuntu/iem/dac-peq-manager/web/modules/autoeq_client.js)) with the top 15 Reddit `r/iems` & `r/inearfidelity` benchmarks (*Truthear Zero:RED, Truthear Hexa, Moondrop Chu II, Moondrop Aria, Moondrop Blessing 3, SIMGOT EW300, SIMGOT SuperMix 4, SIMGOT EM6L, Tangzu Wan'er S.G, 7Hz Zero:2, 7Hz Timeless, Kiwi Ears Cadenza, Letshuoer S12 Pro, BASN BmasterX 6, Sennheiser HD 600*) when GitHub Raw is unreachable.
* **Mobile Android WebHID Banner:** Automatically detects Android mobile browsers where WebHID is unsupported and provides a one-click **Export Wavelet GraphicEQ (.txt)** workflow.

---

## 2. Bundled Acoustic Presets

The suite includes four reference acoustic curves tailored for Tribrid IEM driver configurations:

### Preset 1: `bmasterx6` (BASN BmasterX 6 — 1DD + 3BA + 2PZT)
* **Acoustic Goal:** Tightens the 8mm liquid silicone diaphragm mid-bass warmth, pulls 3 Balanced Armature (BA) vocals forward into the mix, and tames the 9.8 kHz dual-piezoelectric (PZT) ceramic treble spike.
* **Global Preamp:** `-2.5 dB`
* **Bands:**
  1. `Low-Shelf` (`LSQ`) | `50 Hz` | `+2.2 dB` | `Q: 0.71`
  2. `Peaking` (`PK`) | `195 Hz` | `-2.4 dB` | `Q: 1.10`
  3. `Peaking` (`PK`) | `2200 Hz` | `+1.6 dB` | `Q: 1.30`
  4. `Peaking` (`PK`) | `4500 Hz` | `-1.8 dB` | `Q: 2.50`
  5. `Peaking` (`PK`) | `9800 Hz` | `-3.2 dB` | `Q: 3.00`

### Preset 2: `ew300-silver` (SIMGOT EW300 — Silver Steel Nozzle / Red Silicone Ring)
* **Acoustic Goal:** Adds sub-bass authority and smooths out pinna/lower treble energy on the analytical Simgot-Golden2023 target nozzle.
* **Global Preamp:** `-2.8 dB`
* **Bands:**
  1. `Low-Shelf` (`LSQ`) | `55 Hz` | `+2.5 dB` | `Q: 0.71`
  2. `Peaking` (`PK`) | `220 Hz` | `-1.2 dB` | `Q: 1.40`
  3. `Peaking` (`PK`) | `2800 Hz` | `-1.8 dB` | `Q: 2.00`
  4. `Peaking` (`PK`) | `5200 Hz` | `-2.2 dB` | `Q: 2.80`
  5. `High-Shelf` (`HSQ`) | `10500 Hz` | `-1.5 dB` | `Q: 0.71`

### Preset 3: `ew300-gold` (SIMGOT EW300 — Gold Copper Nozzle / Purple Silicone Ring)
* **Acoustic Goal:** Cleans up the warmer H-2019 gaming nozzle, removes lower-mid mud, and restores top-end air and micro-detail.
* **Global Preamp:** `-2.2 dB`
* **Bands:**
  1. `Low-Shelf` (`LSQ`) | `45 Hz` | `+1.5 dB` | `Q: 0.71`
  2. `Peaking` (`PK`) | `180 Hz` | `-2.2 dB` | `Q: 1.20`
  3. `Peaking` (`PK`) | `2000 Hz` | `+1.8 dB` | `Q: 1.40`
  4. `Peaking` (`PK`) | `4200 Hz` | `-1.0 dB` | `Q: 2.20`
  5. `High-Shelf` (`HSQ`) | `9500 Hz` | `+2.0 dB` | `Q: 0.71`

### Preset 4: `flat` (Hardware Bypass / 0 dB Reset)
* **Global Preamp:** `0.0 dB`
* **Bands 1–5:** `Peaking` (`PK`) | `1000 Hz` | `0.0 dB` | `Q: 1.00`

---

## 3. Technical Protocol Specification (KT02H20 / WalkPlay HID)

### HID Report Framing

Communication with the KTMicro KT02H20 DSP controller occurs across standard USB HID endpoints using **11-byte reports** with report ID `0x4B` (ASCII `'K'`).

```text
Byte:     [0]   [1]   [2]   [3]   [4]   [5]   [6]   [7]   [8]   [9]   [10]
Content: 0x4B   Reg  0x00  0x00  0x00   CMD  0x00   D0    D1    D2    D3
```

* **Report ID:** `0x4B` (`75` decimal)
* **Commands:**
  * `0x52` (`'R'`): Read register request
  * `0x57` (`'W'`): Write register request (Live DSP RAM)
  * `0x53` (`'S'`): Save / Commit current RAM registers to non-volatile flash (NVRAM)
  * `0x43` (`'C'`): Clear / reset registers to defaults

### Register Map

| Register | Purpose | Payload D0..D3 Format | Notes |
| :--- | :--- | :--- | :--- |
| `0x24` | Active EQ Slot / Enable | `[SlotID, 0x00, 0x00, 0x00]` | `0x03` = Active custom slot |
| `0x26` | Band 1 Gain & Frequency | `[Gain_Lo, Gain_Hi, Freq_Lo, Freq_Hi]` | Gain: int16 LE (dB × 10). Freq: uint16 LE (Hz). |
| `0x27` | Band 1 Q & Filter Type | `[Q_Lo, Q_Hi, TypeByte, 0x00]` | Q: uint16 LE (Q × 1000). Type: `0=PK, 3=LSQ, 4=HSQ`. |
| `0x28` | Band 2 Gain & Frequency | `[Gain_Lo, Gain_Hi, Freq_Lo, Freq_Hi]` | Band 2 |
| `0x29` | Band 2 Q & Filter Type | `[Q_Lo, Q_Hi, TypeByte, 0x00]` | Band 2 |
| `0x2A` | Band 3 Gain & Frequency | `[Gain_Lo, Gain_Hi, Freq_Lo, Freq_Hi]` | Band 3 |
| `0x2B` | Band 3 Q & Filter Type | `[Q_Lo, Q_Hi, TypeByte, 0x00]` | Band 3 |
| `0x2C` | Band 4 Gain & Frequency | `[Gain_Lo, Gain_Hi, Freq_Lo, Freq_Hi]` | Band 4 |
| `0x2D` | Band 4 Q & Filter Type | `[Q_Lo, Q_Hi, TypeByte, 0x00]` | Band 4 |
| `0x2E` | Band 5 Gain & Frequency | `[Gain_Lo, Gain_Hi, Freq_Lo, Freq_Hi]` | Band 5 |
| `0x2F` | Band 5 Q & Filter Type | `[Q_Lo, Q_Hi, TypeByte, 0x00]` | Band 5 |
| `0x66` | Global Preamp Gain | `[Preamp_Byte, 0x00, 0x00, 0x00]` | Signed int8 (-12 to +12 dB) |
| `0x00` | NVRAM Flash Commit | `[0x00, 0x00, 0x00, 0x00]` with `CMD=0x53` | Burns RAM registers into flash |

### CX31993 Safety Guard

To prevent irreversible bricking:
* `dac-peq-manager` checks vendor ID `0x0572` and product descriptor strings on all operations.
* If a Conexant CX31993 device is detected as the target of an `apply` or `flash` command, the CLI immediately raises `DeviceSecurityException` with exit code `2` and terminates before sending any HID packets.

---

## 4. Installation & Linux `udev` Configuration

### Prerequisites
* Python 3.10 or newer
* `libhidapi-dev` and `python3-hid` (or `hidapi` from PyPI)

```bash
# Ubuntu / Debian
sudo apt install -y python3-hid python3-hidapi libhidapi-dev

# Arch Linux
sudo pacman -S hidapi python-hidapi
```

### Install `dac-peq-manager`
```bash
cd dac-peq-manager
pip install -e .
```

### Configure Linux `udev` Rules (Non-Root USB Access)
Run the built-in rule installer:
```bash
dac-peq-manager udev --install
```
This writes `/etc/udev/rules.d/99-ktmicro-dac.rules` granting `uaccess` and `plugdev` rights to KTMicro and WalkPlay DAC endpoints, and reloads `udevadm`.

---

## 5. CLI Usage & Command Reference

### Scan Connected USB Devices
Enumerate all USB HID endpoints and identify hardware capabilities:
```bash
dac-peq-manager scan
```

### Instant Live Listening (`apply`)
Write the PEQ curve into live DSP RAM without writing to flash. Instant auditioning:
```bash
dac-peq-manager apply bmasterx6
# or test without hardware using the built-in emulator:
dac-peq-manager apply ew300-silver --mock
```

### Burn to Onboard NVRAM (`flash`)
Permanently commit the PEQ curve and preamp to the DAC's onboard non-volatile memory:
```bash
dac-peq-manager flash bmasterx6
# with explicit VID:PID targeting
dac-peq-manager flash ew300-silver --vid 0x31B2 --pid 0x0111
```

### Read Active Hardware Registers (`read`)
Query connected hardware registers and render the current active PEQ curve:
```bash
dac-peq-manager read
# export readback to a JSON file
dac-peq-manager read -o active_backup.json
```

### Visual ASCII Frequency Response Plot (`plot`)
Visualize any bundled preset or custom JSON curve in the terminal without hardware:
```bash
dac-peq-manager plot bmasterx6
dac-peq-manager plot ew300-silver
dac-peq-manager plot ew300-gold
```

### Host-Side DSP for JCALLY JM6 Pro (`export-pipewire`)
Generate a PipeWire `filter-chain` configuration bound to the CX31993 ALSA hardware sink:
```bash
# Install directly to ~/.config/pipewire/pipewire.conf.d/
dac-peq-manager export-pipewire bmasterx6 --install

# Reload PipeWire
systemctl --user restart pipewire
```

### Export Universal EqualizerAPO & Wavelet Suite (`export-apo`)
Generate EqualizerAPO `.txt`, Wavelet AutoEq `GraphicEQ.txt`, and 9-band JSON profiles:
```bash
dac-peq-manager export-apo ew300-silver -o ./exports
```

### Configure Hardware DAC Reconstruction Filters (`filter`)
Switch the KT02H20 hardware anti-aliasing reconstruction filter:
```bash
# Set in live RAM (FAST-LL, FAST-PC, SLOW-LL, SLOW-PC, NON-OS)
dac-peq-manager filter FAST-PC

# Burn filter preference to NVRAM permanently:
dac-peq-manager filter NON-OS --flash
```

### 2X Frequency Clock Compensation (`--compensate-2x`)
If using older or generic KT02H20 clone dongles that exhibit the 2x clock divisor offset bug:
```bash
dac-peq-manager apply bmasterx6 --compensate-2x
dac-peq-manager flash bmasterx6 --compensate-2x -y
```

### Intersample Headroom & Auto-Preamp (`--auto-preamp`)
To avoid inter-sample peaks that saturate the DAC delta-sigma modulator during oversampling, pass `--auto-preamp`. It evaluates peak composite response across all 5 bands and applies the exact negative preamp needed with a 0.5 dB safety margin:
```bash
dac-peq-manager apply jm_1 --auto-preamp
dac-peq-manager flash bmasterx6 --auto-preamp -y
```

### 711 Coupler Resonance Artifact Linter
The CLI and Web Flasher automatically analyze your EQ filters. If an aggressive cut ($> -3.0\text{ dB}$) with high $Q > 2.0$ is detected in the $7.4\text{ kHz} - 9.6\text{ kHz}$ zone, an acoustic advisory warning is displayed, alerting you that the filter may be counteracting an artificial steel coupler reflection rather than real ear canal geometry.

### Modern Target Curve Library (`presets/targets/`)
In addition to IEM tuning presets, the suite bundles reference target curves:
* **`jm_1`** (`JM-1 Target`): Modern Jaytiss human ear canal impedance target with deep sub-bass punch and smooth, non-fatiguing 3kHz ear gain.
* **`ief_neutral`** (`IEF Neutral`): Crinacle's studio monitor reference curve with linear, unboosted bass.
* **`harman_in_ear_2019v2`** (`Harman In-Ear 2019 v2`): Reference consumer target with +9dB sub-bass shelf and forward +12dB ear gain.

```bash
dac-peq-manager plot jm_1
dac-peq-manager plot ief_neutral
dac-peq-manager apply jm_1 --auto-preamp
```

### NVRAM Flash Endurance Protection (`-y` / `--yes`)
Because hardware flash memory has an endurance cycle limit (~10,000 to 100,000 cycles), `dac-peq-manager flash` requires explicit confirmation before committing to EEPROM, protecting your DAC from accidental flash wear during rapid slider adjustments. Pass `-y` / `--yes` in scripts.

---

## 6. Community Measurement Database Engine (AutoEq & Squiglink)

`dac-peq-manager` natively integrates with the open-source **`jaakkopasanen/AutoEq`** database and the **Squiglink** ecosystem, indexing over **8,850+ headphone and IEM measurement profiles** from 29 acoustic labs and reviewers (including *crinacle on 711 & 5128*, *oratory1990 on GRAS 43AG*, *Super* Review*, *Rtings*, *Jaytiss*, *Fahryst*, *Hi End Portable*, *ToneDeafMonk*, and *Innerfidelity*).

### Search 8,800+ Models (`db search`)
```bash
# Search for any IEM or headphone model
dac-peq-manager db search "EW300"
dac-peq-manager db search "Aria" --source "Super Review"
dac-peq-manager db search "HD 600"
```

### Pull, Audition & Flash Community Profiles (`db pull`)
AutoEq explicitly calculates filters 1&ndash;5 as a standalone 5-band PEQ profile for hardware DSP devices. You can pull, plot, audition, and flash any community model in one step:
```bash
# Pull, render frequency curve, and save local JSON preset:
dac-peq-manager db pull "Simgot Audio EW300 (gold)" --plot

# Pull and audition immediately in live DSP RAM:
dac-peq-manager db pull "Moondrop Aria" --apply

# Pull and burn directly to persistent NVRAM flash:
dac-peq-manager db pull "Sennheiser HD 600" --flash
```

### Direct On-the-Fly Querying (`autoeq:<query>`)
Any command that accepts a preset (e.g., `plot`, `apply`, `flash`, `export-pipewire`, `export-apo`) accepts the `autoeq:<query>` prefix:
```bash
# Plot on the fly
dac-peq-manager plot "autoeq:Sennheiser HD 600"

# Generate PipeWire filter-chain configuration for JCALLY JM6 Pro from AutoEq
dac-peq-manager export-pipewire "autoeq:Moondrop Aria" -o ~/.config/pipewire/pipewire.conf.d/99-aria.conf
```

### List Measurement Labs & Update Index Cache (`db sources` & `db update`)
```bash
# List all 29 measurement sources and profile counts
dac-peq-manager db sources

# Refresh local index cache from GitHub
dac-peq-manager db update
```

### Hardware DAC Directory & Compatibility Matrix (`dacs`)
`dac-peq-manager` includes a curated catalog of 17+ portable USB-C DAC dongles, internal chipsets, and recommended DSP workflows (hardware flash vs. host DSP).

```bash
# List all catalogued DAC devices and compatibility status
dac-peq-manager dacs list

# Filter only hardware-flashable KTMicro / WalkPlay devices
dac-peq-manager dacs list --flashable

# Search by chipset, brand, or feature (e.g. CS43131, CX31993, CableCreation, splitter)
dac-peq-manager dacs search "CS43131"
dac-peq-manager dacs search "CableCreation"

# View deep technical specifications and recommended DSP workflow for a specific DAC
dac-peq-manager dacs info allegro_mini
dac-peq-manager dacs info cablecreation_2in1
dac-peq-manager dacs info jcally_jm6_pro
```

---

## 7. Verification & Automated Testing

The suite includes 90 comprehensive unit, integration, and cross-engine parity tests covering:
* Cross-engine Python vs. JavaScript (`node`) floating-point parity (`< 1e-9`) across RBJ biquad coefficients, 127-point composite curves, 5/9-band landmark decimation, RMS delta metrics, and Wavelet GraphicEQ strings
* RBJ biquad coefficient calculations at 48 kHz and 96 kHz
* High-shelf, low-shelf, and peaking analytical frequency response verification
* Peak composite gain and intersample headroom calculation
* Acoustic difference and RMS delta calculations across audible frequencies
* Acoustic linter (711 coupler artifact detection, high boost, and phase ringing warnings)
* Intelligent $N$-band landmark decimation (reducing 10-band curves to 5 or 9 bands while preserving sub-bass/air shelves and pinna peaks)
* Hardware band limit validation (strictly preventing out-of-bounds register writes on 5-band KTMicro vs. 9-band FreeDSP)
* Physical NVRAM FlashWearTracker recording, threshold warning triggers, and cache persistence
* Automated firmware clock divisor quirk probe and bcdDevice heuristic detection
* KTMicro 11-byte packet framing, register mapping & post-commit soft-reboot recovery
* Moondrop FreeDSP 9-band transport adapter and device factory
* 0.5 dB digital volume / preamp precision encoding
* Conexant CX31993 hardware flash prevention safety guards
* PipeWire filter-chain configuration node routing (supporting dynamic 5 to 10+ biquad chains)
* Full-fidelity 10-band host DSP exports for PipeWire and EqualizerAPO
* EqualizerAPO and Wavelet 127-point GraphicEQ generation
* All 4 bundled acoustic presets and 3 reference target curves (JM-1, IEF Neutral, Harman)
* AutoEq index markdown parsing and community measurement extraction
* Multi-keyword database search and local preset persistence
* Curated Hardware DAC Directory querying, filtering, and CLI commands

Run the test suite:
```bash
pytest tests/ -v
```

---

## 8. Zero-Install Web Flasher (WebHID GUI)

For users who prefer a graphical interface or who do not want to install Python, `dac-peq-manager` includes a standalone, zero-dependency Web Flasher located in [`web/`](file:///home/ubuntu/iem/dac-peq-manager/web/):

* **Interactive Frequency Response Graph:** Real-time SVG visualization computed directly with standard RBJ biquad formulas across 220 logarithmic frequency points (20 Hz &ndash; 20 kHz). Drag and drop band nodes 1&ndash;5 to dynamically adjust frequency and gain.
* **Online Community Database Search:** Search 8,800+ models directly in the browser, filter by lab/reviewer (Crinacle, Oratory1990, Super Review, Rtings), and load PEQ curves with one click. Automatic 5-band landmark decimation preserves core tonality and suppresses 711 coupler resonance.
* **Hardware DAC Compatibility Directory:** Search and browse 17+ catalogued USB DAC dongles, chipsets, power ratings, and architectures directly within the UI. Filter by Hardware Flashable, Fixed Mask ROM, Host DSP Only, or 2-in-1 Charging Splitters.
* **Intelligent WebHID Auto-Identification & Hotplug:** When plugging in a USB DAC, the Web Flasher matches the device's USB Vendor/Product ID against the catalog, providing instant feedback on whether the dongle supports onboard hardware flash or requires host DSP export. Listens to USB connect/disconnect events to maintain connection state dynamically.
* **"Remember Device" Session Restoration:** Optional persistent toggle (enabled by default) that silently reconnects previously authorized DACs on page load via `navigator.hid.getDevices()` without opening browser permission modals.
* **Instant Audition & Persistent NVRAM Flash:** Supports temporary live RAM writes (`0x57`) as well as permanent hardware flash commits (`0x53`) with graceful soft-reboot re-enumeration handling.
* **Hardware Safety Interceptor:** Automatically detects Conexant CX31993 hardware descriptors (`0x0572`) and locks out write/flash buttons with a safety warning banner.
* **Host DSP Exporter:** Generates and downloads PipeWire `.conf`, EqualizerAPO `.txt`, and Wavelet `GraphicEQ.txt` files on the fly.
* **Pink Noise Generator:** Built-in Web Audio API pink noise generator for instant acoustic checks through connected IEMs.
* **Demo Mode Simulation:** Fully functional simulation mode allowing interactive tweaking and visual verification even when no physical DAC is plugged in.

### Launching the Web Flasher Locally
```bash
# Start a lightweight local server:
python3 -m http.server 8000 --directory web

# Open http://localhost:8000 in Chrome / Edge / Brave
```
The `web/` directory can also be deployed directly to **GitHub Pages** with zero build step.

---

## 9. Acknowledgments, Attribution & Shared Code

`dac-peq-manager` builds upon protocol reverse-engineering, firmware documentation, and DSP mathematics shared by the open-source audio community. Full attribution and repository links are documented in [ATTRIBUTION.md](file:///home/ubuntu/iem/dac-peq-manager/ATTRIBUTION.md):

* **[`gxcreator/ktmicro-tools`](https://github.com/gxcreator/ktmicro-tools)** (MIT License): Reverse-engineered KT02H20 11-byte HID report framing, register map architecture, and 0.5 dB digital gain (`0x66`) encoding.
* **[`jeromeof/devicePEQ`](https://github.com/jeromeof/devicePEQ)** (0BSD License): Real-world USB HID captures for the Kiwi Ears Allegro Mini, identification of the `compensate2X` frequency divisor quirk, post-commit USB re-enumeration handling, and WebHID browser flashing patterns.
* **[`Ircama/ja11-config`](https://github.com/Ircama/ja11-config)** (GPL-3.0 License): Documentation of internal DAC reconstruction filter IDs and minimal Linux `libusb` vs `hidraw` driver requirements.
* **[`MiyukiVigil/Hub_Moon`](https://github.com/MiyukiVigil/Hub_Moon)** (MIT License): Reverse-engineered Moondrop FreeDSP / May cable 64-byte USB HID report framing and 9-band biquad memory layout.
* **Robert Bristow-Johnson (RBJ)**: Standard [Audio EQ Cookbook](https://www.w3.org/TR/audio-eq-cookbook/) discrete biquad filter transfer functions.
* **[`jaakkopasanen/AutoEq`](https://github.com/jaakkopasanen/AutoEq)** (MIT License): 8,800+ measurement database index schema, parametric EQ markdown table format, and 127-point logarithmic frequency curve formatting for Android Wavelet.
* **IEC 60318-4 (711) Coupler Research & Targets**: Acoustic resonance and target curve research by **Crinacle** (In-Ear Fidelity), **Oratory1990**, **Sean Olive** (Harman International), and **Jaytiss / Jayme** (JM-1 Target).

---

## 10. Hardware Safety Disclaimer

> [!CAUTION]
> **Use at your own risk.** Writing to hardware non-volatile flash memory (NVRAM) involves inherent physical risks. Never disconnect the USB-C cable or power down the host device while executing a `flash` command. The authors and contributors of `dac-peq-manager` assume no liability for damaged or bricked audio hardware.

