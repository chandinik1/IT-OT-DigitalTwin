# Architecture and trade-offs

```text
One simulated machine (Python)
  └─ publishes temperature + vibration every 2 s
       └─ MQTT QoS 1 → Eclipse Mosquitto
            └─ Python consumer validates and scores readings
                 └─ Redis: last state + 60-sample history + frozen baseline
                      ├─ FastAPI: GET /twin, /alerts, /metrics
                      └─ Prometheus scrape → Grafana dashboard (optional)
```

## Why these components?

| Component | Responsibility | Why not something else? |
|---|---|---|
| MQTT/Mosquitto | Loosely couples simulated machine and backend | Direct HTTP would hide industrial Pub/Sub patterns |
| Redis | Low-latency live state, bounded recent samples and counters | A database is better for permanent historical telemetry, intentionally out of scope |
| Python | Event validation and explainable anomaly scoring | No heavy ML framework needed for a baseline detector |
| FastAPI | Read-only machine-health API | Separates telemetry ingestion from client access |
| Kubernetes (kind) | Reproducible local container orchestration | Does not provide production HA or persistence |
| Prometheus + Grafana (optional) | Time-series panels and score visualization | Does not require a custom frontend |

## What makes this a *minimal digital twin*?

It's a synchronized software representation of a machine's **latest measured state**, **derived health state** and **connectivity/freshness**. It is a monitoring-focused digital twin prototype, **not** a physics simulation, full digital thread, or control system.

## Anomaly algorithm

- Warm up using the first 10 readings from an assumed healthy simulator.
- Freeze reference means and standard deviations after warm-up; impose small deviation floors.
- Calculate elevated-temperature and elevated-vibration z-scores.
- The larger positive score controls classification: <2.5 healthy, 2.5–3.99 warning, ≥4 fault.
- Simulated degradation begins only after sample 12, so it is not incorporated in baseline calibration.
- These are **demo thresholds**, not validated industrial safety limits. This detector does not predict failures or remaining useful life.

## Reliability and security limitations

- MQTT QoS 1 can redeliver. We ignore repeated/older sequence values in Redis; state updates are atomic using WATCH/MULTI/EXEC.
- Sequence is a UTC nanosecond timestamp. It assumes a single publisher and sufficiently stable system time; production systems need stronger identity/sequence models.
- The consumer subscribes to live telemetry, not durable message queues. A worker outage can lose processing, even though MQTT uses QoS 1, especially across process recreation.
- Redis AOF is enabled only in Docker Compose. Kubernetes Redis is ephemeral. No historical database or guaranteed audit trail exists.
- MQTT Last Will publishes `offline` on unexpected disconnection. FastAPI also derives `STALE` after 10 seconds without new telemetry. Stale reported values are **not** evidence that physical equipment is running.
- Mosquitto uses `allow_anonymous true` only for a **local simulation**. Never connect this configuration to a real plant network. Production requires TLS, authentication, authorization, and network segmentation.
- Kubernetes scaling to two FastAPI replicas is safe for read-only API calls, but keep one simulator and one event consumer.
