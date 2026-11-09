import os
import time

import requests

from app.db import SessionLocal
from app.models import Notification

MOCK_URL = os.getenv("MOCK_SERVICES_URL", "http://127.0.0.1:9000")
TRIES = 3          # bounded retries
TIMEOUT = 3        # seconds per attempt


def call(method, path, **kwargs):
    """Call a mock service with a timeout and up to 3 tries."""
    last = None
    for attempt in range(1, TRIES + 1):
        try:
            r = requests.request(method, MOCK_URL + path, timeout=TIMEOUT, **kwargs)
            if r.status_code < 500:
                return r
            last = RuntimeError(f"HTTP {r.status_code}")
        except requests.RequestException as e:
            last = e
        time.sleep(0.5 * attempt)
    raise last


def lookup_email(username):
    """Integration 1: HR directory. Falls back to a default address."""
    try:
        r = call("GET", f"/hr/employees/{username}")
        if r.status_code == 200:
            return r.json()["email"], "HR directory"
    except Exception:
        pass
    return f"{username}@company.local", "fallback address (HR directory unavailable or unknown user)"


def notify(usernames, subject, body):
    """Integration 2: email notifier. Runs in the background."""
    db = SessionLocal()
    try:
        for username in usernames:
            email, source = lookup_email(username)
            try:
                r = call("POST", "/email/send",
                         json={"to": email, "subject": subject, "body": body})
                ok = r.status_code == 200
                detail = source if ok else f"{source}; email service answered HTTP {r.status_code}"
            except Exception as e:
                ok = False
                detail = f"{source}; email service unavailable ({type(e).__name__})"
            db.add(Notification(to_username=username, to_email=email,
                                subject=subject[:200], body=body,
                                status="sent" if ok else "failed",
                                detail=detail[:300]))
            db.commit()
    finally:
        db.close()