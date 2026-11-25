#!/usr/bin/env python3
"""Build leakage-safe lagged features for Kyiv school-window forecasts.

Run after build_school_daily.py:
    python build_school_daily.py
    python build_school_features.py

All prev_Nd_* features use only rows strictly before the target date.
The target day's labels/minutes are retained for retrospective evaluation only.
"""
import csv
from pathlib import Path

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/"kyiv_school_daily.csv"
OUTPUT=ROOT/"kyiv_school_features.csv"
WINDOWS=(1,3,7,14,30,90)
THRESHOLDS=(60,120,180)

def main():
    with SOURCE.open(newline="",encoding="utf-8-sig") as f:
        rows=list(csv.DictReader(f))
    rows.sort(key=lambda r:r["date"])
    fields=["date","weekday","school_window_min","alert_ge_60","alert_ge_120","alert_ge_180"]
    for n in WINDOWS:
        fields.extend([f"prev_{n}d_mean_min",f"prev_{n}d_ge60_rate",f"prev_{n}d_ge120_rate",f"prev_{n}d_ge180_rate"])
    with OUTPUT.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        for i,r in enumerate(rows):
            out={k:r[k] for k in fields[:6]}
            for n in WINDOWS:
                past=rows[max(0,i-n):i]
                out[f"prev_{n}d_mean_min"]=f"{sum(float(x['school_window_min']) for x in past)/len(past):.2f}" if past else ""
                for threshold in THRESHOLDS:
                    key=f"prev_{n}d_ge{threshold}_rate"
                    out[key]=f"{sum(int(float(x['school_window_min'])>=threshold) for x in past)/len(past):.4f}" if past else ""
            w.writerow(out)
if __name__=="__main__": main()
