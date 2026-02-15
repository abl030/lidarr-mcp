"""Tests for GH Issue #1: Response payloads too large for agent context windows.

Covers:
- _compact_value: auto-compaction of nested objects
- _compact_object: row-level compaction
- _filter_response: auto-compaction, field selection, filter string parsing
- Generated code assertions: filter param, LIDARR_DEFAULT_MONITOR_OPTION, docstrings
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
# _compact_value tests
# ---------------------------------------------------------------------------


def test_compact_value_large_dict_with_id():
    """A dict with >4 keys and an 'id' should compact to {'id': <id>}."""
    source = _get_generated_source()
    # Execute in a namespace to get the helper functions
    ns: dict = {}
    exec(compile(source, "<test>", "exec"), ns)

    fn = ns["_compact_value"]
    large = {"id": 42, "name": "x", "path": "/a", "status": "ok", "extra": True}
    assert fn(large) == {"id": 42}


def test_compact_value_large_dict_without_id():
    """A dict with >4 keys and no 'id' should compact to {'_keys': N}."""
    source = _get_generated_source()
    ns: dict = {}
    exec(compile(source, "<test>", "exec"), ns)

    fn = ns["_compact_value"]
    large = {"name": "x", "path": "/a", "status": "ok", "extra": True, "more": 5}
    assert fn(large) == {"_keys": 5}


def test_compact_value_small_dict_unchanged():
    """A dict with <=4 keys should pass through unchanged."""
    source = _get_generated_source()
    ns: dict = {}
    exec(compile(source, "<test>", "exec"), ns)

    fn = ns["_compact_value"]
    small = {"value": 3.5, "votes": 10}
    assert fn(small) == {"value": 3.5, "votes": 10}


def test_compact_value_list_of_dicts():
    """A list of dicts should compact to '[N items]'."""
    source = _get_generated_source()
    ns: dict = {}
    exec(compile(source, "<test>", "exec"), ns)

    fn = ns["_compact_value"]
    items = [{"id": 1}, {"id": 2}, {"id": 3}]
    assert fn(items) == "[3 items]"


def test_compact_value_scalar():
    """Scalars pass through unchanged."""
    source = _get_generated_source()
    ns: dict = {}
    exec(compile(source, "<test>", "exec"), ns)

    fn = ns["_compact_value"]
    assert fn(42) == 42
    assert fn("hello") == "hello"
    assert fn(True) is True
    assert fn(None) is None


# ---------------------------------------------------------------------------
# _filter_response tests
# ---------------------------------------------------------------------------


def test_filter_response_auto_compaction():
    """When fields is empty, nested objects should be auto-compacted."""
    source = _get_generated_source()
    ns: dict = {}
    exec(compile(source, "<test>", "exec"), ns)

    fn = ns["_filter_response"]
    data = [
        {
            "id": 1,
            "title": "Album A",
            "artist": {"id": 10, "name": "x", "path": "/a", "status": "ok", "extra": True},
            "tracks": [{"id": 100}, {"id": 101}],
        },
    ]
    result = fn(data)
    assert result["count"] == 1
    row = result["data"][0]
    assert row["id"] == 1
    assert row["title"] == "Album A"
    assert row["artist"] == {"id": 10}  # compacted
    assert row["tracks"] == "[2 items]"  # compacted


def test_filter_response_fields_bypasses_compaction():
    """When fields is specified, return only those fields without compaction."""
    source = _get_generated_source()
    ns: dict = {}
    exec(compile(source, "<test>", "exec"), ns)

    fn = ns["_filter_response"]
    data = [
        {
            "id": 1,
            "title": "Album A",
            "artist": {"id": 10, "name": "x", "path": "/a", "status": "ok", "extra": True},
        },
    ]
    result = fn(data, fields="title")
    row = result["data"][0]
    assert set(row.keys()) == {"id", "title"}


def test_filter_response_filter_string_parsing():
    """Filter string should filter rows by key=value pairs."""
    source = _get_generated_source()
    ns: dict = {}
    exec(compile(source, "<test>", "exec"), ns)

    fn = ns["_filter_response"]
    data = [
        {"id": 1, "name": "Alice", "active": "true"},
        {"id": 2, "name": "Bob", "active": "false"},
        {"id": 3, "name": "Alice", "active": "false"},
    ]
    result = fn(data, filter_expr="name=Alice")
    assert result["count"] == 2
    assert all(row["name"] == "Alice" for row in result["data"])


def test_filter_response_filter_and_fields_together():
    """Filter + fields should work together: filter first, then select fields."""
    source = _get_generated_source()
    ns: dict = {}
    exec(compile(source, "<test>", "exec"), ns)

    fn = ns["_filter_response"]
    data = [
        {"id": 1, "name": "Alice", "active": "true"},
        {"id": 2, "name": "Bob", "active": "false"},
    ]
    result = fn(data, fields="name", filter_expr="active=true")
    assert result["count"] == 1
    row = result["data"][0]
    assert set(row.keys()) == {"id", "name"}
    assert row["name"] == "Alice"


# ---------------------------------------------------------------------------
# Generated code assertions
# ---------------------------------------------------------------------------


def test_generated_uses_filter_not_query():
    """Generated list tools should use 'filter: str' not 'query: dict'."""
    source = _get_generated_source()
    # lidarr_list_artists should have filter: str
    match = re.search(r"async def lidarr_list_artists\(", source)
    assert match
    func_end = source.find(") ->", match.start())
    func_sig = source[match.start():func_end]
    assert "filter: str" in func_sig
    assert "query" not in func_sig


def test_generated_has_monitor_option_env_var():
    """Generated file should have LIDARR_DEFAULT_MONITOR_OPTION."""
    source = _get_generated_source()
    assert 'LIDARR_DEFAULT_MONITOR_OPTION' in source
    assert 'os.environ.get("LIDARR_DEFAULT_MONITOR_OPTION"' in source


def test_generated_create_artist_has_addoptions_hint():
    """create_artist docstring should mention addOptions.monitor values."""
    source = _get_generated_source()
    match = re.search(r"async def lidarr_create_artist\(", source)
    assert match
    # Find the docstring after the function def
    doc_start = source.find('"""', match.start())
    doc_end = source.find('"""', doc_start + 3)
    docstring = source[doc_start:doc_end]
    assert "addOptions.monitor" in docstring


def test_generated_list_tool_has_filter_docs():
    """List tool docstrings should document fields and filter params."""
    source = _get_generated_source()
    match = re.search(r"async def lidarr_list_artists\(", source)
    assert match
    doc_start = source.find('"""', match.start())
    doc_end = source.find('"""', doc_start + 3)
    docstring = source[doc_start:doc_end]
    assert "auto-compacted" in docstring
    assert "filter" in docstring.lower()
