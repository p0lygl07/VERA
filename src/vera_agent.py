#!/usr/bin/env python3
"""
Hermes Agent Harness — local Ollama tool-calling loop.

Tools provided: read_file, write_file, run_shell_command (confirm-before-execute).
"""

import json
import os
import subprocess
import requests

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "hermes3:8b"
PROFILE_PATH = "profile.md"

MODEL_OPTIONS = {
    "temperature": 0.2,
    "num_ctx": 8192,
}


def load_system_prompt():
    if os.path.exists(PROFILE_PATH):
        with open(PROFILE_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return None

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
            "description": "Write (overwrite) content to a file on disk.",
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
            "description": "Run a shell command and return its output. Requires user confirmation before execution.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to run."}
                },
                "required": ["command"],
            },
        },
    },
]


def tool_read_file(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as e:
        return f"ERROR reading file: {e}"


def tool_write_file(path, content):
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"OK: wrote {len(content)} characters to {path}"
    except Exception as e:
        return f"ERROR writing file: {e}"


def tool_run_shell_command(command):
    print(f"\n[CONFIRM] Hermes wants to run this shell command:\n  {command}")
    answer = input("Allow? [y/N]: ").strip().lower()
    if answer != "y":
        return "User declined to run this command."
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=60
        )
        output = result.stdout + result.stderr
        return output.strip() or "(command produced no output)"
    except subprocess.TimeoutExpired:
        return "ERROR: command timed out after 60 seconds."
    except Exception as e:
        return f"ERROR running command: {e}"


TOOL_FUNCTIONS = {
    "read_file": tool_read_file,
    "write_file": tool_write_file,
    "run_shell_command": tool_run_shell_command,
}


def call_tool(name, arguments):
    func = TOOL_FUNCTIONS.get(name)
    if not func:
        return f"ERROR: unknown tool '{name}'"
    try:
        return func(**arguments)
    except TypeError as e:
        return f"ERROR: bad arguments for '{name}': {e}"


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


def run_agent_loop(user_input, messages):
    messages.append({"role": "user", "content": user_input})

    while True:
        result = chat(messages)
        message = result["message"]
        messages.append(message)

        tool_calls = message.get("tool_calls")
        if not tool_calls:
            # Final answer, no more tool calls
            return message.get("content", ""), messages

        for tc in tool_calls:
            fn = tc["function"]
            name = fn["name"]
            args = fn.get("arguments", {})
            print(f"\n[TOOL CALL] {name}({args})")
            tool_result = call_tool(name, args)
            print(f"[TOOL RESULT] {tool_result[:300]}{'...' if len(str(tool_result)) > 300 else ''}")

            messages.append(
                {
                    "role": "tool",
                    "content": str(tool_result),
                    "name": name,
                }
            )


def main():
    print("Hermes Agent Harness — type 'exit' to quit.\n")
    messages = []

    system_prompt = load_system_prompt()
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
        print(f"[loaded {PROFILE_PATH} as system prompt]")
    else:
        print(f"[no {PROFILE_PATH} found — running without profile context]")

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if user_input.lower() in ("exit", "quit"):
            break
        if not user_input:
            continue

        answer, messages = run_agent_loop(user_input, messages)
        print(f"\nHermes: {answer}")


if __name__ == "__main__":
    main()
