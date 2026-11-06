import pandas as pd
import streamlit as st

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

    col1, col2 = st.columns(2)
    col1.metric("Latitude", f"{position['latitude']:.4f}")
    col2.metric("Longitude", f"{position['longitude']:.4f}")

    st.map(
        pd.DataFrame(
            {"lat": [position["latitude"]], "lon": [position["longitude"]]}
        ),
        zoom=2,
    )


show_position()
