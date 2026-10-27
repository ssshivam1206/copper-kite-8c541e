"""Download only the two Elexon datasets in the challenge brief.

Usage: python backend/ingest.py
"""

from __future__ import annotations

import json
import math
import os
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = "https://data.elexon.co.uk/bmrs/api/v1"
OUTPUT = Path(__file__).parent / "data" / "january_2026.json"
START_PUBLICATION = date(2025, 12, 30)
END_PUBLICATION = date(2026, 2, 1)  # exclusive
START_DELIVERY = date(2026, 1, 2)
END_DELIVERY = date(2026, 2, 1)  # inclusive


def request_rows(path: str, params: dict[str, str]) -> tuple[list[dict], str]:
    url = f"{BASE}{path}?{urlencode(params)}"
    for attempt in range(4):
        try:
            request = Request(url, headers={"Accept": "application/json", "User-Agent": "wind-decision-replay/1.0"})
            with urlopen(request, timeout=30) as response:
                rows = json.load(response)
            if not isinstance(rows, list) or not rows:
                raise ValueError(f"Empty or malformed Elexon response: {url}")
            return rows, url
        except (HTTPError, URLError, TimeoutError) as error:
            retryable = not isinstance(error, HTTPError) or error.code in (429, 500, 502, 503, 504)
            if not retryable or attempt == 3:
                raise RuntimeError(f"Elexon request failed: {url}: {error}") from error
            delay = min(2 ** attempt, 8)
            if isinstance(error, HTTPError) and error.headers.get("Retry-After", "").isdigit():
                delay = min(int(error.headers["Retry-After"]), 30)
            time.sleep(delay)
    raise AssertionError("unreachable")


def days(start: date, end_inclusive: date):
    current = start
    while current <= end_inclusive:
        yield current
        current += timedelta(days=1)


def iso_utc(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"Naive Elexon timestamp: {value}")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def mw_value(value) -> float:
    numeric = float(value)
    if not math.isfinite(numeric) or numeric < 0:
        raise ValueError(f"Invalid generation MW: {value}")
    return numeric


def import_data() -> dict:
    forecasts = {}
    actuals = {}
    urls = []
    warnings = []

    for day in days(START_PUBLICATION, END_PUBLICATION - timedelta(days=1)):
        next_day = day + timedelta(days=1)
        rows, url = request_rows("/datasets/WINDFOR/stream", {
            "publishDateTimeFrom": f"{day}T00:00:00Z",
            "publishDateTimeTo": f"{next_day}T00:00:00Z",
        })
        urls.append(url)
        for row in rows:
            published = iso_utc(row["publishTime"])
            target = iso_utc(row["startTime"])
            value = mw_value(row["generation"])
            key = (published, target)
            previous = forecasts.get(key)
            if previous is not None and previous != value:
                raise ValueError(f"Conflicting forecast for {key}")
            forecasts[key] = value
        print(f"WINDFOR {day}: {len(rows)} rows", flush=True)

    for day in days(START_DELIVERY, END_DELIVERY):
        day_targets = set()
        rows, url = request_rows("/datasets/FUELHH/stream", {
            "settlementDateFrom": day.isoformat(),
            "settlementDateTo": day.isoformat(),
            "fuelType": "WIND",
        })
        urls.append(url)
        for row in rows:
            if row.get("fuelType") != "WIND":
                raise ValueError(f"Unexpected fuel type: {row.get('fuelType')}")
            target = iso_utc(row["startTime"])
            day_targets.add(target)
            published = iso_utc(row["publishTime"])
            value = mw_value(row["generation"])
            previous = actuals.get(target)
            if previous is None or published > previous[0]:
                actuals[target] = (published, value)
            elif published == previous[0] and value != previous[1]:
                raise ValueError(f"Conflicting actual at {target}")
        if len(day_targets) != 48:
            warnings.append(f"FUELHH {day}: expected 48 distinct half-hours, received {len(day_targets)}")
        print(f"FUELHH {day}: {len(rows)} rows", flush=True)

    forecast_rows = [{"p": published, "s": target, "mw": value}
                     for (published, target), value in sorted(forecasts.items())]
    actual_rows = [{"p": published, "s": target, "mw": value}
                   for target, (published, value) in sorted(actuals.items())]
    return {
        "metadata": {
            "retrievedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "sourceUrls": urls,
            "forecastRecords": len(forecast_rows),
            "actualRecords": len(actual_rows),
            "warnings": warnings,
        },
        "forecasts": forecast_rows,
        "actuals": actual_rows,
    }


if __name__ == "__main__":
    snapshot = import_data()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".json.tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(snapshot, stream, separators=(",", ":"), allow_nan=False)
    os.replace(temporary, OUTPUT)
    print(f"Wrote {OUTPUT}: {snapshot['metadata']['forecastRecords']} forecasts, "
          f"{snapshot['metadata']['actualRecords']} actuals", flush=True)
