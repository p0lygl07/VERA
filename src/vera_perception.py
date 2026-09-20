#!/usr/bin/env python3
"""
VERA Perception Engine v1.0
Passive ambient intelligence -- VERA sees, hears, and learns continuously.

Four perception channels:
  1. MIC LOOP    -- listens continuously, transcribes with faster-whisper,
                    logs speech context to memory
  2. CAMERA FEED -- captures webcam frames periodically, analyzes with
                    vision model, logs observations to memory
  3. SCREEN MONITOR -- captures screen, extracts text/context via vision,
                       writes learning entries to memory
  4. ACTONE LOOP -- listens for authenticated command/status tones from
                    the Kyger suit or a droid (see vera_actone_devices.py
                    for the shared device-key registry), logs decoded
                    tokens the same way the other channels log observations

All channels write to:
  memory/perception_log.md   -- raw observations
  memory/learned_knowledge.md -- summarized learning
  logs/dashboard_state.json  -- live state for dashboard

Run: python src/vera_perception.py
Or:  python src/vera_perception.py --mic --screen --camera --actone
"""

import argparse
import base64
import datetime
import io
import json
import os
import sys
import threading
import time
from pathlib import Path

import requests

# vera_actone_devices.py / vera_actone_secure.py / libactone_secure.dll all
# live at the project root (same folder as vera.bat), one level up from
# this file's own src/ directory -- same resolution trick vera_agent.py
# uses, so it works regardless of what VERA_ROOT below is set to.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

VERA_ROOT      = Path(__file__).resolve().parent.parent
try:
    # Use the same single source of truth vera_agent.py already relies on,
    # instead of this file's own separately-hardcoded (and stale) path.
    from vera_paths import VERA_ROOT
except ImportError:
    pass  # fall back to the path derived above if vera_paths.py isn't found

MEMORY_PATH    = VERA_ROOT / "memory"
LOGS_PATH      = VERA_ROOT / "logs"
PERCEPTION_LOG = MEMORY_PATH / "perception_log.md"
LEARNING_LOG   = MEMORY_PATH / "learned_knowledge.md"
DASHBOARD_STATE= LOGS_PATH / "dashboard_state.json"
OLLAMA_URL     = "http://localhost:11434/api/chat"
MODEL          = "qwen3.5:9b"
PYTHON         = r"C:\Users\P01yG107\AppData\Local\Programs\Python\Python311\python.exe"

# Intervals (seconds)
MIC_SILENCE_THRESHOLD = 0.5    # energy threshold for speech detection
SCREEN_INTERVAL       = 45     # analyze screen every 45 seconds
CAMERA_INTERVAL       = 60     # analyze camera every 60 seconds
LOG_INTERVAL          = 30     # flush perception log every 30 seconds

# State
_running = True
_perception_buffer = []
_buffer_lock = threading.Lock()
_last_screen_context = ""
_last_camera_context = ""


def log_perception(source, content, analyze=False):
    """Write observation to perception log."""
    MEMORY_PATH.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"\n[{timestamp}] [{source}] {content}"

    with _buffer_lock:
        _perception_buffer.append(entry)

    # Also write to learning log if it's worth keeping
    if analyze and len(content) > 30:
        with open(LEARNING_LOG, "a", encoding="utf-8") as f:
            f.write(f"\n\n## [{timestamp}] perception | {source}\n{content}\n---")

    print(f"[VERA PERCEPTION] [{source}] {content[:80]}{'...' if len(content) > 80 else ''}")


def flush_perception_log():
    """Flush buffer to perception log file."""
    with _buffer_lock:
        if not _perception_buffer:
            return
        entries = _perception_buffer.copy()
        _perception_buffer.clear()

    PERCEPTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(PERCEPTION_LOG, "a", encoding="utf-8") as f:
        f.write("\n".join(entries))


def ask_vera(prompt, context=""):
    """Quick inference call for summarization."""
    try:
        payload = {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": (
                    "You are VERA's perception engine. Summarize observations "
                    "into brief, actionable learning notes for Joshua Burton. "
                    "2-3 sentences max. Focus on what's relevant to cybersecurity, "
                    "AI development, bug bounty, CTF, hardware hacking. "
                    "If nothing relevant, respond: SKIP"
                )},
                {"role": "user", "content": f"{context}\n\nObservation: {prompt[:500]}"}
            ],
            "stream": False,
            "options": {"temperature": 0.2, "num_ctx": 2048},
        }
        resp = requests.post(OLLAMA_URL, data=json.dumps(payload), timeout=30)
        resp.raise_for_status()
        result = resp.json()["message"]["content"].strip()
        return None if result == "SKIP" else result
    except Exception as e:
        return None


def image_to_base64(image):
    """Convert PIL image to base64 string."""
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("utf-8")


def analyze_image(image, question):
    """Send image to VERA's vision model."""
    try:
        img_b64 = image_to_base64(image)
        payload = {
            "model": MODEL,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                    {"type": "text", "text": question}
                ]
            }],
            "stream": False,
            "options": {"temperature": 0.2, "num_ctx": 4096},
        }
        resp = requests.post(OLLAMA_URL, data=json.dumps(payload), timeout=30)
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()
    except Exception as e:
        return f"Vision error: {e}"


# ── MIC LOOP ─────────────────────────────────────────────────────────────────
def mic_loop():
    """
    Continuously listen via microphone.
    Transcribes speech and logs to perception memory.
    Does NOT respond -- passive learning mode only.
    """
    print("[VERA PERCEPTION] Mic loop starting...")

    try:
        from faster_whisper import WhisperModel
        import sounddevice as sd
        import soundfile as sf
        import tempfile
        import numpy as np
    except ImportError as e:
        print(f"[VERA PERCEPTION] Mic loop unavailable: {e}")
        print("[VERA PERCEPTION] Install: pip install faster-whisper sounddevice soundfile")
        return

    try:
        model = WhisperModel("base", device="cpu", compute_type="int8")
        print("[VERA PERCEPTION] Mic model loaded. Listening passively...")
    except Exception as e:
        print(f"[VERA PERCEPTION] Mic model error: {e}")
        return

    SAMPLERATE = 16000
    CHUNK_DURATION = 5  # seconds per capture

    while _running:
        try:
            # Capture audio chunk
            audio = sd.rec(
                int(CHUNK_DURATION * SAMPLERATE),
                samplerate=SAMPLERATE,
                channels=1,
                dtype="float32"
            )
            sd.wait()

            # Check if there's actual audio (not silence)
            rms = float(np.sqrt(np.mean(audio**2)))
            if rms < 0.005:  # silence threshold
                continue

            # Write to temp file and transcribe
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name

            sf.write(tmp_path, audio, SAMPLERATE)

            segments, _ = model.transcribe(tmp_path, language="en", vad_filter=True)
            text = " ".join(seg.text.strip() for seg in segments).strip()

            try:
                os.unlink(tmp_path)
            except Exception:
                pass

            if text and len(text) > 10:
                log_perception("MIC", text, analyze=True)

        except KeyboardInterrupt:
            break
        except Exception as e:
            time.sleep(2)

    print("[VERA PERCEPTION] Mic loop stopped.")


# ── SCREEN MONITOR ────────────────────────────────────────────────────────────
def screen_loop():
    """
    Capture screen periodically and analyze with vision model.
    Logs observations about what Josh is working on.
    """
    global _last_screen_context
    print("[VERA PERCEPTION] Screen monitor starting...")

    try:
        import pyautogui
        from PIL import Image
    except ImportError as e:
        print(f"[VERA PERCEPTION] Screen loop unavailable: {e}")
        return

    print(f"[VERA PERCEPTION] Screen monitor active (every {SCREEN_INTERVAL}s)")

    while _running:
        try:
            time.sleep(SCREEN_INTERVAL)

            # Capture screen
            screenshot = pyautogui.screenshot()

            # Resize for faster inference (half size)
            w, h = screenshot.size
            screenshot = screenshot.resize((w//2, h//2))

            # Analyze
            context = analyze_image(
                screenshot,
                "What is Josh working on right now? Be specific and brief. "
                "Focus on: code, security tools, browser tabs, terminals, "
                "documents. What application is active? Any notable content?"
            )

            if context and context != _last_screen_context:
                # Only log if something changed
                if len(context) > 20:
                    log_perception("SCREEN", context, analyze=True)
                    _last_screen_context = context

                    # Update dashboard state with screen context
                    try:
                        if DASHBOARD_STATE.exists():
                            state = json.loads(DASHBOARD_STATE.read_text(encoding="utf-8"))
                            state["screen_context"] = context[:200]
                            state["screen_updated"] = datetime.datetime.now().isoformat()
                            DASHBOARD_STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
                    except Exception:
                        pass

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[VERA PERCEPTION] Screen error: {e}")
            time.sleep(10)

    print("[VERA PERCEPTION] Screen monitor stopped.")


# ── CAMERA FEED ───────────────────────────────────────────────────────────────
def camera_loop():
    """
    Capture webcam frames periodically and analyze with vision model.
    Logs observations about what's visible in the environment.
    """
    global _last_camera_context
    print("[VERA PERCEPTION] Camera feed starting...")

    try:
        import cv2
        from PIL import Image
        import numpy as np
    except ImportError as e:
        print(f"[VERA PERCEPTION] Camera loop unavailable: {e}")
        print("[VERA PERCEPTION] Install: pip install opencv-python")
        return

    # Try to open camera
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[VERA PERCEPTION] No camera found. Skipping camera loop.")
        return

    print(f"[VERA PERCEPTION] Camera active (every {CAMERA_INTERVAL}s)")

    while _running:
        try:
            time.sleep(CAMERA_INTERVAL)

            ret, frame = cap.read()
            if not ret:
                print("[VERA PERCEPTION] Camera read failed.")
                time.sleep(10)
                continue

            # Convert BGR to RGB and create PIL Image
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb_frame)

            # Resize for faster inference
            pil_image = pil_image.resize((640, 480))

            context = analyze_image(
                pil_image,
                "What do you see in this camera feed? "
                "Describe the environment, any people, devices, screens, or "
                "hardware visible. Be brief and factual. "
                "Note anything relevant to a cybersecurity developer's workspace."
            )

            if context and context != _last_camera_context:
                if len(context) > 20:
                    log_perception("CAMERA", context, analyze=False)
                    _last_camera_context = context

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[VERA PERCEPTION] Camera error: {e}")
            time.sleep(10)

    cap.release()
    print("[VERA PERCEPTION] Camera feed stopped.")


# ── ACTONE LOOP ───────────────────────────────────────────────────────────────
ACTONE_SAMPLE_RATE = 16000    # must match the rate used on the sending device --
                              # NOT 8000: our auth-tone band climbs to ~3950Hz,
                              # which sits right at 8kHz's Nyquist limit (4000Hz)
                              # and gets degraded by real anti-aliasing/mic
                              # filtering there. 16kHz (already used by mic_loop
                              # above for Whisper) gives real headroom instead.
ACTONE_CHUNK_MS     = 150     # small capture chunks fed into a rolling buffer
ACTONE_BUFFER_MS    = 1400    # rolling window kept for scanning (> one frame's
                              # ~520ms, with margin so a burst starting anywhere
                              # in a chunk is still fully contained once buffered)
ACTONE_SCAN_STEP    = 200     # sliding-scan offset step, in samples (~25ms)


def actone_loop():
    """
    Continuously listen for authenticated ACTONE command/status tones
    from any registered device (Kyger suit, droids). Passive logging
    only, same as mic/camera -- deciding whether VERA *acts* on a
    decoded command is the agent's job, not perception's; this loop's
    job stops at "here is what was heard and whether it was genuine."

    Captures small chunks continuously into a rolling buffer and slides
    a search across it (vera_actone_devices.scan_any_device) rather than
    decoding one fixed-size chunk at a time -- a burst can start at any
    arbitrary moment relative to when this loop happened to start
    capturing, so fixed non-overlapping chunks would miss most bursts
    that straddle a chunk boundary.
    """
    print("[VERA PERCEPTION] ACTONE loop starting...")

    try:
        import sounddevice as sd
        import numpy as np
        from vera_actone_devices import scan_any_device
    except ImportError as e:
        print(f"[VERA PERCEPTION] ACTONE loop unavailable: {e}")
        print("[VERA PERCEPTION] Requires vera_actone_devices.py / "
              "vera_actone_secure.py / libactone_secure.dll at VERA_ROOT, "
              "plus: pip install sounddevice numpy")
        return

    chunk_samples = int(ACTONE_SAMPLE_RATE * ACTONE_CHUNK_MS / 1000)
    buffer_samples = int(ACTONE_SAMPLE_RATE * ACTONE_BUFFER_MS / 1000)
    rolling = np.zeros(buffer_samples, dtype=np.int16)

    print(f"[VERA PERCEPTION] ACTONE listening (rolling buffer={ACTONE_BUFFER_MS}ms, "
          f"chunk={ACTONE_CHUNK_MS}ms, rate={ACTONE_SAMPLE_RATE}Hz)...")

    while _running:
        try:
            audio = sd.rec(chunk_samples, samplerate=ACTONE_SAMPLE_RATE,
                            channels=1, dtype="float32")
            sd.wait()
            new_chunk = (audio[:, 0] * 32767.0).astype(np.int16)

            # Slide the rolling buffer: drop the oldest chunk_samples,
            # append the new chunk at the end.
            rolling = np.roll(rolling, -chunk_samples)
            rolling[-chunk_samples:] = new_chunk

            device, result, offset = scan_any_device(
                rolling, sample_rate=ACTONE_SAMPLE_RATE,
                step=ACTONE_SCAN_STEP, now=time.time(),
            )

            if device is not None:
                log_perception("ACTONE", f"{device}: {result.cmd} "
                                f"(counter={result.matched_counter}, offset={offset})",
                                analyze=True)
                # Clear the buffer after a hit so the same physical burst
                # (which may still be tailing off across the next couple
                # of chunks) isn't scanned and matched a second time.
                rolling[:] = 0

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[VERA PERCEPTION] ACTONE error: {e}")
            time.sleep(2)

    print("[VERA PERCEPTION] ACTONE loop stopped.")


# ── LOG FLUSH LOOP ────────────────────────────────────────────────────────────
def flush_loop():
    """Periodically flush perception buffer to disk."""
    while _running:
        time.sleep(LOG_INTERVAL)
        flush_perception_log()


# ── STATUS WRITER ─────────────────────────────────────────────────────────────
def write_status(channels):
    """Write perception engine status to dashboard state."""
    try:
        state = {}
        if DASHBOARD_STATE.exists():
            state = json.loads(DASHBOARD_STATE.read_text(encoding="utf-8"))
        state["perception_active"] = True
        state["perception_channels"] = channels
        state["perception_started"] = datetime.datetime.now().isoformat()
        DASHBOARD_STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception:
        pass


# ── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    global _running

    parser = argparse.ArgumentParser(description="VERA Perception Engine v1.0")
    parser.add_argument("--mic",    action="store_true", help="Enable mic listening loop")
    parser.add_argument("--screen", action="store_true", help="Enable screen monitoring")
    parser.add_argument("--camera", action="store_true", help="Enable camera feed")
    parser.add_argument("--actone", action="store_true", help="Enable ACTONE device listening")
    parser.add_argument("--all",    action="store_true", help="Enable all channels")
    args = parser.parse_args()

    # Default: all channels if none specified
    if not any([args.mic, args.screen, args.camera, args.actone, args.all]):
        args.all = True

    enable_mic    = args.mic    or args.all
    enable_screen = args.screen or args.all
    enable_camera = args.camera or args.all
    enable_actone = args.actone or args.all

    channels = []
    if enable_mic:    channels.append("MIC")
    if enable_screen: channels.append("SCREEN")
    if enable_camera: channels.append("CAMERA")
    if enable_actone: channels.append("ACTONE")

    print("=" * 60)
    print("VERA Perception Engine v1.0")
    print(f"Active channels: {', '.join(channels)}")
    print(f"Perception log: {PERCEPTION_LOG}")
    print(f"Learning log: {LEARNING_LOG}")
    print("Ctrl+C to stop")
    print("=" * 60)

    write_status(channels)

    threads = []

    if enable_mic:
        t = threading.Thread(target=mic_loop, daemon=True, name="VERA-MIC")
        threads.append(t)
        t.start()

    if enable_screen:
        t = threading.Thread(target=screen_loop, daemon=True, name="VERA-SCREEN")
        threads.append(t)
        t.start()

    if enable_camera:
        t = threading.Thread(target=camera_loop, daemon=True, name="VERA-CAMERA")
        threads.append(t)
        t.start()

    if enable_actone:
        t = threading.Thread(target=actone_loop, daemon=True, name="VERA-ACTONE")
        threads.append(t)
        t.start()

    # Flush loop
    t = threading.Thread(target=flush_loop, daemon=True, name="VERA-FLUSH")
    threads.append(t)
    t.start()

    print(f"\n[VERA PERCEPTION] {len(threads)} threads running. Observing silently...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[VERA PERCEPTION] Shutting down...")
        _running = False
        flush_perception_log()
        print("[VERA PERCEPTION] Final log flush complete. Goodbye.")


if __name__ == "__main__":
    main()
