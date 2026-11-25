#!/usr/bin/env python3
"""Exploratory single-change-point scan of Kyiv school-window alert outcomes.

This is descriptive, not a causal test. The maximum over many candidate split
dates is selected on the same data, so the apparent split is optimistic and
must not be interpreted as a formal p-value.
"""
import csv, json, math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "kyiv_school_daily.csv"
OUTPUT = ROOT / "kyiv_regime_change_diagnostic.json"
THRESHOLDS = (60, 120, 180)
MIN_SEGMENT_DAYS = 180

def bernoulli_entropy(events, days):
    if days == 0:
        return 0.0
    p = events / days
    if p <= 0 or p >= 1:
        return 0.0
    return -p * math.log(p) - (1-p) * math.log(1-p)

def main():
    with SOURCE.open(newline="", encoding="utf-8-sig") as f:
        rows = sorted(csv.DictReader(f), key=lambda r: r["date"])
    result = {
        "source": SOURCE.name,
        "first_date": rows[0]["date"],
        "last_date": rows[-1]["date"],
        "rows": len(rows),
        "minimum_segment_days": MIN_SEGMENT_DAYS,
        "method": "For each threshold, scan one split across the full series subject to at least 180 days on each side, selecting the split with greatest reduction in Bernoulli entropy versus one overall rate.",
        "caveats": [
            "Exploratory scan only; the best date is selected after looking at all candidate dates, so the apparent change is optimistic.",
            "No formal significance test or multiple-testing correction is applied.",
            "Alert frequency is not attack frequency and cannot identify the cause of a change.",
            "Source snapshot ends 2026-10-19 and the final 2026 half-year is partial."
        ],
        "thresholds": {}
    }
    for t in THRESHOLDS:
        y = [int(float(r["school_window_min"]) >= t) for r in rows]
        n, total = len(y), sum(y)
        base = n * bernoulli_entropy(total, n)
        best = None
        for k in range(MIN_SEGMENT_DAYS, n-MIN_SEGMENT_DAYS+1):
            left, right = sum(y[:k]), total-sum(y[:k])
            gain = base - k*bernoulli_entropy(left, k) - (n-k)*bernoulli_entropy(right, n-k)
            if best is None or gain > best["entropy_gain_nats"]:
                best = {
                    "split_date": rows[k]["date"],
                    "left_days": k, "left_events": left,
                    "right_days": n-k, "right_events": right,
                    "left_rate": round(left/k, 6),
                    "right_rate": round(right/(n-k), 6),
                    "entropy_gain_nats": round(gain, 3)
                }
        groups = defaultdict(lambda: {"days": 0, "events": 0})
        for row, value in zip(rows, y):
            month = int(row["date"][5:7])
            segment = row["date"][:4] + ("-H1" if month <= 6 else "-H2")
            groups[segment]["days"] += 1
            groups[segment]["events"] += value
        for g in groups.values():
            g["rate"] = round(g["events"]/g["days"], 6)
        result["thresholds"][str(t)] = {
            "overall_days": n, "overall_events": total,
            "overall_rate": round(total/n, 6),
            "best_single_split": best,
            "half_year_rates": dict(sorted(groups.items()))
        }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
