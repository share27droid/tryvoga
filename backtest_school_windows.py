#!/usr/bin/env python3
"""Common-period walk-forward comparison of rolling-frequency baselines.

Run from repository root after build_school_daily.py:
    python build_school_daily.py
    python backtest_school_windows.py

All models are evaluated on the same dates after a 365-day warm-up. No target-day
or future outcome is used to form a prediction. This is a benchmark, not a live
forecast or a safety decision system.
"""
import csv, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "kyiv_school_daily.csv"
PRED = ROOT / "kyiv_window_predictions.csv"
SUMMARY = ROOT / "kyiv_window_backtest_summary.json"
WARMUP = 365
WINDOWS = (30, 60, 90, 180, 365)
THRESHOLDS = (60, 120, 180)

def brier(probabilities, actual):
    return sum((p-y)**2 for p, y in zip(probabilities, actual)) / len(actual)

def main():
    with SOURCE.open(newline="", encoding="utf-8-sig") as f:
        rows = sorted(csv.DictReader(f), key=lambda r: r["date"])
    if len(rows) <= WARMUP:
        raise SystemExit(f"Need more than {WARMUP} daily rows; found {len(rows)}")
    outcomes = {t: [int(float(r["school_window_min"]) >= t) for r in rows]
                for t in THRESHOLDS}
    fields = ["date"]
    for t in THRESHOLDS:
        fields.append(f"actual_ge{t}")
        fields.extend(f"rolling{w}_ge{t}" for w in WINDOWS)
        fields.append(f"expanding_ge{t}")
    predictions = []
    for i in range(WARMUP, len(rows)):
        out = {"date": rows[i]["date"]}
        for t in THRESHOLDS:
            y = outcomes[t]
            out[f"actual_ge{t}"] = y[i]
            for w in WINDOWS:
                out[f"rolling{w}_ge{t}"] = f"{sum(y[i-w:i])/w:.6f}"
            out[f"expanding_ge{t}"] = f"{sum(y[:i])/i:.6f}"
        predictions.append(out)
    with PRED.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(predictions)
    summary = {
        "source_rows": len(rows), "first_date": rows[0]["date"],
        "last_date": rows[-1]["date"], "warmup_days": WARMUP,
        "test_start": rows[WARMUP]["date"], "test_days": len(predictions),
        "common_test_period": True, "rolling_windows_days": list(WINDOWS),
        "metrics": {},
        "caveats": [
            "All compared models are evaluated on the same dates, after a 365-day warm-up.",
            "Each prediction uses only outcomes strictly before its target date.",
            "Rolling-window selection may vary by threshold and time period; this is a historical benchmark, not a production forecast.",
            "Only Kyiv school-window alert history is used; no national attack predictors are included.",
            "The source snapshot ends on 2026-10-19 and is not a live feed.",
            "Historical Brier score does not establish operational safety; official alerts govern safety decisions."
        ]
    }
    for t in THRESHOLDS:
        actual = [int(p[f"actual_ge{t}"]) for p in predictions]
        count = sum(actual)
        metrics = {"event_count": count, "observed_rate": round(count/len(actual), 6),
                   "brier_expanding": round(brier([float(p[f"expanding_ge{t}"]) for p in predictions], actual), 6)}
        for w in WINDOWS:
            metrics[f"brier_rolling{w}"] = round(brier([float(p[f"rolling{w}_ge{t}"]) for p in predictions], actual), 6)
        summary["metrics"][str(t)] = metrics
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
if __name__ == "__main__":
    main()
