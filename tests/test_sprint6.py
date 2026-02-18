"""Tests for Sprint 6: Close Issues #5–#9.

Covers:
- #5: lidarr_create_command body merged flat (not nested under "body" key)
- #5: RenameFiles and RenameArtist dedicated command tools
- #5: Generic command wait_timeout bumped to 120
- #6: lidarr_create_artist has synthetic monitor param
- #6: monitor value injected into addOptions
- #7: lidarr_search_album tool exists with expected params
- #7: lidarr_lookup_album docstring mentions MusicBrainz ID requirement
- #8: lidarr_set_album_release tool exists with expected params
- #9: grab_album auto-detects defaults from root folders
- #9: grab_album re-monitors artist after create
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
    # Match next top-level function, decorator, or if-block
    next_func = re.search(r"\n(?:    )?(?:async def |@mcp\.tool)", source[match.end():])
    if not next_func:
        # Also try matching module gating blocks
        next_func = re.search(r"\nif _module_enabled|^@mcp\.tool\(\)", source[match.end():], re.MULTILINE)
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
# Issue #5: Command body merge + new command types
# ---------------------------------------------------------------------------


def test_create_command_body_merged_flat():
    """lidarr_create_command should use _body.update(body) not _body['body'] = body."""
    source = _get_generated_source()
    body = _get_func_body(source, "lidarr_create_command")
    assert "_body.update(body)" in body
    assert '_body["body"] = body' not in body


def test_rename_files_command_exists():
    """lidarr_command_rename_files should exist in generated output."""
    source = _get_generated_source()
    assert "async def lidarr_command_rename_files(" in source


def test_rename_files_command_params():
    """lidarr_command_rename_files should have artistId and files params."""
    source = _get_generated_source()
    sig = _get_func_sig(source, "lidarr_command_rename_files")
    assert "artistId: int" in sig
    assert "files: list[int]" in sig


def test_rename_artist_command_exists():
    """lidarr_command_rename_artist should exist in generated output."""
    source = _get_generated_source()
    assert "async def lidarr_command_rename_artist(" in source


def test_rename_artist_command_params():
    """lidarr_command_rename_artist should have artistIds param."""
    source = _get_generated_source()
    sig = _get_func_sig(source, "lidarr_command_rename_artist")
    assert "artistIds: list[int]" in sig


def test_generic_command_wait_timeout_120():
    """lidarr_create_command should have wait_timeout default of 120."""
    source = _get_generated_source()
    sig = _get_func_sig(source, "lidarr_create_command")
    assert "wait_timeout: int = 120" in sig


def test_dedicated_command_wait_timeout_30():
    """Dedicated command tools should still have wait_timeout default of 30."""
    source = _get_generated_source()
    sig = _get_func_sig(source, "lidarr_command_album_search")
    assert "wait_timeout: int = 30" in sig


# ---------------------------------------------------------------------------
# Issue #6: create_artist monitor param
# ---------------------------------------------------------------------------


def test_create_artist_monitor_param():
    """lidarr_create_artist should have a synthetic monitor param."""
    source = _get_generated_source()
    sig = _get_func_sig(source, "lidarr_create_artist")
    assert "monitor: str | None = None" in sig


def test_create_artist_monitor_injected():
    """lidarr_create_artist should inject monitor into addOptions."""
    source = _get_generated_source()
    body = _get_func_body(source, "lidarr_create_artist")
    assert 'addOptions["monitor"] = monitor' in body


def test_create_artist_monitor_in_context():
    """The synthetic monitor param should appear in context_builder output."""
    spec = load_spec()
    ctx = build_context(spec)
    tool = next(t for t in ctx["tools"] if t["name"] == "lidarr_create_artist")
    param_names = [p["name"] for p in tool["params"]]
    assert "monitor" in param_names
    monitor_param = next(p for p in tool["params"] if p["name"] == "monitor")
    assert monitor_param["location"] == "synthetic"
    assert "all" in monitor_param["description"]


# ---------------------------------------------------------------------------
# Issue #7: search_album tool + lookup_album docstring
# ---------------------------------------------------------------------------


def test_search_album_tool_exists():
    """lidarr_search_album should exist in generated output."""
    source = _get_generated_source()
    assert "async def lidarr_search_album(" in source


def test_search_album_params():
    """lidarr_search_album should have artist and album params."""
    source = _get_generated_source()
    sig = _get_func_sig(source, "lidarr_search_album")
    assert "artist: str" in sig
    assert 'album: str = ""' in sig


def test_search_album_docstring():
    """lidarr_search_album docstring should explain its purpose."""
    source = _get_generated_source()
    body = _get_func_body(source, "lidarr_search_album")
    doc_start = body.find('"""')
    doc_end = body.find('"""', doc_start + 3)
    docstring = body[doc_start:doc_end]
    assert "artist" in docstring.lower()
    assert "lidarr_grab_album" in docstring


def test_lookup_album_docstring_mbid():
    """lidarr_lookup_album docstring should mention MusicBrainz ID requirement."""
    source = _get_generated_source()
    body = _get_func_body(source, "lidarr_lookup_album")
    doc_start = body.find('"""')
    doc_end = body.find('"""', doc_start + 3)
    docstring = body[doc_start:doc_end]
    assert "MusicBrainz" in docstring
    assert "lidarr_search_album" in docstring


# ---------------------------------------------------------------------------
# Issue #8: set_album_release tool
# ---------------------------------------------------------------------------


def test_set_album_release_tool_exists():
    """lidarr_set_album_release should exist in generated output."""
    source = _get_generated_source()
    assert "async def lidarr_set_album_release(" in source


def test_set_album_release_params():
    """lidarr_set_album_release should have expected params."""
    source = _get_generated_source()
    sig = _get_func_sig(source, "lidarr_set_album_release")
    assert "albumId: int" in sig
    assert "releaseIndex: int | None = None" in sig
    assert "confirm: bool = False" in sig


def test_set_album_release_docstring():
    """lidarr_set_album_release docstring should explain listing and selecting."""
    source = _get_generated_source()
    body = _get_func_body(source, "lidarr_set_album_release")
    doc_start = body.find('"""')
    doc_end = body.find('"""', doc_start + 3)
    docstring = body[doc_start:doc_end]
    assert "release" in docstring.lower()
    assert "releaseIndex" in docstring


def test_update_album_hint_mentions_set_release():
    """lidarr_update_album workflow hint should mention lidarr_set_album_release."""
    source = _get_generated_source()
    body = _get_func_body(source, "lidarr_update_album")
    doc_start = body.find('"""')
    doc_end = body.find('"""', doc_start + 3)
    docstring = body[doc_start:doc_end]
    assert "lidarr_set_album_release" in docstring


# ---------------------------------------------------------------------------
# Issue #9: grab_album auto-detect defaults + artist re-monitor
# ---------------------------------------------------------------------------


def test_grab_album_auto_detect_defaults():
    """lidarr_grab_album should have rootfolder auto-detection code."""
    source = _get_generated_source()
    body = _get_func_body(source, "lidarr_grab_album")
    assert "/api/v1/rootfolder" in body
    assert "defaultQualityProfileId" in body


def test_grab_album_artist_remonitor():
    """lidarr_grab_album should re-monitor artist after create."""
    source = _get_generated_source()
    body = _get_func_body(source, "lidarr_grab_album")
    assert "_newly_created" in body
    # Should have a re-monitor step after create
    assert "Step 1b" in body or "Re-monitor artist" in body


def test_grab_album_docstring_mentions_search_album():
    """lidarr_grab_album docstring should mention lidarr_search_album."""
    source = _get_generated_source()
    body = _get_func_body(source, "lidarr_grab_album")
    doc_start = body.find('"""')
    doc_end = body.find('"""', doc_start + 3)
    docstring = body[doc_start:doc_end]
    assert "lidarr_search_album" in docstring


def test_grab_album_docstring_mentions_set_release():
    """lidarr_grab_album docstring should mention lidarr_set_album_release."""
    source = _get_generated_source()
    body = _get_func_body(source, "lidarr_grab_album")
    doc_start = body.find('"""')
    doc_end = body.find('"""', doc_start + 3)
    docstring = body[doc_start:doc_end]
    assert "lidarr_set_album_release" in docstring


def test_create_artist_auto_detect_defaults():
    """lidarr_create_artist should have rootfolder auto-detection code."""
    source = _get_generated_source()
    body = _get_func_body(source, "lidarr_create_artist")
    assert "/api/v1/rootfolder" in body
    assert "defaultQualityProfileId" in body
