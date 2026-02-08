# MCP Server Smoke Test Plan

Run these checks once the `granola` MCP server is connected.

## 1. Tool discovery

- List tools and confirm all 5 are present: `search_meetings`, `get_meeting`, `get_transcript`, `get_notes`, `analyze_patterns`

## 2. search_meetings

- Search with a broad query (e.g. a common participant name or keyword from recent meetings)
- Verify results include meeting ID, title, date, and participants
- Confirm results are ordered by relevance (title matches ranked above transcript-only matches)

## 3. get_meeting

- Pick a meeting ID from the search results
- Call `get_meeting` with that ID
- Verify it returns title, date, participants, type, and transcript/document availability indicators

## 4. get_transcript

- Using the same meeting ID, call `get_transcript`
- Verify it returns speaker list and transcript content
- Also call with a meeting ID that has no transcript and confirm the "no transcript available" message

## 5. get_notes

- Call `get_notes` for a meeting that has document content
- Verify it returns notes/summary text with document type and created date
- Call for a meeting with no notes and confirm the empty-state message

## 6. analyze_patterns

- Call with `pattern_type: "participants"` -- verify ranked participant list with meeting counts
- Call with `pattern_type: "frequency"` -- verify monthly breakdown and average
- Call with `pattern_type: "topics"` -- verify keyword extraction from titles
- Call with `pattern_type: "frequency"` plus `start_date`/`end_date` filters -- verify the count is a subset of the unfiltered result

## 7. Edge cases

- `get_meeting` with a bogus ID -- should return "not found", not an error
- `search_meetings` with a nonsense query -- should return "no meetings found", not an error
- `analyze_patterns` with no date filters and then with a date range that excludes all meetings -- should return gracefully

## Pass criteria

Every call returns a text response (no `isError: true`). Filtered/empty results return human-readable messages, not exceptions.
