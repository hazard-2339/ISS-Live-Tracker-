import pytest
import requests

from src import api
from src.api import get_iss_position, parse_position

VALID = {
    "latitude": 12.5,
    "longitude": -45.2,
    "altitude": 420.1,
    "velocity": 27600.0,
    "timestamp": 1762450000,
}


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    def raise_for_status(self):
        if self.status >= 400:
            raise requests.HTTPError(f"HTTP {self.status}")

    def json(self):
        return self.payload


def test_parse_valid_payload():
    position = parse_position(VALID)
    assert position.latitude == 12.5
    assert position.timestamp == 1762450000


@pytest.mark.parametrize(
    "key, bad_value",
    [
        ("latitude", 91),
        ("latitude", None),
        ("latitude", True),
        ("longitude", -181),
        ("longitude", float("nan")),
        ("altitude", "high"),
        ("velocity", -1),
    ],
)
def test_parse_rejects_bad_values(key, bad_value):
    with pytest.raises(ValueError):
        parse_position({**VALID, key: bad_value})


def test_parse_rejects_non_object():
    with pytest.raises(TypeError):
        parse_position([1, 2, 3])


def test_get_position_success(monkeypatch):
    monkeypatch.setattr(api.requests, "get", lambda *a, **k: FakeResponse(VALID))
    assert get_iss_position().longitude == -45.2


def test_get_position_http_error(monkeypatch):
    monkeypatch.setattr(api.requests, "get", lambda *a, **k: FakeResponse({}, 500))
    with pytest.raises(requests.HTTPError):
        get_iss_position()