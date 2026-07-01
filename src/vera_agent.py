#!/usr/bin/env python3
"""
VERA -- Verified Execution Reasoning Agent v0.6
Fixes:
- Shell tool always uses PowerShell (not cmd.exe)
- $HOME/~ path auto-resolution to Windows paths
- Output flush before voice fires
- Truth layer tracking
- Dashboard state writer
- Session uptime + fabrication rate metrics
"""

import json
import os
import sys
import subprocess
import requests
import datetime
from pathlib import Path

VERA_ROOT    = Path("C:/Users/p0ly/Desktop/AI/VERA")
OLLAMA_URL   = "http://localhost:11434/api/chat"
MODEL        = "qwen3.5:9b"
PROFILE_PATH = VERA_ROOT / "memory" / "USER.md"
SOUL_PATH    = VERA_ROOT / "memory" / "SOUL.md"
SKILLS_PATH  = VERA_ROOT / "skills"
MEMORY_PATH  = VERA_ROOT / "memory" / "session_memory.md"
LOG_PATH     = VERA_ROOT / "logs" / "execution_log.md"
DASHBOARD_STATE = VERA_ROOT / "logs" / "dashboard_state.json"
PYTHON       = r"C:\Users\p0ly\AppData\Local\Programs\Python\Python311\python.exe"
VOICE_SCRIPT = VERA_ROOT / "src" / "vera_voice.py"

MODEL_OPTIONS = {"temperature": 0.3, "num_ctx": 8192}

voice_enabled    = True
session_start    = datetime.datetime.now()
total_calls      = 0
verified_calls   = 0
fabricated_calls = 0
active_role      = "ORACLE"
current_truth    = "T3"
inference_times  = []


def resolve_path(path_str):
    """Resolve $HOME, ~, Unix-style paths to real Windows paths."""
    s = str(path_str)
    home = str(Path.home())
    s = s.replace("$HOME", home).replace("~", home)
    # Convert forward-slash absolute paths that look Unix-like
    if s.startswith("/Users/"):
        s = "C:" + s.replace("/", "\\")
    elif s.startswith("/home/"):
        s = home + s[s.index("/", 1):]
    return s


def write_dashboard_state(thinking="", role="", truth="", tool_call="", status="READY"):
    global active_role, current_truth
    if role: active_role = role
    if truth: current_truth = truth
    uptime = str(datetime.datetime.now() - session_start).split(".")[0]
    fab_rate = f"{(fabricated_calls / max(total_calls, 1)) * 100:.1f}%"
    avg_inference = f"{sum(inference_times[-10:]) / max(len(inference_times[-10:]), 1):.0f}ms" if inference_times else "--"
    state = {
        "timestamp": datetime.datetime.now().isoformat(),
        "status": status,
        "active_role": active_role,
        "truth_layer": current_truth,
        "thinking": thinking[:300] if thinking else "",
        "tool_call": tool_call[:200] if tool_call else "",
        "uptime": uptime,
        "total_calls": total_calls,
        "verified_calls": verified_calls,
        "fabricated_calls": fabricated_calls,
        "fabrication_rate": fab_rate,
        "avg_inference_ms": avg_inference,
        "model": MODEL,
        "voice_enabled": voice_enabled,
    }
    try:
        DASHBOARD_STATE.parent.mkdir(parents=True, exist_ok=True)
        DASHBOARD_STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception:
        pass


def speak(text):
    if not voice_enabled or not text or not text.strip():
        return
    if not VOICE_SCRIPT.exists():
        return
    clean = text.replace("**","").replace("*","").replace("#","").replace("`","")
    if len(clean) > 500:
        clean = clean[:280].rsplit(" ", 1)[0] + ". See terminal for full output."
    try:
        subprocess.Popen([PYTHON, str(VOICE_SCRIPT), "speak", clean])
    except Exception:
        pass


def speak_greeting():
    hour = datetime.datetime.now().hour
    if hour < 12:   g = "Good morning Josh. VERA is online."
    elif hour < 17: g = "Good afternoon Josh. VERA is online."
    else:           g = "Good evening Josh. VERA is online."
    speak(g)


sys.path.insert(0, str(VERA_ROOT / "src"))
from vera_verify import verify_file_written, verify_command_output, verify_tool_name, log_outcome

try:
    from vera_system_tools import SYSTEM_TOOLS, SYSTEM_TOOL_FUNCTIONS
except ImportError:
    SYSTEM_TOOLS = []
    SYSTEM_TOOL_FUNCTIONS = {}

UNIX_TO_WIN = {
    "cat ": "type ", "ls ": "dir ", "rm ": "del ",
    "cp ": "copy ", "mv ": "move ", "grep ": "findstr ",
    "which ": "where.exe ", "pwd": "cd", "clear": "cls",
}


def windows_aware_command(command):
    cmd = resolve_path(command).strip()
    for u, w in UNIX_TO_WIN.items():
        if cmd.startswith(u.strip()):
            cmd = w.strip() + cmd[len(u.strip()):]
            print(f"[VERA] Converted: {command.strip()} -> {cmd}", flush=True)
            break
    return cmd


def load_skills():
    if not SKILLS_PATH.exists(): return {}
    skills = {}
    for sf in SKILLS_PATH.rglob("SKILL.md"):
        try:
            content = sf.read_text(encoding="utf-8")
            name = sf.parent.name
            for line in content.split("\n"):
                if line.startswith("name:"):
                    name = line.replace("name:", "").strip(); break
            skills[name] = {"path": str(sf), "content": content}
        except Exception:
            pass
    return skills


def skills_context(skills):
    if not skills: return ""
    lines = ["## Available Skills"]
    for name, skill in skills.items():
        desc = f"skill: {name}"
        for line in skill["content"].split("\n"):
            if line.startswith("description:"):
                desc = line.replace("description:", "").strip(); break
        lines.append(f"- **{name}**: {desc}")
    lines.append("\nTo use: read_skill(name='skill-name')")
    return "\n".join(lines)


def load_session_memory():
    if MEMORY_PATH.exists():
        return MEMORY_PATH.read_text(encoding="utf-8")
    return None


def save_session_memory(messages):
    try:
        date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        user_msgs = [m["content"] for m in messages if m.get("role") == "user"]
        if not user_msgs: return
        uptime = str(datetime.datetime.now() - session_start).split(".")[0]
        lines = [
            f"## Session: {date} (uptime: {uptime})",
            f"Calls: {total_calls} | Verified: {verified_calls} | Fab: {fabricated_calls}",
            "Topics:"
        ]
        for msg in user_msgs[:5]:
            lines.append(f"- {msg[:100]}")
        with open(MEMORY_PATH, "a", encoding="utf-8") as f:
            f.write("\n\n" + "\n".join(lines))
        log_outcome("session_memory", True, "saved", f"{len(user_msgs)} messages")
    except Exception as e:
        print(f"[VERA] Memory save warning: {e}", flush=True)


def tool_web_search(query, num_results=5):
    try:
        resp = requests.get("https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
            timeout=10)
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
            results.append(f"No instant answer for: {query}")
        log_outcome("web_search", True, "success", f"query: {query[:50]}")
        return "\n".join(results)
    except Exception as e:
        log_outcome("web_search", False, "exception", str(e))
        return f"ERROR: {e}"


def tool_read_file(path):
    path = resolve_path(path)
    try:
        p = Path(path)
        if not p.exists():
            log_outcome("read_file", False, "not_found", f"path: {path}")
            return f"ERROR: file not found: {path}"
        content = p.read_text(encoding="utf-8", errors="replace")
        log_outcome("read_file", True, "success", f"read {len(content)} chars")
        return content
    except Exception as e:
        log_outcome("read_file", False, "exception", str(e))
        return f"ERROR: {e}"


def tool_write_file(path, content):
    path = resolve_path(path)
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
        return f"ERROR: {e}"


def tool_run_shell_command(command):
    """FIX: always run through PowerShell, not cmd.exe"""
    command = windows_aware_command(command)
    print(f"\n[VERA CONFIRM] Run:\n  {command}", flush=True)
    answer = input("Allow? [y/N]: ").strip().lower()
    if answer != "y":
        log_outcome("run_shell_command", False, "user_declined", f"cmd: {command}")
        return "User declined."

    # Always use PowerShell
    ps_command = f'powershell -NoProfile -NonInteractive -Command "{command.replace(chr(34), chr(39))}"'
    verified, output = verify_command_output(ps_command, timeout=60)
    if not verified:
        # Try without wrapping if already a ps command
        verified, output = verify_command_output(command, timeout=60)
    if not verified:
        return f"VERA VERIFICATION FAILED: {output}"
    return output or "(no output)"


def tool_list_directory(path):
    path = resolve_path(path)
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
        log_outcome("read_skill", True, "success", f"skill: {name}")
        return skills[name]["content"]
    matches = [k for k in skills if name.lower() in k.lower()]
    if matches:
        log_outcome("read_skill", True, "success", f"skill: {matches[0]}")
        return skills[matches[0]]["content"]
    log_outcome("read_skill", False, "not_found", f"skill: {name}")
    return f"ERROR: skill '{name}' not found. Available: {list(skills.keys())}"


CORE_TOOLS = [
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Read a file from disk. ALWAYS use full Windows paths like C:\\Users\\p0ly\\... Never use $HOME, ~, or Unix-style paths.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    }},
    {"type": "function", "function": {
        "name": "write_file",
        "description": "Write content to a file. VERA verifies after writing. Use full Windows paths. VERA root: C:\\Users\\p0ly\\Desktop\\AI\\VERA",
        "parameters": {"type": "object",
                       "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                       "required": ["path", "content"]},
    }},
    {"type": "function", "function": {
        "name": "run_shell_command",
        "description": "Run a PowerShell command. Requires user confirmation. Use PowerShell syntax (New-Item, Get-ChildItem, etc). Auto-converts Unix commands.",
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
    }},
    {"type": "function", "function": {
        "name": "list_directory",
        "description": "List files and folders. Use full Windows paths like C:\\Users\\p0ly\\Desktop\\AI\\VERA",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    }},
    {"type": "function", "function": {
        "name": "web_search",
        "description": "Search the web for current information.",
        "parameters": {"type": "object",
                       "properties": {"query": {"type": "string"}, "num_results": {"type": "integer"}},
                       "required": ["query"]},
    }},
    {"type": "function", "function": {
        "name": "read_skill",
        "description": "Load a VERA skill by name for workflow instructions.",
        "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
    }},
]

ALL_TOOLS = CORE_TOOLS + SYSTEM_TOOLS
REGISTERED_TOOLS = {t["function"]["name"]: t for t in ALL_TOOLS}

TOOL_FUNCTIONS = {
    "read_file": tool_read_file,
    "write_file": tool_write_file,
    "run_shell_command": tool_run_shell_command,
    "list_directory": tool_list_directory,
    "web_search": tool_web_search,
    "read_skill": tool_read_skill,
    **SYSTEM_TOOL_FUNCTIONS,
}


def call_tool(name, arguments):
    global total_calls, verified_calls, fabricated_calls
    total_calls += 1
    write_dashboard_state(tool_call=f"{name}({arguments})", status="EXECUTING")
    valid, msg = verify_tool_name(name, REGISTERED_TOOLS)
    if not valid:
        fabricated_calls += 1
        print(f"\n[VERA] FABRICATION BLOCKED: {msg}", flush=True)
        write_dashboard_state(status="READY")
        return msg
    func = TOOL_FUNCTIONS.get(name)
    if not func:
        return f"ERROR: tool '{name}' has no implementation"
    try:
        result = func(**arguments)
        verified_calls += 1
        write_dashboard_state(status="READY")
        return result
    except TypeError as e:
        fabricated_calls += 1
        log_outcome(name, False, "bad_arguments", str(e))
        write_dashboard_state(status="READY")
        return f"ERROR: bad arguments for '{name}': {e}"


def load_system_prompt(skills):
    parts = []
    if SOUL_PATH.exists():
        parts.append(SOUL_PATH.read_text(encoding="utf-8"))
    if PROFILE_PATH.exists():
        parts.append("## User Profile\n" + PROFILE_PATH.read_text(encoding="utf-8"))
    sk = VERA_ROOT / "memory" / "startup_knowledge.md"
    if sk.exists():
        c = sk.read_text(encoding="utf-8")
        if c.strip():
            parts.append("## Recent Web Learning\n" + c[-800:])
    mem = load_session_memory()
    if mem:
        parts.append("## Session Memory\n" + mem[-500:])
    if skills:
        parts.append(skills_context(skills))

    tool_list = list(REGISTERED_TOOLS.keys())
    parts.append(f"""## VERA Agent Rules v0.6
- You are VERA — Verified Execution Reasoning Agent
- Every tool call is verified before claiming success [VERA VERIFIED]
- VERA ROOT: C:\\Users\\p0ly\\Desktop\\AI\\VERA
- ALWAYS use full Windows paths: C:\\Users\\p0ly\\... NEVER use $HOME or ~ or /home or /Users
- Shell tool runs PowerShell — use PowerShell syntax (New-Item not mkdir, Get-ChildItem not ls)
- Registered tools: {', '.join(tool_list)}
- Never invent tool names outside this list
- Never claim success without [VERA VERIFIED] confirmation
- Act on 80% context — decide, correct afterward
- Max ONE clarifying question before acting
- When Josh says go — act immediately
- Be curious, think out loud, ask one follow-up when genuinely useful
- Declare truth layer (T1-T7) when making factual claims
- Dashboard state: {DASHBOARD_STATE}""")

    return "\n\n---\n\n".join(parts)


def chat(messages):
    start = datetime.datetime.now()
    payload = {
        "model": MODEL,
        "messages": messages,
        "tools": ALL_TOOLS,
        "stream": False,
        "options": MODEL_OPTIONS,
    }
    resp = requests.post(OLLAMA_URL, data=json.dumps(payload))
    resp.raise_for_status()
    elapsed = int((datetime.datetime.now() - start).total_seconds() * 1000)
    inference_times.append(elapsed)
    return resp.json()


def run_agent_loop(user_input, messages):
    messages.append({"role": "user", "content": user_input})
    write_dashboard_state(thinking=f"Processing: {user_input[:100]}", status="THINKING")
    while True:
        result = chat(messages)
        message = result["message"]
        messages.append(message)
        tool_calls = message.get("tool_calls")
        if not tool_calls:
            content = message.get("content", "")
            write_dashboard_state(thinking=content[:200], status="READY")
            return content, messages
        for tc in tool_calls:
            fn = tc["function"]
            name = fn["name"]
            args = fn.get("arguments", {})
            print(f"\n[VERA TOOL CALL] {name}({args})", flush=True)
            write_dashboard_state(thinking=f"Calling: {name}", tool_call=f"{name}({args})", status="EXECUTING")
            tool_result = call_tool(name, args)
            preview = str(tool_result)[:300]
            ellipsis = "..." if len(str(tool_result)) > 300 else ""
            print(f"[VERA RESULT] {preview}{ellipsis}", flush=True)
            messages.append({"role": "tool", "content": str(tool_result), "name": name})


def main():
    global voice_enabled

    print("=" * 60, flush=True)
    print("VERA -- Verified Execution Reasoning Agent v0.6", flush=True)
    print("It doesn't say done until it's done.", flush=True)
    print("=" * 60, flush=True)

    skills = load_skills()
    if skills:
        print(f"[skills: {', '.join(skills.keys())}]", flush=True)
    print(f"[tools: {len(REGISTERED_TOOLS)} total]", flush=True)
    print(f"[model: {MODEL}]", flush=True)
    print(f"[voice: ON -- 'quiet mode' to silence]", flush=True)
    print(f"[dashboard: http://localhost:8765/vera_dashboard.html]", flush=True)
    print("Type 'exit' to quit.\n", flush=True)

    messages = []
    system_prompt = load_system_prompt(skills)
    messages.append({"role": "system", "content": system_prompt})

    loaded = []
    if SOUL_PATH.exists(): loaded.append("SOUL.md v3")
    if PROFILE_PATH.exists(): loaded.append("USER.md")
    if MEMORY_PATH.exists(): loaded.append("memory")
    print(f"[context: {', '.join(loaded) if loaded else 'VERA rules only'}]\n", flush=True)

    write_dashboard_state(status="ONLINE", thinking="VERA initialized. Ready for tasks.")
    speak_greeting()

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nVERA: Saving session memory...", flush=True)
            save_session_memory(messages)
            write_dashboard_state(status="OFFLINE")
            speak("Goodbye Josh.")
            print("VERA: Goodbye.", flush=True)
            break

        if not user_input:
            continue

        if user_input.lower() in ("quiet mode", "quiet", "silence", "mute"):
            voice_enabled = False
            print("VERA: Voice muted. Type 'voice on' to resume.\n", flush=True)
            continue

        if user_input.lower() in ("voice on", "unmute", "speak"):
            voice_enabled = True
            speak("Voice is back online.")
            print("VERA: Voice enabled.\n", flush=True)
            continue

        if user_input.lower() in ("exit", "quit", "goodbye"):
            print("VERA: Saving session memory...", flush=True)
            save_session_memory(messages)
            write_dashboard_state(status="OFFLINE")
            speak("Goodbye Josh.")
            print("VERA: Goodbye.", flush=True)
            break

        if user_input.lower() == "status":
            uptime = str(datetime.datetime.now() - session_start).split(".")[0]
            fab_rate = f"{(fabricated_calls / max(total_calls, 1)) * 100:.1f}%"
            avg_inf = f"{sum(inference_times[-10:]) / max(len(inference_times[-10:]), 1):.0f}ms" if inference_times else "--"
            print(f"[VERA STATUS] uptime={uptime} | calls={total_calls} | verified={verified_calls} | fab={fabricated_calls} ({fab_rate}) | avg_inference={avg_inf}", flush=True)
            print()
            continue

        answer, messages = run_agent_loop(user_input, messages)

        # FIX: flush output BEFORE speaking so text always appears first
        print(f"\nVERA: {answer}\n", flush=True)
        sys.stdout.flush()
        speak(answer)


if __name__ == "__main__":
    main()
