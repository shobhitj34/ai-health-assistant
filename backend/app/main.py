from __future__ import annotations

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

load_dotenv()

from .database import init_db, get_or_create_user, SessionLocal
from .routers.messages import router as messages_router
from .services.llm import send_initial_greeting, handle_user_message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Database initialised")
    _auto_seed()
    yield


def _auto_seed():
    """Seed protocols on startup if the table is empty (safe to run every boot)."""
    from .database import SessionLocal as _SL
    from .models import Protocol
    import importlib, sys
    db = _SL()
    try:
        if db.query(Protocol).count() == 0:
            # Import seed module dynamically to avoid circular deps
            import scripts.seed_protocols as seed_mod
            seed_mod.seed()
            logger.info("Protocols seeded automatically")
    except Exception:
        logger.warning("Auto-seed skipped (seed script not found or already seeded)")
    finally:
        db.close()


app = FastAPI(title="Disha Health Coach API", lifespan=lifespan)

# ── CORS ─────────────────────────────────────────────────────────────────────
_raw_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000,http://127.0.0.1:8000")
origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── REST routes ───────────────────────────────────────────────────────────────
app.include_router(messages_router)


# ── WebSocket ─────────────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str = Query(...),
):
    """
    Real-time channel for the chat UI.

    Client → Server frame (JSON):
        {"type": "message", "content": "..."}

    Server → Client frames (JSON):
        {"type": "typing",           "is_typing": bool}
        {"type": "user_saved",       "id": int, "created_at": str}
        {"type": "chunk",            "content": str}
        {"type": "message_complete", "id": int, "created_at": str}
        {"type": "error",            "message": str}
    """
    if not session_id or len(session_id) > 64:
        await websocket.close(code=4000, reason="Invalid session_id")
        return

    await websocket.accept()

    db = SessionLocal()
    try:
        user = get_or_create_user(db, session_id)

        # Send greeting to brand-new users (never had a message)
        if user.message_count == 0:
            try:
                await send_initial_greeting(websocket, user, db)
            except Exception as e:
                logger.exception("Initial greeting failed for session=%s", session_id)
                # Mark count so reconnects don't retrigger the greeting loop
                from .database import update_user_count
                update_user_count(db, user.id, 1)
                user.message_count = 1
                await websocket.send_json({
                    "type": "error",
                    "message": "Namaste! I'm Disha, your health coach. I had trouble connecting — please send a message to start.",
                })

        while True:
            try:
                data = await websocket.receive_json()
            except Exception:
                # Non-JSON frame — ignore gracefully
                continue

            msg_type = data.get("type")
            if msg_type != "message":
                continue

            content = data.get("content", "")
            if not isinstance(content, str) or not content.strip():
                continue

            await handle_user_message(websocket, user, content, db)

    except WebSocketDisconnect:
        logger.info("Client disconnected: session=%s", session_id)
    except Exception:
        logger.exception("Unexpected error in WS handler for session=%s", session_id)
    finally:
        db.close()


# ── Serve frontend ────────────────────────────────────────────────────────────
_frontend_dir = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
_frontend_dir = os.path.abspath(_frontend_dir)

if os.path.isdir(_frontend_dir):
    app.mount("/static", StaticFiles(directory=_frontend_dir), name="static")

    @app.get("/", response_class=FileResponse)
    def serve_index():
        return FileResponse(os.path.join(_frontend_dir, "index.html"))
