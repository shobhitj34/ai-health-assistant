/**
 * Disha Health Coach – frontend application
 *
 * Architecture:
 *  - Session ID: persisted in localStorage; sent as WS query param and REST query param
 *  - Initial history: REST GET /api/messages  (last 20 messages)
 *  - Infinite scroll upward: REST GET /api/messages?before_id=<oldest>
 *  - Real-time (send message / receive AI reply / typing indicator): WebSocket /ws
 *
 * WebSocket frame protocol
 * ────────────────────────
 * Client → Server:  { type: "message", content: "..." }
 * Server → Client:  { type: "typing",           is_typing: bool }
 *                   { type: "user_saved",        id, created_at }
 *                   { type: "chunk",             content: "..." }
 *                   { type: "message_complete",  id, created_at }
 *                   { type: "error",             message: "..." }
 */

"use strict";

// ── Config ───────────────────────────────────────────────────────────────────
const API_BASE  = "";   // same origin; change to "http://localhost:8000" for dev
const WS_BASE   = (() => {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${location.host}`;
})();
const PAGE_SIZE = 20;
const RECONNECT_DELAY_MS = 3000;
const MAX_INPUT_LENGTH = 4000;

// ── State ────────────────────────────────────────────────────────────────────
let sessionId      = "";
let ws             = null;
let isTyping       = false;
let isSending      = false;        // lock while AI is responding
let hasMore        = false;        // older messages available
let oldestMsgId    = null;         // cursor for pagination
let streamingBubble = null;        // <div> being built from chunks
let reconnectTimer = null;

// ── DOM refs ─────────────────────────────────────────────────────────────────
const chatList     = document.getElementById("chat-list");
const typingEl     = document.getElementById("typing-indicator");
const inputEl      = document.getElementById("msg-input");
const sendBtn      = document.getElementById("send-btn");
const loadMoreBar  = document.getElementById("load-more-bar");
const loadMoreBtn  = document.getElementById("load-more-btn");
const statusEl     = document.getElementById("header-status");

// ── Session ID ───────────────────────────────────────────────────────────────
function getOrCreateSessionId() {
  let id = localStorage.getItem("disha_session_id");
  if (!id || id.length < 8) {
    // generate UUID v4
    id = "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, c => {
      const r = Math.random() * 16 | 0;
      return (c === "x" ? r : (r & 0x3 | 0x8)).toString(16);
    });
    localStorage.setItem("disha_session_id", id);
  }
  return id;
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function formatTime(isoOrDate) {
  const d = isoOrDate instanceof Date ? isoOrDate : new Date(isoOrDate);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function todayLabel(isoOrDate) {
  const d = isoOrDate instanceof Date ? isoOrDate : new Date(isoOrDate);
  const now = new Date();
  if (d.toDateString() === now.toDateString()) return "Today";
  const diff = Math.floor((now - d) / 86400000);
  if (diff === 1) return "Yesterday";
  return d.toLocaleDateString([], { day: "numeric", month: "short", year: "numeric" });
}

let lastDateLabel = null;

function maybeInsertDateSep(isoDate, prepend = false) {
  const label = todayLabel(isoDate);
  if (label === lastDateLabel && !prepend) return;

  if (!prepend) lastDateLabel = label;

  const sep = document.createElement("div");
  sep.className = "date-sep";
  sep.innerHTML = `<span>${label}</span>`;

  if (prepend) {
    chatList.insertBefore(sep, chatList.firstChild);
  } else {
    chatList.appendChild(sep);
  }
}

/**
 * Append a finished message bubble to the chat list.
 * @param {object} msg  - { id?, role, content, created_at? }
 * @param {boolean} prepend - insert at top (for history loading)
 * @returns HTMLElement  the created row
 */
function appendBubble(msg, prepend = false) {
  if (!prepend) {
    maybeInsertDateSep(msg.created_at || new Date().toISOString());
  }

  const row = document.createElement("div");
  row.className = `msg-row ${msg.role}`;
  if (msg.id) row.dataset.msgId = msg.id;

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  if (msg.pending) bubble.classList.add("pending");

  // Render content as plain text (XSS-safe)
  const textNode = document.createElement("span");
  textNode.textContent = msg.content;
  bubble.appendChild(textNode);

  const meta = document.createElement("div");
  meta.className = "bubble-meta";
  meta.textContent = msg.created_at ? formatTime(msg.created_at) : formatTime(new Date());
  bubble.appendChild(meta);

  row.appendChild(bubble);

  if (prepend) {
    chatList.insertBefore(row, chatList.firstChild);
  } else {
    chatList.appendChild(row);
  }

  return row;
}

/** Create an empty streaming bubble for Disha's response (filled by chunks). */
function createStreamingBubble() {
  const row = document.createElement("div");
  row.className = "msg-row assistant";

  const bubble = document.createElement("div");
  bubble.className = "bubble streaming";
  bubble.dataset.text = "";

  row.appendChild(bubble);
  chatList.appendChild(row);
  scrollToBottom();
  return bubble;
}

function appendChunk(text) {
  if (!streamingBubble) {
    streamingBubble = createStreamingBubble();
  }
  streamingBubble.dataset.text += text;
  // Update text node safely
  let textNode = streamingBubble.querySelector("span.stream-text");
  if (!textNode) {
    textNode = document.createElement("span");
    textNode.className = "stream-text";
    streamingBubble.prepend(textNode);
  }
  textNode.textContent = streamingBubble.dataset.text;
  scrollToBottom();
}

function finaliseStreamingBubble(id, createdAt) {
  if (!streamingBubble) return;
  streamingBubble.classList.remove("streaming");

  // Add time meta
  const meta = document.createElement("div");
  meta.className = "bubble-meta";
  meta.textContent = createdAt ? formatTime(createdAt) : formatTime(new Date());
  streamingBubble.appendChild(meta);

  const row = streamingBubble.closest(".msg-row");
  if (id) row.dataset.msgId = id;

  streamingBubble = null;
  scrollToBottom();
}

function scrollToBottom(smooth = true) {
  chatList.scrollTo({ top: chatList.scrollHeight, behavior: smooth ? "smooth" : "instant" });
}

function setStatus(text, online = null) {
  statusEl.textContent = text;
  statusEl.style.color = online === true ? "#a0e6b0" : online === false ? "#f87171" : "";
}

function setInputLocked(locked) {
  isSending = locked;
  inputEl.disabled = locked;
  sendBtn.disabled = locked || inputEl.value.trim() === "";
}

// ── REST: load history ────────────────────────────────────────────────────────
async function loadMessages(beforeId = null) {
  let url = `${API_BASE}/api/messages?session_id=${sessionId}&limit=${PAGE_SIZE}`;
  if (beforeId) url += `&before_id=${beforeId}`;

  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();  // { messages: [...], has_more: bool }
}

async function initialLoad() {
  try {
    const data = await loadMessages();
    hasMore = data.has_more;
    loadMoreBar.classList.toggle("hidden", !hasMore);

    if (data.messages.length === 0) {
      // New user — greeting will come via WS; nothing to render yet
      return;
    }

    // Track date labels while building the list
    lastDateLabel = null;
    data.messages.forEach(m => appendBubble(m));
    if (data.messages.length > 0) {
      oldestMsgId = data.messages[0].id;
    }
    scrollToBottom(false);
  } catch (e) {
    console.error("Failed to load initial messages", e);
  }
}

async function loadMoreMessages() {
  if (!hasMore || !oldestMsgId) return;
  loadMoreBtn.disabled = true;
  loadMoreBtn.textContent = "Loading…";

  try {
    const data = await loadMessages(oldestMsgId);
    hasMore = data.has_more;
    loadMoreBar.classList.toggle("hidden", !hasMore);

    if (data.messages.length === 0) return;

    // Remember scroll position to avoid jumping
    const prevHeight = chatList.scrollHeight;

    // Prepend messages (newest of the batch is at the bottom of what we prepend)
    // data.messages is chronological (oldest → newest), we prepend in reverse so
    // the oldest ends up at the very top.
    for (let i = data.messages.length - 1; i >= 0; i--) {
      appendBubble(data.messages[i], /* prepend */ true);
    }
    // Insert a date separator before the newly prepended block
    if (data.messages.length > 0) {
      maybeInsertDateSep(data.messages[0].created_at, /* prepend */ true);
      oldestMsgId = data.messages[0].id;
    }

    // Restore scroll position (don't jump to bottom)
    const newHeight = chatList.scrollHeight;
    chatList.scrollTop += newHeight - prevHeight;
  } catch (e) {
    console.error("Failed to load more messages", e);
  } finally {
    loadMoreBtn.disabled = false;
    loadMoreBtn.textContent = "Load earlier messages";
  }
}

// ── WebSocket ─────────────────────────────────────────────────────────────────
function connectWS() {
  if (ws && ws.readyState <= WebSocket.OPEN) return;

  setStatus("connecting…");
  ws = new WebSocket(`${WS_BASE}/ws?session_id=${sessionId}`);

  ws.addEventListener("open", () => {
    clearTimeout(reconnectTimer);
    setStatus("online", true);
    setInputLocked(false);
  });

  ws.addEventListener("message", e => {
    let frame;
    try { frame = JSON.parse(e.data); }
    catch { return; }

    switch (frame.type) {

      case "typing":
        if (frame.is_typing) {
          typingEl.classList.remove("hidden");
          scrollToBottom();
        } else {
          typingEl.classList.add("hidden");
        }
        break;

      case "user_saved":
        // Update the pending user bubble with the real id
        {
          const pending = chatList.querySelector(".bubble.pending");
          if (pending) {
            pending.classList.remove("pending");
            const row = pending.closest(".msg-row");
            if (frame.id) row.dataset.msgId = frame.id;
          }
        }
        break;

      case "chunk":
        appendChunk(frame.content);
        break;

      case "message_complete":
        finaliseStreamingBubble(frame.id, frame.created_at);
        setInputLocked(false);
        inputEl.focus();
        break;

      case "error":
        // Remove any partial streaming bubble
        if (streamingBubble) {
          streamingBubble.closest(".msg-row").remove();
          streamingBubble = null;
        }
        appendBubble({
          role: "assistant",
          content: frame.message || "Sorry, something went wrong. Please try again.",
          created_at: new Date().toISOString(),
        });
        setInputLocked(false);
        break;
    }
  });

  ws.addEventListener("close", () => {
    setStatus("disconnected", false);
    setInputLocked(true);
    // Auto-reconnect
    reconnectTimer = setTimeout(connectWS, RECONNECT_DELAY_MS);
  });

  ws.addEventListener("error", () => {
    ws.close();
  });
}

function sendMessage() {
  const content = inputEl.value.trim();
  if (!content || isSending || !ws || ws.readyState !== WebSocket.OPEN) return;

  // Optimistic update — show immediately, marked pending
  appendBubble({ role: "user", content, created_at: new Date().toISOString(), pending: true });
  scrollToBottom();

  setInputLocked(true);
  inputEl.value = "";
  inputEl.style.height = "auto";
  updateSendBtn();

  ws.send(JSON.stringify({ type: "message", content }));
}

// ── Input auto-resize ─────────────────────────────────────────────────────────
function updateSendBtn() {
  sendBtn.disabled = isSending || inputEl.value.trim() === "";
}

inputEl.addEventListener("input", () => {
  // Auto-grow textarea
  inputEl.style.height = "auto";
  inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + "px";
  updateSendBtn();
});

inputEl.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

sendBtn.addEventListener("click", sendMessage);

// ── Infinite scroll ───────────────────────────────────────────────────────────
chatList.addEventListener("scroll", () => {
  if (chatList.scrollTop < 60 && hasMore && !loadMoreBtn.disabled) {
    loadMoreBtn.disabled = true;  // debounce
    loadMoreMessages().finally(() => { loadMoreBtn.disabled = false; });
  }
});

loadMoreBtn.addEventListener("click", loadMoreMessages);

// ── Boot ──────────────────────────────────────────────────────────────────────
(async () => {
  sessionId = getOrCreateSessionId();
  setInputLocked(true);

  // Ensure the session exists on the server before WS connect
  try {
    await fetch(`${API_BASE}/api/session?session_id=${sessionId}`);
  } catch { /* offline — WS will handle it */ }

  await initialLoad();
  connectWS();
})();
