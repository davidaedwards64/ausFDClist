"""FastAPI application: serves the chat UI and SSE /api/chat endpoint."""

from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from backend.agent import run_agent
from backend.config import get_settings
from backend.schemas import ChatRequest, HealthResponse, AuthConfigResponse

app = FastAPI(title="Australian FDC AI Agent")

# Mount frontend static files
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    index = FRONTEND_DIR / "index.html"
    return HTMLResponse(content=index.read_text(encoding="utf-8"))


@app.get("/auth/signin", response_class=HTMLResponse)
async def serve_signin():
    return HTMLResponse((FRONTEND_DIR / "signin.html").read_text(encoding="utf-8"))


@app.get("/auth/callback", response_class=HTMLResponse)
async def serve_callback():
    return HTMLResponse((FRONTEND_DIR / "callback.html").read_text(encoding="utf-8"))


@app.get("/auth/signout")
async def signout(id_token_hint: str = ""):
    """Construct Okta RP-initiated logout URL server-side and redirect."""
    s = get_settings()
    if id_token_hint and s.okta_domain and s.okta_redirect_uri:
        origin = s.okta_redirect_uri.replace("/auth/callback", "")
        post_logout_uri = f"{origin}/auth/signin"
        logout_url = (
            f"{s.okta_domain}/oauth2/v1/logout"
            f"?id_token_hint={quote(id_token_hint, safe='')}"
            f"&post_logout_redirect_uri={quote(post_logout_uri, safe='')}"
        )
        return RedirectResponse(logout_url)
    return RedirectResponse("/auth/signin")


@app.get("/api/config", response_model=AuthConfigResponse)
async def get_auth_config():
    s = get_settings()
    return AuthConfigResponse(
        okta_client_id=s.okta_client_id,
        okta_issuer=s.okta_issuer,
        okta_domain=s.okta_domain,
        okta_redirect_uri=s.okta_redirect_uri,
    )


@app.get("/api/health", response_model=HealthResponse)
async def health():
    settings = get_settings()
    return HealthResponse(
        status="ok",
        model=settings.model,
        php_api_base_url=settings.php_api_base_url,
    )


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Stream agent responses as newline-delimited JSON over SSE."""

    async def event_stream():
        async for chunk in run_agent(request.message, request.session_id):
            yield f"data: {chunk}\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
