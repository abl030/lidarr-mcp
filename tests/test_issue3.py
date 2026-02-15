"""Tests for GH Issue #3: UX improvements — response size, monitor bug, grab_album tool.

Covers:
- _compact_mutation_response compacts list and dict responses
- _compact_mutation_response passes through non-dict/list values
- Generated mutation tools use _compact_mutation_response
- Generated non-mutation tools do NOT use _compact_mutation_response
- Mutation tool docstrings mention compact response format
- lidarr_grab_album exists with expected params and docstring
- lidarr_create_artist workflow hint mentions monitor='none' workaround
- lidarr_create_artist workflow hint mentions foreignArtistId / MBID
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


# ---------------------------------------------------------------------------
# _compact_mutation_response tests
# ---------------------------------------------------------------------------


def test_compact_mutation_response_list():
    """A list of dicts should compact to {"ok": True, "count": N, "ids": [...]}."""
    source = _get_generated_source()
    ns: dict = {}
    exec(compile(source, "<test>", "exec"), ns)

    fn = ns["_compact_mutation_response"]
    data = [{"id": 1, "title": "A"}, {"id": 2, "title": "B"}, {"id": 3, "title": "C"}]
    result = fn(data)
    assert result == {"ok": True, "count": 3, "ids": [1, 2, 3]}


def test_compact_mutation_response_dict():
    """A dict should be compacted via _compact_object."""
    source = _get_generated_source()
    ns: dict = {}
    exec(compile(source, "<test>", "exec"), ns)

    fn = ns["_compact_mutation_response"]
    data = {
        "id": 42,
        "name": "Test",
        "nested": {"id": 10, "a": 1, "b": 2, "c": 3, "d": 4},
        "items": [{"id": 1}, {"id": 2}],
    }
    result = fn(data)
    assert result["id"] == 42
    assert result["name"] == "Test"
    assert result["nested"] == {"id": 10}  # compacted (>4 keys)
    assert result["items"] == "[2 items]"  # compacted list-of-dicts


def test_compact_mutation_response_passthrough():
    """Non-dict/list values should pass through unchanged."""
    source = _get_generated_source()
    ns: dict = {}
    exec(compile(source, "<test>", "exec"), ns)

    fn = ns["_compact_mutation_response"]
    assert fn("some string") == "some string"
    assert fn(42) == 42


# ---------------------------------------------------------------------------
# Generated code assertions
# ---------------------------------------------------------------------------


def test_mutation_tool_uses_compact_mutation_response():
    """Mutation tools (e.g. lidarr_create_artist) should return _compact_mutation_response(_resp)."""
    source = _get_generated_source()
    match = re.search(r"async def lidarr_create_artist\(", source)
    assert match
    next_func = re.search(r"\n\s+async def ", source[match.end():])
    if next_func:
        func_body = source[match.start():match.end() + next_func.start()]
    else:
        func_body = source[match.start():]

    assert "_compact_mutation_response(_resp)" in func_body


def test_non_mutation_tool_does_not_use_compact_mutation_response():
    """Non-mutation tools (e.g. lidarr_list_artists) should NOT use _compact_mutation_response."""
    source = _get_generated_source()
    match = re.search(r"async def lidarr_list_artists\(", source)
    assert match
    next_func = re.search(r"\n\s+async def ", source[match.end():])
    if next_func:
        func_body = source[match.start():match.end() + next_func.start()]
    else:
        func_body = source[match.start():]

    assert "_compact_mutation_response" not in func_body


def test_mutation_docstring_mentions_compact_response():
    """Mutation tool docstrings should mention compact response format."""
    source = _get_generated_source()
    match = re.search(r"async def lidarr_create_artist\(", source)
    assert match
    doc_start = source.find('"""', match.start())
    doc_end = source.find('"""', doc_start + 3)
    docstring = source[doc_start:doc_end]
    assert "Returns compact response" in docstring
    assert "batch results" in docstring


# ---------------------------------------------------------------------------
# lidarr_grab_album tool
# ---------------------------------------------------------------------------


def test_grab_album_exists():
    """lidarr_grab_album should exist in generated output."""
    source = _get_generated_source()
    assert "async def lidarr_grab_album(" in source


def test_grab_album_params():
    """lidarr_grab_album should have the expected parameters."""
    source = _get_generated_source()
    match = re.search(r"async def lidarr_grab_album\(", source)
    assert match
    func_end = source.find(") ->", match.start())
    func_sig = source[match.start():func_end]
    assert "artist: str" in func_sig
    assert "album: str" in func_sig
    assert "foreignArtistId: str" in func_sig
    assert "qualityProfileId" in func_sig
    assert "confirm: bool" in func_sig


def test_grab_album_docstring():
    """lidarr_grab_album docstring should document key params and return format."""
    source = _get_generated_source()
    match = re.search(r"async def lidarr_grab_album\(", source)
    assert match
    doc_start = source.find('"""', match.start())
    doc_end = source.find('"""', doc_start + 3)
    docstring = source[doc_start:doc_end]
    assert "artist" in docstring
    assert "album" in docstring
    assert "foreignArtistId" in docstring
    assert "search_triggered" in docstring
    assert "available album titles" in docstring


# ---------------------------------------------------------------------------
# Workflow hint updates
# ---------------------------------------------------------------------------


def test_create_artist_hint_mentions_monitor_workaround():
    """lidarr_create_artist workflow hint should warn about monitor='none' bug."""
    source = _get_generated_source()
    match = re.search(r"async def lidarr_create_artist\(", source)
    assert match
    doc_start = source.find('"""', match.start())
    doc_end = source.find('"""', doc_start + 3)
    docstring = source[doc_start:doc_end]
    assert "monitor='none'" in docstring or "monitor=\\'none\\'" in docstring


def test_create_artist_hint_mentions_mbid():
    """lidarr_create_artist workflow hint should mention foreignArtistId for MBID bypass."""
    source = _get_generated_source()
    match = re.search(r"async def lidarr_create_artist\(", source)
    assert match
    doc_start = source.find('"""', match.start())
    doc_end = source.find('"""', doc_start + 3)
    docstring = source[doc_start:doc_end]
    assert "foreignArtistId" in docstring
    assert "MusicBrainz" in docstring
