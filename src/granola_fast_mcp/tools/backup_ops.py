"""MCP tool for triggering a Granola cache backup."""

from typing import Any

from fastmcp import Context

from granola_fast_mcp.backup import run_backup
from granola_fast_mcp.server import mcp

_TOOL_ANNOTATIONS = {
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}


@mcp.tool(annotations=_TOOL_ANNOTATIONS)
def backup_cache(ctx: Context) -> str:
    """Create a non-destructive backup of the Granola meeting cache.

    Merges the current cache into the backup file, preserving any
    meetings that may have been pruned from the live cache.  Also
    creates a timestamped snapshot of the previous backup state.
    """
    lc: dict[str, Any] = ctx.request_context.lifespan_context
    config = lc["config"]

    try:
        stats = run_backup(config.cache_path, config.backup_dir, config.max_snapshots)
    except FileNotFoundError:
        return f"Cache file not found: {config.cache_path}"
    except Exception as e:
        return f"Backup failed: {e}"

    return (
        f"# Backup Complete\n\n"
        f"- **Meetings before:** {stats.meetings_before}\n"
        f"- **Meetings after:** {stats.meetings_after}\n"
        f"- **New:** {stats.new_meetings}\n"
        f"- **Updated:** {stats.updated_meetings}\n"
        f"- **Preserved:** {stats.preserved_meetings}\n"
        f"- **Location:** `{config.backup_dir}/backup.json`"
    )
