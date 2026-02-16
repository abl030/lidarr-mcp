"""Tests for GH Issue #4: Batch operations, command polling, metadata profiles, monitor consistency.

Covers:
- Feature 1: lidarr_monitor_album auto-monitors parent artists
- Feature 1: lidarr_grab_album ensures artist is monitored
- Feature 1: Monitor album workflow hint mentions auto-monitoring
- Feature 2: lidarr_update_albums_monitored exists with expected params/docstring
- Feature 3: _poll_command helper exists
- Feature 3: Command tools have wait/wait_timeout params and polling logic
- Feature 3: Generic lidarr_create_command has wait params
- Feature 4: _summarize_metadata_profile helper exists
- Feature 4: Metadata profile list uses summarizer
- Feature 4: Summarizer extracts allowed type names
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

from generator.codegen import generate
from generator.context_builder import build_context
from generator.loader import load_spec


def _get_generated_source() -> str:
    """Generate server.py into a temp dir and return the source."""
    spec = load_spec()
    ctx = build_context(spec)
    with tempfile.TemporaryDirectory() as tmpdir:
        from generator import codegen

        old_dir = codegen.OUTPUT_DIR
        codegen.OUTPUT_DIR = Path(tmpdir)
        try:
            generate(ctx)
            return (Path(tmpdir) / "server.py").read_text()
        finally:
            codegen.OUTPUT_DIR = old_dir


def _get_func_body(source: str, func_name: str) -> str:
    """Extract a function body from source by name."""
    match = re.search(rf"async def {func_name}\(", source)
    assert match, f"{func_name} not found in generated source"
    next_func = re.search(r"\n(?:    )?(?:async def |if |@mcp\.tool)", source[match.end():])
    if next_func:
        return source[match.start():match.end() + next_func.start()]
    return source[match.start():]


def _get_func_sig(source: str, func_name: str) -> str:
    """Extract a function signature from source by name."""
    match = re.search(rf"async def {func_name}\(", source)
    assert match, f"{func_name} not found in generated source"
    func_end = source.find(") ->", match.start())
    return source[match.start():func_end]


# ---------------------------------------------------------------------------
# Feature 1: Monitor consistency
# ---------------------------------------------------------------------------


def test_monitor_album_auto_monitors_artist():
    """lidarr_monitor_album should contain artist-auto-monitoring logic."""
    source = _get_generated_source()
    body = _get_func_body(source, "lidarr_monitor_album")
    assert "_artist_ids_to_check" in body
    assert '"monitored"' in body or "'monitored'" in body
    assert '/api/v1/artist/' in body


def test_grab_album_ensures_artist_monitored():
    """lidarr_grab_album should check and monitor parent artist."""
    source = _get_generated_source()
    # Find the full grab_album function including body (it's a template, not generated)
    match = re.search(r"async def lidarr_grab_album\(", source)
    assert match
    # Find the next top-level @mcp.tool or top-level function
    next_tool = re.search(r"\n@mcp\.tool\(\)|^@mcp\.tool\(\)", source[match.end():], re.MULTILINE)
    if next_tool:
        body = source[match.start():match.end() + next_tool.start()]
    else:
        body = source[match.start():]
    assert "Ensure parent artist" in body or "artist is monitored" in body or "Step 4b" in body
    assert "/api/v1/artist/" in body


def test_monitor_album_workflow_hint():
    """lidarr_monitor_album docstring should mention auto-monitoring."""
    source = _get_generated_source()
    body = _get_func_body(source, "lidarr_monitor_album")
    doc_start = body.find('"""')
    doc_end = body.find('"""', doc_start + 3)
    docstring = body[doc_start:doc_end]
    assert "automatically" in docstring.lower() or "auto" in docstring.lower()
    assert "artist" in docstring.lower()


# ---------------------------------------------------------------------------
# Feature 2: lidarr_update_albums_monitored
# ---------------------------------------------------------------------------


def test_update_albums_monitored_exists():
    """lidarr_update_albums_monitored should exist in generated source."""
    source = _get_generated_source()
    assert "async def lidarr_update_albums_monitored(" in source


def test_update_albums_monitored_params():
    """lidarr_update_albums_monitored should have expected parameters."""
    source = _get_generated_source()
    sig = _get_func_sig(source, "lidarr_update_albums_monitored")
    assert "albumIds: list[int]" in sig
    assert "monitored: bool" in sig
    assert "ensure_artist_monitored: bool" in sig
    assert "confirm: bool" in sig


def test_update_albums_monitored_docstring():
    """lidarr_update_albums_monitored should document return format and workflow."""
    source = _get_generated_source()
    body = _get_func_body(source, "lidarr_update_albums_monitored")
    doc_start = body.find('"""')
    doc_end = body.find('"""', doc_start + 3)
    docstring = body[doc_start:doc_end]
    assert "batch" in docstring.lower() or "Batch" in docstring
    assert "lidarr_grab_album" in docstring
    assert "ok" in docstring or "count" in docstring


def test_update_album_hint_mentions_batch_tool():
    """lidarr_update_album workflow hint should mention lidarr_update_albums_monitored."""
    source = _get_generated_source()
    body = _get_func_body(source, "lidarr_update_album")
    doc_start = body.find('"""')
    doc_end = body.find('"""', doc_start + 3)
    docstring = body[doc_start:doc_end]
    assert "lidarr_update_albums_monitored" in docstring


# ---------------------------------------------------------------------------
# Feature 3: Command polling
# ---------------------------------------------------------------------------


def test_poll_command_helper_exists():
    """_poll_command helper should exist in generated source."""
    source = _get_generated_source()
    assert "async def _poll_command(" in source


def test_command_tool_has_wait_param():
    """lidarr_command_album_search should have wait: bool = False."""
    source = _get_generated_source()
    sig = _get_func_sig(source, "lidarr_command_album_search")
    assert "wait: bool = False" in sig


def test_command_tool_has_wait_timeout_param():
    """lidarr_command_album_search should have wait_timeout: int = 30."""
    source = _get_generated_source()
    sig = _get_func_sig(source, "lidarr_command_album_search")
    assert "wait_timeout: int = 30" in sig


def test_command_tool_poll_logic():
    """Command tool body should call _poll_command when wait=True."""
    source = _get_generated_source()
    body = _get_func_body(source, "lidarr_command_album_search")
    assert "_poll_command" in body
    assert "wait" in body


def test_generic_create_command_has_wait():
    """lidarr_create_command should have wait and wait_timeout params."""
    source = _get_generated_source()
    sig = _get_func_sig(source, "lidarr_create_command")
    assert "wait: bool = False" in sig
    assert "wait_timeout: int = 30" in sig


def test_command_docstring_mentions_wait():
    """Command tool docstrings should document wait and wait_timeout."""
    source = _get_generated_source()
    body = _get_func_body(source, "lidarr_command_album_search")
    doc_start = body.find('"""')
    doc_end = body.find('"""', doc_start + 3)
    docstring = body[doc_start:doc_end]
    assert "wait" in docstring.lower()
    assert "poll" in docstring.lower() or "timeout" in docstring.lower()


# ---------------------------------------------------------------------------
# Feature 4: Metadata profile summary
# ---------------------------------------------------------------------------


def test_summarize_metadata_profile_helper():
    """_summarize_metadata_profile should exist in generated source."""
    source = _get_generated_source()
    assert "def _summarize_metadata_profile(" in source


def test_metadata_profile_list_uses_summarize():
    """lidarr_list_metadata_profiles body should reference _summarize_metadata_profile."""
    source = _get_generated_source()
    body = _get_func_body(source, "lidarr_list_metadata_profiles")
    assert "_summarize_metadata_profile" in body


def test_summarize_extracts_allowed_types():
    """_summarize_metadata_profile should extract allowed type names."""
    source = _get_generated_source()
    ns: dict = {}
    exec(compile(source, "<test>", "exec"), ns)

    fn = ns["_summarize_metadata_profile"]
    profile = {
        "id": 1,
        "name": "Standard",
        "primaryAlbumTypes": [
            {"albumType": {"name": "Album"}, "allowed": True},
            {"albumType": {"name": "EP"}, "allowed": False},
            {"albumType": {"name": "Single"}, "allowed": True},
        ],
        "secondaryAlbumTypes": [
            {"albumType": {"name": "Studio"}, "allowed": True},
            {"albumType": {"name": "Live"}, "allowed": False},
        ],
        "releaseStatuses": [
            {"releaseStatus": {"name": "Official"}, "allowed": True},
            {"releaseStatus": {"name": "Bootleg"}, "allowed": False},
        ],
    }
    result = fn(profile)
    assert result["id"] == 1
    assert result["name"] == "Standard"
    assert result["primaryAlbumTypes"] == ["Album", "Single"]
    assert result["secondaryAlbumTypes"] == ["Studio"]
    assert result["releaseStatuses"] == ["Official"]


def test_metadata_profile_hint():
    """lidarr_list_metadata_profiles docstring should mention allowed types."""
    source = _get_generated_source()
    body = _get_func_body(source, "lidarr_list_metadata_profiles")
    doc_start = body.find('"""')
    doc_end = body.find('"""', doc_start + 3)
    docstring = body[doc_start:doc_end]
    assert "allowedTypes" in docstring or "allowed" in docstring.lower()
