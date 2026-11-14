import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import numpy as np
import hotspot_core as hc
import demo_data


def _setup():
    df = demo_data.make_demo()
    m = hc.monthly_counts(hc.filter_df(df, "nominal"), "cells")
    c = hc.calibrate(m)
    return df, m, c, hc.harmonize(m, c)


def test_schema_and_sensors():
    df = demo_data.make_demo()
    assert set(df["sensor"].astype(str)) == {"MODIS", "VIIRS"}
    assert df.attrs["kind"] == "demo"


def test_calibration_and_harmonize():
    _, m, c, h = _setup()
    assert c is not None and c.global_ratio > 0 and c.n_overlap >= 12
    assert h["value"].notna().all()
    assert (h["basis"] == "MODIS (scaled to VIIRS)").any() and (h["basis"] == "VIIRS (observed)").any()


def test_anomalies_run():
    _, _, _, h = _setup()
    a = hc.anomaly_table(h["value"])
    assert {"unusually high", "normal"} <= set(a["flag"]) | {"normal"}
    assert len(hc.baseline_by_month(h["value"])) == 12


if __name__ == "__main__":
    for f in (test_schema_and_sensors, test_calibration_and_harmonize, test_anomalies_run):
        f(); print("PASS", f.__name__)
    _, m, c, h = _setup()
    print(m.head(3)); print(m.tail(3)); print(c)
    print(hc.anomaly_table(h["value"])["flag"].value_counts())
