"""
Unit tests for the apartment_search module.

All Google Maps API calls are mocked to avoid real network requests.
"""

import os
from unittest.mock import MagicMock, patch

import pytest


# ===================================================================
# Helpers
# ===================================================================

def _mock_geocode_result(lat=48.1634, lng=11.5861):
    return [{"geometry": {"location": {"lat": lat, "lng": lng}}}]


def _mock_places_nearby(name="Test Place", vicinity="Test Street 1"):
    return {
        "results": [
            {
                "name": name,
                "vicinity": vicinity,
                "geometry": {"location": {"lat": 48.164, "lng": 11.587}},
            }
        ]
    }


def _mock_distance_matrix(duration_text="5 Min.", duration_value=300,
                           distance_text="400 m", status="OK"):
    return {
        "rows": [
            {
                "elements": [
                    {
                        "status": status,
                        "duration": {"text": duration_text, "value": duration_value},
                        "distance": {"text": distance_text},
                    }
                ]
            }
        ]
    }


@pytest.fixture
def mock_gmaps():
    """Return a mocked googlemaps.Client with sensible defaults."""
    client = MagicMock()
    client.geocode.return_value = _mock_geocode_result()
    client.places_nearby.return_value = _mock_places_nearby()
    client.distance_matrix.return_value = _mock_distance_matrix()
    return client


# ===================================================================
# _find_nearest
# ===================================================================

class TestFindNearest:

    def test_returns_nearest_with_walking_time(self, mock_gmaps):
        from apartment_search import _find_nearest

        result = _find_nearest(mock_gmaps, "Leopoldstr. 97, München", "Supermarket", "supermarket")

        assert result["category"] == "Supermarket"
        assert result["name"] == "Test Place"
        assert "5 Min." in result["walking_time"]
        assert "400 m" in result["walking_distance"]

    def test_geocode_failure_returns_error(self, mock_gmaps):
        from apartment_search import _find_nearest

        mock_gmaps.geocode.return_value = []
        result = _find_nearest(mock_gmaps, "Invalid Address", "Kita", "child_care")

        assert "error" in result
        assert "geocode" in result["error"].lower()

    def test_no_places_found_returns_error(self, mock_gmaps):
        from apartment_search import _find_nearest

        mock_gmaps.places_nearby.return_value = {"results": []}
        result = _find_nearest(mock_gmaps, "Remote Location", "Playground", "playground")

        assert "error" in result
        assert "No Playground found" in result["error"]

    def test_keyword_search_for_child_care(self, mock_gmaps):
        from apartment_search import _find_nearest

        _find_nearest(mock_gmaps, "Test Addr", "Kita", "child_care")

        # child_care is in _KEYWORD_ONLY, so it should use keyword= not type=
        call_kwargs = mock_gmaps.places_nearby.call_args
        assert "keyword" in call_kwargs.kwargs or call_kwargs[1].get("keyword")

    def test_distance_matrix_not_ok_returns_error(self, mock_gmaps):
        from apartment_search import _find_nearest

        mock_gmaps.distance_matrix.return_value = _mock_distance_matrix(status="ZERO_RESULTS")
        result = _find_nearest(mock_gmaps, "Test Addr", "Cafe", "cafe")

        assert "error" in result


# ===================================================================
# _commute_times
# ===================================================================

class TestCommuteTimes:

    def test_returns_driving_and_transit_for_each_work_address(self, mock_gmaps):
        from apartment_search import _commute_times, WORK_ADDRESSES

        results = _commute_times(mock_gmaps, "Leopoldstr. 97, München", WORK_ADDRESSES)

        assert len(results) == 2
        for entry in results:
            assert "driving_time" in entry
            assert "transit_time" in entry
            assert entry["driving_time"] == "5 Min."
            assert entry["transit_time"] == "5 Min."

    def test_handles_api_error_gracefully(self, mock_gmaps):
        from apartment_search import _commute_times

        mock_gmaps.distance_matrix.side_effect = Exception("API Error")
        results = _commute_times(mock_gmaps, "Test", [{"label": "Office", "address": "Addr"}])

        assert len(results) == 1
        assert "Error" in results[0]["driving_time"]

    def test_handles_not_found_status(self, mock_gmaps):
        from apartment_search import _commute_times

        mock_gmaps.distance_matrix.return_value = _mock_distance_matrix(status="NOT_FOUND")
        results = _commute_times(mock_gmaps, "Test", [{"label": "Office", "address": "Addr"}])

        assert results[0]["driving_time"] == "N/A"


# ===================================================================
# apartment_search (full integration with mocks)
# ===================================================================

class TestApartmentSearch:

    def test_returns_complete_report(self, mock_gmaps):
        from apartment_search import apartment_search

        with patch("apartment_search._init_client", return_value=mock_gmaps), \
             patch("apartment_search._web_search_area", return_value="Nice area info"):
            result = apartment_search("Leopoldstraße 97, München")

        assert "Apartment Search Report" in result
        assert "Leopoldstraße 97" in result
        assert "Nearby Amenities" in result
        assert "Commute to Work" in result
        assert "Area Information" in result
        assert "Nice area info" in result

    def test_report_contains_all_amenity_categories(self, mock_gmaps):
        from apartment_search import apartment_search, AMENITY_CATEGORIES

        with patch("apartment_search._init_client", return_value=mock_gmaps), \
             patch("apartment_search._web_search_area", return_value=""):
            result = apartment_search("Test Address")

        for label, _ in AMENITY_CATEGORIES:
            assert label in result

    def test_report_contains_both_work_addresses(self, mock_gmaps):
        from apartment_search import apartment_search

        with patch("apartment_search._init_client", return_value=mock_gmaps), \
             patch("apartment_search._web_search_area", return_value=""):
            result = apartment_search("Test Address")

        assert "BMW" in result
        assert "Workday" in result

    def test_no_api_key_raises_error(self):
        from apartment_search import apartment_search

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RuntimeError, match="No Google API key"):
                apartment_search("Test Address")
