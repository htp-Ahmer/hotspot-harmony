"""SYNTHETIC demonstration data generator.

!!! THESE ARE NOT NASA DATA. !!!
Random points with an invented seasonal pattern, used only to test the app's
interface and code when no FIRMS files are available. Never use for results.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import hotspot_core as hc

SEASON = np.array([.3, .3, .6, 1.6, 1.8, .9, .4, .4, .6, 1.5, 1.7, .6])  # invented shape


def _raw(sensor, years, rate, rng, bbox=(69.3, 27.7, 75.4, 34.0)):
    days = pd.date_range(f"{years[0]}-01-01", f"{years[1]}-10-31", freq="D")
    if sensor == "VIIRS":
        days = days[days >= "2012-01-20"]
    ymult = dict(zip(range(1900, 2100), rng.lognormal(0, .3, 200)))
    lam = np.array([rate * SEASON[d.month - 1] * ymult[d.year] for d in days])
    n = rng.poisson(lam)
    dates = np.repeat(days.values, n)
    k = len(dates)
    w, s, e, nn = bbox
    centers = rng.uniform([w, s], [e, nn], size=(40, 2))
    c = centers[rng.integers(0, 40, k)]
    lon = np.clip(c[:, 0] + rng.normal(0, .35, k), w, e)
    lat = np.clip(c[:, 1] + rng.normal(0, .35, k), s, nn)
    raw = pd.DataFrame({"latitude": lat, "longitude": lon,
                        "acq_date": pd.to_datetime(dates).strftime("%Y-%m-%d"),
                        "acq_time": rng.integers(0, 2400, k), "frp": rng.gamma(2, 6, k),
                        "daynight": "D", "type": 0})
    if sensor == "VIIRS":
        raw["bright_ti4"] = 330.0
        raw["bright_ti5"] = 295.0
        raw["confidence"] = rng.choice(["l", "n", "h"], k, p=[.1, .7, .2])
    else:
        raw["brightness"] = 330.0
        raw["bright_t31"] = 295.0
        raw["confidence"] = rng.integers(10, 100, k)
    return raw


def make_demo(seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    frames = [hc.normalize_firms(_raw("MODIS", (2005, 2025), 9, rng)),
              hc.normalize_firms(_raw("VIIRS", (2012, 2025), 38, rng))]
    return hc.combine(frames, f"demo|{seed}", "demo")
