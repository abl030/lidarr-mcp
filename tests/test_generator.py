"""Tests for the full generation pipeline.

Verifies that the generator produces valid, well-structured output.
"""

import re
import py_compile
import tempfile
from pathlib import Path

from generator.loader import load_spec
from generator.context_builder import build_context
from generator.codegen import generate


def _build():
    spec = load_spec()
    return build_context(spec)


def test_tool_count_in_range():
    """Should produce between 200 and 260 tools."""
    ctx = _build()
    assert 200 <= ctx["tool_count"] <= 260, f"Got {ctx['tool_count']} tools"


def test_all_modules_present():
    """Should have all expected modules."""
    ctx = _build()
    expected = {
        "album", "artist", "calendar", "command", "config",
        "downloadclient", "history", "importlist", "indexer",
        "quality", "queue", "release", "system", "track", "wanted",
    }
    actual = set(ctx["modules"].keys())
    missing = expected - actual
    assert not missing, f"Missing modules: {missing}"


def test_no_duplicate_tool_names():
    """All tool names must be unique."""
    ctx = _build()
    names = [t["name"] for t in ctx["tools"]]
    dupes = {n for n in names if names.count(n) > 1}
    assert not dupes, f"Duplicate names: {dupes}"


def test_all_names_are_valid_identifiers():
    """All tool names must be valid Python identifiers."""
    ctx = _build()
    for tool in ctx["tools"]:
        assert tool["name"].isidentifier(), f"Invalid identifier: {tool['name']}"


def test_all_names_start_with_lidarr():
    """All tool names must start with 'lidarr_'."""
    ctx = _build()
    for tool in ctx["tools"]:
        assert tool["name"].startswith("lidarr_"), f"Bad prefix: {tool['name']}"


def test_mutations_flagged():
    """POST/PUT/PATCH/DELETE should be flagged as mutations."""
    ctx = _build()
    for tool in ctx["tools"]:
        if tool["method"] in ("post", "put", "patch", "delete"):
            assert tool["is_mutation"], f"{tool['name']} should be a mutation"
        elif tool["method"] == "get":
            assert not tool["is_mutation"], f"{tool['name']} should not be a mutation"


def test_list_tools_have_list_flag():
    """GET endpoints returning arrays/paging should have is_list=True."""
    ctx = _build()
    list_tools = [t for t in ctx["tools"] if t["is_list"]]
    assert len(list_tools) > 10, f"Only {len(list_tools)} list tools found"


def test_generated_file_compiles():
    """The generated server.py must be valid Python."""
    ctx = _build()
    with tempfile.TemporaryDirectory() as tmpdir:
        # Temporarily change output
        output_path = Path(tmpdir) / "server.py"
        from generator import codegen
        old_dir = codegen.OUTPUT_DIR
        codegen.OUTPUT_DIR = Path(tmpdir)
        try:
            generate(ctx)
            py_compile.compile(str(output_path), doraise=True)
        finally:
            codegen.OUTPUT_DIR = old_dir


def test_generated_has_mcp_tool_decorators():
    """Generated file should have @mcp.tool() decorators for all tools."""
    ctx = _build()
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "server.py"
        from generator import codegen
        old_dir = codegen.OUTPUT_DIR
        codegen.OUTPUT_DIR = Path(tmpdir)
        try:
            generate(ctx)
            content = output_path.read_text()
        finally:
            codegen.OUTPUT_DIR = old_dir

        decorator_count = content.count("@mcp.tool()")
        # 230 generated + 3 always-registered
        assert decorator_count >= ctx["tool_count"], (
            f"Expected >= {ctx['tool_count']} @mcp.tool(), got {decorator_count}"
        )


def test_mutations_have_confirm_param():
    """All mutation tool functions should have confirm parameter."""
    ctx = _build()
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "server.py"
        from generator import codegen
        old_dir = codegen.OUTPUT_DIR
        codegen.OUTPUT_DIR = Path(tmpdir)
        try:
            generate(ctx)
            content = output_path.read_text()
        finally:
            codegen.OUTPUT_DIR = old_dir

        for tool in ctx["tools"]:
            if tool["is_mutation"]:
                # Find the function definition
                pattern = rf"async def {tool['name']}\("
                match = re.search(pattern, content)
                assert match, f"Function {tool['name']} not found"
                # Check for confirm parameter in the function
                func_start = match.start()
                func_end = content.find(") ->", func_start)
                func_sig = content[func_start:func_end]
                assert "confirm" in func_sig, (
                    f"{tool['name']} is a mutation but missing confirm param"
                )


def test_read_only_gating():
    """Mutation tools should be gated on LIDARR_READ_ONLY."""
    ctx = _build()
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "server.py"
        from generator import codegen
        old_dir = codegen.OUTPUT_DIR
        codegen.OUTPUT_DIR = Path(tmpdir)
        try:
            generate(ctx)
            content = output_path.read_text()
        finally:
            codegen.OUTPUT_DIR = old_dir

        assert "LIDARR_READ_ONLY" in content
        assert "if not LIDARR_READ_ONLY:" in content


def test_module_gating():
    """Tools should be gated by module."""
    ctx = _build()
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "server.py"
        from generator import codegen
        old_dir = codegen.OUTPUT_DIR
        codegen.OUTPUT_DIR = Path(tmpdir)
        try:
            generate(ctx)
            content = output_path.read_text()
        finally:
            codegen.OUTPUT_DIR = old_dir

        assert '_module_enabled("artist")' in content
        assert '_module_enabled("album")' in content
        assert '_module_enabled("system")' in content


def test_list_tools_have_filter_params():
    """List tool functions should have fields and query params."""
    ctx = _build()
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "server.py"
        from generator import codegen
        old_dir = codegen.OUTPUT_DIR
        codegen.OUTPUT_DIR = Path(tmpdir)
        try:
            generate(ctx)
            content = output_path.read_text()
        finally:
            codegen.OUTPUT_DIR = old_dir

        # Check lidarr_list_artists has fields and query
        match = re.search(r"async def lidarr_list_artists\(", content)
        assert match
        func_end = content.find(") ->", match.start())
        func_sig = content[match.start():func_end]
        assert "fields" in func_sig
        assert "filter" in func_sig


def test_always_registered_tools_present():
    """lidarr_get_overview, lidarr_search_tools, lidarr_report_issue always present."""
    ctx = _build()
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "server.py"
        from generator import codegen
        old_dir = codegen.OUTPUT_DIR
        codegen.OUTPUT_DIR = Path(tmpdir)
        try:
            generate(ctx)
            content = output_path.read_text()
        finally:
            codegen.OUTPUT_DIR = old_dir

        assert "async def lidarr_get_overview" in content
        assert "async def lidarr_search_tools" in content
        assert "async def lidarr_report_issue" in content
