from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from app.main import app, get_redis, project_twin


def test_project_twin_online_and_stale():
    now = datetime.now(timezone.utc)
    raw = {"machine_id": "machine01", "reported_mode": "RUNNING", "temperature_c": "68", "vibration_mm_s": "2.2", "health": "HEALTHY", "anomaly_score": "0", "reason": "Normal", "received_at": now.isoformat()}
    assert project_twin(raw, "online", 5)["connectivity"] == "ONLINE"
    raw["received_at"] = (now - timedelta(seconds=120)).isoformat()
    assert project_twin(raw, "online", 5)["connectivity"] == "STALE"
    assert project_twin(raw, "offline", 5)["connectivity"] == "OFFLINE"


class FakeRedis:
    async def hgetall(self, key):
        return {"machine_id": "machine01", "reported_mode": "RUNNING", "temperature_c": "78", "vibration_mm_s": "2.5", "health": "WARNING", "anomaly_score": "3", "reason": "Rising temp", "received_at": datetime.now(timezone.utc).isoformat()}

    async def get(self, key):
        if key.endswith(":availability"):
            return "online"
        if key.endswith(":count"):
            return "14"
        return None

async def fake_redis_dependency():
    yield FakeRedis()


def test_twin_and_alerts_api():
    app.dependency_overrides[get_redis] = fake_redis_dependency
    try:
        client = TestClient(app)
        response = client.get("/twin")
        assert response.status_code == 200
        assert response.json()["health"] == "WARNING"
        assert response.json()["processed_events"] == 14
        assert client.get("/alerts").json()["alerts"][0]["health"] == "WARNING"
        assert "twin_temperature_celsius 78.0" in client.get("/metrics").text
    finally:
        app.dependency_overrides.clear()
