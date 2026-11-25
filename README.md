# ISS Live Tracker

A Streamlit app that shows where the International Space Station is right now, draws its predicted ground track, and tells you when it will pass over your location.

![pytest](<Screenshot 2026-11-25 234923.png>) ![streamlit](<Screenshot 2026-11-25 234238.png>)

## Features

- **Live position** of the ISS on an interactive Leaflet map, fetched from the [Where the ISS at?](https://wheretheiss.at/w/developer) API
- **Predicted ground track** computed locally with SGP4 orbit propagation (no network call needed for the prediction itself)
- **Pass predictor** for your own latitude/longitude: when the ISS rises, peaks and sets
- **Validated, typed data models**: API responses are checked before they reach the UI, so bad data fails loudly instead of drawing a satellite in the wrong place
- **Tests and CI**: pytest suite and ruff linting run on every push

## Quick start

```bash
git clone https://github.com/<your-username>/iss-live-tracker.git
cd iss-live-tracker

python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate

pip install -r requirements.txt
python -m streamlit run app.py
```

Streamlit prints a local URL (usually `http://localhost:8501`). Open it in your browser.

> **Windows note:** run Streamlit with `python -m streamlit run app.py` rather than `streamlit run app.py`. This project deliberately avoids `pandas`, because Windows Application Control policies can block its compiled DLLs.

## How it works

```
 wheretheiss.at API ──► src/api.py ──► typed models ──► app.py (Streamlit UI)
                                            ▲                 │
                  TLE (orbital elements) ──► src/orbit.py     └─► Leaflet map
                                         (SGP4 propagation)
```

| Part | What it does |
|---|---|
| `app.py` | Streamlit entry point: layout, map, controls |
| `src/api.py` | API client. Requests the ISS (NORAD ID `25544`) and validates latitude/longitude |
| `src/orbit.py` | SGP4 propagation: turns orbital elements into future positions and ground tracks |
| `tests/` | pytest suite for the API client, models and orbit module |
| `assets/` | Images and static files |

### Where the live data comes from

The client calls `https://api.wheretheiss.at/v1/satellites/25544`, which returns JSON like this (shape taken from the API documentation; the numbers are the docs' example, not a live reading):

```json
{
  "name": "iss",
  "id": 25544,
  "latitude": 50.11496269845,
  "longitude": 118.07900427317,
  "altitude": 408.05526028199,
  "velocity": 27635.971970874
}
```

Altitude is in kilometres and velocity in km/h by default. The API is rate limited, so the app should not poll faster than necessary.

### Why SGP4?

The live API only tells you where the ISS is *now*. To draw where it *will be*, the app uses a Two-Line Element set (TLE) and the SGP4 model, the standard method for propagating near-Earth satellite orbits. The ISS circles the Earth about every 92 minutes, so the predicted track is most accurate close to the TLE's epoch and degrades over days.

## Example usage

```python
from src.api import get_iss_position

pos = get_iss_position()
print(pos.latitude, pos.longitude)
```

<!-- Replace with the real function names from src/api.py and src/orbit.py -->

## Development

```bash
pip install -r requirements.txt
ruff check .
pytest
```

CI runs the same two commands on every push and pull request.

## Project structure

```
iss-live-tracker/
├── app.py
├── requirements.txt
├── .gitignore
├── src/
│   ├── api.py
│   └── orbit.py
├── tests/
└── assets/
```

## Roadmap

The next step is evolving this into **Orbit Lab**, a tool for teachers, students and clubs, with three screens:

- **Now**: live position and basic facts
- **Plan**: a printable pass sheet for your location
- **Lab**: simple experiments built on real orbit data

Milestone 1 covers configuration, azimuth and look angles, more precise rise/set times, and support for any satellite via TLE.

## Data sources and credits

- Live position: [Where the ISS at?](https://wheretheiss.at/w/developer) by Bill Shupp
- Orbit propagation: SGP4
- Map: Leaflet with OpenStreetMap tiles

## License

