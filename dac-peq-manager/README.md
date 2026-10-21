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

---

## 6. Verification & Automated Testing

The suite includes 36 unit and integration tests covering:
* RBJ biquad coefficient calculations at 48 kHz and 96 kHz
* High-shelf, low-shelf, and peaking analytical frequency response verification
* KTMicro 11-byte packet framing & register mapping
* Conexant CX31993 hardware flash prevention safety guards
* PipeWire filter-chain configuration node routing
* EqualizerAPO and Wavelet 127-point GraphicEQ generation
* All 4 bundled acoustic presets

Run the test suite:
```bash
pytest tests/ -v
```
