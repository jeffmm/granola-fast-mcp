"""Non-destructive backup of the Granola cache with merge-based preservation."""

import json
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

_SECTIONS = ("documents", "transcripts", "documentPanels")


def _is_empty(value: Any) -> bool:
    """Return True if *value* is None, an empty list, an empty dict, or an empty string."""
    return value is None or value == [] or value == {} or value == ""


def _unwrap_cache(raw_data: dict[str, Any]) -> dict[str, Any]:
    """Unwrap Granola's nested JSON-string-inside-JSON format.

    Returns the inner dict with keys: documents, transcripts, documentPanels.
    Flat-format caches are returned as-is.
    """
    if "cache" in raw_data and isinstance(raw_data["cache"], str):
        actual = json.loads(raw_data["cache"])
        return actual.get("state", actual)
    return raw_data


@dataclass
class MergeStats:
    """Statistics from a merge operation."""

    meetings_before: int
    meetings_after: int
    new_meetings: int
    updated_meetings: int
    preserved_meetings: int


def merge_cache(
    backup: dict[str, Any],
    current: dict[str, Any],
) -> tuple[dict[str, Any], MergeStats]:
    """Merge *current* cache data into *backup*, preserving pruned meetings.

    For each section (documents, transcripts, documentPanels):
    - Meetings only in *backup* are kept (pruned from source, preserved here).
    - Meetings only in *current* are added.
    - Meetings in both are replaced with the *current* version.

    Returns the merged dict and statistics based on the ``documents`` section
    (the authoritative list of meetings).
    """
    merged: dict[str, Any] = {}

    for section in _SECTIONS:
        backup_section = backup.get(section, {})
        current_section = current.get(section, {})

        # Start with backup as the base, then layer current on top — but
        # never overwrite non-empty content with empty content (protects
        # against Granola evicting data by blanking a key rather than
        # deleting it).
        result = dict(backup_section)
        for key, value in current_section.items():
            if _is_empty(value) and not _is_empty(result.get(key)):
                continue
            result[key] = value
        merged[section] = result

    # Stats are based on the documents section (one entry per meeting)
    backup_ids = set(backup.get("documents", {}))
    current_ids = set(current.get("documents", {}))

    return merged, MergeStats(
        meetings_before=len(backup_ids),
        meetings_after=len(backup_ids | current_ids),
        new_meetings=len(current_ids - backup_ids),
        updated_meetings=len(current_ids & backup_ids),
        preserved_meetings=len(backup_ids - current_ids),
    )


def _snapshot_backup(backup_path: Path, snapshots_dir: Path) -> Path | None:
    """Copy the current backup file to a timestamped snapshot.

    Returns the snapshot path, or ``None`` if there was no existing backup.
    """
    if not backup_path.exists():
        return None
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    dest = snapshots_dir / f"backup-{stamp}.json"
    shutil.copy2(backup_path, dest)
    return dest


def _prune_snapshots(snapshots_dir: Path, max_snapshots: int) -> int:
    """Delete oldest snapshots beyond *max_snapshots*.  Returns count removed."""
    if not snapshots_dir.exists():
        return 0
    snaps = sorted(snapshots_dir.glob("backup-*.json"))
    to_remove = snaps[: max(0, len(snaps) - max_snapshots)]
    for p in to_remove:
        p.unlink()
    return len(to_remove)


def run_backup(
    cache_path: str,
    backup_dir: str,
    max_snapshots: int = 10,
) -> MergeStats:
    """Run a full backup cycle: read, snapshot, merge, write, prune.

    Args:
        cache_path: Path to the live Granola cache JSON file.
        backup_dir: Directory for ``backup.json`` and ``snapshots/``.
        max_snapshots: Maximum number of timestamped snapshots to keep.

    Returns:
        Merge statistics.
    """
    backup_root = Path(backup_dir)
    backup_root.mkdir(parents=True, exist_ok=True)
    backup_path = backup_root / "backup.json"
    snapshots_dir = backup_root / "snapshots"

    # 1. Read current Granola cache
    with open(cache_path, "r", encoding="utf-8") as f:
        raw_current = json.load(f)
    current = _unwrap_cache(raw_current)

    # 2. Read existing backup (if any)
    created_at = datetime.now().isoformat()
    if backup_path.exists():
        with open(backup_path, "r", encoding="utf-8") as f:
            raw_backup = json.load(f)
        backup_data = {s: raw_backup.get(s, {}) for s in _SECTIONS}
        created_at = raw_backup.get("backup_metadata", {}).get("created_at", created_at)
    else:
        backup_data = {}

    # 3. Snapshot the existing backup before we overwrite it
    _snapshot_backup(backup_path, snapshots_dir)

    # 4. Merge
    merged, stats = merge_cache(backup_data, current)

    # 5. Write merged result with metadata
    output = {
        "backup_metadata": {
            "created_at": created_at,
            "last_merged_at": datetime.now().isoformat(),
            "source_path": cache_path,
            "meeting_count": stats.meetings_after,
            "version": 1,
        },
        **merged,
    }
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False)

    # 6. Prune old snapshots
    _prune_snapshots(snapshots_dir, max_snapshots)

    return stats


def main() -> None:
    """CLI entry point for ``granola-backup``."""
    from .config import Config

    config = Config()

    if not Path(config.cache_path).exists():
        print(f"Cache file not found: {config.cache_path}")
        sys.exit(1)

    stats = run_backup(config.cache_path, config.backup_dir, config.max_snapshots)

    print("Granola cache backup complete.")
    print(f"  Meetings before: {stats.meetings_before}")
    print(f"  Meetings after:  {stats.meetings_after}")
    print(f"  New:             {stats.new_meetings}")
    print(f"  Updated:         {stats.updated_meetings}")
    print(f"  Preserved:       {stats.preserved_meetings}")
    print(f"  Backup location: {config.backup_dir}/backup.json")
