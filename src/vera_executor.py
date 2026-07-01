#!/usr/bin/env python3
"""
VERA Autonomous Executor v1.0
Confidence-based action system with tiered autonomy.

Tiers:
  HIGH   (>0.85) : act immediately, log after
  MEDIUM (0.50+) : announce then act
  LOW    (<0.50) : ask before acting
  ADMIN  (any)   : always ask — irreversible or system-critical actions
"""

import os
import sys
import json
import subprocess
import datetime
import pyautogui
import time
from pathlib import Path

VERA_ROOT = Path(__file__).parent.parent
LOG_PATH  = VERA_ROOT / "logs" / "execution_log.md"
ACTION_LOG = VERA_ROOT / "logs" / "action_log.md"

# ── Confidence thresholds ─────────────────────────────────────────────────────
HIGH_CONFIDENCE   = 0.85
MEDIUM_CONFIDENCE = 0.50

# ── Admin-tier actions (always require confirmation) ──────────────────────────
ADMIN_ACTIONS = {
    "delete_file", "delete_directory", "format_drive",
    "install_software", "uninstall_software",
    "modify_registry", "change_system_settings",
    "modify_hosts_file", "change_network_config",
    "run_as_admin", "elevate_privileges",
    "modify_firewall", "disable_antivirus",
    "send_email", "post_to_social", "submit_form",
    "make_purchase", "transfer_funds",
}

# ── Action categories with base confidence ────────────────────────────────────
ACTION_PROFILES = {
    # File operations
    "read_file":         {"base_confidence": 0.95, "admin": False, "reversible": True},
    "write_file":        {"base_confidence": 0.90, "admin": False, "reversible": True},
    "create_directory":  {"base_confidence": 0.90, "admin": False, "reversible": True},
    "copy_file":         {"base_confidence": 0.88, "admin": False, "reversible": True},
    "move_file":         {"base_confidence": 0.80, "admin": False, "reversible": False},
    "delete_file":       {"base_confidence": 0.70, "admin": True,  "reversible": False},

    # Applications
    "open_application":  {"base_confidence": 0.92, "admin": False, "reversible": True},
    "close_application": {"base_confidence": 0.85, "admin": False, "reversible": True},
    "focus_window":      {"base_confidence": 0.95, "admin": False, "reversible": True},
    "take_screenshot":   {"base_confidence": 0.98, "admin": False, "reversible": True},

    # UI automation
    "click":             {"base_confidence": 0.80, "admin": False, "reversible": False},
    "type_text":         {"base_confidence": 0.82, "admin": False, "reversible": False},
    "key_press":         {"base_confidence": 0.85, "admin": False, "reversible": False},
    "scroll":            {"base_confidence": 0.90, "admin": False, "reversible": True},
    "drag_drop":         {"base_confidence": 0.70, "admin": False, "reversible": False},

    # Shell
    "run_command":       {"base_confidence": 0.78, "admin": False, "reversible": False},
    "run_admin_command": {"base_confidence": 0.40, "admin": True,  "reversible": False},

    # System
    "get_system_info":   {"base_confidence": 0.98, "admin": False, "reversible": True},
    "list_processes":    {"base_confidence": 0.98, "admin": False, "reversible": True},
    "kill_process":      {"base_confidence": 0.60, "admin": True,  "reversible": False},
    "install_software":  {"base_confidence": 0.30, "admin": True,  "reversible": False},

    # Web
    "open_url":          {"base_confidence": 0.90, "admin": False, "reversible": True},
    "web_search":        {"base_confidence": 0.95, "admin": False, "reversible": True},
    "download_file":     {"base_confidence": 0.72, "admin": False, "reversible": True},

    # Clipboard
    "read_clipboard":    {"base_confidence": 0.98, "admin": False, "reversible": True},
    "write_clipboard":   {"base_confidence": 0.92, "admin": False, "reversible": True},
}


def log_action(action, confidence, tier, outcome, notes=""):
    """Log every action VERA takes to the action log."""
    ACTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = (f"| {timestamp} | {action} | {confidence:.0%} | {tier} "
           f"| {outcome} | {notes} |\n")
    try:
        with open(ACTION_LOG, "a", encoding="utf-8") as f:
            f.write(row)
    except Exception:
        pass


def get_confidence(action_name, context_factors=None):
    """
    Calculate confidence for an action.
    context_factors: dict of modifiers e.g. {"target_verified": 0.1, "reversible": 0.05}
    """
    profile = ACTION_PROFILES.get(action_name, {"base_confidence": 0.50, "admin": False})
    confidence = profile["base_confidence"]

    if context_factors:
        for factor, modifier in context_factors.items():
            confidence += modifier

    return min(1.0, max(0.0, confidence))


def decide_tier(action_name, confidence, context_factors=None):
    """Determine execution tier for an action."""
    profile = ACTION_PROFILES.get(action_name, {"admin": False})

    # Admin actions always require confirmation
    if profile.get("admin") or action_name in ADMIN_ACTIONS:
        return "ADMIN"

    if confidence >= HIGH_CONFIDENCE:
        return "HIGH"
    elif confidence >= MEDIUM_CONFIDENCE:
        return "MEDIUM"
    else:
        return "LOW"


def request_confirmation(action_name, details, confidence, reason=""):
    """Ask user for confirmation on low-confidence or admin actions."""
    print(f"\n[VERA EXECUTOR] Confirmation required")
    print(f"  Action:     {action_name}")
    print(f"  Details:    {details}")
    print(f"  Confidence: {confidence:.0%}")
    if reason:
        print(f"  Reason:     {reason}")
    print(f"  [This action {'is irreversible' if ACTION_PROFILES.get(action_name, {}).get('reversible') is False else 'may have side effects'}]")

    answer = input("  Proceed? [y/N]: ").strip().lower()
    return answer == "y"


def execute(action_name, action_fn, details="", context_factors=None, speak_fn=None):
    """
    Main execution dispatcher.
    Determines tier, handles confirmation if needed, executes, logs.
    """
    confidence = get_confidence(action_name, context_factors)
    tier = decide_tier(action_name, confidence)

    timestamp = datetime.datetime.now().strftime("%H:%M:%S")

    if tier == "ADMIN":
        if speak_fn:
            speak_fn(f"I need your confirmation for this action: {action_name.replace('_', ' ')}.")
        approved = request_confirmation(action_name, details, confidence,
                                       "Admin-tier action requires explicit approval")
        if not approved:
            log_action(action_name, confidence, tier, "DECLINED", details)
            return None, "Action declined by user."

    elif tier == "HIGH":
        # Act immediately — no announcement needed
        pass

    elif tier == "MEDIUM":
        # Announce then act
        announcement = f"Running {action_name.replace('_', ' ')}."
        print(f"[VERA EXECUTOR] {timestamp} | {tier} | {announcement}")
        if speak_fn:
            speak_fn(announcement)

    elif tier == "LOW":
        if speak_fn:
            speak_fn(f"I'm not confident about {action_name.replace('_', ' ')}. Shall I proceed?")
        approved = request_confirmation(action_name, details, confidence,
                                       f"Low confidence: {confidence:.0%}")
        if not approved:
            log_action(action_name, confidence, tier, "DECLINED", details)
            return None, "Action declined by user."

    # Execute
    try:
        result = action_fn()
        log_action(action_name, confidence, tier, "SUCCESS", details[:100])
        return result, "OK"
    except Exception as e:
        log_action(action_name, confidence, tier, f"FAILED: {e}", details[:100])
        return None, f"ERROR: {e}"


# ── UI Automation actions ─────────────────────────────────────────────────────
def action_screenshot(save_path=None):
    """Take a screenshot and optionally save it."""
    screenshot = pyautogui.screenshot()
    if save_path:
        screenshot.save(save_path)
        return str(save_path)
    # Return as temp file
    import tempfile
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    screenshot.save(tmp.name)
    return tmp.name


def action_click(x, y, button="left", clicks=1):
    """Click at screen coordinates."""
    pyautogui.click(x, y, button=button, clicks=clicks)
    return f"Clicked ({x},{y})"


def action_type_text(text, interval=0.02):
    """Type text at current cursor position."""
    pyautogui.write(text, interval=interval)
    return f"Typed: {text[:50]}"


def action_key_press(keys):
    """Press key combination e.g. 'ctrl+c', 'alt+tab'."""
    pyautogui.hotkey(*keys.split("+"))
    return f"Pressed: {keys}"


def action_open_url(url):
    """Open URL in default browser."""
    subprocess.Popen(["start", url], shell=True)
    return f"Opened: {url}"


def action_open_app(app_name):
    """Open application by name."""
    app_map = {
        "chrome": "chrome", "browser": "chrome",
        "firefox": "firefox", "notepad": "notepad",
        "terminal": "wt", "powershell": "powershell",
        "explorer": "explorer", "obsidian": "obsidian",
        "vscode": "code", "burpsuite": "burpsuite",
        "calculator": "calc", "paint": "mspaint",
        "task manager": "taskmgr", "settings": "ms-settings:",
    }
    exe = app_map.get(app_name.lower(), app_name)
    subprocess.Popen(exe, shell=True)
    return f"Opened: {app_name}"


def action_run_command(command):
    """Run a shell command and return output."""
    result = subprocess.run(
        command, shell=True, capture_output=True,
        text=True, timeout=60
    )
    output = result.stdout + result.stderr
    return output.strip() or "(no output)"


def action_get_screen_text():
    """OCR the current screen to get text content."""
    try:
        import pytesseract
        from PIL import Image
        screenshot = pyautogui.screenshot()
        text = pytesseract.image_to_string(screenshot)
        return text.strip()
    except ImportError:
        return "OCR not available — install pytesseract and Tesseract"


# ── Multimodal: vision ────────────────────────────────────────────────────────
def analyze_screenshot_with_vera(image_path, question, ollama_url, model):
    """
    Send a screenshot to VERA's vision model for analysis.
    Requires a vision-capable model (qwen3.5:9b supports vision).
    """
    import base64
    import requests

    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")

    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url",
                 "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                {"type": "text", "text": question}
            ]
        }],
        "stream": False,
    }

    try:
        resp = requests.post(f"{ollama_url}/api/chat",
                            data=json.dumps(payload), timeout=60)
        resp.raise_for_status()
        return resp.json()["message"]["content"]
    except Exception as e:
        return f"Vision analysis error: {e}"


# ── Tool wrappers for VERA agent ──────────────────────────────────────────────
EXECUTOR_TOOLS = [
    {"type": "function", "function": {
        "name": "take_screenshot",
        "description": "Take a screenshot of the current screen. Returns image path.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "click_screen",
        "description": "Click at screen coordinates.",
        "parameters": {"type": "object", "properties": {
            "x": {"type": "integer"},
            "y": {"type": "integer"},
            "button": {"type": "string", "default": "left"},
        }, "required": ["x", "y"]},
    }},
    {"type": "function", "function": {
        "name": "type_text",
        "description": "Type text at the current cursor position.",
        "parameters": {"type": "object", "properties": {
            "text": {"type": "string"},
        }, "required": ["text"]},
    }},
    {"type": "function", "function": {
        "name": "press_keys",
        "description": "Press a key or key combination e.g. 'ctrl+c', 'alt+tab', 'enter'.",
        "parameters": {"type": "object", "properties": {
            "keys": {"type": "string"},
        }, "required": ["keys"]},
    }},
    {"type": "function", "function": {
        "name": "open_url",
        "description": "Open a URL in the default browser.",
        "parameters": {"type": "object", "properties": {
            "url": {"type": "string"},
        }, "required": ["url"]},
    }},
    {"type": "function", "function": {
        "name": "open_app",
        "description": "Open an application by name (chrome, notepad, terminal, vscode, etc).",
        "parameters": {"type": "object", "properties": {
            "app_name": {"type": "string"},
        }, "required": ["app_name"]},
    }},
    {"type": "function", "function": {
        "name": "run_command_auto",
        "description": "Run a shell command autonomously based on confidence level.",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string"},
            "confidence": {"type": "number", "description": "VERA's confidence 0.0-1.0"},
        }, "required": ["command", "confidence"]},
    }},
    {"type": "function", "function": {
        "name": "read_screen",
        "description": "Take a screenshot and analyze what's on screen using vision.",
        "parameters": {"type": "object", "properties": {
            "question": {"type": "string",
                        "description": "What to look for or analyze on screen"},
        }, "required": ["question"]},
    }},
]


def make_executor_functions(speak_fn=None, ollama_url="http://localhost:11434",
                             model="qwen3.5:9b"):
    """Create tool function dict with speak_fn and model injected."""

    def tool_take_screenshot(**kwargs):
        result, msg = execute(
            "take_screenshot",
            lambda: action_screenshot(
                VERA_ROOT / "logs" / f"screen_{datetime.datetime.now().strftime('%H%M%S')}.png"
            ),
            "Taking screenshot",
            speak_fn=speak_fn
        )
        return str(result) if result else msg

    def tool_click_screen(x, y, button="left", **kwargs):
        result, msg = execute(
            "click",
            lambda: action_click(x, y, button),
            f"Click at ({x},{y})",
            speak_fn=speak_fn
        )
        return result or msg

    def tool_type_text(text, **kwargs):
        result, msg = execute(
            "type_text",
            lambda: action_type_text(text),
            f"Type: {text[:30]}",
            speak_fn=speak_fn
        )
        return result or msg

    def tool_press_keys(keys, **kwargs):
        result, msg = execute(
            "key_press",
            lambda: action_key_press(keys),
            f"Keys: {keys}",
            speak_fn=speak_fn
        )
        return result or msg

    def tool_open_url(url, **kwargs):
        result, msg = execute(
            "open_url",
            lambda: action_open_url(url),
            f"URL: {url[:50]}",
            speak_fn=speak_fn
        )
        return result or msg

    def tool_open_app(app_name, **kwargs):
        result, msg = execute(
            "open_application",
            lambda: action_open_app(app_name),
            f"App: {app_name}",
            speak_fn=speak_fn
        )
        return result or msg

    def tool_run_command_auto(command, confidence=0.75, **kwargs):
        tier = decide_tier("run_command", float(confidence))
        result, msg = execute(
            "run_command",
            lambda: action_run_command(command),
            f"Command: {command[:60]}",
            context_factors={"vera_confidence": float(confidence) - 0.78},
            speak_fn=speak_fn
        )
        return result or msg

    def tool_read_screen(question, **kwargs):
        img_path = action_screenshot()
        analysis = analyze_screenshot_with_vera(img_path, question, ollama_url, model)
        try:
            os.unlink(img_path)
        except Exception:
            pass
        log_action("read_screen", 0.95, "HIGH", "SUCCESS", question[:50])
        return analysis

    return {
        "take_screenshot": tool_take_screenshot,
        "click_screen": tool_click_screen,
        "type_text": tool_type_text,
        "press_keys": tool_press_keys,
        "open_url": tool_open_url,
        "open_app": tool_open_app,
        "run_command_auto": tool_run_command_auto,
        "read_screen": tool_read_screen,
    }


if __name__ == "__main__":
    print("VERA Autonomous Executor -- self test")
    print("\nAction profiles loaded:", len(ACTION_PROFILES))
    print("Admin-tier actions:", len(ADMIN_ACTIONS))

    # Test confidence calculation
    tests = ["read_file", "delete_file", "click", "take_screenshot", "run_admin_command"]
    print("\nConfidence test:")
    for action in tests:
        conf = get_confidence(action)
        tier = decide_tier(action, conf)
        print(f"  {action:<25} confidence={conf:.0%}  tier={tier}")

    print("\nInitializing action log...")
    log_action("self_test", 1.0, "HIGH", "SUCCESS", "executor self-test complete")
    print(f"Action log: {ACTION_LOG}")
