"""MCP tools for Granola meeting data."""

import zoneinfo
from datetime import datetime
from typing import Annotated, Any, Literal

from fastmcp import Context
from pydantic import Field

from granola_fast_mcp.cache import get_cache_mtime, load_cache
from granola_fast_mcp.server import mcp
from granola_fast_mcp.timezone import format_local_time
from granola_fast_mcp.types import CacheData, MeetingMetadata

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_state(ctx: Context) -> tuple[CacheData, zoneinfo.ZoneInfo]:
    """Extract cache and timezone from lifespan context.

    Automatically reloads the cache from disk when the file has been
    modified since the last load, so new meetings and updated notes
    appear without restarting the server.
    """
    lc: dict[str, Any] = ctx.request_context.lifespan_context
    config = lc["config"]
    current_mtime = get_cache_mtime(config.cache_path)
    if current_mtime != lc["cache_mtime"]:
        lc["cache"] = load_cache(config.cache_path)
        lc["cache_mtime"] = current_mtime
    return lc["cache"], lc["tz"]


_TOOL_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool(annotations=_TOOL_ANNOTATIONS)
def search_meetings(
    query: Annotated[str, Field(description="Search query for meetings")],
    ctx: Context,
    limit: Annotated[
        int, Field(description="Maximum number of results", ge=1, le=50)
    ] = 10,
) -> str:
    """Search meetings by title, content, or participants."""
    cache, tz = _get_state(ctx)

    if not cache.meetings:
        return "No meeting data available"

    query_lower = query.lower()
    scored: list[tuple[int, MeetingMetadata]] = []

    for meeting_id, meeting in cache.meetings.items():
        score = 0
        if query_lower in meeting.title.lower():
            score += 2
        for participant in meeting.participants:
            if query_lower in participant.lower():
                score += 1
        if meeting_id in cache.transcripts:
            if query_lower in cache.transcripts[meeting_id].content.lower():
                score += 1
        if score > 0:
            scored.append((score, meeting))

    scored.sort(key=lambda x: x[0], reverse=True)
    scored = scored[:limit]

    if not scored:
        return f"No meetings found matching '{query}'"

    lines = [f"Found {len(scored)} meeting(s) matching '{query}':\n"]
    for _score, meeting in scored:
        lines.append(f"• **{meeting.title}** ({meeting.id})")
        lines.append(f"  Date: {format_local_time(meeting.date, tz)}")
        if meeting.participants:
            lines.append(f"  Participants: {', '.join(meeting.participants)}")
        lines.append("")

    return "\n".join(lines)


@mcp.tool(annotations=_TOOL_ANNOTATIONS)
def get_meeting(
    meeting_id: Annotated[str, Field(description="Meeting ID to retrieve")],
    ctx: Context,
) -> str:
    """Get detailed information about a specific meeting."""
    cache, tz = _get_state(ctx)

    if meeting_id not in cache.meetings:
        return f"Meeting '{meeting_id}' not found"

    meeting = cache.meetings[meeting_id]

    details = [
        f"# Meeting Details: {meeting.title}\n",
        f"**ID:** {meeting.id}",
        f"**Date:** {format_local_time(meeting.date, tz)}",
    ]

    if meeting.duration:
        details.append(f"**Duration:** {meeting.duration} minutes")
    if meeting.participants:
        details.append(f"**Participants:** {', '.join(meeting.participants)}")
    if meeting.meeting_type:
        details.append(f"**Type:** {meeting.meeting_type}")
    if meeting.platform:
        details.append(f"**Platform:** {meeting.platform}")

    doc_count = sum(1 for d in cache.documents.values() if d.meeting_id == meeting_id)
    if doc_count > 0:
        details.append(f"**Documents:** {doc_count}")

    if meeting_id in cache.transcripts:
        details.append("**Transcript:** Available")

    return "\n".join(details)


@mcp.tool(annotations=_TOOL_ANNOTATIONS)
def get_transcript(
    meeting_id: Annotated[str, Field(description="Meeting ID to get transcript for")],
    ctx: Context,
) -> str:
    """Get the full transcript for a specific meeting."""
    cache, _tz = _get_state(ctx)

    if meeting_id not in cache.transcripts:
        return f"No transcript available for meeting '{meeting_id}'"

    transcript = cache.transcripts[meeting_id]
    meeting = cache.meetings.get(meeting_id)

    output = [f"# Transcript: {meeting.title if meeting else meeting_id}\n"]

    if transcript.speakers:
        output.append(f"**Speakers:** {', '.join(transcript.speakers)}")
    if transcript.language:
        output.append(f"**Language:** {transcript.language}")
    if transcript.confidence:
        output.append(f"**Confidence:** {transcript.confidence:.2%}")

    output.append("\n## Transcript Content\n")
    output.append(transcript.content)

    return "\n".join(output)


@mcp.tool(annotations=_TOOL_ANNOTATIONS)
def get_notes(
    meeting_id: Annotated[str, Field(description="Meeting ID to get notes for")],
    ctx: Context,
) -> str:
    """Get notes and documents associated with a meeting."""
    cache, tz = _get_state(ctx)

    documents = [d for d in cache.documents.values() if d.meeting_id == meeting_id]

    if not documents:
        return f"No documents found for meeting '{meeting_id}'"

    meeting = cache.meetings.get(meeting_id)
    output = [f"# Documents: {meeting.title if meeting else meeting_id}\n"]
    output.append(f"Found {len(documents)} document(s):\n")

    for doc in documents:
        output.append(f"## {doc.title}")
        output.append(f"**Type:** {doc.document_type}")
        output.append(f"**Created:** {format_local_time(doc.created_at, tz)}")
        if doc.tags:
            output.append(f"**Tags:** {', '.join(doc.tags)}")
        output.append(f"\n{doc.content}\n")
        output.append("---\n")

    return "\n".join(output)


@mcp.tool(annotations=_TOOL_ANNOTATIONS)
def analyze_patterns(
    pattern_type: Annotated[
        Literal["topics", "participants", "frequency"],
        Field(description="Type of pattern to analyze"),
    ],
    ctx: Context,
    start_date: Annotated[
        str | None, Field(description="Start date (ISO format, e.g. 2024-01-01)")
    ] = None,
    end_date: Annotated[
        str | None, Field(description="End date (ISO format, e.g. 2024-12-31)")
    ] = None,
) -> str:
    """Analyze patterns across multiple meetings."""
    cache, _tz = _get_state(ctx)

    if not cache.meetings:
        return "No meeting data available"

    meetings = list(cache.meetings.values())

    if start_date or end_date:
        sd = datetime.fromisoformat(start_date) if start_date else datetime.min
        ed = datetime.fromisoformat(end_date) if end_date else datetime.max
        meetings = [m for m in meetings if sd <= m.date.replace(tzinfo=None) <= ed]

    if pattern_type == "participants":
        return _analyze_participants(meetings)
    elif pattern_type == "frequency":
        return _analyze_frequency(meetings)
    else:
        return _analyze_topics(meetings)


# ---------------------------------------------------------------------------
# Pattern analysis helpers
# ---------------------------------------------------------------------------


def _analyze_participants(meetings: list[MeetingMetadata]) -> str:
    counts: dict[str, int] = {}
    for m in meetings:
        for p in m.participants:
            counts[p] = counts.get(p, 0) + 1

    if not counts:
        return "No participant data found"

    ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    lines = [
        f"# Participant Analysis ({len(meetings)} meetings)\n",
        "## Most Active Participants\n",
    ]
    for name, count in ranked[:10]:
        lines.append(f"• **{name}:** {count} meetings")
    return "\n".join(lines)


def _analyze_frequency(meetings: list[MeetingMetadata]) -> str:
    if not meetings:
        return "No meetings found for analysis"

    monthly: dict[str, int] = {}
    for m in meetings:
        key = m.date.strftime("%Y-%m")
        monthly[key] = monthly.get(key, 0) + 1

    lines = [
        f"# Meeting Frequency Analysis ({len(meetings)} meetings)\n",
        "## Meetings by Month\n",
    ]
    for month, count in sorted(monthly.items()):
        lines.append(f"• **{month}:** {count} meetings")

    avg = len(meetings) / len(monthly) if monthly else 0
    lines.append(f"\n**Average per month:** {avg:.1f}")
    return "\n".join(lines)


def _analyze_topics(meetings: list[MeetingMetadata]) -> str:
    if not meetings:
        return "No meetings found for analysis"

    stop_words = {"meeting", "call", "sync", "with"}
    counts: dict[str, int] = {}
    for m in meetings:
        for word in m.title.lower().split():
            if len(word) > 3 and word not in stop_words:
                counts[word] = counts.get(word, 0) + 1

    if not counts:
        return "No significant topics found in meeting titles"

    ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    lines = [
        f"# Topic Analysis ({len(meetings)} meetings)\n",
        "## Most Common Topics (from titles)\n",
    ]
    for topic, count in ranked[:15]:
        lines.append(f"• **{topic}:** {count} mentions")
    return "\n".join(lines)
