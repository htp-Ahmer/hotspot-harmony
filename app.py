"""Hotspot Harmony - MODIS + VIIRS active-fire harmonisation (NASA Space Apps 2026)."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import demo_data
import firms_api
import hotspot_core as hc

st.set_page_config(page_title="Hotspot Harmony", page_icon="🔥", layout="wide")

DATA_DIR = Path(__file__).parent / "data"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
PRESETS = {"Punjab, Pakistan (approx. bounding box)": (69.3, 27.7, 75.4, 34.0),
           "All loaded data": None, "Custom bounding box": "custom"}
ORANGE, BLUE, GREY = "#FF6B2C", "#4DA3FF", "#8FA3C4"
LAYOUT = dict(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
              margin=dict(l=10, r=10, t=50, b=10), legend=dict(orientation="h", y=-0.2))

st.markdown("""
<style>
.block-container {padding-top: 1.5rem; max-width: 1400px;}
div[data-testid="stMetric"] {background:#141E33; border:1px solid #23314f; border-radius:12px; padding:12px 16px;}
.hh-banner {padding:10px 14px; border-radius:10px; margin-bottom:12px; font-size:0.95rem;}
.hh-real {background:#10301f; border:1px solid #1f6b3f;}
.hh-demo {background:#3a1d12; border:2px solid #FF6B2C;}
@media (max-width: 640px) {h1 {font-size:1.6rem !important;} .block-container {padding:1rem 0.8rem;}}
</style>""", unsafe_allow_html=True)


def show(fig):
    try:
        st.plotly_chart(fig, width="stretch")
    except TypeError:  # older Streamlit
        st.plotly_chart(fig, use_container_width=True)


def show_df(df, **kw):
    try:
        st.dataframe(df, width="stretch", **kw)
    except TypeError:
        st.dataframe(df, use_container_width=True, **kw)


# ------------------------------------------------------------------ data loading
@st.cache_data(show_spinner="Reading FIRMS files…", hash_funcs={Path: str})
def _load_local(folder: str, signature: tuple):
    return hc.load_folder(folder)


def _sig(folder: Path):
    return tuple((p.name, p.stat().st_size, int(p.stat().st_mtime)) for p in sorted(folder.glob("*.csv")))


def sidebar_data():
    st.sidebar.title("🔥 Hotspot Harmony")
    st.sidebar.caption("MODIS + VIIRS active-fire harmonisation")
    local = sorted(DATA_DIR.glob("*.csv")) if DATA_DIR.exists() else []
    modes = ["Local CSV files (data/ folder)", "Upload CSV files",
             "NASA FIRMS API (MAP_KEY)", "Demo data (SYNTHETIC - not NASA)"]
    mode = st.sidebar.radio("Data source", modes, index=0 if local else 1)
    if mode == modes[0]:
        if not local:
            st.sidebar.warning("No CSV files in data/ yet.")
            return None
        df, skipped = _load_local(str(DATA_DIR), _sig(DATA_DIR))
        for s in skipped:
            st.sidebar.warning(f"Skipped: {s}")
        return df if len(df) else None
    if mode == modes[1]:
        ups = st.sidebar.file_uploader("FIRMS MODIS / VIIRS CSV files", type="csv",
                                       accept_multiple_files=True)
        if not ups:
            return None
        key = "up|" + "|".join(f"{u.name}:{u.size}" for u in ups)
        if st.session_state.get("up_key") != key:
            frames = []
            for u in ups:
                try:
                    frames.append(hc.read_csv_bytes(u.getvalue()))
                except Exception as exc:  # noqa: BLE001
                    st.sidebar.warning(f"Skipped {u.name}: {exc}")
            st.session_state["up_key"] = key
            st.session_state["up_df"] = hc.combine(frames, key, "real") if frames else None
        return st.session_state.get("up_df")
    if mode == modes[2]:
        with st.sidebar.expander("Fetch from FIRMS API", expanded=True):
            st.caption("Free MAP_KEY: firms.modaps.eosdis.nasa.gov/api/map_key/ · 5 days per request, "
                       "so long ranges are slow. For multi-year history use the archive download (README).")
            key_in = st.text_input("MAP_KEY", type="password")
            c1, c2 = st.columns(2)
            start = c1.date_input("Start", date(2024, 1, 1))
            end = c2.date_input("End", date(2024, 12, 31))
            box = st.text_input("Bounding box W,S,E,N", "69.3,27.7,75.4,34.0")
            if st.button("Download MODIS + VIIRS") and key_in:
                try:
                    bbox = tuple(float(x) for x in box.split(","))
                    frames, bar = [], st.sidebar.progress(0.0)
                    for src in ("MODIS_SP", "VIIRS_SNPP_SP"):
                        raw = firms_api.fetch_area(key_in, src, bbox, start, end, progress=bar.progress)
                        if len(raw):
                            DATA_DIR.mkdir(exist_ok=True)
                            raw.to_csv(DATA_DIR / f"firms_api_{src}_{start}_{end}.csv", index=False)
                            frames.append(hc.normalize_firms(raw))
                    st.session_state["api_df"] = hc.combine(frames, f"api|{start}|{end}|{box}", "real")
                except Exception as exc:  # noqa: BLE001
                    st.sidebar.error(str(exc))
        return st.session_state.get("api_df")
    if "demo_df" not in st.session_state:
        st.session_state["demo_df"] = demo_data.make_demo()
    return st.session_state["demo_df"]


# ------------------------------------------------------------------ cached analysis
_H = {pd.DataFrame: lambda d: (d.attrs.get("key"), len(d))}


@st.cache_data(show_spinner="Harmonising sensors…", hash_funcs=_H)
def analyse(df, min_conf, bbox, veg, metric):
    f = hc.filter_df(df, min_conf, bbox, veg)
    monthly = hc.monthly_counts(f, metric)
    calib = hc.calibrate(monthly)
    harm = hc.harmonize(monthly, calib)
    return dict(monthly=monthly, calib=calib, harm=harm, rows=f["sensor"].astype(str).value_counts().to_dict(),
                last=f["date"].max() if len(f) else None, first=f["date"].min() if len(f) else None)


@st.cache_data(show_spinner="Preparing map…", hash_funcs=_H)
def map_points(df, min_conf, bbox, veg, year, month, sensors, cap=60000):
    f = hc.filter_df(df, min_conf, bbox, veg)
    f = f[(f["date"].dt.year == year) & (f["date"].dt.month == month) & f["sensor"].astype(str).isin(sensors)]
    n = len(f)
    return (f.sample(cap, random_state=1) if n > cap else f)[["lat", "lon", "frp", "sensor"]].assign(
        sensor=lambda d: d["sensor"].astype(str)), n


# ------------------------------------------------------------------ UI
df = sidebar_data()
st.title("🔥 Hotspot Harmony")
st.caption("One continuous burning-activity calendar from NASA FIRMS MODIS and VIIRS active-fire detections.")

if df is None or df.empty:
    st.info("**No data loaded yet.** Add NASA FIRMS CSV files (MODIS and VIIRS) to the `data/` folder, "
            "upload them in the sidebar, or fetch them with a FIRMS MAP_KEY. See README.md for the 5-minute steps. "
            "The sidebar also has a clearly-labelled synthetic demo mode for testing the interface only.")
    st.stop()

kind = df.attrs.get("kind", "real")
if kind == "demo":
    st.markdown('<div class="hh-banner hh-demo">⚠️ <b>SYNTHETIC DEMONSTRATION DATA - NOT NASA DATA.</b> '
                'Randomly generated to test the interface. Do not draw conclusions from anything shown.</div>',
                unsafe_allow_html=True)
else:
    st.markdown('<div class="hh-banner hh-real">✅ <b>Real NASA FIRMS data</b> loaded from your CSV files '
                '(MODIS and/or VIIRS active-fire detections).</div>', unsafe_allow_html=True)

with st.sidebar:
    st.markdown("---")
    st.subheader("Filters")
    preset = st.selectbox("Region", list(PRESETS), index=0)
    bbox = PRESETS[preset]
    if bbox == "custom":
        w = st.number_input("West", value=60.0); s = st.number_input("South", value=20.0)
        e = st.number_input("East", value=80.0); n = st.number_input("North", value=40.0)
        bbox = (w, s, e, n)
    min_conf = st.select_slider("Minimum confidence", ["low", "nominal", "high"], value="nominal")
    has_type = bool(df["type"].notna().any())
    veg = st.checkbox("Vegetation fires only (type 0)", value=False, disabled=not has_type,
                      help="Uses the FIRMS 'type' column when present (archive files).")
    metric_label = st.radio("Activity metric", ["Fire-cell-days (recommended)", "Raw detections"],
                            help="Fire-cell-days counts each 0.1° grid cell once per day and sensor, "
                                 "which reduces the pixel-size bias between MODIS (1 km) and VIIRS (375 m).")
    metric = "cells" if metric_label.startswith("Fire") else "detections"

res = analyse(df, min_conf, bbox, veg, metric)
h, calib, monthly = res["harm"], res["calib"], res["monthly"]
if h.empty:
    st.warning("No detections match the current filters. Widen the region or lower the confidence.")
    st.stop()
s = h["value"]
unit = "fire-cell-days" if metric == "cells" else "detections"
last_month = s.index.max()
partial_last = res["last"] is not None and res["last"] < last_month + pd.offsets.MonthEnd(0)

tab_over, tab_cmp, tab_anom, tab_map, tab_harm, tab_about = st.tabs(
    ["📅 Calendar", "📊 Compare to history", "🚨 Unusual periods", "🗺️ Map", "🔗 Harmonisation", "ℹ️ Methods & data"])

# ---- Calendar
with tab_over:
    years = sorted(s.index.year.unique())
    ann = s.groupby(s.index.year).sum()
    c = st.columns(4)
    c[0].metric("Period", f"{years[0]}–{years[-1]}")
    pk = s.idxmax()
    c[1].metric("Peak month", f"{MONTHS[pk.month - 1]} {pk.year}", f"{s.max():,.0f} {unit}", delta_color="off")
    c[2].metric("Peak year", f"{ann.idxmax()}", f"{ann.max():,.0f} {unit}", delta_color="off")
    c[3].metric("Detections loaded", f"{sum(res['rows'].values()):,}",
                " · ".join(f"{k} {v:,}" for k, v in res["rows"].items()), delta_color="off")
    grid = s.to_frame("v").assign(y=s.index.year, m=s.index.month).pivot(index="y", columns="m", values="v")
    grid = grid.reindex(columns=range(1, 13))
    fig = px.imshow(grid.values, x=MONTHS, y=grid.index.astype(str), aspect="auto",
                    color_continuous_scale="YlOrRd", labels=dict(color=unit))
    fig.update_layout(title="Burning activity calendar (harmonised, VIIRS-equivalent)", height=max(380, 22 * len(grid) + 120),
                      **{k: v for k, v in LAYOUT.items() if k != "legend"})
    fig.update_yaxes(autorange="reversed", type="category")
    show(fig)
    if partial_last:
        st.caption(f"⚠️ The latest month ({MONTHS[last_month.month - 1]} {last_month.year}) is incomplete "
                   f"(data end {res['last']:%d %b %Y}).")
    c1, c2 = st.columns(2)
    with c1:
        top = s.sort_values(ascending=False).head(10).rename("activity").reset_index()
        top["month"] = top["month"].dt.strftime("%b %Y")
        st.markdown("**Top 10 months**")
        show_df(top.merge(h["basis"].reset_index().assign(month=lambda d: d["month"].dt.strftime("%b %Y")),
                          on="month"), hide_index=True)
    with c2:
        st.markdown("**Annual totals**")
        a = go.Figure(go.Bar(x=ann.index.astype(str), y=ann.values, marker_color=ORANGE))
        a.update_layout(height=330, **LAYOUT)
        show(a)

# ---- Compare to history
with tab_cmp:
    years = sorted(s.index.year.unique())
    c1, c2 = st.columns(2)
    sel_y = c1.selectbox("Year", years[::-1], index=0)
    sel_m = c2.selectbox("Month", range(1, 13), index=last_month.month - 1, format_func=lambda m: MONTHS[m - 1])
    ts = pd.Timestamp(sel_y, sel_m, 1)
    base = hc.baseline_by_month(s)
    an = hc.anomaly_table(s)
    if ts in s.index:
        r = an.loc[ts]
        k = st.columns(4)
        k[0].metric(f"{MONTHS[sel_m - 1]} {sel_y}", f"{r['value']:,.0f}", unit, delta_color="off")
        k[1].metric("Median, other years", "n/a" if pd.isna(r["median_other_years"]) else f"{r['median_other_years']:,.0f}")
        k[2].metric("Ratio to median", "n/a" if pd.isna(r["ratio_to_median"]) else f"{r['ratio_to_median']:.2f}×")
        k[3].metric("Status", r["flag"])
        if ts == last_month and partial_last:
            st.warning("This month is still incomplete, so it will look lower than the final total.")
    else:
        st.info("No data for that month.")
    sub = s[s.index.month == sel_m]
    med = base.loc[sel_m, "median"]
    f1 = go.Figure(go.Bar(x=sub.index.year.astype(str), y=sub.values,
                          marker_color=[ORANGE if y == sel_y else GREY for y in sub.index.year]))
    f1.add_hline(y=med, line_dash="dash", line_color=BLUE, annotation_text=f"median {med:,.0f}")
    f1.update_layout(title=f"{MONTHS[sel_m - 1]} across all years", height=360, **LAYOUT)
    show(f1)
    yr = s[s.index.year == sel_y]
    f2 = go.Figure()
    f2.add_trace(go.Scatter(x=MONTHS, y=base["q3"], line=dict(width=0), showlegend=False, hoverinfo="skip"))
    f2.add_trace(go.Scatter(x=MONTHS, y=base["q1"], fill="tonexty", fillcolor="rgba(77,163,255,0.2)",
                            line=dict(width=0), name="Typical range (Q1–Q3)"))
    f2.add_trace(go.Scatter(x=MONTHS, y=base["median"], line=dict(color=BLUE, dash="dash"), name="Historical median"))
    f2.add_trace(go.Scatter(x=[MONTHS[m - 1] for m in yr.index.month], y=yr.values, mode="lines+markers",
                            line=dict(color=ORANGE, width=3), name=str(sel_y)))
    f2.update_layout(title=f"{sel_y} vs historical monthly median", height=380, **LAYOUT)
    show(f2)

# ---- Unusual periods
with tab_anom:
    an = hc.anomaly_table(s)
    st.caption("Each month is compared with the same calendar month in all other years (robust z-score from median/MAD). "
               "Flags are a transparent heuristic, not an official classification.")
    flags = st.multiselect("Show", ["unusually high", "unusually low"], default=["unusually high", "unusually low"])
    z = an.reset_index()
    fz = go.Figure()
    fz.add_trace(go.Scatter(x=z["month"], y=z["robust_z"], mode="markers",
                            marker=dict(color=[ORANGE if f == "unusually high" else BLUE if f == "unusually low" else GREY
                                               for f in z["flag"]], size=6), text=z["flag"], name="robust z"))
    fz.add_hline(y=2, line_dash="dot", line_color=ORANGE)
    fz.add_hline(y=-2, line_dash="dot", line_color=BLUE)
    fz.update_layout(title="Robust z-score by month", height=360, **LAYOUT)
    show(fz)
    tab = z[z["flag"].isin(flags)].sort_values("robust_z", ascending=False)
    tab["month"] = tab["month"].dt.strftime("%b %Y")
    show_df(tab.round(2), hide_index=True)
    st.download_button("Download harmonised monthly series (CSV)", h.reset_index().to_csv(index=False).encode(),
                       "hotspot_harmony_monthly.csv", "text/csv")

# ---- Map
with tab_map:
    years = sorted(s.index.year.unique())
    c1, c2, c3 = st.columns(3)
    my = c1.selectbox("Map year", years[::-1], index=0)
    mm = c2.selectbox("Map month", range(1, 13), index=last_month.month - 1, format_func=lambda m: MONTHS[m - 1])
    sens = c3.multiselect("Sensors", ["MODIS", "VIIRS"], default=["MODIS", "VIIRS"])
    pts, n_all = map_points(df, min_conf, bbox, veg, my, mm, tuple(sens))
    if pts.empty:
        st.info("No detections for that selection.")
    else:
        ctr = dict(lat=float(pts["lat"].mean()), lon=float(pts["lon"].mean()))
        fm = px.density_map(pts, lat="lat", lon="lon", radius=7, center=ctr, zoom=5,
                            map_style="carto-darkmatter", color_continuous_scale="YlOrRd")
        fm.update_layout(height=560, margin=dict(l=0, r=0, t=0, b=0))
        show(fm)
        st.caption(f"{n_all:,} detections in {MONTHS[mm - 1]} {my}" + (f" (showing a random sample of {len(pts):,})" if n_all > len(pts) else "") + ".")

# ---- Harmonisation
with tab_harm:
    st.markdown("**Raw sensors vs harmonised series**")
    fh = go.Figure()
    fh.add_trace(go.Scatter(x=monthly.index, y=monthly["MODIS"], name="MODIS (raw)", line=dict(color=GREY, width=1.5)))
    fh.add_trace(go.Scatter(x=monthly.index, y=monthly["VIIRS"], name="VIIRS (raw)", line=dict(color=BLUE, width=1.5)))
    fh.add_trace(go.Scatter(x=h.index, y=h["value"], name="Harmonised", line=dict(color=ORANGE, width=2.5)))
    fh.update_layout(height=400, yaxis_title=unit, **LAYOUT)
    show(fh)
    if calib is None:
        st.warning("Not enough months with both sensors (≥12) to calibrate. Load both MODIS and VIIRS for overlapping years "
                   "(VIIRS S-NPP starts in 2012). Showing uncalibrated data.")
    else:
        k = st.columns(4)
        k[0].metric("Overlap months used", calib.n_overlap)
        k[1].metric("Median VIIRS/MODIS ratio", f"{calib.global_ratio:.2f}")
        k[2].metric("Rank correlation*", f"{calib.spearman:.2f}")
        k[3].metric("Median abs. error*", f"{calib.median_abs_pct_err:.0f}%")
        st.caption("*In-sample check on the overlap months used to calibrate (not independent validation).")
        both = monthly.dropna()
        sc = px.scatter(both, x="MODIS", y="VIIRS", labels=dict(MODIS=f"MODIS {unit}", VIIRS=f"VIIRS {unit}"))
        sc.update_traces(marker=dict(color=ORANGE))
        sc.update_layout(title="Overlap months: VIIRS vs MODIS", height=360, **LAYOUT)
        show(sc)
        show_df(calib.by_month.rename("VIIRS/MODIS ratio").round(2).rename_axis("calendar month")
                .rename(index=lambda m: MONTHS[m - 1]).to_frame().T)

# ---- About
with tab_about:
    st.markdown("""
### How the harmonisation works
1. **Read** NASA FIRMS MODIS and VIIRS active-fire CSVs and convert them to one schema
   (MODIS confidence 0–100 → low/nominal/high; VIIRS l/n/h).
2. **Count** monthly activity per sensor. The recommended metric counts each 0.1° grid cell once per day per sensor
   ("fire-cell-days"), because VIIRS (375 m) sees many more detections than MODIS (1 km) for the same fire.
3. **Calibrate** on the months where both sensors operate (VIIRS S-NPP data begin in 2012): median VIIRS/MODIS ratio per calendar month.
4. **Harmonise:** use observed VIIRS where available; earlier MODIS-only months are MODIS × ratio → one VIIRS-equivalent record.
5. **Compare** each month with the same calendar month in other years (median, quartiles, robust z-score) to flag unusual periods.

### Data
- NASA FIRMS (LANCE/EOSDIS): <https://firms.modaps.eosdis.nasa.gov/> · downloads: <https://firms.modaps.eosdis.nasa.gov/download/> · API: <https://firms.modaps.eosdis.nasa.gov/api/>
- The app shows **only the files you load**. Synthetic demo mode is labelled and exists to test the interface.

### Limitations
- Active-fire detections are not burned area or fire size; cloud, overpass time and sensor differences affect counts.
- The ratio calibration is a simple, transparent approach and is checked only in-sample.
- Anomaly flags are heuristic thresholds (|robust z| ≥ 2 plus a ratio rule), not an official product.
- Results depend on the region, confidence filter and date coverage of the loaded files.

*Built by Muhammad Ahmar (team "MODIS Meets VIIRS") for the 2026 NASA Space Apps Challenge. Not affiliated with or endorsed by NASA.*
""")
