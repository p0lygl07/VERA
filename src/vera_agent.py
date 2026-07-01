#!/usr/bin/env python3
"""
VERA -- Verified Execution Reasoning Agent v0.5
Full system tools integration + voice toggle + curiosity/decisiveness.

Voice toggle:
  say/type 'quiet mode' to silence
  say/type 'voice on'   to resume
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
PYTHON       = r"C:\Users\p0ly\AppData\Local\Programs\Python\Python311\python.exe"
VOICE_SCRIPT = Path(__file__).parent / "vera_voice.py"

MODEL_OPTIONS = {
    "temperature": 0.3,
    "num_ctx": 8192,
}

# ── Voice state ───────────────────────────────────────────────────────────────
voice_enabled = True


def speak(text):
    if not voice_enabled or not text or not text.strip():
        return
    if not VOICE_SCRIPT.exists():
        return
    clean = text.replace("**", "").replace("*", "").replace("#", "").replace("`", "")
    if len(clean) > 500:
        clean = clean[:280].rsplit(" ", 1)[0] + ". See terminal for full output."
    try:
        subprocess.Popen([PYTHON, str(VOICE_SCRIPT), "speak", clean])
    except Exception:
        pass


def speak_greeting():
    hour = datetime.datetime.now().hour
    if hour < 12:
        greeting = "Good morning Josh. VERA is online."
    elif hour < 17:
        greeting = "Good afternoon Josh. VERA is online."
    else:
        greeting = "Good evening Josh. VERA is online."
    speak(greeting)


# ── Verifier ──────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from vera_verify import (
    verify_file_written,
    verify_command_output,
    verify_tool_name,
    log_outcome,
)

# ── System tools ──────────────────────────────────────────────────────────────
try:
    from vera_system_tools import SYSTEM_TOOLS, SYSTEM_TOOL_FUNCTIONS
    SYSTEM_TOOLS_AVAILABLE = True
except ImportError:
    SYSTEM_TOOLS = []
    SYSTEM_TOOL_FUNCTIONS = {}
    SYSTEM_TOOLS_AVAILABLE = False
    print("[VERA] Warning: vera_system_tools.py not found — system tools disabled")

# ── Windows command map ───────────────────────────────────────────────────────
UNIX_TO_WINDOWS = {
    "cat ": "type ",
    "ls ": "dir ",
    "ls\n": "dir\n",
    "rm ": "del ",
    "cp ": "copy ",
    "mv ": "move ",
    "grep ": "findstr ",
    "which ": "where.exe ",
    "pwd": "cd",
    "clear": "cls",
}


def windows_aware_command(command):
    cmd = command.strip()
    for unix, win in UNIX_TO_WINDOWS.items():
        if cmd.startswith(unix.strip()):
            cmd = win.strip() + cmd[len(unix.strip()):]
            print(f"[VERA] Auto-converted: {command.strip()} -> {cmd}")
            break
    return cmd


# ── Skills ────────────────────────────────────────────────────────────────────
def load_skills():
    if not SKILLS_PATH.exists():
        return {}
    skills = {}
    for skill_file in SKILLS_PATH.rglob("SKILL.md"):
        try:
            content = skill_file.read_text(encoding="utf-8")
            name = skill_file.parent.name
            for line in content.split("\n"):
                if line.startswith("name:"):
                    name = line.replace("name:", "").strip()
                    break
            skills[name] = {"path": str(skill_file), "content": content}
        except Exception:
            pass
    return skills


def skills_context(skills):
    if not skills:
        return ""
    lines = ["## Available Skills"]
    for name, skill in skills.items():
        desc = f"skill: {name}"
        for line in skill["content"].split("\n"):
            if line.startswith("description:"):
                desc = line.replace("description:", "").strip()
                break
        lines.append(f"- **{name}**: {desc}")
    lines.append("\nTo use a skill: read_skill(name='skill-name')")
    return "\n".join(lines)


# ── Memory ────────────────────────────────────────────────────────────────────
def load_session_memory():
    if MEMORY_PATH.exists():
        return MEMORY_PATH.read_text(encoding="utf-8")
    return None


def save_session_memory(messages):
    try:
        date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        user_msgs = [m["content"] for m in messages if m.get("role") == "user"]
        if not user_msgs:
            return
        summary_lines = [f"## Session: {date}", f"Messages: {len(messages)}", "Topics:"]
        for msg in user_msgs[:5]:
            summary_lines.append(f"- {msg[:100]}")
        with open(MEMORY_PATH, "a", encoding="utf-8") as f:
            f.write("\n\n" + "\n".join(summary_lines))
        log_outcome("session_memory", True, "saved", f"{len(user_msgs)} messages")
    except Exception as e:
        print(f"[VERA] Warning: could not save session memory: {e}")


# ── Web search ────────────────────────────────────────────────────────────────
def tool_web_search(query, num_results=5):
    try:
        url = "https://api.duckduckgo.com/"
        params = {"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"}
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        results = []
        if data.get("AbstractText"):
            results.append(f"[ANSWER] {data['AbstractText']}")
            if data.get("AbstractURL"):
                results.append(f"Source: {data['AbstractURL']}")
        for topic in data.get("RelatedTopics", [])[:num_results]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append(f"- {topic['Text'][:200]}")
        if not results:
            results.append(f"No instant answer found for: {query}")
        log_outcome("web_search", True, "success", f"query: {query[:50]}")
        return "\n".join(results)
    except Exception as e:
        log_outcome("web_search", False, "exception", str(e))
        return f"ERROR searching web: {e}"


# ── Core tools ────────────────────────────────────────────────────────────────
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
    print(f"\n[VERA CONFIRM] Run:\n  {command}")
    answer = input("Allow? [y/N]: ").strip().lower()
    if answer != "y":
        log_outcome("run_shell_command", False, "user_declined", f"command: {command}")
        return "User declined."
    verified, output = verify_command_output(command, timeout=60)
    if not verified:
        return f"VERA VERIFICATION FAILED: {output}"
    return output or "(no output)"


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
        return result or "(empty)"
    except Exception as e:
        log_outcome("list_directory", False, "exception", str(e))
        return f"ERROR: {e}"


def tool_read_skill(name):
    skills = load_skills()
    if name in skills:
        log_outcome("read_skill", True, "success", f"loaded skill: {name}")
        return skills[name]["content"]
    matches = [k for k in skills if name.lower() in k.lower()]
    if matches:
        log_outcome("read_skill", True, "success", f"loaded skill: {matches[0]}")
        return skills[matches[0]]["content"]
    log_outcome("read_skill", False, "not_found", f"skill: {name}")
    return f"ERROR: skill '{name}' not found. Available: {list(skills.keys())}"


# ── Tool registry ─────────────────────────────────────────────────────────────
CORE_TOOLS = [
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Read the contents of a file on disk.",
        "parameters": {"type": "object",
                       "properties": {"path": {"type": "string"}},
                       "required": ["path"]},
    }},
    {"type": "function", "function": {
        "name": "write_file",
        "description": "Write content to a file. VERA verifies after writing.",
        "parameters": {"type": "object",
                       "properties": {"path": {"type": "string"},
                                      "content": {"type": "string"}},
                       "required": ["path", "content"]},
    }},
    {"type": "function", "function": {
        "name": "run_shell_command",
        "description": "Run a Windows PowerShell command. Requires confirmation. Auto-converts Unix commands.",
        "parameters": {"type": "object",
                       "properties": {"command": {"type": "string"}},
                       "required": ["command"]},
    }},
    {"type": "function", "function": {
        "name": "list_directory",
        "description": "List files and folders in a directory.",
        "parameters": {"type": "object",
                       "properties": {"path": {"type": "string"}},
                       "required": ["path"]},
    }},
    {"type": "function", "function": {
        "name": "web_search",
        "description": "Search the web for current information.",
        "parameters": {"type": "object",
                       "properties": {"query": {"type": "string"},
                                      "num_results": {"type": "integer"}},
                       "required": ["query"]},
    }},
    {"type": "function", "function": {
        "name": "read_skill",
        "description": "Load a VERA skill by name to get full workflow instructions.",
        "parameters": {"type": "object",
                       "properties": {"name": {"type": "string"}},
                       "required": ["name"]},
    }},
]

# Combine core + system tools
ALL_TOOLS = CORE_TOOLS + SYSTEM_TOOLS
REGISTERED_TOOLS = {t["function"]["name"]: t for t in ALL_TOOLS}

CORE_TOOL_FUNCTIONS = {
    "read_file": tool_read_file,
    "write_file": tool_write_file,
    "run_shell_command": tool_run_shell_command,
    "list_directory": tool_list_directory,
    "web_search": tool_web_search,
    "read_skill": tool_read_skill,
}

TOOL_FUNCTIONS = {**CORE_TOOL_FUNCTIONS, **SYSTEM_TOOL_FUNCTIONS}


def call_tool(name, arguments):
    valid, msg = verify_tool_name(name, REGISTERED_TOOLS)
    if not valid:
        print(f"\n[VERA] FABRICATION BLOCKED: {msg}")
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
    memory = load_session_memory()
    if memory:
        parts.append("## Recent Session Memory\n" + memory[-500:])
    if skills:
        parts.append(skills_context(skills))

    tool_list = list(REGISTERED_TOOLS.keys())
    parts.append(f"""## VERA Agent Rules
- You are VERA -- Verified Execution Reasoning Agent v0.5
- Every tool call is verified before claiming success
- Registered tools: {', '.join(tool_list)}
- Do not invent tool names outside this list
- Windows environment -- commands run in PowerShell
- Unix commands are auto-converted (cat->type, ls->dir, etc.)
- Never claim success before seeing [VERA VERIFIED] in tool result
- Make decisions where uncertain -- act on 80% context, correct afterward
- Never ask more than one clarifying question before acting
- When Josh says go or do it -- act immediately
- Be curious -- notice things, ask one follow-up question when relevant
- Think out loud on complex problems
- Surface relevant information proactively without being asked""")

    return "\n\n---\n\n".join(parts)


# ── Ollama API ────────────────────────────────────────────────────────────────
def chat(messages):
    payload = {
        "model": MODEL,
        "messages": messages,
        "tools": ALL_TOOLS,
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
    global voice_enabled

    print("=" * 60)
    print("VERA -- Verified Execution Reasoning Agent v0.5")
    print("It doesn't say done until it's done.")
    print("=" * 60)

    skills = load_skills()
    if skills:
        print(f"[skills: {', '.join(skills.keys())}]")

    tool_count = len(REGISTERED_TOOLS)
    system_tool_count = len(SYSTEM_TOOL_FUNCTIONS)
    print(f"[tools: {tool_count} total ({system_tool_count} system tools)]")
    print(f"[model: {MODEL}]")
    print(f"[voice: ON -- 'quiet mode' to silence, 'voice on' to resume]")
    print("Type 'exit' to quit.\n")

    messages = []
    system_prompt = load_system_prompt(skills)
    messages.append({"role": "system", "content": system_prompt})

    loaded = []
    if SOUL_PATH.exists():
        loaded.append("SOUL.md v3")
    if PROFILE_PATH.exists():
        loaded.append("USER.md")
    if MEMORY_PATH.exists():
        loaded.append("memory")
    print(f"[context: {', '.join(loaded) if loaded else 'VERA rules only'}]\n")

    speak_greeting()

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nVERA: Saving session memory...")
            save_session_memory(messages)
            speak("Goodbye Josh.")
            print("VERA: Goodbye.")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quiet mode", "quiet", "silence", "mute"):
            voice_enabled = False
            print("VERA: Voice muted. Type 'voice on' to resume.\n")
            continue

        if user_input.lower() in ("voice on", "unmute", "speak"):
            voice_enabled = True
            speak("Voice is back online.")
            print("VERA: Voice enabled.\n")
            continue

        if user_input.lower() in ("exit", "quit", "goodbye"):
            print("VERA: Saving session memory...")
            save_session_memory(messages)
            speak("Goodbye Josh.")
            print("VERA: Goodbye.")
            break

        if user_input.lower() == "tools":
            print(f"[VERA] Registered tools ({len(REGISTERED_TOOLS)}):")
            for name in sorted(REGISTERED_TOOLS.keys()):
                print(f"  - {name}")
            print()
            continue

        answer, messages = run_agent_loop(user_input, messages)
        print(f"\nVERA: {answer}\n")
        speak(answer)


if __name__ == "__main__":
    main()
