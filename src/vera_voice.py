#!/usr/bin/env python3
"""
VERA Voice Interface v3.3
Fixes:
- Strip punctuation from transcribed text before wake word matching
- When wake word detected with no inline command, go straight to listening
- Pre-loaded whisper, 1.5s burst, 90s playback timeout
"""

import sys
import asyncio
import tempfile
import os
import time
import json
import subprocess
import threading
import string
from pathlib import Path

VERA_ROOT  = Path(__file__).parent.parent
VOICE      = "en-GB-SoniaNeural"
RATE       = "+5%"
VOLUME     = "+0%"
WAKE_WORDS = ["hey vera", "hey vera", "vera", "ok vera"]
STT_MODEL  = "base"
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL      = "qwen3.5:9b"
PYTHON     = r"C:\Users\p0ly\AppData\Local\Programs\Python\Python311\python.exe"

_is_speaking = threading.Event()


def clean_text(text):
    """Strip punctuation and normalize whitespace for matching."""
    return text.translate(str.maketrans("", "", string.punctuation)).strip().lower()


async def _speak_async(text):
    import edge_tts
    communicate = edge_tts.Communicate(text, VOICE, rate=RATE, volume=VOLUME)
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        await communicate.save(tmp_path)
        file_size = os.path.getsize(tmp_path)
        duration_ms = max(1500, int(file_size / 6))
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
            timeout=90
        )
    except subprocess.TimeoutExpired:
        print("[VERA VOICE] Playback timeout -- audio may have played partially")
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
    import sounddevice as sd
    audio = sd.rec(
        int(duration * samplerate),
        samplerate=samplerate,
        channels=1,
        dtype="float32"
    )
    sd.wait()
    return audio, samplerate


def transcribe_audio(audio, samplerate=16000):
    import soundfile as sf
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        sf.write(tmp_path, audio, samplerate)
        model = load_whisper()
        segments, _ = model.transcribe(tmp_path, language="en", vad_filter=True)
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
    Listen in 1.5s bursts for wake word.
    Returns inline command string if command followed wake word,
    or None if wake word was spoken alone (caller should then listen).
    """
    print(f"[VERA VOICE] Waiting for wake word ({' / '.join(set(WAKE_WORDS))})...")
    while True:
        if _is_speaking.is_set():
            time.sleep(0.1)
            continue
        try:
            audio, sr = record_audio(duration=1.5)
            raw_text = transcribe_audio(audio, sr)
            if not raw_text:
                continue

            # Clean punctuation for matching
            cleaned = clean_text(raw_text)

            wake_detected = any(w in cleaned for w in WAKE_WORDS)
            if wake_detected:
                print(f"[VERA VOICE] Wake word detected: '{raw_text}'")

                # Try to extract inline command after wake word
                for w in WAKE_WORDS:
                    if w in cleaned:
                        parts = cleaned.split(w, 1)
                        if len(parts) > 1:
                            inline = parts[1].strip()
                            if inline and len(inline) > 1:
                                print(f"[VERA VOICE] Inline command: '{inline}'")
                                return inline

                # Wake word only -- no inline command
                return None

        except Exception as e:
            print(f"[VERA VOICE] Wake word error: {e}")
            time.sleep(0.5)


def ask_vera(command, messages, speak_response=True):
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
            clean = response.replace("**", "").replace("*", "").replace("#", "")
            clean = " ".join(clean.split())
            if len(clean) > 300:
                clean = clean[:280].rsplit(" ", 1)[0] + "."
            speak(clean)
        return response, messages
    except Exception as e:
        error_msg = "I'm having trouble reaching my reasoning engine."
        print(f"[VERA VOICE] Model error: {e}")
        if speak_response:
            speak(error_msg)
        return error_msg, messages


def voice_conversation_loop():
    soul_path = VERA_ROOT / "memory" / "SOUL.md"
    user_path = VERA_ROOT / "memory" / "USER.md"
    briefing_path = VERA_ROOT / "memory" / "latest_briefing.md"

    system_parts = []
    if soul_path.exists():
        system_parts.append(soul_path.read_text(encoding="utf-8"))
    if user_path.exists():
        system_parts.append(user_path.read_text(encoding="utf-8"))
    system_parts.append(
        "VOICE MODE ACTIVE.\n"
        "- Keep ALL responses to 1-3 short sentences maximum\n"
        "- No markdown, no bullet points, no lists, no headers\n"
        "- Natural British spoken English only\n"
        "- Be curious and decisive -- one follow-up question max\n"
        "- Make decisions, don't hedge endlessly\n"
        "- When uncertain, choose and explain in one sentence"
    )

    system_prompt = "\n\n".join(system_parts)
    messages = [{"role": "system", "content": system_prompt}]

    print("=" * 60)
    print("VERA Voice Mode v3.3")
    print(f"Wake words: hey vera / vera / ok vera")
    print("Say 'goodbye vera' to exit")
    print("=" * 60)

    # Pre-load whisper to eliminate first-use latency
    print("[VERA VOICE] Pre-loading speech model...")
    load_whisper()
    print("[VERA VOICE] Ready -- say 'Hey VERA' to begin.")

    # Proactive startup briefing
    if briefing_path.exists():
        briefing = briefing_path.read_text(encoding="utf-8")
        lines = [l.strip() for l in briefing.split("\n")
                if l.strip() and not l.startswith("#") and len(l.strip()) > 20]
        if lines:
            time.sleep(0.5)
            speak("I have a project update.")
            time.sleep(0.3)
            speak(lines[0][:200])
            time.sleep(0.5)

    consecutive_errors = 0

    while True:
        try:
            # Listen for wake word
            command_inline = listen_for_wake_word()

            if command_inline is None:
                # Wake word only -- listen for command
                speak("Yes?")
                command = listen(duration=7)
            else:
                # Command came with wake word
                command = command_inline

            # Skip if nothing heard
            if not command or len(clean_text(command)) < 2:
                # Don't say "I didn't catch that" for punctuation-only responses
                consecutive_errors += 1
                if consecutive_errors > 4:
                    speak("Having trouble hearing you. Check your microphone.")
                    consecutive_errors = 0
                continue

            consecutive_errors = 0
            command_clean = clean_text(command)

            # Exit commands
            if any(w in command_clean for w in ["goodbye", "bye vera",
                                                  "exit vera", "shutdown",
                                                  "stop vera", "power off"]):
                speak("Goodbye Josh. VERA standing by.")
                break

            # Quiet mode
            if any(w in command_clean for w in ["quiet mode", "be quiet",
                                                  "mute", "silence"]):
                speak("Going quiet.")
                while True:
                    cmd = listen(duration=3)
                    if any(w in clean_text(cmd) for w in ["voice on", "unmute",
                                                            "speak again"]):
                        speak("Voice restored.")
                        break
                continue

            # Process command through VERA
            response, messages = ask_vera(command, messages)

        except KeyboardInterrupt:
            print("\n[VERA VOICE] Voice mode interrupted.")
            speak("Voice mode interrupted.")
            break
        except Exception as e:
            print(f"[VERA VOICE] Loop error: {e}")
            consecutive_errors += 1
            time.sleep(1)


def main():
    if len(sys.argv) >= 2:
        cmd = sys.argv[1].lower()

        if cmd == "test":
            print("Testing VERA voice (en-GB-SoniaNeural)...")
            speak("Hello Josh. VERA voice is online and ready.")
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
                        if l.strip() and not l.startswith("#")
                        and len(l.strip()) > 20]
                if lines:
                    speak(lines[0][:250])
                else:
                    speak("No active alerts.")
            else:
                speak("No briefing available.")

        elif cmd == "wake":
            print("Testing wake word detection...")
            load_whisper()
            result = listen(duration=4)
            cleaned = clean_text(result)
            if any(w in cleaned for w in WAKE_WORDS):
                speak("Wake word confirmed. I heard you.")
            else:
                print(f"Heard: '{result}' -- no wake word detected")

        else:
            print("Commands: test | speak <text> | listen | alert | wake")
            print("No args = full voice conversation mode")
    else:
        voice_conversation_loop()


if __name__ == "__main__":
    main()
