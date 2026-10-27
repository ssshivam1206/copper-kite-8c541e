"""Reconstruct what was known at a January 2026 buying decision."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from statistics import mean
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")
FIRST_DECISION = date(2026, 1, 1)
LAST_DECISION = date(2026, 1, 31)


def utc_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("All source timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


def as_utc_string(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def metrics(rows: list[dict]) -> dict:
    errors = [row["forecastMw"] - row["actualMw"] for row in rows
              if row["forecastMw"] is not None and row["actualMw"] is not None]
    return {
        "matched": len(errors),
        "forecastAvailable": sum(row["forecastMw"] is not None for row in rows),
        "actualAvailable": sum(row["actualMw"] is not None for row in rows),
        "maeMw": round(mean(abs(error) for error in errors), 1) if errors else None,
        "biasMw": round(mean(errors), 1) if errors else None,
        "overforecastRate": round(sum(error > 0 for error in errors) / len(errors), 4) if errors else None,
    }


class DecisionData:
    def __init__(self, snapshot: dict):
        self.meta = snapshot["metadata"]
        self.forecasts: dict[str, list[tuple[datetime, float]]] = defaultdict(list)
        self.actuals: dict[str, float] = {}
        for row in snapshot["forecasts"]:
            self.forecasts[row["s"]].append((utc_datetime(row["p"]), float(row["mw"])))
        for entries in self.forecasts.values():
            entries.sort(key=lambda item: item[0])
        for row in snapshot["actuals"]:
            if row["s"] in self.actuals:
                raise ValueError(f"Duplicate actual timestamp in snapshot: {row['s']}")
            self.actuals[row["s"]] = float(row["mw"])

    def replay(self, as_of: datetime) -> dict:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must include a timezone")
        as_of = as_of.astimezone(timezone.utc)
        local = as_of.astimezone(LONDON)
        if not FIRST_DECISION <= local.date() <= LAST_DECISION:
            raise ValueError("Decision must be in January 2026, Europe/London")
        delivery = local.date() + timedelta(days=1)
        rows = []
        for slot in range(48):
            target_local = datetime.combine(delivery, time.min, LONDON) + timedelta(minutes=30 * slot)
            target_utc = target_local.astimezone(timezone.utc)
            key = as_utc_string(target_utc)
            selected = None
            for published, value in self.forecasts.get(key, []):
                if published <= as_of:
                    selected = (published, value)
                else:
                    break
            forecast = selected[1] if selected else None
            actual = self.actuals.get(key)
            rows.append({
                "startTime": key,
                "localTime": target_local.strftime("%H:%M"),
                "forecastMw": forecast,
                "actualMw": actual,
                "publishTime": as_utc_string(selected[0]) if selected else None,
                "errorMw": round(forecast - actual, 1) if forecast is not None and actual is not None else None,
            })
        return {
            "asOf": as_utc_string(as_of),
            "decisionDate": local.date().isoformat(),
            "deliveryDate": delivery.isoformat(),
            "timezone": "Europe/London",
            "unit": "MW",
            "rows": rows,
            "metrics": metrics(rows),
            "metadata": self.public_metadata(),
        }

    def summary(self, decision_time: time) -> dict:
        days = []
        all_rows = []
        for offset in range(31):
            decision_date = FIRST_DECISION + timedelta(days=offset)
            as_of = datetime.combine(decision_date, decision_time, LONDON)
            replay = self.replay(as_of)
            all_rows.extend(replay["rows"])
            days.append({
                "decisionDate": replay["decisionDate"],
                "deliveryDate": replay["deliveryDate"],
                **replay["metrics"],
            })
        return {
            "decisionTime": decision_time.strftime("%H:%M"),
            "timezone": "Europe/London",
            "unit": "MW",
            "days": days,
            "metrics": metrics(all_rows),
            "metadata": self.public_metadata(),
        }

    def public_metadata(self) -> dict:
        return {
            "retrievedAt": self.meta["retrievedAt"],
            "forecastRecords": self.meta["forecastRecords"],
            "actualRecords": self.meta["actualRecords"],
            "warnings": self.meta.get("warnings", []),
            "method": "Exact startTime matches only; no interpolation. Actuals were known afterward.",
        }
