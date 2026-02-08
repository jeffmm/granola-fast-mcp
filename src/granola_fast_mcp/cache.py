"""Cache loading and Granola JSON parsing."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from .types import CacheData, MeetingDocument, MeetingMetadata, MeetingTranscript


def _extract_structured_notes(notes_data: dict[str, Any]) -> str:
    """Extract text content from Granola's structured notes format.

    Granola stores notes as a nested tree of paragraph/text nodes.
    This recursively traverses the tree to produce plain text.
    """
    if not isinstance(notes_data, dict) or "content" not in notes_data:
        return ""

    def _extract(content_list: Any) -> str:
        parts: list[str] = []
        if isinstance(content_list, list):
            for item in content_list:
                if isinstance(item, dict):
                    if item.get("type") == "text" and "text" in item:
                        parts.append(item["text"])
                    elif "content" in item:
                        parts.append(_extract(item["content"]))
        return " ".join(parts)

    try:
        return _extract(notes_data["content"])
    except Exception:
        return ""


def _parse_meetings(
    documents: dict[str, Any],
) -> dict[str, MeetingMetadata]:
    """Parse Granola documents into MeetingMetadata objects."""
    meetings: dict[str, MeetingMetadata] = {}

    for meeting_id, data in documents.items():
        try:
            participants: list[str] = []
            if isinstance(data.get("people"), list):
                participants = [
                    p.get("name", "") for p in data["people"] if p.get("name")
                ]

            created_at = data.get("created_at")
            if created_at:
                if created_at.endswith("Z"):
                    created_at = created_at[:-1] + "+00:00"
                meeting_date = datetime.fromisoformat(created_at)
            else:
                meeting_date = datetime.now()

            meetings[meeting_id] = MeetingMetadata(
                id=meeting_id,
                title=data.get("title", "Untitled Meeting"),
                date=meeting_date,
                duration=None,
                participants=participants,
                meeting_type=data.get("type", "meeting"),
                platform=None,
            )
        except Exception as e:
            print(f"Error parsing meeting {meeting_id}: {e}")

    return meetings


def _parse_transcripts(
    transcripts_raw: dict[str, Any],
) -> dict[str, MeetingTranscript]:
    """Parse Granola transcripts (list-of-segments format)."""
    transcripts: dict[str, MeetingTranscript] = {}

    for transcript_id, data in transcripts_raw.items():
        try:
            content_parts: list[str] = []
            speakers_set: set[str] = set()

            if isinstance(data, list):
                for segment in data:
                    if isinstance(segment, dict) and "text" in segment:
                        text = segment["text"].strip()
                        if text:
                            content_parts.append(text)
                        if "source" in segment:
                            speakers_set.add(segment["source"])

            elif isinstance(data, dict):
                for key in ("content", "text", "transcript"):
                    if data.get(key):
                        content_parts.append(data[key])
                        break
                if "speakers" in data:
                    speakers_set.update(data["speakers"])

            if content_parts:
                transcripts[transcript_id] = MeetingTranscript(
                    meeting_id=transcript_id,
                    content=" ".join(content_parts),
                    speakers=list(speakers_set),
                )
        except Exception as e:
            print(f"Error parsing transcript {transcript_id}: {e}")

    return transcripts


def _parse_documents(
    documents_raw: dict[str, Any],
    meetings: dict[str, MeetingMetadata],
    panels_raw: dict[str, Any] | None = None,
) -> dict[str, MeetingDocument]:
    """Extract document/notes content from Granola documents.

    Granola stores notes in two places:
    - ``documents[id].notes_plain`` / ``notes_markdown`` / ``notes`` (legacy)
    - ``documentPanels[id][panel_id].content`` (current AI-generated summaries)

    We prefer the inline fields when present and fall back to panels.
    """
    docs: dict[str, MeetingDocument] = {}

    for doc_id, data in documents_raw.items():
        try:
            content_parts: list[str] = []

            # 1. Inline note fields on the document itself
            if data.get("notes_plain"):
                content_parts.append(data["notes_plain"])
            elif data.get("notes_markdown"):
                content_parts.append(data["notes_markdown"])
            elif isinstance(data.get("notes"), dict):
                notes_text = _extract_structured_notes(data["notes"])
                if notes_text:
                    content_parts.append(notes_text)

            # 2. Fall back to documentPanels (AI-generated summaries)
            if not content_parts and panels_raw and doc_id in panels_raw:
                panel_dict = panels_raw[doc_id]
                if isinstance(panel_dict, dict):
                    for panel_data in panel_dict.values():
                        if isinstance(panel_data, dict):
                            panel_content = panel_data.get("content")
                            if isinstance(panel_content, dict):
                                text = _extract_structured_notes(panel_content)
                                if text:
                                    content_parts.append(text)

            if data.get("overview"):
                content_parts.append(f"Overview: {data['overview']}")
            if data.get("summary"):
                content_parts.append(f"Summary: {data['summary']}")

            content = "\n\n".join(content_parts)

            if doc_id in meetings:
                meeting = meetings[doc_id]
                docs[doc_id] = MeetingDocument(
                    id=doc_id,
                    meeting_id=doc_id,
                    title=meeting.title,
                    content=content,
                    document_type="meeting_notes",
                    created_at=meeting.date,
                    tags=[],
                )
        except Exception as e:
            print(f"Error extracting document content for {doc_id}: {e}")

    return docs


def load_cache(cache_path: str) -> CacheData:
    """Load and parse Granola cache data.

    Args:
        cache_path: Path to the Granola cache JSON file.

    Returns:
        Parsed CacheData (empty if file is missing or unparseable).
    """
    path = Path(cache_path)
    if not path.exists():
        return CacheData()

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except Exception as e:
        print(f"Error loading cache: {e}")
        return CacheData()

    # Unwrap Granola's nested JSON-string-inside-JSON structure
    if "cache" in raw_data and isinstance(raw_data["cache"], str):
        actual = json.loads(raw_data["cache"])
        raw_data = actual.get("state", actual)

    documents_raw = raw_data.get("documents", {})
    transcripts_raw = raw_data.get("transcripts", {})
    panels_raw = raw_data.get("documentPanels", {})

    meetings = _parse_meetings(documents_raw)
    transcripts = _parse_transcripts(transcripts_raw)
    documents = _parse_documents(documents_raw, meetings, panels_raw)

    return CacheData(
        meetings=meetings,
        documents=documents,
        transcripts=transcripts,
        last_updated=datetime.now(),
    )


def get_cache_mtime(cache_path: str) -> float:
    """Return the modification time of the cache file, or 0.0 if missing."""
    try:
        return os.path.getmtime(cache_path)
    except OSError:
        return 0.0
