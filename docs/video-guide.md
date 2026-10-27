# Video guide for the candidate

Record one unlisted YouTube video. Keep it under 10 minutes, with a clear break between the two parts. Speak in your own words and verify every metric against the deployed app before recording. This guide is preparation; it is not the submitted video.

## Part 1 — customer presentation (about 4 minutes 30 seconds)

1. **Problem (0:00–0:35).** A day ahead buyer needs a view of wind generation that reflects only the forecasts available when the purchase decision was made. Later revisions can give a misleading picture of what the team knew.
2. **Set the moment (0:35–1:15).** Open Decision replay. Choose 15 January 2026 at 12:00 UK time. Point out that delivery is 16 January and that noon is a user-selected assumption, not a market deadline.
3. **Show the day (1:15–2:35).** Explain the hourly green forecast and half-hourly grey outturn. The grey series is retrospective and was not available to the buyer. Open the period table and point to one publication timestamp, forecast, outturn, and signed difference.
4. **Show the month (2:35–3:45).** Open January accuracy. Explain mean absolute difference, signed bias, overforecast frequency, and the matched count. Change the decision time and show how the comparison updates.
5. **Close (3:45–4:30).** Say the pilot makes the timing and historical forecast gap visible. It does not calculate purchase volume because consumer demand, other generation, and prices are outside the supplied data.

## Part 2 — technical review (about 4 minutes 30 seconds)

1. **Architecture (4:30–5:20).** Show the React frontend, FastAPI backend, and fixed Elexon snapshot. Docker Compose runs both locally; the public deployment serves `/` and `/api` together.
2. **Import and provenance (5:20–6:10).** Show `backend/ingest.py`, the two source endpoint paths, bounded retries, coverage checks, and source URLs/retrieval time in the snapshot.
3. **Core algorithm (6:10–7:15).** Show `backend/analysis.py`: for each delivery timestamp, use the latest forecast whose `publishTime` is at or before `as_of`; match actuals by exact `startTime`. No later forecast or interpolated half-hour enters the metrics.
4. **Metrics and limits (7:15–8:05).** Explain error as forecast minus outturn, averages over matched records, and why coverage is displayed. Note the hourly forecast versus 30-minute average outturn limitation.
5. **Quality and handoff (8:05–9:00).** Show the timing and boundary tests, CI checks, health endpoint, README startup steps, and public links. Leave time to finish clearly before 10:00.

## Before submitting

- Set YouTube visibility to **Unlisted**, not Private.
- Confirm the final duration is at most 10:00 and both parts are present.
- Open the YouTube link, deployed app, and public GitHub repo in an incognito window.
- Submit the form only after those checks pass.
