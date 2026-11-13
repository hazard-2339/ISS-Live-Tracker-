import math
from datetime import datetime, timedelta, timezone

import requests
from sgp4.api import Satrec, jday
from sgp4.propagation import gstime

from src.models import GroundPoint, SkyPass

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


def _ecef_km(satellite: Satrec, when: datetime) -> tuple[float, float, float]:
    """Satellite position in Earth-fixed Cartesian coordinates (km)."""
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
    return x, y, r[2]


def position_at(satellite: Satrec, when: datetime) -> GroundPoint:
    """Propagate the orbit to `when` (timezone-aware) and return the sub-satellite point."""
    x, y, z = _ecef_km(satellite, when)

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


def split_at_antimeridian(points: list[GroundPoint]) -> list[list[GroundPoint]]:
    """Break a track wherever it crosses longitude +/-180, so lines don't streak across the map."""
    segments: list[list[GroundPoint]] = []
    current: list[GroundPoint] = []
    for point in points:
        if current and abs(point.longitude - current[-1].longitude) > 180:
            segments.append(current)
            current = []
        current.append(point)
    if current:
        segments.append(current)
    return segments


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle (haversine) distance between two surface points."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = p2 - p1
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def elevation_deg(
    satellite: Satrec, when: datetime, obs_lat: float, obs_lon: float
) -> float:
    """Angle of the satellite above the observer's horizon, in degrees."""
    sx, sy, sz = _ecef_km(satellite, when)

    phi, lam = math.radians(obs_lat), math.radians(obs_lon)
    n = WGS84_A / math.sqrt(1 - WGS84_E2 * math.sin(phi) ** 2)
    ox = n * math.cos(phi) * math.cos(lam)
    oy = n * math.cos(phi) * math.sin(lam)
    oz = n * (1 - WGS84_E2) * math.sin(phi)

    dx, dy, dz = sx - ox, sy - oy, sz - oz
    # Component of the look vector along the local "Up" direction.
    up = (
        math.cos(phi) * math.cos(lam) * dx
        + math.cos(phi) * math.sin(lam) * dy
        + math.sin(phi) * dz
    )
    distance = math.sqrt(dx**2 + dy**2 + dz**2)
    return math.degrees(math.asin(up / distance))


def find_passes(
    satellite: Satrec,
    obs_lat: float,
    obs_lon: float,
    start: datetime,
    hours: int = 24,
    step_seconds: int = 30,
    min_elevation: float = 10.0,
) -> list[SkyPass]:
    """Find periods when the satellite is above `min_elevation` for the observer."""
    passes: list[SkyPass] = []
    rise = peak_time = last_above = None
    peak_elevation = -90.0

    for i in range(hours * 3600 // step_seconds + 1):
        t = start + timedelta(seconds=i * step_seconds)
        elevation = elevation_deg(satellite, t, obs_lat, obs_lon)

        if elevation >= min_elevation:
            if rise is None:
                rise, peak_time, peak_elevation = t, t, elevation
            elif elevation > peak_elevation:
                peak_time, peak_elevation = t, elevation
            last_above = t
        elif rise is not None:
            passes.append(SkyPass(rise, peak_time, last_above, peak_elevation))
            rise = None

    if rise is not None:  # a pass was still in progress when the window ended
        passes.append(SkyPass(rise, peak_time, last_above, peak_elevation))
    return passes
