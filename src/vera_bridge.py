#!/usr/bin/env python3
"""
VERA HTTP Bridge v1.1
Connects dashboard browser to Ollama + voice (edge-tts).

Port: 8767

Endpoints:
  POST /chat      -- send message, get VERA response
  POST /speak     -- convert text to audio (returns mp3)
  GET  /status    -- bridge health check
  GET  /history   -- get recent conversation
  POST /clear     -- clear conversation history
"""

import json
import datetime
import threading
import asyncio
import tempfile
import os
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests

VERA_ROOT   = Path("C:/Users/p0ly/Desktop/AI/VERA")
SOUL_PATH   = VERA_ROOT / "memory" / "SOUL.md"
USER_PATH   = VERA_ROOT / "memory" / "USER.md"
BRIDGE_LOG  = VERA_ROOT / "logs" / "bridge_log.md"
OLLAMA_URL  = "http://localhost:11434/api/chat"
MODEL       = "qwen3.5:9b"
PORT        = 8767
VOICE       = "en-GB-SoniaNeural"
VOICE_RATE  = "+5%"

conversation = []
conversation_lock = threading.Lock()


def load_system_prompt():
    parts = []
    if SOUL_PATH.exists():
        parts.append(SOUL_PATH.read_text(encoding="utf-8"))
    if USER_PATH.exists():
        parts.append(USER_PATH.read_text(encoding="utf-8"))
    parts.append(
        "DASHBOARD CHAT MODE: Responding via the VERA web dashboard. "
        "Keep responses concise -- 2-4 sentences for voice replies. "
        "Use plain conversational text. No markdown headers or bullet lists. "
        "Declare truth layer [T1-T7] when making factual claims."
    )
    return "\n\n---\n\n".join(parts)


def chat_with_vera(user_message):
    """Send message to Ollama, return response."""
    global conversation
    with conversation_lock:
        if not conversation:
            conversation = [{"role": "system", "content": load_system_prompt()}]
        conversation.append({"role": "user", "content": user_message})
        try:
            payload = {
                "model": MODEL,
                "messages": conversation,
                "stream": False,
                "options": {"temperature": 0.3, "num_ctx": 4096},
            }
            resp = requests.post(OLLAMA_URL, data=json.dumps(payload), timeout=60)
            resp.raise_for_status()
            response_text = resp.json()["message"]["content"]
            conversation.append({"role": "assistant", "content": response_text})
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            BRIDGE_LOG.parent.mkdir(parents=True, exist_ok=True)
            with open(BRIDGE_LOG, "a", encoding="utf-8") as f:
                f.write(f"\n[{timestamp}] USER: {user_message[:100]}\n")
                f.write(f"[{timestamp}] VERA: {response_text[:200]}\n---\n")
            return {"status": "ok", "response": response_text, "timestamp": timestamp}
        except requests.exceptions.ConnectionError:
            return {"status": "error", "response": "Ollama is offline."}
        except Exception as e:
            return {"status": "error", "response": f"Error: {e}"}


async def text_to_speech_async(text, output_path):
    """Generate speech using edge-tts."""
    try:
        import edge_tts
        clean = text.replace("**", "").replace("*", "").replace("#", "").replace("`", "")
        # Trim for voice -- keep it concise
        if len(clean) > 400:
            clean = clean[:380].rsplit(".", 1)[0] + "."
        communicate = edge_tts.Communicate(clean, VOICE, rate=VOICE_RATE)
        await communicate.save(output_path)
        return True
    except ImportError:
        return False
    except Exception as e:
        print(f"[VERA BRIDGE] TTS error: {e}")
        return False


def text_to_speech(text):
    """Generate speech and return audio bytes."""
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        loop = asyncio.new_event_loop()
        success = loop.run_until_complete(text_to_speech_async(text, tmp_path))
        loop.close()
        if success and os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
            with open(tmp_path, "rb") as f:
                return f.read()
        return None
    finally:
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass


class BridgeHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress HTTP logs

    def send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):
        if self.path == "/status":
            try:
                resp = requests.get("http://localhost:11434/api/tags", timeout=3)
                ollama_ok = resp.status_code == 200
            except Exception:
                ollama_ok = False

            # Check edge-tts
            try:
                import edge_tts
                tts_ok = True
            except ImportError:
                tts_ok = False

            data = {
                "status": "online",
                "bridge_port": PORT,
                "ollama": "online" if ollama_ok else "offline",
                "tts": "online" if tts_ok else "offline (pip install edge-tts)",
                "voice": VOICE,
                "model": MODEL,
                "conversation_length": len([m for m in conversation
                                           if m.get("role") != "system"]),
                "timestamp": datetime.datetime.now().isoformat(),
            }
            self._respond_json(200, data)

        elif self.path == "/history":
            with conversation_lock:
                history = [
                    {"role": m["role"], "content": m["content"]}
                    for m in conversation
                    if m.get("role") in ("user", "assistant")
                ]
            self._respond_json(200, {"history": history[-20:]})

        else:
            self._respond_json(404, {"error": "Not found"})

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")

        if self.path == "/chat":
            try:
                data = json.loads(body)
                message = data.get("message", "").strip()
                voice_reply = data.get("voice", False)
                if not message:
                    self._respond_json(400, {"error": "No message"})
                    return
                result = chat_with_vera(message)
                # Optionally include audio
                if voice_reply and result.get("status") == "ok":
                    audio = text_to_speech(result["response"])
                    if audio:
                        import base64
                        result["audio_b64"] = base64.b64encode(audio).decode("utf-8")
                        result["audio_type"] = "audio/mpeg"
                self._respond_json(200, result)
            except json.JSONDecodeError:
                self._respond_json(400, {"error": "Invalid JSON"})

        elif self.path == "/speak":
            # Generate speech for any text
            try:
                data = json.loads(body)
                text = data.get("text", "").strip()
                if not text:
                    self._respond_json(400, {"error": "No text"})
                    return
                audio = text_to_speech(text)
                if audio:
                    self.send_response(200)
                    self.send_header("Content-Type", "audio/mpeg")
                    self.send_header("Content-Length", str(len(audio)))
                    self.send_cors_headers()
                    self.end_headers()
                    self.wfile.write(audio)
                else:
                    self._respond_json(500, {"error": "TTS failed. Is edge-tts installed?"})
            except Exception as e:
                self._respond_json(500, {"error": str(e)})

        elif self.path == "/clear":
            with conversation_lock:
                conversation.clear()
            self._respond_json(200, {"status": "cleared"})

        else:
            self._respond_json(404, {"error": "Not found"})

    def _respond_json(self, code, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(body)


def main():
    print("=" * 60)
    print("VERA HTTP Bridge v1.1")
    print(f"Listening on http://localhost:{PORT}")
    print(f"Voice: {VOICE}")
    print(f"Endpoints: /chat | /speak | /status | /history | /clear")
    print("=" * 60)

    # Test TTS on startup
    try:
        import edge_tts
        print(f"[VERA BRIDGE] TTS: edge-tts available ({VOICE})")
    except ImportError:
        print("[VERA BRIDGE] TTS: edge-tts not found -- text only mode")

    server = HTTPServer(("127.0.0.1", PORT), BridgeHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[VERA BRIDGE] Stopped.")


if __name__ == "__main__":
    main()
