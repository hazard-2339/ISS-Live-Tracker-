import math

import requests

API_URL = "https://api.wheretheiss.at/v1/satellites/25544"


def get_iss_position():
    response = requests.get(API_URL, timeout=10)
    response.raise_for_status()

    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("The API response must be a JSON object.")

    latitude = data.get("latitude")
    longitude = data.get("longitude")

    if (
        isinstance(latitude, bool)
        or not isinstance(latitude, (int, float))
        or not math.isfinite(latitude)
        or not -90 <= latitude <= 90
    ):
        raise ValueError("The API returned an invalid latitude.")

    if (
        isinstance(longitude, bool)
        or not isinstance(longitude, (int, float))
        or not math.isfinite(longitude)
        or not -180 <= longitude <= 180
    ):
        raise ValueError("The API returned an invalid longitude.")

    return {"latitude": latitude, "longitude": longitude}


if __name__ == "__main__":
    try:
        position = get_iss_position()
        print(f"ISS latitude:  {position['latitude']}")
        print(f"ISS longitude: {position['longitude']}")
    except (requests.RequestException, ValueError) as error:
        print(f"Could not fetch a valid ISS position: {error}")