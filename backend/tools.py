"""Tool definitions for the Claude agent — JSON schema for all 6 tools."""

# IssueId format:  yyyy-tnn        (e.g. 1966-I01, 2024-I15)
#   yyyy = 4-digit year
#   t    = single-letter issue type (I, L, V, F, M, C, Z, Y, O, X, P, R, S)
#   nn   = 2-digit sequential number for that year+type
#
# CoverId format:  yyyy-tnn-mmm    (e.g. 1966-I01-003, 2024-I15-012)
#   mmm  = 3-digit sequential number within the issue
#
# Join:  SUBSTRING_INDEX(CoverId, '-', 2) = IssueId

TOOLS = [
    {
        "name": "search_covers",
        "description": (
            "Search the Australian First Day Cover (FDC) database. "
            "Returns matching covers with their CoverId, title, date, source code, "
            "up to 4 cover images, and the parent stamp issue title and stamp image. "
            "Use this for queries about physical covers: who made them, what they look like, "
            "which makers/sources are represented.\n\n"
            "Cover type codes (Covers.Type): FDC, FDCSA, MSFDC, FDCBP, FDCFR, JIFDC, JMSFDC, "
            "OCJIFDC, PFDC, SFDC, FDCSet, PPE, CC, PCC, PNC, SMC.\n\n"
            "Source codes (Covers.Source) are single letters: "
            "A=Australia Post, C=Collector(AP), G=PMG Shield, Z=PMG Hermes, S=Special Issue, "
            "T=Challis, E=Excelsior, U=Guthrie, H=Haslems, J=John Gower, M=Mappin&Curran, "
            "L=Miller Bros, Y=S Mitchell, P=Parade/ACCA, Q=Qld Stamp Mart, R=Royal, "
            "B=Bodin/SCP, W=Wesley, I=Wide World, X=Pharmaceutical, O=Other.\n\n"
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
                    "description": (
                        "Filter by cover type code, e.g. 'FDC', 'FDCSA', 'MSFDC', 'PNC', 'SMC', 'PPE', 'CC'. "
                        "Partial matches are supported."
                    ),
                },
                "source": {
                    "type": "string",
                    "description": (
                        "Filter by single-letter source code, e.g. 'A' for Australia Post, "
                        "'T' for Challis, 'W' for Wesley. "
                        "Partial matches are supported."
                    ),
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
            "or wants to find what stamp releases exist (independent of the covers made for them).\n\n"
            "IssueId format: yyyy-tnn where t is a single-letter issue type:\n"
            "I=Regular Issue, L=Stamped Label, V=Vending Machine, F=Frama Machine, "
            "M=Other Machine, C=Counter Printed, Z=Instant, Y=Personalised, "
            "O=Olympic/Games, X=Stamp Exhibition, P=PPE/PSE only, R=Reprint/Reissue, "
            "S=Other Special Issue.\n\n"
            "year can be a 4-digit year (e.g. 1985) or a decade prefix (e.g. 198 for 1980s)."
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
                    "description": (
                        "Filter by issue type code — the single letter in the IssueId "
                        "(e.g. 'I' for regular issues, 'Y' for personalised stamps)."
                    ),
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
            "Get full details for a single cover by its CoverId (format: yyyy-tnn-mmm, "
            "e.g. '1966-I01-003'). Returns all cover fields plus the parent stamp issue record. "
            "Use this when the user asks about a specific cover by its catalogue number."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "cover_id": {
                    "type": "string",
                    "description": "The cover catalogue ID in format yyyy-tnn-mmm, e.g. '1966-I01-003'.",
                }
            },
            "required": ["cover_id"],
        },
    },
    {
        "name": "get_issue_with_covers",
        "description": (
            "Get a stamp issue and all covers made for it, by IssueId (format: yyyy-tnn, "
            "e.g. '1966-I01'). Returns the issue record plus every cover associated with it. "
            "Use this when the user wants to see all covers for a particular stamp issue."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "issue_id": {
                    "type": "string",
                    "description": "The issue catalogue ID in format yyyy-tnn, e.g. '1966-I01'.",
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
            "asks for breakdowns by year, source, or type, or wants an overview of the collection. "
            "Note: by_source statistics return single-letter source codes (e.g. A, T, W)."
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
                        "'by_source' for counts per maker/source code, "
                        "'by_type' for counts per cover/issue type code."
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
            "List all known cover source codes with their full names and UI colors. "
            "Also returns all cover type codes and issue type codes. "
            "Use this when the user asks who makes FDCs, what sources or types are available, "
            "or asks about the color-coding system."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]
