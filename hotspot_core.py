"""Hotspot Harmony - core data logic (pure pandas/numpy; no Streamlit/Plotly).

Reads NASA FIRMS active-fire CSVs from MODIS and VIIRS, normalises them to one
schema, builds monthly activity series and harmonises the two sensors.
"""
from __future__ import annotations

import glob
import io
import os
from dataclasses import dataclass

import numpy as np
import pandas as pd

CELL_DEG = 0.1  # grid size used to de-duplicate detections (fire-cell-days)
CONF_ORDER = {"low": 0, "nominal": 1, "unknown": 1, "high": 2}


# --------------------------------------------------------------------------
# Reading / normalising FIRMS files
# --------------------------------------------------------------------------
def detect_sensor(columns) -> str | None:
    cols = {str(c).strip().lower() for c in columns}
    if "bright_ti4" in cols:
        return "VIIRS"
    if "brightness" in cols and "bright_t31" in cols:
        return "MODIS"
    return None


def _confidence_level(series: pd.Series, sensor: str) -> pd.Series:
    if sensor == "VIIRS":
        m = {"l": "low", "low": "low", "n": "nominal", "nominal": "nominal",
             "h": "high", "high": "high"}
        out = series.astype(str).str.strip().str.lower().map(m)
        return out.fillna("unknown").astype(object)
    num = pd.to_numeric(series, errors="coerce")  # MODIS: 0-100
    out = np.select([num < 30, num < 80, num >= 80], ["low", "nominal", "high"],
                    default="unknown")
    return pd.Series(out, index=series.index, dtype=object)


def normalize_firms(raw: pd.DataFrame) -> pd.DataFrame:
    """Convert a raw FIRMS CSV (MODIS or VIIRS) to the common schema."""
    df = raw.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    sensor = detect_sensor(df.columns)
    if sensor is None:
        raise ValueError("Not a FIRMS MODIS/VIIRS file (no 'brightness'/'bright_ti4' column).")
    missing = {"latitude", "longitude", "acq_date"} - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    n = len(df)
    nan = pd.Series(np.nan, index=df.index)
    out = pd.DataFrame({
        "sensor": sensor,
        "date": pd.to_datetime(df["acq_date"], errors="coerce"),
        "time": pd.to_numeric(df.get("acq_time", nan), errors="coerce").fillna(-1).astype("int32"),
        "lat": pd.to_numeric(df["latitude"], errors="coerce").astype("float32"),
        "lon": pd.to_numeric(df["longitude"], errors="coerce").astype("float32"),
        "frp": pd.to_numeric(df.get("frp", nan), errors="coerce").astype("float32"),
        "type": pd.to_numeric(df.get("type", nan), errors="coerce"),
        "confidence": (_confidence_level(df["confidence"], sensor)
                       if "confidence" in df.columns else "unknown"),
    })
    out = out.dropna(subset=["date", "lat", "lon"]).reset_index(drop=True)
    return out


def read_csv_bytes(data: bytes) -> pd.DataFrame:
    return normalize_firms(pd.read_csv(io.BytesIO(data), low_memory=False))


def combine(frames: list[pd.DataFrame], key: str, kind: str) -> pd.DataFrame:
    """Concatenate normalised frames, drop duplicate detections, tag provenance."""
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset=["sensor", "date", "time", "lat", "lon"])
    df["sensor"] = df["sensor"].astype("category")
    df.attrs["key"] = key
    df.attrs["kind"] = kind  # "real" (NASA FIRMS files) or "demo" (synthetic)
    return df.reset_index(drop=True)


def load_folder(folder: str):
    """Load every *.csv in a folder. Returns (df, skipped_files)."""
    frames, skipped, names = [], [], []
    for path in sorted(glob.glob(os.path.join(folder, "*.csv"))):
        try:
            frames.append(normalize_firms(pd.read_csv(path, low_memory=False)))
            names.append(f"{os.path.basename(path)}:{os.path.getsize(path)}")
        except Exception as exc:  # noqa: BLE001
            skipped.append(f"{os.path.basename(path)} ({exc})")
    return combine(frames, "local|" + "|".join(names), "real"), skipped


def filter_df(df: pd.DataFrame, min_conf: str = "nominal", bbox=None,
              vegetation_only: bool = False) -> pd.DataFrame:
    """bbox = (west, south, east, north) or None."""
    if df.empty:
        return df
    lvl = df["confidence"].map(CONF_ORDER).fillna(1)
    mask = lvl >= CONF_ORDER[min_conf]
    if bbox:
        w, s, e, n = bbox
        mask &= df["lon"].between(w, e) & df["lat"].between(s, n)
    if vegetation_only and df["type"].notna().any():
        mask &= df["type"].fillna(0).eq(0)
    return df[mask]


# --------------------------------------------------------------------------
# Monthly series + harmonisation
# --------------------------------------------------------------------------
def monthly_counts(df: pd.DataFrame, metric: str = "cells") -> pd.DataFrame:
    """Monthly activity per sensor (columns MODIS, VIIRS; NaN = sensor not operating/loaded).

    metric='cells'      -> unique (day, 0.1-degree cell) per sensor. Reduces the
                           resolution bias between 1 km MODIS and 375 m VIIRS pixels.
    metric='detections' -> raw detection count.
    """
    if df.empty:
        return pd.DataFrame(columns=["MODIS", "VIIRS"])
    d = df[["sensor", "date", "lat", "lon"]].copy()
    d["sensor"] = d["sensor"].astype(str)
    if metric == "cells":
        d["cy"] = np.floor(d["lat"] / CELL_DEG).astype("int32")
        d["cx"] = np.floor(d["lon"] / CELL_DEG).astype("int32")
        d = d.drop_duplicates(["sensor", "date", "cy", "cx"])
    d["month"] = d["date"].dt.to_period("M").dt.to_timestamp()
    g = d.groupby(["month", "sensor"]).size().unstack("sensor")
    result = {}
    for s in ("MODIS", "VIIRS"):
        if s not in g.columns:
            continue
        first = d.loc[d["sensor"] == s, "date"].min()
        start = first.to_period("M").to_timestamp()
        if first.day != 1:  # first month only partly covered
            start = start + pd.offsets.MonthBegin(1)
        idx = pd.date_range(start, g.index.max(), freq="MS")
        result[s] = g[s].reindex(idx).fillna(0)
    out = pd.DataFrame(result)
    for s in ("MODIS", "VIIRS"):
        if s not in out:
            out[s] = np.nan
    out = out[["MODIS", "VIIRS"]].sort_index()
    out.index.name = "month"
    return out


@dataclass
class Calibration:
    global_ratio: float          # median VIIRS/MODIS over overlap months
    by_month: pd.Series          # calendar-month ratios (index 1..12)
    n_overlap: int               # months used
    spearman: float              # rank correlation, scaled MODIS vs VIIRS (in-sample)
    median_abs_pct_err: float    # median |scaled MODIS - VIIRS| / VIIRS in % (in-sample)


def calibrate(monthly: pd.DataFrame, min_overlap: int = 12) -> Calibration | None:
    both = monthly.dropna(subset=["MODIS", "VIIRS"])
    both = both[(both["MODIS"] > 0) & (both["VIIRS"] > 0)]
    if len(both) < min_overlap:
        return None
    ratio = both["VIIRS"] / both["MODIS"]
    g = float(ratio.median())
    per = ratio.groupby(ratio.index.month).median()
    cnt = ratio.groupby(ratio.index.month).size()
    per = per.where(cnt >= 3, g).reindex(range(1, 13)).fillna(g)
    scaled = both["MODIS"] * both.index.month.map(per).to_numpy()
    rho = float(scaled.rank().corr(both["VIIRS"].rank()))
    err = float(((scaled - both["VIIRS"]).abs() / both["VIIRS"]).median() * 100)
    return Calibration(g, per, len(both), rho, err)


def harmonize(monthly: pd.DataFrame, calib: Calibration | None) -> pd.DataFrame:
    """One continuous VIIRS-equivalent monthly series.

    VIIRS months use observed VIIRS; earlier MODIS-only months are MODIS x ratio.
    """
    rows = []
    for ts, r in monthly.iterrows():
        if pd.notna(r["VIIRS"]):
            rows.append((ts, r["VIIRS"], "VIIRS (observed)"))
        elif pd.notna(r["MODIS"]) and calib is not None:
            rows.append((ts, r["MODIS"] * calib.by_month[ts.month], "MODIS (scaled to VIIRS)"))
        elif pd.notna(r["MODIS"]):
            rows.append((ts, r["MODIS"], "MODIS (uncalibrated)"))
    out = pd.DataFrame(rows, columns=["month", "value", "basis"]).set_index("month")
    return out


def baseline_by_month(s: pd.Series) -> pd.DataFrame:
    g = s.dropna().groupby(s.dropna().index.month)
    b = pd.DataFrame({"median": g.median(), "q1": g.quantile(0.25),
                      "q3": g.quantile(0.75), "min": g.min(), "max": g.max(),
                      "years": g.size()})
    return b.reindex(range(1, 13))


def anomaly_table(s: pd.Series, min_other_years: int = 5, min_count: float = 10) -> pd.DataFrame:
    """Compare each month with the same calendar month in all OTHER years.

    robust_z = (value - median) / (1.4826 * MAD, at least 1). Heuristic flags:
    'unusually high' z>=2, ratio>=1.5, value>=min_count; 'unusually low' z<=-2, ratio<=0.5.
    """
    s = s.dropna()
    rows = []
    for _, grp in s.groupby(s.index.month):
        for ts, val in grp.items():
            others = grp.drop(ts).to_numpy(dtype=float)
            if len(others) < min_other_years:
                rows.append((ts, val, np.nan, np.nan, np.nan, np.nan, len(others), "insufficient history"))
                continue
            med = float(np.median(others))
            mad = float(np.median(np.abs(others - med))) * 1.4826
            z = (val - med) / max(mad, 1.0)
            ratio = val / med if med > 0 else np.nan
            pct = float((others < val).mean() * 100)
            flag = "normal"
            if z >= 2 and val >= min_count and (np.isnan(ratio) or ratio >= 1.5):
                flag = "unusually high"
            elif z <= -2 and not np.isnan(ratio) and ratio <= 0.5:
                flag = "unusually low"
            rows.append((ts, val, med, ratio, z, pct, len(others), flag))
    out = pd.DataFrame(rows, columns=["month", "value", "median_other_years", "ratio_to_median",
                                      "robust_z", "percentile", "other_years", "flag"])
    return out.sort_values("month").set_index("month")
