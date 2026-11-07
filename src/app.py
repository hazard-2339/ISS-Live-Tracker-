import streamlit as st
import streamlit.components.v1 as components

from src.api import get_iss_position

st.set_page_config(page_title="ISS Live Tracker", page_icon="🛰️")
st.title("ISS Live Tracker")


@st.fragment(run_every=5)
def show_position():
    try:
        position = get_iss_position()
    except Exception as error:
        st.error(f"Could not fetch the ISS position: {error}")
        return

    lat = position["latitude"]
    lon = position["longitude"]

    col1, col2 = st.columns(2)
    col1.metric("Latitude", f"{lat:.4f}")
    col2.metric("Longitude", f"{lon:.4f}")

    bbox = f"{lon - 30},{lat - 15},{lon + 30},{lat + 15}"
    url = (
        "https://www.openstreetmap.org/export/embed.html"
        f"?bbox={bbox}&layer=mapnik&marker={lat},{lon}"
    )
    components.html(
        f'<iframe src="{url}" width="100%" height="450" style="border:0"></iframe>',
        height=460,
    )


show_position(    lat = position.latitude
    lon = position.longitude

    col1, col2 = st.columns(2)
    col1.metric("Latitude", f"{lat:.4f}")
    col2.metric("Longitude", f"{lon:.4f}")

    col3, col4 = st.columns(2)
    col3.metric("Altitude", f"{position.altitude_km:.1f} km")
    col4.metric("Speed", f"{position.velocity_kmh:,.0f} km/h")
    )