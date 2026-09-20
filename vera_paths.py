"""
VERA centralized path resolution.

Nothing in the codebase should hardcode C:\\Users\\<name>\\... again. Every
script should import from here instead. This file auto-detects its own
location, so moving the whole VERA folder (new machine, new username, new
drive) requires zero code changes anywhere else.

Drop this file at the VERA project root (same level as vera_agent.py).
"""

import sys
from pathlib import Path

# Root = the folder this file lives in, wherever that actually is.
VERA_ROOT = Path(__file__).resolve().parent

MEMORY_DIR = VERA_ROOT / "memory"
LOGS_DIR   = VERA_ROOT / "logs"
DATA_DIR   = VERA_ROOT / "data"
SKILLS_DIR = VERA_ROOT / "skills"
SRC_DIR    = VERA_ROOT / "src"

EVOLUTION_LOG   = MEMORY_DIR / "evolution.md"
LIVE_FEED_LOG   = LOGS_DIR / "live_feed.log"
ALERTS_LOG      = LOGS_DIR / "alerts.md"
DECISIONS_LOG   = MEMORY_DIR / "vera_decisions.md"
SESSION_MEMORY  = MEMORY_DIR / "session_memory.md"
EXECUTION_LOG   = LOGS_DIR / "execution_log.md"
DASHBOARD_STATE = LOGS_DIR / "dashboard_state.json"
USER_PROFILE    = MEMORY_DIR / "USER.md"
SOUL_PATH       = MEMORY_DIR / "SOUL.md"
VOICE_SCRIPT    = SRC_DIR / "vera_voice.py"

# The currently running interpreter -- never hardcode a python.exe path.
# Whatever venv/interpreter you launched VERA with is the one sub-processes
# should use too.
PYTHON_EXE = sys.executable

for _d in (MEMORY_DIR, LOGS_DIR, DATA_DIR):
    _d.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    print(f"VERA_ROOT   = {VERA_ROOT}")
    print(f"PYTHON_EXE  = {PYTHON_EXE}")
    print(f"MEMORY_DIR  = {MEMORY_DIR}")
    print(f"LOGS_DIR    = {LOGS_DIR}")
