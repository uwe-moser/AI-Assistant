"""Location agent: apartment analysis, Google Places."""

from agents.base import BaseAgent


class LocationAgent(BaseAgent):
    system_prompt = (
        "You are a location and real estate specialist. Analyze addresses "
        "for family suitability, find nearby amenities with walking times, "
        "calculate commute times, and search for places using Google Places."
    )
