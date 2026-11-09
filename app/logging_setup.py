"""Structured application logs: one JSON object per line, on screen and in logs/app.jsonl."""
import json
import logging
import os
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

_STANDARD = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record):
        entry = {"time": datetime.fromtimestamp(record.created, timezone.utc)
                 .isoformat(timespec="milliseconds"),
                 "level": record.levelname, "logger": record.name,
                 "event": record.getMessage()}
        for key, value in record.__dict__.items():          # fields passed with extra={...}
            if key not in _STANDARD and not key.startswith("_"):
                entry[key] = value
        if record.exc_info:
            entry["error"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def setup_logging():
    root = logging.getLogger()
    if getattr(root, "_json_logging", False):                # run once, even with --reload
        return
    root._json_logging = True
    root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    formatter = JsonFormatter()
    screen = logging.StreamHandler(sys.stdout)
    screen.setFormatter(formatter)
    root.addHandler(screen)
    log_file = os.getenv("LOG_FILE", "logs/app.jsonl")
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        to_file = RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=3,
                                      encoding="utf-8")
        to_file.setFormatter(formatter)
        root.addHandler(to_file)
    for noisy in ("httpx", "httpcore", "urllib3", "chromadb"):   # one line per model call is too much
        logging.getLogger(noisy).setLevel(logging.WARNING)


def log_question(user, out, ms, fallback):
    """One line per question. It holds ids and numbers only, never the question text."""
    try:
        role = user.role.name
    except Exception:
        role = ""
    logging.getLogger("knowledge.ask").info("question", extra={
        "run_id": out.get("run_id"), "user": user.username, "role": role,
        "status": out.get("status"), "duration_ms": ms, "fallback": fallback,
        "sources": len(out.get("sources", [])), "llm_calls": out.get("llm_calls", 0),
        "input_tokens": out.get("input_tokens", 0), "output_tokens": out.get("output_tokens", 0),
        "cost_usd": out.get("cost_usd", 0.0)})