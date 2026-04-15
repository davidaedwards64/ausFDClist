"""FastAPI application: serves the chat UI and SSE /api/chat endpoint."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from backend.agent import run_agent
from backend.config import get_settings
from backend.schemas import ChatRequest, HealthResponse

app = FastAPI(title="Australian FDC AI Agent")

# Mount frontend static files
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    index = FRONTEND_DIR / "index.html"
    return HTMLResponse(content=index.read_text(encoding="utf-8"))


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
