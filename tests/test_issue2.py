"""Tests for GH Issue #2: PUT endpoints need better error handling and partial update support.

Covers:
- merge: bool = True parameter on PUT tools with {id} in path
- merge parameter absent on non-PUT tools and batch PUT tools (no {id})
- PUT error responses include 'hint' field
- PUT tool docstrings mention merge
- Merge logic block present in generated PUT tool code
- Workflow hints updated for update tools
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
# merge parameter presence
# ---------------------------------------------------------------------------


def test_put_tool_with_id_has_merge_param():
    """PUT tools with {id} in path (e.g. lidarr_update_artist) should have merge: bool = True."""
    source = _get_generated_source()
    match = re.search(r"async def lidarr_update_artist\(", source)
    assert match
    func_end = source.find(") ->", match.start())
    func_sig = source[match.start():func_end]
    assert "merge: bool = True" in func_sig


def test_put_tool_album_has_merge_param():
    """PUT tools for album update should also have merge: bool = True."""
    source = _get_generated_source()
    match = re.search(r"async def lidarr_update_album\(", source)
    assert match
    func_end = source.find(") ->", match.start())
    func_sig = source[match.start():func_end]
    assert "merge: bool = True" in func_sig


def test_non_put_tool_does_not_have_merge():
    """Non-PUT tools (e.g. POST lidarr_create_artist) should NOT have merge param."""
    source = _get_generated_source()
    match = re.search(r"async def lidarr_create_artist\(", source)
    assert match
    func_end = source.find(") ->", match.start())
    func_sig = source[match.start():func_end]
    assert "merge" not in func_sig


def test_batch_put_without_id_does_not_have_merge():
    """Batch PUT tools without {id} (e.g. lidarr_monitor_album) should NOT have merge."""
    source = _get_generated_source()
    match = re.search(r"async def lidarr_monitor_album\(", source)
    assert match
    func_end = source.find(") ->", match.start())
    func_sig = source[match.start():func_end]
    assert "merge" not in func_sig


# ---------------------------------------------------------------------------
# merge logic block
# ---------------------------------------------------------------------------


def test_merge_logic_present_in_put_tool():
    """PUT tools with {id} should have the merge GET-then-merge logic block."""
    source = _get_generated_source()
    # Find the lidarr_update_artist function body
    match = re.search(r"async def lidarr_update_artist\(", source)
    assert match
    # Find the next function definition to bound the search
    next_func = re.search(r"\n\s+async def ", source[match.end():])
    if next_func:
        func_body = source[match.start():match.end() + next_func.start()]
    else:
        func_body = source[match.start():]

    assert "if merge:" in func_body
    assert '_existing = await _client.request("GET", _path)' in func_body
    assert '{**_existing, **_body}' in func_body


def test_merge_logic_absent_in_batch_put():
    """Batch PUT tools without {id} should NOT have merge logic."""
    source = _get_generated_source()
    match = re.search(r"async def lidarr_monitor_album\(", source)
    assert match
    next_func = re.search(r"\n\s+async def ", source[match.end():])
    if next_func:
        func_body = source[match.start():match.end() + next_func.start()]
    else:
        func_body = source[match.start():]

    assert "if merge:" not in func_body


# ---------------------------------------------------------------------------
# PUT error hint
# ---------------------------------------------------------------------------


def test_put_error_has_hint():
    """PUT tool error dicts should include a 'hint' field."""
    source = _get_generated_source()
    # Find lidarr_update_artist's error handling
    match = re.search(r"async def lidarr_update_artist\(", source)
    assert match
    next_func = re.search(r"\n\s+async def ", source[match.end():])
    if next_func:
        func_body = source[match.start():match.end() + next_func.start()]
    else:
        func_body = source[match.start():]

    assert '"hint"' in func_body
    assert "PUT requires the full object" in func_body


def test_non_put_error_has_no_hint():
    """Non-PUT tool error dicts should NOT include a 'hint' field."""
    source = _get_generated_source()
    # Find lidarr_create_artist's error handling
    match = re.search(r"async def lidarr_create_artist\(", source)
    assert match
    next_func = re.search(r"\n\s+async def ", source[match.end():])
    if next_func:
        func_body = source[match.start():match.end() + next_func.start()]
    else:
        func_body = source[match.start():]

    assert '"hint"' not in func_body


# ---------------------------------------------------------------------------
# Docstring mentions merge
# ---------------------------------------------------------------------------


def test_put_docstring_mentions_merge():
    """PUT tool with {id} should document merge parameter in docstring."""
    source = _get_generated_source()
    match = re.search(r"async def lidarr_update_artist\(", source)
    assert match
    doc_start = source.find('"""', match.start())
    doc_end = source.find('"""', doc_start + 3)
    docstring = source[doc_start:doc_end]
    assert "merge" in docstring.lower()
    assert "Auto-fetch current object" in docstring


# ---------------------------------------------------------------------------
# Workflow hints updated
# ---------------------------------------------------------------------------


def test_workflow_hint_update_artist_mentions_merge():
    """lidarr_update_artist workflow hint should mention merge=True."""
    source = _get_generated_source()
    match = re.search(r"async def lidarr_update_artist\(", source)
    assert match
    doc_start = source.find('"""', match.start())
    doc_end = source.find('"""', doc_start + 3)
    docstring = source[doc_start:doc_end]
    assert "merge=True" in docstring or "auto-fetch" in docstring.lower()


def test_workflow_hint_update_album_mentions_merge():
    """lidarr_update_album workflow hint should mention merge=True."""
    source = _get_generated_source()
    match = re.search(r"async def lidarr_update_album\(", source)
    assert match
    doc_start = source.find('"""', match.start())
    doc_end = source.find('"""', doc_start + 3)
    docstring = source[doc_start:doc_end]
    assert "merge=True" in docstring or "auto-fetch" in docstring.lower()
