"""Location tools: apartment search, Google Places."""

import os

from langchain_core.tools import Tool


def get_tools():
    """Return location tools (conditional on API keys being set)."""
    tools = []

    if os.getenv("GPLACES_API_KEY"):
        from langchain_google_community import GooglePlacesTool
        tools.append(GooglePlacesTool())

    if os.getenv("GOOGLE_API_KEY") or os.getenv("GPLACES_API_KEY"):
        from apartment_search import apartment_search

        tools.append(Tool(
            name="apartment_search",
            func=apartment_search,
            description=(
                "Perform a comprehensive apartment/address search analysis for families. "
                "Finds the nearest Grundschule, Kita, Supermarket, Cafe, Playground, and Restaurant "
                "with walking times, calculates commute times by car and public transport to "
                "BMW (Bremer Str. 6, München) and Workday (Streitfeldstraße 19, München), "
                "and gathers general area information. "
                "Pass the full address, e.g. 'Leopoldstraße 97, München'."
            ),
        ))

    return tools
