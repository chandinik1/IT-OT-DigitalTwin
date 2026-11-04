"""One simulated machine with normal and gradual-degradation scenarios."""
import json
import logging
import os
import signal
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from app.config import MACHINE_ID, MQTT_HOST, MQTT_PORT, MQTT_TOPIC
from simulator.generator import generate_reading

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)
stop = False


def request_stop(*_args):
    global stop
    stop = True


def main():
    scenario = os.getenv("SCENARIO", "healthy").lower()
    if scenario not in {"healthy", "degrading"}:
        raise ValueError("SCENARIO must be healthy or degrading")
    interval = float(os.getenv("PUBLISH_INTERVAL", "2"))
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"sim-{MACHINE_ID}")
    client.will_set(f"factory/line1/{MACHINE_ID}/availability", "offline", qos=1, retain=True)
    # retry a temporary broker startup outage
    while not stop:
        try:
            client.connect(MQTT_HOST, MQTT_PORT, keepalive=15)
            break
        except OSError:
            log.warning("MQTT broker unavailable; retrying")
            time.sleep(2)
    if stop:
        return
    client.loop_start()
    client.publish(f"factory/line1/{MACHINE_ID}/availability", "online", qos=1, retain=True)
    log.info("Publishing %s machine events to %s (scenario=%s)", MACHINE_ID, MQTT_TOPIC, scenario)
    last_seq = 0
    step = 0
    try:
        while not stop:
            temperature, vibration = generate_reading(step, scenario)
            # nanosecond UTC clock; guard monotonic sequence during this process.
            last_seq = max(time.time_ns(), last_seq + 1)
            payload = {
                "machine_id": MACHINE_ID,
                "sequence": last_seq,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "temperature_c": temperature,
                "vibration_mm_s": vibration,
                "reported_mode": "RUNNING",
            }
            info = client.publish(MQTT_TOPIC, json.dumps(payload), qos=1)
            info.wait_for_publish(timeout=5)
            log.info("sent #%d: temp=%s vibration=%s", step, temperature, vibration)
            step += 1
            time.sleep(interval)
    finally:
        client.publish(f"factory/line1/{MACHINE_ID}/availability", "offline", qos=1, retain=True).wait_for_publish(timeout=3)
        client.disconnect()
        client.loop_stop()

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    main()
