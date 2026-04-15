"""Claude agentic tool-use loop with SSE streaming."""

import json
import uuid
from typing import AsyncGenerator, Dict, List, Optional

import anthropic

from backend.config import get_settings
from backend.tools import TOOLS
from backend.handlers import TOOL_HANDLERS

SYSTEM_PROMPT = """\
You are an expert assistant for the Australian First Day Cover (FDC) collection database at davidaedwards.com/ausfdclist.

## Catalogue ID formats

**IssueId:** `yyyy-tnn`  — e.g. `1966-I01`, `2024-I15`
- `yyyy` = 4-digit year
- `t`    = single-letter issue type (see Issue Types below)
- `nn`   = 2-digit sequential number for that year+type

**CoverId:** `yyyy-tnn-mmm`  — e.g. `1966-I01-003`, `2024-I15-012`
- First two segments form the parent IssueId.
- `mmm` = 3-digit sequential number within the issue.

## Issue types (the `t` in IssueId)

| Code | Description |
|------|-------------|
| I | Regular Stamp Issue (gum, p&s) — commemorative and definitive |
| L | Stamped Label Issue |
| V | Vending Machine Issued |
| F | Frama Machine Issued |
| M | Other Machine Issued |
| C | Counter Printed Stamp Issue |
| Z | Instant Stamp Issue |
| Y | Personalised Stamp Issue |
| O | Olympic/Comm. Games Special Issue |
| X | Stamp Exhibition Special Issue |
| P | PPE/PSE only (no stamps) |
| R | Reprint/Reissue/Overprint Issue |
| S | Other Special Issue (Souvenir etc.) |

## Cover types (Covers.Type column)

| Code | Description |
|------|-------------|
| FDC | First Day Cover (gummed) |
| FDCSA | First Day Cover (self-adhesive) |
| MSFDC | First Day Cover (minisheet) |
| FDCBP | First Day Cover (booklet pane) |
| FDCFR | First Day Cover (frama label) |
| JIFDC | Joint Issue First Day Cover |
| JMSFDC | Joint Issue FDC (minisheet) |
| OCJIFDC | Other Country Joint Issue FDC |
| PFDC | Prestige First Day Cover |
| SFDC | Special First Day Cover |
| FDCSet | Set of First Day Covers |
| PPE | Pre-Paid/Pre-Stamped Envelope |
| CC | Commemorative Cover (released after FDI) |
| PCC | Prestige Comm. Cover (released after FDI) |
| PNC | Philatelic and Numismatic Cover |
| SMC | Stamp and Medallion Cover |

## Source codes (Covers.Source column — single letters)

**Australia Post family** (gold/red tones in UI):
| Code | Maker |
|------|-------|
| A | Australia Post |
| C | Collector (on AP cover) |
| G | PMG Generic/Shield |
| Z | PMG Generic/Hermes |
| S | Special Issue |

**Non-Australia Post makers** (blue/green/other tones in UI):
| Code | Maker |
|------|-------|
| T | Challis |
| E | Excelsior (Baglin) |
| U | Guthrie |
| H | Haslems Cover Service |
| J | John Gower (pre-WCS) |
| M | Mappin and Curran |
| L | Miller Bros (Orlo-Smith) |
| Y | S Mitchell |
| P | Parade, ACCA (McCallum) |
| Q | Queensland Stamp Mart |
| R | Royal |
| B | Southern Cross Printers (Bodin) |
| W | Wesley (WCS) |
| I | Wide World |
| X | Pharmaceutical |
| O | Other non-AP |

## How to help users

- Translate natural-language queries into tool calls — use the right tool for the question.
- For cover searches: use `search_covers` (filter by year, text, type, source code).
- For stamp issue searches: use `search_issues`.
- For a specific cover by ID: use `get_cover_details`.
- For all covers of a stamp issue: use `get_issue_with_covers`.
- For collection statistics: use `get_statistics`.
- To explain source codes, cover types, or issue types: use `list_available_sources`.

- When filtering by source, use the single-letter code (e.g. source="A" for Australia Post, "W" for Wesley).
- When filtering by type, use the code (e.g. type="FDC", type="PNC").
- Use the user's exact search words in text queries — never abbreviate (e.g. use "Christmas" not "Xmas", "Anniversary" not "Anniv").
- Be concise but informative. When you get results, summarise what was found, \
  highlight notable items, and invite follow-up questions.
- If a search returns no results, suggest alternative search terms or broader filters.
- You may call multiple tools in sequence to answer a complex question.
- Always present CoverIds and IssueIds in catalogue format (e.g. `1966-I01-003`, `2024-I15`).
- When images are available, mention that the user can click thumbnails to view them larger.
- When displaying statistics that show source codes, translate them to maker names.
"""

# In-memory conversation history keyed by session_id
_sessions: Dict[str, List[Dict]] = {}


def _get_or_create_session(session_id: Optional[str]) -> tuple[str, List[Dict]]:
    if session_id is None or session_id not in _sessions:
        session_id = session_id or str(uuid.uuid4())
        _sessions[session_id] = []
    return session_id, _sessions[session_id]


async def run_agent(message: str, session_id: Optional[str]) -> AsyncGenerator[str, None]:
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
