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


def test_lookup_uses_sub_action_verb():
    """Lookup is a sub-action that becomes the verb: lidarr_lookup_artist."""
    name = build_tool_name("GET", "/api/v1/artist/lookup")
    assert name == "lidarr_lookup_artist"


def test_sub_resource_path():
    """Nested paths like /wanted/missing include both segments."""
    name = build_tool_name("GET", "/api/v1/wanted/missing")
    assert name == "lidarr_list_wanted_missing"


def test_monitor_sub_action():
    """Monitor is a sub-action verb."""
    name = build_tool_name("PUT", "/api/v1/album/monitor")
    assert name == "lidarr_monitor_album"


def test_editor_sub_action():
    """Editor maps to 'edit' verb with plural resource."""
    name = build_tool_name("POST", "/api/v1/artist/editor")
    assert name == "lidarr_edit_artists"


def test_delete_artist():
    name = build_tool_name("DELETE", "/api/v1/artist/{id}")
    assert name == "lidarr_delete_artist"


def test_update_artist():
    name = build_tool_name("PUT", "/api/v1/artist/{id}")
    assert name == "lidarr_update_artist"


def test_config_sub_resource():
    """Config sub-resources include the sub-path."""
    name = build_tool_name("GET", "/api/v1/config/host")
    assert name == "lidarr_list_config_host"


def test_system_sub_resource():
    name = build_tool_name("GET", "/api/v1/system/status")
    assert name == "lidarr_list_system_status"
