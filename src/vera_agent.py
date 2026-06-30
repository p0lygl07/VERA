#!/usr/bin/env python3
"""
VERA — Verified Execution Reasoning Agent
Local Ollama tool-calling loop with execution verification.

Every tool call is verified before claiming success.
Every outcome is logged to logs/execution_log.md.
"""

import json
import os
import sys
import subprocess
import requests
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
VERA_ROOT    = Path(__file__).parent.parent
OLLAMA_URL   = "http://localhost:11434/api/chat"
MODEL        = "qwen3.5:9b"
PROFILE_PATH = VERA_ROOT / "memory" / "USER.md"
SOUL_PATH    = VERA_ROOT / "memory" / "SOUL.md"
LOG_PATH     = VERA_ROOT / "logs" / "execution_log.md"

MODEL_OPTIONS = {
    "temperature": 0.2,
    "num_ctx": 8192,
}

# ── Import VERA verifier ──────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from vera_verify import (
    verify_file_written,
    verify_command_output,
    verify_tool_name,
    log_outcome,
)

# ── Registered tool schema (VERA enforces this) ───────────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file on disk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file to read."}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file on disk. VERA verifies the file exists after writing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file to write."},
                    "content": {"type": "string", "description": "Content to write to the file."},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell_command",
            "description": "Run a shell command. Requires user confirmation. VERA verifies real output was produced.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to run."}
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and folders in a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to list."}
                },
                "required": ["path"],
            },
        },
    },
]

# Build the registered tool name set for verification
REGISTERED_TOOLS = {t["function"]["name"]: t for t in TOOLS}


# ── Tool implementations (with VERA verification) ─────────────────────────────
def tool_read_file(path):
    try:
        p = Path(path)
        if not p.exists():
            log_outcome("read_file", False, "file_not_found", f"path does not exist: {path}")
            return f"ERROR: file not found: {path}"
        content = p.read_text(encoding="utf-8", errors="replace")
        log_outcome("read_file", True, "success", f"read {len(content)} chars from {path}")
        return content
    except Exception as e:
        log_outcome("read_file", False, "exception", str(e))
        return f"ERROR reading file: {e}"


def tool_write_file(path, content):
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

        # VERA verification — confirm file actually exists with content
        verified, msg = verify_file_written(path, min_bytes=1)
        if not verified:
            return f"VERA VERIFICATION FAILED: {msg}"

        return f"OK: wrote {len(content)} characters to {path} [VERA VERIFIED]"
    except Exception as e:
        log_outcome("write_file", False, "exception", str(e))
        return f"ERROR writing file: {e}"


def tool_run_shell_command(command):
    print(f"\n[VERA CONFIRM] Agent wants to run:\n  {command}")
    answer = input("Allow? [y/N]: ").strip().lower()
    if answer != "y":
        log_outcome("run_shell_command", False, "user_declined", f"command: {command}")
        return "User declined to run this command."

    # VERA verification — confirm real output was produced
    verified, output = verify_command_output(command, timeout=60)
    if not verified:
        return f"VERA VERIFICATION FAILED: {output}"

    return output or "(command produced no output)"


def tool_list_directory(path):
    try:
        p = Path(path)
        if not p.exists():
            log_outcome("list_directory", False, "not_found", f"directory does not exist: {path}")
            return f"ERROR: directory not found: {path}"
        entries = list(p.iterdir())
        result = "\n".join(
            f"{'[DIR] ' if e.is_dir() else '[FILE]'} {e.name}"
            for e in sorted(entries)
        )
        log_outcome("list_directory", True, "success", f"listed {len(entries)} entries in {path}")
        return result or "(empty directory)"
    except Exception as e:
        log_outcome("list_directory", False, "exception", str(e))
        return f"ERROR listing directory: {e}"


TOOL_FUNCTIONS = {
    "read_file": tool_read_file,
    "write_file": tool_write_file,
    "run_shell_command": tool_run_shell_command,
    "list_directory": tool_list_directory,
}


# ── VERA tool dispatcher (with schema verification) ───────────────────────────
def call_tool(name, arguments):
    # Step 1: verify tool name is registered before calling
    valid, msg = verify_tool_name(name, REGISTERED_TOOLS)
    if not valid:
        print(f"\n[VERA] ⚠ FABRICATION BLOCKED: {msg}")
        return msg

    func = TOOL_FUNCTIONS.get(name)
    if not func:
        log_outcome(name, False, "missing_implementation", "tool registered but not implemented")
        return f"ERROR: tool '{name}' has no implementation"

    try:
        return func(**arguments)
    except TypeError as e:
        log_outcome(name, False, "bad_arguments", str(e))
        return f"ERROR: bad arguments for '{name}': {e}"


# ── System prompt loader ──────────────────────────────────────────────────────
def load_system_prompt():
    parts = []

    # Load SOUL.md if exists
    if SOUL_PATH.exists():
        parts.append(SOUL_PATH.read_text(encoding="utf-8"))

    # Load USER.md if exists
    if PROFILE_PATH.exists():
        parts.append("## User Profile\n" + PROFILE_PATH.read_text(encoding="utf-8"))

    # Add VERA behavior rules
    parts.append("""## VERA Agent Rules
- You are VERA — Verified Execution Reasoning Agent
- Every tool call you make is verified by the VERA execution layer
- If a tool call fails verification, you will be told explicitly
- Never claim success before seeing a [VERA VERIFIED] confirmation
- If you cannot do something with registered tools, say so plainly
- Registered tools: read_file, write_file, run_shell_command, list_directory
- Do not invent tool names — only these four exist in this session
- Windows environment — use Windows paths and commands (dir, type, copy, del)""")

    return "\n\n---\n\n".join(parts) if parts else None


# ── Ollama API call ───────────────────────────────────────────────────────────
def chat(messages):
    payload = {
        "model": MODEL,
        "messages": messages,
        "tools": TOOLS,
        "stream": False,
        "options": MODEL_OPTIONS,
    }
    resp = requests.post(OLLAMA_URL, data=json.dumps(payload))
    resp.raise_for_status()
    return resp.json()


# ── Main agent loop ───────────────────────────────────────────────────────────
def run_agent_loop(user_input, messages):
    messages.append({"role": "user", "content": user_input})

    while True:
        result = chat(messages)
        message = result["message"]
        messages.append(message)

        tool_calls = message.get("tool_calls")
        if not tool_calls:
            return message.get("content", ""), messages

        for tc in tool_calls:
            fn = tc["function"]
            name = fn["name"]
            args = fn.get("arguments", {})

            print(f"\n[VERA TOOL CALL] {name}({args})")
            tool_result = call_tool(name, args)
            preview = str(tool_result)[:300]
            ellipsis = "..." if len(str(tool_result)) > 300 else ""
            print(f"[VERA RESULT] {preview}{ellipsis}")

            messages.append({
                "role": "tool",
                "content": str(tool_result),
                "name": name,
            })


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("VERA — Verified Execution Reasoning Agent")
    print("It doesn't say done until it's done.")
    print("=" * 60)
    print(f"Model: {MODEL}")
    print(f"Endpoint: {OLLAMA_URL}")
    print(f"Log: {LOG_PATH}")
    print("Type 'exit' to quit.\n")

    messages = []

    system_prompt = load_system_prompt()
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
        loaded = []
        if SOUL_PATH.exists(): loaded.append("SOUL.md")
        if PROFILE_PATH.exists(): loaded.append("USER.md")
        loaded.append("VERA rules")
        print(f"[loaded: {', '.join(loaded)}]")
    else:
        print("[no profile found — running with VERA rules only]")

    print()

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nVERA: Goodbye.")
            break

        if user_input.lower() in ("exit", "quit"):
            print("VERA: Goodbye.")
            break
        if not user_input:
            continue

        answer, messages = run_agent_loop(user_input, messages)
        print(f"\nVERA: {answer}\n")


if __name__ == "__main__":
    main()
