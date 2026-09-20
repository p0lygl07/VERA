"""
One-time archive: separates pre-rebuild memory/log content from the fresh
rebuild state, so old session_memory.md content stops bleeding into current
context (this is what caused VERA to drift into stale UO conversation
content mid-task instead of completing the actual request).

Run once from the VERA project root:
    python archive_pre_rebuild_memory.py

What it does:
  - memory/session_memory.md: moves ALL current content to
    memory/archive/session_memory_pre_rebuild.md, replaces the live file
    with a clean header dated today.
  - logs/execution_log.md: splits rows by date. Everything before REBUILD_DATE
    goes to logs/archive/execution_log_pre_rebuild.md. Rows from REBUILD_DATE
    onward stay in the live file, so today's real verification entries aren't
    lost.
  - Flags (does not delete) the stale root-level execution_log.md, which is a
    different, older file than logs/execution_log.md and isn't the one the
    code actually writes to.
"""

import shutil
from pathlib import Path
from datetime import date

VERA_ROOT = Path(__file__).resolve().parent
REBUILD_DATE = "2026-09-05"  # adjust if your rebuild started on a different day

MEMORY_DIR = VERA_ROOT / "memory"
LOGS_DIR = VERA_ROOT / "logs"
ARCHIVE_MEMORY = MEMORY_DIR / "archive"
ARCHIVE_LOGS = LOGS_DIR / "archive"

ARCHIVE_MEMORY.mkdir(parents=True, exist_ok=True)
ARCHIVE_LOGS.mkdir(parents=True, exist_ok=True)


def archive_session_memory():
    live = MEMORY_DIR / "session_memory.md"
    if not live.exists():
        print("[SKIP] memory/session_memory.md not found")
        return
    old_content = live.read_text(encoding="utf-8")
    if not old_content.strip():
        print("[SKIP] session_memory.md is already empty")
        return

    archive_path = ARCHIVE_MEMORY / "session_memory_pre_rebuild.md"
    with open(archive_path, "a", encoding="utf-8") as f:
        f.write(f"\n\n<!-- archived {date.today().isoformat()} -->\n")
        f.write(old_content)

    live.write_text(
        f"# VERA Session Memory\n"
        f"# Reset {date.today().isoformat()} -- pre-rebuild content archived to "
        f"memory/archive/session_memory_pre_rebuild.md\n\n",
        encoding="utf-8",
    )
    print(f"[OK] session_memory.md archived ({len(old_content)} chars) and reset")


def archive_execution_log():
    live = LOGS_DIR / "execution_log.md"
    if not live.exists():
        print("[SKIP] logs/execution_log.md not found")
        return

    lines = live.read_text(encoding="utf-8").splitlines(keepends=True)

    header_lines = []
    old_rows = []
    new_rows = []
    in_table = False

    for line in lines:
        if line.startswith("|") and "Date" in line and "Tool" in line:
            header_lines.append(line)
            in_table = True
            continue
        if line.startswith("|---") or line.startswith("|-"):
            header_lines.append(line)
            continue
        if not in_table:
            header_lines.append(line)
            continue
        if line.startswith("|"):
            if REBUILD_DATE in line.split("|")[1]:
                new_rows.append(line)
            elif line.split("|")[1].strip() >= REBUILD_DATE:
                new_rows.append(line)
            else:
                old_rows.append(line)

    if not old_rows:
        print("[SKIP] no pre-rebuild rows found in execution_log.md")
        return

    archive_path = ARCHIVE_LOGS / "execution_log_pre_rebuild.md"
    with open(archive_path, "a", encoding="utf-8") as f:
        f.write(f"\n\n<!-- archived {date.today().isoformat()} -->\n")
        f.writelines(header_lines)
        f.writelines(old_rows)

    with open(live, "w", encoding="utf-8") as f:
        f.writelines(header_lines)
        f.writelines(new_rows)

    print(f"[OK] execution_log.md: archived {len(old_rows)} pre-rebuild rows, kept {len(new_rows)} current rows")


def flag_stale_root_log():
    stale = VERA_ROOT / "execution_log.md"
    if stale.exists():
        print(f"[FLAG] {stale} exists and is NOT the file vera_verify.py writes to "
              f"(that's logs/execution_log.md). This is old dead-weight content, "
              f"similar to the retired root vera_agent.py. Not auto-deleted -- "
              f"review and remove manually if confirmed unused.")


if __name__ == "__main__":
    archive_session_memory()
    archive_execution_log()
    flag_stale_root_log()
