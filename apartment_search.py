"""
Apartment Search Agent
Evaluates a residential address for family suitability by:
- Finding the nearest Grundschule, Kita, Supermarket, Cafe, Playground, Restaurant
  and calculating walking time to each
- Calculating driving and public transport time to predefined work addresses
- Gathering general area information via web search
- Generating an interactive map showing all points of interest
"""

import os
import json
import googlemaps
from langchain_community.utilities import GoogleSerperAPIWrapper
from dotenv import load_dotenv

load_dotenv(override=True)

AMENITY_CATEGORIES = [
    ("Grundschule", "primary_school"),
    ("Kita", "child_care"),       # mapped to keyword search below
    ("Supermarket", "supermarket"),
    ("Cafe", "cafe"),
    ("Playground", "playground"),  # mapped to keyword search below
    ("Restaurant", "restaurant"),
]

# Predefined work addresses
WORK_ADDRESSES = [
    {"label": "BMW", "address": "Bremer Str. 6, 80807 München"},
    {"label": "Workday", "address": "Streitfeldstraße 19, 81673 München"},
]

# Google Places API "type" field doesn't cover all categories equally well.
# For some we do a text/nearby search with a keyword instead.
_KEYWORD_ONLY = {"child_care", "playground", "primary_school"}

# Marker colors per category for the map
_MARKER_COLORS = {
    "Grundschule": "#e74c3c",   # red
    "Kita": "#e67e22",          # orange
    "Supermarket": "#2ecc71",   # green
    "Cafe": "#9b59b6",          # purple
    "Playground": "#f1c40f",    # yellow
    "Restaurant": "#3498db",    # blue
    "BMW": "#1a1a2e",           # dark blue
    "Workday": "#16a085",       # teal
    "Home": "#e74c3c",          # red (special)
}


def _init_client():
    api_key = os.getenv("GPLACES_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("No Google API key found. Set GPLACES_API_KEY or GOOGLE_API_KEY in .env")
    return googlemaps.Client(key=api_key)


def _find_nearest(gmaps, origin_address: str, category_label: str, place_type: str, radius: int = 2000):
    """Find the nearest place of a given type and return its name, address, walking distance, and coordinates."""
    # Geocode the origin first
    geocode_result = gmaps.geocode(origin_address)
    if not geocode_result:
        return {"category": category_label, "error": "Could not geocode origin address"}

    origin_loc = geocode_result[0]["geometry"]["location"]

    # Search for nearby places
    if place_type in _KEYWORD_ONLY:
        places_result = gmaps.places_nearby(
            location=(origin_loc["lat"], origin_loc["lng"]),
            radius=radius,
            keyword=category_label,
        )
    else:
        places_result = gmaps.places_nearby(
            location=(origin_loc["lat"], origin_loc["lng"]),
            radius=radius,
            type=place_type,
        )

    results = places_result.get("results", [])
    if not results:
        # Retry with larger radius
        if place_type in _KEYWORD_ONLY:
            places_result = gmaps.places_nearby(
                location=(origin_loc["lat"], origin_loc["lng"]),
                radius=5000,
                keyword=category_label,
            )
        else:
            places_result = gmaps.places_nearby(
                location=(origin_loc["lat"], origin_loc["lng"]),
                radius=5000,
                type=place_type,
            )
        results = places_result.get("results", [])

    if not results:
        return {"category": category_label, "error": f"No {category_label} found within 5 km"}

    # Take the nearest result (API returns by prominence, so we pick the closest by distance matrix)
    # Use up to 5 candidates and pick the one with shortest walking time
    candidates = results[:5]
    destinations = [
        f"{p['geometry']['location']['lat']},{p['geometry']['location']['lng']}"
        for p in candidates
    ]

    dm_result = gmaps.distance_matrix(
        origins=[origin_address],
        destinations=destinations,
        mode="walking",
        language="de",
    )

    best = None
    best_duration = float("inf")
    for i, element in enumerate(dm_result["rows"][0]["elements"]):
        if element["status"] == "OK":
            duration_sec = element["duration"]["value"]
            if duration_sec < best_duration:
                best_duration = duration_sec
                best = {
                    "category": category_label,
                    "name": candidates[i].get("name", "Unknown"),
                    "address": candidates[i].get("vicinity", ""),
                    "walking_time": element["duration"]["text"],
                    "walking_distance": element["distance"]["text"],
                    "lat": candidates[i]["geometry"]["location"]["lat"],
                    "lng": candidates[i]["geometry"]["location"]["lng"],
                }

    return best or {"category": category_label, "error": f"Could not calculate walking time to any {category_label}"}


def _commute_times(gmaps, origin_address: str, work_addresses: list[dict]):
    """Calculate driving and public transport times from origin to each work address."""
    results = []
    for work in work_addresses:
        entry = {"label": work["label"], "address": work["address"]}

        # Geocode work address for map coordinates
        try:
            geo = gmaps.geocode(work["address"])
            if geo:
                entry["lat"] = geo[0]["geometry"]["location"]["lat"]
                entry["lng"] = geo[0]["geometry"]["location"]["lng"]
        except Exception:
            pass

        # Driving
        try:
            dm_driving = gmaps.distance_matrix(
                origins=[origin_address],
                destinations=[work["address"]],
                mode="driving",
                language="de",
            )
            el = dm_driving["rows"][0]["elements"][0]
            if el["status"] == "OK":
                entry["driving_time"] = el["duration"]["text"]
                entry["driving_distance"] = el["distance"]["text"]
            else:
                entry["driving_time"] = "N/A"
        except Exception as e:
            entry["driving_time"] = f"Error: {e}"

        # Public transport
        try:
            dm_transit = gmaps.distance_matrix(
                origins=[origin_address],
                destinations=[work["address"]],
                mode="transit",
                language="de",
            )
            el = dm_transit["rows"][0]["elements"][0]
            if el["status"] == "OK":
                entry["transit_time"] = el["duration"]["text"]
                entry["transit_distance"] = el["distance"]["text"]
            else:
                entry["transit_time"] = "N/A"
        except Exception as e:
            entry["transit_time"] = f"Error: {e}"

        results.append(entry)
    return results


def _web_search_area(address: str) -> str:
    """Search the web for general information about the area."""
    try:
        serper = GoogleSerperAPIWrapper()
        query = f"{address} Wohngegend Bewertung Familie Lebensqualität"
        return serper.run(query)
    except Exception as e:
        return f"Web search failed: {e}"


def _generate_map(origin_lat: float, origin_lng: float, address: str,
                  amenities: list[dict], commutes: list[dict]) -> str:
    """Generate an interactive HTML map with all points of interest and save to sandbox."""
    markers_js = []

    # Home marker
    popup_home = f"<b>Home</b><br>{address}"
    markers_js.append(
        f'L.marker([{origin_lat}, {origin_lng}], {{icon: homeIcon}})'
        f'.addTo(map).bindPopup({json.dumps(popup_home)});'
    )

    # Amenity markers
    for a in amenities:
        if "error" in a or "lat" not in a:
            continue
        color = _MARKER_COLORS.get(a["category"], "#999")
        popup = (
            f"<b>{a['category']}</b><br>"
            f"{a['name']}<br>"
            f"{a['address']}<br>"
            f"Walking: {a['walking_time']} ({a['walking_distance']})"
        )
        markers_js.append(
            f'L.circleMarker([{a["lat"]}, {a["lng"]}], '
            f'{{radius: 10, fillColor: "{color}", color: "#fff", weight: 2, '
            f'opacity: 1, fillOpacity: 0.85}})'
            f'.addTo(map).bindPopup({json.dumps(popup)});'
        )

    # Work markers
    for c in commutes:
        if "lat" not in c:
            continue
        color = _MARKER_COLORS.get(c["label"], "#333")
        popup = (
            f"<b>{c['label']}</b><br>"
            f"{c['address']}<br>"
            f"Car: {c.get('driving_time', 'N/A')}<br>"
            f"Public Transport: {c.get('transit_time', 'N/A')}"
        )
        markers_js.append(
            f'L.marker([{c["lat"]}, {c["lng"]}], {{icon: workIcon}})'
            f'.addTo(map).bindPopup({json.dumps(popup)});'
        )

    # Build legend entries
    legend_items = []
    legend_items.append('<i style="background:#e74c3c"></i> Home')
    for a in amenities:
        if "error" not in a:
            color = _MARKER_COLORS.get(a["category"], "#999")
            legend_items.append(f'<i style="background:{color}"></i> {a["category"]}')
    for c in commutes:
        if "lat" in c:
            legend_items.append(f'<i style="background:{_MARKER_COLORS.get(c["label"], "#333")}"></i> {c["label"]} (Work)')

    legend_html = "<br>".join(legend_items)
    markers_block = "\n    ".join(markers_js)

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Apartment Search Map — {address}</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ width: 100%; height: 100vh; }}
        .legend {{
            background: white; padding: 10px 14px; border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2); line-height: 22px;
            font: 13px/1.5 -apple-system, Arial, sans-serif;
        }}
        .legend i {{
            width: 14px; height: 14px; display: inline-block;
            margin-right: 6px; border-radius: 50%; vertical-align: middle;
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    <script>
    var map = L.map('map').setView([{origin_lat}, {origin_lng}], 14);
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 19
    }}).addTo(map);

    var homeIcon = L.divIcon({{
        html: '<div style="background:#e74c3c;width:20px;height:20px;border-radius:50%;border:3px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,0.4);"></div>',
        className: '', iconSize: [26, 26], iconAnchor: [13, 13], popupAnchor: [0, -15]
    }});
    var workIcon = L.divIcon({{
        html: '<div style="background:#1a1a2e;width:16px;height:16px;border-radius:3px;border:2px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,0.3);"></div>',
        className: '', iconSize: [20, 20], iconAnchor: [10, 10], popupAnchor: [0, -12]
    }});

    {markers_block}

    // Fit map to show all markers
    var allCoords = [[{origin_lat}, {origin_lng}]];
    map.eachLayer(function(layer) {{
        if (layer.getLatLng) allCoords.push([layer.getLatLng().lat, layer.getLatLng().lng]);
    }});
    if (allCoords.length > 1) map.fitBounds(allCoords, {{padding: [40, 40]}});

    // Legend
    var legend = L.control({{position: 'bottomright'}});
    legend.onAdd = function() {{
        var div = L.DomUtil.create('div', 'legend');
        div.innerHTML = '<b>Legend</b><br>{legend_html}';
        return div;
    }};
    legend.addTo(map);
    </script>
</body>
</html>"""

    os.makedirs("sandbox", exist_ok=True)
    map_path = os.path.join("sandbox", "apartment_search_map.html")
    with open(map_path, "w", encoding="utf-8") as f:
        f.write(html)

    return map_path


def apartment_search(address: str) -> str:
    """Perform a comprehensive apartment search analysis for a given address.
    Finds the nearest family-relevant amenities (Grundschule, Kita, Supermarket, Cafe,
    Playground, Restaurant) with walking times, calculates commute times by car and
    public transport to BMW and Workday offices, gathers general area information,
    and generates an interactive map showing all points of interest.
    Pass the full address, e.g. 'Leopoldstraße 97, München'.
    """
    gmaps = _init_client()

    # Geocode origin for map
    geocode_result = gmaps.geocode(address)
    if not geocode_result:
        return f"Error: Could not geocode address '{address}'"
    origin_loc = geocode_result[0]["geometry"]["location"]

    # 1. Find nearest amenities with walking times
    amenities = []
    for label, place_type in AMENITY_CATEGORIES:
        result = _find_nearest(gmaps, address, label, place_type)
        amenities.append(result)

    # 2. Calculate commute times to work addresses
    commutes = _commute_times(gmaps, address, WORK_ADDRESSES)

    # 3. Web search for general area information
    area_info = _web_search_area(address)

    # 4. Generate interactive map
    map_path = _generate_map(origin_loc["lat"], origin_loc["lng"], address, amenities, commutes)

    # 5. Build report
    report_lines = []
    report_lines.append(f"# Apartment Search Report: {address}")
    report_lines.append("")

    report_lines.append("## Nearby Amenities (Walking)")
    report_lines.append("")
    for a in amenities:
        if "error" in a:
            report_lines.append(f"- **{a['category']}**: {a['error']}")
        else:
            report_lines.append(
                f"- **{a['category']}**: {a['name']} ({a['address']}) — "
                f"Walking: {a['walking_time']} ({a['walking_distance']})"
            )
    report_lines.append("")

    report_lines.append("## Commute to Work")
    report_lines.append("")
    for c in commutes:
        report_lines.append(f"### {c['label']} — {c['address']}")
        report_lines.append(f"- Car: {c.get('driving_time', 'N/A')} ({c.get('driving_distance', '')})")
        report_lines.append(f"- Public Transport: {c.get('transit_time', 'N/A')} ({c.get('transit_distance', '')})")
        report_lines.append("")

    report_lines.append("## Area Information")
    report_lines.append("")
    report_lines.append(area_info)

    report_lines.append("")
    report_lines.append(f"## Interactive Map")
    report_lines.append("")
    report_lines.append(f"An interactive map with all points of interest has been saved to: **{map_path}**")
    report_lines.append("Open it in a browser to explore the locations.")

    return "\n".join(report_lines)
