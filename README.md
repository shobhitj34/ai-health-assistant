# Disha – AI Health Coach

A WhatsApp-style AI health coaching chat app powered by Google Gemini.

---

## Quick start (local)

### Prerequisites
- Python 3.9+
- A [Gemini API key](https://aistudio.google.com/) (free tier available)

### 1. Clone & set up environment

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Open .env and set GEMINI_API_KEY=AIza...
```

Full list of variables:

| Variable | Required | Default | Notes |
|---|---|---|---|
| `GEMINI_API_KEY` | **yes** | — | Your Google Gemini API key |
| `MAIN_MODEL` | no | `gemini-2.5-flash-lite` | Model for chat responses |
| `FAST_MODEL` | no | `gemini-2.5-flash-lite` | Model for memory extraction |
| `DATABASE_URL` | no | `sqlite:///./disha.db` | SQLAlchemy URL; swap to Postgres if needed |
| `CORS_ORIGINS` | no | `http://localhost:8000` | Comma-separated allowed origins |

### 3. Initialise the database & seed protocols

The DB schema is created automatically on first startup.
Seed the medical/policy protocols once:

```bash
# Still inside backend/
python -m scripts.seed_protocols
```

### 4. Run the server

```bash
uvicorn app.main:app --reload --port 8000
```

Open **http://localhost:8000** in your browser.
The backend serves the frontend from the `frontend/` directory at the root path.

---

## Project structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app, WebSocket endpoint, static file serving
│   │   ├── database.py       # SQLAlchemy engine + session helpers
│   │   ├── models.py         # ORM models: User, Message, Protocol
│   │   ├── schemas.py        # Pydantic response schemas
│   │   ├── routers/
│   │   │   └── messages.py   # REST: GET /api/session, GET /api/messages
│   │   └── services/
│   │       ├── llm.py        # LLM orchestration: prompts, streaming, memory
│   │       └── protocols.py  # Keyword-based protocol matching
│   ├── scripts/
│   │   └── seed_protocols.py # One-time DB seed for health protocols
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── index.html
    ├── style.css
    └── app.js
```

---

## Architecture overview

### Backend layers

```
HTTP/WebSocket request
       │
       ▼
  FastAPI app  (main.py)
       │
   ┌───┴────────────┐
   │                │
REST router     WebSocket handler
(messages.py)   (main.py → llm.py)
   │                │
   └───────┬────────┘
           │
     SQLAlchemy ORM
     (database.py / models.py)
           │
        SQLite
```

**REST endpoints** handle stateless reads:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/session` | Get or create user session |
| `GET` | `/api/messages` | Paginated message history (cursor-based) |

**WebSocket** (`/ws?session_id=<id>`) handles everything real-time:

| Frame (server → client) | Meaning |
|---|---|
| `typing { is_typing }` | Show/hide typing indicator |
| `user_saved { id, created_at }` | Confirm user message was persisted |
| `chunk { content }` | Streamed token from Gemini |
| `message_complete { id, created_at }` | AI response fully received |
| `error { message }` | Graceful error shown in chat |

### Frontend state machine

```
page load
  → getOrCreateSessionId()          (localStorage UUID)
  → GET /api/session                (create server-side record)
  → GET /api/messages               (last 20 messages, chronological)
  → connectWS()

user scrolls to top
  → GET /api/messages?before_id=<oldest>   (cursor pagination)
  → prepend bubbles, restore scroll position

user sends message
  → optimistic bubble (pending state)
  → WS send {type:"message", content}
  → on user_saved  → mark bubble confirmed
  → on chunk       → stream into AI bubble
  → on message_complete → finalise bubble, unlock input
```

### LLM call architecture

Every AI response is a single Gemini `generate_content_stream` call with context layers assembled at call time:

1. **System prompt** – Disha's persona + communication rules
2. **Long-term memory** – Structured facts extracted from past conversations (name, age, conditions, goals, medications)
3. **Matched protocols** – Up to 3 health/policy protocols whose keywords appear in the user's message
4. **Conversation summary** – Compressed narrative of messages older than the context window
5. **Recent messages** – Last 30 messages verbatim (as the `messages` array)

**Context overflow handling**

- Only the last `MAX_CONTEXT_MESSAGES = 30` messages are sent verbatim.
- When `message_count >= 30`, a background task compresses older messages into a short narrative stored in `user.conversation_summary` and included in the system prompt.
- This keeps token usage bounded without losing long-term context.

**Memory extraction**

After every 10 messages (or after the first 4 onboarding messages), a background `asyncio.create_task` calls `gemini-2.5-flash-lite` with a structured extraction prompt to update `user.long_term_memory` (a JSON column). The task opens its own DB session so it never blocks the WebSocket.

**Onboarding**

New users (message_count == 0) receive a welcome message generated automatically on WebSocket connect. The system prompt enters "onboarding mode" which instructs Disha to gather name, age, primary health concern, and conditions conversationally over 2-3 messages. Once the extraction detects a name + concern, `onboarding_complete` is set to `true`.

### Protocol matching

`services/protocols.py` does keyword-frequency scoring over all rows in the `protocols` table. It returns the top-3 most-relevant protocols (sorted by keyword hit count, then priority). These are appended to the system prompt verbatim.

This is intentionally simple. Given more time, embeddings + cosine similarity would be significantly better.

---

## Trade-offs & "if I had more time…"

| Area | Current | Better approach |
|---|---|---|
| **Protocol retrieval** | Exact keyword matching | Sentence embeddings + cosine similarity (pgvector / FAISS) |
| **Auth** | UUID in localStorage | Proper auth (phone OTP for Indian users) |
| **Persistence** | SQLite | PostgreSQL with connection pooling for production |
| **Streaming** | WebSocket | WebSocket is correct; add Redis pub/sub to support horizontal scaling |
| **Memory** | Full re-extraction every N messages | Incremental updates + versioning |
| **Onboarding** | LLM-driven, soft | Structured form → LLM hybrid for guaranteed data capture |
| **Testing** | None | Unit tests for protocol matching, memory extraction, pagination logic |
| **Rate limiting** | None | Per-session rate limiting (Redis token bucket) |
| **Input safety** | Length cap only | LLM-based content moderation pre-call |
| **Conversation summary** | Generated lazily | Proactive rolling summary every N messages |
| **Frontend** | Vanilla JS | React + proper virtual list for very long histories |

---

## Deploying to Render (free)

A `render.yaml` is included for one-click deployment.

### Steps

1. Push this repo to GitHub (already done)
2. Go to [render.com](https://render.com) → **New** → **Blueprint**
3. Connect your GitHub account and select the `ai-health-assistant` repo
4. Render will detect `render.yaml` and create:
   - A **PostgreSQL** database (`disha-db`)
   - A **Web Service** (`disha-health-coach`)
5. Before deploying, set the secret environment variable in the Render dashboard:
   - Service → **Environment** → Add `GEMINI_API_KEY` = your key
6. Click **Deploy** — the app will be live at `https://disha-health-coach.onrender.com`

> **Note:** On the free plan the service spins down after 15 minutes of inactivity. The first request after a cold start takes ~30 seconds.

### What render.yaml does
- Provisions a free PostgreSQL database
- Sets `DATABASE_URL` automatically from the database connection string
- Runs `uvicorn` on the `$PORT` Render assigns
- Uses Python 3.11 on the server
- Protocols are seeded automatically on first startup (no manual step needed)
