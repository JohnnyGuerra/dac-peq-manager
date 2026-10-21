"""Local NVRAM flash wear-out health and endurance tracking for USB DSP DACs.

Microcontrollers with onboard EEPROM or NOR flash (such as the KTMicro KT02H20)
have finite write cycle endurance (~10k-100k cycles) and lack wear-leveling controllers.
Repeatedly flashing physical NVRAM can degrade silicon blocks and lead to permanent failure.

This module persists timestamped write commits keyed by USB VID:PID / Serial into:
    ~/.cache/dac-peq-manager/flash_history.json
and provides wear statistics and preventive warning thresholds.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def get_default_cache_file() -> Path:
    """Return path to flash history cache file adhering to XDG conventions."""
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache:
        base = Path(xdg_cache)
    else:
        base = Path.home() / ".cache"
    return base / "dac-peq-manager" / "flash_history.json"


class FlashWearTracker:
    """Tracks and audits hardware NVRAM flash commits across USB DAC devices."""

    DAILY_WARNING_THRESHOLD = 10
    CUMULATIVE_WARNING_THRESHOLD = 50

    def __init__(self, cache_file: Optional[Path] = None):
        self.cache_file = cache_file or get_default_cache_file()
        self._data: Dict[str, Any] = {"version": 1, "devices": {}}
        self._load()

    def _load(self) -> None:
        """Load history from cache file if present and valid."""
        if not self.cache_file.is_file():
            return
        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict) and "devices" in loaded:
                    self._data = loaded
        except Exception:
            # Fall back to empty in-memory state on corrupted cache
            self._data = {"version": 1, "devices": {}}

    def _save(self) -> None:
        """Persist history to disk gracefully."""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except Exception:
            # Avoid crashing if cache dir is read-only
            pass

    def record_commit(
        self,
        device_id: str,
        preset_name: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> int:
        """Record a flash commit event for a hardware device.

        Args:
            device_id: Canonical device identifier (e.g. '0x31B2:0x0111').
            preset_name: Optional name of the preset burned to flash.
            notes: Optional descriptive metadata.

        Returns:
            Updated cumulative commit count for the device.
        """
        key = device_id.lower()
        devices = self._data.setdefault("devices", {})
        dev_entry = devices.setdefault(
            key,
            {
                "device_id": key,
                "total_commits": 0,
                "history": [],
            },
        )

        dev_entry["total_commits"] += 1
        now_iso = datetime.now(timezone.utc).isoformat()

        record = {
            "timestamp": now_iso,
            "epoch": time.time(),
            "preset": preset_name or "custom",
        }
        if notes:
            record["notes"] = notes

        dev_entry["history"].append(record)

        # Prune history to last 500 entries to prevent unbounded growth
        if len(dev_entry["history"]) > 500:
            dev_entry["history"] = dev_entry["history"][-500:]

        self._save()
        return dev_entry["total_commits"]

    def get_stats(self, device_id: str) -> Dict[str, Any]:
        """Retrieve wear metrics for a specific device.

        Returns:
            {
                'device_id': str,
                'total_commits': int,
                'last_24h_commits': int,
                'last_commit_time': Optional[str],
                'last_preset': Optional[str],
            }
        """
        key = device_id.lower()
        dev_entry = self._data.get("devices", {}).get(key)
        if not dev_entry:
            return {
                "device_id": key,
                "total_commits": 0,
                "last_24h_commits": 0,
                "last_commit_time": None,
                "last_preset": None,
            }

        one_day_ago = time.time() - 24 * 3600
        history = dev_entry.get("history", [])
        last_24h = sum(1 for h in history if h.get("epoch", 0.0) >= one_day_ago)

        last_record = history[-1] if history else {}
        return {
            "device_id": key,
            "total_commits": dev_entry.get("total_commits", 0),
            "last_24h_commits": last_24h,
            "last_commit_time": last_record.get("timestamp"),
            "last_preset": last_record.get("preset"),
        }

    def should_warn(
        self,
        device_id: str,
        daily_threshold: int = DAILY_WARNING_THRESHOLD,
        cumulative_threshold: int = CUMULATIVE_WARNING_THRESHOLD,
    ) -> Tuple[bool, str]:
        """Check if committing to flash exceeds safe wear thresholds.

        Returns:
            (should_warn, warning_message)
        """
        stats = self.get_stats(device_id)
        last_24h = stats["last_24h_commits"]
        total = stats["total_commits"]

        if last_24h >= daily_threshold:
            msg = (
                f"You have committed to hardware flash {last_24h} times in the last 24 hours "
                f"({total} cumulative burns). High flash frequency exhausts EEPROM endurance "
                "and can permanently corrupt onboard DSP memory."
            )
            return True, msg

        if total >= cumulative_threshold:
            msg = (
                f"This DAC has logged {total} cumulative NVRAM burns. "
                "Budget microcontroller flash sectors degrade after sustained writes. "
                "Consider auditioning changes via RAM ('apply') before committing."
            )
            return True, msg

        return False, ""

    def get_all_devices(self) -> List[Dict[str, Any]]:
        """Return statistics across all tracked devices."""
        return [self.get_stats(k) for k in self._data.get("devices", {})]

    def clear(self, device_id: Optional[str] = None) -> None:
        """Clear flash history for one device or all devices."""
        if device_id:
            key = device_id.lower()
            if key in self._data.get("devices", {}):
                del self._data["devices"][key]
        else:
            self._data = {"version": 1, "devices": {}}
        self._save()
