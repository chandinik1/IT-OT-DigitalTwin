"""Shared MQTT message contract."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

class Telemetry(BaseModel):
    machine_id: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    sequence: int = Field(gt=0)
    timestamp: datetime
    temperature_c: float = Field(ge=-50, le=300)
    vibration_mm_s: float = Field(ge=0, le=100)
    reported_mode: Literal["RUNNING", "IDLE", "STOPPED"] = "RUNNING"
