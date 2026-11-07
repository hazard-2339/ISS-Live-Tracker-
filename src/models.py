from dataclasses import dataclass


@dataclass(frozen=True)
class IssPosition:
    latitude: float
    longitude: float
    altitude_km: float
    velocity_kmh: float
    timestamp: int

