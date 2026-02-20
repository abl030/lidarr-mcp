"""Tests for Sprint 7: Issues #10 & #11.

Covers:
- #10a: foreignAlbumId param in grab_album + Step 3b album creation via MBID
- #10b: Error hints for lidarr_create_album POST errors
- #10b: Workflow hint for lidarr_create_album
- #11a: Unconditional artist re-monitor in Step 1b and Step 4b
- #11b: Rich confirm=false preview with read-only lookups
- #11c: fields param on single-resource GET tools
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

from generator.codegen import generate
from generator.context_builder import build_context, _WORKFLOW_HINTS, _ERROR_HINTS
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
    next_func = re.search(r"\n(?:    )?(?:async def |@mcp\.tool)", source[match.end():])
    if not next_func:
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
# 10a: foreignAlbumId in grab_album
# ---------------------------------------------------------------------------


def test_grab_album_has_foreignAlbumId_param():
    """grab_album signature includes foreignAlbumId: str = ''."""
    source = _get_generated_source()
    sig = _get_func_sig(source, "lidarr_grab_album")
    assert 'foreignAlbumId: str = ""' in sig


def test_grab_album_foreignAlbumId_in_docstring():
    """grab_album docstring mentions foreignAlbumId."""
    source = _get_generated_source()
    body = _get_func_body(source, "lidarr_grab_album")
    doc_start = body.find('"""')
    doc_end = body.find('"""', doc_start + 3)
    docstring = body[doc_start:doc_end]
    assert "foreignAlbumId" in docstring


def test_grab_album_creates_album_via_mbid():
    """grab_album body contains POST /api/v1/album in Step 3b."""
    source = _get_generated_source()
    body = _get_func_body(source, "lidarr_grab_album")
    assert "POST" in body and "/api/v1/album" in body
    assert "Step 3b" in body


def test_grab_album_album_create_required_fields():
    """Step 3b includes required empty arrays for album creation."""
    source = _get_generated_source()
    body = _get_func_body(source, "lidarr_grab_album")
    # Check the album create payload has required empty arrays
    assert '"images": []' in body
    assert '"links": []' in body
    assert '"releases": []' in body
    assert '"media": []' in body


def test_grab_album_match_fail_hints_mbid():
    """When album match fails without foreignAlbumId, error hints to provide it."""
    source = _get_generated_source()
    body = _get_func_body(source, "lidarr_grab_album")
    assert "Provide foreignAlbumId" in body


# ---------------------------------------------------------------------------
# 10b: Error hints for lidarr_create_album
# ---------------------------------------------------------------------------


def test_create_album_error_hint():
    """Generated lidarr_create_album has 'hint' in error handler."""
    source = _get_generated_source()
    body = _get_func_body(source, "lidarr_create_album")
    assert '"hint"' in body
    assert "POST /album" in body


def test_create_album_workflow_hint():
    """_WORKFLOW_HINTS has lidarr_create_album entry."""
    assert "lidarr_create_album" in _WORKFLOW_HINTS
    hint = _WORKFLOW_HINTS["lidarr_create_album"]
    assert "lidarr_grab_album" in hint
    assert "images" in hint


def test_create_album_error_hints_dict():
    """_ERROR_HINTS has lidarr_create_album entry."""
    assert "lidarr_create_album" in _ERROR_HINTS
    hint = _ERROR_HINTS["lidarr_create_album"]
    assert "artist" in hint
    assert "images" in hint


# ---------------------------------------------------------------------------
# 11a: Unconditional artist re-monitor
# ---------------------------------------------------------------------------


def test_grab_album_remonitor_unconditional():
    """Step 1b is NOT gated on _newly_created."""
    source = _get_generated_source()
    body = _get_func_body(source, "lidarr_grab_album")
    # Find Step 1b
    step1b_idx = body.find("Step 1b")
    assert step1b_idx > 0
    # The block before Step 1b should NOT contain "if _newly_created"
    # Check the 200 chars before Step 1b for the gate
    context_before = body[max(0, step1b_idx - 200):step1b_idx]
    assert "if _newly_created" not in context_before


def test_grab_album_step4b_no_gate():
    """Step 4b is NOT gated on 'not _newly_created'."""
    source = _get_generated_source()
    body = _get_func_body(source, "lidarr_grab_album")
    step4b_idx = body.find("Step 4b")
    assert step4b_idx > 0
    context_before = body[max(0, step4b_idx - 200):step4b_idx]
    assert "not _newly_created" not in context_before
    assert "if _newly_created" not in context_before


# ---------------------------------------------------------------------------
# 11b: Rich confirm=false preview
# ---------------------------------------------------------------------------


def test_grab_album_preview_does_lookups():
    """Preview block calls artist lookup API."""
    source = _get_generated_source()
    body = _get_func_body(source, "lidarr_grab_album")
    # Find the preview section (between "if not confirm:" and the next major step)
    preview_start = body.find("if not confirm:")
    assert preview_start > 0
    # The preview block should contain API lookups
    preview_block = body[preview_start:preview_start + 3000]
    assert "/api/v1/artist/lookup" in preview_block or "/api/v1/artist" in preview_block


def test_grab_album_preview_artist_in_library():
    """Preview returns 'artist_in_library' key."""
    source = _get_generated_source()
    body = _get_func_body(source, "lidarr_grab_album")
    assert "artist_in_library" in body


def test_grab_album_preview_will_create_artist():
    """Preview returns 'will_create_artist' key."""
    source = _get_generated_source()
    body = _get_func_body(source, "lidarr_grab_album")
    assert "will_create_artist" in body


def test_grab_album_preview_matched_album():
    """Preview returns 'matched_album' key."""
    source = _get_generated_source()
    body = _get_func_body(source, "lidarr_grab_album")
    assert "matched_album" in body


def test_grab_album_preview_quality_profile():
    """Preview returns 'qualityProfileId' key."""
    source = _get_generated_source()
    body = _get_func_body(source, "lidarr_grab_album")
    # The preview dict should include qualityProfileId
    preview_start = body.find("if not confirm:")
    preview_block = body[preview_start:preview_start + 1000]
    assert "qualityProfileId" in preview_block


# ---------------------------------------------------------------------------
# 11c: fields param on single-resource GET tools
# ---------------------------------------------------------------------------


def test_single_get_has_fields_param():
    """lidarr_get_artist has fields: str = '' param."""
    source = _get_generated_source()
    sig = _get_func_sig(source, "lidarr_get_artist")
    assert 'fields: str = ""' in sig


def test_single_get_fields_docstring():
    """lidarr_get_artist docstring mentions fields."""
    source = _get_generated_source()
    body = _get_func_body(source, "lidarr_get_artist")
    doc_start = body.find('"""')
    doc_end = body.find('"""', doc_start + 3)
    docstring = body[doc_start:doc_end]
    assert "fields" in docstring


def test_single_get_fields_applied():
    """lidarr_get_artist body contains _field_set logic."""
    source = _get_generated_source()
    body = _get_func_body(source, "lidarr_get_artist")
    assert "_field_set" in body


def test_list_still_has_filter():
    """lidarr_list_artists still has filter param."""
    source = _get_generated_source()
    sig = _get_func_sig(source, "lidarr_list_artists")
    assert 'filter: str = ""' in sig


def test_single_get_no_filter():
    """lidarr_get_artist does NOT have filter param."""
    source = _get_generated_source()
    sig = _get_func_sig(source, "lidarr_get_artist")
    assert "filter" not in sig


def test_context_is_single_get_flag():
    """is_single_get=True for lidarr_get_artist in context."""
    spec = load_spec()
    ctx = build_context(spec)
    tool = next(t for t in ctx["tools"] if t["name"] == "lidarr_get_artist")
    assert tool["is_single_get"] is True


def test_mutation_no_fields():
    """lidarr_create_artist does NOT have fields param."""
    source = _get_generated_source()
    sig = _get_func_sig(source, "lidarr_create_artist")
    assert "fields" not in sig
