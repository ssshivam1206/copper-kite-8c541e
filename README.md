# January 2026 wind decision replay

A historical pilot for a Great Britain electricity buyer. Pick a decision time in January 2026 to see the wind forecast that was available for the next delivery day, then compare that forecast with subsequently published generation outturn. The comparison is in MW and is not a purchase recommendation.

## Start locally

```bash
docker compose up --build
```

Open `http://localhost:5173`. The API is at `http://localhost:8000/api/health`.

Without Docker, install `backend/requirements.txt`, run `uvicorn main:app --app-dir backend --reload`, then run `npm install && npm run dev` in `frontend/`.

## Repository map

- `backend/main.py`: FastAPI endpoints and request validation.
- `backend/analysis.py`: decision reconstruction and accuracy calculations.
- `backend/ingest.py`: reproducible Elexon import with retries and provenance.
- `backend/data/january_2026.json`: fixed historical snapshot used by the demo.
- `backend/tests/`: timing, boundary, and metric tests.
- `frontend/`: React and TypeScript dashboard.
- `docker-compose.yml` and Dockerfiles: local packaging.
- `.github/workflows/ci.yml`: backend and frontend checks.
- `docs/video-guide.md`: recording outline and submission gates.

## Data and method

The import uses only Elexon `WINDFOR/stream` forecasts and `FUELHH/stream` actual generation filtered to `WIND`. To refresh the snapshot:

```bash
python backend/ingest.py
```

The importer requests forecast publications from 30 December 2025 through 31 January 2026 and outturn for delivery days 2 January through 1 February 2026. It stores the source URLs, retrieval time, row counts, and any coverage warnings in the snapshot. Each request is checked; an empty or failed response aborts the import without replacing the existing snapshot.

For each delivery timestamp, the app chooses the forecast with the latest `publishTime` no later than the selected decision time. The actual value is matched only when `startTime` is identical. Forecast targets are hourly in the inspected January sample; outturn is half-hourly. The app displays both series at their native timestamps and computes metrics only from exact matches. It does not fill forecast gaps by interpolation.

Error is `forecast MW − outturn MW`. Positive values mean wind was overforecast. Mean absolute error and signed bias average over matched timestamps only. Overforecast frequency is the share of matched timestamps with positive error. Coverage is always shown alongside metrics. FUELHH is 30-minute average MW; WINDFOR forecast values may have a different interval meaning, so the result is labelled a forecast-versus-outturn difference, not a pure model accuracy score.

The app treats each selected January date as the decision date and the next UK calendar day as delivery. Times are displayed in `Europe/London`; the default 12:00 decision time is an app assumption, not an official market deadline. Actuals are shown retrospectively and were not known when the decision was made. The datasets describe Great Britain generation. They do not supply the utility's demand, other generation, or market prices, so the app cannot calculate how much power to buy.

## API

- `GET /api/replay?as_of=2026-01-15T12:00:00Z`: one decision and its next delivery day.
- `GET /api/summary?decision_time=12:00`: all January decisions at the same UK local time.
- `GET /api/health`: snapshot availability and retrieval time.

## Verification

```bash
python -m pip install -r backend/requirements-dev.txt
python -m pytest backend/tests -q
cd frontend && npm ci && npm run check && npm run build
```

## Deployment

The repository contains a Vercel Services configuration that serves the React frontend at `/` and FastAPI at `/api` on one URL. Deployment requires a Vercel account and production project connection. **Live app URL: pending deployment.**

## AI tool use

OpenAI Codex was used to help plan, implement, review, and test this assignment. The candidate is responsible for checking the data interpretation, code, and presentation before submission.
