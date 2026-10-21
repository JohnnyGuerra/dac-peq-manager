# Acknowledgments, Attribution & Shared Code

`dac-peq-manager` relies on research, reverse-engineering, mathematical standards, and protocol documentation pioneered by the open-source audio community. We gratefully credit the following upstream authors and projects:

---

## 1. KTMicro KT02H20 / WalkPlay Reverse-Engineering

### [`gxcreator/ktmicro-tools`](https://github.com/gxcreator/ktmicro-tools)
* **Author:** [@gxcreator](https://github.com/gxcreator)
* **License:** MIT License
* **Contribution & Reference:**
  * Documented the 11-byte USB HID report framing led by magic report ID `0x4B` (`'K'`).
  * Register map architecture:
    * `0x24`: DAC EQ enable bitmask.
    * `0x26`–`0x2F`: Live DSP RAM biquad filter registers (A-reg for Freq/Gain, B-reg for Q/Type).
  * Digital volume & global gain (`0x66`): Revealed that digital gain is encoded as a signed byte with **0.5 dB steps** (`gain_dB = signed_byte / 2.0`), enabling exact fractional preamp resolution.

---

### [`jeromeof/devicePEQ`](https://github.com/jeromeof/devicePEQ)
* **Author:** [@jeromeof](https://github.com/jeromeof)
* **License:** BSD-0-Clause (0BSD)
* **Contribution & Reference:**
  * Real-world USB HID exchange captures from hardware targets, including the **Kiwi Ears Allegro Mini** (`0x31B2:0x0111`) and **FiiO JA11** (`0x2972:0x0102`).
  * Identified the **`compensate2X`** clock divisor discrepancy present in legacy/generic KT02H20 firmware variants.
  * Documented the post-commit USB PHY bus re-enumeration behavior (`disconnectOnSave`), allowing client software to handle flash commit resets cleanly.

---

### [`Ircama/ja11-config`](https://github.com/Ircama/ja11-config)
* **Author:** [@Ircama](https://github.com/Ircama)
* **License:** GNU General Public License v3.0 (GPL-3.0)
* **Contribution & Reference:**
  * Documented the five internal hardware DAC digital reconstruction filters in the KT02H20 (`FAST-LL`, `FAST-PC`, `SLOW-LL`, `SLOW-PC`, `NON-OS`) at register `0x11`.
  * Highlighted `libusb` vs `/dev/hidraw` kernel driver distinctions on embedded/minimal Linux systems, informing our dual-subsystem Linux `udev` rules.

---

### [`MiyukiVigil/Hub_Moon`](https://github.com/MiyukiVigil/Hub_Moon)
* **Author:** [@MiyukiVigil](https://github.com/MiyukiVigil)
* **License:** MIT License
* **Contribution & Reference:**
  * Reverse-engineered Moondrop's web configurator (`hub.moondroplab.tech`) and 64-byte USB HID report framing for the **Moondrop FreeDSP**, **Chu II DSP**, and **May DSP** cables (`0x31B2:0x0112`).
  * Documented 9-band hardware biquad memory structures and live RAM (`0x20`) vs. flash commit (`0x21`) command opcodes.

---

## 2. DSP Mathematics & Filter Calculations

### Audio EQ Cookbook (RBJ Biquad Formulae)
* **Author:** Robert Bristow-Johnson
* **Reference:** [W3C Audio EQ Cookbook](https://www.w3.org/TR/audio-eq-cookbook/)
* **Contribution:**
  * Mathematical derivation and transfer function equations for biquad filter types:
    * Peaking (`PK`)
    * Low-Shelf with Q (`LSQ`)
    * High-Shelf with Q (`HSQ`)
  * Normalization of intermediate variables ($A, \omega_0, \alpha$) and standard coefficient scaling by $a_0$.

---

## 3. Host-Side Equalizer Formats & Systems

### [`AutoEq`](https://github.com/jaakkopasanen/AutoEq)
* **Author:** Jaakko Pasanen ([@jaakkopasanen](https://github.com/jaakkopasanen))
* **License:** MIT License
* **Contribution:**
  * Specification and normalization conventions for 127-point logarithmically spaced `GraphicEQ` strings used by the Android **Wavelet** application.

---

### [PipeWire Project](https://pipewire.org)
* **Authors:** Wim Taymans and the PipeWire / FreeDesktop Contributors
* **License:** MIT / LGPL
* **Contribution:**
  * Architecture of `libpipewire-module-filter-chain` and built-in DSP filter primitives (`linear`, `bq_lowshelf`, `bq_peaking`, `bq_highshelf`).

---

### [EqualizerAPO](https://sourceforge.net/projects/equalizerapo/)
* **Author:** Peter Verheet
* **License:** GNU General Public License v2.0 (GPL-2.0)
* **Contribution:**
  * Parametric configuration syntax (`Preamp:`, `Filter X: ON <TYPE> Fc ... Gain ... Q ...`).

---

## 4. Hardware Safety Disclaimer

> [!CAUTION]
> **Use at your own risk.** Writing to hardware non-volatile flash memory (NVRAM) involves inherent physical risks. Never disconnect the USB-C cable or power down the host device while executing a `flash` command. The authors and contributors of `dac-peq-manager` assume no liability for damaged or bricked audio hardware.
