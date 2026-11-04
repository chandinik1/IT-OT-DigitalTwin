"""MQTT events → validated, sequence-aware Redis digital twin snapshot."""
import json
import logging
import os
import signal
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
import redis
from pydantic import ValidationError
from app.analytics import assess, make_baseline
from app.config import MACHINE_ID, MQTT_HOST, MQTT_PORT, MQTT_TOPIC, REDIS_URL
from app.models import Telemetry

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)
store = redis.Redis.from_url(REDIS_URL, decode_responses=True)
KEY = f"twin:{MACHINE_ID}"
HISTORY = f"{KEY}:history"
BASELINE = f"{KEY}:baseline"
COUNT = f"{KEY}:count"
AVAILABILITY = f"{KEY}:availability"


def process_telemetry(event: Telemetry) -> bool:
    """Ignore duplicates/old events; use WATCH to avoid concurrent overwrites.

    Assumption: one event producer and one consumer; a producer's sequence is
    its nanosecond UTC timestamp, so clocks must be reasonably synchronized.
    """
    if event.machine_id != MACHINE_ID:
        log.warning("Unexpected machine ID %s", event.machine_id)
        return False
    for _ in range(5):
        try:
            with store.pipeline() as pipe:
                pipe.watch(KEY, HISTORY, BASELINE)
                latest = pipe.hgetall(KEY)
                if event.sequence <= int(latest.get("sequence", "0")):
                    log.info("Ignored duplicate or late sequence %s", event.sequence)
                    return False
                baseline_raw = pipe.get(BASELINE)
                baseline = json.loads(baseline_raw) if baseline_raw else None
                historical = [json.loads(x) for x in pipe.lrange(HISTORY, 0, -1)]
                new_sample = {"temperature_c": event.temperature_c, "vibration_mm_s": event.vibration_mm_s}
                # list is newest-first. Reconstruct oldest-first for calibration.
                ordered_samples = list(reversed(historical)) + [new_sample]
                if baseline is None:
                    baseline = make_baseline(ordered_samples)
                result = assess(event.temperature_c, event.vibration_mm_s, baseline)
                snapshot = {
                    "machine_id": event.machine_id,
                    "sequence": str(event.sequence),
                    "timestamp": event.timestamp.isoformat(),
                    "temperature_c": str(event.temperature_c),
                    "vibration_mm_s": str(event.vibration_mm_s),
                    "reported_mode": event.reported_mode,
                    "health": result.health,
                    "anomaly_score": str(result.score),
                    "reason": result.reason,
                    "received_at": datetime.now(timezone.utc).isoformat(),
                }
                pipe.multi()
                pipe.hset(KEY, mapping=snapshot)
                pipe.lpush(HISTORY, json.dumps(new_sample))
                pipe.ltrim(HISTORY, 0, 59)
                pipe.incr(COUNT)
                if baseline_raw is None and baseline is not None:
                    pipe.set(BASELINE, json.dumps(baseline))
                pipe.execute()
                log.info("twin=%s temp=%s score=%.2f health=%s", MACHINE_ID, event.temperature_c, result.score, result.health)
                return True
        except redis.WatchError:
            continue
    raise RuntimeError("Redis state changed too often; failed to apply event")


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        client.subscribe([(MQTT_TOPIC, 1), (f"factory/line1/{MACHINE_ID}/availability", 1)])
        log.info("MQTT subscription active")
    else:
        log.error("MQTT connection failed: %s", reason_code)


def on_message(client, userdata, msg):
    try:
        if msg.topic.endswith("/availability"):
            value = msg.payload.decode().lower()
            if value in {"online", "offline"}:
                store.set(AVAILABILITY, value)
            return
        event = Telemetry.model_validate_json(msg.payload)
        process_telemetry(event)
    except (ValidationError, ValueError) as exc:
        log.warning("Rejected MQTT payload: %s", exc)
    except redis.RedisError:
        log.exception("Redis unavailable; event not stored (MQTT QoS 1 is not a durable app-level queue)")


def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="twin-consumer")
    client.on_connect = on_connect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=10)
    while True:
        try:
            store.ping()
            client.connect(MQTT_HOST, MQTT_PORT, keepalive=15)
            break
        except (OSError, redis.RedisError):
            log.warning("Waiting for Redis and Mosquitto")
            time.sleep(2)
    client.loop_forever()

if __name__ == "__main__":
    main()
