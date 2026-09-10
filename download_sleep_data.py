#!/usr/bin/env python3
"""Download historical sleep data from the SleepIQ API for all sleepers."""

import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

from sleepnumber_client import SleepNumberClient

DATA_DIR = Path(__file__).parent / "data"


def months_between(start_date, end_date):
    """Yield (year, month) tuples from start_date to end_date inclusive."""
    current = start_date.replace(day=1)
    while current <= end_date:
        yield current.year, current.month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)


def download_all(client, months_back=12):
    DATA_DIR.mkdir(exist_ok=True)

    print("Logging in...")
    login_data = client.login()
    print(f"  Logged in as user {login_data.get('userId', '?')}")

    print("\nFetching sleepers...")
    sleepers = client.get_sleepers()
    for s in sleepers:
        print(f"  {s['firstName']} (id={s['sleeperId']}, side={'left' if s.get('side') == 0 else 'right'})")

    print("\nFetching beds...")
    beds = client.get_beds()
    for b in beds:
        print(f"  Bed {b.get('name', '?')} (id={b['bedId']}, model={b.get('model', '?')})")

    sleeper_dir = DATA_DIR / "sleepers"
    sleeper_dir.mkdir(exist_ok=True)
    with open(sleeper_dir / "sleepers.json", "w") as f:
        json.dump(sleepers, f, indent=2)
    bed_dir = DATA_DIR / "beds"
    bed_dir.mkdir(exist_ok=True)
    with open(bed_dir / "beds.json", "w") as f:
        json.dump(beds, f, indent=2)

    today = date.today()
    start_date = today - timedelta(days=months_back * 30)

    for sleeper in sleepers:
        sid = sleeper["sleeperId"]
        name = sleeper["firstName"]
        print(f"\n{'='*60}")
        print(f"Downloading sleep data for {name} (id={sid})")
        print(f"{'='*60}")

        sleeper_data_dir = DATA_DIR / "sleep_data" / name.lower()
        sleeper_data_dir.mkdir(parents=True, exist_ok=True)

        for year, month in months_between(start_date, today):
            month_str = f"{year}-{month:02d}"
            date_str = f"{year}-{month:02d}-01"
            out_file = sleeper_data_dir / f"{month_str}.json"

            if out_file.exists():
                print(f"  {month_str}: already downloaded, skipping")
                continue

            print(f"  {month_str}: fetching...", end=" ", flush=True)
            try:
                data = client.get_sleep_data(sid, date_str, interval="M1")
                with open(out_file, "w") as f:
                    json.dump(data, f, indent=2)

                day_count = 0
                session_count = 0
                if "sleepData" in data:
                    for day in data["sleepData"]:
                        day_count += 1
                        session_count += len(day.get("sessions", []))
                print(f"{day_count} days, {session_count} sessions")
            except Exception as e:
                print(f"ERROR: {e}")

            time.sleep(1)

    print(f"\n{'='*60}")
    print("Downloading daily sleep slice data (time-series)...")
    print(f"{'='*60}")

    for sleeper in sleepers:
        sid = sleeper["sleeperId"]
        name = sleeper["firstName"]
        slice_dir = DATA_DIR / "sleep_slices" / name.lower()
        slice_dir.mkdir(parents=True, exist_ok=True)

        sleeper_data_dir = DATA_DIR / "sleep_data" / name.lower()
        dates_with_data = set()
        for month_file in sorted(sleeper_data_dir.glob("*.json")):
            with open(month_file) as f:
                month_data = json.load(f)
            for day in month_data.get("sleepData", []):
                if day.get("sessions"):
                    dates_with_data.add(day["date"])

        print(f"\n  {name}: {len(dates_with_data)} days with sleep data")
        fetched = 0
        for d in sorted(dates_with_data):
            out_file = slice_dir / f"{d}.json"
            if out_file.exists():
                continue
            try:
                data = client.get_sleep_slice_data(sid, d)
                with open(out_file, "w") as f:
                    json.dump(data, f, indent=2)
                fetched += 1
                if fetched % 20 == 0:
                    print(f"    ...fetched {fetched} slice files")
                time.sleep(0.5)
            except Exception as e:
                print(f"    ERROR on {d}: {e}")
                time.sleep(2)

        print(f"    Done: fetched {fetched} new slice files")

    print(f"\nAll data saved to {DATA_DIR.resolve()}")


def main():
    load_dotenv("credentials.env", override=True)
    username = os.environ.get("USERNAME")
    password = os.environ.get("PASSWORD")
    if not username or not password:
        print("ERROR: Set USERNAME and PASSWORD in credentials.env", file=sys.stderr)
        sys.exit(1)

    months_back = 12
    if len(sys.argv) > 1:
        try:
            months_back = int(sys.argv[1])
        except ValueError:
            print(f"Usage: {sys.argv[0]} [months_back]", file=sys.stderr)
            sys.exit(1)

    client = SleepNumberClient(username, password)
    download_all(client, months_back)


if __name__ == "__main__":
    main()
