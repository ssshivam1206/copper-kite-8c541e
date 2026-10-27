from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health_and_replay_with_real_snapshot():
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["snapshot"]["actualRecords"] == 1488
    replay = client.get("/api/replay", params={"as_of": "2026-01-15T12:00:00Z"})
    assert replay.status_code == 200
    body = replay.json()
    assert body["deliveryDate"] == "2026-01-16"
    assert len(body["rows"]) == 48
    assert body["metrics"]["matched"] > 0
    assert all(row["publishTime"] <= body["asOf"] for row in body["rows"] if row["publishTime"])


def test_api_rejects_out_of_range_and_naive_dates():
    assert client.get("/api/replay", params={"as_of": "2026-02-01T12:00:00Z"}).status_code == 422
    assert client.get("/api/replay", params={"as_of": "2026-01-15T12:00:00"}).status_code == 422
    assert client.get("/api/summary", params={"decision_time": "25:00"}).status_code == 422
