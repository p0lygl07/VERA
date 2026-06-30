#!/usr/bin/env python3
"""
VERA — Verified Execution Reasoning Agent v0.3
Full feature build:
- Execution verification (v0.1)
- Skills loader (v0.2)
- Memory persistence (v0.2)
- Windows-aware shell (v0.3)
- Web search tool (v0.3)
"""

import json
import os
import sys
import subprocess
import requests
import datetime
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
VERA_ROOT    = Path(__file__).parent.parent
OLLAMA_URL   = "http://localhost:11434/api/chat"
MODEL        = "qwen3.5:9b"
PROFILE_PATH = VERA_ROOT / "memory" / "USER.md"
SOUL_PATH    = VERA_ROOT / "memory" / "SOUL.md"
SKILLS_PATH  = VERA_ROOT / "skills"
MEMORY_PATH  = VERA_ROOT / "memory" / "session_memory.md"
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

# ── Windows command map ───────────────────────────────────────────────────────
UNIX_TO_WINDOWS = {
    "cat": "type",
    "ls": "dir",
    "rm": "del",
    "cp": "copy",
    "mv": "move",
    "mkdir -p": "mkdir",
    "touch": "echo. >",
    "grep": "findstr",
    "which": "where.exe",
    "pwd": "cd",
    "clear": "cls",
}

def windows_aware_command(command):
    """Convert common Unix commands to Windows equivalents."""
    cmd = command.strip()
    for unix, win in UNIX_TO_WINDOWS.items():
        if cmd.startswith(unix + " ") or cmd == unix:
            cmd = cmd.replace(unix, win, 1)
            print(f"[VERA] Auto-converted Unix command to Windows: {command} → {cmd}")
            break
    return cmd

# ── Skills loader ─────────────────────────────────────────────────────────────
def load_skills():
    """Load all SKILL.md files from the skills directory."""
    if not SKILLS_PATH.exists():
        return {}
    skills = {}
    for skill_file in SKILLS_PATH.rglob("SKILL.md"):
        try:
            content = skill_file.read_text(encoding="utf-8")
            # Extract name from frontmatter
            name = skill_file.parent.name
            for line in content.split("\n"):
                if line.startswith("name:"):
                    name = line.replace("name:", "").strip()
                    break
            skills[name] = {
                "path": str(skill_file),
                "content": content,
            }
        except Exception as e:
            print(f"[VERA] Warning: could not load skill {skill_file}: {e}")
    return skills

def skills_context(skills):
    """Generate system prompt context from loaded skills."""
    if not skills:
        return ""
    lines = ["## Available Skills"]
    for name, skill in skills.items():
        # Extract description from frontmatter
        desc = f"skill: {name}"
        for line in skill["content"].split("\n"):
            if line.startswith("description:"):
                desc = line.replace("description:", "").strip()
                break
        lines.append(f"- **{name}**: {desc}")
    lines.append("\nTo use a skill, call read_skill(name='skill-name') to load its full instructions.")
    return "\n".join(lines)

# ── Memory persistence ────────────────────────────────────────────────────────
def load_session_memory():
    """Load previous session memory if it exists."""
    if MEMORY_PATH.exists():
        return MEMORY_PATH.read_text(encoding="utf-8")
    return None

def save_session_memory(messages):
    """Save a summary of this session to memory."""
    try:
        date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        # Extract user messages for summary
        user_msgs = [m["content"] for m in messages if m.get("role") == "user"]
        if not user_msgs:
            return
        summary_lines = [
            f"## Session: {date}",
            f"Messages: {len(messages)}",
            "Topics discussed:",
        ]
        for msg in user_msgs[:5]:  # First 5 user messages as summary
            summary_lines.append(f"- {msg[:100]}")
        summary = "\n".join(summary_lines)

        # Append to memory file
        with open(MEMORY_PATH, "a", encoding="utf-8") as f:
            f.write("\n\n" + summary)
        log_outcome("session_memory", True, "saved", f"saved {len(user_msgs)} messages to memory")
    except Exception as e:
        print(f"[VERA] Warning: could not save session memory: {e}")

# ── Web search ────────────────────────────────────────────────────────────────
def tool_web_search(query, num_results=5):
    """Real web search using DuckDuckGo's instant answer API."""
    try:
        url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1",
        }
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        results = []

        # Abstract (main answer)
        if data.get("AbstractText"):
            results.append(f"[ANSWER] {data['AbstractText']}")
            if data.get("AbstractURL"):
                results.append(f"Source: {data['AbstractURL']}")

        # Related topics
        for topic in data.get("RelatedTopics", [])[:num_results]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append(f"- {topic['Text'][:200]}")

        if not results:
            # Fallback: try web search results
            results.append(f"No instant answer found for: {query}")
            results.append("Try a more specific query or use read_file for local files.")

        output = "\n".join(results)
        log_outcome("web_search", True, "success", f"query: {query[:50]}")
        return output

    except requests.exceptions.ConnectionError:
        log_outcome("web_search", False, "no_connection", f"query: {query[:50]}")
        return "ERROR: No internet connection available."
    except Exception as e:
        log_outcome("web_search", False, "exception", str(e))
        return f"ERROR searching web: {e}"

# ── Tool implementations ──────────────────────────────────────────────────────
def tool_read_file(path):
    try:
        p = Path(path)
        if not p.exists():
            log_outcome("read_file", False, "not_found", f"path: {path}")
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
        verified, msg = verify_file_written(path, min_bytes=1)
        if not verified:
            return f"VERA VERIFICATION FAILED: {msg}"
        return f"OK: wrote {len(content)} characters to {path} [VERA VERIFIED]"
    except Exception as e:
        log_outcome("write_file", False, "exception", str(e))
        return f"ERROR writing file: {e}"

def tool_run_shell_command(command):
    command = windows_aware_command(command)
    print(f"\n[VERA CONFIRM] Agent wants to run:\n  {command}")
    answer = input("Allow? [y/N]: ").strip().lower()
    if answer != "y":
        log_outcome("run_shell_command", False, "user_declined", f"command: {command}")
        return "User declined to run this command."
    verified, output = verify_command_output(command, timeout=60)
    if not verified:
        return f"VERA VERIFICATION FAILED: {output}"
    return output or "(command produced no output)"

def tool_list_directory(path):
    try:
        p = Path(path)
        if not p.exists():
            log_outcome("list_directory", False, "not_found", f"path: {path}")
            return f"ERROR: directory not found: {path}"
        entries = list(p.iterdir())
        result = "\n".join(
            f"{'[DIR] ' if e.is_dir() else '[FILE]'} {e.name}"
            for e in sorted(entries)
        )
        log_outcome("list_directory", True, "success", f"listed {len(entries)} entries")
        return result or "(empty directory)"
    except Exception as e:
        log_outcome("list_directory", False, "exception", str(e))
        return f"ERROR listing directory: {e}"

def tool_read_skill(name):
    """Load a specific skill's full content."""
    skills = load_skills()
    if name in skills:
        log_outcome("read_skill", True, "success", f"loaded skill: {name}")
        return skills[name]["content"]
    # Try partial match
    matches = [k for k in skills if name.lower() in k.lower()]
    if matches:
        skill = skills[matches[0]]
        log_outcome("read_skill", True, "success", f"loaded skill: {matches[0]}")
        return skill["content"]
    log_outcome("read_skill", False, "not_found", f"skill: {name}")
    available = list(skills.keys())
    return f"ERROR: skill '{name}' not found. Available: {available}"

# ── Tool registry ─────────────────────────────────────────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file on disk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"}
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
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell_command",
            "description": "Run a Windows PowerShell command. Requires user confirmation. Auto-converts Unix commands.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"}
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
                    "path": {"type": "string"}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "num_results": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_skill",
            "description": "Load a VERA skill by name to get full instructions for a specific workflow.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"}
                },
                "required": ["name"],
            },
        },
    },
]

REGISTERED_TOOLS = {t["function"]["name"]: t for t in TOOLS}

TOOL_FUNCTIONS = {
    "read_file": tool_read_file,
    "write_file": tool_write_file,
    "run_shell_command": tool_run_shell_command,
    "list_directory": tool_list_directory,
    "web_search": tool_web_search,
    "read_skill": tool_read_skill,
}

# ── VERA tool dispatcher ──────────────────────────────────────────────────────
def call_tool(name, arguments):
    valid, msg = verify_tool_name(name, REGISTERED_TOOLS)
    if not valid:
        print(f"\n[VERA] ⚠ FABRICATION BLOCKED: {msg}")
        return msg
    func = TOOL_FUNCTIONS.get(name)
    if not func:
        return f"ERROR: tool '{name}' has no implementation"
    try:
        return func(**arguments)
    except TypeError as e:
        log_outcome(name, False, "bad_arguments", str(e))
        return f"ERROR: bad arguments for '{name}': {e}"

# ── System prompt ─────────────────────────────────────────────────────────────
def load_system_prompt(skills):
    parts = []
    if SOUL_PATH.exists():
        parts.append(SOUL_PATH.read_text(encoding="utf-8"))
    if PROFILE_PATH.exists():
        parts.append("## User Profile\n" + PROFILE_PATH.read_text(encoding="utf-8"))

    # Previous session memory
    memory = load_session_memory()
    if memory:
        # Only last 500 chars to keep context lean
        parts.append("## Recent Session Memory\n" + memory[-500:])

    # Skills context
    if skills:
        parts.append(skills_context(skills))

    parts.append(f"""## VERA Agent Rules
- You are VERA — Verified Execution Reasoning Agent
- Every tool call is verified by the VERA execution layer before claiming success
- Registered tools: {', '.join(REGISTERED_TOOLS.keys())}
- Do not invent tool names outside this list
- Windows environment — commands run in PowerShell
- Unix commands are auto-converted (cat→type, ls→dir, etc.)
- Never claim success before seeing [VERA VERIFIED] in the tool result
- If you cannot do something, say so plainly""")

    return "\n\n---\n\n".join(parts)

# ── Ollama API ────────────────────────────────────────────────────────────────
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

# ── Agent loop ────────────────────────────────────────────────────────────────
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
    print("VERA — Verified Execution Reasoning Agent v0.3")
    print("It doesn't say done until it's done.")
    print("=" * 60)

    # Load skills
    skills = load_skills()
    if skills:
        print(f"[skills loaded: {', '.join(skills.keys())}]")
    else:
        print("[no skills found — add SKILL.md files to skills/ folder]")

    print(f"[model: {MODEL}]")
    print(f"[log: {LOG_PATH}]")
    print("Type 'exit' to quit.\n")

    messages = []
    system_prompt = load_system_prompt(skills)
    messages.append({"role": "system", "content": system_prompt})

    loaded = []
    if SOUL_PATH.exists(): loaded.append("SOUL.md")
    if PROFILE_PATH.exists(): loaded.append("USER.md")
    if MEMORY_PATH.exists(): loaded.append("session memory")
    print(f"[context: {', '.join(loaded) if loaded else 'VERA rules only'}]\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nVERA: Saving session memory...")
            save_session_memory(messages)
            print("VERA: Goodbye.")
            break

        if user_input.lower() in ("exit", "quit"):
            print("VERA: Saving session memory...")
            save_session_memory(messages)
            print("VERA: Goodbye.")
            break
        if not user_input:
            continue

        answer, messages = run_agent_loop(user_input, messages)
        print(f"\nVERA: {answer}\n")


if __name__ == "__main__":
    main()
