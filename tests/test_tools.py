"""Integration tests for MCP tools via FastMCP Client."""

import json
import os
import time
from pathlib import Path

import pytest
from fastmcp import Client


def _make_server(cache_path: str):
    """Import the server module with GRANOLA_CACHE_PATH pointed at a test file.

    We need a fresh module import each time so the lifespan reads from the
    right cache path.  We set the env var *before* the lifespan runs (which
    happens when the Client connects).
    """
    os.environ["GRANOLA_CACHE_PATH"] = cache_path

    # Import the module-level `mcp` server object.
    # The lifespan hasn't fired yet — it runs when Client.__aenter__ connects.
    from granola_fast_mcp.server import mcp

    return mcp


@pytest.fixture
def client(sample_cache_path: Path):
    server = _make_server(str(sample_cache_path))
    return Client(server)


class TestSearchMeetings:
    @pytest.mark.asyncio
    async def test_search_by_title(self, client: Client):
        async with client:
            result = await client.call_tool("search_meetings", {"query": "standup"})
            text = result.content[0].text
            assert "Weekly Team Standup" in text

    @pytest.mark.asyncio
    async def test_search_by_participant(self, client: Client):
        async with client:
            result = await client.call_tool("search_meetings", {"query": "David"})
            text = result.content[0].text
            assert "Q1 Planning" in text

    @pytest.mark.asyncio
    async def test_search_no_results(self, client: Client):
        async with client:
            result = await client.call_tool(
                "search_meetings", {"query": "zzzznonexistent"}
            )
            text = result.content[0].text
            assert "No meetings found" in text

    @pytest.mark.asyncio
    async def test_search_limit(self, client: Client):
        async with client:
            # "Alice" appears in multiple meetings; limit=1 should return only one
            result = await client.call_tool(
                "search_meetings", {"query": "Alice", "limit": 1}
            )
            text = result.content[0].text
            assert text.count("•") == 1

    @pytest.mark.asyncio
    async def test_search_in_transcript(self, client: Client):
        async with client:
            result = await client.call_tool("search_meetings", {"query": "login"})
            text = result.content[0].text
            assert "Weekly Team Standup" in text


class TestGetMeeting:
    @pytest.mark.asyncio
    async def test_existing_meeting(self, client: Client):
        async with client:
            result = await client.call_tool("get_meeting", {"meeting_id": "meeting_1"})
            text = result.content[0].text
            assert "Weekly Team Standup" in text
            assert "Alice" in text
            assert "Transcript:** Available" in text

    @pytest.mark.asyncio
    async def test_missing_meeting(self, client: Client):
        async with client:
            result = await client.call_tool("get_meeting", {"meeting_id": "nope"})
            text = result.content[0].text
            assert "not found" in text


class TestGetTranscript:
    @pytest.mark.asyncio
    async def test_existing_transcript(self, client: Client):
        async with client:
            result = await client.call_tool(
                "get_transcript", {"meeting_id": "meeting_1"}
            )
            text = result.content[0].text
            assert "Good morning everyone" in text
            assert "Alice" in text

    @pytest.mark.asyncio
    async def test_missing_transcript(self, client: Client):
        async with client:
            result = await client.call_tool(
                "get_transcript", {"meeting_id": "meeting_3"}
            )
            text = result.content[0].text
            assert "No transcript available" in text


class TestGetNotes:
    @pytest.mark.asyncio
    async def test_existing_notes(self, client: Client):
        async with client:
            result = await client.call_tool("get_notes", {"meeting_id": "meeting_1"})
            text = result.content[0].text
            assert "user authentication" in text

    @pytest.mark.asyncio
    async def test_notes_from_panels(self, client: Client):
        """Notes are extracted from documentPanels when inline notes are empty."""
        async with client:
            result = await client.call_tool("get_notes", {"meeting_id": "meeting_2"})
            text = result.content[0].text
            assert "Q1 Roadmap Discussion" in text
            assert "scalability improvements" in text

    @pytest.mark.asyncio
    async def test_missing_notes(self, client: Client):
        async with client:
            result = await client.call_tool("get_notes", {"meeting_id": "nonexistent"})
            text = result.content[0].text
            assert "No documents found" in text


class TestAnalyzePatterns:
    @pytest.mark.asyncio
    async def test_participants(self, client: Client):
        async with client:
            result = await client.call_tool(
                "analyze_patterns", {"pattern_type": "participants"}
            )
            text = result.content[0].text
            assert "Participant Analysis" in text
            assert "Alice" in text

    @pytest.mark.asyncio
    async def test_frequency(self, client: Client):
        async with client:
            result = await client.call_tool(
                "analyze_patterns", {"pattern_type": "frequency"}
            )
            text = result.content[0].text
            assert "Frequency Analysis" in text
            assert "2024-01" in text

    @pytest.mark.asyncio
    async def test_topics(self, client: Client):
        async with client:
            result = await client.call_tool(
                "analyze_patterns", {"pattern_type": "topics"}
            )
            text = result.content[0].text
            assert "Topic Analysis" in text

    @pytest.mark.asyncio
    async def test_date_filter(self, client: Client):
        async with client:
            result = await client.call_tool(
                "analyze_patterns",
                {
                    "pattern_type": "frequency",
                    "start_date": "2024-02-01",
                    "end_date": "2024-12-31",
                },
            )
            text = result.content[0].text
            # Only meeting_3 is in Feb 2024
            assert "1 meetings" in text


class TestCacheAutoReload:
    """Test that _get_state reloads the cache when the file changes.

    NOTE: FastMCP's lifespan only fires once per mcp singleton, so we
    can't test auto-reload through the MCP Client in a multi-test suite.
    Instead we test the mechanism directly via the helpers it relies on.
    """

    def test_mtime_detects_file_change(self, sample_cache_path: Path):
        """get_cache_mtime returns a different value after the file is rewritten."""
        from granola_fast_mcp.cache import get_cache_mtime

        mtime1 = get_cache_mtime(str(sample_cache_path))
        assert mtime1 > 0

        # Rewrite with extra data and bump mtime into the future
        data = json.loads(sample_cache_path.read_text())
        data["documents"]["meeting_4"] = {
            "title": "Brand New Meeting",
            "created_at": "2024-03-01T10:00:00Z",
            "type": "meeting",
            "people": [{"name": "Zara"}],
        }
        sample_cache_path.write_text(json.dumps(data))
        future = time.time() + 2
        os.utime(sample_cache_path, (future, future))

        mtime2 = get_cache_mtime(str(sample_cache_path))
        assert mtime2 != mtime1

    def test_reload_picks_up_new_meetings(self, sample_cache_path: Path):
        """Calling load_cache again after a file change returns updated data."""
        from granola_fast_mcp.cache import load_cache

        cache1 = load_cache(str(sample_cache_path))
        assert len(cache1.meetings) == 3

        data = json.loads(sample_cache_path.read_text())
        data["documents"]["meeting_4"] = {
            "title": "Brand New Meeting",
            "created_at": "2024-03-01T10:00:00Z",
            "type": "meeting",
            "people": [{"name": "Zara"}],
        }
        sample_cache_path.write_text(json.dumps(data))

        cache2 = load_cache(str(sample_cache_path))
        assert len(cache2.meetings) == 4
        assert "Brand New Meeting" == cache2.meetings["meeting_4"].title


class TestToolListing:
    @pytest.mark.asyncio
    async def test_lists_all_tools(self, client: Client):
        async with client:
            tools = await client.list_tools()
            names = {t.name for t in tools}
            assert names == {
                "search_meetings",
                "get_meeting",
                "get_transcript",
                "get_notes",
                "analyze_patterns",
                "backup_cache",
            }
