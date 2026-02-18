"""Build Jinja2 template context from parsed OpenAPI spec.

Assigns each operation to a module, builds tool definitions,
and assembles the full context dict for server.py.j2.
"""

from __future__ import annotations

from typing import Any

from .loader import get_paths
from .naming import build_tool_name
from .schema_parser import get_response_type, parse_parameters

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
    "/api/v1/qualitydefinition": "quality",
    "/api/v1/releaseprofile": "release",
    "/api/v1/remotepathmapping": "system",
    "/api/v1/mediacover": "system",
    "/login": "auth",
    "/logout": "auth",
    "/api": "system",
}

# HTTP methods considered mutations (require confirm gate)
_MUTATION_METHODS = {"post", "put", "patch", "delete"}

# Workflow hints appended to mutation tool docstrings (BP #5)
_WORKFLOW_HINTS: dict[str, str] = {
    "lidarr_create_artist": (
        "Note: Use the 'monitor' shorthand param instead of addOptions.monitor."
        " Valid values: all, future, missing, existing, latest, first, none."
        " Default monitors entire discography."
        " Warning: monitor='none' may still mark albums as monitored"
        " (Lidarr API bug). Workaround: create artist, then batch-unmonitor"
        " albums, then selectively monitor. Or use lidarr_grab_album which"
        " handles this automatically. foreignArtistId accepts MusicBrainz"
        " artist IDs for direct creation when Lidarr search API is unavailable."
        " Use lidarr_search_album to browse an artist's albums before adding."
    ),
    "lidarr_monitor_album": (
        "Note: Call lidarr_create_command with name='AlbumSearch' to trigger"
        " a download search. When setting monitored=True, this tool"
        " automatically ensures the parent artist is also monitored"
        " (required for soularr and other automation tools)."
    ),
    "lidarr_update_artist": (
        "Note: Call lidarr_create_command with name='RefreshArtist' after"
        " updating. Uses merge=True by default to auto-fetch the current object."
    ),
    "lidarr_update_album": (
        "Note: Call lidarr_create_command with name='RefreshArtist' after"
        " updating. Uses merge=True by default to auto-fetch the current object."
        " For batch album monitoring, use lidarr_update_albums_monitored instead."
        " To select a specific release, use lidarr_set_album_release."
    ),
    "lidarr_lookup_album": (
        "Note: This endpoint only works with MusicBrainz release group IDs"
        " (term=lidarr:MBID). For text-based album search, use"
        " lidarr_search_album instead."
    ),
    "lidarr_delete_artist": (
        "Note: Files may remain on disk unless deleteFiles=True."
    ),
    "lidarr_list_metadata_profiles": (
        "Note: Responses include summarized primaryAlbumTypes,"
        " secondaryAlbumTypes, and releaseStatuses showing only"
        " allowed type names instead of the full objects."
    ),
}

# Dedicated command types for POST /api/v1/command (polymorphic endpoint)
_COMMAND_TYPES: list[dict[str, Any]] = [
    {
        "name": "lidarr_command_album_search",
        "command_name": "AlbumSearch",
        "description": (
            "Trigger a download search for specific albums."
            " Set wait=True to poll until completion (default timeout 30s)."
            " If unexpected errors occur, call lidarr_report_issue."
        ),
        "params": [
            {
                "name": "albumIds",
                "type": "list[int]",
                "required": True,
                "default": None,
                "description": "List of album IDs to search for downloads.",
                "enum": None,
                "location": "body",
                "nullable": False,
            },
        ],
    },
    {
        "name": "lidarr_command_artist_search",
        "command_name": "ArtistSearch",
        "description": (
            "Trigger a download search for all monitored albums of an artist."
            " Set wait=True to poll until completion (default timeout 30s)."
            " If unexpected errors occur, call lidarr_report_issue."
        ),
        "params": [
            {
                "name": "artistId",
                "type": "int",
                "required": True,
                "default": None,
                "description": "The artist ID to search for.",
                "enum": None,
                "location": "body",
                "nullable": False,
            },
        ],
    },
    {
        "name": "lidarr_command_refresh_artist",
        "command_name": "RefreshArtist",
        "description": (
            "Refresh artist metadata and album list from MusicBrainz."
            " Set wait=True to poll until completion (default timeout 30s)."
            " If unexpected errors occur, call lidarr_report_issue."
        ),
        "params": [
            {
                "name": "artistId",
                "type": "int",
                "required": False,
                "default": None,
                "description": "Artist ID to refresh. Omit to refresh all.",
                "enum": None,
                "location": "body",
                "nullable": False,
            },
        ],
    },
    {
        "name": "lidarr_command_rescan_artist",
        "command_name": "RescanFolders",
        "description": (
            "Rescan an artist's folder on disk for new or changed files."
            " Set wait=True to poll until completion (default timeout 30s)."
            " If unexpected errors occur, call lidarr_report_issue."
        ),
        "params": [
            {
                "name": "artistId",
                "type": "int",
                "required": False,
                "default": None,
                "description": "Artist ID to rescan. Omit to rescan all.",
                "enum": None,
                "location": "body",
                "nullable": False,
            },
        ],
    },
    {
        "name": "lidarr_command_missing_album_search",
        "command_name": "MissingAlbumSearch",
        "description": (
            "Search for all missing (monitored, not downloaded) albums."
            " Set wait=True to poll until completion (default timeout 30s)."
            " If unexpected errors occur, call lidarr_report_issue."
        ),
        "params": [],
    },
    {
        "name": "lidarr_command_rename_files",
        "command_name": "RenameFiles",
        "description": (
            "Rename track files for an artist according to naming settings."
            " Set wait=True to poll until completion (default timeout 120s,"
            " may be slow on NFS)."
            " If unexpected errors occur, call lidarr_report_issue."
        ),
        "params": [
            {
                "name": "artistId",
                "type": "int",
                "required": True,
                "default": None,
                "description": "The artist ID whose files to rename.",
                "enum": None,
                "location": "body",
                "nullable": False,
            },
            {
                "name": "files",
                "type": "list[int]",
                "required": True,
                "default": None,
                "description": "List of track file IDs to rename.",
                "enum": None,
                "location": "body",
                "nullable": False,
            },
        ],
    },
    {
        "name": "lidarr_command_rename_artist",
        "command_name": "RenameArtist",
        "description": (
            "Rename artist folders according to naming settings."
            " Set wait=True to poll until completion (default timeout 120s,"
            " may be slow on NFS)."
            " If unexpected errors occur, call lidarr_report_issue."
        ),
        "params": [
            {
                "name": "artistIds",
                "type": "list[int]",
                "required": True,
                "default": None,
                "description": "List of artist IDs whose folders to rename.",
                "enum": None,
                "location": "body",
                "nullable": False,
            },
        ],
    },
]

# Synthetic extra params injected into specific tools
_EXTRA_PARAMS: dict[str, list[dict[str, Any]]] = {
    "lidarr_create_artist": [
        {
            "name": "monitor",
            "type": "str",
            "required": False,
            "default": None,
            "description": (
                "Shorthand for addOptions.monitor. Valid values: all, future,"
                " missing, existing, first, latest, none."
                " When set, injects into addOptions automatically."
            ),
            "enum": None,
            "location": "synthetic",
            "nullable": False,
        },
    ],
}

# Paths to skip (non-API endpoints, catch-all routes, static content)
_SKIP_PATHS = {
    "/",
    "/api",
    "/content/{path}",
    "/{path}",
    "/ping",
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


def _should_skip_path(path: str) -> bool:
    """Check if a path should be skipped during generation."""
    if path in _SKIP_PATHS:
        return True
    # Skip the catch-all {path} routes
    if path.endswith("/{path}"):
        return True
    return False


def _make_description(
    method: str, path: str, operation: dict, response_type: str, tool_name: str,
) -> str:
    """Build a tool description/docstring."""
    summary = operation.get("summary", "")
    description = operation.get("description", "")

    if summary:
        doc = summary
    elif description:
        doc = description.split(".")[0]
    else:
        # Build from tool name: lidarr_list_artists → "List artists"
        parts = tool_name.replace("lidarr_", "").split("_")
        verb = parts[0].capitalize()
        resource = " ".join(parts[1:])
        has_id = "{id}" in path
        if has_id and method == "get":
            doc = f"Get {resource} by ID"
        elif has_id and method == "delete":
            doc = f"Delete {resource} by ID"
        elif has_id and method in ("put", "patch"):
            doc = f"Update {resource} by ID"
        else:
            doc = f"{verb} {resource}"

    # Add response type hint
    if response_type == "array":
        doc += ". Returns a list."
    elif response_type == "paging":
        doc += ". Returns paginated results."

    # Add error reporting nudge
    doc += " If unexpected errors occur, call lidarr_report_issue."

    # Add workflow hint if one exists for this tool
    hint = _WORKFLOW_HINTS.get(tool_name)
    if hint:
        doc += f" {hint}"

    return doc


def _deduplicate_tool_names(tools: list[dict[str, Any]]) -> None:
    """Ensure all tool names are unique by appending method suffix if needed."""
    seen: dict[str, int] = {}
    for tool in tools:
        name = tool["name"]
        if name in seen:
            seen[name] += 1
            # Append the HTTP method to disambiguate
            tool["name"] = f"{name}_{tool['method']}"
        else:
            seen[name] = 1

    # Second pass: rename the first occurrence too if there were dupes
    name_counts: dict[str, int] = {}
    for tool in tools:
        base = tool["name"]
        if base in name_counts:
            name_counts[base] += 1
        else:
            name_counts[base] = 1

    # Handle remaining collisions with numeric suffix
    final_seen: dict[str, int] = {}
    for tool in tools:
        name = tool["name"]
        if name in final_seen:
            final_seen[name] += 1
            tool["name"] = f"{name}_{final_seen[name]}"
        else:
            final_seen[name] = 1


def build_context(spec: dict[str, Any]) -> dict[str, Any]:
    """Build the full template context from the OpenAPI spec.

    Returns a dict ready to pass to the Jinja2 template.
    """
    paths = get_paths(spec)
    tools: list[dict[str, Any]] = []
    modules: dict[str, list[str]] = {}

    for path, path_item in sorted(paths.items()):
        if _should_skip_path(path):
            continue

        for method in ("get", "post", "put", "delete", "patch"):
            if method not in path_item:
                continue

            operation = path_item[method]
            # Attach method for schema_parser to use
            operation["_method"] = method

            # Build tool name
            name = build_tool_name(method, path)

            # Determine module
            module = path_to_module(path)

            # Parse parameters
            params = parse_parameters(spec, operation, path)

            # Determine response type
            response_type = get_response_type(spec, operation)

            # Is this a list endpoint?
            is_list = response_type in ("array", "paging")

            # Is this a mutation?
            is_mutation = method in _MUTATION_METHODS

            # Build description
            description = _make_description(method, path, operation, response_type, name)

            # Extract tags
            tags = operation.get("tags", [])

            # Flag lookup tools for unicode normalization
            is_lookup = "lookup" in path.split("/")

            tool = {
                "name": name,
                "method": method,
                "path": path,
                "params": params,
                "module": module,
                "is_mutation": is_mutation,
                "is_list": is_list,
                "is_lookup": is_lookup,
                "response_type": response_type,
                "description": description,
                "tags": tags,
            }
            tools.append(tool)

            # Track modules
            if module not in modules:
                modules[module] = []
            modules[module].append(name)

    # Expand POST /api/v1/command into dedicated command-type tools
    for cmd_type in _COMMAND_TYPES:
        cmd_tool = {
            "name": cmd_type["name"],
            "method": "post",
            "path": "/api/v1/command",
            "params": list(cmd_type["params"]),
            "module": "command",
            "is_mutation": True,
            "is_list": False,
            "is_lookup": False,
            "is_command": True,
            "command_name": cmd_type["command_name"],
            "response_type": "object",
            "description": cmd_type["description"],
            "tags": ["Command"],
        }
        tools.append(cmd_tool)
        if "command" not in modules:
            modules["command"] = []
        modules["command"].append(cmd_type["name"])

    # Flag lidarr_create_command as generic command (for wait param)
    # Flag lidarr_list_metadata_profiles for post-processing
    for tool in tools:
        if tool["name"] == "lidarr_create_command":
            tool["is_command_generic"] = True
        if tool["name"] == "lidarr_list_metadata_profiles":
            tool["post_process"] = "metadata_profile"

    # Wire quality profile env-var defaults for lidarr_create_artist
    _ENV_DEFAULTS = {
        "lidarr_create_artist": {
            "qualityProfileId": "LIDARR_DEFAULT_QUALITY_PROFILE_ID",
            "rootFolderPath": "LIDARR_DEFAULT_ROOT_FOLDER",
        },
    }
    for tool in tools:
        env_map = _ENV_DEFAULTS.get(tool["name"])
        if env_map:
            for param in tool["params"]:
                if param["name"] in env_map:
                    param["env_default"] = env_map[param["name"]]

    # Inject synthetic extra params
    for tool in tools:
        extra = _EXTRA_PARAMS.get(tool["name"])
        if extra:
            tool["params"].extend(extra)

    # Deduplicate tool names
    _deduplicate_tool_names(tools)

    return {
        "tools": tools,
        "modules": modules,
        "tool_count": len(tools),
        "lidarr_version": spec.get("info", {}).get("version", "unknown"),
    }
