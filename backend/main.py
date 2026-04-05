"""
FastAPI backend for the AI Travel Agent.
Serves the frontend and exposes a streaming SSE chat endpoint.

Run with:
  cd backend
  uvicorn main:app --reload --port 8000
"""
import json
import uuid
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

# Load .env from the project root (one level up from backend/)
_ROOT = Path(__file__).parent.parent
load_dotenv(_ROOT / ".env")

from orchestrator import TravelOrchestrator

app = FastAPI(title="AI Travel Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory sessions (use Redis for production)
sessions: dict[str, TravelOrchestrator] = {}

FRONTEND_PATH = Path(__file__).parent.parent / "frontend" / "index.html"
FRONTEND_DIR  = Path(__file__).parent.parent / "frontend"

app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")


@app.get("/")
async def serve_frontend():
    if FRONTEND_PATH.exists():
        return FileResponse(str(FRONTEND_PATH))
    return HTMLResponse("<h1>Frontend not found. Please ensure frontend/index.html exists.</h1>")


@app.post("/session")
async def create_session():
    """Create a new chat session and return its ID."""
    session_id = str(uuid.uuid4())
    sessions[session_id] = TravelOrchestrator()
    return {"session_id": session_id}


@app.post("/chat/{session_id}")
async def chat(session_id: str, request: Request):
    """
    Stream the AI response as Server-Sent Events.
    Each event: data: <json>\n\n
    Last event: data: [DONE]\n\n
    """
    body = await request.json()
    user_message = body.get("message", "").strip()

    if not user_message:
        return {"error": "Empty message"}

    if session_id not in sessions:
        sessions[session_id] = TravelOrchestrator()

    orchestrator = sessions[session_id]

    async def event_stream():
        try:
            async for event in orchestrator.process(user_message):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.delete("/session/{session_id}")
async def reset_session(session_id: str):
    """Reset (delete) a session so the user can start over."""
    if session_id in sessions:
        del sessions[session_id]
    return {"status": "ok"}


@app.get("/health")
async def health():
    return {"status": "ok", "sessions_active": len(sessions)}
