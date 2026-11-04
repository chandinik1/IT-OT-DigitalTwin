"""Pure telemetry generator; kept separate from MQTT for easy testing."""
import random


def generate_reading(step: int, scenario: str) -> tuple[float, float]:
    """Increase temperature/vibration after 12 readings in degrading mode."""
    drift = max(0, step - 12) if scenario == "degrading" else 0
    return (round(64 + drift * 0.75 + random.uniform(-0.6, 0.6), 2),
            round(2 + drift * 0.09 + random.uniform(-0.08, 0.08), 3))
