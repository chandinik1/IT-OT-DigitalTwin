from app.analytics import WARMUP, assess, make_baseline
from simulator.generator import generate_reading


def test_calibrating_until_enough_samples():
    assert make_baseline([{"temperature_c": 64, "vibration_mm_s": 2}] * (WARMUP - 1)) is None
    assert assess(64, 2, None).health == "CALIBRATING"


def test_anomaly_detects_elevated_temperature():
    samples = [{"temperature_c": 64, "vibration_mm_s": 2}] * WARMUP
    baseline = make_baseline(samples)
    assert baseline is not None
    assert assess(64, 2, baseline).health == "HEALTHY"
    assert assess(68, 2, baseline).health == "WARNING"
    assert assess(72, 2, baseline).health == "FAULT"


def test_degrading_simulator_starts_after_calibration():
    import random
    random.seed(10)
    temperatures = [generate_reading(i, "degrading")[0] for i in range(35)]
    assert temperatures[-1] > temperatures[0] + 10
