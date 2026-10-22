# USB DAC & IEM Hardware Compatibility Matrix

This document tracks the hardware support, protocol reverse-engineering status, and physical verification for all known portable USB-C DAC dongles, DSP upgrade cables, and Bluetooth/USB hybrid DACs in `dac-peq-manager`.

---

## Status Legend

| Badge | Status | Definition |
| :---: | :--- | :--- |
| 🟢 | **Verified & Tested on Hardware** | Physically tested on device. Live PEQ RAM writes, hardware NVRAM commits (`0x53`), volume controls on iOS/Android, and 2-way readback verified working. |
| 🟡 | **Protocol Complete (Awaiting Tester)** | Protocol framing, biquad registers, and checksum calculations implemented and unit-tested; awaiting community confirmation on physical silicon. |
| 🔵 | **Protocol In Development (Help Wanted)** | Protocol analyzed via APK / JS / captures. Actively seeking USB packet captures, tester validation, or device donations. |
| 🔴 | **Fixed Mask ROM / Host DSP Only** | Silicon uses fixed mask ROM with One-Time Programmable (OTP) registers (e.g. Conexant CX31993). Hardware flashing is permanently locked out to prevent bricking; managed via host DSP (PipeWire, Wavelet, EqualizerAPO). |

---

## 1. Hardware-Flashable Devices (Onboard NVRAM PEQ)

These devices store Parametric EQ filters directly into onboard non-volatile memory (EEPROM/Flash). Once burned, the acoustic profile persists across all sources (iPhone, Android, Mac, Windows, Linux, iPad, Nintendo Switch) with zero background apps running.

| Device | Brand | Chipset / Architecture | USB VID:PID | EQ Bands | Memory Slots | Status | Notes |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Allegro Mini** | Kiwi Ears | KTMicro KT02H20 / CB1200AU | `0x31B2:0x0111` | 5 Bands | Slot 3 (Custom) | 🟢 | Dual 3.5mm SE + 4.4mm Bal. Verified iOS volume buttons & YouTube Music control restored with `0x43 CLEAR`. Note: Hardware is pure stereo playback (no mic ADC / no inline cable remote detection). |
| **FreeDSP / May Cable** | Moondrop | Moondrop Custom 9-Band DSP | `0x31B2:0x0112` | 9 Bands | Slot 1 | 🟢 | 0.78mm 2-pin modular Type-C cable. 9-band hardware biquad with live readback. |
| **BmasterX 6 Plug** | BASN | OEM KTMicro / WalkPlay DSP | `0x31B2:0x0111` | 5 Bands | Slot 3 (Custom) | 🟢 | Modular Type-C termination for BASN 1DD+3BA+2PZT Tribrid IEM. |
| **JadeAudio JA11** | FiiO / JadeAudio | KTMicro KT02H20 | `0x2972:0x0102` | 5 Bands | Slot 3 | 🟡 | 3.5mm SE dongle with FIR filter selection (FAST-LL, SLOW, NON-OS). Firmware v1.8+ uses native clocking. |
| **JM12** | JCALLY | KTMicro KT02H20 | `0x31B2:0x0111` | 5 Bands | Slot 3 | 🟡 | Budget 3.5mm SE dongle. Protocol identical to Allegro Mini. |
| **Allegro Pro** | Kiwi Ears | KTMicro KT_3016L | `0x31B2:0x3016` | 5 Bands | Slot 3 | 🟡 | Dual 3.5mm + 4.4mm balanced high-output dongle. Register layout mapped. |
| **S-Link DSP Cable** | Kiwi Ears | KTMicro KT_1132L | `0x31B2:0x1132` | 5 Bands | Slot 3 | 🟡 | 0.78mm 2-pin DSP cable. Register map addresses 0x35-0x3F. |
| **Chu II DSP** | Moondrop | KTMicro KT02H20 | `0x31B2:0x1112` | 5 Bands | Slot 3 | 🟡 | Entry-level 1DD IEM with integrated Type-C KT02H20 plug. |
| **ONE DSP** | Tanchjim | KTMicro KT02H20 | `0x31B2:0x1113` | 5 Bands | Slot 3 | 🟡 | 1DD IEM with Type-C plug DSP. Consecutive 0x26-0x2F registers. |
| **Bunny DSP** | Tanchjim | KTMicro KT02H20 | `0x31B2:0x1112` | 5 Bands | Slot 3 | 🟡 | 0.78mm 2-pin cable with Type-C DSP. |
| **Fission DSP** | Tanchjim | KTMicro KT02H20 | `0x31B2:0x1119` | 5 Bands | Slot 3 | 🟡 | Modular Type-C DSP cable. |
| **Wyvern Abyss DSP** | Kinera / Celest | WalkPlay / KTMicro OEM | `0x262A:0x0101` | 5 Bands | Slot 3 | 🟡 | 0.78mm 2-pin gaming IEM cable with boom mic. |
| **EW300 DSP Cable** | SIMGOT | KTMicro / WalkPlay OEM | `0x31B2:0x0111` | 5 Bands | Slot 3 | 🟡 | Modular 0.78mm 2-pin Type-C cable for Simgot EW300 Tribrid. |
| **LS-TC2 DSP Cable** | FiiO | KTMicro / FiiO DSP | `0x2972:0x0107` | 5 Bands | Slot 3 | 🟡 | 0.78mm 2-pin replacement cable with inline remote and mic. |
| **DS3** | Fosi Audio | ESS ES9039Q2M + KTMicro | `0x31B2:0x1118` | 8 Bands | Multi | 🟡 | High-power ES9039Q2M dual-output DAC dongle. |
| **KEYX DSP Cable** | Truthear | WalkPlay Scheme 15 DSP | `0x3302:0x4362` | 8 Bands | Preset 1-4 | 🔵 | Official Truthear 0.78mm 2-pin Type-C DSP cable. WalkPlay multi-frame protocol. |
| **SPACE Pro** | Tanchjim | Dual CS43131 + WalkPlay | `0x3302:0x431D` | 10 Bands | Multi | 🔵 | Dual CS43131 flagship dongle with 10-band hardware PEQ. |
| **STARGATE II** | Tanchjim | Cirrus CS43131 + WalkPlay | `0x3302:0x4353` | 8 Bands | Multi | 🔵 | CS43131 dongle using WalkPlay Scheme 15 framing. |
| **DSP Cable - Memory**| ddHiFi | WalkPlay Scheme 15 DSP | `0x3302` | 8 Bands | Preset 1-4 | 🔵 | Audiophile MMCX / 0.78mm 2-pin Type-C DSP cable. |
| **KA15** | FiiO | Dual CS43198 + SGM8262 | `0x2972:0x0104` | 10 Bands | USER1-3 | 🔵 | 560mW Desktop Mode dongle with color LCD retro cassette display. FiiO framed protocol. |
| **KA17** | FiiO | Dual ES9069Q + THX AAA 78+ | `0x2972:0x0105` | 10 Bands | USER1-3 | 🔵 | 650mW Desktop Mode with dedicated external power port. |
| **BTR13** | FiiO | Dual CS43131 + QCC5125 | `0x2972:0x0106` | 10 Bands | USER1-3 | 🔵 | Bluetooth 5.1 + USB DAC with independent hardware PEQ. |
| **BTR17** | FiiO | Dual ES9069Q + THX AAA 78+ | `0x2972` | 10 Bands | USER1-10 | 🔵 | Flagship Bluetooth / USB DAC with aptX Lossless and LDAC. |
| **5K Reference** | Qudelix | Dual ES9218P + QCC5124 | `0x04DD:0x1001` | 20 Bands | 20 Presets | 🔵 | Wireless & USB DAC with 20 onboard memory slots. Qudelix serial HID protocol. |

---

## 2. Fixed Mask ROM & Host-DSP DACs (Safety Locked)

These devices use fixed-function silicon without writable DSP registers or NVRAM. `dac-peq-manager` **actively detects and blocks flash operations** on these chips to protect their One-Time Programmable (OTP) descriptors, seamlessly providing exported filter configurations for Linux PipeWire, Android Wavelet, and Windows EqualizerAPO instead.

| Device | Brand | Chipset / Architecture | USB VID:PID | Status | Recommended DSP Host |
| :--- | :--- | :--- | :---: | :---: | :--- |
| **CX31993 384kHz HiFi** | TTGK Technology | Conexant CX31993 | `0x3302:0x3365` | 🔴 | Verified on hardware. Fixed mask ROM. Hardware flashing blocked. Use `dac-peq export-pipewire` or `export-apo`. |
| **JM6 Pro** | JCALLY | Conexant CX31993 + MAX97220 | `0x0572:0x1B08` | 🔴 | Fixed mask ROM. Flashing blocked for silicon safety. |
| **JM6** | JCALLY | Conexant CX31993 | `0x0572:0x1B08` | 🔴 | Fixed mask ROM. |
| **Generic WD01 / RY-WD01**| Rythflo / Generic | Generic UAC 1.0 Codec | `0x001F:0x1637` | 🔴 | Verified on hardware. 16-bit / 48kHz UAC1 audio with Consumer Control media keys. |
| **AB13X USB Audio** | Bluetrum / Generic | Bluetrum AB13X (AB136T) | `0x001F:0x0B21` | 🔴 | Verified on hardware. 16-bit / 48kHz. Note: 3-pole TRS jacks on 4-pole sockets can cause floating ground phantom media events. |
| **Apple USB-C Adapter** | Apple | Cirrus Logic Custom (A2049/A2155)| `0x0452:0x110A` | 🔴 | Fixed 24-bit/48kHz UAC2. Clean measurements. Use host-side DSP. |
| **Moondrop Dawn Pro** | Moondrop | Dual Cirrus CS43131 | `0x2FC6:0x0001` | 🔴 | Fixed UAC2 DAC with hardware button volume control. Host DSP only. |
| **CableCreation 2-in-1** | CableCreation | Realtek ALC4040 + VIA PD 100W | `0x0BDA:0x4040` | 🔴 | 16-bit/48kHz UAC1 splitter dongle. |
| **UGREEN 2-in-1** | UGREEN | Bestechnic BES / Realtek + PD 60W | `0x0BDA:0x4042` | 🔴 | 24-bit/96kHz UAC1 splitter dongle. |

---

## How to Get Your Device Verified

If you own a device marked **🟡 (Awaiting Tester)** or **🔵 (Help Wanted)**:
1. Open the [Web Flasher](https://github.com/johnnyguerra/dac-peq-manager) in Chrome, Brave, or Edge.
2. Connect your device, test applying/flashing a profile, and check your host's volume buttons.
3. Submit a report using our [Hardware Verification Issue Template](https://github.com/johnnyguerra/dac-peq-manager/issues/new?template=dac_hardware_report.yml)!
