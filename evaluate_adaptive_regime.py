#!/usr/bin/env python3
"""Evaluate a simple regime-sensitive blend of rolling-30 and rolling-90 baselines.

Input: kyiv_window_predictions.csv (from backtest_school_windows.py)
Outputs: kyiv_adaptive_regime_predictions.csv and kyiv_adaptive_regime_summary.json

This is an exploratory benchmark, not a production forecast. The blend rule is
fixed in advance and uses only past-derived predictions:
  gap = abs(p30 - p90)
  w = clamp(0.25 + 4*gap, 0.25, 0.80)
  p_adaptive = w*p30 + (1-w)*p90
"""
import csv, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "kyiv_window_predictions.csv"
PRED = ROOT / "kyiv_adaptive_regime_predictions.csv"
SUMMARY = ROOT / "kyiv_adaptive_regime_summary.json"
THRESHOLDS = (60, 120, 180)

def main():
    with SOURCE.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit("No predictions found; run backtest_school_windows.py first.")
    out_fields = ["date"]
    for t in THRESHOLDS:
        out_fields += [f"actual_ge{t}", f"rolling30_ge{t}", f"rolling90_ge{t}",
                       f"abs_gap_ge{t}", f"adaptive_weight_ge{t}",
                       f"adaptive_probability_ge{t}"]
    sums = {t: {"events": 0, "brier30": 0.0, "brier90": 0.0, "brier_adaptive": 0.0}
            for t in THRESHOLDS}
    with PRED.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields)
        writer.writeheader()
        for row in rows:
            out = {"date": row["date"]}
            for t in THRESHOLDS:
                y = int(row[f"actual_ge{t}"])
                p30 = float(row[f"rolling30_ge{t}"])
                p90 = float(row[f"rolling90_ge{t}"])
                gap = abs(p30 - p90)
                weight = max(0.25, min(0.80, 0.25 + 4.0 * gap))
                p = weight * p30 + (1.0 - weight) * p90
                out.update({
                    f"actual_ge{t}": y,
                    f"rolling30_ge{t}": f"{p30:.6f}",
                    f"rolling90_ge{t}": f"{p90:.6f}",
                    f"abs_gap_ge{t}": f"{gap:.6f}",
                    f"adaptive_weight_ge{t}": f"{weight:.6f}",
                    f"adaptive_probability_ge{t}": f"{p:.6f}",
                })
                m = sums[t]
                m["events"] += y
                m["brier30"] += (p30-y)**2
                m["brier90"] += (p90-y)**2
                m["brier_adaptive"] += (p-y)**2
            writer.writerow(out)
    n = len(rows)
    summary = {
        "source": SOURCE.name,
        "source_first_date": rows[0]["date"],
        "source_last_date": rows[-1]["date"],
        "test_days": n,
        "method": "p_adaptive = w*p30 + (1-w)*p90; w = clamp(0.25 + 4*abs(p30-p90), 0.25, 0.80).",
        "metrics": {},
        "interpretation": "Exploratory regime-sensitive blend. It does not materially beat rolling-30 overall for 60- or 120-minute outcomes; a very small improvement appears for 180 minutes. This does not establish that strategy change caused the regime shift. No attack-weapon predictors are included.",
        "caveats": [
            "Historical snapshot ends 2026-10-19 and is not live.",
            "The 30-day baseline remains best on the aggregate common test period.",
            "The 180-minute threshold has few events; small Brier differences are unstable.",
            "Historical attack data with publication timestamps is needed to test whether weapon mix and daytime-wave features add predictive value without leakage."
        ]
    }
    for t, m in sums.items():
        summary["metrics"][str(t)] = {
            "event_count": m["events"],
            "brier_rolling30": round(m["brier30"]/n, 6),
            "brier_rolling90": round(m["brier90"]/n, 6),
            "brier_adaptive_regime_blend": round(m["brier_adaptive"]/n, 6)
        }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
