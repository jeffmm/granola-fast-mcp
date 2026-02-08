# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Python MCP (Model Context Protocol) server built with FastMCP v2 that exposes Granola.ai meeting data (meetings, transcripts, notes) as read-only tools. It reads from Granola's local JSON cache file on disk — there are no external API calls.

## Commands

```bash
# Install/sync dependencies
uv sync

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_cache.py

# Run a single test
uv run pytest tests/test_tools.py::TestSearchMeetings::test_search_by_title

# Lint and format
uv run ruff check --select I --fix src/ tests/
uv run ruff format src/ tests/

# Type check
uv run ty check

# Run all pre-commit hooks (ruff + ty)
uv run prek

# Run the MCP server
uv run granola-fast-mcp

# Build, test, format, lint via Makefile
make build   # uv sync --all-extras
make test    # uv run pytest tests/ -v
make format  # ruff format
make lint    # ruff check
```

## Architecture

**Data flow:** Granola desktop app writes `~/Library/Application Support/Granola/cache-v3.json` → `config.py` resolves the path (env var or default) → `cache.py` parses it at server startup via the lifespan → tools query the in-memory `CacheData` on each request. The cache auto-reloads when the file's mtime changes (checked in `_get_state()` on every tool call).

### Key modules (`src/granola_fast_mcp/`)

- **server.py** — FastMCP server instance (`mcp`), lifespan setup, and tool module imports. The lifespan loads config, parses cache, and detects timezone. Tool modules are imported after `mcp` is created to trigger `@mcp.tool()` registration.
- **config.py** — `Config` frozen dataclass and `load_config()`. Resolves `GRANOLA_CACHE_PATH` env var, falls back to default macOS path.
- **cache.py** — Parses Granola's cache JSON into Pydantic models. Handles two formats: flat (`{documents, transcripts}`) and nested (`{cache: "<json-string>"}` with inner `state` key). Notes content comes from `documentPanels` (AI-generated summaries) with fallback to inline `notes_plain`/`notes_markdown` fields. Also provides `get_cache_mtime()` for file-change detection.
- **types.py** — Pydantic models: `CacheData`, `MeetingMetadata`, `MeetingDocument`, `MeetingTranscript`.
- **timezone.py** — US-focused timezone detection from system clock; converts UTC datetimes to local for display.
- **tools/meeting_ops.py** — All 5 MCP tools (`search_meetings`, `get_meeting`, `get_transcript`, `get_notes`, `analyze_patterns`) and pattern analysis helpers. Imports `mcp` from `server.py` and registers tools via decorators.
- **__main__.py** — Entry point for `python -m granola_fast_mcp`.

### Testing patterns

Tests use `pytest-asyncio` with `asyncio_mode = "auto"`. Integration tests in `test_tools.py` use FastMCP's `Client` to exercise tools end-to-end — the `client` fixture sets `GRANOLA_CACHE_PATH` to a temp file containing sample data from `conftest.py`, so the lifespan reads test data instead of the real cache. Unit tests in `test_cache.py` test parsing logic by calling `load_cache()` directly with temp file paths.

**Important:** FastMCP's lifespan fires only once per `mcp` singleton, even across multiple `Client` sessions. This means integration tests all share one lifespan context. Cache auto-reload tests use unit-style assertions (calling `load_cache`/`get_cache_mtime` directly) rather than going through the MCP Client.

## Conventions

- All tools return markdown-formatted strings; errors are returned as user-friendly messages, never raised as exceptions.
- All tools are annotated as read-only, non-destructive, and idempotent (`_TOOL_ANNOTATIONS`).
- Tool parameters use `Annotated[type, Field(description=...)]` for MCP schema generation.
- Python >=3.13 required. Package manager is `uv` with `uv_build` build backend.
- Modern type hints only (`str | None`, `list[str]`, `dict[str, int]`). Never import `Optional` or `Union` from `typing`.
