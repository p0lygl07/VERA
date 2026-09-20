#!/usr/bin/env python3
import json, os
from pathlib import Path
PREFS_PATH = Path(__file__).parent / "vera_prefs.json"
STATE_PATH = Path(__file__).parent / "voice_state.txt"
def load_sandbox_prefs():
    defaults = {"voice_enabled": False, "max_speaks_per_hour": 0, "fallback_mode": "silent_safe"}
    try:
        if not PREFS_PATH.exists():
            print("[MOCK VOICE WARNING] vera_prefs.json missing! Falling back to silent_safe.")
            return defaults
        with open(PREFS_PATH, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"[MOCK VOICE CRITICAL] Config corrupted ({e})! Graceful degradation active: silent_safe mode forced.")
        return defaults
def speak(text):
    prefs = load_sandbox_prefs()
    if not prefs.get("voice_enabled", False) or prefs.get("fallback_mode") == "silent_safe":
        print(f"[CONSOLE OUTPUT ONLY]: {text}"); return
    if prefs.get("skip_code_blocks") and ("```" in text or len(text.split()) > 30):
        print(f"[MOCK VOICE] Suppressed speech for long output/code. Printed to terminal."); return
    print(f"[MOCK TTS AUDIO] Sonia Voice: '{text}'")
if __name__ == "__main__":
    print("[MOCK VOICE] Running sandbox baseline test...")
    speak("System online. Testing defensive fallback layers.")