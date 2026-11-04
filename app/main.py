"""Read-only digital twin API, plus minimal Prometheus-format metrics for Grafana."""
from datetime import datetime, timezone
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from redis import asyncio as aioredis
from redis.exceptions import RedisError

from app.config import MACHINE_ID, REDIS_URL, STALE_AFTER_SECONDS

app = FastAPI(title="Smart Industrial Digital Twin", version="1.0.0")

async def get_redis():
    client = aioredis.from_url(REDIS_URL, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


def project_twin(raw: dict, availability: str | None, count: int) -> dict:
    received = datetime.fromisoformat(raw["received_at"])
    age = max(0, (datetime.now(timezone.utc) - received).total_seconds())
    stale = age > STALE_AFTER_SECONDS
    connectivity = "OFFLINE" if availability == "offline" else ("STALE" if stale else "ONLINE")
    return {
        "machine_id": raw["machine_id"],
        "reported_mode": raw["reported_mode"],
        "temperature_c": float(raw["temperature_c"]),
        "vibration_mm_s": float(raw["vibration_mm_s"]),
        "health": raw["health"],
        "anomaly_score": float(raw["anomaly_score"]),
        "reason": raw["reason"],
        "connectivity": connectivity,
        "last_seen": raw["received_at"],
        "seconds_since_last_event": round(age, 1),
        "processed_events": count,
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready(redis_client=Depends(get_redis)):
    try:
        await redis_client.ping()
        return {"status": "ready"}
    except RedisError:
        raise HTTPException(status_code=503, detail="Redis not ready")


async def load_twin(redis_client):
    try:
        raw = await redis_client.hgetall(f"twin:{MACHINE_ID}")
        if not raw:
            return None
        availability = await redis_client.get(f"twin:{MACHINE_ID}:availability")
        count = int((await redis_client.get(f"twin:{MACHINE_ID}:count")) or 0)
        return project_twin(raw, availability, count)
    except RedisError:
        raise HTTPException(status_code=503, detail="Redis unavailable")


@app.get("/twin")
async def twin(redis_client=Depends(get_redis)):
    state = await load_twin(redis_client)
    if state is None:
        raise HTTPException(status_code=404, detail="No telemetry received yet")
    return state


@app.get("/alerts")
async def alerts(redis_client=Depends(get_redis)):
    state = await load_twin(redis_client)
    if state is None:
        return {"alerts": []}
    if state["health"] in {"WARNING", "FAULT"}:
        return {"alerts": [{"machine_id": MACHINE_ID, "health": state["health"], "reason": state["reason"], "connectivity": state["connectivity"]}]}
    return {"alerts": []}


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics(redis_client=Depends(get_redis)):
    """Prometheus scrape endpoint: only fixed metric names and numeric values."""
    state = await load_twin(redis_client)
    if state is None:
        state = {"temperature_c": 0, "vibration_mm_s": 0, "anomaly_score": 0, "processed_events": 0, "connectivity": "STALE", "health": "CALIBRATING"}
    names = {
        "twin_temperature_celsius": state["temperature_c"],
        "twin_vibration_mm_per_second": state["vibration_mm_s"],
        "twin_anomaly_score": state["anomaly_score"],
        "twin_processed_events_total": state["processed_events"],
        "twin_connected": int(state["connectivity"] == "ONLINE"),
        "twin_warning": int(state["health"] in {"WARNING", "FAULT"}),
    }
    return "\n".join(f"# TYPE {k} gauge\n{k} {v}" for k, v in names.items()) + "\n"
