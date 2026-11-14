# 🔥 Hotspot Harmony
Harmonising NASA FIRMS **MODIS** and **VIIRS** active-fire hotspots into one interactive burning-activity calendar.
NASA Space Apps Challenge 2026 · Challenge: *Harmonization of MODIS and VIIRS Hot Spots* · Team "MODIS Meets VIIRS" · Muhammad Ahmar

## Install (Windows 10 / macOS / Linux, Python 3.10+)
```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Get the real data (once)
1. Open https://firms.modaps.eosdis.nasa.gov/download/ and sign in (free).
2. Create a request for your area (e.g. Pakistan) and the longest period you want, in **CSV**, for:
   - **MODIS** (Collection 6.1, Standard Processing) - from 2000
   - **VIIRS S-NPP 375 m** (Standard Processing) - from 2012
   (menu names can change slightly; pick MODIS and VIIRS S-NPP archive products.)
3. Download the files FIRMS emails you and put the `.csv` files in `data/`.
4. `streamlit run app.py` - the app auto-detects MODIS vs VIIRS by column names.

Alternatives: upload CSVs from the sidebar, or fetch recent periods with a free FIRMS MAP_KEY
(https://firms.modaps.eosdis.nasa.gov/api/map_key/).

## Features
Burning-activity calendar (year × month heatmap) · peak months/years · current month vs historical median/quartiles ·
unusual-period detection (robust z-score) · MODIS+VIIRS harmonisation with calibration stats · density map ·
region/confidence filters · CSV export · dark responsive UI.

## Real data vs demo
The app only shows files you load. **Demo mode** (`demo_data.py`) generates **synthetic random data**, bannered in the UI,
for interface testing only. Do not use it for results.

## Test / screenshots
```bash
python tests/test_core.py                 # core logic checks (pandas/numpy only)
pip install -r requirements-dev.txt && playwright install chromium
python tools/capture_screenshots.py       # with the app running on real data -> screenshots/
node tools/build_deck.js                  # rebuilds the 7-slide PPTX with those screenshots
```

## Files
`app.py` UI · `hotspot_core.py` data/harmonisation logic · `firms_api.py` optional API download · `demo_data.py` synthetic test data.

## Method in brief
Monthly fire-cell-days (unique day × 0.1° cell per sensor) → VIIRS/MODIS ratio per calendar month on overlap months (2012+) →
VIIRS observed where available, MODIS×ratio before → compare each month with the same month in other years.
Limitations: counts are not burned area; calibration is in-sample only; flags are heuristic.

Data: NASA FIRMS (LANCE / EOSDIS). Not affiliated with or endorsed by NASA.
