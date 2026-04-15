"""Tool execution handlers — async httpx calls to the PHP API."""

import httpx
from typing import Any, Dict

from backend.config import get_settings

# Source → color mapping (also returned by list_available_sources)
SOURCE_COLORS: Dict[str, str] = {
    "Australia Post": "#FFD700",
    "APTA": "#4169E1",
    "AMPCA": "#228B22",
    "PNC": "#DC143C",
    "Philatelic": "#9370DB",
    "Maxicard": "#FF8C00",
    "Coin Cover": "#708090",
    "Other": "#A9A9A9",
}


async def _php_get(action: str, params: Dict[str, Any]) -> Any:
    """Make a GET request to the PHP API and return parsed JSON."""
    settings = get_settings()
    url = f"{settings.php_api_base_url}/api.php"
    params = {k: v for k, v in params.items() if v is not None}
    params["action"] = action

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()


async def handle_search_covers(args: Dict[str, Any]) -> Any:
    params = {
        "year": args.get("year"),
        "text": args.get("text"),
        "type": args.get("type"),
        "source": args.get("source"),
        "limit": args.get("limit", 20),
    }
    return await _php_get("search_covers", params)


async def handle_search_issues(args: Dict[str, Any]) -> Any:
    params = {
        "year": args.get("year"),
        "text": args.get("text"),
        "series": args.get("series"),
        "type": args.get("type"),
        "limit": args.get("limit", 20),
    }
    return await _php_get("search_issues", params)


async def handle_get_cover_details(args: Dict[str, Any]) -> Any:
    params = {"id": args["cover_id"]}
    return await _php_get("cover_details", params)


async def handle_get_issue_with_covers(args: Dict[str, Any]) -> Any:
    params = {"issue_id": args["issue_id"]}
    return await _php_get("issue_with_covers", params)


async def handle_get_statistics(args: Dict[str, Any]) -> Any:
    params = {
        "stat_type": args["stat_type"],
        "table": args.get("table", "covers"),
    }
    return await _php_get("statistics", params)


async def handle_list_available_sources(_args: Dict[str, Any]) -> Any:
    return {
        "sources": [
            {"name": name, "color": color}
            for name, color in SOURCE_COLORS.items()
        ],
        "description": (
            "These are the known cover makers/sources in the database. "
            "Each is represented by a color badge in the UI."
        ),
    }


TOOL_HANDLERS = {
    "search_covers": handle_search_covers,
    "search_issues": handle_search_issues,
    "get_cover_details": handle_get_cover_details,
    "get_issue_with_covers": handle_get_issue_with_covers,
    "get_statistics": handle_get_statistics,
    "list_available_sources": handle_list_available_sources,
}
