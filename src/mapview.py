import json

from src.models import GroundPoint

LEAFLET_CSS = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css"
LEAFLET_JS = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js"


def render_map(lat: float, lon: float, segments: list[list[GroundPoint]]) -> str:
    """Return a self-contained HTML page: a Leaflet map with the ISS and its predicted track."""
    coords = json.dumps([[[p.latitude, p.longitude] for p in seg] for seg in segments])
    return f"""
<link rel="stylesheet" href="{LEAFLET_CSS}">
<div id="map" style="height:450px"></div>
<script src="{LEAFLET_JS}"></script>
<script>
  const map = L.map('map', {{ worldCopyJump: true }}).setView([{lat}, {lon}], 3);
  L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    maxZoom: 18,
    attribution: '&copy; OpenStreetMap contributors'
  }}).addTo(map);
  const segments = {coords};
  segments.forEach(s => L.polyline(s, {{ color: '#e63946', weight: 2, dashArray: '6 6' }}).addTo(map));
  L.circleMarker([{lat}, {lon}], {{
    radius: 8, color: '#ffffff', weight: 2, fillColor: '#1d4ed8', fillOpacity: 1
  }}).addTo(map).bindTooltip('ISS');
</script>
"""
