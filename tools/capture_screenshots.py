"""Capture screenshots of the RUNNING app (real data loaded) for the slides.

1) Put FIRMS CSVs in data/ and run:  streamlit run app.py
2) In another terminal:             python tools/capture_screenshots.py
Needs:  pip install playwright  &&  playwright install chromium
"""
import pathlib
from playwright.sync_api import sync_playwright

OUT = pathlib.Path(__file__).resolve().parent.parent / "screenshots"
OUT.mkdir(exist_ok=True)
TABS = [("Calendar", "01_calendar"), ("Compare to history", "02_compare"),
        ("Unusual periods", "03_unusual"), ("Map", "04_map"), ("Harmonisation", "05_harmonisation")]

with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1500, "height": 900})
    page.goto("http://localhost:8501")
    page.wait_for_selector("[data-testid='stTabs']", timeout=60000)
    page.wait_for_timeout(4000)
    for label, name in TABS:
        page.get_by_role("tab", name=label).first.click()
        page.wait_for_timeout(3500)
        page.screenshot(path=str(OUT / f"{name}.png"))
        print("saved", name)
    b.close()
