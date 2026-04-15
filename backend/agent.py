"""Claude agentic tool-use loop with SSE streaming."""

import json
import uuid
from typing import AsyncGenerator, Dict, List

import anthropic

from backend.config import get_settings
from backend.tools import TOOLS
from backend.handlers import TOOL_HANDLERS

SYSTEM_PROMPT = """\
You are an expert assistant for the Australian First Day Cover (FDC) collection database at davidaedwards.com/ausfdclist.

## Your domain knowledge

**First Day Covers (FDCs)** are envelopes or cards bearing stamps cancelled on the first day of issue. \
The Australian FDC collection spans 1940 to the present day.

**Two main tables:**
- **Issues** (`yyyy-Inn`): stamp issues released by Australia Post. Each issue has a date, title, series, type, \
  stamp details, and a stamp image.
- **Covers** (`yyyy-Inn-mmm`): the physical FDCs made for each issue. Multiple covers (from different makers) \
  can exist for a single issue. Each cover has images (Pic1–Pic4), a source/maker, size, and description.

**Relationship:** A CoverId like `2024-I15-003` belongs to Issue `2024-I15` \
(drop the third segment to get the IssueId).

**Sources/makers** are color-coded in the UI:
- Australia Post: gold
- APTA (Australian Philatelic Traders Association): blue
- AMPCA: green
- PNC (Prestige Note Cover): red
- Others: various colors

## How to help users

- Translate natural-language queries into tool calls — use the right tool for the question.
- For cover searches: use `search_covers` (can filter by year, text, type, source).
- For stamp issue searches: use `search_issues`.
- For a specific cover by ID: use `get_cover_details`.
- For all covers of a stamp issue: use `get_issue_with_covers`.
- For collection statistics: use `get_statistics`.
- To explain the source color system: use `list_available_sources`.

- Be concise but informative. When you get results, summarise what was found, \
  highlight notable items, and invite follow-up questions.
- If a search returns no results, suggest alternative search terms or broader filters.
- You may call multiple tools in sequence to answer a complex question.
- Always present CoverIds and IssueIds in their catalogue format (e.g. `1966-I01-003`).
- When images are available, mention that the user can click thumbnails to view them larger.
"""

# In-memory conversation history keyed by session_id
_sessions: Dict[str, List[Dict]] = {}


def _get_or_create_session(session_id: str | None) -> tuple[str, List[Dict]]:
    if session_id is None or session_id not in _sessions:
        session_id = session_id or str(uuid.uuid4())
        _sessions[session_id] = []
    return session_id, _sessions[session_id]


async def run_agent(message: str, session_id: str | None) -> AsyncGenerator[str, None]:
    """
    Run the agentic loop and yield newline-delimited JSON events:
      {"type": "session", "session_id": "..."}
      {"type": "text", "text": "..."}
      {"type": "tool_call", "name": "...", "input": {...}}
      {"type": "tool_result", "name": "...", "result": {...}}
      {"type": "end"}
      {"type": "error", "message": "..."}
    """
    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    session_id, history = _get_or_create_session(session_id)
    yield json.dumps({"type": "session", "session_id": session_id}) + "\n"

    # Append the new user message
    history.append({"role": "user", "content": message})

    try:
        while True:
            response = await client.messages.create(
                model=settings.model,
                max_tokens=settings.max_tokens,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=history,
            )

            # Collect assistant content blocks for history
            assistant_content: List[Dict] = []

            for block in response.content:
                if block.type == "text":
                    assistant_content.append({"type": "text", "text": block.text})
                    yield json.dumps({"type": "text", "text": block.text}) + "\n"

                elif block.type == "tool_use":
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })
                    yield json.dumps({
                        "type": "tool_call",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    }) + "\n"

            # Save assistant turn
            history.append({"role": "assistant", "content": assistant_content})

            # If no tool calls, we're done
            if response.stop_reason == "end_turn":
                break

            # Execute tool calls and build tool_result messages
            tool_results: List[Dict] = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                handler = TOOL_HANDLERS.get(block.name)
                if handler is None:
                    result = {"error": f"Unknown tool: {block.name}"}
                else:
                    try:
                        result = await handler(block.input)
                    except Exception as exc:
                        result = {"error": str(exc)}

                yield json.dumps({
                    "type": "tool_result",
                    "id": block.id,
                    "name": block.name,
                    "result": result,
                }) + "\n"

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                })

            if not tool_results:
                break

            history.append({"role": "user", "content": tool_results})

    except Exception as exc:
        yield json.dumps({"type": "error", "message": str(exc)}) + "\n"

    yield json.dumps({"type": "end"}) + "\n"
