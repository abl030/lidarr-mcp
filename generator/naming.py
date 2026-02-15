"""Convert operationIds to MCP tool names.

Pattern: lidarr_{verb}_{resource}
  - GET singular -> get
  - GET plural -> list
  - POST -> create
  - PUT -> update
  - DELETE -> delete

Examples:
  - GET /api/v1/artist -> lidarr_list_artists
  - GET /api/v1/artist/{id} -> lidarr_get_artist
  - POST /api/v1/artist -> lidarr_create_artist
  - PUT /api/v1/artist/{id} -> lidarr_update_artist
  - DELETE /api/v1/artist/{id} -> lidarr_delete_artist
  - GET /api/v1/artist/lookup -> lidarr_lookup_artist
  - PUT /api/v1/album/monitor -> lidarr_monitor_albums
"""

from __future__ import annotations

import re


def build_tool_name(method: str, path: str, operation_id: str | None = None) -> str:
    """Build a tool name from HTTP method and path.

    Returns a name like 'lidarr_list_artists' or 'lidarr_get_artist'.
    """
    # TODO: Implement full naming logic in Sprint 1
    # For now, return a placeholder based on operationId or path
    if operation_id:
        # Convert camelCase operationId to snake_case
        name = re.sub(r"(?<!^)(?=[A-Z])", "_", operation_id).lower()
        return f"lidarr_{name}"

    # Fallback: derive from path
    parts = path.strip("/").replace("api/v1/", "").split("/")
    clean = "_".join(p for p in parts if not p.startswith("{"))
    verb_map = {"get": "get", "post": "create", "put": "update", "delete": "delete"}
    verb = verb_map.get(method.lower(), method.lower())
    return f"lidarr_{verb}_{clean}"
