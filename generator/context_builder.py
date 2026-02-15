"""Build Jinja2 template context from parsed OpenAPI spec.

Assigns each operation to a module, builds tool definitions,
and assembles the full context dict for server.py.j2.
"""

from __future__ import annotations

from typing import Any

# Module assignment by API path prefix (longest prefix match)
_PATH_TO_MODULE: dict[str, str] = {
    "/api/v1/artist": "artist",
    "/api/v1/album": "album",
    "/api/v1/track": "track",
    "/api/v1/trackfile": "track",
    "/api/v1/release": "release",
    "/api/v1/queue": "queue",
    "/api/v1/command": "command",
    "/api/v1/qualityprofile": "quality",
    "/api/v1/customformat": "quality",
    "/api/v1/wanted": "wanted",
    "/api/v1/history": "history",
    "/api/v1/calendar": "calendar",
    "/feed/v1/calendar": "calendar",
    "/api/v1/indexer": "indexer",
    "/api/v1/downloadclient": "downloadclient",
    "/api/v1/importlist": "importlist",
    "/api/v1/importlistexclusion": "importlist",
    "/api/v1/manualimport": "command",
    "/api/v1/albumstudio": "album",
    "/api/v1/rename": "command",
    "/api/v1/retag": "command",
    "/api/v1/rootfolder": "system",
    "/api/v1/tag": "system",
    "/api/v1/health": "system",
    "/api/v1/system": "system",
    "/api/v1/diskspace": "system",
    "/api/v1/log": "system",
    "/api/v1/blocklist": "system",
    "/api/v1/notification": "system",
    "/api/v1/metadata": "system",
    "/api/v1/metadataprofile": "system",
    "/api/v1/delayprofile": "quality",
    "/api/v1/config": "config",
    "/api/v1/filesystem": "system",
    "/api/v1/localization": "system",
    "/api/v1/language": "system",
    "/api/v1/parse": "system",
    "/api/v1/search": "artist",
    "/api/v1/update": "system",
    "/api/v1/customfilter": "system",
    "/api/v1/autotagging": "system",
    "/api/v1/indexerflag": "indexer",
    "/login": "auth",
    "/logout": "auth",
    "/api": "system",
}


def path_to_module(path: str) -> str:
    """Map an API path to its module using longest prefix match."""
    best_match = "system"  # default
    best_len = 0
    for prefix, module in _PATH_TO_MODULE.items():
        if path.startswith(prefix) and len(prefix) > best_len:
            best_match = module
            best_len = len(prefix)
    return best_match


def build_context(spec: dict[str, Any]) -> dict[str, Any]:
    """Build the full template context from the OpenAPI spec.

    Returns a dict ready to pass to the Jinja2 template.
    """
    # TODO: Implement in Sprint 1
    return {
        "tools": [],
        "modules": {},
        "tool_count": 0,
        "lidarr_version": spec.get("info", {}).get("version", "unknown"),
    }
