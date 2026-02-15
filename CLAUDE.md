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
Status: NOT STARTED

### Sprint 2: Quality & Correctness
Status: NOT STARTED

### Sprint 3: Nix Packaging & Integration
Status: NOT STARTED

### Sprint 4: LLM Testing
Status: NOT STARTED

### Sprint 5: Documentation & Release
Status: NOT STARTED
