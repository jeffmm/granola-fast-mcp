"""Shared fixtures for tests."""

import json
from pathlib import Path

import pytest

# Sample data matching Granola's real cache format (documents at top level,
# participants in a "people" array, transcripts as segment lists).
SAMPLE_CACHE_GRANOLA_FORMAT: dict = {
    "documents": {
        "meeting_1": {
            "title": "Weekly Team Standup",
            "created_at": "2024-01-15T10:00:00Z",
            "type": "standup",
            "people": [
                {"name": "Alice"},
                {"name": "Bob"},
                {"name": "Charlie"},
            ],
            "notes_plain": "Focus on user authentication and database optimization",
            "overview": "Sprint planning discussion",
            "summary": "Team aligned on Q1 goals",
        },
        "meeting_2": {
            "title": "Q1 Planning Session",
            "created_at": "2024-01-20T14:00:00Z",
            "type": "planning",
            "people": [
                {"name": "Alice"},
                {"name": "David"},
                {"name": "Eve"},
            ],
        },
        "meeting_3": {
            "title": "Database Optimization Review",
            "created_at": "2024-02-05T09:00:00Z",
            "type": "review",
            "people": [
                {"name": "Bob"},
                {"name": "Charlie"},
            ],
            "notes_markdown": "## Action Items\n- Optimize slow queries\n- Add indexes",
        },
    },
    "transcripts": {
        "meeting_1": [
            {"text": "Good morning everyone.", "source": "Alice"},
            {"text": "Let's start with yesterday's progress.", "source": "Alice"},
            {"text": "I completed the user login feature.", "source": "Bob"},
            {"text": "I'm working on database queries.", "source": "Charlie"},
        ],
        "meeting_2": [
            {"text": "Let's discuss Q1 roadmap.", "source": "Alice"},
            {"text": "We need to focus on scalability.", "source": "David"},
        ],
    },
    "documentPanels": {
        "meeting_2": {
            "panel_1": {
                "id": "panel_1",
                "document_id": "meeting_2",
                "title": "Summary",
                "template_slug": "meeting-summary-consolidated",
                "created_at": "2024-01-20T15:00:00Z",
                "updated_at": "2024-01-20T15:00:00Z",
                "content": {
                    "type": "doc",
                    "content": [
                        {
                            "type": "heading",
                            "attrs": {"level": 3},
                            "content": [
                                {"type": "text", "text": "Q1 Roadmap Discussion"}
                            ],
                        },
                        {
                            "type": "bulletList",
                            "content": [
                                {
                                    "type": "listItem",
                                    "content": [
                                        {
                                            "type": "paragraph",
                                            "content": [
                                                {
                                                    "type": "text",
                                                    "text": "Team agreed to prioritize scalability improvements",
                                                }
                                            ],
                                        }
                                    ],
                                }
                            ],
                        },
                    ],
                },
            }
        },
    },
}


# The same data wrapped in Granola's real nested JSON-string format.
SAMPLE_CACHE_NESTED: dict = {
    "cache": json.dumps({"state": SAMPLE_CACHE_GRANOLA_FORMAT}),
}


@pytest.fixture
def sample_cache_path(tmp_path: Path) -> Path:
    """Write sample Granola-format cache to a temp file and return its path."""
    path = tmp_path / "cache-v3.json"
    path.write_text(json.dumps(SAMPLE_CACHE_GRANOLA_FORMAT))
    return path


@pytest.fixture
def sample_nested_cache_path(tmp_path: Path) -> Path:
    """Write nested (real Granola) cache format to a temp file."""
    path = tmp_path / "cache-v3.json"
    path.write_text(json.dumps(SAMPLE_CACHE_NESTED))
    return path
