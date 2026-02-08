"""Tests for cache loading and parsing."""

import json
from pathlib import Path

from granola_fast_mcp.cache import load_cache


class TestLoadCache:
    """Test load_cache with various input formats."""

    def test_flat_format(self, sample_cache_path: Path):
        """Cache with documents/transcripts at top level."""
        cache = load_cache(str(sample_cache_path))

        assert len(cache.meetings) == 3
        assert len(cache.transcripts) == 2
        assert len(cache.documents) == 3
        assert cache.last_updated is not None

    def test_nested_format(self, sample_nested_cache_path: Path):
        """Cache wrapped in Granola's JSON-string-inside-JSON structure."""
        cache = load_cache(str(sample_nested_cache_path))

        assert len(cache.meetings) == 3
        assert len(cache.transcripts) == 2

    def test_meeting_fields(self, sample_cache_path: Path):
        """Meeting metadata is parsed correctly."""
        cache = load_cache(str(sample_cache_path))
        m = cache.meetings["meeting_1"]

        assert m.title == "Weekly Team Standup"
        assert m.meeting_type == "standup"
        assert set(m.participants) == {"Alice", "Bob", "Charlie"}
        assert m.date.year == 2024
        assert m.date.month == 1
        assert m.date.day == 15

    def test_transcript_segments(self, sample_cache_path: Path):
        """Transcript segments are joined and speakers extracted."""
        cache = load_cache(str(sample_cache_path))
        t = cache.transcripts["meeting_1"]

        assert "Good morning everyone." in t.content
        assert "user login feature" in t.content
        assert set(t.speakers) == {"Alice", "Bob", "Charlie"}

    def test_document_notes_plain(self, sample_cache_path: Path):
        """notes_plain is preferred for document content."""
        cache = load_cache(str(sample_cache_path))
        doc = cache.documents["meeting_1"]

        assert "user authentication" in doc.content
        assert "Overview: Sprint planning discussion" in doc.content
        assert "Summary: Team aligned on Q1 goals" in doc.content

    def test_document_notes_markdown(self, sample_cache_path: Path):
        """notes_markdown is used when notes_plain is absent."""
        cache = load_cache(str(sample_cache_path))
        doc = cache.documents["meeting_3"]

        assert "Optimize slow queries" in doc.content

    def test_nonexistent_file(self, tmp_path: Path):
        """Missing cache file returns empty CacheData."""
        cache = load_cache(str(tmp_path / "does_not_exist.json"))

        assert len(cache.meetings) == 0
        assert len(cache.transcripts) == 0
        assert len(cache.documents) == 0

    def test_invalid_json(self, tmp_path: Path):
        """Corrupt JSON returns empty CacheData."""
        bad = tmp_path / "bad.json"
        bad.write_text("not json at all {{{")

        cache = load_cache(str(bad))
        assert len(cache.meetings) == 0

    def test_empty_documents(self, tmp_path: Path):
        """Cache with no documents produces empty results."""
        path = tmp_path / "empty.json"
        path.write_text(json.dumps({"documents": {}, "transcripts": {}}))

        cache = load_cache(str(path))
        assert len(cache.meetings) == 0
        assert len(cache.transcripts) == 0

    def test_transcript_dict_format(self, tmp_path: Path):
        """Legacy dict-format transcripts are handled."""
        data = {
            "documents": {
                "m1": {
                    "title": "Test",
                    "created_at": "2024-06-01T12:00:00Z",
                    "people": [],
                }
            },
            "transcripts": {
                "m1": {
                    "content": "Hello from dict format",
                    "speakers": ["Speaker A"],
                }
            },
        }
        path = tmp_path / "dict_transcript.json"
        path.write_text(json.dumps(data))

        cache = load_cache(str(path))
        assert "Hello from dict format" in cache.transcripts["m1"].content
        assert "Speaker A" in cache.transcripts["m1"].speakers

    def test_structured_notes(self, tmp_path: Path):
        """Granola's nested paragraph/text node structure is extracted."""
        data = {
            "documents": {
                "m1": {
                    "title": "Structured",
                    "created_at": "2024-06-01T12:00:00Z",
                    "people": [],
                    "notes": {
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [
                                    {"type": "text", "text": "First paragraph."}
                                ],
                            },
                            {
                                "type": "paragraph",
                                "content": [
                                    {"type": "text", "text": "Second paragraph."}
                                ],
                            },
                        ]
                    },
                }
            },
            "transcripts": {},
        }
        path = tmp_path / "structured.json"
        path.write_text(json.dumps(data))

        cache = load_cache(str(path))
        doc = cache.documents["m1"]
        assert "First paragraph." in doc.content
        assert "Second paragraph." in doc.content

    def test_document_panels_fallback(self, tmp_path: Path):
        """AI-generated notes in documentPanels are used when inline notes are empty."""
        data = {
            "documents": {
                "m1": {
                    "title": "Panel Meeting",
                    "created_at": "2024-06-01T12:00:00Z",
                    "people": [],
                    "notes": {
                        "type": "doc",
                        "content": [{"type": "paragraph", "attrs": {"id": "x"}}],
                    },
                }
            },
            "transcripts": {},
            "documentPanels": {
                "m1": {
                    "p1": {
                        "id": "p1",
                        "document_id": "m1",
                        "title": "Summary",
                        "content": {
                            "type": "doc",
                            "content": [
                                {
                                    "type": "heading",
                                    "attrs": {"level": 3},
                                    "content": [
                                        {"type": "text", "text": "Key Decisions"}
                                    ],
                                },
                                {
                                    "type": "paragraph",
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": "Decided to migrate to new platform",
                                        }
                                    ],
                                },
                            ],
                        },
                    }
                },
            },
        }
        path = tmp_path / "panels.json"
        path.write_text(json.dumps(data))

        cache = load_cache(str(path))
        doc = cache.documents["m1"]
        assert "Key Decisions" in doc.content
        assert "migrate to new platform" in doc.content

    def test_inline_notes_preferred_over_panels(self, tmp_path: Path):
        """Inline notes_plain takes priority over documentPanels content."""
        data = {
            "documents": {
                "m1": {
                    "title": "Both Sources",
                    "created_at": "2024-06-01T12:00:00Z",
                    "people": [],
                    "notes_plain": "Inline notes content here",
                }
            },
            "transcripts": {},
            "documentPanels": {
                "m1": {
                    "p1": {
                        "id": "p1",
                        "content": {
                            "type": "doc",
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [
                                        {"type": "text", "text": "Panel content"}
                                    ],
                                }
                            ],
                        },
                    }
                },
            },
        }
        path = tmp_path / "both.json"
        path.write_text(json.dumps(data))

        cache = load_cache(str(path))
        doc = cache.documents["m1"]
        assert "Inline notes content here" in doc.content
        assert "Panel content" not in doc.content
