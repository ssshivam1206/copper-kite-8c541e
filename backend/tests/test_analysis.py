from datetime import datetime, time, timezone

import pytest

from analysis import DecisionData, metrics


def fixture_data():
    return DecisionData({
        "metadata": {"retrievedAt": "2026-10-27T00:00:00Z", "forecastRecords": 5, "actualRecords": 3},
        "forecasts": [
            {"p": "2025-12-31T23:30:00Z", "s": "2026-01-02T00:00:00Z", "mw": 100},
            {"p": "2026-01-01T12:00:00Z", "s": "2026-01-02T00:00:00Z", "mw": 200},
            {"p": "2026-01-01T12:00:01Z", "s": "2026-01-02T00:00:00Z", "mw": 999},
            {"p": "2026-01-01T11:00:00Z", "s": "2026-01-02T01:00:00Z", "mw": 160},
            {"p": "2026-01-31T12:00:00Z", "s": "2026-02-01T00:00:00Z", "mw": 120},
        ],
        "actuals": [
            {"p": "2026-01-03T00:00:00Z", "s": "2026-01-02T00:00:00Z", "mw": 150},
            {"p": "2026-01-03T00:00:00Z", "s": "2026-01-02T00:30:00Z", "mw": 80},
            {"p": "2026-02-02T00:00:00Z", "s": "2026-02-01T00:00:00Z", "mw": 100},
        ],
    })


def test_latest_forecast_at_exact_cutoff_and_only_exact_matches():
    result = fixture_data().replay(datetime(2026, 1, 1, 12, tzinfo=timezone.utc))
    assert result["rows"][0]["forecastMw"] == 200
    assert result["rows"][0]["publishTime"] == "2026-01-01T12:00:00Z"
    assert result["rows"][0]["errorMw"] == 50
    assert result["rows"][1]["forecastMw"] is None
    assert result["rows"][1]["actualMw"] == 80
    assert result["metrics"] == {
        "matched": 1, "forecastAvailable": 2, "actualAvailable": 2,
        "maeMw": 50, "biasMw": 50, "overforecastRate": 1,
    }


def test_early_january_uses_previous_december_publication():
    result = fixture_data().replay(datetime(2026, 1, 1, 0, tzinfo=timezone.utc))
    assert result["rows"][0]["forecastMw"] == 100
    assert result["rows"][0]["errorMw"] == -50


def test_last_january_decision_delivers_on_february_first():
    result = fixture_data().replay(datetime(2026, 1, 31, 12, tzinfo=timezone.utc))
    assert result["deliveryDate"] == "2026-02-01"
    assert result["rows"][0]["forecastMw"] == 120
    assert result["rows"][0]["actualMw"] == 100


def test_invalid_and_naive_decision_times_are_rejected():
    data = fixture_data()
    with pytest.raises(ValueError, match="timezone"):
        data.replay(datetime(2026, 1, 1, 12))
    with pytest.raises(ValueError, match="January"):
        data.replay(datetime(2025, 12, 31, 12, tzinfo=timezone.utc))
    with pytest.raises(ValueError, match="January"):
        data.replay(datetime(2026, 2, 1, 12, tzinfo=timezone.utc))


def test_month_summary_uses_matched_points_not_daily_averages():
    result = fixture_data().summary(time(12, 0))
    assert len(result["days"]) == 31
    assert result["metrics"]["matched"] == 2
    assert result["metrics"]["maeMw"] == 35
    assert result["metrics"]["biasMw"] == 35
    assert result["metrics"]["overforecastRate"] == 1


def test_no_pairs_have_null_metrics_not_zero():
    result = metrics([{"forecastMw": None, "actualMw": 0}])
    assert result["matched"] == 0
    assert result["maeMw"] is None
    assert result["biasMw"] is None
    assert result["overforecastRate"] is None
