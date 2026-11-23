import math
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import requests
from sgp4.api import Satrec, jday
from sgp4.propagation import gstime

from src.config import (
    DEFAULT_CATALOG_NUMBER,
    EDGE_TOLERANCE_SECONDS,
    MIN_PASS_ELEVATION_DEG,
    PASS_SCAN_STEP_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
    TLE_URL_TEMPLATE,
)
from src.models import GroundPoint, LookAngles, SkyPass

EARTH_RADIUS_KM = 6371.0

# WGS84 ellipsoid
WGS84_A = 6378.137
WGS84_E2 = (1 / 298.257223563) * (2 - 1 / 298.257223563)

COMPASS_POINTS = (
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
)
DEGREES_PER_COMPASS_POINT = 360 / len(COMPASS_POINTS)


def fetch_tle(catalog_number: int = DEFAULT_CATALOG_NUMBER) -> tuple[str, str]:
    url = TLE_URL_TEMPLATE.format(catalog_number=catalog_number)
    response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    lines = [line.strip() for line in response.text.splitlines() if line.strip()]
    if len(lines) < 2 or not lines[-2].startswith("1 ") or not lines[-1].startswith("2 "):
        raise ValueError("Unexpected TLE format from the data source.")
    return lines[-2], lines[-1]


def build_satellite(line1: str, line2: str) -> Satrec:
    return Satrec.twoline2rv(line1, line2)


def _ecef_km(satellite: Satrec, when: datetime) -> tuple[float, float, float]:
    """Satellite position in Earth-fixed Cartesian coordinates (km)."""
    when = when.astimezone(UTC)
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
        position_at(satellite, datetime.fromtimestamp(start_ts + i * step_seconds, UTC))
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


def compass_point(azimuth_deg: float) -> str:
    """Turn a bearing in degrees (0 = north, clockwise) into N, NNE, NE, ..."""
    index = round((azimuth_deg % 360) / DEGREES_PER_COMPASS_POINT) % len(COMPASS_POINTS)
    return COMPASS_POINTS[index]


def observer_ecef_km(lat_deg: float, lon_deg: float) -> tuple[float, float, float]:
    """Earth-fixed position of a point on the WGS84 surface."""
    phi, lam = math.radians(lat_deg), math.radians(lon_deg)
    n = WGS84_A / math.sqrt(1 - WGS84_E2 * math.sin(phi) ** 2)
    return (
        n * math.cos(phi) * math.cos(lam),
        n * math.cos(phi) * math.sin(lam),
        n * (1 - WGS84_E2) * math.sin(phi),
    )


def look_angles_from_ecef(
    sat_xyz: tuple[float, float, float], obs_lat: float, obs_lon: float
) -> LookAngles:
    """Elevation and azimuth of a point, seen from an observer on the ground."""
    ox, oy, oz = observer_ecef_km(obs_lat, obs_lon)
    dx, dy, dz = sat_xyz[0] - ox, sat_xyz[1] - oy, sat_xyz[2] - oz

    phi, lam = math.radians(obs_lat), math.radians(obs_lon)
    east = -math.sin(lam) * dx + math.cos(lam) * dy
    north = (
        -math.sin(phi) * math.cos(lam) * dx
        - math.sin(phi) * math.sin(lam) * dy
        + math.cos(phi) * dz
    )
    up = (
        math.cos(phi) * math.cos(lam) * dx
        + math.cos(phi) * math.sin(lam) * dy
        + math.sin(phi) * dz
    )

    distance = math.sqrt(dx**2 + dy**2 + dz**2)
    sine_elevation = max(-1.0, min(1.0, up / distance))  # guard against rounding error
    return LookAngles(
        elevation_deg=math.degrees(math.asin(sine_elevation)),
        azimuth_deg=math.degrees(math.atan2(east, north)) % 360,
    )


def look_angles(
    satellite: Satrec, when: datetime, obs_lat: float, obs_lon: float
) -> LookAngles:
    return look_angles_from_ecef(_ecef_km(satellite, when), obs_lat, obs_lon)


def elevation_deg(
    satellite: Satrec, when: datetime, obs_lat: float, obs_lon: float
) -> float:
    """Angle of the satellite above the observer's horizon, in degrees."""
    return look_angles(satellite, when, obs_lat, obs_lon).elevation_deg


def refine_crossing(
    is_above: Callable[[datetime], bool],
    t_below: datetime,
    t_above: datetime,
    tolerance_seconds: float = EDGE_TOLERANCE_SECONDS,
) -> datetime:
    """Bisection: find where `is_above` flips, given one time where it is False
    (`t_below`) and one where it is True (`t_above`, either side of it).

    Returns the True-side time, within `tolerance_seconds` of the true crossing.
    """
    while abs((t_above - t_below).total_seconds()) > tolerance_seconds:
        middle = t_below + (t_above - t_below) / 2
        if is_above(middle):
            t_above = middle
        else:
            t_below = middle
    return t_above


def refine_peak(
    value_at: Callable[[datetime], float],
    t_low: datetime,
    t_high: datetime,
    tolerance_seconds: float = EDGE_TOLERANCE_SECONDS,
) -> datetime:
    """Ternary search for the time of the maximum, assuming a single peak in range."""
    while (t_high - t_low).total_seconds() > tolerance_seconds:
        third = (t_high - t_low) / 3
        first, second = t_low + third, t_high - third
        if value_at(first) < value_at(second):
            t_low = first
        else:
            t_high = second
    return t_low + (t_high - t_low) / 2


def find_passes(
    satellite: Satrec,
    obs_lat: float,
    obs_lon: float,
    start: datetime,
    hours: int = 24,
    step_seconds: int = PASS_SCAN_STEP_SECONDS,
    min_elevation: float = MIN_PASS_ELEVATION_DEG,
    tolerance_seconds: float = EDGE_TOLERANCE_SECONDS,
) -> list[SkyPass]:
    """Find periods above `min_elevation`, with edge times refined by bisection."""

    def angles_at(when: datetime) -> LookAngles:
        return look_angles(satellite, when, obs_lat, obs_lon)

    def elevation_at(when: datetime) -> float:
        return angles_at(when).elevation_deg

    def is_above(when: datetime) -> bool:
        return elevation_at(when) >= min_elevation

    def build_pass(rise: datetime, peak_sample: datetime, end: datetime) -> SkyPass:
        step = timedelta(seconds=step_seconds)
        peak = refine_peak(elevation_at, peak_sample - step, peak_sample + step, tolerance_seconds)
        return SkyPass(
            start=rise,
            peak=peak,
            end=end,
            max_elevation_deg=elevation_at(peak),
            start_azimuth_deg=angles_at(rise).azimuth_deg,
            peak_azimuth_deg=angles_at(peak).azimuth_deg,
            end_azimuth_deg=angles_at(end).azimuth_deg,
        )

    passes: list[SkyPass] = []
    rise: datetime | None = None
    peak_sample = start
    peak_elevation = -90.0
    previous: datetime | None = None

    for i in range(hours * 3600 // step_seconds + 1):
        now = start + timedelta(seconds=i * step_seconds)
        elevation = elevation_at(now)

        if elevation >= min_elevation:
            if rise is None:
                if previous is None:  # already in progress when the window opened
                    rise = now
                else:
                    rise = refine_crossing(is_above, previous, now, tolerance_seconds)
                peak_sample, peak_elevation = now, elevation
            elif elevation > peak_elevation:
                peak_sample, peak_elevation = now, elevation
        elif rise is not None and previous is not None:
            end = refine_crossing(is_above, now, previous, tolerance_seconds)
            passes.append(build_pass(rise, peak_sample, end))
            rise = None
        previous = now

    if rise is not None and previous is not None:  # still in progress at window end
        passes.append(build_pass(rise, peak_sample, previous))
    return passes