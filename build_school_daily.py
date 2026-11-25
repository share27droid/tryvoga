#!/usr/bin/env python3
"""Rebuild kyiv_school_daily.csv from the official Kyiv airAlert.json snapshot.
Times are interpreted as Kyiv local wall-clock times. School window is [08:30, 15:00).
Overlapping intervals are merged; unknown level/cause metadata is not imputed.
Run: python build_school_daily.py
"""
import csv, json
from datetime import datetime, date, time, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/"airAlert.json"
OUTPUT=ROOT/"kyiv_school_daily.csv"
START, END=time(8,30), time(15,0)
def stamp(v): return datetime.fromisoformat(v.replace("Z",""))
def known(v): return v not in (None,"","null","None")
def main():
    data=json.loads(SOURCE.read_text(encoding="utf-8"))
    intervals=[]
    for r in data:
        try: a,b=stamp(r["dateTimeStart"]),stamp(r["dateTimeEnd"])
        except (KeyError,TypeError,ValueError): continue
        if b>a: intervals.append((a,b,r.get("level"),r.get("cause")))
    if not intervals: raise SystemExit("No valid intervals")
    first=min(x[0].date() for x in intervals); last=max(x[1].date() for x in intervals)
    fields=["date","weekday","school_window_min","any_school_alert","alert_ge_60","alert_ge_120","alert_ge_180","overlapping_event_rows","raw_overlap_min","overlap_excess_min","classified_level_event_rows","unclassified_level_event_rows","known_cause_event_rows","unknown_cause_event_rows"]
    with OUTPUT.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); day=first
        while day<=last:
            lo=datetime.combine(day,START); hi=datetime.combine(day,END); hits=[]
            for a,b,level,cause in intervals:
                x,y=max(a,lo),min(b,hi)
                if y>x: hits.append((x,y,level,cause))
            merged=[]
            for x,y,_,_ in sorted(hits):
                if not merged or x>merged[-1][1]: merged.append([x,y])
                elif y>merged[-1][1]: merged[-1][1]=y
            minutes=sum((y-x).total_seconds()/60 for x,y in merged)
            raw=sum((y-x).total_seconds()/60 for x,y,_,_ in hits)
            cl=sum(known(x[2]) for x in hits); cc=sum(known(x[3]) for x in hits)
            w.writerow({"date":day.isoformat(),"weekday":day.strftime("%a"),"school_window_min":f"{minutes:.2f}","any_school_alert":int(minutes>0),"alert_ge_60":int(minutes>=60),"alert_ge_120":int(minutes>=120),"alert_ge_180":int(minutes>=180),"overlapping_event_rows":len(hits),"raw_overlap_min":f"{raw:.2f}","overlap_excess_min":f"{max(0,raw-minutes):.2f}","classified_level_event_rows":cl,"unclassified_level_event_rows":len(hits)-cl,"known_cause_event_rows":cc,"unknown_cause_event_rows":len(hits)-cc})
            day+=timedelta(days=1)
if __name__=="__main__": main()
