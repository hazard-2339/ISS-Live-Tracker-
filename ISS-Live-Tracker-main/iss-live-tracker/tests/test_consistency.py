from datetime import UTC, datetime

from src.orbit import build_satellite, elevation_deg, find_passes, position_at

LINE1 = "1 25544U 98067A   19343.69339541  .00001764  00000-0  38792-4 0  9991"
LINE2 = "2 25544  51.6439 211.2001 0007417  17.6667  85.6398 15.50103472202482"
EPOCH = datetime(2019, 12, 9, 16, 38, 29, tzinfo=UTC)
MIN_ELEVATION = 10.0


def test_elevation_is_90_directly_below_the_satellite():
    satellite = build_satellite(LINE1, LINE2)
    point = position_at(satellite, EPOCH)
    assert elevation_deg(satellite, EPOCH, point.latitude, point.longitude) > 89.9


def test_passes_are_ordered_and_valid():
    satellite = build_satellite(LINE1, LINE2)
    passes = find_passes(satellite, 0.0, 0.0, EPOCH)
    assert passes
    for p in passes:
        assert p.start <= p.peak <= p.end
        assert p.max_elevation_deg >= MIN_ELEVATION
    assert all(a.end < b.start for a, b in zip(passes, passes[1:], strict=False))