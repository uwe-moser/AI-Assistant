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

    def test_returns_coordinates(self, mock_gmaps):
        from apartment_search import _find_nearest

        result = _find_nearest(mock_gmaps, "Leopoldstr. 97, München", "Cafe", "cafe")

        assert "lat" in result
        assert "lng" in result
        assert result["lat"] == 48.164
        assert result["lng"] == 11.587

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

    def test_returns_coordinates_for_work_addresses(self, mock_gmaps):
        from apartment_search import _commute_times

        results = _commute_times(mock_gmaps, "Test", [{"label": "Office", "address": "Addr"}])

        assert "lat" in results[0]
        assert "lng" in results[0]

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
# _generate_map
# ===================================================================

class TestGenerateMap:

    def test_creates_html_file(self, sandbox_cwd):
        from apartment_search import _generate_map

        amenities = [{"category": "Cafe", "name": "Test Cafe", "address": "Street 1",
                       "walking_time": "3 Min.", "walking_distance": "250 m",
                       "lat": 48.165, "lng": 11.588}]
        commutes = [{"label": "BMW", "address": "Bremer Str. 6", "lat": 48.18, "lng": 11.56,
                      "driving_time": "15 Min.", "transit_time": "25 Min."}]

        path = _generate_map(48.1634, 11.5861, "Test Address", amenities, commutes)

        assert os.path.isfile(path)
        with open(path, encoding="utf-8") as f:
            html = f.read()
        assert "leaflet" in html.lower()
        assert "Test Address" in html
        assert "Test Cafe" in html
        assert "BMW" in html

    def test_handles_amenities_with_errors(self, sandbox_cwd):
        from apartment_search import _generate_map

        amenities = [{"category": "Kita", "error": "Not found"}]
        path = _generate_map(48.16, 11.58, "Addr", amenities, [])

        assert os.path.isfile(path)

    def test_map_contains_legend(self, sandbox_cwd):
        from apartment_search import _generate_map

        amenities = [{"category": "Supermarket", "name": "Aldi", "address": "St 1",
                       "walking_time": "5 Min.", "walking_distance": "400 m",
                       "lat": 48.165, "lng": 11.588}]
        path = _generate_map(48.16, 11.58, "Addr", amenities, [])

        with open(path, encoding="utf-8") as f:
            html = f.read()
        assert "Legend" in html
        assert "Supermarket" in html


# ===================================================================
# apartment_search (full integration with mocks)
# ===================================================================

class TestApartmentSearch:

    def test_returns_complete_report(self, mock_gmaps, sandbox_cwd):
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
        assert "Interactive Map" in result
        assert "apartment_search_map.html" in result

    def test_report_contains_all_amenity_categories(self, mock_gmaps, sandbox_cwd):
        from apartment_search import apartment_search, AMENITY_CATEGORIES

        with patch("apartment_search._init_client", return_value=mock_gmaps), \
             patch("apartment_search._web_search_area", return_value=""):
            result = apartment_search("Test Address")

        for label, _ in AMENITY_CATEGORIES:
            assert label in result

    def test_report_contains_both_work_addresses(self, mock_gmaps, sandbox_cwd):
        from apartment_search import apartment_search

        with patch("apartment_search._init_client", return_value=mock_gmaps), \
             patch("apartment_search._web_search_area", return_value=""):
            result = apartment_search("Test Address")

        assert "BMW" in result
        assert "Workday" in result

    def test_generates_map_file(self, mock_gmaps, sandbox_cwd):
        from apartment_search import apartment_search

        with patch("apartment_search._init_client", return_value=mock_gmaps), \
             patch("apartment_search._web_search_area", return_value=""):
            apartment_search("Test Address")

        assert (sandbox_cwd / "apartment_search_map.html").is_file()

    def test_no_api_key_raises_error(self):
        from apartment_search import apartment_search

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RuntimeError, match="No Google API key"):
                apartment_search("Test Address")

    def test_geocode_failure_returns_error(self, mock_gmaps):
        from apartment_search import apartment_search

        mock_gmaps.geocode.return_value = []
        with patch("apartment_search._init_client", return_value=mock_gmaps):
            result = apartment_search("Nowhere")

        assert "Error" in result
        assert "geocode" in result.lower()
