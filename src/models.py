from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class IssPosition:
    latitude: float
    longitude: float
    altitude_km: float
    velocity_kmh: float
    timestamp: int


@dataclass(frozen=True)
class GroundPoint:
    latitude: float
    longitude: float
    altitude_km: float
    timestamp: int


@dataclass(frozen=True)
class SkyPass:
    start: datetime
    peak: datetime
    end: datetime
    max_elevation_deg: float

    @property
    def duration_seconds(self) -> int:
        return int((self.end - self.start).total_seconds())
