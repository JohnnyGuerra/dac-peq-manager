"""Abstract base class and device factory for USB Audio DSP controllers.

--------------------------------------------------------------------------------
ACKNOWLEDGMENTS & UPSTREAM ATTRIBUTION:
This module establishes a vendor-agnostic hardware DSP abstraction layer
unifying multiple reverse-engineered protocols:
  1. KTMicro KT02H20 / WalkPlay (gxcreator/ktmicro-tools, jeromeof/devicePEQ, Ircama/ja11-config)
  2. Moondrop FreeDSP / Savitech / Comtrue (MiyukiVigil/Hub_Moon)
--------------------------------------------------------------------------------
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseDSPDevice(ABC):
    """Abstract interface representing a programmable USB Audio DSP hardware device."""

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

    @property
    @abstractmethod
    def max_bands(self) -> int:
        """Maximum number of hardware biquad bands supported by this device."""
        ...

    @property
    @abstractmethod
    def architecture_name(self) -> str:
        """Architecture identifier string."""
        ...

    @abstractmethod
    def connect(self) -> None:
        """Open USB HID handle and verify device connectivity and safety."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Close USB HID handle."""
        ...

    def __enter__(self) -> BaseDSPDevice:
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    @abstractmethod
    def apply_preset(
        self,
        preset: Dict[str, Any],
        commit_flash: bool = False,
        compensate_2x: bool = False,
    ) -> None:
        """Write PEQ bands and preamp to live RAM (or commit to NVRAM flash)."""
        ...

    @abstractmethod
    def read_current_peq(self, compensate_2x: bool = False) -> Dict[str, Any]:
        """Read active PEQ registers from hardware."""
        ...


def get_dsp_device(
    vendor_id: Optional[int] = None,
    product_id: Optional[int] = None,
    path: Optional[bytes] = None,
    use_mock: bool = False,
) -> BaseDSPDevice:
    """Factory creating the appropriate DSP driver instance based on USB IDs."""
    if vendor_id == 0x31B2 and product_id == 0x0112:
        from dac_peq.moondrop import MoondropFreeDSPDevice
        return MoondropFreeDSPDevice(vendor_id, product_id, path, use_mock)

    from dac_peq.ktmicro_hid import KTMicroDSPDevice
    return KTMicroDSPDevice(vendor_id, product_id, path, use_mock)
