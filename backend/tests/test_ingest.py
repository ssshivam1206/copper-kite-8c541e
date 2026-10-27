from io import BytesIO
from urllib.error import HTTPError

import pytest

import ingest


class Response(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def test_request_retries_rate_limit_then_succeeds(monkeypatch):
    attempts = []

    def fake_urlopen(request, timeout):
        attempts.append((request.full_url, timeout))
        if len(attempts) == 1:
            raise HTTPError(request.full_url, 429, "rate limited", {"Retry-After": "0"}, None)
        return Response(b'[{"generation": 100}]')

    monkeypatch.setattr(ingest, "urlopen", fake_urlopen)
    monkeypatch.setattr(ingest.time, "sleep", lambda _seconds: None)
    rows, url = ingest.request_rows("/datasets/WINDFOR/stream", {"publishDateTimeFrom": "2026-01-01T00:00:00Z"})
    assert len(attempts) == 2
    assert rows == [{"generation": 100}]
    assert "publishDateTimeFrom=" in url


def test_request_rejects_empty_response(monkeypatch):
    monkeypatch.setattr(ingest, "urlopen", lambda *_args, **_kwargs: Response(b"[]"))
    with pytest.raises(ValueError, match="Empty"):
        ingest.request_rows("/datasets/FUELHH/stream", {"fuelType": "WIND"})


@pytest.mark.parametrize("value", ["nan", "inf", -1])
def test_invalid_generation_is_rejected(value):
    with pytest.raises(ValueError, match="Invalid"):
        ingest.mw_value(value)


def test_conflicting_forecast_publication_fails_import(monkeypatch):
    def fake_rows(_path, _params):
        row = {"publishTime": "2025-12-30T03:30:00Z", "startTime": "2026-01-02T00:00:00Z"}
        return [{**row, "generation": 100}, {**row, "generation": 200}], "https://example.test"

    monkeypatch.setattr(ingest, "request_rows", fake_rows)
    with pytest.raises(ValueError, match="Conflicting forecast"):
        ingest.import_data()
