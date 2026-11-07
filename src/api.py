import math

import requests

from src.models import IssPosition

API_URL = "https://api.wheretheiss.at/v1/satellites/25544"
TIMEOUT_SECONDS = 10


def _number(data: dict, key: str, low: float, high: float) -> float:
    value = data.get(key)
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not low <= value <= high
    ):
        raise ValueError(f"The API returned an invalid {key}.")
    return float(value)


def parse_position(data: object) -> IssPosition:
    if not isinstance(data, dict):
        raise ValueError("The API response must be a JSON object.")
    return IssPosition(
        latitude=_number(data, "latitude", -90, 90),
        longitude=_number(data, "longitude", -180, 180),
        altitude_km=_number(data, "altitude", 0, 2000),
        velocity_kmh=_number(data, "velocity", 0, 50000),
        timestamp=int(_number(data, "timestamp", 0, 4102444800)),
    )


def get_iss_position() -> IssPosition:
    response = requests.get(API_URL, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return parse_position(response.json())


if __name__ == "__main__":
    try:
        print(get_iss_position())
    except (requests.RequestException, ValueError) as error:
        print(f"Could not fetch a valid ISS position: {error}")