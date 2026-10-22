"""Hardware DAC Directory & Compatibility Database for dac-peq-manager.

Catalogues portable USB-C DAC dongles, internal chipsets, max resolutions,
hardware flashability (KTMicro KT02H20 / WalkPlay vs. Conexant CX31993 vs. CS43131),
and recommended host vs. hardware DSP workflows.

--------------------------------------------------------------------------------
ACKNOWLEDGMENTS & HARDWARE ARCHITECTURE CITATIONS:
Hardware profiles, USB VID/PID mappings, and chipset architectures compile public
datasheets, Linux kernel USB audio device quirks, and community research:
  - KTMicro KT02H20: Reverse-engineered by gxcreator, jeromeof, and Ircama.
  - Conexant CX31993: Synaptics CX31993 UAC2 fixed-function audio controller.
  - Cirrus Logic CS43131: MasterHIFI 32-bit/384kHz high-dynamic-range DAC.
  - VIA Labs VL102/VL103: USB PD 100W/60W charging controller in 2-in-1 splitters.
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class DACInfo:
    """Detailed profile of a USB-C Audio DAC dongle."""
    id: str
    name: str
    brand: str
    chipset: str
    architecture: str
    dac_type: str  # 'hardware_dsp', 'fixed_mask_rom', 'host_dsp_only'
    flashable: bool
    vid: Optional[int] = None
    pid: Optional[int] = None
    vid_hex: Optional[str] = None
    pid_hex: Optional[str] = None
    resolution: str = "24-bit / 96 kHz"
    output_power: str = "30mW @ 32Ω"
    outputs: List[str] = field(default_factory=list)
    trrs_mic: bool = True
    recommendation: str = ""
    quirks: List[str] = field(default_factory=list)

    @property
    def is_hardware_flashable(self) -> bool:
        return self.flashable and self.architecture in ("ktmicro_dsp", "moondrop_dsp")

    @property
    def is_fixed_mask_rom(self) -> bool:
        return self.dac_type == "fixed_mask_rom" or "mask_rom_safety_lock" in self.quirks


class DACDatabase:
    """Catalog of known USB DAC dongles and DSP architectures."""

    def __init__(self, data_file: Optional[Path] = None):
        if data_file is None:
            cur = Path(__file__).resolve().parent
            data_file = cur / "data" / "dacs.json"
        self.data_file = data_file
        self._dacs: List[DACInfo] = []
        self._load()

    def _load(self) -> None:
        if not self.data_file.exists():
            return
        with open(self.data_file, "r", encoding="utf-8") as f:
            raw = json.load(f)
            self._dacs = [DACInfo(**item) for item in raw]

    def all(self) -> List[DACInfo]:
        """Return all catalogued DAC devices."""
        return list(self._dacs)

    def lookup(self, vid: Optional[int], pid: Optional[int]) -> Optional[DACInfo]:
        """Lookup DAC by exact USB Vendor ID and Product ID."""
        if vid is None:
            return None
        for d in self._dacs:
            if d.vid == vid and (pid is None or d.pid == pid or d.pid is None):
                return d
        return None

    def lookup_by_string(self, text: str) -> Optional[DACInfo]:
        """Lookup DAC by matching product name or chipset string."""
        text_lower = text.lower()
        for d in self._dacs:
            if d.name.lower() in text_lower or text_lower in d.name.lower():
                return d
            if d.chipset.lower() in text_lower:
                return d
        return None

    def search(self, query: str, flashable_only: bool = False) -> List[DACInfo]:
        """Search catalogued DACs by name, brand, chipset, architecture, or features."""
        words = query.lower().split()
        results: List[DACInfo] = []
        for d in self._dacs:
            if flashable_only and not d.flashable:
                continue
            haystack = (
                f"{d.id} {d.name} {d.brand} {d.chipset} {d.architecture} "
                f"{d.recommendation} {' '.join(d.quirks)} {' '.join(d.outputs)} "
                f"{d.vid_hex or ''} {d.pid_hex or ''}"
            ).lower()
            if all(w in haystack for w in words):
                results.append(d)
        return results

    def list_flashable(self) -> List[DACInfo]:
        """Return all hardware-flashable KTMicro / WalkPlay DSP devices."""
        return [d for d in self._dacs if d.flashable]

    def list_mask_rom(self) -> List[DACInfo]:
        """Return all fixed mask ROM devices (Conexant CX31993, etc.)."""
        return [d for d in self._dacs if d.is_fixed_mask_rom]
