from typing import List, Optional
import os
import json
import asyncio
import logging
from datetime import datetime

import anthropic
from sqlalchemy.orm import Session

from ..models import User, Message, Protocol
from ..database import SessionLocal, save_message, update_user_count, update_user_memory
from .protocols import match_protocols

logger = logging.getLogger(__name__)

MAIN_MODEL = os.getenv("MAIN_MODEL", "claude-sonnet-4-6")
FAST_MODEL = os.getenv("FAST_MODEL", "claude-haiku-4-5-20251001")
MAX_CONTEXT_MESSAGES = 30   # keep this many messages verbatim for LLM context
MEMORY_EXTRACT_INTERVAL = 10  # extract memory every N total messages

_client: Optional[anthropic.AsyncAnthropic] = None


def get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        _client = anthropic.AsyncAnthropic(api_key=api_key)
    return _client


# ── Prompt construction ──────────────────────────────────────────────────────

DISHA_PERSONA = """You are Disha, a warm and knowledgeable AI health coach from India. \
You are like a caring, trusted friend who happens to know a great deal about health and wellness.

Your communication style:
- Write SHORT, conversational messages — like WhatsApp texts, NOT long essays or bullet lists
- Be warm, empathetic, and genuine; show you actually care
- Use simple language; sprinkle in Hindi phrases when they feel natural \
(e.g. "araam karo", "theek ho jaoge", "bilkul", "ghabrao mat")
- Ask ONE thoughtful follow-up question at a time to understand the person better
- Never sound clinical, robotic, or like ChatGPT
- When symptoms are serious, calmly recommend seeing a doctor without causing panic
- For emergencies (chest pain, stroke signs, severe injury) immediately direct to emergency services

Important limits:
- You are a health COACH, not a doctor — never formally diagnose
- Be honest when something is outside your knowledge
- Keep responses under ~150 words unless a detailed explanation is truly needed"""


def _format_memory(memory: dict) -> str:
    if not memory:
        return ""
    parts = []
    if memory.get("name"):
        parts.append(f"Name: {memory['name']}")
    if memory.get("age"):
        parts.append(f"Age: {memory['age']}")
    if memory.get("conditions"):
        conds = memory["conditions"]
        if isinstance(conds, list):
            parts.append(f"Health conditions: {', '.join(conds)}")
    if memory.get("medications"):
        meds = memory["medications"]
        if isinstance(meds, list):
            parts.append(f"Current medications: {', '.join(meds)}")
    if memory.get("goals"):
        goals = memory["goals"]
        if isinstance(goals, list):
            parts.append(f"Health goals: {', '.join(goals)}")
    if memory.get("preferences"):
        parts.append(f"Notes: {memory['preferences']}")
    return "\n".join(parts)


def build_system_prompt(user: User, protocols: List[Protocol], onboarding_mode: bool) -> str:
    sections = [DISHA_PERSONA]

    memory_text = _format_memory(user.long_term_memory or {})
    if memory_text:
        sections.append(f"\n## What you know about this user:\n{memory_text}")

    if protocols:
        proto_lines = ["\n## Relevant health guidance for this conversation:"]
        for p in protocols:
            proto_lines.append(f"\n### {p.title}\n{p.content}")
        sections.append("\n".join(proto_lines))

    if user.conversation_summary:
        sections.append(
            f"\n## Summary of earlier conversation (for context only):\n{user.conversation_summary}"
        )

    if onboarding_mode:
        sections.append(
            "\n## First-time user — onboarding\n"
            "This person has never chatted with you before. Warmly welcome them and, "
            "over 2-3 natural messages, learn: their name, approximate age, the main "
            "health concern or goal that brought them here, and any existing conditions. "
            "Do NOT fire questions like a form. Start with ONE warm greeting + ONE question."
        )

    return "\n".join(sections)


# ── Context window management ────────────────────────────────────────────────

def get_context_messages(user_id: int, db: Session) -> List[dict]:
    """Return the last MAX_CONTEXT_MESSAGES messages formatted for the Anthropic API."""
    msgs = (
        db.query(Message)
        .filter(Message.user_id == user_id)
        .order_by(Message.id.desc())
        .limit(MAX_CONTEXT_MESSAGES)
        .all()
    )
    msgs.reverse()  # chronological order
    return [{"role": m.role, "content": m.content} for m in msgs]


# ── Core streaming helper ────────────────────────────────────────────────────

async def _stream_to_websocket(
    websocket,
    system: str,
    messages: List[dict],
    max_tokens: int = 1024,
) -> str:
    """Stream Claude's reply token-by-token over a WebSocket. Returns full text."""
    client = get_client()
    full_response = ""

    async with client.messages.stream(
        model=MAIN_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
    ) as stream:
        async for text in stream.text_stream:
            full_response += text
            await websocket.send_json({"type": "chunk", "content": text})

    return full_response


# ── Public handlers ──────────────────────────────────────────────────────────

async def send_initial_greeting(websocket, user: User, db: Session) -> None:
    """Generate and stream the very first Disha message for a brand-new user."""
    await websocket.send_json({"type": "typing", "is_typing": True})
    try:
        system = build_system_prompt(user, [], onboarding_mode=True)
        # Synthetic "Hi" so the model has a user turn to respond to
        messages = [{"role": "user", "content": "Hi"}]

        full_response = await _stream_to_websocket(websocket, system, messages)

        ai_msg = save_message(db, user.id, "assistant", full_response)
        update_user_count(db, user.id, 1)
        user.message_count = 1

        await websocket.send_json({
            "type": "message_complete",
            "id": ai_msg.id,
            "created_at": ai_msg.created_at.isoformat(),
        })
    finally:
        await websocket.send_json({"type": "typing", "is_typing": False})


async def handle_user_message(websocket, user: User, content: str, db: Session) -> None:
    """
    Full pipeline for a user-sent message:
    1. Save user message
    2. Match protocols
    3. Build system prompt
    4. Stream AI response
    5. Save AI response
    6. Optionally trigger background memory extraction
    """
    # Validate / sanitise
    content = content.strip()
    if not content:
        return
    # Hard cap on input length (prevent prompt injection via very long inputs)
    content = content[:4000]

    # Persist user message first so it's never lost
    user_msg = save_message(db, user.id, "user", content)
    await websocket.send_json({
        "type": "user_saved",
        "id": user_msg.id,
        "created_at": user_msg.created_at.isoformat(),
    })

    await websocket.send_json({"type": "typing", "is_typing": True})

    try:
        protocols = match_protocols(content, db)
        onboarding_mode = not user.onboarding_complete
        system = build_system_prompt(user, protocols, onboarding_mode)
        context_msgs = get_context_messages(user.id, db)

        full_response = await _stream_to_websocket(websocket, system, context_msgs)

        ai_msg = save_message(db, user.id, "assistant", full_response)
        new_count = user.message_count + 2
        update_user_count(db, user.id, new_count)
        user.message_count = new_count

        await websocket.send_json({
            "type": "message_complete",
            "id": ai_msg.id,
            "created_at": ai_msg.created_at.isoformat(),
        })

        # Background memory extraction — non-blocking
        if _should_extract_memory(user):
            asyncio.create_task(
                _extract_memory_task(user.id, user.message_count, user.long_term_memory or {})
            )

    except Exception:
        logger.exception("Error generating LLM response for user %s", user.id)
        await websocket.send_json({
            "type": "error",
            "message": "Sorry, I couldn't respond just now. Please try again in a moment.",
        })
    finally:
        await websocket.send_json({"type": "typing", "is_typing": False})


# ── Memory extraction ────────────────────────────────────────────────────────

def _should_extract_memory(user: User) -> bool:
    if not user.onboarding_complete and user.message_count >= 4:
        return True
    if user.message_count > 0 and user.message_count % MEMORY_EXTRACT_INTERVAL == 0:
        return True
    return False


async def _extract_memory_task(user_id: int, message_count: int, existing_memory: dict) -> None:
    """
    Background coroutine: extract key health facts from recent conversation and
    persist them into user.long_term_memory.  Uses its own DB session.
    """
    db = SessionLocal()
    try:
        msgs = (
            db.query(Message)
            .filter(Message.user_id == user_id)
            .order_by(Message.id.desc())
            .limit(20)
            .all()
        )
        msgs.reverse()

        if not msgs:
            return

        convo = "\n".join(f"{m.role}: {m.content}" for m in msgs)
        current_mem = json.dumps(existing_memory, indent=2)

        extraction_prompt = f"""You are a data-extraction assistant. \
From the conversation below, extract key health information about the USER (not the coach).

Current known info (may be empty or partial):
{current_mem}

Recent conversation:
{convo}

Return ONLY a valid JSON object with these fields \
(omit any field where the information is not clearly present):
{{
  "name": "user's first name",
  "age": 30,
  "conditions": ["diabetes", "hypertension"],
  "medications": ["metformin"],
  "goals": ["lose weight", "manage sugar"],
  "preferences": "vegetarian; prefers home remedies",
  "onboarding_complete": true
}}

Rules:
- Merge new info with existing — do NOT drop known facts unless the user corrected them
- "onboarding_complete" = true only when you know the user's name AND primary health concern
- Return ONLY the JSON, no explanation"""

        client = get_client()
        response = await client.messages.create(
            model=FAST_MODEL,
            max_tokens=512,
            messages=[{"role": "user", "content": extraction_prompt}],
        )

        raw = response.content[0].text.strip()
        # Strip markdown fences if the model added them
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        extracted: dict = json.loads(raw)
        onboarding_complete: bool = bool(extracted.pop("onboarding_complete", False))

        # Merge: new values override, but don't erase existing ones with empty
        merged = {**existing_memory}
        for k, v in extracted.items():
            if v or v == 0:  # keep falsy-but-meaningful values like age=0
                merged[k] = v

        # Generate a conversation summary if we're accumulating many messages
        summary: str | None = None
        if message_count >= MAX_CONTEXT_MESSAGES:
            summary = await _summarise_old_messages(user_id, db)

        update_user_memory(db, user_id, merged, onboarding_complete, summary)

    except json.JSONDecodeError:
        logger.warning("Memory extraction returned non-JSON for user %s", user_id)
    except Exception:
        logger.exception("Memory extraction failed for user %s", user_id)
    finally:
        db.close()


async def _summarise_old_messages(user_id: int, db: Session) -> str:
    """Create a short summary of messages older than the context window."""
    older_msgs = (
        db.query(Message)
        .filter(Message.user_id == user_id)
        .order_by(Message.id.asc())
        .limit(
            # summarise everything except the most recent window
            db.query(Message).filter(Message.user_id == user_id).count()
            - MAX_CONTEXT_MESSAGES
        )
        .all()
    )
    if not older_msgs:
        return ""

    convo = "\n".join(f"{m.role}: {m.content}" for m in older_msgs)
    prompt = (
        f"Summarise the following health coaching conversation in 3-5 sentences, "
        f"focusing on the user's health concerns, advice given, and any decisions made:\n\n{convo}"
    )

    client = get_client()
    resp = await client.messages.create(
        model=FAST_MODEL,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text.strip()
