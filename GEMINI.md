# IEM & USB DAC PEQ Manager Guidelines

## 1. KTMicro / WalkPlay DSP Architecture Rules
- **Factory Reset Command (`0x43 CLEAR`)**:
  - If a user reports volume control lockout (e.g., iPhone physical volume buttons or YouTube Music volume slider stop responding), zeroing PEQ bands will NOT restore volume control.
  - The hardware requires an official `0x43 CLEAR` command (`dac-peq reset -y` or Web Flasher Factory Reset) to wipe NVRAM registers and reboot the MCU.
  - After sending `0x43 CLEAR` or `0x53 COMMIT`, always await USB re-enumeration before re-attempting communication.
- **2X Clock Divisor Quirk**:
  - Generic KT02H20 / Allegro Mini firmwares with `bcdDevice <= 0x0100` divide the biquad calculation frequency by 2 at 48kHz. Center frequencies must be halved (`f / 2`) when calculating register coefficients.
  - Modern revisions (`bcdDevice > 0x0100`, FiiO JA11 v1.8+ `release_number >= 0x0180`) corrected this bug internally; do NOT apply frequency halving on these.

## 2. Hardware Safety Guardrails (Conexant CX31993)
- **Fixed Mask ROM Protection**:
  - Devices matching Conexant CX31993 (`VID 0x0572`, `VID:PID 0x3302:0x3365` TTGK, or descriptor containing `"cx31993"`) use fixed mask ROM with One-Time Programmable (OTP) registers.
  - NEVER attempt to send KTMicro HID register writes (`0x4B...`) to Conexant hardware. It will risk corrupting OTP descriptors.
  - Always route Conexant CX31993 to host-side DSP exporters (`export-pipewire`, `export-apo`, Wavelet).

## 3. Remote Physical DAC Diagnostics
- When diagnosing USB audio hardware on `linux-laptop` over Tailscale SSH:
  - Check ALSA streams: `cat /proc/asound/card*/stream0` to verify native sample rates and bit depths.
  - Inspect HID report descriptors: `hexdump -C /sys/class/hidraw/hidraw*/device/report_descriptor` to determine whether the device exposes proprietary DSP registers or standard Consumer Control media keys (`0x0C`).
  - Bluetrum AB13X (`0x001F:0x0B21`) adapters: warn users that 3-pole TRS plugs on 4-pole TRRS sockets can cause floating sleeve phantom media control events.
