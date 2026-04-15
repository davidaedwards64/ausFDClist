# Australian FDC AI Agent

AI-powered chat interface for the Australian First Day Cover (FDC) collection at [davidaedwards.com/ausfdclist](https://davidaedwards.com/ausfdclist).

Users can search and explore thousands of FDCs (1940–present) using plain English. The agent uses Claude with tool use to query a PHP/MySQL backend.

---

## Architecture

```
[Browser Chat UI] ←SSE→ [FastAPI + Claude Agent] ←httpx→ [PHP api.php] ←→ [MySQL]
```

- **Frontend** — vanilla HTML/CSS/JS, no build step
- **Backend** — FastAPI (Python), Claude `claude-opus-4-6`, agentic tool-use loop
- **PHP API** — thin JSON API over the existing MySQL database
- **Deployment** — Render.com (auto-deploys from GitHub `main`)

---

## Local development

### 1. Prerequisites

- Python 3.11+
- An [Anthropic API key](https://console.anthropic.com)

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
# Edit .env — add your ANTHROPIC_API_KEY
```

### 4. Run

```bash
uvicorn backend.main:app --reload
```

Open [http://localhost:8000](http://localhost:8000).

---

## PHP API deployment

Copy `php/api.php` to `davidaedwards.com/ausfdclist/api.php`.

Edit the database credentials at the top of the file:

```php
define('DB_HOST', 'localhost');
define('DB_NAME', 'ausfdc');
define('DB_USER', 'your_db_user');
define('DB_PASS', 'your_db_pass');
```

Test it:
```
https://davidaedwards.com/ausfdclist/api.php?action=statistics&stat_type=total&table=covers
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
