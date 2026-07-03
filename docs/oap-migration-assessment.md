# OAP Migration Assessment: ausFDClist

## Can your app move to the Okta App Platform (OAP)?

**Short answer: Yes, it's viable — mostly a lift-and-shift.** Here's the full breakdown.

---

## What your app is

- **Python FastAPI** backend serving both a static HTML/JS frontend and a `/api/chat` SSE streaming endpoint
- **Server-side OIDC** auth against Okta (confidential client, authorization code flow with client secret)
- **Starlette `SessionMiddleware`** for encrypted HttpOnly cookie sessions
- **Okta STS token exchange**: trades the user's `id_token` for a vaulted DB secret (O4AA Managed Connections flow)
- Calls the **Anthropic API** for Claude and an **external PHP API** at `davidaedwards.com/ausfdclist`
- Currently deployed on Render as `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`

---

## What OAP supports that matches

| Requirement | OAP support |
|---|---|
| Python runtime | Auto-detected via `requirements.txt` + `main.py` — generates a Wolfi/Python container |
| Bind to `$PORT` | Your `render.yaml` already does `--port $PORT` — no change needed |
| SSE streaming | Not explicitly restricted; full-container hosting means standard HTTP streaming works |
| Secrets/env vars | Full support with encryption at rest |
| Outbound HTTPS (Okta, Anthropic, PHP API) | No restrictions documented |
| Static file serving | Works fine — FastAPI mounts `frontend/` as static files within the container |

---

## Auth: the nuanced part

OAP has its own auth layer (Okta as upstream IdP → OAP issues tenant-scoped tokens). You **don't need to use it**. Your existing auth code talks directly to Okta's `/v1/authorize`, `/v1/token`, and token exchange endpoints — all outbound HTTPS calls that work from any container.

The **Okta STS vaulted secret exchange** (`okta_sts.py`) is unchanged — it calls `{okta_domain}/oauth2/v1/token` directly and that keeps working.

**One required change:** Update `OKTA_REDIRECT_URI` to your new OAP app URL (and register it in Okta's admin console). That's the same thing you'd do on any hosting migration.

---

## Things to know / minor gaps

1. **In-memory conversation history** (`_sessions` dict in `agent.py`) is lost on container restart. This was already true on Render — OAP doesn't make it worse, but if you want persistence, OAP's built-in Postgres would be the place for it.

2. **Session secret stability** — already handled in `render.yaml` (`SESSION_SECRET` as a secret). Set the same in OAP secrets and sessions survive restarts.

3. **WebSocket flag** — OAP requires `ws_enabled: true` per-app for WebSocket. Your app only uses SSE (plain HTTP streaming), so this doesn't apply.

4. **Deploy config** — `render.yaml` gets replaced with OAP's app config. Their format is different (YAML/API-based), but the equivalent fields are: build command `pip install -r requirements.txt`, start command `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`.

---

## What you'd actually have to do

1. Create an OAP tenant and app, pointing it at your GitHub repo
2. Set all secrets in OAP:
   - `ANTHROPIC_API_KEY`
   - `OKTA_CLIENT_ID`
   - `OKTA_CLIENT_SECRET`
   - `OKTA_ISSUER`
   - `OKTA_DOMAIN`
   - `OKTA_REDIRECT_URI` (updated to OAP URL)
   - `SESSION_SECRET`
   - `OKTA_AGENT_CLIENT_ID`
   - `OKTA_AGENT_PRIVATE_JWK`
   - `OKTA_DB_RESOURCE_INDICATOR`
3. Update `OKTA_REDIRECT_URI` to the OAP-assigned URL for your app
4. Add the new redirect URI to your Okta app registration
5. Remove `render.yaml` or add an OAP equivalent config file

No code changes required for a working migration.

---

## Optional native integration

If you wanted to go further, OAP's built-in auth (Access Gate) could handle the Okta OIDC flow entirely at the gateway level, eliminating all the auth code in `main.py` and `auth.js`. That would be a meaningful refactor, not a requirement for viability.
