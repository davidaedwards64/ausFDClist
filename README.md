# Australian FDC AI Agent

AI-powered chat interface for the Australian First Day Cover (FDC) collection at [davidaedwards.com/ausfdclist](https://davidaedwards.com/ausfdclist).

Users can search and explore thousands of FDCs (1940–present) using plain English. The agent uses Claude with tool use to query a PHP/MySQL backend.

---

## Architecture

See [`docs/architecture.txt`](docs/architecture.txt) for the full diagram.

```
╔══════════════════════════════════════════════════════════════════════════════════╗
║                    AUSTRALIAN FDC AI ASSISTANT — ARCHITECTURE                   ║
╚══════════════════════════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────────────────────────┐
│  BROWSER                                                                        │
│                                                                                 │
│  signin.html          index.html                                                │
│  ┌──────────────┐     ┌────────────────────────────────────────────────────┐   │
│  │ Sign in btn  │     │  auth.js        GET /api/me → populate user        │   │
│  │  → /auth/    │     │  app.js         form submit, message rendering     │   │
│  │    start     │     │  streaming.js   POST /api/chat → consume SSE       │   │
│  └──────────────┘     │  auth-steps.js  render Okta auth flow panel        │   │
│                        └────────────────────────────────────────────────────┘   │
└──────────┬──────────────────────────┬──────────────────────────────────────────┘
           │  HTTPS (session cookie)  │  SSE stream (ndjson events)
           │  ①  ④                   │  ⑤ text · tool_call · tool_result ·
           ▼                          │     token_exchange · end
┌──────────────────────────────────────────────────────────────────────────────────┐
│  FASTAPI BACKEND  (Render, Python / Uvicorn)                                    │
│                                                                                 │
│  main.py                                                                        │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  GET /auth/start    → redirect browser to Okta /v1/authorize  ──────①  │   │
│  │  GET /auth/callback ← receive auth code, POST Okta /v1/token  ──────②  │   │
│  │                       store id_token + user in encrypted session cookie │   │
│  │  GET /auth/logout   → clear session, redirect to /auth/signin           │   │
│  │  GET /api/me        → return user from session (or 401)        ──────④  │   │
│  │  POST /api/chat     → run_agent(message, session_id, id_token) ──────⑤  │   │
│  └────────────────────────────────────────────┬────────────────────────────┘   │
│                                               │                                 │
│  agent.py  (agentic SSE loop)                 │                                 │
│  ┌────────────────────────────────────────────▼────────────────────────────┐   │
│  │  1. yield session event                                                 │   │
│  │  2. call okta_sts.exchange_id_token_for_vaulted_secret()  ──────────③  │   │
│  │     yield token_exchange event → browser auth-steps panel              │   │
│  │  3. loop: call Anthropic Claude API  ───────────────────────────────⑥  │   │
│  │           yield text / tool_call events                                │   │
│  │           dispatch to handlers.py, yield tool_result events            │   │
│  │  4. yield end event                                                     │   │
│  └──────────────┬──────────────────────────────────────────────────────---┘   │
│                 │                                                               │
│  auth/okta_sts.py                                                               │
│  ┌──────────────▼────────────────────────────────────────────────────────-┐   │
│  │  - Build client_assertion JWT (RS256, agent private JWK)               │   │
│  │  - POST /oauth2/v1/token  grant=token-exchange  ────────────────────③  │   │
│  │      subject_token = user id_token                                     │   │
│  │      requested_token_type = vaulted-secret                             │   │
│  │  - Return vaulted_secret { username, password }                        │   │
│  │  - In-memory cache keyed by session_id (TTL = expires_in)              │   │
│  └────────────────────────────────────────────────────────────────────────┘   │
│                 │                                                               │
│  handlers.py  (tool handlers)                                                   │
│  ┌──────────────▼────────────────────────────────────────────────────────-┐   │
│  │  search_covers · search_issues · get_cover_details                     │   │
│  │  get_issue_with_covers · get_statistics · list_available_sources       │   │
│  │  Each: _get_db_credentials() → _php_post(action, params,  ──────────⑦ │   │
│  │                                           db_user, db_pass)            │   │
│  └────────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────---┘
           │  ②                    │  ③                         │  ⑥
           ▼                       ▼                            ▼
┌──────────────────┐   ┌────────────────────────┐   ┌─────────────────────┐
│  OKTA            │   │  OKTA STS              │   │  ANTHROPIC API      │
│                  │   │                        │   │                     │
│  OIDC Auth       │   │  /oauth2/v1/token      │   │  claude-sonnet-4-5  │
│  /v1/authorize   │   │  Token Exchange        │   │  (tool use,         │
│  /v1/token       │   │  (RFC 8693)            │   │   streaming)        │
│  (code flow,     │   │                        │   │                     │
│   confidential   │   │  Validates:            │   └─────────────────────┘
│   client)        │   │  - user id_token       │
│                  │   │  - client_assertion JWT│
│  issues:         │   │  - token-exchange      │
│  - id_token      │   │    policy              │
│  - access_token  │   │                        │
└──────────────────┘   └───────────┬────────────┘
                                   │ ③ retrieves secret
                                   ▼
                        ┌────────────────────────┐
                        │  OPA VAULT             │
                        │  (Okta Privileged      │
                        │   Access)              │
                        │                        │
                        │  Managed Connection:   │
                        │  ausFDClist-DB-Creds   │
                        │  { username, password }│
                        └────────────────────────┘

           │  ⑦  HTTP POST  { action, params, db_user, db_pass }
           ▼
┌──────────────────────────────────┐    ┌───────────────────────┐
│  PHP API                         │    │  MySQL DATABASE       │
│  (davidaedwards.com/ausfdclist)  │    │  (davidaedwards.com)  │
│                                  │    │                       │
│  api.php                         │    │  Tables:              │
│  - reads db_user/db_pass from    │───▶│  - Covers             │
│    POST body                     │    │  - Issues             │
│  - opens PDO connection          │    │  - Stamps (ref)       │
│  - executes action_*() SQL       │◀───│                       │
│  - returns JSON results          │    │  (credentials used    │
│  - new connection per request    │    │   once, not cached)   │
└──────────────────────────────────┘    └───────────────────────┘


KEY FLOWS
─────────
① Sign-in:   Browser → /auth/start → Okta authorize → /auth/callback
             → Okta token endpoint (code exchange) → session cookie → /

② Per-message: Browser POST /api/chat
             → FastAPI checks session for id_token
             → okta_sts exchanges id_token for vaulted DB creds (cached per session)
             → Claude API agentic loop (tool calls as needed)
             → each tool: fetch fresh creds from cache, POST to api.php
             → api.php queries MySQL, returns JSON
             → results streamed back to browser as SSE

③ Token cache: Vaulted secret cached server-side in memory (TTL ~300s).
               If cache hit, Okta STS is not called again for that session.
```

- **Frontend** — vanilla HTML/CSS/JS, no build step
- **Backend** — FastAPI (Python), Claude `claude-sonnet-4-5`, agentic tool-use loop, Okta OIDC (confidential client, server-side code flow)
- **Auth** — Okta STS token exchange trades the user's `id_token` for vaulted DB credentials stored in OPA (Okta Privileged Access)
- **PHP API** — thin JSON API over the existing MySQL database; receives DB credentials per-request from FastAPI
- **Deployment** — Render.com (auto-deploys from GitHub `main`)

---

## Local development

### 1. Prerequisites

- Python 3.11+
- An [Anthropic API key](https://console.anthropic.com)
- An Okta org with an **OIDC Web App** configured for Authorization Code flow (confidential client):
  - Sign-in redirect URI: `http://localhost:8000/auth/callback`
  - Provides: `OKTA_CLIENT_ID`, `OKTA_CLIENT_SECRET`, `OKTA_ISSUER`, `OKTA_DOMAIN`
- *(Optional)* Okta AI Agent app + OPA Managed Connection for DB credential vaulting:
  - Provides: `OKTA_AGENT_CLIENT_ID`, `OKTA_AGENT_PRIVATE_JWK`, `OKTA_DB_RESOURCE_INDICATOR`
  - If not configured the app runs fine — the auth steps panel will show "NOT CONFIGURED" for STS, and DB calls will fall back to unauthenticated (will fail unless api.php has fallback creds)

### 2. Clone and install

```bash
git clone https://github.com/davidaedwards64/ausFDClist.git
cd ausFDClist
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in all required values:

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key |
| `PHP_API_BASE_URL` | Yes | Base URL of the PHP API (no trailing slash) |
| `OKTA_CLIENT_ID` | Yes | OIDC Web App client ID |
| `OKTA_CLIENT_SECRET` | Yes | OIDC Web App client secret |
| `OKTA_ISSUER` | Yes | Okta issuer URL (e.g. `https://your-org.okta.com/oauth2/default`) |
| `OKTA_DOMAIN` | Yes | Okta org base URL (e.g. `https://your-org.okta.com`) |
| `OKTA_REDIRECT_URI` | Yes | `http://localhost:8000/auth/callback` for local dev |
| `SESSION_SECRET` | Yes | Random hex key for session cookie signing — generate with: `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `OKTA_AGENT_CLIENT_ID` | Optional | AI Agent OAuth app client ID (STS token exchange) |
| `OKTA_AGENT_PRIVATE_JWK` | Optional | Agent private JWK as a JSON string (RS256) |
| `OKTA_DB_RESOURCE_INDICATOR` | Optional | OPA Managed Connection resource URI |

### 4. Run

```bash
uvicorn backend.main:app --reload
```

Open [http://localhost:8000](http://localhost:8000). You will be redirected to the Okta sign-in page on first visit.

---

## PHP API deployment

Copy `php/api.php` to `davidaedwards.com/ausfdclist/api.php`.

Edit the static connection settings at the top of the file (host and database name only — credentials are no longer hardcoded):

```php
define('DB_HOST', 'localhost');
define('DB_NAME', 'ausfdc');
```

`db_user` and `db_pass` are supplied at runtime by the FastAPI backend on every request via the JSON POST body. They are retrieved from **OPA Vault via Okta STS token exchange** and never stored in source code or on disk.

Test it (expects a POST with credentials — a direct GET will return a 400):
```bash
curl -s -X POST https://davidaedwards.com/ausfdclist/api.php \
  -H "Content-Type: application/json" \
  -d '{"action":"statistics","stat_type":"total","table":"covers","db_user":"…","db_pass":"…"}'
```

---

## Render.com deployment

1. Push this repo to `github.com/davidaedwards64/ausFDClist`
2. In Render dashboard → **New Web Service** → connect the repo
3. Render auto-detects `render.yaml` — review and confirm
4. In **Environment** → add secret: `ANTHROPIC_API_KEY = sk-ant-...`
5. Deploy → visit the live URL

> **Free tier note:** Render free tier spins down after 15 min idle (~30s cold start on first request). Upgrade to Starter ($7/mo) to avoid this.

---

## Agent tools

| Tool | Description |
|---|---|
| `search_covers` | Search covers by text, year, type, source |
| `search_issues` | Search stamp issues by text, year, series, type |
| `get_cover_details` | Full record for a single cover by CoverId |
| `get_issue_with_covers` | Issue + all its covers by IssueId |
| `get_statistics` | Counts by year/source/type or total |
| `list_available_sources` | Known makers with color codes |

---

## Example queries

- *"Show me Christmas FDCs from the 1980s"*
- *"What covers exist for the 1966 Round the World Air Service issue?"*
- *"Find all Bird series stamp issues"*
- *"Tell me about cover 1966-I01-03"*
- *"How many covers are in the database?"*
- *"What makers produce FDCs?"*
