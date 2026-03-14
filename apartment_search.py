"""
Apartment Search Agent
Evaluates a residential address for family suitability by:
- Finding the nearest Grundschule, Kita, Supermarket, Cafe, Playground, Restaurant
  and calculating walking time to each
- Calculating driving and public transport time to predefined work addresses
- Gathering general area information via web search
"""

import os
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


def _init_client():
    api_key = os.getenv("GPLACES_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("No Google API key found. Set GOOGLE_API_KEY or GPLACES_API_KEY in .env")
    return googlemaps.Client(key=api_key)


def _find_nearest(gmaps, origin_address: str, category_label: str, place_type: str, radius: int = 2000):
    """Find the nearest place of a given type and return its name, address, and walking distance."""
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
                }

    return best or {"category": category_label, "error": f"Could not calculate walking time to any {category_label}"}


def _commute_times(gmaps, origin_address: str, work_addresses: list[dict]):
    """Calculate driving and public transport times from origin to each work address."""
    results = []
    for work in work_addresses:
        entry = {"label": work["label"], "address": work["address"]}

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


def apartment_search(address: str) -> str:
    """Perform a comprehensive apartment search analysis for a given address.
    Finds the nearest family-relevant amenities (Grundschule, Kita, Supermarket, Cafe,
    Playground, Restaurant) with walking times, calculates commute times by car and
    public transport to BMW and Workday offices, and gathers general area information.
    Pass the full address, e.g. 'Leopoldstraße 97, München'.
    """
    gmaps = _init_client()

    # 1. Find nearest amenities with walking times
    amenities = []
    for label, place_type in AMENITY_CATEGORIES:
        result = _find_nearest(gmaps, address, label, place_type)
        amenities.append(result)

    # 2. Calculate commute times to work addresses
    commutes = _commute_times(gmaps, address, WORK_ADDRESSES)

    # 3. Web search for general area information
    area_info = _web_search_area(address)

    # 4. Build report
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

    return "\n".join(report_lines)
