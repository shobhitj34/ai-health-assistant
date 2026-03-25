"""
Keep the Render free-tier service alive by pinging /api/health every 2 minutes.
Run: python3 keepalive.py
"""
import time
import urllib.request
import urllib.error
from datetime import datetime

URL = "https://disha-health-coach.onrender.com/api/health"
INTERVAL = 120  # seconds

print(f"Keep-alive started — pinging {URL} every {INTERVAL}s\n")

while True:
    try:
        with urllib.request.urlopen(URL, timeout=15) as r:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✓ OK ({r.status})")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✗ {e}")
    time.sleep(INTERVAL)
