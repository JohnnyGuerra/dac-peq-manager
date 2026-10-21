"""USB HID communication layer for KTMicro KT02H20 / WalkPlay SoC DACs.

Implements the 11-byte register protocol:
  - Report ID: 0x4B ('K')
  - Read: [0x4B, reg, 0x00, 0x00, 0x00, 0x52, 0x00, 0x00, 0x00, 0x00, 0x00]
  - Write Gain/Freq: [0x4B, reg, 0x00, 0x00, 0x00, 0x57, 0x00, gain_lo, gain_hi, freq_lo, freq_hi]
  - Write Q/Type: [0x4B, reg, 0x00, 0x00, 0x00, 0x57, 0x00, q_lo, q_hi, type_byte, 0x00]
  - Write Preamp: [0x4B, 0x66, 0x00, 0x00, 0x00, 0x57, 0x00, gain_byte, 0x00, 0x00, 0x00]
    (0.5 dB resolution: value = round(db * 2))
  - Write DAC Filter: [0x4B, 0x11, 0x00, 0x00, 0x00, 0x57, 0x00, filter_idx, 0x00, 0x00, 0x00]
  - Enable/Slot: [0x4B, 0x24, 0x00, 0x00, 0x00, 0x57, 0x00, slot_id, 0x00, 0x00, 0x00]
  - Commit/Save: [0x4B, 0x00, 0x00, 0x00, 0x00, 0x53, 0x00, 0x00, 0x00, 0x00, 0x00]

Safety Guard:
  - Explicitly blocks writes to Conexant CX31993 (VID 0x0572) to prevent
    corrupting OTP descriptor registers.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

try:
    import hid
except ImportError:
    hid = None


# Known KTMicro / WalkPlay Vendor IDs
KTMICRO_KNOWN_VIDS = [
    0x31B2,  # KTMicro / JCALLY / Kiwi Ears Allegro Mini
    0x2972,  # FiiO / JadeAudio JA11
    0x0BDA,  # Realtek / WalkPlay OEM
    0x0661,  # KTMicro OEM
    0x262A,  # WalkPlay OEM
]

# Blocked hardware: Conexant CX31993 (Fixed Mask ROM - DO NOT FLASH)
CONEXANT_VID = 0x0572
CONEXANT_PID = 0x1B08


class DeviceSecurityException(Exception):
    """Raised when an unsafe operation is attempted against protected or fixed-ROM hardware."""
    pass


class DeviceCommunicationError(Exception):
    """Raised when HID communication fails or device times out."""
    pass


@dataclass
class DiscoveredDevice:
    vendor_id: int
    product_id: int
    path: bytes
    manufacturer_string: str
    product_string: str
    serial_number: str
    is_ktmicro: bool = False
    is_conexant: bool = False
    status_description: str = ""

    @property
    def vid_pid_hex(self) -> str:
        return f"0x{self.vendor_id:04X}:0x{self.product_id:04X}"


def is_conexant_cx31993(dev_info: Dict[str, Any]) -> bool:
    """Check if device descriptor matches Conexant CX31993."""
    vid = dev_info.get("vendor_id", 0)
    prod = str(dev_info.get("product_string", "")).lower()
    mfg = str(dev_info.get("manufacturer_string", "")).lower()

    if vid == CONEXANT_VID:
        return True
    if "cx31993" in prod or "cx31993" in mfg:
        return True
    if "conexant" in prod or "conexant" in mfg:
        return True
    return False


def is_ktmicro_candidate(dev_info: Dict[str, Any]) -> bool:
    """Check if device descriptor matches known KTMicro / WalkPlay hardware."""
    vid = dev_info.get("vendor_id", 0)
    prod = str(dev_info.get("product_string", "")).lower()
    mfg = str(dev_info.get("manufacturer_string", "")).lower()

    if vid in KTMICRO_KNOWN_VIDS:
        return True

    kt_keywords = ["allegro", "bmaster", "kt02h20", "ktmicro", "walkplay", "ja11", "jm12"]
    if any(k in prod or k in mfg for k in kt_keywords):
        return True

    return False


def scan_devices() -> List[DiscoveredDevice]:
    """Scan and classify all connected USB HID audio/DSP devices."""
    if hid is None:
        return []

    results: List[DiscoveredDevice] = []
    seen_paths = set()

    for item in hid.enumerate():
        path = item.get("path", b"")
        if path in seen_paths:
            continue
        seen_paths.add(path)

        vid = item.get("vendor_id", 0)
        pid = item.get("product_id", 0)
        prod = item.get("product_string") or "Unknown Device"
        mfg = item.get("manufacturer_string") or ""
        serial = item.get("serial_number") or ""

        is_cx = is_conexant_cx31993(item)
        is_kt = is_ktmicro_candidate(item)

        if is_cx:
            status = "Host DSP Only (Conexant CX31993 - Flash BLOCKED for hardware safety)"
        elif is_kt:
            status = "Hardware Flashable (KTMicro KT02H20 / WalkPlay HID)"
        else:
            status = "Standard USB HID Device"

        results.append(
            DiscoveredDevice(
                vendor_id=vid,
                product_id=pid,
                path=path,
                manufacturer_string=mfg,
                product_string=prod,
                serial_number=serial,
                is_ktmicro=is_kt,
                is_conexant=is_cx,
                status_description=status,
            )
        )

    return results


class MockKTDevice:
    """Emulates KTMicro KT02H20 USB HID registers for testing and dry-run without hardware."""

    def __init__(self, vendor_id: int = 0x31B2, product_id: int = 0x0111):
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.is_open = True
        self.ram_registers: Dict[int, List[int]] = {}
        self.nvram_registers: Dict[int, List[int]] = {}
        self.last_sent: List[int] = []
        self.response_queue: List[List[int]] = []
        self.commit_count = 0

        # Initialize defaults
        self._init_defaults()

    def _init_defaults(self):
        # Register 0x24: EQ slot (default active slot = 0x03)
        self.ram_registers[0x24] = [0x24, 0, 0, 0, 0x57, 0, 0x03, 0, 0, 0]
        # Register 0x66: Preamp (0.0 dB, 0.5 dB steps: 0*2 = 0)
        self.ram_registers[0x66] = [0x66, 0, 0, 0, 0x57, 0, 0x00, 0, 0, 0]
        # Register 0x11: DAC Digital Filter (1 = FAST-LL default)
        self.ram_registers[0x11] = [0x11, 0, 0, 0, 0x57, 0, 0x01, 0, 0, 0]

        default_freqs = [100, 500, 1000, 2500, 10000]
        for i in range(5):
            gf_reg = 0x26 + i * 2
            q_reg = gf_reg + 1
            freq = default_freqs[i]
            # gain=0, freq
            self.ram_registers[gf_reg] = [gf_reg, 0, 0, 0, 0x57, 0, 0, 0, freq & 0xFF, (freq >> 8) & 0xFF]
            # Q=1.00 (1000), type=0 (PK)
            self.ram_registers[q_reg] = [q_reg, 0, 0, 0, 0x57, 0, 232, 3, 0, 0]

        self.nvram_registers = {k: list(v) for k, v in self.ram_registers.items()}

    def write(self, data: Sequence[int]) -> int:
        pkt = list(data)
        self.last_sent = pkt
        if not pkt or pkt[0] != 0x4B:
            return len(data)

        payload = pkt[1:]
        reg = payload[0]
        cmd = payload[4]

        if cmd == 0x52:  # READ
            # Respond with current register content
            content = self.ram_registers.get(reg, [reg, 0, 0, 0, 0x52, 0, 0, 0, 0, 0])
            resp = [0x4B] + list(content)
            resp[5] = 0x52  # CMD byte in report response
            self.response_queue.append(resp)

        elif cmd == 0x57:  # WRITE to RAM
            self.ram_registers[reg] = list(payload)

        elif cmd == 0x53:  # COMMIT to NVRAM
            self.nvram_registers = {k: list(v) for k, v in self.ram_registers.items()}
            self.commit_count += 1
            # Commit ACK response
            self.response_queue.append([0x4B, 0, 0, 0, 0, 0x53, 0, 3, 0, 0, 0])

        elif cmd == 0x43:  # CLEAR / RESET
            self._init_defaults()
            self.response_queue.append([0x4B, 0, 0, 0, 0, 0x43, 0, 0, 0, 0, 0])

        return len(data)

    def read(self, max_length: int, timeout_ms: int = 500) -> List[int]:
        if self.response_queue:
            return self.response_queue.pop(0)
        return []

    def close(self):
        self.is_open = False


class KTMicroDSPDevice:
    """Manages high-level PEQ operations for KTMicro KT02H20 / WalkPlay DSP DACs."""

    BASE_REG_OFFSET = 0x26
    REG_SLOT = 0x24
    REG_PREAMP = 0x66
    REG_DAC_FILTER = 0x11
    REPORT_ID = 0x4B
    CMD_READ = 0x52    # 'R'
    CMD_WRITE = 0x57   # 'W'
    CMD_COMMIT = 0x53  # 'S'
    CMD_CLEAR = 0x43   # 'C'

    TYPE_MAP = {
        "PK": 0,
        "PEAK": 0,
        "PEAKING": 0,
        "LPF": 1,
        "HPF": 2,
        "LSQ": 3,
        "LOW_SHELF": 3,
        "LOWSHELF": 3,
        "HSQ": 4,
        "HIGH_SHELF": 4,
        "HIGHSHELF": 4,
    }

    TYPE_REV_MAP = {
        0: "PK",
        1: "LPF",
        2: "HPF",
        3: "LSQ",
        4: "HSQ",
    }

    DAC_FILTERS = {
        "FAST-LL": 1,  # Fast roll-off, linear phase
        "FAST-PC": 2,  # Fast roll-off, phase compensation
        "SLOW-LL": 3,  # Slow roll-off, linear phase
        "SLOW-PC": 4,  # Slow roll-off, phase compensation
        "NON-OS": 5,   # Non-oversampling (NOS)
    }

    DAC_FILTERS_REV = {v: k for k, v in DAC_FILTERS.items()}

    def __init__(
        self,
        vendor_id: Optional[int] = None,
        product_id: Optional[int] = None,
        path: Optional[bytes] = None,
        use_mock: bool = False,
    ):
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.path = path
        self.use_mock = use_mock
        self._dev = None

    def connect(self):
        """Connect to target HID device with safety verification."""
        # Safety Guard Check: Conexant CX31993
        if self.vendor_id == CONEXANT_VID:
            raise DeviceSecurityException(
                f"SAFETY GUARD: Device 0x{self.vendor_id:04X}:0x{self.product_id:04X} is a Conexant CX31993 DAC. "
                "The CX31993 has fixed mask ROM and does not support hardware flashing. "
                "Attempting HID register writes will corrupt OTP descriptors. "
                "Use 'export-pipewire' or 'export-apo' for host-side DSP."
            )

        if self.use_mock:
            self._dev = MockKTDevice(self.vendor_id or 0x31B2, self.product_id or 0x0111)
            return

        if hid is None:
            raise DeviceCommunicationError("Python 'hid' library is not available.")

        # If specific path provided, open directly
        if self.path:
            self._dev = hid.device()
            self._dev.open_path(self.path)
            return

        # If VID/PID specified, find and verify
        if self.vendor_id is not None and self.product_id is not None:
            for item in hid.enumerate(self.vendor_id, self.product_id):
                if is_conexant_cx31993(item):
                    raise DeviceSecurityException(
                        f"SAFETY GUARD: Device at {item.get('path')} matches Conexant CX31993. Flashing blocked."
                    )
                self._dev = hid.device()
                self._dev.open_path(item["path"])
                return
            raise DeviceCommunicationError(f"Device 0x{self.vendor_id:04X}:0x{self.product_id:04X} not found.")

        # Otherwise dynamic scan for KTMicro candidate
        candidates = scan_devices()
        kt_candidates = [d for d in candidates if d.is_ktmicro and not d.is_conexant]
        if not kt_candidates:
            raise DeviceCommunicationError(
                "No compatible KTMicro / WalkPlay DSP DAC found. "
                "Ensure device is connected and udev rules are installed."
            )

        # Open the first matching KTMicro candidate
        chosen = kt_candidates[0]
        self.vendor_id = chosen.vendor_id
        self.product_id = chosen.product_id
        self._dev = hid.device()
        self._dev.open_path(chosen.path)

    def close(self):
        if self._dev:
            self._dev.close()
            self._dev = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _send_packet(self, reg: int, cmd: int, d0: int = 0, d1: int = 0, d2: int = 0, d3: int = 0) -> None:
        """Frame and send an 11-byte report to the DAC."""
        report = [
            self.REPORT_ID,
            reg & 0xFF,
            0x00,
            0x00,
            0x00,
            cmd & 0xFF,
            0x00,
            d0 & 0xFF,
            d1 & 0xFF,
            d2 & 0xFF,
            d3 & 0xFF,
        ]
        if not self._dev:
            raise DeviceCommunicationError("Device not connected.")
        self._dev.write(report)

    def _read_register(self, reg: int, timeout_ms: int = 500) -> List[int]:
        """Send a READ request for register and return the received payload matching reg."""
        self._send_packet(reg=reg, cmd=self.CMD_READ)
        start_time = time.time()
        while (time.time() - start_time) * 1000 < timeout_ms:
            resp = self._dev.read(64, timeout_ms=50)
            if not resp:
                continue
            # Strip ReportID byte if returned by backend
            if resp[0] == self.REPORT_ID:
                resp = resp[1:]
            # Ensure packet is the READ response for requested register
            if len(resp) >= 6 and resp[0] == reg and resp[4] == self.CMD_READ:
                return resp

        raise DeviceCommunicationError(f"Timeout reading register 0x{reg:02X}.")

    def set_dac_filter(self, filter_name: str, commit_flash: bool = False) -> None:
        """Set hardware DAC reconstruction filter (FAST-LL, FAST-PC, SLOW-LL, SLOW-PC, NON-OS)."""
        idx = self.DAC_FILTERS.get(filter_name.upper())
        if not idx:
            valid = ", ".join(self.DAC_FILTERS.keys())
            raise ValueError(f"Unknown filter '{filter_name}'. Valid options: {valid}")
        self._send_packet(self.REG_DAC_FILTER, self.CMD_WRITE, idx, 0, 0, 0)
        time.sleep(0.02)
        if commit_flash:
            self._send_packet(0x00, self.CMD_COMMIT, 0, 0, 0, 0)
            time.sleep(0.05)
            try:
                self._dev.read(64, timeout_ms=300)
            except Exception:
                pass

    def apply_preset(
        self,
        preset: Dict[str, Any],
        commit_flash: bool = False,
        compensate_2x: bool = False,
    ) -> None:
        """Write 5-band PEQ and preamp into the DAC.

        If commit_flash is True, commits settings to onboard NVRAM.
        If compensate_2x is True, compensates for older KT02H20 firmwares with 2x frequency offset.
        """
        bands = preset.get("bands", [])
        if len(bands) < 5:
            raise ValueError(f"Preset requires 5 bands, got {len(bands)}.")

        # 1. Enable EQ slot (Slot 0x03)
        slot_id = preset.get("slot_id", 0x03)
        self._send_packet(reg=self.REG_SLOT, cmd=self.CMD_WRITE, d0=slot_id)
        time.sleep(0.01)

        # 2. Write 5 bands
        for i in range(5):
            band = bands[i]
            gain = float(band.get("gain", 0.0))
            freq = float(band.get("freq", 1000.0))
            if compensate_2x:
                freq = freq / 2.0
            q = float(band.get("q", 1.0))
            ftype = str(band.get("type", "PK")).upper()

            # Encode Gain: signed 16-bit little-endian, scaled x 10
            gain_scaled = int(round(gain * 10.0))
            if gain_scaled < 0:
                gain_scaled += 0x10000
            gain_lo = gain_scaled & 0xFF
            gain_hi = (gain_scaled >> 8) & 0xFF

            # Encode Frequency: unsigned 16-bit little-endian, Hz
            freq_val = int(round(freq))
            freq_lo = freq_val & 0xFF
            freq_hi = (freq_val >> 8) & 0xFF

            # Encode Q: unsigned 16-bit little-endian, scaled x 1000
            q_scaled = int(round(q * 1000.0))
            q_lo = q_scaled & 0xFF
            q_hi = (q_scaled >> 8) & 0xFF

            # Encode Type
            type_val = self.TYPE_MAP.get(ftype, 0)

            # Register addresses
            reg_gf = self.BASE_REG_OFFSET + i * 2
            reg_q = reg_gf + 1

            # Fire register writes (Gain/Freq then Q/Type)
            self._send_packet(reg_gf, self.CMD_WRITE, gain_lo, gain_hi, freq_lo, freq_hi)
            time.sleep(0.01)
            self._send_packet(reg_q, self.CMD_WRITE, q_lo, q_hi, type_val, 0x00)
            time.sleep(0.01)

        # 3. Write Preamp (Register 0x66)
        # KTMicro stores signed digital gain with 0.5 dB steps: value = round(gain_db * 2)
        preamp_db = float(preset.get("preamp", 0.0))
        preamp_encoded = int(round(preamp_db * 2.0)) & 0xFF
        self._send_packet(self.REG_PREAMP, self.CMD_WRITE, preamp_encoded, 0x00, 0x00, 0x00)
        time.sleep(0.01)

        # 4. Optional NVRAM Flash Commit
        if commit_flash:
            # Commit command to register 0x00
            self._send_packet(0x00, self.CMD_COMMIT, 0x00, 0x00, 0x00, 0x00)
            time.sleep(0.05)
            # Read and consume commit ACK
            try:
                self._dev.read(64, timeout_ms=300)
            except Exception:
                pass

    def read_current_peq(self, compensate_2x: bool = False) -> Dict[str, Any]:
        """Read 5 bands, global preamp, and active slot from the hardware registers."""
        # 1. Read active slot
        slot_resp = self._read_register(self.REG_SLOT)
        slot_id = slot_resp[6] if len(slot_resp) > 6 else 0x03

        # 2. Read preamp (0.5 dB step decoding: signed_byte / 2.0)
        preamp_resp = self._read_register(self.REG_PREAMP)
        raw_preamp = preamp_resp[6] if len(preamp_resp) > 6 else 0
        signed_preamp = raw_preamp - 256 if raw_preamp > 127 else raw_preamp
        preamp_db = round(signed_preamp / 2.0, 1)

        # 3. Read DAC reconstruction filter
        try:
            filter_resp = self._read_register(self.REG_DAC_FILTER, timeout_ms=200)
            filter_idx = filter_resp[6] if len(filter_resp) > 6 else 1
            filter_name = self.DAC_FILTERS_REV.get(filter_idx, f"FILTER_{filter_idx}")
        except Exception:
            filter_name = "FAST-LL"

        # 4. Read 5 bands
        bands = []
        for i in range(5):
            reg_gf = self.BASE_REG_OFFSET + i * 2
            reg_q = reg_gf + 1

            gf_resp = self._read_register(reg_gf)
            q_resp = self._read_register(reg_q)

            # Decode gain & freq
            gain_raw = gf_resp[6] | (gf_resp[7] << 8)
            gain_signed = gain_raw - 0x10000 if gain_raw > 0x7FFF else gain_raw
            gain_db = round(gain_signed / 10.0, 1)

            freq_hz = float(gf_resp[8] | (gf_resp[9] << 8))
            if compensate_2x:
                freq_hz = freq_hz * 2.0

            # Decode Q & filter type
            q_raw = q_resp[6] | (q_resp[7] << 8)
            q_val = round(q_raw / 1000.0, 2)
            type_val = q_resp[8]
            ftype = self.TYPE_REV_MAP.get(type_val, "PK")

            bands.append({
                "index": i + 1,
                "type": ftype,
                "freq": freq_hz,
                "gain": gain_db,
                "q": q_val,
            })

        return {
            "slot_id": slot_id,
            "preamp": preamp_db,
            "dac_filter": filter_name,
            "bands": bands,
        }
