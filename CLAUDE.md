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
Status: NOT STARTED

### Sprint 4: LLM Testing
Status: NOT STARTED

### Sprint 5: Documentation & Release
Status: NOT STARTED
