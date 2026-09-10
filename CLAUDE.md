# Sleep Number Tools

Tools for downloading and analyzing sleep data from the SleepIQ API (Sleep Number beds).

## Setup

Credentials are stored in `credentials.env` (gitignored):
```
USERNAME=<email>
PASSWORD=<password>
```
**Important:** `load_dotenv` must use `override=True` because `USERNAME` collides with the Linux system environment variable.

## Usage

```bash
# Download all historical sleep data (default 12 months back)
python3 download_sleep_data.py [months_back]

# Run analysis and export reports
python3 analyze_wake_times.py
```

## Data Outputs (all under data/, gitignored)

- `data/sleep_data/{name}/{YYYY-MM}.json` — raw monthly API responses
- `data/sleep_slices/{name}/{YYYY-MM-DD}.json` — daily time-series sleep states
- `data/sleep_records.json` — consolidated flat JSON, queryable with jq
- `data/wake_times.csv` — flat CSV for spreadsheets/graphing
- `data/reports/monthly_summary.json` — monthly aggregates per sleeper

## API Details

- Base URL: `https://prod-api.sleepiq.sleepnumber.com/rest`
- Auth: `PUT /rest/login` returns a session `key`, passed as `_k` query param on all requests
- Key endpoints:
  - `GET /rest/sleeper` — list sleepers (ids, names, bed side)
  - `GET /rest/bed` — list beds
  - `GET /rest/sleepData?date=YYYY-MM-DD&interval=M1&sleeper={id}` — monthly bulk sleep data
  - `GET /rest/sleepSliceData?date=YYYY-MM-DD&sleeper={id}` — daily time-series

## Beds and Sleepers

- **Home bed** (PSE model, dual): Dan (left side), Ally (right side)
- Additional beds: Sienna (C2), Tristan (C2, K2)
- Data availability starts June 12, 2025

## Dependencies

Python 3, requests, python-dotenv, pandas
