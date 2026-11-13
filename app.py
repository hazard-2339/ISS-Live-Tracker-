from datetime import datetime, timedelta, timezone

import requests
import streamlit as st
import streamlit.components.v1 as components

from src.api import get_iss_position
from src.mapview import render_map
from src.orbit import (
    build_satellite,
    distance_km,
    fetch_tle,
    find_passes,
    ground_track,
    position_at,
    split_at_antimeridian,
)

st.set_page_config(page_title="ISS Live Tracker", page_icon="🛰️")
st.title("ISS Live Tracker")


@st.cache_resource(ttl=6 * 3600)
def load_satellite():
    return build_satellite(*fetch_tle())


@st.cache_data(ttl=60)
def predicted_track():
    return ground_track(load_satellite(), datetime.now(timezone.utc))


@st.cache_data(ttl=600)
def upcoming_passes(lat: float, lon: float):
    return find_passes(load_satellite(), lat, lon, datetime.now(timezone.utc))


@st.fragment(run_every=5)
def show_position():
    try:
        position = get_iss_position()
    except (requests.RequestException, ValueError, TypeError) as error:
        st.error(f"Could not fetch the ISS position: {error}")
        return

    lat = position.latitude
    lon = position.longitude

    col1, col2 = st.columns(2)
    col1.metric("Latitude", f"{lat:.4f}")
    col2.metric("Longitude", f"{lon:.4f}")

    col3, col4 = st.columns(2)
    col3.metric("Altitude", f"{position.altitude_km:.1f} km")
    col4.metric("Speed", f"{position.velocity_kmh:,.0f} km/h")

    segments = []
    try:
        when = datetime.fromtimestamp(position.timestamp, timezone.utc)
        predicted = position_at(load_satellite(), when)
        gap = distance_km(lat, lon, predicted.latitude, predicted.longitude)
        st.caption(f"Orbit model check: my SGP4 calculation is {gap:.1f} km from the API reading.")
        segments = split_at_antimeridian(predicted_track())
    except (requests.RequestException, ValueError, TypeError) as error:
        st.caption(f"Orbit model unavailable: {error}")

    components.html(render_map(lat, lon, segments), height=470)


def show_passes() -> None:
    st.sidebar.header("Pass predictor")
    obs_lat = st.sidebar.number_input(
        "Your latitude", min_value=-90.0, max_value=90.0, value=0.0, step=0.1, format="%.4f"
    )
    obs_lon = st.sidebar.number_input(
        "Your longitude", min_value=-180.0, max_value=180.0, value=0.0, step=0.1, format="%.4f"
    )
    offset = st.sidebar.number_input(
        "UTC offset (hours)", min_value=-12.0, max_value=14.0, value=0.0, step=0.5
    )

    try:
        passes = upcoming_passes(obs_lat, obs_lon)
    except (requests.RequestException, ValueError, TypeError) as error:
        st.sidebar.error(f"Could not compute passes: {error}")
        return

    if not passes:
        st.sidebar.write("No passes above 10° in the next 24 hours.")
        return

    tz = timezone(timedelta(hours=offset))
    st.sidebar.caption("Passes above 10° elevation, next 24 hours")
    for p in passes[:6]:
        minutes, seconds = divmod(p.duration_seconds, 60)
        st.sidebar.write(
            f"**{p.start.astimezone(tz):%a %H:%M}** · peak {p.max_elevation_deg:.0f}° · {minutes}m {seconds:02d}s"
        )


show_passes()
show_position()
