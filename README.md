# granola-fast-mcp

An MCP server that exposes your [Granola.ai](https://granola.ai) meeting data — search, transcripts, notes, and pattern analysis — as tools. Built with [FastMCP](https://github.com/jlowin/fastmcp) v2.

It reads directly from Granola's local cache file on disk. No API keys, no external calls. Includes a non-destructive backup system that preserves meeting data (especially transcripts) that Granola may evict from its local cache.

> **Note:** The default cache path assumes macOS (`~/Library/Application Support/Granola/cache-v3.json`). If you're running Granola on another platform, set the `GRANOLA_CACHE_PATH` environment variable to the correct location.

## Tools

| Tool | Description |
|------|-------------|
| `search_meetings` | Search by title, participant, or transcript content |
| `get_meeting` | Meeting details (title, date, type, participants) |
| `get_transcript` | Full transcript with speaker labels |
| `get_notes` | AI-generated meeting notes and summaries |
| `analyze_patterns` | Cross-meeting analysis: topics, participants, frequency |
| `backup_cache` | Non-destructive backup of meeting data to `~/.granola-backup/` |

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

### Automatic backups

On startup (and whenever the live cache changes), the server merges the Granola cache into a local backup at `~/.granola-backup/backup.json`, then serves data from the backup. This is important because Granola's local cache evicts transcripts after a few days — the backup preserves them indefinitely.

The merge is non-destructive: meetings that disappear from the live cache are kept in the backup, and empty values never overwrite real data. Timestamped snapshots of the backup are saved before each merge as a safety net.

You can also run the backup manually:

```bash
uv run granola-backup
```

**Tip:** Granola only loads transcripts into the local cache when you open a meeting in the app. To backfill transcripts for older meetings, click through them in Granola, then run a backup to capture them before they get evicted.

### Configuration

Settings are managed via environment variables (prefixed with `GRANOLA_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `GRANOLA_CACHE_PATH` | `~/Library/Application Support/Granola/cache-v3.json` | Path to Granola's cache file |
| `GRANOLA_BACKUP_DIR` | `~/.granola-backup` | Directory for backup files and snapshots |
| `GRANOLA_MAX_SNAPSHOTS` | `10` | Maximum timestamped snapshots to retain |
| `GRANOLA_LOG_LEVEL` | `info` | Logging level |

## Development

```bash
uv run pytest              # run tests
uv run ruff format src/ tests/   # format
uv run ruff check src/ tests/    # lint
uv run prek                # run all pre-commit hooks
```
