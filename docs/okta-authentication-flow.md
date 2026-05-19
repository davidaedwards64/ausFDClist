# Okta Authentication Flow

The agent uses two distinct authentication stages:

---

## Stage 1 — User Sign-In (Standard OIDC)

The browser-based flow uses the Authorization Code grant. No tokens are ever exposed to the frontend.

**`backend/main.py` — Initiate sign-in:**
```python
# Lines 60-74: /auth/start
params = urllib.parse.urlencode({
    "client_id":     s.okta_client_id,
    "response_type": "code",
    "scope":         "openid email profile",
    "redirect_uri":  s.okta_redirect_uri,
    "state":         state,          # CSRF protection
})
return RedirectResponse(f"{s.okta_issuer}/v1/authorize?{params}")
```

**`backend/main.py` — Handle callback (`/auth/callback`, lines 77-124):**
- Validates the `state` parameter (CSRF check)
- Posts the authorization `code` to Okta's `/v1/token` endpoint, using `client_secret` on the server side
- Decodes the returned `id_token` JWT (no signature verification needed — Okta sent it directly)
- Stores `{id_token, user: {email, name, sub}}` in an encrypted, HTTP-only session cookie

---

## Stage 2 — STS Token Exchange for Database Credentials (RFC 8693)

The user's `id_token` is exchanged for short-lived, vaulted DB credentials via Okta Privileged Access.

**`backend/auth/okta_sts.py` — Create a signed client assertion JWT (lines 20-35):**
```python
# Agent signs its own JWT with its private key to prove identity to Okta
claims = {
    "iss": client_id, "sub": client_id,
    "aud": token_url,
    "exp": now + 60,
    "jti": str(uuid.uuid4()),
}
return jose.jwt.encode(claims, private_key, algorithm="RS256")
```

**`backend/auth/okta_sts.py` — Token exchange (lines 38-141):**
```
POST {OKTA_DOMAIN}/oauth2/v1/token

grant_type:            urn:ietf:params:oauth:grant-type:token-exchange
subject_token:         {user_id_token}
subject_token_type:    urn:ietf:params:oauth:token-type:id_token
requested_token_type:  urn:okta:params:oauth:token-type:vaulted-secret
client_assertion_type: urn:ietf:params:oauth:client-assertion-type:jwt-bearer
client_assertion:      {signed_agent_jwt}
resource:              {OKTA_DB_RESOURCE_INDICATOR}
```

Okta returns `{"username": "...", "password": "..."}` — fresh DB credentials valid for ~5 minutes, cached in memory per session.

---

## Where Authentication Gates API Access

| File | Line(s) | What it protects |
|---|---|---|
| `backend/main.py` | 45-50 | `GET /` — redirects to sign-in if no `id_token` in session |
| `backend/main.py` | 135-144 | `GET /api/me` — returns 401 if not authenticated |
| `backend/main.py` | 153-171 | `POST /api/chat` — returns 401 if not authenticated |
| `backend/handlers.py` | 103-116 | `_get_db_credentials()` — calls STS exchange before every DB tool call |

---

## Frontend Role

- **`frontend/js/auth.js`** — calls `/api/me` on page load; redirects to sign-in if it returns 401
- **`frontend/signin.html`** — "Sign in with Okta" button redirects to `/auth/start`
- **`frontend/js/auth-steps.js`** — renders a visual panel showing both auth stages and the vaulted secret result (with masked password)

---

## Key Security Properties

- The client secret never leaves the server
- CSRF is prevented via the `state` parameter
- Session cookies are encrypted and HTTP-only
- DB credentials are just-in-time and short-lived per user session
