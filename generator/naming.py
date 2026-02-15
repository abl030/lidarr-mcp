"""Convert HTTP method + path to MCP tool names.

Pattern: lidarr_{verb}_{resource}
  - GET collection      -> list_{plural}
  - GET collection/{id} -> get_{singular}
  - POST collection     -> create_{singular}
  - PUT collection/{id} -> update_{singular}
  - DELETE col/{id}     -> delete_{singular}
  - GET col/sub-action  -> {sub_action}_{singular}
  - PUT col/action      -> {action}_{singular}

Examples:
  GET  /api/v1/artist           -> lidarr_list_artists
  GET  /api/v1/artist/{id}      -> lidarr_get_artist
  POST /api/v1/artist           -> lidarr_create_artist
  PUT  /api/v1/artist/{id}      -> lidarr_update_artist
  DELETE /api/v1/artist/{id}    -> lidarr_delete_artist
  GET  /api/v1/artist/lookup    -> lidarr_lookup_artist
  PUT  /api/v1/album/monitor    -> lidarr_monitor_album
  GET  /api/v1/wanted/missing   -> lidarr_list_wanted_missing
  POST /api/v1/artist/editor    -> lidarr_edit_artists
"""

from __future__ import annotations

import re

# Sub-actions that become the verb rather than part of the resource
_SUB_ACTION_VERBS: dict[str, str] = {
    "lookup": "lookup",
    "monitor": "monitor",
    "editor": "edit",
}

# Standard HTTP method to verb mapping
_METHOD_VERBS: dict[str, str] = {
    "get": "list",
    "post": "create",
    "put": "update",
    "delete": "delete",
    "patch": "update",
}

# Irregular plurals and known plural forms
_PLURALS: dict[str, str] = {
    "artist": "artists",
    "album": "albums",
    "track": "tracks",
    "release": "releases",
    "queue": "queue",
    "command": "commands",
    "history": "history",
    "health": "health",
    "tag": "tags",
    "notification": "notifications",
    "diskspace": "diskspace",
    "calendar": "calendar",
    "parse": "parse",
    "search": "search",
    "update": "updates",
    "blocklist": "blocklist",
    "backup": "backups",
    "task": "tasks",
    "status": "status",
    "log": "logs",
    "indexer": "indexers",
    "qualityprofile": "quality_profiles",
    "qualitydefinition": "quality_definitions",
    "metadataprofile": "metadata_profiles",
    "customformat": "custom_formats",
    "delayprofile": "delay_profiles",
    "releaseprofile": "release_profiles",
    "downloadclient": "download_clients",
    "importlist": "import_lists",
    "importlistexclusion": "import_list_exclusions",
    "rootfolder": "root_folders",
    "remotepathmapping": "remote_path_mappings",
    "customfilter": "custom_filters",
    "autotagging": "autotagging",
    "filesystem": "filesystem",
    "localization": "localization",
    "language": "languages",
    "manualimport": "manual_import",
    "rename": "rename",
    "retag": "retag",
    "trackfile": "track_files",
    "albumstudio": "album_studio",
    "metadata": "metadata",
    "indexerflag": "indexer_flags",
    "mediacover": "media_cover",
    "wanted": "wanted",
}

# Corresponding singular forms
_SINGULARS: dict[str, str] = {
    "artists": "artist",
    "albums": "album",
    "tracks": "track",
    "releases": "release",
    "commands": "command",
    "tags": "tag",
    "notifications": "notification",
    "backups": "backup",
    "tasks": "task",
    "logs": "log",
    "indexers": "indexer",
    "quality_profiles": "quality_profile",
    "quality_definitions": "quality_definition",
    "metadata_profiles": "metadata_profile",
    "custom_formats": "custom_format",
    "delay_profiles": "delay_profile",
    "release_profiles": "release_profile",
    "download_clients": "download_client",
    "import_lists": "import_list",
    "import_list_exclusions": "import_list_exclusion",
    "root_folders": "root_folder",
    "remote_path_mappings": "remote_path_mapping",
    "custom_filters": "custom_filter",
    "track_files": "track_file",
    "languages": "language",
    "updates": "update",
    "indexer_flags": "indexer_flag",
}


def _pluralize(word: str) -> str:
    """Return the plural form of a resource name."""
    return _PLURALS.get(word, word + "s")


def _singularize(word: str) -> str:
    """Return the singular form of a resource name."""
    if word in _SINGULARS:
        return _SINGULARS[word]
    # Already singular if it's in _PLURALS keys
    if word in _PLURALS:
        return word
    # Fallback: strip trailing 's'
    if word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _camel_to_snake(name: str) -> str:
    """Convert camelCase or PascalCase to snake_case."""
    s1 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    return re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s1).lower()


def _extract_path_parts(path: str) -> list[str]:
    """Extract meaningful path segments, stripping /api/v1/ prefix and {params}."""
    # Strip common prefixes
    for prefix in ("/api/v1/", "/feed/v1/", "/api/"):
        if path.startswith(prefix):
            path = path[len(prefix):]
            break
    else:
        path = path.lstrip("/")

    parts = [p for p in path.split("/") if p and not p.startswith("{")]
    return parts


def build_tool_name(method: str, path: str, operation_id: str | None = None) -> str:
    """Build a tool name from HTTP method and path.

    Returns a name like 'lidarr_list_artists' or 'lidarr_get_artist'.
    """
    method_lower = method.lower()
    parts = _extract_path_parts(path)
    has_id = "{id}" in path or any(p.startswith("{") for p in path.split("/"))

    if not parts:
        # Root path like / or /api
        return f"lidarr_{_METHOD_VERBS.get(method_lower, method_lower)}_root"

    resource = parts[0]  # Primary resource (artist, album, etc.)
    sub_parts = parts[1:]  # Sub-paths (lookup, editor, missing, etc.)

    # Check for sub-action verbs (lookup, monitor, editor)
    if sub_parts and sub_parts[0] in _SUB_ACTION_VERBS:
        verb = _SUB_ACTION_VERBS[sub_parts[0]]
        # "edit" works on collections, "lookup" on singular concept
        if verb == "edit":
            resource_name = _pluralize(resource)
        else:
            resource_name = _singularize(_PLURALS.get(resource, resource))
        return f"lidarr_{verb}_{resource_name}"

    # Sub-resource paths like /wanted/missing, /config/host, /system/status
    if sub_parts:
        # Filter out path params
        clean_subs = [_camel_to_snake(p) for p in sub_parts if not p.startswith("{")]
        if clean_subs:
            sub_resource = "_".join(clean_subs)
            if method_lower == "get" and not has_id:
                verb = "list"
            elif method_lower == "get" and has_id:
                verb = "get"
            else:
                verb = _METHOD_VERBS.get(method_lower, method_lower)
            resource_name = _PLURALS.get(resource, resource)
            return f"lidarr_{verb}_{resource_name}_{sub_resource}"

    # Standard CRUD patterns
    if method_lower == "get":
        if has_id:
            verb = "get"
            resource_name = _singularize(_PLURALS.get(resource, resource))
        else:
            verb = "list"
            resource_name = _pluralize(resource)
    elif method_lower == "post":
        verb = "create"
        resource_name = _singularize(_PLURALS.get(resource, resource))
    elif method_lower in ("put", "patch"):
        verb = "update"
        resource_name = _singularize(_PLURALS.get(resource, resource))
    elif method_lower == "delete":
        verb = "delete"
        resource_name = _singularize(_PLURALS.get(resource, resource))
    else:
        verb = method_lower
        resource_name = _PLURALS.get(resource, resource)

    return f"lidarr_{verb}_{resource_name}"
