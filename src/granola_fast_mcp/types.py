"""Data models for Granola meeting information."""

from datetime import datetime

from pydantic import BaseModel


class MeetingMetadata(BaseModel):
    """Meeting metadata information."""

    id: str
    title: str
    date: datetime
    duration: int | None = None
    participants: list[str] = []
    meeting_type: str | None = None
    platform: str | None = None


class MeetingDocument(BaseModel):
    """Meeting document / notes information."""

    id: str
    meeting_id: str
    title: str
    content: str
    document_type: str
    created_at: datetime
    tags: list[str] = []


class MeetingTranscript(BaseModel):
    """Meeting transcript information."""

    meeting_id: str
    content: str
    speakers: list[str] = []
    language: str | None = None
    confidence: float | None = None


class CacheData(BaseModel):
    """Complete cache data structure."""

    meetings: dict[str, MeetingMetadata] = {}
    documents: dict[str, MeetingDocument] = {}
    transcripts: dict[str, MeetingTranscript] = {}
    last_updated: datetime | None = None
