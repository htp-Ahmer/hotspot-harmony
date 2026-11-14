"""Optional helper: download FIRMS area data through the official FIRMS API.

Needs a free MAP_KEY: https://firms.modaps.eosdis.nasa.gov/api/map_key/
API docs: https://firms.modaps.eosdis.nasa.gov/api/area/
For multi-year history the archive download page is usually easier
(https://firms.modaps.eosdis.nasa.gov/download/); see README.md.
"""
from __future__ import annotations

import io
from datetime import date, timedelta

import pandas as pd
import requests

BASE = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
SOURCES = {"MODIS (Standard Processing)": "MODIS_SP",
           "VIIRS S-NPP (Standard Processing)": "VIIRS_SNPP_SP",
           "MODIS (Near Real-Time)": "MODIS_NRT",
           "VIIRS S-NPP (Near Real-Time)": "VIIRS_SNPP_NRT"}
MAX_DAYS = 5  # days per request


def fetch_area(map_key: str, source: str, bbox, start: date, end: date, progress=None) -> pd.DataFrame:
    """bbox=(west, south, east, north). Returns raw FIRMS CSV rows as a DataFrame."""
    w, s, e, n = bbox
    chunks, cur = [], start
    total = max(1, (end - start).days // MAX_DAYS + 1)
    i = 0
    while cur <= end:
        days = min(MAX_DAYS, (end - cur).days + 1)
        url = f"{BASE}/{map_key}/{source}/{w},{s},{e},{n}/{days}/{cur.isoformat()}"
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        text = r.text.strip()
        if not text.lower().startswith("latitude"):
            if text and "," not in text.split("\n")[0]:
                raise RuntimeError(f"FIRMS API replied: {text[:200]}")
        else:
            chunks.append(pd.read_csv(io.StringIO(text)))
        cur += timedelta(days=days)
        i += 1
        if progress:
            progress(min(1.0, i / total))
    return pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()
