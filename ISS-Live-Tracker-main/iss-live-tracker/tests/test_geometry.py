import math
from datetime import UTC, datetime, timedelta

import pytest

from src.orbit import (
    WGS84_A,
    build_satellite,
    compass_point,
    elevation_deg,
    find_passes,
    look_angles_from_ecef,
    refine_crossing,
    refine_peak,
)

LINE1 = "1 25544U 98067A   19343.69339541  .00001764  00000-0  38792-4 0  9991"
LINE2 = "2 25544  51.6439 211.2001 0007417  17.6667  85.6398 15.50103472202482"
EPOCH = datetime(2019, 12, 9, 16, 38, 29, tzinfo=UTC)
WINDOW_HOURS = 24
MIN_ELEVATION = 10.0
T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _angles(dx: float, dy: float, dz: float):
    # An observer at latitude 0, longitude 0 sits on the +X axis, so east is +Y,
    # north is +Z and up is +X. That makes the expected answers easy to see.
    return look_angles_from_ecef((WGS84_A + dx, dy, dz), 0.0, 0.0)


@pytest.mark.parametrize(
    ("dx", "dy", "dz", "expected_azimuth"),
    [
        (0, 0, 1000, 0.0),
        (0, 1000, 0, 90.0),
        (0, 0, -1000, 180.0),
        (0, -1000, 0, 270.0),
    ],
)
def test_azimuth_cardinal_directions(dx, dy, dz, expected_azimuth):
    angles = _angles(dx, dy, dz)
    assert angles.azimuth_deg == pytest.approx(expected_azimuth, abs=1e-6)
    assert angles.elevation_deg == pytest.approx(0.0, abs=1e-6)


def test_elevated_target_to_the_east():
    angles = _angles(500, 1000, 0)
    assert angles.azimuth_deg == pytest.approx(90.0, abs=1e-6)
    assert angles.elevation_deg == pytest.approx(math.degrees(math.atan2(500, 1000)), abs=1e-6)


def test_directly_overhead_is_90_degrees():
    assert _angles(400, 0, 0).elevation_deg == pytest.approx(90.0, abs=1e-6)


def test_target_below_horizon_has_negative_elevation():
    assert _angles(-300, 1000, 0).elevation_deg < 0


@pytest.mark.parametrize(
    ("azimuth", "expected"),
    [
        (0, "N"),
        (22.5, "NNE"),
        (45, "NE"),
        (90, "E"),
        (135, "SE"),
        (180, "S"),
        (225, "SW"),
        (270, "W"),
        (315, "NW"),
        (350, "N"),
        (359.9, "N"),
        (-90, "W"),
    ],
)
def test_compass_point(azimuth, expected):
    assert compass_point(azimuth) == expected


def test_refine_crossing_rising_edge():
    crossing = T0 + timedelta(seconds=17.3)
    result = refine_crossing(lambda t: t >= crossing, T0, T0 + timedelta(seconds=30), 0.1)
    assert 0 <= (result - crossing).total_seconds() <= 0.1


def test_refine_crossing_falling_edge():
    crossing = T0 + timedelta(seconds=12.7)
    result = refine_crossing(lambda t: t <= crossing, T0 + timedelta(seconds=30), T0, 0.1)
    assert 0 <= (crossing - result).total_seconds() <= 0.1


def test_refine_crossing_takes_five_halvings_from_30s_to_1s():
    crossing = T0 + timedelta(seconds=17.3)
    calls = []

    def probe(when):
        calls.append(when)
        return when >= crossing

    refine_crossing(probe, T0, T0 + timedelta(seconds=30), 1.0)
    assert len(calls) == 5


def test_refine_peak_finds_the_maximum():
    peak_time = T0 + timedelta(seconds=41.2)

    def elevation(when):
        return 80 - 0.01 * (when - peak_time).total_seconds() ** 2

    result = refine_peak(elevation, T0 + timedelta(seconds=20), T0 + timedelta(seconds=80), 0.5)
    assert abs((result - peak_time).total_seconds()) <= 0.5


@pytest.fixture(scope="module")
def scan():
    satellite = build_satellite(LINE1, LINE2)
    return satellite, find_passes(satellite, 0.0, 0.0, EPOCH, hours=WINDOW_HOURS)


def _interior(found):
    """Passes that neither began at the window start nor run past its end."""
    window_end = EPOCH + timedelta(hours=WINDOW_HOURS)
    return [p for p in found if p.start > EPOCH and p.end < window_end]


def test_edges_are_refined_to_about_one_second(scan):
    satellite, found = scan
    interior = _interior(found)
    assert interior
    two_seconds = timedelta(seconds=2)
    for p in interior:
        assert elevation_deg(satellite, p.start, 0.0, 0.0) >= MIN_ELEVATION
        assert elevation_deg(satellite, p.start - two_seconds, 0.0, 0.0) < MIN_ELEVATION
        assert elevation_deg(satellite, p.end, 0.0, 0.0) >= MIN_ELEVATION
        assert elevation_deg(satellite, p.end + two_seconds, 0.0, 0.0) < MIN_ELEVATION


def test_peak_is_the_highest_point(scan):
    satellite, found = scan
    for p in _interior(found):
        sampled_best = max(
            elevation_deg(satellite, p.start + timedelta(seconds=s), 0.0, 0.0)
            for s in range(0, p.duration_seconds + 1, 5)
        )
        assert p.max_elevation_deg >= sampled_best - 0.01


def test_azimuths_are_valid_bearings(scan):
    _, found = scan
    for p in found:
        for azimuth in (p.start_azimuth_deg, p.peak_azimuth_deg, p.end_azimuth_deg):
            assert 0.0 <= azimuth < 360.0