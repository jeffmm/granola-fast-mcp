"""Granola MCP Server — FastMCP v2 implementation."""

from contextlib import asynccontextmanager

from fastmcp import FastMCP

from .cache import get_cache_mtime, load_cache
from .config import Config
from .timezone import detect_local_timezone

# ---------------------------------------------------------------------------
# Lifespan: load config, cache, and detect timezone once at startup
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(server: FastMCP):
    config = Config()
    cache = load_cache(config.cache_path)
    mtime = get_cache_mtime(config.cache_path)
    tz = detect_local_timezone()
    yield {"cache": cache, "tz": tz, "config": config, "cache_mtime": mtime}


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
