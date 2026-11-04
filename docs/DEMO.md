# Five-minute demonstration

Run from the project directory.

## Scenario A: Healthy machine

```bash
docker compose up --build -d
docker compose logs -f consumer
```

After ~20 seconds, a baseline is available. In another terminal:

```bash
curl http://localhost:8000/twin
curl http://localhost:8000/alerts
```

Expected (not guaranteed exact readings): `health=HEALTHY`, temperature near 64°C, and no alerts.

## Scenario B: Gradual degradation

```bash
docker compose stop simulator
# Reset demo state to ensure a fresh healthy calibration
# This clears only the dedicated project's Redis DB.
docker compose exec redis redis-cli FLUSHDB
SCENARIO=degrading docker compose up -d --force-recreate simulator
docker compose logs -f simulator consumer
```

Watch `http://localhost:8000/twin` after ~30–60 seconds. Health should shift from CALIBRATING to HEALTHY to WARNING/FAULT as the simulated signals drift.

## Optional Grafana

```bash
docker compose --profile observability up -d
```

- URL: http://localhost:3000
- Login: `admin` / `admin` (demo only; change if you publish this anywhere)
- Dashboard: **Industrial Twin → Industrial Digital Twin — Machine 01**

Prometheus at http://localhost:9090; raw application metrics at http://localhost:8000/metrics.

## Failure test

```bash
docker compose stop simulator
sleep 12
curl http://localhost:8000/twin
```

Expected: `connectivity=OFFLINE` after a clean exit or `STALE` when telemetry stops without a delivered availability message. Last readings are kept but should not be treated as live.

## Cleanup

```bash
docker compose --profile observability down
# If you want to erase your locally persisted Redis demo data:
docker compose --profile observability down -v
```
