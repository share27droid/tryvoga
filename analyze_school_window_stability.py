#!/usr/bin/env python3
"""Check whether rolling-30 vs rolling-90 baseline performance is stable by half-year.

The segmentation is descriptive only. Do not use future segments to select a
model for past dates. All daily predictions use strictly prior outcomes.
"""
import csv, json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "kyiv_school_daily.csv"
OUTPUT = ROOT / "kyiv_window_stability.json"
WARMUP = 365
THRESHOLDS = (60, 120, 180)
WINDOWS = (30, 90)

def main():
    with SOURCE.open(newline="", encoding="utf-8-sig") as f:
        rows = sorted(csv.DictReader(f), key=lambda r: r["date"])
    outcomes = {t: [int(float(r["school_window_min"]) >= t) for r in rows]
                for t in THRESHOLDS}
    groups = defaultdict(lambda: {"days": 0, "metrics": {}})
    for i in range(WARMUP, len(rows)):
        month = int(rows[i]["date"][5:7])
        segment = rows[i]["date"][:4] + ("-H1" if month <= 6 else "-H2")
        g = groups[segment]
        g["days"] += 1
        for t in THRESHOLDS:
            y = outcomes[t]
            m = g["metrics"].setdefault(str(t), {"events": 0, "sum_sq_30": 0.0, "sum_sq_90": 0.0})
            actual = y[i]
            m["events"] += actual
            for w in WINDOWS:
                p = sum(y[i-w:i]) / w
                m[f"sum_sq_{w}"] += (p-actual)**2
    result = {
        "source_last_date": rows[-1]["date"],
        "warmup_days": WARMUP,
        "segments": {},
        "caveat": "Half-year slices can have few events, especially at the 180-minute threshold. These diagnostics describe regime variation; they do not authorize selecting a model using future data."
    }
    for segment, g in sorted(groups.items()):
        result["segments"][segment] = {"days": g["days"], "metrics": {}}
        for t, m in g["metrics"].items():
            n = g["days"]
            b30 = m["sum_sq_30"] / n
            b90 = m["sum_sq_90"] / n
            result["segments"][segment]["metrics"][t] = {
                "events": m["events"],
                "brier_rolling30": round(b30, 6),
                "brier_rolling90": round(b90, 6),
                "rolling30_improvement_pct": round(100*(b90-b30)/b90, 2) if b90 else None
            }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
if __name__ == "__main__":
    main()
