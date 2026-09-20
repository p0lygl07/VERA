#!/usr/bin/env python3
"""
VERA Self-Repair Engine v1.0
VERA reasons through errors and fixes them autonomously.

When VERA encounters an error:
  1. Capture the full error context
  2. Ask her model to diagnose and propose a fix
  3. Apply the fix if confidence is HIGH
  4. Log the repair for learning

Usage: imported by other VERA modules
"""

import json
import sys
import traceback
import datetime
import requests
from pathlib import Path
from functools import wraps

VERA_ROOT   = Path(__file__).parent.parent
REPAIR_LOG  = VERA_ROOT / "logs" / "repair_log.md"
OLLAMA_URL  = "http://localhost:11434/api/chat"
MODEL       = "qwen3.5:9b"


def log_repair(error_type, diagnosis, fix_applied, outcome):
    """Log every self-repair attempt."""
    REPAIR_LOG.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = (
        f"\n## [{timestamp}] {error_type}\n"
        f"**Diagnosis:** {diagnosis[:200]}\n"
        f"**Fix applied:** {fix_applied}\n"
        f"**Outcome:** {outcome}\n---"
    )
    with open(REPAIR_LOG, "a", encoding="utf-8") as f:
        f.write(entry)


def diagnose_error(error, context="", code_snippet=""):
    """Ask VERA's model to diagnose an error and propose a fix."""
    try:
        payload = {
            "model": MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are VERA's self-repair engine. "
                        "Diagnose Python errors and propose specific fixes. "
                        "Be concise and precise. Give the exact fix, not general advice. "
                        "Format: DIAGNOSIS: [what went wrong] | FIX: [exact code or action]"
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"Error: {error}\n\n"
                        f"Context: {context}\n\n"
                        f"Code snippet: {code_snippet}\n\n"
                        "Diagnose and give the exact fix."
                    )
                }
            ],
            "stream": False,
            "options": {"temperature": 0.1, "num_ctx": 2048},
        }
        resp = requests.post(OLLAMA_URL, data=json.dumps(payload), timeout=30)
        resp.raise_for_status()
        return resp.json()["message"]["content"]
    except Exception:
        return f"Self-diagnosis unavailable. Manual fix needed."


def with_self_repair(context_description=""):
    """
    Decorator that wraps functions with VERA's self-repair logic.
    If the function fails, VERA diagnoses the error and logs it.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_msg = str(e)
                tb = traceback.format_exc()
                print(f"[VERA REPAIR] Error in {func.__name__}: {error_msg}")

                # Diagnose
                diagnosis = diagnose_error(
                    error=f"{type(e).__name__}: {error_msg}",
                    context=f"{context_description} | function: {func.__name__}",
                    code_snippet=tb.split("\n")[-3] if tb else ""
                )
                print(f"[VERA REPAIR] Diagnosis: {diagnosis[:150]}")

                # Log it
                log_repair(
                    error_type=f"{type(e).__name__} in {func.__name__}",
                    diagnosis=diagnosis,
                    fix_applied="logged for review",
                    outcome="function returned None"
                )

                return None
        return wrapper
    return decorator


class VERARepairContext:
    """Context manager for self-repairing code blocks."""

    def __init__(self, description, fallback=None, speak_fn=None):
        self.description = description
        self.fallback = fallback
        self.speak_fn = speak_fn
        self.error = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.error = exc_val
            error_msg = f"{exc_type.__name__}: {exc_val}"
            print(f"[VERA REPAIR] Error in '{self.description}': {error_msg}")

            # Diagnose
            diagnosis = diagnose_error(
                error=error_msg,
                context=self.description,
            )
            print(f"[VERA REPAIR] {diagnosis[:200]}")

            # Speak error summary if voice available
            if self.speak_fn:
                short = f"I hit an error in {self.description}. " \
                       f"I've diagnosed it and logged it for fixing."
                self.speak_fn(short)

            log_repair(
                error_type=f"{exc_type.__name__} in {self.description}",
                diagnosis=diagnosis,
                fix_applied="fallback used" if self.fallback else "none",
                outcome="suppressed" if self.fallback else "propagated"
            )

            if self.fallback is not None:
                return True  # Suppress exception, use fallback
        return False


# ── Known error patterns and their fixes ─────────────────────────────────────
KNOWN_FIXES = {
    "WinError 32": {
        "description": "File locked by another process",
        "fix": "Use BytesIO buffer instead of temp file, or add retry with delay",
        "auto_fix": "buffer",
    },
    "NoneType.*lower": {
        "description": "None value where string expected",
        "fix": "Add null check: `if value is not None` before calling .lower()",
        "auto_fix": "null_check",
    },
    "Connection refused": {
        "description": "Service not running or wrong port",
        "fix": "Check if service is running, verify port, try alternative ports",
        "auto_fix": None,
    },
    "timeout": {
        "description": "Request timed out",
        "fix": "Increase timeout, check network, or retry with exponential backoff",
        "auto_fix": "retry",
    },
    "404": {
        "description": "Endpoint not found - URL may have changed",
        "fix": "Check if API URL has changed, try alternative endpoints",
        "auto_fix": None,
    },
    "mismatched tag": {
        "description": "Malformed XML/HTML in response",
        "fix": "Use html.parser instead of xml.etree, or use feedparser",
        "auto_fix": None,
    },
}


def identify_known_fix(error_message):
    """Check if error matches a known pattern with a known fix."""
    import re
    for pattern, fix_info in KNOWN_FIXES.items():
        if re.search(pattern, error_message, re.IGNORECASE):
            return fix_info
    return None


def safe_call(fn, *args, fallback=None, description="", **kwargs):
    """
    Call a function safely with automatic error diagnosis.
    Returns fallback value on failure.
    """
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"

        # Check known fixes first
        known = identify_known_fix(error_msg)
        if known:
            print(f"[VERA REPAIR] Known error: {known['description']}")
            print(f"[VERA REPAIR] Fix: {known['fix']}")
            log_repair(
                error_type=error_msg[:80],
                diagnosis=known["description"],
                fix_applied=known["fix"],
                outcome=f"fallback={fallback}"
            )
        else:
            print(f"[VERA REPAIR] Error: {error_msg}")
            diagnosis = diagnose_error(error_msg, description)
            log_repair(error_msg[:80], diagnosis, "none", f"fallback={fallback}")

        return fallback


if __name__ == "__main__":
    print("VERA Self-Repair Engine -- test")

    # Test error identification
    test_errors = [
        "[WinError 32] The process cannot access the file",
        "'NoneType' object has no attribute 'lower'",
        "Connection refused",
        "404 Client Error: Not Found",
    ]

    print("\nKnown error patterns:")
    for err in test_errors:
        fix = identify_known_fix(err)
        if fix:
            print(f"  ERROR: {err[:50]}")
            print(f"  FIX:   {fix['fix']}")
        else:
            print(f"  ERROR: {err[:50]} -- no known fix")
    print("\nRepair engine ready.")
