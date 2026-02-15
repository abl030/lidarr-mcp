"""Tests for tool naming conventions.

Verifies that operationIds and paths produce correct tool names.
"""

from generator.naming import build_tool_name


def test_list_artists():
    assert build_tool_name("GET", "/api/v1/artist").startswith("lidarr_")


def test_get_artist_by_id():
    name = build_tool_name("GET", "/api/v1/artist/{id}")
    assert "artist" in name


def test_create_artist():
    name = build_tool_name("POST", "/api/v1/artist")
    assert "create" in name or "artist" in name


def test_lookup_uses_operation_id():
    name = build_tool_name("GET", "/api/v1/artist/lookup", operation_id="getArtistLookup")
    assert name == "lidarr_get_artist_lookup"
