"""Shared configuration (environment variables work with Compose and Kubernetes)."""
import os

MACHINE_ID = os.getenv("MACHINE_ID", "machine01")
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", f"factory/line1/{MACHINE_ID}/telemetry")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
STALE_AFTER_SECONDS = int(os.getenv("STALE_AFTER_SECONDS", "10"))
