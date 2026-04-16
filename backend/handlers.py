"""Tool execution handlers — async httpx calls to the PHP API."""

import logging
from typing import Any, Dict, Optional

import httpx

from backend.auth.okta_sts import exchange_id_token_for_vaulted_secret
from backend.config import get_settings

logger = logging.getLogger(__name__)

# Single-letter source codes (Covers.Source column) → full names
SOURCE_NAMES: Dict[str, str] = {
    "A": "Australia Post",
    "C": "Collector (on AP cover)",
    "G": "PMG Generic/Shield",
    "Z": "PMG Generic/Hermes",
    "S": "Special Issue",
    "T": "Challis",
    "E": "Excelsior (Baglin)",
    "U": "Guthrie",
    "H": "Haslems Cover Service",
    "J": "John Gower (pre-WCS)",
    "M": "Mappin and Curran",
    "L": "Miller Bros (Orlo-Smith)",
    "Y": "S Mitchell",
    "P": "Parade, ACCA (McCallum)",
    "Q": "Queensland Stamp Mart (?)",
    "R": "Royal",
    "B": "Southern Cross Printers (Bodin)",
    "W": "Wesley (WCS)",
    "I": "Wide World",
    "X": "Pharmaceutical",
    "O": "Other non-AP",
}

# Source code → UI badge color
SOURCE_COLORS: Dict[str, str] = {
    # Australia Post family (gold/red tones)
    "A": "#d4a017",
    "C": "#c8971e",
    "G": "#b8860b",
    "Z": "#b8860b",
    "S": "#8b0000",
    # Non-AP commercial makers
    "T": "#2e5fd6",
    "E": "#1a6b4a",
    "U": "#4b3a8c",
    "H": "#c0522a",
    "J": "#2e8b57",
    "M": "#6b3a3a",
    "L": "#3a6b8c",
    "Y": "#8c6b2e",
    "P": "#4a7c59",
    "Q": "#6b4a8c",
    "R": "#8b2252",
    "B": "#8c3a3a",
    "W": "#2e6b9c",
    "I": "#2e9c8c",
    "X": "#5a5a6e",
    "O": "#6b7280",
}

# Cover type codes (Covers.Type column)
COVER_TYPES: Dict[str, str] = {
    "FDC":     "First Day Cover (gummed)",
    "FDCSA":   "First Day Cover (self-adhesive)",
    "MSFDC":   "First Day Cover (minisheet)",
    "FDCBP":   "First Day Cover (booklet pane)",
    "FDCFR":   "First Day Cover (frama label)",
    "JIFDC":   "Joint Issue First Day Cover",
    "JMSFDC":  "Joint Issue FDC (minisheet)",
    "OCJIFDC": "Other Country Joint Issue FDC",
    "PFDC":    "Prestige First Day Cover",
    "SFDC":    "Special First Day Cover",
    "FDCSet":  "Set of First Day Covers",
    "PPE":     "Pre-Paid Envelope/Pre-Stamped Envelope",
    "CC":      "Commemorative Cover (released after FDI)",
    "PCC":     "Prestige Comm. Cover (released after FDI)",
    "PNC":     "Philatelic and Numismatic Cover",
    "SMC":     "Stamp and Medallion Cover",
}

# Issue type codes — the single letter (t) in IssueId format yyyy-tnn
ISSUE_TYPES: Dict[str, str] = {
    "I": "Regular Stamp Issue (gum, p&s) - comm. and defin.",
    "L": "Stamped Label Issue",
    "V": "Vending Machine Issued",
    "F": "Frama Machine Issued",
    "M": "Other Machine Issued",
    "C": "Counter Printed Stamp Issue",
    "Z": "Instant Stamp Issue",
    "Y": "Personalised Stamp Issue",
    "O": "Olympic/Comm. Games Special Issue",
    "X": "Stamp Exhibition Special Issue",
    "P": "PPE/PSE only (no stamps)",
    "R": "Reprint/Reissue/Overprint Issue",
    "S": "Other Special Issue (Souvenir etc.)",
}


async def _get_db_credentials(
    user_id_token: Optional[str],
    session_id: Optional[str],
) -> Optional[Dict[str, str]]:
    """Retrieve DB credentials via Okta STS token exchange. Returns None on failure."""
    result = await exchange_id_token_for_vaulted_secret(
        user_id_token=user_id_token,
        cache_key=session_id,
    )
    if not result.get("success"):
        logger.warning("Failed to obtain DB credentials: %s", result.get("error"))
        return None
    secret = result.get("vaulted_secret", {})
    return {"db_user": secret.get("username", ""), "db_pass": secret.get("password", "")}


async def _php_post(
    action: str,
    params: Dict[str, Any],
    db_user: Optional[str] = None,
    db_pass: Optional[str] = None,
) -> Any:
    """Make a POST request to the PHP API and return parsed JSON."""
    settings = get_settings()
    url = f"{settings.php_api_base_url}/api.php"
    body = {k: v for k, v in params.items() if v is not None}
    body["action"] = action
    if db_user is not None:
        body["db_user"] = db_user
    if db_pass is not None:
        body["db_pass"] = db_pass

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=body)
        response.raise_for_status()
        return response.json()


async def handle_search_covers(
    args: Dict[str, Any],
    user_id_token: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Any:
    creds = await _get_db_credentials(user_id_token, session_id)
    params = {
        "year": args.get("year"),
        "text": args.get("text"),
        "type": args.get("type"),
        "source": args.get("source"),
        "limit": args.get("limit", 20),
    }
    return await _php_post(
        "search_covers", params,
        db_user=creds["db_user"] if creds else None,
        db_pass=creds["db_pass"] if creds else None,
    )


async def handle_search_issues(
    args: Dict[str, Any],
    user_id_token: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Any:
    creds = await _get_db_credentials(user_id_token, session_id)
    params = {
        "year": args.get("year"),
        "text": args.get("text"),
        "series": args.get("series"),
        "type": args.get("type"),
        "limit": args.get("limit", 20),
    }
    return await _php_post(
        "search_issues", params,
        db_user=creds["db_user"] if creds else None,
        db_pass=creds["db_pass"] if creds else None,
    )


async def handle_get_cover_details(
    args: Dict[str, Any],
    user_id_token: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Any:
    creds = await _get_db_credentials(user_id_token, session_id)
    params = {"id": args["cover_id"]}
    return await _php_post(
        "cover_details", params,
        db_user=creds["db_user"] if creds else None,
        db_pass=creds["db_pass"] if creds else None,
    )


async def handle_get_issue_with_covers(
    args: Dict[str, Any],
    user_id_token: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Any:
    creds = await _get_db_credentials(user_id_token, session_id)
    params = {"issue_id": args["issue_id"]}
    return await _php_post(
        "issue_with_covers", params,
        db_user=creds["db_user"] if creds else None,
        db_pass=creds["db_pass"] if creds else None,
    )


async def handle_get_statistics(
    args: Dict[str, Any],
    user_id_token: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Any:
    creds = await _get_db_credentials(user_id_token, session_id)
    params = {
        "stat_type": args["stat_type"],
        "table": args.get("table", "covers"),
    }
    return await _php_post(
        "statistics", params,
        db_user=creds["db_user"] if creds else None,
        db_pass=creds["db_pass"] if creds else None,
    )


async def handle_list_available_sources(
    _args: Dict[str, Any],
    user_id_token: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Any:
    return {
        "sources": [
            {"code": code, "name": SOURCE_NAMES[code], "color": SOURCE_COLORS[code]}
            for code in SOURCE_COLORS
        ],
        "australia_post_codes": ["A", "C", "G", "Z", "S"],
        "non_ap_codes": [c for c in SOURCE_COLORS if c not in ("A", "C", "G", "Z", "S")],
        "cover_types": [
            {"code": code, "description": desc}
            for code, desc in COVER_TYPES.items()
        ],
        "issue_types": [
            {"code": code, "description": desc}
            for code, desc in ISSUE_TYPES.items()
        ],
        "description": (
            "Source codes are single letters stored in Covers.Source. "
            "Australia Post family: A, C, G, Z, S. Non-AP makers: all others. "
            "Cover type codes are stored in Covers.Type. "
            "Issue type codes are the single letter in IssueId (e.g. 'I' in 2024-I15)."
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
