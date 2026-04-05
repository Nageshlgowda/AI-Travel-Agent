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
import logging
import time
from pathlib import Path

from fastapi import FastAPI, Request, Form
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

# Load .env from the project root (one level up from backend/)
_ROOT = Path(__file__).parent.parent
load_dotenv(_ROOT / ".env")

from orchestrator import TravelOrchestrator

# ── LOGGING SETUP ───────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("travel_agent")

# ── APP ─────────────────────────────────────────────────────────────────────
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

@app.get("/style.css")
async def serve_css():
    return FileResponse(str(FRONTEND_DIR / "style.css"), media_type="text/css")

@app.get("/app.js")
async def serve_js():
    return FileResponse(str(FRONTEND_DIR / "app.js"), media_type="application/javascript")

logger.info("AI Travel Agent starting up")
logger.info("Frontend path: %s (exists=%s)", FRONTEND_PATH, FRONTEND_PATH.exists())


@app.get("/")
async def serve_frontend():
    if FRONTEND_PATH.exists():
        logger.debug("Serving frontend index.html")
        return FileResponse(str(FRONTEND_PATH))
    logger.warning("Frontend index.html not found at %s", FRONTEND_PATH)
    return HTMLResponse("<h1>Frontend not found. Please ensure frontend/index.html exists.</h1>")


@app.post("/session")
async def create_session():
    """Create a new chat session and return its ID."""
    session_id = str(uuid.uuid4())
    sessions[session_id] = TravelOrchestrator()
    logger.info("Session created: %s (total active: %d)", session_id, len(sessions))
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
        logger.warning("Empty message received for session %s", session_id)
        return {"error": "Empty message"}

    if session_id not in sessions:
        logger.info("Unknown session %s — creating new orchestrator", session_id)
        sessions[session_id] = TravelOrchestrator()

    orchestrator = sessions[session_id]
    logger.info("Chat [%s] → %r", session_id, user_message[:120])

    async def event_stream():
        start = time.monotonic()
        event_count = 0
        try:
            async for event in orchestrator.process(user_message):
                event_count += 1
                event_type = event.get("type", "unknown")
                if event_type == "text":
                    logger.debug("Chat [%s] text chunk (%d chars)", session_id, len(event.get("content", "")))
                else:
                    logger.info("Chat [%s] event: %s", session_id, event_type)
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            logger.error("Chat [%s] stream error: %s", session_id, e, exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            elapsed = time.monotonic() - start
            logger.info("Chat [%s] stream done — %d events in %.2fs", session_id, event_count, elapsed)
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
        logger.info("Session deleted: %s (remaining: %d)", session_id, len(sessions))
    else:
        logger.warning("Delete requested for unknown session: %s", session_id)
    return {"status": "ok"}


@app.get("/health")
async def health():
    logger.debug("Health check — active sessions: %d", len(sessions))
    return {"status": "ok", "sessions_active": len(sessions)}




# ── WHATSAPP INTEGRATION ────────────────────────────────────────────────────

TWILIO_ACCOUNT_SID    = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN     = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM  = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
WHATSAPP_NUMBER       = os.getenv("WHATSAPP_NUMBER", "+14155238886")

if TWILIO_ACCOUNT_SID:
    logger.info("Twilio configured — WhatsApp from %s", TWILIO_WHATSAPP_FROM)
else:
    logger.warning("Twilio credentials not set — WhatsApp replies disabled")


@app.get("/whatsapp/config")
async def whatsapp_config():
    """Return the WhatsApp number so the frontend can generate a QR code."""
    logger.debug("WhatsApp config requested — number: %s", WHATSAPP_NUMBER)
    return {"phone": WHATSAPP_NUMBER}


@app.post("/whatsapp/webhook")
async def whatsapp_webhook(From: str = Form(...), Body: str = Form(...)):
    """
    Twilio webhook: receives incoming WhatsApp messages, runs them through
    the same travel orchestrator, and replies via Twilio REST API.
    Set this URL as your Twilio WhatsApp sandbox / incoming-message webhook.
    """
    logger.info("WhatsApp message from %s: %r", From, Body[:120])

    session_key = f"wa_{From}"
    is_new = session_key not in sessions
    if is_new:
        sessions[session_key] = TravelOrchestrator()
        logger.info("WhatsApp new session created for %s", From)

    orchestrator = sessions[session_key]

    # Collect streaming events into a single reply
    reply_parts: list[str] = []
    start = time.monotonic()
    async for event in orchestrator.process(Body):
        t = event.get("type")
        if t == "text":
            reply_parts.append(event.get("content", ""))
        elif t == "confirm_prompt":
            reply_parts.append("\n" + event.get("message", "") +
                               "\n\nReply *yes* to confirm your booking.")
        elif t == "booking_confirmation":
            d = event.get("data", {})
            reply_parts.append(
                "\n🎉 *Booking Confirmed!*\n"
                f"Destination: {d.get('destination', '—')}\n"
                f"Dates: {d.get('dates', '—')}\n"
                f"Travelers: {d.get('travelers', '—')}\n"
                f"Flight Ref: {d.get('flight', {}).get('booking_reference', '—')}\n"
                f"Hotel Ref: {d.get('hotel', {}).get('booking_reference', '—')}"
            )

    reply = "".join(reply_parts).strip() or "I'm working on your request — please wait a moment."
    elapsed = time.monotonic() - start
    logger.info("WhatsApp reply ready for %s — %d chars in %.2fs", From, len(reply), elapsed)

    # Send reply via Twilio (if credentials are configured)
    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
        try:
            from twilio.rest import Client as TwilioClient
            client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            chunks = range(0, len(reply), 1500)
            for i in chunks:
                client.messages.create(
                    from_=TWILIO_WHATSAPP_FROM,
                    body=reply[i:i + 1500],
                    to=From,
                )
            logger.info("WhatsApp reply sent to %s (%d chunk(s))", From, len(chunks))
        except Exception as e:
            logger.error("WhatsApp Twilio send error for %s: %s", From, e, exc_info=True)
    else:
        logger.warning("Twilio not configured — skipping WhatsApp reply to %s", From)

    # Acknowledge to Twilio with an empty TwiML response
    return Response(
        content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
        media_type="application/xml",
    )
