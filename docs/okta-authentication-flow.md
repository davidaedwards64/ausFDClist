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

## Okta App Redirect URIs and How They Map to Code

When configuring the Okta application, two redirect URIs must be registered. Here is how each maps to the codebase.

### Sign-In Redirect URI — `/auth/callback`

This is set via `OKTA_REDIRECT_URI` in `.env` and must be registered in the Okta app's **Sign-in redirect URIs** list (e.g. `http://localhost:8000/auth/callback`).

After the user authenticates at Okta, Okta posts the authorization `code` back to this URI. The endpoint at `main.py:77` handles it:

```python
# main.py:77-124
@app.get("/auth/callback")
async def auth_callback(request: Request, code: str = None, state: str = None, ...):
    # 1. Validates CSRF state parameter
    # 2. POSTs code to Okta /v1/token to get id_token
    # 3. Stores id_token + user claims in encrypted session cookie
    # 4. Redirects to /
```

From there, the `id_token` flows through the rest of the agent modules:

```
/auth/callback  (main.py:77)
  → stores id_token in session cookie
        ↓
/api/chat  (main.py:153)
  → reads id_token from session
  → passes to run_agent()  ← agent.py
        ↓
run_agent()  (agent.py:133)
  → calls exchange_id_token_for_vaulted_secret()  ← okta_sts.py
  → forwards (user_id_token, session_id) to each TOOL_HANDLERS call  ← handlers.py
        ↓
each handler  (handlers.py)
  → calls _get_db_credentials()  → okta_sts.py (cached)
  → forwards db_user/db_pass to PHP API
```

The `id_token` originates solely at `/auth/callback` and is never re-fetched — it flows via the session cookie into every downstream module.

---

### Sign-Out / Login Page URI — `/auth/signin`

This endpoint (`main.py:53`) simply renders the static sign-in page:

```python
# main.py:53-55
@app.get("/auth/signin", response_class=HTMLResponse)
async def serve_signin():
    return HTMLResponse((FRONTEND_DIR / "signin.html").read_text(encoding="utf-8"))
```

It performs no authentication itself. The "Sign in with Okta" button inside `signin.html` redirects the browser to `/auth/start`, which kicks off the OIDC flow:

```
/auth/signin  →  renders signin.html
                      ↓  (user clicks "Sign in with Okta")
              /auth/start  →  redirects to Okta authorize endpoint
```

`/auth/signin` is also used as the fallback redirect in four error cases within `main.py`:

| Location | Trigger |
|---|---|
| `main.py:49` | `GET /` — no `id_token` in session (unauthenticated visit) |
| `main.py:88` | `/auth/callback` — Okta returned an error |
| `main.py:92` | `/auth/callback` — `state` mismatch (CSRF failure) |
| `main.py:110` | `/auth/callback` — Okta token endpoint returned a non-2xx response |
| `main.py:115` | `/auth/callback` — no `id_token` in Okta response |

If configuring an Okta **post-logout redirect URI**, point it to `/auth/signin` so the browser lands on the login page after Okta ends the session. The local logout endpoint (`main.py:127`) clears the session cookie and redirects there directly without involving Okta's logout endpoint.

---

## Key Security Properties

- The client secret never leaves the server
- CSRF is prevented via the `state` parameter
- Session cookies are encrypted and HTTP-only
- DB credentials are just-in-time and short-lived per user session
