# Troubleshooting – Common Issues & Fixes

---

## 1. Page not loading / blank screen at http://localhost:8000

**Cause:** Server isn't running or crashed silently.

**Fix:**
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```
Check the terminal for any startup errors. If port 8000 is already in use:
```bash
kill $(lsof -ti :8000)
# then start the server again
```

---

## 2. Disha keeps connecting and disconnecting in a loop

**Cause:** The LLM API call for the initial greeting is failing (bad key, no quota, network error), which crashes the WebSocket. The frontend auto-reconnects and the cycle repeats.

**Fix:** Check your API key and quota first:
```bash
cd backend
source venv/bin/activate
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv()
from google import genai
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
r = client.models.generate_content(model='gemini-2.5-flash-lite', contents='hi')
print('OK:', r.text)
"
```
- If you get `RESOURCE_EXHAUSTED` → your free tier quota is used up; wait until it resets (daily) or try a different model (see issue #5)
- If you get `API_KEY_INVALID` → double-check the key in your `.env` file

---

## 3. "Sorry, I couldn't respond just now" on every message

**Cause:** Same as above — the Gemini API call is failing silently.

**Fix:** Run the test snippet from issue #2 to see the exact error, then follow the relevant fix below.

---

## 4. `GEMINI_API_KEY is not set` error in server logs

**Cause:** The `.env` file is missing or not in the right place.

**Fix:**
```bash
cd backend
ls .env          # should exist
cat .env         # should contain GEMINI_API_KEY=AIza...
```
If missing:
```bash
cp .env.example .env
# then open .env and add your key
```
Make sure you start the server from inside the `backend/` directory — the `.env` file is loaded relative to where `uvicorn` runs.

---

## 5. `429 RESOURCE_EXHAUSTED` — quota exceeded

**Cause:** The free tier daily/per-minute limit for the chosen model is exhausted.

**Fix — try a different model:**
```bash
# In backend/.env, add:
MAIN_MODEL=gemini-2.5-flash
FAST_MODEL=gemini-2.5-flash
```
Or list all models available on your key:
```bash
python3 -c "
import os; from dotenv import load_dotenv; load_dotenv()
from google import genai
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
for m in client.models.list():
    print(m.name)
"
```
Pick any `flash` model from the list and set it in `.env`.

---

## 6. `ModuleNotFoundError` when starting the server

**Cause:** Dependencies aren't installed, or the wrong Python environment is active.

**Fix:**
```bash
cd backend
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
If the `venv` folder doesn't exist yet:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 7. `TypeError: unsupported operand type(s) for |` or similar type errors

**Cause:** Running Python 3.9 with code that uses newer type hint syntax.

**Fix:** The codebase is already compatible with Python 3.9. If you see this error, make sure you're running the project's own venv, not a system Python:
```bash
which python3        # should point to venv/bin/python3
source venv/bin/activate
```

---

## 8. Protocols table is empty / Disha ignores health keywords

**Cause:** The seed script hasn't been run.

**Fix:**
```bash
cd backend
source venv/bin/activate
python3 -m scripts.seed_protocols
```
This is a one-time setup step. It's safe to run again — it skips seeding if rows already exist.

---

## 9. Old chat history doesn't load on refresh

**Cause:** The `disha.db` file was deleted, or a different `session_id` is being used.

**Fix:** The session ID is stored in your browser's `localStorage`. It persists across refreshes automatically as long as:
- You use the same browser
- You haven't cleared site data / localStorage

To inspect your session ID in the browser:
```
DevTools → Application → Local Storage → http://localhost:8000 → disha_session_id
```

---

## 10. Port 8000 is already in use

```bash
# Find what's using it
lsof -i :8000

# Kill it
kill $(lsof -ti :8000)

# Or run on a different port
uvicorn app.main:app --reload --port 8080
# then open http://localhost:8080
```

---

## 11. FutureWarning / NotOpenSSLWarning spam in terminal

These are harmless warnings from the Google SDK about Python 3.9 being end-of-life and the macOS system LibreSSL. They do not affect functionality. To suppress them:
```bash
uvicorn app.main:app --reload --port 8000 2>&1 | grep -v Warning | grep -v warn | grep -v urllib
```
Or upgrade to Python 3.11+ for a clean experience.

---

## 12. WebSocket connection refused in browser console

**Cause:** The server is running on a different port than the frontend expects, or CORS is blocking the WS upgrade.

**Fix:** Make sure the server is on port 8000 (the frontend connects to the same host/port it was served from). If you changed the port, update the `CORS_ORIGINS` env var:
```bash
# backend/.env
CORS_ORIGINS=http://localhost:8080
```
Then restart the server.

---

## Still stuck?

Check the full server logs — most errors print there with a full traceback. Run:
```bash
uvicorn app.main:app --port 8000 --log-level debug
```
