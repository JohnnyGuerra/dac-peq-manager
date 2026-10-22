"""Moondrop FreeDSP / May DSP Cable hardware protocol adapter.

--------------------------------------------------------------------------------
ACKNOWLEDGMENTS & UPSTREAM ATTRIBUTION:
This module incorporates protocol research and packet framing reverse-engineered
from Moondrop's cloud web configurator (https://hub.moondroplab.tech) and the
open-source community project:
  - MiyukiVigil/Hub_Moon (https://github.com/MiyukiVigil/Hub_Moon, MIT License)
    Documented the 64-byte USB HID report framing, 9-band biquad memory layout,
    and live audition (0x20) vs. flash commit (0x21) command opcodes.
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Sequence

try:
    import hid
except ImportError:
    hid = None

from dac_peq.ktmicro_hid import DeviceCommunicationError, DeviceSecurityException
from dac_peq.transport import BaseDSPDevice


class MockMoondropDevice:
    """Mock device emulating Moondrop FreeDSP 9-band HID endpoints for unit testing."""

    def __init__(self, vendor_id: int = 0x31B2, product_id: int = 0x0112):
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.is_open = True
        self.written_reports: List[List[int]] = []
        self.commit_count = 0
        
        # Default 9-band flat frame
        self.last_payload = [0x00] * 64
        self.last_payload[0] = 0x20
        self.last_payload[1] = 9
        for i in range(9):
            offset = 4 + i * 5
            self.last_payload[offset] = 0  # PK
            freq = 1000
            self.last_payload[offset + 1] = freq & 0xFF
            self.last_payload[offset + 2] = (freq >> 8) & 0xFF
            self.last_payload[offset + 3] = 0  # 0 dB
            self.last_payload[offset + 4] = 10 # Q=1.0

    def write(self, data: Sequence[int]) -> int:
        pkt = list(data)
        self.written_reports.append(pkt)
        if pkt:
            if pkt[0] in (0x20, 0x21):
                self.last_payload = list(pkt)
                if pkt[0] == 0x21:
                    self.commit_count += 1
        return len(data)

    def read(self, max_length: int, timeout_ms: int = 500) -> List[int]:
        return list(self.last_payload)

    def close(self):
        self.is_open = False


class MoondropFreeDSPDevice(BaseDSPDevice):
    """Hardware DSP driver for Moondrop FreeDSP, Chu II DSP, and May DSP cable.

    Features:
      - 9-band hardware biquad parametric equalizer
      - Preamp digital volume adjustment
      - Direct live RAM or flash commit
    """

    REPORT_ID = 0x00
    MOONDROP_VID = 0x31B2
    MOONDROP_PID = 0x0112

    TYPE_MAP = {
        "PK": 0,
        "PEAK": 0,
        "PEAKING": 0,
        "LSQ": 1,
        "LOW_SHELF": 1,
        "LOWSHELF": 1,
        "HSQ": 2,
        "HIGH_SHELF": 2,
        "HIGHSHELF": 2,
    }

    TYPE_REV_MAP = {
        0: "PK",
        1: "LSQ",
        2: "HSQ",
    }

    @property
    def max_bands(self) -> int:
        return 9

    @property
    def architecture_name(self) -> str:
        return "moondrop_dsp"

    def connect(self) -> None:
        if self.use_mock:
            self._dev = MockMoondropDevice(self.vendor_id or self.MOONDROP_VID, self.product_id or self.MOONDROP_PID)
            return

        if hid is None:
            raise DeviceCommunicationError("Python 'hid' library is not available.")

        vid = self.vendor_id or self.MOONDROP_VID
        pid = self.product_id or self.MOONDROP_PID

        for item in hid.enumerate(vid, pid):
            self._dev = hid.device()
            self._dev.open_path(item["path"])
            return

        raise DeviceCommunicationError(f"Moondrop FreeDSP device 0x{vid:04X}:0x{pid:04X} not found.")

    def close(self) -> None:
        if hasattr(self, "_dev") and self._dev:
            self._dev.close()
            self._dev = None

    def apply_preset(
        self,
        preset: Dict[str, Any],
        commit_flash: bool = False,
        compensate_2x: bool = False,
    ) -> None:
        """Encode and transmit up to 9 biquad bands to Moondrop DSP."""
        bands = preset.get("bands", [])
        if len(bands) > self.max_bands:
            from dac_peq.biquad import decimate_bands
            bands = decimate_bands(bands, target_bands=self.max_bands)

        preamp = float(preset.get("preamp", 0.0))

        # Build Moondrop FreeDSP 64-byte payload frame
        # Byte 0: Command (0x20 = Apply Live RAM, 0x21 = Flash Commit)
        cmd_byte = 0x21 if commit_flash else 0x20
        payload = [0x00] * 64
        payload[0] = cmd_byte
        payload[1] = len(bands) & 0xFF

        # Preamp encoded as int16 LE x 100
        preamp_scaled = int(round(preamp * 100.0))
        if preamp_scaled < 0:
            preamp_scaled += 0x10000
        payload[2] = preamp_scaled & 0xFF
        payload[3] = (preamp_scaled >> 8) & 0xFF

        # Write each band (5 bytes per band: Type[1], Freq[2], Gain[1], Q[1])
        offset = 4
        for b in bands[:self.max_bands]:
            ftype = self.TYPE_MAP.get(str(b.get("type", "PK")).upper(), 0)
            freq = int(round(float(b.get("freq", 1000.0))))
            gain = int(round(float(b.get("gain", 0.0)) * 10.0))
            if gain < 0:
                gain += 256
            q_val = int(round(float(b.get("q", 1.0)) * 10.0)) & 0xFF

            payload[offset] = ftype & 0xFF
            payload[offset + 1] = freq & 0xFF
            payload[offset + 2] = (freq >> 8) & 0xFF
            payload[offset + 3] = gain & 0xFF
            payload[offset + 4] = q_val & 0xFF
            offset += 5

        if not hasattr(self, "_dev") or not self._dev:
            raise DeviceCommunicationError("Device not connected.")

        self._dev.write(payload)
        if commit_flash:
            time.sleep(0.5)

    def read_current_peq(self, compensate_2x: bool = False) -> Dict[str, Any]:
        """Read 9 bands and preamp from hardware."""
        if not hasattr(self, "_dev") or not self._dev:
            raise DeviceCommunicationError("Device not connected.")

        # Request state in real device
        if not self.use_mock:
            req = [0x00] * 64
            req[0] = 0x22
            try:
                self._dev.write(req)
            except Exception:
                pass

        raw = self._dev.read(64, timeout_ms=500)
        if not raw or len(raw) < 4:
            raise DeviceCommunicationError("Timeout reading registers from Moondrop FreeDSP.")

        num_bands = min(self.max_bands, max(1, raw[1]))
        preamp_raw = raw[2] | (raw[3] << 8)
        if preamp_raw > 32767:
            preamp_raw -= 65536
        preamp_db = round(preamp_raw / 100.0, 1)

        bands = []
        offset = 4
        for i in range(num_bands):
            if offset + 5 > len(raw):
                break
            type_val = raw[offset]
            ftype = self.TYPE_REV_MAP.get(type_val, "PK")
            freq_hz = float(raw[offset + 1] | (raw[offset + 2] << 8))
            gain_raw = raw[offset + 3]
            if gain_raw > 127:
                gain_raw -= 256
            gain_db = round(gain_raw / 10.0, 1)
            q_raw = raw[offset + 4]
            q_val = round(q_raw / 10.0, 2)
            offset += 5

            bands.append({
                "index": i + 1,
                "type": ftype,
                "freq": freq_hz,
                "gain": gain_db,
                "q": q_val,
            })

        while len(bands) < self.max_bands:
            bands.append({
                "index": len(bands) + 1,
                "type": "PK",
                "freq": 1000.0,
                "gain": 0.0,
                "q": 1.0,
            })

        return {
            "name": "Moondrop FreeDSP Active Hardware PEQ",
            "preamp": preamp_db,
            "bands": bands,
        }
