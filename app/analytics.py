"""Small, explainable anomaly detector: fixed baseline after warm-up."""
from __future__ import annotations
from dataclasses import dataclass
from statistics import mean, pstdev

WARMUP = 10
STD_FLOOR_TEMP = 1.5
STD_FLOOR_VIB = 0.15

@dataclass(frozen=True)
class Assessment:
    score: float
    health: str
    reason: str


def make_baseline(samples: list[dict]) -> dict | None:
    """Freeze baseline using the first 10 healthy readings (not online retraining)."""
    if len(samples) < WARMUP:
        return None
    initial = samples[:WARMUP]
    temps = [float(s["temperature_c"]) for s in initial]
    vibs = [float(s["vibration_mm_s"]) for s in initial]
    return {
        "temperature_mean": mean(temps),
        "temperature_std": max(pstdev(temps), STD_FLOOR_TEMP),
        "vibration_mean": mean(vibs),
        "vibration_std": max(pstdev(vibs), STD_FLOOR_VIB),
    }


def assess(temperature: float, vibration: float, baseline: dict | None) -> Assessment:
    if baseline is None:
        return Assessment(0.0, "CALIBRATING", "Waiting for 10 baseline readings")
    # Only elevated temperature/vibration is anomalous for this particular demo.
    t = max(0.0, (temperature - baseline["temperature_mean"]) / baseline["temperature_std"])
    v = max(0.0, (vibration - baseline["vibration_mean"]) / baseline["vibration_std"])
    score = round(max(t, v), 2)
    if score >= 4:
        return Assessment(score, "FAULT", "Large departure from healthy baseline")
    if score >= 2.5:
        return Assessment(score, "WARNING", "Elevated temperature or vibration")
    return Assessment(score, "HEALTHY", "Within baseline range")
