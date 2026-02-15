# Lidarr MCP Server

An MCP (Model Context Protocol) server that gives AI agents full control over Lidarr music management. Auto-generated from the official [Lidarr OpenAPI spec](https://github.com/Lidarr/Lidarr/blob/develop/src/Lidarr.Api.V1/openapi.json) (161 paths, 236 operations).

Built because the existing `mcp-arr-server` only has read operations. This one has full CRUD — add artists, monitor albums, grab releases, manage quality profiles, trigger searches, and import files. All the write operations that [cost us 60% of our tokens](https://github.com/abl030/nixosconfig/blob/master/docs/music-pipeline-postmortem.md) doing manually.

This entire project — the generator, the server, the test suite, and this README — was built by AI (Claude) and is designed to be installed and used by AI agents.

## Install

### Option 1: Nix Flake (recommended)

```nix
# flake.nix
{
  inputs.lidarr-mcp.url = "github:abl030/lidarr-mcp";
}
```

```nix
# Use the package
environment.systemPackages = [ inputs.lidarr-mcp.packages.${pkgs.system}.default ];

# Or in an MCP server config
{
  command = "${inputs.lidarr-mcp.packages.${pkgs.system}.default}/bin/lidarr-mcp";
  env = {
    LIDARR_URL = "http://localhost:8686";
    LIDARR_API_KEY = "your-api-key";
  };
}
```

Quick test without installing:

```bash
LIDARR_URL=http://localhost:8686 LIDARR_API_KEY=your-key nix run github:abl030/lidarr-mcp
```

### Option 2: uv (non-Nix)

```bash
git clone https://github.com/abl030/lidarr-mcp.git
cd lidarr-mcp
uv sync
uv run python -m generator    # produces generated/server.py
```

### Configure Your MCP Client

**Claude Code:**

```bash
# Nix
claude mcp add lidarr -- \
  env LIDARR_URL=http://YOUR_LIDARR_HOST:8686 \
  LIDARR_API_KEY=YOUR_API_KEY \
  lidarr-mcp

# Non-Nix
claude mcp add lidarr -- \
  env LIDARR_URL=http://YOUR_LIDARR_HOST:8686 \
  LIDARR_API_KEY=YOUR_API_KEY \
  uv run --directory /path/to/lidarr-mcp fastmcp run generated/server.py
```

**Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "lidarr": {
      "command": "lidarr-mcp",
      "env": {
        "LIDARR_URL": "http://YOUR_LIDARR_HOST:8686",
        "LIDARR_API_KEY": "YOUR_API_KEY",
        "LIDARR_MODULES": "artist,album,queue,release,command,quality,system"
      }
    }
  }
}
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LIDARR_URL` | `http://localhost:8686` | Lidarr base URL |
| `LIDARR_API_KEY` | *(required)* | API key (Settings > General > Security) |
| `LIDARR_MODULES` | *(all modules)* | Comma-separated list of modules to enable |
| `LIDARR_READ_ONLY` | `false` | Strip all mutation tools (POST/PUT/DELETE) |

### Module Filtering

By default all tools are registered. Set `LIDARR_MODULES` to load only what you need:

| Module | What it covers |
|--------|----------------|
| `artist` | Artist CRUD, lookup, editor, bulk operations |
| `album` | Album CRUD, lookup, monitoring, album studio |
| `track` | Track listing and file management |
| `release` | Release searching and grabbing |
| `queue` | Download queue management |
| `command` | Trigger searches, rescans, imports, renames |
| `quality` | Quality profiles and custom formats |
| `wanted` | Missing/cutoff albums |
| `history` | Import/grab history |
| `calendar` | Upcoming releases |
| `indexer` | Indexer configuration |
| `downloadclient` | Download client management |
| `importlist` | Import list management |
| `system` | Health, backup, disk space, logs, tags, root folders |
| `config` | Host, naming, media management settings |

`lidarr_get_overview`, `lidarr_search_tools`, and `lidarr_report_issue` are always registered regardless of module selection.

**Example configurations:**

```bash
# Music management (~core tools)
LIDARR_MODULES=artist,album,release,queue,command,quality,wanted

# Read-only monitoring
LIDARR_MODULES=artist,album,queue,wanted,history
LIDARR_READ_ONLY=true

# Full control
# (default — all modules enabled)
```

## What You Get

**TODO: Tool counts will be filled after generator Sprint 1 completes.**

| Category | Examples |
|----------|---------|
| **Artist** | add, update, delete, lookup, bulk edit, search by MusicBrainz ID |
| **Album** | CRUD, monitor/unmonitor, album studio |
| **Release** | Search releases for album, grab specific release |
| **Queue** | List, remove, bulk remove downloads |
| **Command** | AlbumSearch, ArtistSearch, RescanArtist, RefreshArtist, ManualImport, Rename |
| **Quality** | Profile CRUD, custom format CRUD |
| **Wanted** | Missing albums, cutoff unmet |
| **History** | Import/grab history, mark failed |
| **Calendar** | Upcoming releases by date range |
| **System** | Health, disk space, backups, tags, root folders, logs |

### High-Level Tools (no API knowledge needed)

These are the tools most LLMs should use — they wrap common multi-step workflows:

| Tool | Description |
|------|-------------|
| `lidarr_get_overview` | System summary: health, disk space, queue, wanted, artist count |
| `lidarr_search_tools` | Keyword search across all tool names/descriptions |
| `lidarr_report_issue` | Generate structured bug report |

### Safety: Confirmation Gate

All mutations require `confirm=True`. Without it, you get a dry-run preview:

```
# Preview only — nothing changes
lidarr_add_artist(term="Linkin Park", quality_profile_id=1, root_folder_path="/music")

# Actually adds the artist
lidarr_add_artist(term="Linkin Park", quality_profile_id=1, root_folder_path="/music", confirm=True)
```

### List Tool Filtering

All `lidarr_list_*` tools support optional parameters:

- **`fields`** — Comma-separated field names to return (e.g. `"id,artistName,monitored"`)
- **`query`** — Dict of key-value pairs for row filtering (e.g. `{"monitored": true}`)

### Error Reporting

Every tool's docstring nudges AI consumers to call `lidarr_report_issue` on unexpected errors. This tool composes a ready-to-paste `gh issue create` command with structured context.

## How It Works

A Python **generator** reads the Lidarr OpenAPI 3.0.4 spec (161 paths, 236 operations) and produces the MCP server via Jinja2 templates. When Lidarr updates their API, pull a new spec and re-run:

```bash
nix develop -c python -m generator    # regenerates generated/server.py
```

The generated server uses FastMCP with a single `LidarrClient` class (httpx + API key auth via `X-Api-Key` header). One async tool function per API operation. Never hand-edit the generated output — fix the generator instead.

### Architecture

```
spec/openapi.json              # Lidarr OpenAPI 3.0.4 spec (input, 161 paths)
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
```

## Testing

### Unit Tests (no Lidarr needed)

```bash
nix develop -c python -m pytest tests/ -v
```

### Integration Tests (needs Lidarr)

```bash
# Start Lidarr in Docker
docker compose -f docker/docker-compose.yml up -d

# Wait for ready
bash docker/wait-for-ready.sh

# Run integration tests
nix develop -c python -m pytest tests/test_integration.py -v --integration

# Tear down
docker compose -f docker/docker-compose.yml down
```

## Sprint Plan

### Sprint 1: Generator Core
- [ ] OpenAPI spec loader (`loader.py`) — parse paths, operations, schemas
- [ ] Naming conventions (`naming.py`) — `operationId` to `lidarr_{verb}_{resource}`
- [ ] Schema parser (`schema_parser.py`) — extract parameter types, handle `$ref`, `allOf`
- [ ] Context builder (`context_builder.py`) — assign modules, build template context
- [ ] Code generator (`codegen.py`) — render server.py via Jinja2
- [ ] Server template (`server.py.j2`) — FastMCP server with LidarrClient, module gating, confirm gates
- [ ] Generate and verify tool count matches spec

### Sprint 2: Quality & Correctness
- [ ] Apply MCP best practices (see `research/mcp-server-best-practices.md`)
  - Sanitize large integers (>= 2^53)
  - Exclude readOnly fields from request parameters
  - Enum values in parameter descriptions
  - Conditional required fields downgraded to optional
  - Strip HTML from descriptions
  - PATCH defaults to None
- [ ] List tool enhancements: `fields`, `query` parameters, "Known fields" in docstrings
- [ ] High-level tools: `lidarr_get_overview`, `lidarr_search_tools`, `lidarr_report_issue`
- [ ] Unit tests: naming, modules, list tools

### Sprint 3: Nix Packaging & Integration
- [ ] `flake.nix` with package + devShell
- [ ] `pyproject.toml` with uv dependencies
- [ ] Docker compose for integration testing
- [ ] Integration tests against live Lidarr

### Sprint 4: LLM Testing (Bank Tester)
- [ ] Task config and auto-generated task files
- [ ] Run bank tests against Lidarr in Docker
- [ ] Analyze coverage, fix first-attempt failures
- [ ] Docstring improvements from test feedback

### Sprint 5: Documentation & Release
- [ ] Fill in tool counts in README
- [ ] Add bank tester coverage table
- [ ] Wire into nixosconfig `.mcp.json`
- [ ] Replace `mcp-arr-server` wrapper

## This Project is AI-Generated

Every file in this repository was written by Claude (Anthropic). The generator, the templates, the test suite, this README — all of it. Designed for AI-to-AI use: an AI generates the server, AI agents consume it to manage Lidarr music libraries.

Humans are welcome too.

## Dependencies

**Nix users:** `nix run github:abl030/lidarr-mcp` — everything bundled.

**Non-Nix users:** Python 3.11+, [uv](https://docs.astral.sh/uv/), fastmcp, httpx, jinja2 (installed by `uv sync`).

## License

MIT
