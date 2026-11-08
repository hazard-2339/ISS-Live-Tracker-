import math
from datetime import datetime, timezone

import requests
from sgp4.api import Satrec, jday
from sgp4.propagation import gstime

from src.models import GroundPoint

TLE_URL = "https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=tle"
TIMEOUT_SECONDS = 10
EARTH_RADIUS_KM = 6371.0

# WGS84 ellipsoid
WGS84_A = 6378.137
WGS84_E2 = (1 / 298.257223563) * (2 - 1 / 298.257223563)


def fetch_tle() -> tuple[str, str]:
    response = requests.get(TLE_URL, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    lines = [line.strip() for line in response.text.splitlines() if line.strip()]
    if len(lines) < 2 or not lines[-2].startswith("1 ") or not lines[-1].startswith("2 "):
        raise ValueError("Unexpected TLE format from the data source.")
    return lines[-2], lines[-1]


def build_satellite(line1: str, line2: str) -> Satrec:
    return Satrec.twoline2rv(line1, line2)


def position_at(satellite: Satrec, when: datetime) -> GroundPoint:
    """Propagate the orbit to `when` (timezone-aware) and return the sub-satellite point."""
    when = when.astimezone(timezone.utc)
    seconds = when.second + when.microsecond / 1e6
    jd, fr = jday(when.year, when.month, when.day, when.hour, when.minute, seconds)

    error, r, _ = satellite.sgp4(jd, fr)
    if error:
        raise ValueError(f"SGP4 propagation failed (code {error}).")

    # Rotate from the inertial (TEME) frame to the Earth-fixed frame.
    theta = gstime(jd + fr)
    x = r[0] * math.cos(theta) + r[1] * math.sin(theta)
    y = -r[0] * math.sin(theta) + r[1] * math.cos(theta)
    z = r[2]

    # Cartesian -> geodetic latitude/longitude/altitude on the WGS84 ellipsoid.
    longitude = math.atan2(y, x)
    p = math.hypot(x, y)
    latitude = math.atan2(z, p * (1 - WGS84_E2))
    for _ in range(5):
        n = WGS84_A / math.sqrt(1 - WGS84_E2 * math.sin(latitude) ** 2)
        altitude = p / math.cos(latitude) - n
        latitude = math.atan2(z, p * (1 - WGS84_E2 * n / (n + altitude)))

    return GroundPoint(
        latitude=math.degrees(latitude),
        longitude=math.degrees(longitude),
        altitude_km=altitude,
        timestamp=int(when.timestamp()),
    )


def ground_track(
    satellite: Satrec,
    start: datetime,
    minutes: int = 95,
    step_seconds: int = 60,
) -> list[GroundPoint]:
    """Predicted path for the next `minutes` (about one orbit by default)."""
    start_ts = start.timestamp()
    steps = (minutes * 60) // step_seconds + 1
    return [
        position_at(satellite, datetime.fromtimestamp(start_ts + i * step_seconds, timezone.utc))
        for i in range(steps)
    ]


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle (haversine) distance between two surface points."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = p2 - p1
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))