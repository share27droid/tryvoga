#!/usr/bin/env python3
"""Leakage-safe baseline backtest for Kyiv school-window alert duration.

Uses only the previous observations for each prediction. This is a benchmark,
not the four-model production forecast. Run after build_school_daily.py:
    python build_school_daily.py
    python backtest_school_baselines.py
"""
import csv, json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/"kyiv_school_daily.csv"
PRED=ROOT/"kyiv_baseline_predictions.csv"
SUMMARY=ROOT/"kyiv_baseline_backtest_summary.json"
THRESHOLDS=(60,120,180)
WARMUP=180
ROLLING=90

def brier(pred, actual):
    return sum((p-y)**2 for p,y in zip(pred,actual))/len(actual)

def main():
    with SOURCE.open(newline="",encoding="utf-8-sig") as f:
        rows=list(csv.DictReader(f))
    rows.sort(key=lambda r:r["date"])
    outcomes={t:[int(float(r["school_window_min"])>=t) for r in rows] for t in THRESHOLDS}
    fields=["date"]
    for t in THRESHOLDS:
        fields.extend([f"actual_ge{t}",f"expanding_rate_ge{t}",f"rolling90_rate_ge{t}"])
    predictions=[]
    for i in range(WARMUP,len(rows)):
        out={"date":rows[i]["date"]}
        for t in THRESHOLDS:
            y=outcomes[t]
            out[f"actual_ge{t}"]=y[i]
            out[f"expanding_rate_ge{t}"]=f"{sum(y[:i])/i:.6f}"
            past=y[max(0,i-ROLLING):i]
            out[f"rolling90_rate_ge{t}"]=f"{sum(past)/len(past):.6f}"
        predictions.append(out)
    with PRED.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(predictions)
    summary={"source_rows":len(rows),"first_date":rows[0]["date"],"last_date":rows[-1]["date"],"warmup_days":WARMUP,"test_days":len(predictions),"rolling_window_days":ROLLING,"metrics":{},"caveats":["Only Kyiv alert history is used; no national attack predictors are included.","Predictions use strictly earlier labels; the current date's outcome is never used as its own feature.","Brier score is evaluated on historical labels and does not establish operational safety.","The source snapshot ends on 2026-10-19 and is not a live feed."]}
    for t in THRESHOLDS:
        actual=[int(p[f"actual_ge{t}"]) for p in predictions]
        exp=[float(p[f"expanding_rate_ge{t}"]) for p in predictions]
        roll=[float(p[f"rolling90_rate_ge{t}"]) for p in predictions]
        summary["metrics"][str(t)]={"event_count":sum(actual),"observed_rate":round(sum(actual)/len(actual),6),"brier_expanding":round(brier(exp,actual),6),"brier_rolling90":round(brier(roll,actual),6),"brier_relative_improvement_pct":round(100*(brier(exp,actual)-brier(roll,actual))/brier(exp,actual),2)}
    SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
if __name__=="__main__":main()
