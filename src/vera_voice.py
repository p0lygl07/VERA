#!/usr/bin/env python3
"""
VERA Voice Module v2
British female voice (en-GB-SoniaNeural).
Plays mp3 directly on Windows — no conversion needed.
faster-whisper for local speech-to-text.
Wake word: "Hey VERA"

Run with system Python:
  python src/vera_voice.py test
  python src/vera_voice.py speak "text"
  python src/vera_voice.py listen
  python src/vera_voice.py          # full voice mode
"""

import sys
import asyncio
import tempfile
import os
import time
import json
import subprocess
import threading
from pathlib import Path

VERA_ROOT  = Path(__file__).parent.parent
VOICE      = "en-GB-SoniaNeural"
RATE       = "+0%"
VOLUME     = "+0%"
WAKE_WORD  = "hey vera"
STT_MODEL  = "base"
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL      = "qwen3.5:9b"


# ── TTS ───────────────────────────────────────────────────────────────────────
async def _speak_async(text):
    import edge_tts

    communicate = edge_tts.Communicate(text, VOICE, rate=RATE, volume=VOLUME)

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        await communicate.save(tmp_path)
        file_size = os.path.getsize(tmp_path)

        # Play using Windows PowerShell wmplayer (silent background playback)
        ps_script = (
            f"Add-Type -AssemblyName presentationCore; "
            f"$mp = New-Object System.Windows.Media.MediaPlayer; "
            f"$mp.Open([uri]::new('{tmp_path}')); "
            f"$mp.Play(); "
            f"Start-Sleep -Milliseconds {max(2000, int(file_size / 4))}; "
            f"$mp.Stop(); $mp.Close()"
        )
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            timeout=30
        )
    except Exception as e:
        print(f"[VERA VOICE] Playback error: {e}")
    finally:
        time.sleep(0.3)
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass


def speak(text):
    """Speak text aloud using VERA's British female voice."""
    print(f"[VERA] {text}")
    try:
        asyncio.run(_speak_async(text))
    except Exception as e:
        print(f"[VERA VOICE] TTS error: {e}")


# ── STT ───────────────────────────────────────────────────────────────────────
_whisper_model = None


def load_whisper():
    global _whisper_model
    if _whisper_model is None:
        print(f"[VERA VOICE] Loading speech model ({STT_MODEL})...")
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel(STT_MODEL, device="cpu", compute_type="int8")
        print("[VERA VOICE] Speech recognition ready.")
    return _whisper_model


def listen(duration=5, samplerate=16000):
    """Record audio and transcribe."""
    try:
        import sounddevice as sd
        import soundfile as sf
        import numpy as np

        print(f"[VERA VOICE] Listening ({duration}s)...")
        audio = sd.rec(
            int(duration * samplerate),
            samplerate=samplerate,
            channels=1,
            dtype="float32"
        )
        sd.wait()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            sf.write(tmp_path, audio, samplerate)
            model = load_whisper()
            segments, _ = model.transcribe(tmp_path, language="en")
            text = " ".join(seg.text.strip() for seg in segments).strip()
            print(f"[VERA VOICE] Heard: '{text}'")
            return text.lower()
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    except ImportError:
        print("[VERA VOICE] sounddevice not available for STT")
        return ""
    except Exception as e:
        print(f"[VERA VOICE] STT error: {e}")
        return ""


# ── Wake word ─────────────────────────────────────────────────────────────────
def listen_for_wake_word(timeout=None):
    print(f"[VERA VOICE] Waiting for: '{WAKE_WORD}'")
    start = time.time()
    while True:
        if timeout and (time.time() - start) > timeout:
            return False
        text = listen(duration=3)
        if WAKE_WORD in text:
            print("[VERA VOICE] Wake word detected.")
            return True


# ── Voice conversation loop ───────────────────────────────────────────────────
def voice_conversation_loop():
    import requests

    # Build system prompt
    soul_path = VERA_ROOT / "memory" / "SOUL.md"
    user_path = VERA_ROOT / "memory" / "USER.md"
    briefing_path = VERA_ROOT / "memory" / "latest_briefing.md"

    system_parts = []
    if soul_path.exists():
        system_parts.append(soul_path.read_text(encoding="utf-8"))
    if user_path.exists():
        system_parts.append(user_path.read_text(encoding="utf-8"))
    system_parts.append(
        "IMPORTANT: You are speaking out loud. Keep ALL responses to 1-3 short sentences. "
        "No markdown, no bullet points, no numbered lists. "
        "Natural spoken British English only. Be direct and casual."
    )
    system_prompt = "\n\n".join(system_parts)
    messages = [{"role": "system", "content": system_prompt}]

    print("=" * 60)
    print("VERA Voice Mode")
    print(f"Say '{WAKE_WORD}' to speak to VERA")
    print("Say 'goodbye' to exit voice mode")
    print("=" * 60)

    # Proactive alert on startup
    if briefing_path.exists():
        briefing = briefing_path.read_text(encoding="utf-8")
        alert_lines = [l.strip() for l in briefing.split("\n")
                      if l.strip() and not l.startswith("#") and len(l.strip()) > 20]
        if alert_lines:
            speak("Hello Josh. I have a project update.")
            time.sleep(0.3)
            speak(alert_lines[0][:200])

    while True:
        detected = listen_for_wake_word(timeout=300)
        if not detected:
            print("[VERA VOICE] Timeout — exiting voice mode.")
            break

        speak("Yes?")
        command = listen(duration=6)

        if not command:
            speak("I didn't catch that.")
            continue

        if any(w in command for w in ["goodbye", "bye vera", "exit", "stop listening"]):
            speak("Goodbye Josh.")
            break

        messages.append({"role": "user", "content": command})

        try:
            payload = {
                "model": MODEL,
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.2, "num_ctx": 4096},
            }
            resp = requests.post(OLLAMA_URL, data=json.dumps(payload), timeout=30)
            resp.raise_for_status()
            response = resp.json()["message"]["content"]
            messages.append({"role": "assistant", "content": response})
            speak(response)
        except Exception as e:
            print(f"[VERA VOICE] Model error: {e}")
            speak("I'm having trouble reaching my reasoning engine.")


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    if len(sys.argv) >= 2:
        cmd = sys.argv[1].lower()

        if cmd == "test":
            print("Testing VERA voice (en-GB-SoniaNeural)...")
            speak("Hello Josh. VERA voice is online. I am ready.")
            print("Voice test complete.")

        elif cmd == "speak" and len(sys.argv) >= 3:
            speak(" ".join(sys.argv[2:]))

        elif cmd == "listen":
            text = listen(duration=5)
            print(f"Transcribed: '{text}'")

        elif cmd == "wake":
            if listen_for_wake_word(timeout=30):
                speak("Yes Josh?")
            else:
                print("No wake word detected.")

        elif cmd == "alert":
            # Speak the latest briefing
            briefing_path = VERA_ROOT / "memory" / "latest_briefing.md"
            if briefing_path.exists():
                content = briefing_path.read_text(encoding="utf-8")
                lines = [l.strip() for l in content.split("\n")
                        if l.strip() and not l.startswith("#")]
                for line in lines[:3]:
                    speak(line)
                    time.sleep(0.3)
            else:
                speak("No alerts at this time.")
        else:
            print("Commands: test | speak <text> | listen | wake | alert")
    else:
        voice_conversation_loop()


if __name__ == "__main__":
    main()
