"""Tests for module assignment.

Verifies that API paths map to the correct modules.
"""

from generator.context_builder import path_to_module


def test_artist_module():
    assert path_to_module("/api/v1/artist") == "artist"
    assert path_to_module("/api/v1/artist/123") == "artist"
    assert path_to_module("/api/v1/artist/lookup") == "artist"


def test_album_module():
    assert path_to_module("/api/v1/album") == "album"
    assert path_to_module("/api/v1/album/123") == "album"
    assert path_to_module("/api/v1/album/monitor") == "album"
    assert path_to_module("/api/v1/albumstudio") == "album"


def test_release_module():
    assert path_to_module("/api/v1/release") == "release"


def test_queue_module():
    assert path_to_module("/api/v1/queue") == "queue"
    assert path_to_module("/api/v1/queue/123") == "queue"


def test_command_module():
    assert path_to_module("/api/v1/command") == "command"
    assert path_to_module("/api/v1/manualimport") == "command"


def test_quality_module():
    assert path_to_module("/api/v1/qualityprofile") == "quality"
    assert path_to_module("/api/v1/customformat") == "quality"
    assert path_to_module("/api/v1/delayprofile") == "quality"


def test_system_module():
    assert path_to_module("/api/v1/health") == "system"
    assert path_to_module("/api/v1/rootfolder") == "system"
    assert path_to_module("/api/v1/tag") == "system"
    assert path_to_module("/api/v1/system/backup") == "system"


def test_config_module():
    assert path_to_module("/api/v1/config/host") == "config"


def test_unknown_defaults_to_system():
    assert path_to_module("/api/v1/something/unknown") == "system"
