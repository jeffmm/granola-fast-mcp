"""Tests for the non-destructive cache backup system."""

import json
from pathlib import Path

from granola_fast_mcp.backup import (
    MergeStats,
    _prune_snapshots,
    _snapshot_backup,
    _unwrap_cache,
    merge_cache,
    run_backup,
)


# ---------------------------------------------------------------------------
# _unwrap_cache
# ---------------------------------------------------------------------------


class TestUnwrapCache:
    def test_flat_format_passthrough(self):
        data = {"documents": {"m1": {}}, "transcripts": {}}
        assert _unwrap_cache(data) is data

    def test_nested_format(self):
        inner = {"documents": {"m1": {"title": "Hello"}}, "transcripts": {}}
        nested = {"cache": json.dumps({"state": inner})}
        result = _unwrap_cache(nested)
        assert result == inner

    def test_nested_without_state_key(self):
        inner = {"documents": {"m1": {}}}
        nested = {"cache": json.dumps(inner)}
        result = _unwrap_cache(nested)
        assert result == inner


# ---------------------------------------------------------------------------
# merge_cache
# ---------------------------------------------------------------------------


class TestMergeCache:
    def test_merge_into_empty_backup(self):
        current = {
            "documents": {"m1": {"title": "A"}, "m2": {"title": "B"}},
            "transcripts": {"m1": [{"text": "hi"}]},
            "documentPanels": {},
        }
        merged, stats = merge_cache({}, current)

        assert set(merged["documents"]) == {"m1", "m2"}
        assert stats == MergeStats(
            meetings_before=0,
            meetings_after=2,
            new_meetings=2,
            updated_meetings=0,
            preserved_meetings=0,
        )

    def test_preserves_pruned_meetings(self):
        backup = {
            "documents": {"old": {"title": "Old"}, "shared": {"title": "Shared v1"}},
            "transcripts": {"old": [{"text": "old transcript"}]},
            "documentPanels": {},
        }
        current = {
            "documents": {"shared": {"title": "Shared v2"}, "new": {"title": "New"}},
            "transcripts": {"shared": [{"text": "updated"}]},
            "documentPanels": {},
        }

        merged, stats = merge_cache(backup, current)

        # "old" is preserved, "shared" is updated, "new" is added
        assert set(merged["documents"]) == {"old", "shared", "new"}
        assert merged["documents"]["old"]["title"] == "Old"
        assert merged["documents"]["shared"]["title"] == "Shared v2"
        assert merged["documents"]["new"]["title"] == "New"

        # Transcript for "old" is preserved
        assert merged["transcripts"]["old"] == [{"text": "old transcript"}]
        # Transcript for "shared" is updated
        assert merged["transcripts"]["shared"] == [{"text": "updated"}]

        assert stats.meetings_before == 2
        assert stats.meetings_after == 3
        assert stats.new_meetings == 1
        assert stats.updated_meetings == 1
        assert stats.preserved_meetings == 1

    def test_updates_existing_meetings(self):
        backup = {"documents": {"m1": {"title": "Old Title"}}}
        current = {"documents": {"m1": {"title": "New Title"}}}
        merged, stats = merge_cache(backup, current)

        assert merged["documents"]["m1"]["title"] == "New Title"
        assert stats.updated_meetings == 1
        assert stats.new_meetings == 0
        assert stats.preserved_meetings == 0

    def test_empty_value_does_not_overwrite(self):
        """An empty list in current should not overwrite real data in backup."""
        backup = {
            "transcripts": {"m1": [{"text": "real transcript"}]},
            "documents": {"m1": {"title": "Meeting"}},
            "documentPanels": {"m1": {"p1": {"content": "notes"}}},
        }
        current = {
            "transcripts": {"m1": []},
            "documents": {"m1": {"title": "Meeting updated"}},
            "documentPanels": {"m1": {}},
        }
        merged, _ = merge_cache(backup, current)

        # Transcript preserved — empty [] didn't overwrite
        assert merged["transcripts"]["m1"] == [{"text": "real transcript"}]
        # Document updated normally (non-empty replaced non-empty)
        assert merged["documents"]["m1"]["title"] == "Meeting updated"
        # Panel preserved — empty {} didn't overwrite
        assert merged["documentPanels"]["m1"] == {"p1": {"content": "notes"}}

    def test_empty_value_can_fill_empty(self):
        """An empty value replacing another empty value is fine."""
        backup = {"transcripts": {"m1": []}}
        current = {"transcripts": {"m1": []}}
        merged, _ = merge_cache(backup, current)
        assert merged["transcripts"]["m1"] == []

    def test_handles_missing_sections(self):
        backup = {"documents": {"m1": {"title": "A"}}}
        current = {"documents": {"m2": {"title": "B"}}, "transcripts": {"m2": []}}
        merged, stats = merge_cache(backup, current)

        assert "m1" in merged["documents"]
        assert "m2" in merged["documents"]
        assert "m2" in merged["transcripts"]
        assert merged.get("documentPanels") == {}


# ---------------------------------------------------------------------------
# Snapshot management
# ---------------------------------------------------------------------------


class TestSnapshots:
    def test_snapshot_created(self, tmp_path: Path):
        backup_path = tmp_path / "backup.json"
        backup_path.write_text('{"documents": {}}')
        snapshots_dir = tmp_path / "snapshots"

        result = _snapshot_backup(backup_path, snapshots_dir)

        assert result is not None
        assert result.exists()
        assert result.parent == snapshots_dir
        assert json.loads(result.read_text()) == {"documents": {}}

    def test_no_snapshot_when_no_backup(self, tmp_path: Path):
        backup_path = tmp_path / "backup.json"
        snapshots_dir = tmp_path / "snapshots"
        result = _snapshot_backup(backup_path, snapshots_dir)
        assert result is None

    def test_prune_snapshots(self, tmp_path: Path):
        snapshots_dir = tmp_path / "snapshots"
        snapshots_dir.mkdir()

        # Create 5 snapshot files
        for i in range(5):
            (snapshots_dir / f"backup-2026-01-0{i + 1}T00-00-00.json").write_text("{}")

        removed = _prune_snapshots(snapshots_dir, max_snapshots=3)

        assert removed == 2
        remaining = list(snapshots_dir.glob("backup-*.json"))
        assert len(remaining) == 3

    def test_prune_keeps_newest(self, tmp_path: Path):
        snapshots_dir = tmp_path / "snapshots"
        snapshots_dir.mkdir()

        names = [
            "backup-2026-01-01T00-00-00.json",
            "backup-2026-01-02T00-00-00.json",
            "backup-2026-01-03T00-00-00.json",
        ]
        for name in names:
            (snapshots_dir / name).write_text("{}")

        _prune_snapshots(snapshots_dir, max_snapshots=2)

        remaining = sorted(p.name for p in snapshots_dir.glob("backup-*.json"))
        assert remaining == [
            "backup-2026-01-02T00-00-00.json",
            "backup-2026-01-03T00-00-00.json",
        ]


# ---------------------------------------------------------------------------
# run_backup (integration)
# ---------------------------------------------------------------------------


class TestRunBackup:
    def test_first_run(self, sample_cache_path: Path, tmp_path: Path):
        backup_dir = tmp_path / "backups"
        stats = run_backup(str(sample_cache_path), str(backup_dir))

        assert stats.meetings_before == 0
        assert stats.meetings_after == 3
        assert stats.new_meetings == 3
        assert stats.preserved_meetings == 0

        backup_file = backup_dir / "backup.json"
        assert backup_file.exists()
        data = json.loads(backup_file.read_text())
        assert "backup_metadata" in data
        assert data["backup_metadata"]["meeting_count"] == 3
        assert set(data["documents"]) == {"meeting_1", "meeting_2", "meeting_3"}

    def test_idempotent_second_run(self, sample_cache_path: Path, tmp_path: Path):
        backup_dir = tmp_path / "backups"
        run_backup(str(sample_cache_path), str(backup_dir))
        stats = run_backup(str(sample_cache_path), str(backup_dir))

        assert stats.meetings_after == 3
        assert stats.new_meetings == 0
        assert stats.updated_meetings == 3
        assert stats.preserved_meetings == 0

    def test_preserves_after_pruning(self, tmp_path: Path):
        """Simulate Granola pruning old meetings from the cache."""
        cache_path = tmp_path / "cache.json"
        backup_dir = tmp_path / "backups"

        # First backup with 3 meetings
        full_cache = {
            "documents": {
                "m1": {"title": "A"},
                "m2": {"title": "B"},
                "m3": {"title": "C"},
            },
            "transcripts": {
                "m1": [{"text": "t1"}],
                "m2": [{"text": "t2"}],
                "m3": [{"text": "t3"}],
            },
            "documentPanels": {},
        }
        cache_path.write_text(json.dumps(full_cache))
        run_backup(str(cache_path), str(backup_dir))

        # Simulate Granola pruning m1 and m2
        pruned_cache = {
            "documents": {"m3": {"title": "C updated"}},
            "transcripts": {"m3": [{"text": "t3 updated"}]},
            "documentPanels": {},
        }
        cache_path.write_text(json.dumps(pruned_cache))
        stats = run_backup(str(cache_path), str(backup_dir))

        assert stats.meetings_after == 3
        assert stats.new_meetings == 0
        assert stats.updated_meetings == 1
        assert stats.preserved_meetings == 2

        data = json.loads((backup_dir / "backup.json").read_text())
        assert set(data["documents"]) == {"m1", "m2", "m3"}
        assert data["documents"]["m1"]["title"] == "A"
        assert data["documents"]["m3"]["title"] == "C updated"
        assert data["transcripts"]["m1"] == [{"text": "t1"}]
        assert data["transcripts"]["m3"] == [{"text": "t3 updated"}]

    def test_nested_format_cache(self, sample_nested_cache_path: Path, tmp_path: Path):
        backup_dir = tmp_path / "backups"
        stats = run_backup(str(sample_nested_cache_path), str(backup_dir))

        assert stats.meetings_after == 3
        assert stats.new_meetings == 3

    def test_snapshot_created_on_second_run(
        self, sample_cache_path: Path, tmp_path: Path
    ):
        backup_dir = tmp_path / "backups"
        run_backup(str(sample_cache_path), str(backup_dir))
        run_backup(str(sample_cache_path), str(backup_dir))

        snapshots = list((backup_dir / "snapshots").glob("backup-*.json"))
        assert len(snapshots) == 1

    def test_created_at_preserved(self, sample_cache_path: Path, tmp_path: Path):
        backup_dir = tmp_path / "backups"
        run_backup(str(sample_cache_path), str(backup_dir))

        data1 = json.loads((backup_dir / "backup.json").read_text())
        created_at = data1["backup_metadata"]["created_at"]

        run_backup(str(sample_cache_path), str(backup_dir))

        data2 = json.loads((backup_dir / "backup.json").read_text())
        assert data2["backup_metadata"]["created_at"] == created_at
        assert data2["backup_metadata"]["last_merged_at"] != created_at
