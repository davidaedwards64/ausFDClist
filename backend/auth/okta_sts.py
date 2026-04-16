"""Okta STS token exchange — trades a user id_token for a vaulted DB secret."""

import json
import logging
import time
import uuid
from typing import Any, Dict, Optional

import httpx
from jose import jwt

from backend.config import get_settings

logger = logging.getLogger(__name__)

# Simple in-memory cache: cache_key → {"data": dict, "expires_at": float}
_cache: Dict[str, Dict[str, Any]] = {}


def create_client_assertion_jwt(client_id: str, private_jwk_str: str, okta_domain: str) -> str:
    """Sign a short-lived JWT (RS256) for use as client_assertion in the token exchange."""
    private_jwk = json.loads(private_jwk_str)
    now = int(time.time())
    claims = {
        "iss": client_id,
        "sub": client_id,
        "aud": f"{okta_domain}/oauth2/v1/token",
        "iat": now,
        "exp": now + 60,
        "jti": str(uuid.uuid4()),
    }
    headers = {"alg": "RS256"}
    if "kid" in private_jwk:
        headers["kid"] = private_jwk["kid"]
    return jwt.encode(claims, private_jwk, algorithm="RS256", headers=headers)


async def exchange_id_token_for_vaulted_secret(
    user_id_token: Optional[str],
    cache_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Exchange a user id_token for a vaulted DB secret via Okta STS.

    Returns a dict with keys:
      success, status, vaulted_secret, issued_token_type, expires_in, exchanged_at, cached, error
    """
    settings = get_settings()

    # Graceful no-op when not configured
    if not settings.okta_agent_client_id or not settings.okta_agent_private_jwk:
        return {
            "success": False,
            "status": "not_configured",
            "error": "OKTA_AGENT_CLIENT_ID or OKTA_AGENT_PRIVATE_JWK not set",
        }

    if not user_id_token:
        return {
            "success": False,
            "status": "no_token",
            "error": "No user id_token provided",
        }

    # Return cached entry if still valid
    if cache_key and cache_key in _cache:
        entry = _cache[cache_key]
        if time.time() < entry["expires_at"]:
            result = dict(entry["data"])
            result["cached"] = True
            return result

    try:
        client_assertion = create_client_assertion_jwt(
            settings.okta_agent_client_id,
            settings.okta_agent_private_jwk,
            settings.okta_domain,
        )

        token_url = f"{settings.okta_domain}/oauth2/v1/token"
        payload: Dict[str, str] = {
            "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
            "subject_token": user_id_token,
            "subject_token_type": "urn:ietf:params:oauth:token-type:id_token",
            "requested_token_type": "urn:okta:params:oauth:token-type:vaulted-secret",
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": client_assertion,
        }
        if settings.okta_db_resource_indicator:
            payload["resource"] = settings.okta_db_resource_indicator

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                token_url,
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        if resp.status_code != 200:
            error_body = resp.text
            logger.warning("Okta STS exchange failed (%s): %s", resp.status_code, error_body)
            return {
                "success": False,
                "status": "exchange_failed",
                "error": f"HTTP {resp.status_code}: {error_body}",
            }

        body = resp.json()
        vaulted = body.get("vaulted_secret", {})
        expires_in = int(body.get("expires_in", 300))
        issued_token_type = body.get("issued_token_type", "")
        exchanged_at = int(time.time())

        result: Dict[str, Any] = {
            "success": True,
            "status": "success",
            "vaulted_secret": {
                "username": vaulted.get("username", ""),
                "password": vaulted.get("password", ""),
            },
            "issued_token_type": issued_token_type,
            "expires_in": expires_in,
            "exchanged_at": exchanged_at,
            "cached": False,
        }

        # Store in cache
        if cache_key:
            _cache[cache_key] = {
                "data": result,
                "expires_at": time.time() + expires_in,
            }

        return result

    except Exception as exc:
        logger.exception("Unexpected error in Okta STS exchange")
        return {
            "success": False,
            "status": "error",
            "error": str(exc),
        }
