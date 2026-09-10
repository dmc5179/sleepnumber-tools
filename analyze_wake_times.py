#!/usr/bin/env python3
"""Analyze bed exit times from downloaded SleepIQ data.

Outputs:
  data/wake_times.csv               — flat CSV for spreadsheets/plotting
  data/sleep_records.json           — consolidated JSON for jq queries
  data/reports/monthly_summary.json — monthly aggregates for reporting
  stdout                            — consistency comparison report
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"


def extract_all_sessions():
    """Parse all monthly sleep data files and extract every session per sleeper."""
    sleep_data_dir = DATA_DIR / "sleep_data"
    if not sleep_data_dir.exists():
        print("No data directory found. Run download_sleep_data.py first.", file=sys.stderr)
        sys.exit(1)

    records = []
    for sleeper_dir in sorted(sleep_data_dir.iterdir()):
        if not sleeper_dir.is_dir():
            continue
        name = sleeper_dir.name.title()

        for month_file in sorted(sleeper_dir.glob("*.json")):
            with open(month_file) as f:
                data = json.load(f)

            for day in data.get("sleepData", []):
                sessions = day.get("sessions", [])
                if not sessions:
                    continue

                primary = None
                for s in sessions:
                    if s.get("longest"):
                        primary = s
                        break
                if primary is None:
                    primary = max(sessions, key=lambda s: s.get("totalSleepSessionTime", 0))

                try:
                    bed_exit = datetime.fromisoformat(primary["endDate"])
                    bed_enter = datetime.fromisoformat(primary["startDate"])
                except (KeyError, ValueError):
                    continue

                total_sec = primary.get("totalSleepSessionTime", 0)
                restful_sec = primary.get("restful", 0)
                restless_sec = primary.get("restless", 0)
                out_of_bed_sec = primary.get("outOfBed", 0)

                records.append({
                    "name": name,
                    "date": day["date"],
                    "day_of_week": datetime.strptime(day["date"], "%Y-%m-%d").strftime("%A"),
                    "month": day["date"][:7],
                    "bed_enter_ts": bed_enter.isoformat(),
                    "bed_exit_ts": bed_exit.isoformat(),
                    "sleep_time": bed_enter.strftime("%H:%M"),
                    "wake_time": bed_exit.strftime("%H:%M"),
                    "wake_hour_decimal": round(bed_exit.hour + bed_exit.minute / 60, 2),
                    "sleep_hour_decimal": round(bed_enter.hour + bed_enter.minute / 60 - (24 if bed_enter.hour < 12 else 0), 2),
                    "total_sleep_hours": round(total_sec / 3600, 2),
                    "restful_hours": round(restful_sec / 3600, 2),
                    "restless_hours": round(restless_sec / 3600, 2),
                    "out_of_bed_min": round(out_of_bed_sec / 60, 1),
                    "restful_pct": round(restful_sec / total_sec * 100, 1) if total_sec else 0,
                    "sleep_number": primary.get("sleepNumber"),
                    "sleep_score": primary.get("sleepQuotient"),
                    "heart_rate": primary.get("avgHeartRate"),
                    "resp_rate": primary.get("avgRespirationRate"),
                    "session_count": len(sessions),
                    "message": day.get("message", ""),
                })

    return records


def print_consistency_report(df):
    print("=" * 70)
    print("BED EXIT TIME CONSISTENCY REPORT")
    print("=" * 70)

    for name in sorted(df["name"].unique()):
        person = df[df["name"] == name].copy()
        person = person.sort_values("date")

        wake_hours = person["wake_hour_decimal"]
        mean_wake = wake_hours.mean()
        std_wake = wake_hours.std()
        mean_h = int(mean_wake)
        mean_m = int((mean_wake - mean_h) * 60)

        sleep_hours = person["total_sleep_hours"]

        print(f"\n{'─' * 50}")
        print(f"  {name}")
        print(f"{'─' * 50}")
        print(f"  Days of data:        {len(person)}")
        print(f"  Date range:          {person['date'].min()} to {person['date'].max()}")
        print(f"  Average wake time:   {mean_h:02d}:{mean_m:02d}")
        print(f"  Std deviation:       {std_wake * 60:.1f} minutes")
        print(f"  Avg sleep duration:  {sleep_hours.mean():.1f} hours")
        print(f"  Avg restful %:       {person['restful_pct'].mean():.1f}%")
        print(f"  Avg sleep score:     {person['sleep_score'].mean():.0f}")
        print(f"  Earliest wake:       {person.loc[wake_hours.idxmin(), 'wake_time']} ({person.loc[wake_hours.idxmin(), 'date']})")
        print(f"  Latest wake:         {person.loc[wake_hours.idxmax(), 'wake_time']} ({person.loc[wake_hours.idxmax(), 'date']})")

        print(f"\n  Wake time by day of week:")
        for dow in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
            dow_data = person[person["day_of_week"] == dow]["wake_hour_decimal"]
            if len(dow_data) == 0:
                continue
            avg = dow_data.mean()
            h, m = int(avg), int((avg - int(avg)) * 60)
            std = dow_data.std() * 60
            print(f"    {dow:12s}  avg {h:02d}:{m:02d}  ({std:4.1f} min spread, n={len(dow_data)})")

    if len(df["name"].unique()) >= 2:
        print(f"\n{'=' * 70}")
        print("CONSISTENCY COMPARISON")
        print(f"{'=' * 70}")
        for name in sorted(df["name"].unique()):
            person = df[df["name"] == name]
            std_min = person["wake_hour_decimal"].std() * 60
            print(f"  {name:15s}  std dev = {std_min:5.1f} min  (lower = more consistent)")

    print()


def build_monthly_summary(records):
    """Aggregate records into monthly summaries per sleeper."""
    df = pd.DataFrame(records)
    summaries = []

    for (name, month), group in df.groupby(["name", "month"]):
        summaries.append({
            "name": name,
            "month": month,
            "days": len(group),
            "avg_wake_time": _decimal_to_time(group["wake_hour_decimal"].mean()),
            "wake_std_dev_min": round(group["wake_hour_decimal"].std() * 60, 1),
            "avg_sleep_time": _decimal_to_time(group["sleep_hour_decimal"].mean() % 24),
            "avg_sleep_hours": round(group["total_sleep_hours"].mean(), 2),
            "avg_restful_pct": round(group["restful_pct"].mean(), 1),
            "avg_sleep_score": round(group["sleep_score"].dropna().mean(), 1) if group["sleep_score"].notna().any() else None,
            "avg_heart_rate": round(group["heart_rate"].dropna().mean(), 1) if group["heart_rate"].notna().any() else None,
        })

    return summaries


def _decimal_to_time(dec):
    dec = dec % 24
    h = int(dec)
    m = int((dec - h) * 60)
    return f"{h:02d}:{m:02d}"


def main():
    records = extract_all_sessions()
    if not records:
        print("No sleep data found. Run download_sleep_data.py first.", file=sys.stderr)
        sys.exit(1)

    df = pd.DataFrame(records)

    # Only report on Dan and Ally (the primary bed)
    primary = df[df["name"].isin(["Dan", "Ally"])]
    print_consistency_report(primary)

    # Export consolidated JSON (all sleepers — queryable with jq)
    json_path = DATA_DIR / "sleep_records.json"
    with open(json_path, "w") as f:
        json.dump(records, f, indent=2)
    print(f"JSON exported to {json_path}  ({len(records)} records)")

    # Export CSV (all sleepers)
    csv_path = DATA_DIR / "wake_times.csv"
    csv_cols = ["date", "name", "day_of_week", "month", "sleep_time", "wake_time",
                "total_sleep_hours", "restful_hours", "restless_hours", "restful_pct",
                "out_of_bed_min", "sleep_number", "sleep_score", "heart_rate", "resp_rate",
                "session_count"]
    df[csv_cols].sort_values(["date", "name"]).to_csv(csv_path, index=False)
    print(f"CSV exported to {csv_path}")

    # Export monthly summary JSON
    reports_dir = DATA_DIR / "reports"
    reports_dir.mkdir(exist_ok=True)
    monthly = build_monthly_summary(records)
    monthly_path = reports_dir / "monthly_summary.json"
    with open(monthly_path, "w") as f:
        json.dump(monthly, f, indent=2)
    print(f"Monthly summary exported to {monthly_path}")

    # Print jq usage hints
    print(f"""
Example jq queries on {json_path.name}:
  # Dan's wake times this month
  jq '[.[] | select(.name=="Dan" and .month=="2026-09")] | sort_by(.date) | .[] | "\\(.date) \\(.wake_time)"' data/sleep_records.json

  # Compare wake time consistency
  jq 'group_by(.name) | .[] | {{name: .[0].name, days: length, avg_wake: ([.[].wake_hour_decimal] | add / length), std_dev_min: (([.[].wake_hour_decimal] | (add / length) as $m | [.[] | (. - $m) * (. - $m)] | add / length | sqrt) * 60)}}' data/sleep_records.json

  # Weekly averages for Dan
  jq '[.[] | select(.name=="Dan")] | group_by(.day_of_week) | .[] | {{day: .[0].day_of_week, avg_wake: ([.[].wake_hour_decimal] | add / length | . * 100 | round / 100)}}' data/sleep_records.json
""")


if __name__ == "__main__":
    main()
