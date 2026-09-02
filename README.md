# Ambassador Portal

A web-based ambassador directory that dynamically syncs with a Google Sheet, built with
FastAPI, Jinja2, Tailwind CSS, Leaflet, and Chart.js.

## What it does

- **Live data sync** — pulls ambassador data from a Google Sheet (published as CSV) on a
  scheduled interval (default 15 min) via APScheduler, no manual redeploys needed.
- **Data cleaning pipeline** (`app/data.py`) — normalizes column names, strips whitespace,
  standardizes phone numbers, computes a per-record **data completeness score**, and flags
  incomplete records instead of hiding them.
- **Coverage map** — an interactive India choropleth (Leaflet) showing ambassador density
  per state, using a public India-states GeoJSON.
- **Searchable roster** — filter by name, brand, city, ambassador code, or state; also filter
  by profile type and sort any column (click a column header to sort, click again to reverse).
- **Analytics dashboard** — ambassadors by state, by profile type, and overall data-quality
  metrics (Chart.js).
- **Graceful fallback** — if no Google Sheet URL is configured, or the live fetch fails,
  the app automatically falls back to a bundled sample dataset so it never breaks.
- **Live sync status** — a "Synced Xm ago" indicator in the header (not just the footer) so
  it's always obvious the automation is running, plus a manual sync button.
- **Loading and error states** — the coverage map and analytics charts show a skeleton
  placeholder while loading and a friendly message instead of blank space if a fetch fails.
- **Debug endpoint** (`/api/debug`) — surfaces raw column names, row counts, and sample rows
  from the live sheet fetch, for diagnosing header/column mismatches quickly.

## Project structure

```
ambassador-portal/
├── app/
│   ├── main.py          # FastAPI app, routes, scheduler
│   ├── data.py           # Google Sheet ingestion + cleaning + analytics logic
│   ├── config.py         # env vars, state-name mapping, geojson URL
│   ├── templates/        # Jinja2 pages (home, roster, analytics)
│   └── static/           # CSS + JS (map, roster table, charts)
├── data/
│   └── sample_ambassadors.csv   # fallback dataset
├── requirements.txt
└── .env.example
```

## Running locally

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and set GOOGLE_SHEET_CSV_URL (see below) — or leave blank to use sample data

uvicorn app.main:app --reload
```

Visit http://127.0.0.1:8000

## Connecting your own Google Sheet

1. In Google Sheets: **File → Share → Publish to web**
2. Select the specific sheet/tab, choose **CSV**, click **Publish**
3. Copy the generated link into `GOOGLE_SHEET_CSV_URL` in your `.env` file
4. Make sure your sheet's header row matches (case-insensitive): `Sr. No.`, `Name`,
   `Brand Name`, `Billing Name`, `Ambassador Code`, `City`, `State`, `Contact Number`,
   `E-mail`, `Profile`

The app re-fetches automatically every `REFRESH_INTERVAL_MINUTES`, and there's also a
manual **Sync** button in the header that calls `/api/refresh` on demand.

## Deploying

Works on any platform that runs a Python web service (Render, Railway, Fly.io, or
Vercel's Python runtime). General steps:

1. Push this repo to GitHub
2. Create a new web service, set the start command to:
   `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Set `GOOGLE_SHEET_CSV_URL` and `REFRESH_INTERVAL_MINUTES` as environment variables

## Design decisions worth calling out

- **Data completeness scoring**: each record gets a % score based on how many of 6 key
  fields (name, brand, city, state, phone, email) are filled in. Records under 60% are
  flagged. This surfaces exactly the kind of gaps visible in the original sheet
  (missing phone numbers, blank cities) instead of hiding them.
- **Separation of ingestion vs. presentation**: `data.py` has zero knowledge of HTML/JSON
  — it just returns clean pandas-derived Python structures. `main.py` decides how to
  serve that (page vs API). This keeps the pipeline testable and reusable.
- **In-memory cache + background scheduler** instead of hitting Google Sheets on every
  page load — keeps the site fast and avoids rate limits, while still staying near-real-time.