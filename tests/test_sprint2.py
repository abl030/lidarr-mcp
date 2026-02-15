"""Tests for Sprint 2: Quality & Correctness features.

Covers:
- 2a: Workflow hints in mutation docstrings
- 2b: Error source distinction (structured error wrapping)
- 2c: Array sub-resource documentation notes
- 2d: Sub-resource parent_id typing (str | int)
- 2e: Unicode normalization helper
- 2f: Command endpoint polymorphism
- 2g: Quality profile env-var defaults
"""

import re
import tempfile
from pathlib import Path

from generator.loader import load_spec
from generator.context_builder import build_context
from generator.codegen import generate
from generator.schema_parser import parse_parameters


def _build():
    spec = load_spec()
    return build_context(spec)


def _generate_content():
    """Build context and generate server.py, return its content."""
    ctx = _build()
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "server.py"
        from generator import codegen
        old_dir = codegen.OUTPUT_DIR
        codegen.OUTPUT_DIR = Path(tmpdir)
        try:
            generate(ctx)
            return output_path.read_text(), ctx
        finally:
            codegen.OUTPUT_DIR = old_dir


# ── 2a: Workflow hints ───────────────────────────────────────────────


def test_create_artist_has_workflow_hint():
    """lidarr_create_artist should mention searching for commands after adding."""
    ctx = _build()
    tool = next(t for t in ctx["tools"] if t["name"] == "lidarr_create_artist")
    assert "lidarr_search_tools" in tool["description"]


def test_monitor_album_has_workflow_hint():
    """lidarr_monitor_album should mention AlbumSearch command."""
    ctx = _build()
    tool = next(t for t in ctx["tools"] if t["name"] == "lidarr_monitor_album")
    assert "AlbumSearch" in tool["description"]


def test_update_artist_has_workflow_hint():
    """lidarr_update_artist should mention RefreshArtist command."""
    ctx = _build()
    tool = next(t for t in ctx["tools"] if t["name"] == "lidarr_update_artist")
    assert "RefreshArtist" in tool["description"]


def test_delete_artist_has_workflow_hint():
    """lidarr_delete_artist should mention deleteFiles."""
    ctx = _build()
    tool = next(t for t in ctx["tools"] if t["name"] == "lidarr_delete_artist")
    assert "deleteFiles" in tool["description"]


def test_workflow_hints_in_generated_docstrings():
    """Workflow hints should appear in generated function docstrings."""
    content, _ = _generate_content()
    # Check lidarr_create_artist docstring mentions searching
    match = re.search(r'async def lidarr_create_artist\(', content)
    assert match
    # Find the docstring after the function def
    docstring_start = content.find('"""', match.end())
    docstring_end = content.find('"""', docstring_start + 3)
    docstring = content[docstring_start:docstring_end]
    assert "lidarr_search_tools" in docstring


# ── 2b: Error source distinction ─────────────────────────────────────


def test_error_wrapping_in_generated_code():
    """Generated tools should have try/except around _client.request()."""
    content, _ = _generate_content()
    assert "except httpx.HTTPStatusError as exc:" in content
    assert '"source": "lidarr_api"' in content


def test_network_error_wrapping():
    """Generated tools should catch httpx.RequestError for network errors."""
    content, _ = _generate_content()
    assert "except httpx.RequestError as exc:" in content
    assert '"source": "network"' in content


def test_error_wrapping_includes_tool_name():
    """Error dict should include the tool name for identification."""
    content, _ = _generate_content()
    # Check that a specific tool includes its name in the error dict
    assert '"tool": "lidarr_list_artists"' in content
    assert '"tool": "lidarr_create_artist"' in content


def test_every_tool_has_error_wrapping():
    """Every generated tool should have error wrapping."""
    content, ctx = _generate_content()
    for tool in ctx["tools"]:
        pattern = rf'"tool": "{tool["name"]}"'
        assert re.search(pattern, content), (
            f"{tool['name']} missing error wrapping"
        )


# ── 2c: Array sub-resource documentation ─────────────────────────────


def test_list_dict_params_have_subresource_note():
    """Body params with list[dict] type should have sub-resource note."""
    ctx = _build()
    tool = next(t for t in ctx["tools"] if t["name"] == "lidarr_create_artist")
    list_dict_params = [
        p for p in tool["params"]
        if p["type"] == "list[dict]" and p["location"] == "body"
    ]
    assert len(list_dict_params) > 0, "lidarr_create_artist should have list[dict] params"
    for p in list_dict_params:
        assert "sub-resource endpoints" in p["description"], (
            f"Param {p['name']} missing sub-resource note"
        )


def test_subresource_note_in_generated_docstring():
    """Array sub-resource notes should appear in generated docstrings."""
    content, _ = _generate_content()
    assert "sub-resource endpoints instead" in content


# ── 2d: Sub-resource parent_id typing ────────────────────────────────


def test_path_params_ending_in_id_are_str_or_int():
    """Path params ending in 'Id' should have str | int type."""
    spec = load_spec()
    # Check a path that has {artistId} as a sub-resource
    for path, path_item in spec["paths"].items():
        for method in ("get", "post", "put", "delete", "patch"):
            if method not in path_item:
                continue
            op = path_item[method]
            op["_method"] = method
            params = parse_parameters(spec, op, path)
            for p in params:
                if p["location"] == "path" and p["name"].endswith("Id"):
                    assert p["type"] == "str | int", (
                        f"Path param {p['name']} in {method.upper()} {path}"
                        f" should be str | int, got {p['type']}"
                    )


def test_regular_id_param_not_affected():
    """Path param named just 'id' (not ending in 'Id') should keep original type."""
    spec = load_spec()
    op = spec["paths"]["/api/v1/artist/{id}"]["get"]
    op["_method"] = "get"
    params = parse_parameters(spec, op, "/api/v1/artist/{id}")
    id_param = next(p for p in params if p["name"] == "id")
    # 'id' doesn't end with 'Id' (capital I), so type should stay int
    assert id_param["type"] == "int"


# ── 2e: Unicode normalization ─────────────────────────────────────────


def test_unicode_normalization_helper_in_generated():
    """Generated code should include _normalize_unicode helper."""
    content, _ = _generate_content()
    assert "def _normalize_unicode(text: str) -> str:" in content


def test_unicode_normalization_applied_in_lookup_tools():
    """Lookup tools should call _normalize_unicode on the term param."""
    content, _ = _generate_content()
    # Find lidarr_lookup_artist and check for normalization
    match = re.search(r"async def lidarr_lookup_artist\(", content)
    assert match
    # Look for _normalize_unicode call after the function def
    func_body_start = match.end()
    next_func = content.find("async def ", func_body_start)
    func_body = content[func_body_start:next_func]
    assert "_normalize_unicode" in func_body


def test_unicode_replacement_table_in_generated():
    """Generated code should have Unicode replacement table with exotic hyphens."""
    content, _ = _generate_content()
    assert "\\u2011" in content  # NON-BREAKING HYPHEN
    assert "\\u2013" in content  # EN DASH
    assert "\\u00a0" in content  # NON-BREAKING SPACE


def test_lookup_tools_flagged():
    """Lookup tools should have is_lookup=True in context."""
    ctx = _build()
    lookup_tools = [t for t in ctx["tools"] if t.get("is_lookup")]
    assert len(lookup_tools) >= 2, "Should have at least 2 lookup tools"
    lookup_names = {t["name"] for t in lookup_tools}
    assert "lidarr_lookup_artist" in lookup_names
    assert "lidarr_lookup_album" in lookup_names


def test_non_lookup_tools_not_flagged():
    """Non-lookup tools should have is_lookup=False."""
    ctx = _build()
    tool = next(t for t in ctx["tools"] if t["name"] == "lidarr_list_artists")
    assert not tool.get("is_lookup")


# ── 2f: Command endpoint polymorphism ────────────────────────────────


def test_command_tools_present():
    """Dedicated command type tools should exist in context."""
    ctx = _build()
    cmd_tools = [t for t in ctx["tools"] if t.get("is_command")]
    assert len(cmd_tools) == 5
    cmd_names = {t["name"] for t in cmd_tools}
    assert "lidarr_command_album_search" in cmd_names
    assert "lidarr_command_artist_search" in cmd_names
    assert "lidarr_command_refresh_artist" in cmd_names
    assert "lidarr_command_rescan_artist" in cmd_names
    assert "lidarr_command_missing_album_search" in cmd_names


def test_command_tools_have_correct_params():
    """Command tools should have the right parameters."""
    ctx = _build()
    album_search = next(
        t for t in ctx["tools"] if t["name"] == "lidarr_command_album_search"
    )
    param_names = [p["name"] for p in album_search["params"]]
    assert "albumIds" in param_names

    artist_search = next(
        t for t in ctx["tools"] if t["name"] == "lidarr_command_artist_search"
    )
    param_names = [p["name"] for p in artist_search["params"]]
    assert "artistId" in param_names

    missing = next(
        t for t in ctx["tools"] if t["name"] == "lidarr_command_missing_album_search"
    )
    assert len(missing["params"]) == 0


def test_command_tools_are_mutations():
    """Command tools should be flagged as mutations."""
    ctx = _build()
    cmd_tools = [t for t in ctx["tools"] if t.get("is_command")]
    for tool in cmd_tools:
        assert tool["is_mutation"], f"{tool['name']} should be a mutation"


def test_command_tools_in_command_module():
    """Command tools should be in the command module."""
    ctx = _build()
    cmd_tools = [t for t in ctx["tools"] if t.get("is_command")]
    for tool in cmd_tools:
        assert tool["module"] == "command", (
            f"{tool['name']} should be in command module"
        )


def test_command_body_has_name_field():
    """Generated command tools should send {name: 'CommandName'} in body."""
    content, _ = _generate_content()
    assert '_body: dict[str, Any] = {"name": "AlbumSearch"}' in content
    assert '_body: dict[str, Any] = {"name": "ArtistSearch"}' in content
    assert '_body: dict[str, Any] = {"name": "RefreshArtist"}' in content
    assert '_body: dict[str, Any] = {"name": "MissingAlbumSearch"}' in content


def test_generic_create_command_still_exists():
    """The generic lidarr_create_command should still exist as fallback."""
    ctx = _build()
    generic = [t for t in ctx["tools"] if t["name"] == "lidarr_create_command"]
    assert len(generic) == 1, "Generic lidarr_create_command should exist"
    assert not generic[0].get("is_command"), "Generic should not be flagged as command type"


def test_command_tools_in_generated_code():
    """Command tools should appear as async def in generated code."""
    content, _ = _generate_content()
    assert "async def lidarr_command_album_search(" in content
    assert "async def lidarr_command_artist_search(" in content
    assert "async def lidarr_command_refresh_artist(" in content
    assert "async def lidarr_command_rescan_artist(" in content
    assert "async def lidarr_command_missing_album_search(" in content


# ── 2g: Quality profile env-var defaults ──────────────────────────────


def test_quality_profile_env_vars_in_generated():
    """Generated code should have LIDARR_DEFAULT_QUALITY_PROFILE_ID env var."""
    content, _ = _generate_content()
    assert "LIDARR_DEFAULT_QUALITY_PROFILE_ID" in content
    assert "LIDARR_DEFAULT_ROOT_FOLDER" in content


def test_create_artist_uses_quality_profile_default():
    """lidarr_create_artist should fall back to env var for qualityProfileId."""
    content, _ = _generate_content()
    # Find the lidarr_create_artist function body
    match = re.search(r"async def lidarr_create_artist\(", content)
    assert match
    func_start = match.start()
    # Find next function to delimit the body
    next_func = content.find("async def ", func_start + 10)
    func_body = content[func_start:next_func]
    assert "LIDARR_DEFAULT_QUALITY_PROFILE_ID" in func_body
    assert "LIDARR_DEFAULT_ROOT_FOLDER" in func_body


def test_env_default_param_flagged_in_context():
    """Params with env defaults should have env_default key in context."""
    ctx = _build()
    tool = next(t for t in ctx["tools"] if t["name"] == "lidarr_create_artist")
    quality_param = next(
        (p for p in tool["params"] if p["name"] == "qualityProfileId"), None
    )
    assert quality_param is not None
    assert quality_param.get("env_default") == "LIDARR_DEFAULT_QUALITY_PROFILE_ID"

    root_param = next(
        (p for p in tool["params"] if p["name"] == "rootFolderPath"), None
    )
    assert root_param is not None
    assert root_param.get("env_default") == "LIDARR_DEFAULT_ROOT_FOLDER"


def test_other_tools_no_env_default():
    """Non-create_artist tools should not have env_default params."""
    ctx = _build()
    tool = next(t for t in ctx["tools"] if t["name"] == "lidarr_list_artists")
    for p in tool["params"]:
        assert not p.get("env_default"), (
            f"Param {p['name']} in lidarr_list_artists should not have env_default"
        )
