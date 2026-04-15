"""Tool definitions for the Claude agent — JSON schema for all 6 tools."""

TOOLS = [
    {
        "name": "search_covers",
        "description": (
            "Search the Australian First Day Cover (FDC) database. "
            "Returns matching covers with their catalogue IDs, titles, dates, sources, "
            "up to 4 cover images, and the parent stamp issue title and stamp image. "
            "Use this for queries about physical covers: who made them, what they look like, "
            "which makers/sources are represented. "
            "year can be a 4-digit year (e.g. 1985) or a decade prefix (e.g. 198 for 1980s)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Free-text search across cover Title, AKA, and parent issue Title and Series.",
                },
                "year": {
                    "type": "string",
                    "description": "Filter by year (e.g. '1985') or decade prefix (e.g. '198' for 1980s).",
                },
                "type": {
                    "type": "string",
                    "description": "Filter by cover type, e.g. 'FDC', 'Coin Cover', 'Maxicard'.",
                },
                "source": {
                    "type": "string",
                    "description": "Filter by maker/source, e.g. 'Australia Post', 'APTA', 'PNC'.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default 20, max 100).",
                    "default": 20,
                },
            },
            "required": [],
        },
    },
    {
        "name": "search_issues",
        "description": (
            "Search stamp issues in the Australian FDC database. "
            "Returns matching stamp issues with their IssueId, title, date, type, stamps, "
            "and stamp image. Use this when the user asks about stamp issues, series, "
            "or wants to find what stamp releases exist (independent of the covers made for them)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Free-text search across issue Title, AKA, and Series.",
                },
                "year": {
                    "type": "string",
                    "description": "Filter by year (e.g. '1985') or decade prefix (e.g. '198' for 1980s).",
                },
                "series": {
                    "type": "string",
                    "description": "Filter by series/set name.",
                },
                "type": {
                    "type": "string",
                    "description": "Filter by issue type.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default 20, max 100).",
                    "default": 20,
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_cover_details",
        "description": (
            "Get full details for a single cover by its CoverId (format: yyyy-Inn-mmm, "
            "e.g. '1966-I01-003'). Returns all cover fields plus the parent stamp issue record. "
            "Use this when the user asks about a specific cover by its catalogue number."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "cover_id": {
                    "type": "string",
                    "description": "The cover catalogue ID in format yyyy-Inn-mmm, e.g. '1966-I01-003'.",
                }
            },
            "required": ["cover_id"],
        },
    },
    {
        "name": "get_issue_with_covers",
        "description": (
            "Get a stamp issue and all covers made for it, by IssueId (format: yyyy-Inn, "
            "e.g. '1966-I01'). Returns the issue record plus every cover associated with it. "
            "Use this when the user wants to see all covers for a particular stamp issue."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "issue_id": {
                    "type": "string",
                    "description": "The issue catalogue ID in format yyyy-Inn, e.g. '1966-I01'.",
                }
            },
            "required": ["issue_id"],
        },
    },
    {
        "name": "get_statistics",
        "description": (
            "Get aggregate statistics about the FDC collection. "
            "Use this when the user asks how many covers or issues are in the database, "
            "asks for breakdowns by year, source, or type, or wants an overview of the collection."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "stat_type": {
                    "type": "string",
                    "enum": ["total", "by_year", "by_source", "by_type"],
                    "description": (
                        "Type of statistic: 'total' for overall count, "
                        "'by_year' for counts per year, "
                        "'by_source' for counts per maker/source, "
                        "'by_type' for counts per cover type."
                    ),
                },
                "table": {
                    "type": "string",
                    "enum": ["covers", "issues"],
                    "description": "Which table to aggregate: 'covers' or 'issues'.",
                    "default": "covers",
                },
            },
            "required": ["stat_type"],
        },
    },
    {
        "name": "list_available_sources",
        "description": (
            "List all known cover makers/sources with their color codes used in the UI. "
            "Use this when the user asks who makes FDCs, what sources are available, "
            "or asks about the color-coding system."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]
