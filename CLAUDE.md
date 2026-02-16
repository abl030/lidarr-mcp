# Lidarr MCP Server

Auto-generated MCP server for the Lidarr API v1. Tools generated from `spec/openapi.json` (OpenAPI 3.0.4, 161 paths, 236 operations). When Lidarr updates their API, pull a new spec and re-run the generator.

## Rules

1. **Never manually edit `generated/server.py`**. Fix the generator or templates instead.
2. **`spec/openapi.json` is the single source of truth**. All type information, parameter names, and endpoint structure come from the spec.
3. **Test against Docker, not production**. Use `docker/docker-compose.yml` for integration testing.
4. **Always use `nix develop -c`** as the default wrapper for repo commands.
5. **Testing must be automated**. Every feature/fix needs a pytest suite or equivalent.
6. **Add tests with features**. When adding new functionality, always write automated tests in the same change.
7. **Sprint progress lives in CLAUDE.md**. When work spans multiple sessions, document sprint plans, progress, and outcomes here.
8. **Reference `research/mcp-server-best-practices.md`** before making generator decisions. These are hard-won lessons from 3 prior MCP builds (pfSense 677 tools, UniFi 286 tools, Loki 42 tools).
9. **Every new feature must include both tests AND docstring updates.** Tool docstrings are the primary way consuming LLMs discover and understand tools. If a feature isn't described in docstrings, it doesn't exist to the LLM. When adding or changing functionality: (a) add/update unit tests, (b) add/update integration tests where the feature touches the generated server, and (c) ensure tool docstrings clearly describe what the tool does, its parameters, expected return values, and any workflow hints (e.g. "call X after Y"). Docstrings are generated from `context_builder.py` descriptions and `_WORKFLOW_HINTS` — update those, not the generated file.

## Repository Structure

```
spec/openapi.json              # Lidarr OpenAPI 3.0.4 spec (input)
generator/                     # Python generator
  __main__.py                  # Entry point: python -m generator
  loader.py                    # Load and parse the OpenAPI spec
  naming.py                    # Convert operationIds to tool names
  schema_parser.py             # Extract parameter types from schemas
  context_builder.py           # Build template context, assign modules
  codegen.py                   # Render templates and write output
templates/
  server.py.j2                 # FastMCP server template
generated/
  server.py                    # The MCP server (never hand-edit)
tests/                         # Unit + integration tests
research/                      # Best practices, API notes
docker/                        # Integration test infrastructure
```

## Generator

Reads `spec/openapi.json`, builds tool definitions for each path+method, renders via Jinja2.

```bash
nix develop -c python -m generator    # regenerate generated/server.py
```

### Key patterns (matching pfSense/UniFi/Loki MCPs):
- **FastMCP** server with `LidarrClient` (httpx + X-Api-Key auth)
- **Module gating**: tools wrapped in `if "module" in _LIDARR_MODULES:` blocks
- **Read-only mode**: mutation tools additionally gated on `not _LIDARR_READ_ONLY`
- **Confirmation gates**: all mutations require `confirm=True`
- **List tool enhancements**: `fields` (field selection) and `query` (row filtering) params
- **High-level tools**: `lidarr_get_overview`, `lidarr_search_tools`, `lidarr_report_issue`
- **Error reporting nudge**: every docstring says to call `lidarr_report_issue` on unexpected errors

### Generator best practices (from research/mcp-server-best-practices.md):
- Sanitize large integers (>= 2^53) — Anthropic API rejects them
- Exclude `readOnly` schema fields from request parameters
- Put enum values in parameter descriptions
- Downgrade conditional required fields to optional
- Strip HTML from descriptions
- PATCH defaults to `None` (not spec defaults) to avoid overwriting
- `allOf`/`$ref` in array items must resolve to `dict`, not `str`
- Consistent naming: `lidarr_{verb}_{resource}` (get/list/create/update/delete)

### Module system:
- Each API path maps to a module via prefix matching
- `codegen.py` groups tools by `(module, is_mutation)` and wraps in `if` blocks
- `lidarr_get_overview`, `lidarr_search_tools`, `lidarr_report_issue` always registered

### Lidarr-specific notes:
- Auth is via `X-Api-Key` header (not Basic Auth like pfSense, not cookie-based like UniFi)
- Unicode normalization: MusicBrainz uses exotic hyphens (U+2011 etc). The lookup/search tools should normalize these.
- The `/api/v1/command` endpoint is polymorphic — `name` field determines the command type (AlbumSearch, RescanArtist, etc.)
- Some endpoints use `albumIds` (array) in request body, not path params

## Sprint Progress

### Sprint 1: Generator Core
Status: COMPLETE

Deliverables:
- `naming.py`: Path-based tool naming (no operationIds in spec). Handles CRUD, sub-actions (lookup/monitor/editor), sub-resources, deduplication. 230 unique valid Python identifiers.
- `schema_parser.py`: Full parameter extraction — path/query/body params, `$ref` resolution, `allOf` composition, `readOnly` exclusion, enum value extraction, large integer sanitization, PATCH/PUT `None` defaults, body-vs-path deduplication.
- `context_builder.py`: Iterates all paths/methods, builds tool dicts, assigns modules, flags mutations/lists, generates descriptions.
- `templates/server.py.j2`: Generates real async functions with signatures, docstrings, confirmation gates, list enhancements (fields/query), module gating, read-only gating.
- `generated/server.py`: 230 tools, 8005 lines, valid Python, 16 modules.
- 58 tests (naming, modules, schema parsing, full pipeline).

### Sprint 2: Quality & Correctness
Status: COMPLETE

Goal: Close all remaining best-practice gaps from `research/mcp-server-best-practices.md` and add Lidarr-specific enhancements.

#### 2a — Apply-pattern reminders in docstrings (BP #5)
Add workflow hints to mutation tool docstrings so the LLM consumer knows what to call next:
- `lidarr_create_artist` → *"Note: Call lidarr_search_tools with 'command' to find album search commands after adding."*
- `lidarr_monitor_album` → *"Note: Call lidarr_create_command with name='AlbumSearch' to trigger a download search."*
- `lidarr_update_artist` / `lidarr_update_album` → *"Note: Call lidarr_create_command with name='RefreshArtist' after updating."*
- `lidarr_delete_artist` → *"Note: Files may remain on disk unless deleteFiles=True."*
Implement via a `_WORKFLOW_HINTS` dict in `context_builder.py` keyed by tool name, appended to descriptions.

#### 2b — Error source distinction (BP #8)
Wrap `_client.request()` in a try/except that catches `httpx.HTTPStatusError` and returns a structured error dict:
```python
{"error": True, "source": "lidarr_api", "status": 404, "message": "Not Found", "tool": "lidarr_get_artist"}
```
This makes it unambiguous whether the error came from the Lidarr API vs. schema validation vs. network failure. Implement in the template (`server.py.j2`) around the `_client.request()` call.

#### 2c — Array sub-resource documentation (BP #14)
For body params with `list[dict]` type, append a note to the description:
*"Pass as JSON array of objects. If creation fails, manage these via their dedicated sub-resource endpoints instead."*
Implement in `schema_parser.py` when building body param descriptions.

#### 2d — Sub-resource parent_id typing (BP #20)
Normalize path params ending in `Id` (e.g. `artistId`, `albumId`) to `str | int` instead of using the raw spec type. Implement in `schema_parser.py` for `location == "path"` params.

#### 2e — Unicode normalization (Lidarr-specific)
Add a `_normalize_unicode(text: str) -> str` helper to the template that normalizes exotic Unicode characters (U+2010–U+2015 hyphens, U+00A0 non-breaking space, etc.) to ASCII equivalents. Apply it in `lidarr_lookup_artist` and `lidarr_lookup_album` to the `term` parameter before sending to the API.
Implement as a helper function in the template and a Jinja2 conditional in the tool body for lookup tools.

#### 2f — Command endpoint polymorphism (Lidarr-specific)
Instead of one generic `lidarr_create_command`, generate dedicated tools per command type:
- `lidarr_command_album_search(albumIds: list[int])`
- `lidarr_command_artist_search(artistId: int)`
- `lidarr_command_refresh_artist(artistId: int)`
- `lidarr_command_rescan_artist(artistId: int)`
- `lidarr_command_missing_album_search()`
- `lidarr_command_manual_import(...)`
Add a `_COMMAND_TYPES` dict in `context_builder.py` that expands `POST /api/v1/command` into multiple tools with appropriate params and descriptions. Keep the generic `lidarr_create_command` as a fallback for unlisted command types.

#### 2g — Quality profile workflow hints (Lidarr-specific)
Add env-var defaults `LIDARR_DEFAULT_QUALITY_PROFILE_ID` and `LIDARR_DEFAULT_ROOT_FOLDER` to the template config section. Wire them as defaults in `lidarr_create_artist` params `qualityProfileId` and `rootFolderPath` so the consumer doesn't need to look them up every time.

#### 2h — Tests
- Test workflow hints appear in generated docstrings
- Test error wrapping returns structured dicts
- Test array sub-resource notes in descriptions
- Test parent_id params have `str | int` type
- Test unicode normalization helper
- Test command polymorphism produces separate tools
- Test quality profile env-var defaults

Deliverables:
- `context_builder.py`: `_WORKFLOW_HINTS` dict (2a), `_COMMAND_TYPES` list with 5 dedicated command tools (2f), `_ENV_DEFAULTS` for quality profile env vars (2g), `is_lookup` flag for unicode normalization (2e).
- `schema_parser.py`: Array sub-resource notes for `list[dict]` params (2c), parent_id `str | int` normalization for path params ending in `Id` (2d).
- `templates/server.py.j2`: Error wrapping with `httpx.HTTPStatusError`/`httpx.RequestError` → structured error dicts (2b), `_normalize_unicode` helper + application in lookup tools (2e), `LIDARR_DEFAULT_QUALITY_PROFILE_ID`/`LIDARR_DEFAULT_ROOT_FOLDER` env vars (2g), command body with `{"name": "CommandName"}` (2f).
- `generated/server.py`: 235 tools (230 API + 5 command types), valid Python.
- `tests/test_sprint2.py`: 29 tests covering all 7 features.
- Total tests: 87 (58 Sprint 1 + 29 Sprint 2).

### Sprint 3: Nix Packaging & Integration
Status: COMPLETE

Goal: Close the gap between generator tests and live-server validation. Add integration tests against Docker Lidarr, a Makefile for orchestration, and Nix flake checks.

#### 3a — pytest config (`pyproject.toml`)
Added `[tool.pytest.ini_options]`: `asyncio_mode = "auto"`, integration marker, `timeout = 60`.

#### 3b — Test infrastructure (`tests/conftest.py`, `generated/__init__.py`)
- `generated/__init__.py`: Empty package marker for importability.
- `tests/conftest.py`: Session-scoped `server` fixture (sets env vars, imports `generated.server`), `pytest_collection_modifyitems` hook auto-skips integration tests when `LIDARR_API_KEY` is unset.

#### 3c — Integration tests (`tests/test_integration.py`)
20 async tests across 9 categories, all `@pytest.mark.integration`:

| Category | Tests | What's validated |
|----------|-------|-----------------|
| Connection & Auth | 2 | System status returns version; bad API key → structured error dict |
| High-level tools | 4 | `get_overview` keys, `search_tools` matching/no-match, `report_issue` gh command |
| Read operations | 4 | `list_artists`, `list_albums`, `list_root_folders`, `list_quality_profiles` |
| List enhancements | 2 | `fields` restricts keys, `query` filters rows |
| CRUD lifecycle | 1 | lookup Metallica → create → get → update → verify → delete → verify 404 |
| Command tools | 1 | `command_missing_album_search` executes |
| Confirmation gates | 2 | `create_artist(confirm=False)` → preview, `delete_artist(confirm=False)` → preview |
| Error handling | 2 | Non-existent artist → 404, non-existent album → error |
| Unicode | 2 | Lookup with en-dash doesn't crash; `_normalize_unicode` helper works |

#### 3d — Makefile
- `make test` → unit tests only (fast, no Docker)
- `make test-integration` → docker up → wait → extract key → pytest integration → docker down
- `make generate` → regenerate server.py
- `make check` → nix flake check

#### 3e — Nix flake improvements (`flake.nix`)
Added `checks.${system}.unit-tests` output that runs unit tests (not integration) inside a Nix derivation via `pkgs.runCommand`.

#### Bugs found and fixed during integration testing
- `mcp._tool_manager.tools` → `._tools` (FastMCP internal API mismatch in `lidarr_search_tools`)
- `LidarrClient.request()` crashed on empty response body (DELETE returns 200 with no JSON) — added `not response.content` guard
- `docker/wait-for-ready.sh` now `chmod 777` volume mounts so Lidarr user can write

Deliverables:
- `pyproject.toml`: `[tool.pytest.ini_options]` with asyncio_mode, session-scoped event loop, markers, timeout.
- `generated/__init__.py`: Empty package marker.
- `tests/conftest.py`: Session fixture with `_ToolUnwrapper` proxy (unwraps FastMCP `FunctionTool` → raw `async def`) + auto-skip hook.
- `tests/test_integration.py`: 20 integration tests across 9 categories.
- `Makefile`: 4 targets (test, test-integration, generate, check).
- `flake.nix`: `checks` output with unit-tests derivation, `gnumake` in devShell.
- `templates/server.py.j2`: Fixed `_tool_manager._tools` access, empty response body handling.
- `docker/wait-for-ready.sh`: Volume permission fix.
- Total tests: 107 (87 unit + 20 integration).

### Sprint 4: LLM Testing
Status: SKIPPED — deferred indefinitely (cost-prohibitive for now).

### Sprint 5: Documentation & Release
Status: COMPLETE — shipped as v0.1.0.

### Issue #1: Response payloads too large for agent context windows
Status: COMPLETE

Goal: Fix real-world issues where list tool responses blow out LLM context windows.

#### 1a — Auto-compact nested objects in list responses
Added `_compact_value` and `_compact_object` helpers. When `fields` is NOT specified, list responses auto-compact:
- Dict values with >4 keys → `{"id": <id>}` (or `{"_keys": N}` if no id)
- List-of-dict values → `"[N items]"`
- Small embedded objects (<=4 keys) kept as-is
Single-object GETs are not affected — only list responses are compacted.

#### 1b — Replace `query` dict with string-based `filter`
Renamed `query: dict[str, Any] | None = None` → `filter: str = ""` in all list tool signatures. Format: `"key=value,key2=value2"`. Avoids pydantic `dict[str, Any]` serialization issues in MCP.

#### 1c — Safer `create_artist` addOptions defaults
Added `LIDARR_DEFAULT_MONITOR_OPTION` env var. When set and `addOptions is None`, injects `{"monitor": <value>, "searchForMissingAlbums": False}`. Updated workflow hint to document monitor values (all, future, missing, existing, latest, first, none).

#### 1d — Docstring improvements for list tools
Added `fields` and `filter` documentation to all list tool docstrings.

Deliverables:
- `templates/server.py.j2`: `_compact_value`/`_compact_object` helpers, rewritten `_filter_response` with auto-compaction and filter string parsing, `query` → `filter` rename, `LIDARR_DEFAULT_MONITOR_OPTION` env var and addOptions injection, list tool docstring enhancements.
- `generator/context_builder.py`: Updated `_WORKFLOW_HINTS["lidarr_create_artist"]` with addOptions.monitor documentation.
- `tests/test_issue1.py`: 13 new unit tests covering compaction, filter parsing, and generated code assertions.
- `tests/test_generator.py`: Updated `query` → `filter` assertion.
- `tests/test_integration.py`: Updated `query=` → `filter=` in 2 places.
- `generated/server.py`: Regenerated with all changes.
- Total tests: 120 (100 unit + 20 integration).

### Issue #2: PUT endpoints need better error handling and partial update support
Status: COMPLETE

Goal: Fix real-world issues where Lidarr's PUT endpoints require the full object for updates, causing 500 errors when callers only provide changed fields.

#### 2a — Synthetic PATCH via `merge` parameter on PUT tools
Added `merge: bool = True` to PUT mutation tool signatures (only for single-resource PUTs where `{id}` is in the path — not batch/bulk endpoints like `lidarr_monitor_album`).
When `merge=True`: GET the current object, deep-merge caller's non-None fields on top, then PUT the complete result.
When `merge=False`: current behavior (send only explicitly-provided fields).
Safety guard: only merge when GET returns a dict with `"id"` key; on GET failure, silently fall back to non-merge behavior.

#### 2b — Better error messages for PUT endpoints
Added `"hint": "PUT requires the full object. Use merge=True to auto-fetch and merge."` to the `httpx.HTTPStatusError` error dict for all PUT tools.

#### 2c — Workflow hint updates
Updated `_WORKFLOW_HINTS` for `lidarr_update_artist` and `lidarr_update_album` to mention `merge=True` default behavior.

#### 2d — Tests
- `tests/test_issue2.py`: 11 new unit tests covering merge param presence/absence, merge logic block, error hints, docstrings, and workflow hints.
- `tests/test_integration.py`: Added `test_update_artist_merge_partial` — partial update with only `monitored=True` and `merge=True`.

Deliverables:
- `templates/server.py.j2`: `merge` param in PUT signatures (gated on `{id}` in path), merge GET-then-merge logic before API call, `hint` in PUT error responses, docstring note for merge.
- `generator/context_builder.py`: Updated `_WORKFLOW_HINTS` for update tools to mention merge=True.
- `tests/test_issue2.py`: 11 new unit tests.
- `tests/test_integration.py`: 1 new integration test (merge partial update).
- `generated/server.py`: Regenerated with all changes (235 tools, 28 PUT tools with merge).
- Total tests: 132 (111 unit + 21 integration).

### Issue #3: UX improvements — response size, monitor bug, grab_album tool
Status: COMPLETE

Goal: Fix real-world friction points: mutation response bloat, monitor bug workaround, multi-step album grab workflow, and upstream search bypass.

#### 3a — Compact mutation responses
Added `_compact_mutation_response` helper in `templates/server.py.j2`. All mutation tool returns now use this instead of raw `_resp`:
- List responses (e.g. `monitor_album` updating 29 albums) → `{"ok": true, "count": 29, "ids": [...]}`
- Dict responses (e.g. `create_artist`) → top-level keys preserved, nested objects compacted via `_compact_object`
- Non-mutation (GET) tools unaffected

Mutation tool docstrings updated to document compact response format.

#### 3b — Monitor bug workaround
`addOptions.monitor: "none"` on `create_artist` may still mark albums as monitored (Lidarr API bug). Updated `_WORKFLOW_HINTS["lidarr_create_artist"]` to warn about this behavior and document the workaround: create artist → batch-unmonitor → selectively monitor. The `lidarr_grab_album` tool handles this automatically.

#### 3c — `lidarr_grab_album` high-level tool
Added always-registered `lidarr_grab_album` tool that combines 5 tool calls into one:
1. Lookup artist (or use `foreignArtistId` to bypass search)
2. Create artist if not in library (with `addOptions.monitor="none"`)
3. List albums and match by case-insensitive substring
4. Monitor the target album
5. Trigger download search

Returns `{"ok": true, "artistId": ..., "albumId": ..., "albumTitle": ..., "status": "search_triggered"}` on success. On album mismatch, returns available titles for retry.

#### 3d — MBID fallback (upstream search bypass)
`lidarr_grab_album` accepts `foreignArtistId` parameter (MusicBrainz ID) to bypass Lidarr's search API when it's unavailable. Updated `lidarr_create_artist` workflow hint to document `foreignArtistId` for direct creation.

#### 3e — Tests
- `tests/test_issue3.py`: 11 new unit tests covering compaction, generated code assertions, grab_album presence/params/docstring, workflow hints.
- `tests/test_integration.py`: 2 new integration tests (`test_grab_album_confirm_false_preview`, `test_grab_album_workflow`).

Deliverables:
- `templates/server.py.j2`: `_compact_mutation_response` helper, mutation return compaction, `lidarr_grab_album` tool, mutation docstring update.
- `generator/context_builder.py`: Updated `_WORKFLOW_HINTS["lidarr_create_artist"]` with monitor bug warning, MBID note, and `lidarr_grab_album` reference.
- `tests/test_issue3.py`: 11 new unit tests.
- `tests/test_integration.py`: 2 new integration tests.
- `generated/server.py`: Regenerated with all changes (235 tools + grab_album).
- Total tests: 145 (122 unit + 23 integration).

### Issue #4: Agent UX — Batch Operations, Command Polling, Metadata Profiles, Monitor Consistency
Status: COMPLETE

Goal: Fix real-world friction points: batch album monitoring, fire-and-forget commands, metadata profile compaction, and artist/album monitor consistency.

#### 4a — Artist/Album Monitor Consistency
- `lidarr_monitor_album`: When setting `monitored=True`, auto-checks and monitors parent artists (required for soularr).
- `lidarr_grab_album`: After monitoring album (Step 4b), ensures pre-existing parent artist is also monitored.
- Workflow hint updated to document auto-monitoring behavior.

#### 4b — `lidarr_update_albums_monitored` High-Level Tool
Always-registered tool wrapping `PUT /api/v1/album/monitor` with artist consistency.
Params: `albumIds`, `monitored`, `ensure_artist_monitored` (default True), `confirm`.
Docstring points to `lidarr_grab_album` for full add+monitor+search workflow.
Updated `lidarr_update_album` workflow hint to point to this batch tool.

#### 4c — Async Command Polling (`wait` parameter)
- `_poll_command` helper: polls `GET /api/v1/command/{id}` every 2s until completed/failed/aborted or timeout.
- All command tools (`is_command` and `is_command_generic`) get `wait: bool = False` and `wait_timeout: int = 30` params.
- When `wait=True`, polls after firing the command and returns `{"commandId": N, "status": "completed|failed|timeout", ...}`.
- `_COMMAND_TYPES` descriptions updated to document wait/wait_timeout.

#### 4d — Metadata Profile Summary
- `_summarize_metadata_profile` helper: extracts allowed type/status names from `primaryAlbumTypes`, `secondaryAlbumTypes`, `releaseStatuses`.
- `lidarr_list_metadata_profiles` flagged with `post_process = "metadata_profile"` in context_builder.
- Template conditional: when `fields` is empty, uses summarizer instead of generic compaction.
- Workflow hint documents summarized response format.

Deliverables:
- `templates/server.py.j2`: `_poll_command` helper, `_summarize_metadata_profile` helper, `lidarr_update_albums_monitored` tool, wait params in command rendering, artist-auto-monitor in `lidarr_monitor_album` + `lidarr_grab_album`, metadata profile post-processing.
- `generator/context_builder.py`: Updated `_WORKFLOW_HINTS` (monitor_album, update_album, list_metadata_profiles), `is_command_generic` flag, `post_process` flag, wait docs in `_COMMAND_TYPES`.
- `tests/test_issue4.py`: 17 new unit tests.
- `tests/test_integration.py`: 3 new integration tests.
- `generated/server.py`: Regenerated with all changes (235 tools + update_albums_monitored + grab_album).
- Total tests: 165 (139 unit + 26 integration).
