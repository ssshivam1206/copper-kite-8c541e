"""Read-only API for the historical January wind pilot."""

from __future__ import annotations

import json
import logging
from datetime import datetime, time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from analysis import DecisionData

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SNAPSHOT_PATH = Path(__file__).parent / "data" / "january_2026.json"


def load_data(path: Path = SNAPSHOT_PATH) -> DecisionData | None:
    if not path.exists():
        logger.warning("Snapshot unavailable: %s", path)
        return None
    with path.open(encoding="utf-8") as stream:
        return DecisionData(json.load(stream))


data = load_data()
app = FastAPI(title="Wind decision replay", version="1.0.0")


@app.exception_handler(ValueError)
async def value_error_handler(_request, error: ValueError):
    return JSONResponse(status_code=422, content={"detail": str(error)})


def require_data() -> DecisionData:
    if data is None:
        raise HTTPException(status_code=503, detail="Historical Elexon snapshot is not installed")
    return data


@app.get("/api/health")
async def health():
    if data is None:
        return JSONResponse(status_code=503, content={"status": "unavailable", "snapshot": None})
    return {"status": "ok", "snapshot": data.public_metadata()}


@app.get("/api/replay")
async def replay(as_of: datetime = Query(description="Timezone-aware ISO decision timestamp")):
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise HTTPException(status_code=422, detail="as_of must include a timezone")
    return require_data().replay(as_of)


@app.get("/api/summary")
async def summary(decision_time: str = Query(default="12:00", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")):
    return require_data().summary(time.fromisoformat(decision_time))
