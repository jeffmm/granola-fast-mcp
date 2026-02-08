# granola-fast-mcp

An MCP server that exposes your [Granola.ai](https://granola.ai) meeting data — search, transcripts, notes, and pattern analysis — as read-only tools. Built with [FastMCP](https://github.com/jlowin/fastmcp) v2.

It reads directly from Granola's local cache file on disk. No API keys, no external calls.

## Tools

| Tool | Description |
|------|-------------|
| `search_meetings` | Search by title, participant, or transcript content |
| `get_meeting` | Meeting details (title, date, type, participants) |
| `get_transcript` | Full transcript with speaker labels |
| `get_notes` | AI-generated meeting notes and summaries |
| `analyze_patterns` | Cross-meeting analysis: topics, participants, frequency |

## Setup

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

### Claude Desktop

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "granola": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/granola-fast-mcp", "granola-fast-mcp"]
    }
  }
}
```

### Claude Code

```bash
claude mcp add granola -- uv run --directory /path/to/granola-fast-mcp granola-fast-mcp
```

## How it works

Granola's desktop app writes meeting data to `~/Library/Application Support/Granola/cache-v3.json`. This server parses that file into structured meeting, transcript, and document data exposed as MCP tools.

The cache auto-reloads when the file changes — new meetings and updated notes appear without restarting the server.

To use a different cache file path, set `GRANOLA_CACHE_PATH`:

```bash
GRANOLA_CACHE_PATH=/path/to/cache.json uv run granola-fast-mcp
```

## Development

```bash
uv run pytest              # run tests
uv run ruff format src/ tests/   # format
uv run ruff check src/ tests/    # lint
uv run prek                # run all pre-commit hooks
```
