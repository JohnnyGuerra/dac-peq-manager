"""
dac-peq-manager - Online Community Measurement Databases Engine
Integrates jaakkopasanen/AutoEq and Squiglink/CrinGraph databases.
Enables searching 8,800+ headphone & IEM models, parsing 5-band biquad parameters,
and pulling profiles directly into KTMicro hardware NVRAM or host DSP exporters.

--------------------------------------------------------------------------------
ACKNOWLEDGMENTS & UPSTREAM ATTRIBUTION:
  - jaakkopasanen/AutoEq (https://github.com/jaakkopasanen/AutoEq, MIT License):
    Universal index schema (INDEX.md), parametric EQ tables, and multi-source
    measurement normalization across 29 independent review labs.
  - Squiglink community measurers: Super Review, Crinacle, Oratory1990, HBB,
    TimmyV, Paul Wasabii, GadgetryTech, Fahryst, ToneDeafMonk.
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

AUTOEQ_INDEX_URL = "https://raw.githubusercontent.com/jaakkopasanen/AutoEq/master/results/INDEX.md"
AUTOEQ_RAW_BASE = "https://raw.githubusercontent.com/jaakkopasanen/AutoEq/master/results"
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "dac-peq-manager"


@dataclass
class DatabaseEntry:
    """A headphone/IEM entry in the community measurement database."""
    name: str
    source: str
    path: str  # E.g. "./oratory1990/over-ear/Sennheiser%20HD%20600"
    fallback_preamp: Optional[float] = None
    fallback_bands: Optional[List[Dict[str, Any]]] = None

    @property
    def clean_path(self) -> str:
        """Strip leading ./ from relative path."""
        return self.path.lstrip("./")

    @property
    def raw_readme_url(self) -> str:
        """Direct raw GitHub URL for the model's README.md."""
        clean = self.clean_path
        return f"{AUTOEQ_RAW_BASE}/{clean}/README.md"

    @property
    def raw_parametric_eq_url(self) -> str:
        """Direct raw GitHub URL for ParametricEQ.txt."""
        clean = self.clean_path
        model_name = urllib.parse.quote(self.name)
        return f"{AUTOEQ_RAW_BASE}/{clean}/{model_name}%20ParametricEQ.txt"

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "name": self.name,
            "source": self.source,
            "path": self.path,
            "readme_url": self.raw_readme_url,
        }
        if self.fallback_preamp is not None:
            out["preamp"] = self.fallback_preamp
        if self.fallback_bands is not None:
            out["bands"] = self.fallback_bands
        return out


def load_offline_fallback() -> List[DatabaseEntry]:
    """Load the bundled Top 15 Reddit IEM & benchmark offline AutoEq snapshot."""
    cur = Path(__file__).resolve().parent
    candidates = [
        cur / "data" / "autoeq_fallback.json",
        cur.parent.parent / "data" / "autoeq_fallback.json",
        Path.cwd() / "data" / "autoeq_fallback.json",
    ]
    for cand in candidates:
        if cand.is_file():
            try:
                raw = json.loads(cand.read_text(encoding="utf-8"))
                return [
                    DatabaseEntry(
                        name=item["name"],
                        source=item["source"],
                        path=item["path"],
                        fallback_preamp=item.get("preamp"),
                        fallback_bands=item.get("bands"),
                    )
                    for item in raw
                ]
            except Exception:
                pass
    return []


def parse_index_markdown(markdown_text: str) -> List[DatabaseEntry]:
    """Parse AutoEq INDEX.md into structured DatabaseEntry items."""
    pattern = re.compile(r"^- \[(.*?)\]\((.*?)\)(?: by (.*?))?$")
    entries: List[DatabaseEntry] = []
    for line in markdown_text.splitlines():
        line_clean = line.strip()
        m = pattern.match(line_clean)
        if m:
            name = m.group(1).strip()
            path = m.group(2).strip()
            source = (m.group(3) or "Community").strip()
            entries.append(DatabaseEntry(name=name, source=source, path=path))
    return entries


def parse_readme_peq(readme_text: str, max_bands: Optional[int] = 5) -> Tuple[float, List[Dict[str, Any]]]:
    """
    Parse PEQ parameters and preamp from an AutoEq README.md.
    AutoEq explicitly optimizes filters 1-5 as a standalone 5-band PEQ for hardware equalizers.
    If max_bands is None, extracts all available bands.
    """
    # 1. Preamp extraction
    # E.g. "Apply preamp of -6.2 dB or -6.1 dB, respectively." or "Apply preamp of -3.5 dB"
    preamp = 0.0
    preamp_match = re.search(
        r"Apply preamp of\s+([+-]?\d+(?:\.\d+)?)\s*dB(?:\s+or\s+([+-]?\d+(?:\.\d+)?)\s*dB)?",
        readme_text,
        re.IGNORECASE,
    )
    if preamp_match:
        preamp = float(preamp_match.group(1))

    # 2. Table extraction
    bands: List[Dict[str, Any]] = []
    in_peq_section = False

    for line in readme_text.splitlines():
        if "### Parametric EQs" in line or "## Parametric EQs" in line:
            in_peq_section = True
            continue
        if in_peq_section and line.startswith("### ") and not "Parametric" in line:
            break
        if in_peq_section and line.strip().startswith("|") and not line.strip().startswith("|---"):
            parts = [p.strip() for p in line.split("|")[1:-1]]
            if len(parts) >= 5 and parts[0].isdigit():
                idx = int(parts[0])
                ftype_raw = parts[1].lower()
                try:
                    fc = float(parts[2])
                    q = float(parts[3])
                    gain = float(parts[4])
                except ValueError:
                    continue

                ftype = "PK"
                if "low" in ftype_raw or "lsc" in ftype_raw or "lsq" in ftype_raw:
                    ftype = "LSQ"
                elif "high" in ftype_raw or "hsc" in ftype_raw or "hsq" in ftype_raw:
                    ftype = "HSQ"

                bands.append({
                    "index": idx,
                    "type": ftype,
                    "freq": fc,
                    "gain": gain,
                    "q": q,
                })

    if max_bands is not None:
        return preamp, bands[:max_bands]
    return preamp, bands


def parse_parametric_eq_text(eq_text: str, max_bands: Optional[int] = 5) -> Tuple[float, List[Dict[str, Any]]]:
    """Fallback parser for standard EqualizerAPO ParametricEQ.txt files."""
    preamp = 0.0
    preamp_m = re.search(r"Preamp:\s*([+-]?\d+(?:\.\d+)?)\s*dB", eq_text, re.IGNORECASE)
    if preamp_m:
        preamp = float(preamp_m.group(1))

    # Filter lines: Filter 1: ON PK Fc 200 Hz Gain -2.0 dB Q 1.4
    filter_pattern = re.compile(
        r"Filter\s+(\d+):\s+ON\s+([A-Z0-9_]+)\s+Fc\s+([0-9.]+)\s*Hz\s+Gain\s+([+-]?[0-9.]+)\s*dB\s+Q\s+([0-9.]+)",
        re.IGNORECASE,
    )

    bands: List[Dict[str, Any]] = []
    for line in eq_text.splitlines():
        m = filter_pattern.search(line)
        if m:
            idx = int(m.group(1))
            ftype_raw = m.group(2).upper()
            fc = float(m.group(3))
            gain = float(m.group(4))
            q = float(m.group(5))

            ftype = "PK"
            if ftype_raw in ("LSC", "LOW_SHELF", "LSQ"):
                ftype = "LSQ"
            elif ftype_raw in ("HSC", "HIGH_SHELF", "HSQ"):
                ftype = "HSQ"

            bands.append({
                "index": idx,
                "type": ftype,
                "freq": fc,
                "gain": gain,
                "q": q,
            })

    if max_bands is not None:
        return preamp, bands[:max_bands]
    return preamp, bands


class AutoEqDatabase:
    """Manager for querying and pulling headphone/IEM profiles from AutoEq."""

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self.cache_file = self.cache_dir / "autoeq_index.json"
        self._entries: Optional[List[DatabaseEntry]] = None

    def _ensure_cache_dir(self) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def fetch_index(self, force_refresh: bool = False, max_age_seconds: int = 86400 * 7) -> List[DatabaseEntry]:
        """Fetch the AutoEq index, reading from local cache when fresh."""
        if self._entries and not force_refresh:
            return self._entries

        self._ensure_cache_dir()

        # Check local cache validity
        if not force_refresh and self.cache_file.exists():
            file_age = time.time() - self.cache_file.stat().st_mtime
            if file_age < max_age_seconds:
                try:
                    with open(self.cache_file, "r", encoding="utf-8") as f:
                        raw_data = json.load(f)
                        self._entries = [
                            DatabaseEntry(name=item["name"], source=item["source"], path=item["path"])
                            for item in raw_data
                        ]
                        return self._entries
                except Exception:
                    pass  # Cache corrupt, fallback to download

        # Download from GitHub, falling back to bundled offline snapshot if offline
        try:
            req = urllib.request.Request(
                AUTOEQ_INDEX_URL,
                headers={"User-Agent": "dac-peq-manager/1.0"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                text = resp.read().decode("utf-8")

            self._entries = parse_index_markdown(text)

            # Write to local cache
            try:
                with open(self.cache_file, "w", encoding="utf-8") as f:
                    json.dump([e.to_dict() for e in self._entries], f, indent=2)
            except Exception:
                pass
        except Exception:
            fallback = load_offline_fallback()
            if fallback:
                self._entries = fallback
            else:
                raise

        return self._entries

    def search(
        self,
        query: str,
        source: Optional[str] = None,
        limit: int = 25,
    ) -> List[DatabaseEntry]:
        """
        Search indexed models by keyword.
        Matches all whitespace-separated words in query against model name and source.
        """
        entries = self.fetch_index()
        words = [w.lower() for w in query.strip().split() if w]

        results = []
        for e in entries:
            name_lower = e.name.lower()
            source_lower = e.source.lower()

            if source and source.lower() not in source_lower:
                continue

            if all(w in name_lower or w in source_lower for w in words):
                results.append(e)
                if len(results) >= limit:
                    break

        return results

    def list_sources(self) -> List[Tuple[str, int]]:
        """List all unique measurement sources with their model counts."""
        entries = self.fetch_index()
        counts: Dict[str, int] = {}
        for e in entries:
            counts[e.source] = counts.get(e.source, 0) + 1
        return sorted(counts.items(), key=lambda x: x[1], reverse=True)

    def pull_preset(self, entry: DatabaseEntry, target_bands: Optional[int] = 5) -> Dict[str, Any]:
        """
        Download and extract PEQ parameters and preamp for a given model.
        If target_bands is specified (default 5 for hardware), intelligently decimates
        using acoustic landmarks. If target_bands is None, preserves all parsed bands.
        """
        # Try fetching README.md first, then ParametricEQ.txt, then bundled offline snapshot
        preamp: float = 0.0
        bands: List[Dict[str, Any]] = []
        try:
            req = urllib.request.Request(
                entry.raw_readme_url,
                headers={"User-Agent": "dac-peq-manager/1.0"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                readme_text = resp.read().decode("utf-8")
            preamp, bands = parse_readme_peq(readme_text, max_bands=None)
        except Exception:
            try:
                req = urllib.request.Request(
                    entry.raw_parametric_eq_url,
                    headers={"User-Agent": "dac-peq-manager/1.0"},
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    eq_text = resp.read().decode("utf-8")
                preamp, bands = parse_parametric_eq_text(eq_text, max_bands=None)
            except Exception:
                if entry.fallback_bands:
                    preamp = float(entry.fallback_preamp or 0.0)
                    bands = [dict(b) for b in entry.fallback_bands]
                else:
                    for fb in load_offline_fallback():
                        if fb.name.lower() == entry.name.lower() and fb.fallback_bands:
                            preamp = float(fb.fallback_preamp or 0.0)
                            bands = [dict(b) for b in fb.fallback_bands]
                            break

        if not bands:
            raise ValueError(f"Could not extract parametric EQ bands for '{entry.name}'.")

        full_bands = [
            {
                "type": b["type"],
                "freq": round(float(b["freq"]), 1),
                "gain": round(float(b["gain"]), 1),
                "q": round(float(b["q"]), 2),
            }
            for b in bands
        ]

        if target_bands is not None:
            from dac_peq.biquad import decimate_bands
            active_bands = decimate_bands(bands, target_bands=target_bands)
        else:
            active_bands = full_bands

        # Generate clean slug
        clean_name = re.sub(r"[^a-zA-Z0-9]+", "_", entry.name).strip("_").lower()
        clean_source = re.sub(r"[^a-zA-Z0-9]+", "_", entry.source).strip("_").lower()
        slug = f"{clean_name}_{clean_source}"

        preset_data = {
            "name": f"{entry.name} ({entry.source})",
            "slug": slug,
            "description": f"AutoEq target optimization (source: {entry.source})",
            "preamp": round(preamp, 1),
            "bands": [
                {
                    "type": b["type"],
                    "freq": round(float(b["freq"]), 1),
                    "gain": round(float(b["gain"]), 1),
                    "q": round(float(b["q"]), 2),
                }
                for b in active_bands
            ],
            "full_bands": full_bands,
        }
        return preset_data

    def save_preset(self, preset_data: Dict[str, Any], dest_dir: Optional[Path] = None) -> Path:
        """Save a pulled preset to a local JSON file."""
        if dest_dir is None:
            # Look for default project presets directory
            dest_dir = Path.cwd() / "presets"
            if not dest_dir.exists():
                dest_dir = DEFAULT_CACHE_DIR / "presets"

        dest_dir.mkdir(parents=True, exist_ok=True)
        slug = preset_data.get("slug", "community_preset")
        target_path = dest_dir / f"{slug}.json"

        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(preset_data, f, indent=2)

        return target_path
