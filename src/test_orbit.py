from datetime import datetime, timezone

from src.orbit import build_satellite, distance_km, ground_track, position_at

LINE1 = "1 25544U 98067A   19343.69339541  .00001764  00000-0  38792-4 0  9991"
LINE2 = "2 25544  51.6439 211.2001 0007417  17.6667  85.6398 15.50103472202482"
EPOCH = datetime(2019, 12, 9, 16, 38, 29, tzinfo=timezone.utc)


def test_position_is_physically_plausible():
    point = position_at(build_satellite(LINE1, LINE2), EPOCH)
    # Inclination is 51.64 deg (geocentric); geodetic latitude peaks ~0.2 deg higher.
    assert abs(point.latitude) <= 52.0
    assert -180 <= point.longitude <= 180
    assert 380 <= point.altitude_km <= 460


def test_ground_track_covers_about_one_orbit():
    track = ground_track(build_satellite(LINE1, LINE2), EPOCH, minutes=95)
    assert len(track) == 96
    assert all(abs(p.latitude) <= 52.0 for p in track)

    

def test_distance_zero_and_known_value():
    assert distance_km(10, 20, 10, 20) == 0
    # one degree of latitude is roughly 111 km
    assert 110 < distance_km(0, 0, 1, 0) < 112