"""Granola MCP Server — FastMCP v2 implementation."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastmcp import FastMCP

from .backup import run_backup
from .cache import get_cache_mtime, load_cache
from .config import Config
from .timezone import detect_local_timezone

# ---------------------------------------------------------------------------
# Lifespan: backup cache, load from backup, and detect timezone
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(server: FastMCP):
    config = Config()
    backup_path = str(Path(config.backup_dir) / "backup.json")

    # Merge live cache into backup, then load from backup (the superset)
    if Path(config.cache_path).exists():
        run_backup(config.cache_path, config.backup_dir, config.max_snapshots)

    cache = load_cache(backup_path)
    mtime = get_cache_mtime(config.cache_path)
    tz = detect_local_timezone()
    yield {
        "cache": cache,
        "tz": tz,
        "config": config,
        "cache_mtime": mtime,
        "backup_path": backup_path,
    }


# ---------------------------------------------------------------------------
# Server instance
# ---------------------------------------------------------------------------

mcp = FastMCP("granola", lifespan=lifespan)

# Importing tool modules triggers @mcp.tool() registration
from granola_fast_mcp.tools import backup_ops, meeting_ops  # noqa: E402, F401

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    mcp.run()
