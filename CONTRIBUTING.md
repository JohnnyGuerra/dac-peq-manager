# Contributing to `dac-peq-manager`

We welcome contributions from audiophiles, audio engineers, embedded developers, and reverse engineers! Whether you are verifying a newly tested dongle, capturing USB packets from a vendor's web app, or submitting code for a new protocol family, your help directly expands the open-source hardware DSP ecosystem.

---

## 1. How You Can Help

### A. Verify a 🟡 "Awaiting Tester" Device
If you own any device marked **🟡** in [COMPATIBILITY.md](./COMPATIBILITY.md) (such as the **Moondrop Chu II DSP**, **Tanchjim ONE DSP**, **FiiO JA11**, **Fosi DS3**, or **FiiO LS-TC2**):
1. Plug your DAC into a PC or Android device running Chrome, Brave, or Edge.
2. Open the [Web Flasher](https://johnnyguerra.github.io/dac-peq-manager/) (or run `dac-peq-manager scan` from the CLI).
3. Connect via WebHID and verify:
   * Does it connect and read current filter values?
   * Does applying a profile alter the sound as expected?
   * Does committing to hardware NVRAM persist after unplugging?
   * Do physical volume buttons on your phone/computer still function normally?
4. Open a [Hardware Report Issue](https://github.com/johnnyguerra/dac-peq-manager/issues/new?template=dac_hardware_report.yml) with your findings!

---

### B. Capture & Submit USB Packets (No Coding Required!)
If you have a dongle supported by an official vendor web flasher (like `equalizer.kiwiears.com`, `fiiocontrol.fiio.com`, or Walkplay) that we haven't verified or that uses a new protocol:

#### Method 1: Browser WebHID Console Log (Easiest)
1. Open Chrome and navigate to the vendor's official web tool.
2. Press `F12` to open DevTools, then switch to the **Console** tab.
3. Paste the following snippet into the Console and press Enter:
   ```javascript
   const origSend = HIDDevice.prototype.sendReport;
   HIDDevice.prototype.sendReport = function(id, data) {
     console.log(`[HID TX] Report 0x${id.toString(16)}:`, Array.from(new Uint8Array(data.buffer || data)).map(b => '0x' + b.toString(16).padStart(2, '0')).join(' '));
     return origSend.apply(this, arguments);
   };
   ```
4. Perform an action in the vendor app (read EQ, change a band, commit flash).
5. Copy the console output and paste it into a [New DAC Request Issue](https://github.com/johnnyguerra/dac-peq-manager/issues/new?template=new_dac_request.yml).

#### Method 2: Wireshark + USBPcap (Windows / Linux)
1. Open Wireshark and capture on your USB interface (`USBPcap1` on Windows or `usbmon` on Linux).
2. Filter by: `usb.transfer_type == 0x02 || usb.transfer_type == 0x03` (Control / Interrupt transfers).
3. Connect to the vendor app, make a 1 dB adjustment to Band 1, save, and stop capture.
4. Export specified packets as `.pcapng` and attach to your issue.

---

### C. Device Loaners & Hardware Sponsorship
If you are a manufacturer, retailer, or community member who would like to send a loaner dongle or sample for reverse engineering and integration into `dac-peq-manager`:
* Please open an issue with the tag `[Hardware Loaner]` or reach out via GitHub Discussions.
* Loaner devices will be non-destructively analyzed (USB descriptors, HID report exchanges, live register behavior, clock divisor checks) and promptly shipped back upon request.

---

## 2. Development & Testing Workflow

### Local Development Setup
```bash
git clone https://github.com/johnnyguerra/dac-peq-manager.git
cd dac-peq-manager
python3 -m venv venv
source venv/bin/activate
pip install -e .
pip install pytest
```

### Running the Test Suite
All 98 unit tests run in < 5 seconds and include full mock hardware emulation:
```bash
pytest dac-peq-manager/tests -v
```

### Running the Web Flasher Locally
The Web Flasher is pure static HTML5/JavaScript with zero build step required:
```bash
python3 -m http.server 8888 --directory dac-peq-manager/web
# Open http://localhost:8888 in Chrome/Brave
```

---

## 3. Core Architecture Rules to Follow

When adding new device handlers or PRs, please review [GEMINI.md](./GEMINI.md):
1. **Never send flash writes to Conexant hardware:** CX31993 uses fixed mask ROM with OTP registers. Always route to host DSP.
2. **Never overwrite Register `0x11` or `0x66` on KTMicro KT02H20:** On Kiwi Ears Allegro Mini, writing `0x11` directly overwrites the MCU's internal volume attenuation control, locking out physical buttons on iOS/Android.
3. **Respect the 2X clock divisor quirk:** For generic KT02H20 hardware with `bcdDevice <= 0x0100`, biquad frequencies are halved (`f / 2`) at 48kHz. Newer firmwares (`bcdDevice > 0x0100`) must not have frequencies halved.
4. **Always include a unit test:** All protocol handlers must have mock device tests in `tests/`.
