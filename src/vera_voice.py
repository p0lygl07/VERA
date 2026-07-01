#!/usr/bin/env python3
"""
VERA Voice Interface v3
Full duplex voice conversation with VERA.
Wake word: "Hey VERA"
Voice: en-GB-SoniaNeural (British female)
STT: faster-whisper (local, private)

Usage:
  python src/vera_voice.py              # full voice conversation mode
  python src/vera_voice.py test         # test TTS
  python src/vera_voice.py speak <text> # speak one phrase
  python src/vera_voice.py listen       # test microphone
  python src/vera_voice.py alert        # speak latest briefing
"""

import sys
import asyncio
import tempfile
import os
import time
import json
import subprocess
import threading
import queue
from pathlib import Path

VERA_ROOT  = Path(__file__).parent.parent
VOICE      = "en-GB-SoniaNeural"
RATE       = "+5%"
VOLUME     = "+0%"
WAKE_WORDS = ["hey vera", "hey, vera", "vera", "ok vera"]
STT_MODEL  = "base"
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL      = "qwen3.5:9b"
PYTHON     = r"C:\Users\p0ly\AppData\Local\Programs\Python\Python311\python.exe"

# Shared speaking state — prevents listening while speaking
_is_speaking = threading.Event()


# ── TTS ───────────────────────────────────────────────────────────────────────
async def _speak_async(text):
    import edge_tts
    communicate = edge_tts.Communicate(text, VOICE, rate=RATE, volume=VOLUME)
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        await communicate.save(tmp_path)
        file_size = os.path.getsize(tmp_path)
        duration_ms = max(1500, int(file_size / 4))
        ps_script = (
            f"Add-Type -AssemblyName presentationCore; "
            f"$mp = New-Object System.Windows.Media.MediaPlayer; "
            f"$mp.Open([uri]::new('{tmp_path}')); "
            f"$mp.Play(); "
            f"Start-Sleep -Milliseconds {duration_ms}; "
            f"$mp.Stop(); $mp.Close()"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            timeout=30
        )
    except Exception as e:
        print(f"[VERA VOICE] Playback error: {e}")
    finally:
        time.sleep(0.2)
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass


def speak(text):
    """Speak text aloud. Blocks until complete."""
    if not text or not text.strip():
        return
    _is_speaking.set()
    print(f"[VERA] {text}")
    try:
        asyncio.run(_speak_async(text))
    except Exception as e:
        print(f"[VERA VOICE] TTS error: {e}")
    finally:
        _is_speaking.clear()


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


def record_audio(duration=5, samplerate=16000):
    """Record audio from microphone."""
    import sounddevice as sd
    import soundfile as sf
    import numpy as np

    audio = sd.rec(
        int(duration * samplerate),
        samplerate=samplerate,
        channels=1,
        dtype="float32"
    )
    sd.wait()
    return audio, samplerate


def transcribe_audio(audio, samplerate=16000):
    """Transcribe audio using faster-whisper."""
    import soundfile as sf

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        sf.write(tmp_path, audio, samplerate)
        model = load_whisper()
        segments, info = model.transcribe(tmp_path, language="en", vad_filter=True)
        text = " ".join(seg.text.strip() for seg in segments).strip()
        return text.lower()
    except Exception as e:
        print(f"[VERA VOICE] STT error: {e}")
        return ""
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def listen(duration=5):
    """Record and transcribe speech."""
    try:
        print(f"[VERA VOICE] Listening ({duration}s)...")
        audio, sr = record_audio(duration)
        text = transcribe_audio(audio, sr)
        if text:
            print(f"[VERA VOICE] Heard: '{text}'")
        return text
    except ImportError:
        print("[VERA VOICE] Audio libraries not available")
        return ""
    except Exception as e:
        print(f"[VERA VOICE] Listen error: {e}")
        return ""


def listen_for_wake_word():
    """
    Continuously listen in short bursts for wake word.
    Returns the full utterance after the wake word if detected.
    """
    import sounddevice as sd

    print(f"[VERA VOICE] Waiting for wake word ({' / '.join(WAKE_WORDS)})...")

    while True:
        # Don't listen while speaking
        if _is_speaking.is_set():
            time.sleep(0.1)
            continue

        try:
            # Short burst listening for wake word
            audio, sr = record_audio(duration=2)
            text = transcribe_audio(audio, sr)

            if not text:
                continue

            # Check for wake word
            wake_detected = any(w in text for w in WAKE_WORDS)
            if wake_detected:
                print(f"[VERA VOICE] Wake word detected in: '{text}'")

                # Extract any command that followed the wake word
                command_after = text
                for w in WAKE_WORDS:
                    if w in command_after:
                        parts = command_after.split(w, 1)
                        if len(parts) > 1 and parts[1].strip():
                            command_after = parts[1].strip()
                            return command_after  # command was in same utterance

                # Wake word only — listen for the command
                return None  # Signal: heard wake word, need command

        except Exception as e:
            print(f"[VERA VOICE] Wake word listen error: {e}")
            time.sleep(0.5)


# ── VERA reasoning ────────────────────────────────────────────────────────────
def ask_vera(command, messages, speak_response=True):
    """Send a command to VERA's reasoning engine and get a response."""
    import requests

    messages.append({"role": "user", "content": command})
    try:
        payload = {
            "model": MODEL,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.3, "num_ctx": 4096},
        }
        resp = requests.post(OLLAMA_URL, data=json.dumps(payload), timeout=45)
        resp.raise_for_status()
        response = resp.json()["message"]["content"]
        messages.append({"role": "assistant", "content": response})

        if speak_response:
            # Truncate for speech — speak first 2-3 sentences
            sentences = response.replace("**", "").replace("*", "").replace("#", "")
            # Remove markdown
            clean = " ".join(sentences.split())
            # Take first 300 chars max for voice
            if len(clean) > 300:
                truncated = clean[:280].rsplit(" ", 1)[0]
                speak(truncated + ".")
            else:
                speak(clean)

        return response, messages
    except Exception as e:
        error_msg = "I'm having trouble reaching my reasoning engine."
        print(f"[VERA VOICE] Model error: {e}")
        if speak_response:
            speak(error_msg)
        return error_msg, messages


# ── Voice conversation loop ───────────────────────────────────────────────────
def voice_conversation_loop():
    """Full JARVIS-style voice conversation."""
    # Build system context
    soul_path = VERA_ROOT / "memory" / "SOUL.md"
    user_path = VERA_ROOT / "memory" / "USER.md"
    briefing_path = VERA_ROOT / "memory" / "latest_briefing.md"

    system_parts = []
    if soul_path.exists():
        system_parts.append(soul_path.read_text(encoding="utf-8"))
    if user_path.exists():
        system_parts.append(user_path.read_text(encoding="utf-8"))
    system_parts.append(
        "VOICE MODE ACTIVE. Critical rules for voice:\n"
        "- Keep ALL responses to 1-3 short sentences maximum\n"
        "- No markdown, no bullet points, no lists, no headers\n"
        "- Natural British spoken English only\n"
        "- Be curious and decisive — ask one follow-up question when relevant\n"
        "- If you need more info, ask directly in one sentence\n"
        "- When uncertain, make a decision and state your reasoning briefly"
    )

    system_prompt = "\n\n".join(system_parts)
    messages = [{"role": "system", "content": system_prompt}]

    print("=" * 60)
    print("VERA Voice Mode v3")
    print(f"Wake words: {', '.join(WAKE_WORDS)}")
    print("Say 'goodbye vera' to exit")
    print("=" * 60)

    # Proactive startup briefing
    if briefing_path.exists():
        briefing = briefing_path.read_text(encoding="utf-8")
        lines = [l.strip() for l in briefing.split("\n")
                if l.strip() and not l.startswith("#") and len(l.strip()) > 20]
        if lines:
            time.sleep(0.5)
            speak("I have a project update for you.")
            time.sleep(0.3)
            brief_text = lines[0][:200]
            speak(brief_text)
            time.sleep(0.5)

    consecutive_errors = 0

    while True:
        try:
            # Listen for wake word
            command_inline = listen_for_wake_word()

            if command_inline is None:
                # Wake word heard, need to listen for command
                speak("Yes?")
                command = listen(duration=7)
            else:
                # Command was in the same utterance as wake word
                command = command_inline
                print(f"[VERA VOICE] Inline command: '{command}'")

            if not command or len(command.strip()) < 2:
                speak("I didn't catch that.")
                consecutive_errors += 1
                if consecutive_errors > 3:
                    speak("Having trouble hearing you. Check your microphone.")
                    consecutive_errors = 0
                continue

            consecutive_errors = 0

            # Exit commands
            if any(w in command for w in ["goodbye", "bye vera", "exit vera",
                                           "shutdown", "stop vera", "power off"]):
                speak("Goodbye Josh. VERA standing by.")
                break

            # Quiet mode
            if any(w in command for w in ["quiet mode", "be quiet", "mute", "silence"]):
                speak("Going quiet.")
                # Keep listening but stop speaking
                while True:
                    cmd = listen(duration=3)
                    if any(w in cmd for w in ["voice on", "unmute", "speak again"]):
                        speak("Voice restored.")
                        break
                continue

            # Process command
            response, messages = ask_vera(command, messages)

        except KeyboardInterrupt:
            print("\n[VERA VOICE] Voice mode interrupted.")
            speak("Voice mode interrupted.")
            break
        except Exception as e:
            print(f"[VERA VOICE] Loop error: {e}")
            consecutive_errors += 1
            time.sleep(1)


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    if len(sys.argv) >= 2:
        cmd = sys.argv[1].lower()

        if cmd == "test":
            print("Testing VERA voice (en-GB-SoniaNeural)...")
            speak("Hello Josh. VERA voice is online. I am ready and listening.")
            print("Voice test complete.")

        elif cmd == "speak" and len(sys.argv) >= 3:
            speak(" ".join(sys.argv[2:]))

        elif cmd == "listen":
            print("Speak now...")
            text = listen(duration=6)
            print(f"Transcribed: '{text}'")

        elif cmd == "alert":
            briefing_path = VERA_ROOT / "memory" / "latest_briefing.md"
            if briefing_path.exists():
                content = briefing_path.read_text(encoding="utf-8")
                lines = [l.strip() for l in content.split("\n")
                        if l.strip() and not l.startswith("#") and len(l.strip()) > 20]
                if lines:
                    speak(lines[0][:250])
                else:
                    speak("No active alerts.")
            else:
                speak("No briefing available.")

        elif cmd == "wake":
            print("Testing wake word detection (30s timeout)...")
            load_whisper()
            result = listen(duration=4)
            if any(w in result for w in WAKE_WORDS):
                speak("Wake word confirmed. I heard you.")
            else:
                print(f"Heard: '{result}' — no wake word detected")

        else:
            print("Commands: test | speak <text> | listen | alert | wake")
            print("Or run with no args for full voice conversation mode")
    else:
        voice_conversation_loop()


if __name__ == "__main__":
    main()
