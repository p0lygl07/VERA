#!/usr/bin/env python3
"""
VERA HTTP Bridge v1.2
Connects dashboard to Ollama (chat) + Conductor (execution) + edge-tts (voice).

Port: 8767

Endpoints:
  POST /chat      -- conversation with VERA (text + optional Sonia voice)
  POST /execute   -- route execution task to conductor sub-agent
  POST /speak     -- text to Sonia voice (returns mp3)
  GET  /status    -- full system status
  GET  /history   -- conversation history
  POST /clear     -- clear conversation
"""

import json
import datetime
import threading
import asyncio
import tempfile
import os
import socket
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests

VERA_ROOT      = Path("C:/Users/p0ly/Desktop/AI/VERA")
SOUL_PATH      = VERA_ROOT / "memory" / "SOUL.md"
USER_PATH      = VERA_ROOT / "memory" / "USER.md"
BRIDGE_LOG     = VERA_ROOT / "logs" / "bridge_log.md"
OLLAMA_URL     = "http://localhost:11434/api/chat"
MODEL          = "qwen3.5:9b"
PORT           = 8767
CONDUCTOR_HOST = "127.0.0.1"
CONDUCTOR_PORT = 8766
VOICE          = "en-GB-SoniaNeural"
VOICE_RATE     = "+5%"
TIMEOUT        = 300  # seconds for conductor calls

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
        "Keep responses concise and conversational. "
        "You DO have execution capabilities via the dashboard -- "
        "tool calls are routed through the conductor on port 8766. "
        "When asked to open terminals, run commands, or execute tasks, "
        "tell the user you are routing to the appropriate sub-agent. "
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
            _log(f"USER: {user_message[:80]} | VERA: {response_text[:80]}")
            return {"status": "ok", "response": response_text,
                    "timestamp": datetime.datetime.now().strftime("%H:%M:%S")}
        except requests.exceptions.ConnectionError:
            return {"status": "error", "response": "Ollama is offline. Start Ollama first."}
        except Exception as e:
            return {"status": "error", "response": f"Error: {e}"}


def route_to_conductor(target, task):
    """
    Send task to conductor sub-agent via IPC socket.
    Returns the sub-agent result.
    """
    payload = {
        "target": target,
        "text": task,
        "payload": task,
        "source": "vera_dashboard_bridge",
        "timestamp": datetime.datetime.now().isoformat(),
    }
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(TIMEOUT)
        sock.connect((CONDUCTOR_HOST, CONDUCTOR_PORT))
        sock.sendall(json.dumps(payload).encode("utf-8"))

        # Receive full response
        data = b""
        sock.settimeout(TIMEOUT)
        while True:
            try:
                chunk = sock.recv(8192)
                if not chunk:
                    break
                data += chunk
            except socket.timeout:
                break
        sock.close()

        if not data:
            return {"status": "error", "result": "No response from conductor"}

        response = json.loads(data.decode("utf-8"))
        return {"status": "ok", "result": response.get("result", ""),
                "message": response.get("message", "")}

    except ConnectionRefusedError:
        return {"status": "error",
                "result": "Conductor offline. Start: python core/agent_conductor.py"}
    except socket.timeout:
        return {"status": "error",
                "result": f"Conductor timed out after {TIMEOUT}s. Sub-agent may still be running."}
    except Exception as e:
        return {"status": "error", "result": f"Conductor error: {e}"}


def decide_target(task):
    """Auto-detect which sub-agent should handle a task."""
    task_lower = task.lower()
    if any(w in task_lower for w in ["terminal", "powershell", "cmd", "command",
                                       "run", "execute", "install", "pip",
                                       "import", "dependency", "path", "repair"]):
        return "sre_engineer"
    elif any(w in task_lower for w in ["scan", "port", "network", "monitor",
                                         "log", "watch", "check status", "health"]):
        return "monitor_operative"
    elif any(w in task_lower for w in ["recon", "subfinder", "httpx", "nuclei",
                                         "ffuf", "bug bounty", "target", "enumerate"]):
        return "recon_operative"
    elif any(w in task_lower for w in ["ctf", "lab", "challenge", "html",
                                         "snhupers", "pdf", "solution guide"]):
        return "ctf_builder"
    else:
        return "sre_engineer"  # default


async def text_to_speech_async(text, output_path):
    try:
        import edge_tts
        clean = text.replace("**", "").replace("*", "").replace("#", "").replace("`", "")
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


def _log(message):
    BRIDGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(BRIDGE_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")


def check_conductor():
    """Check if conductor is online."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect((CONDUCTOR_HOST, CONDUCTOR_PORT))
        sock.sendall(json.dumps({"ping": True}).encode("utf-8"))
        data = sock.recv(1024)
        sock.close()
        return True
    except Exception:
        return False


class BridgeHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def send_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/status":
            try:
                ollama_ok = requests.get(
                    "http://localhost:11434/api/tags", timeout=3
                ).status_code == 200
            except Exception:
                ollama_ok = False

            try:
                import edge_tts
                tts_ok = True
            except ImportError:
                tts_ok = False

            conductor_ok = check_conductor()

            data = {
                "status": "online",
                "bridge_port": PORT,
                "ollama": "online" if ollama_ok else "offline",
                "conductor": "online" if conductor_ok else "offline (start: python core/agent_conductor.py)",
                "tts": "online" if tts_ok else "offline (pip install edge-tts)",
                "voice": VOICE,
                "model": MODEL,
                "conversation_length": len([m for m in conversation
                                           if m.get("role") != "system"]),
                "sub_agents": ["monitor_operative", "sre_engineer",
                               "recon_operative", "ctf_builder"],
                "timestamp": datetime.datetime.now().isoformat(),
            }
            self._json(200, data)

        elif self.path == "/history":
            with conversation_lock:
                history = [{"role": m["role"], "content": m["content"]}
                          for m in conversation
                          if m.get("role") in ("user", "assistant")]
            self._json(200, {"history": history[-20:]})

        else:
            self._json(404, {"error": "Not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")

        if self.path == "/chat":
            try:
                data = json.loads(body)
                message = data.get("message", "").strip()
                if not message:
                    self._json(400, {"error": "No message"})
                    return
                result = chat_with_vera(message)
                self._json(200, result)
            except json.JSONDecodeError:
                self._json(400, {"error": "Invalid JSON"})

        elif self.path == "/execute":
            """Route execution task to conductor sub-agent."""
            try:
                data = json.loads(body)
                task = data.get("task", "").strip()
                target = data.get("target", "").strip()

                if not task:
                    self._json(400, {"error": "No task provided"})
                    return

                # Auto-detect target if not specified
                if not target:
                    target = decide_target(task)

                print(f"[VERA BRIDGE] Routing to {target}: {task[:60]}")
                _log(f"EXECUTE -> {target}: {task[:80]}")

                result = route_to_conductor(target, task)
                result["target"] = target
                self._json(200, result)

            except json.JSONDecodeError:
                self._json(400, {"error": "Invalid JSON"})

        elif self.path == "/speak":
            try:
                data = json.loads(body)
                text = data.get("text", "").strip()
                if not text:
                    self._json(400, {"error": "No text"})
                    return
                audio = text_to_speech(text)
                if audio:
                    self.send_response(200)
                    self.send_header("Content-Type", "audio/mpeg")
                    self.send_header("Content-Length", str(len(audio)))
                    self.send_cors()
                    self.end_headers()
                    self.wfile.write(audio)
                else:
                    self._json(500, {"error": "TTS failed"})
            except Exception as e:
                self._json(500, {"error": str(e)})

        elif self.path == "/clear":
            with conversation_lock:
                conversation.clear()
            self._json(200, {"status": "cleared"})

        else:
            self._json(404, {"error": "Not found"})

    def _json(self, code, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_cors()
        self.end_headers()
        self.wfile.write(body)


def main():
    print("=" * 60)
    print("VERA HTTP Bridge v1.2")
    print(f"Port: {PORT} | Conductor: {CONDUCTOR_HOST}:{CONDUCTOR_PORT}")
    print(f"Endpoints: /chat | /execute | /speak | /status | /history | /clear")
    print("=" * 60)

    try:
        import edge_tts
        print(f"[VERA BRIDGE] TTS: {VOICE} ready")
    except ImportError:
        print("[VERA BRIDGE] TTS: offline (pip install edge-tts)")

    conductor_ok = check_conductor()
    print(f"[VERA BRIDGE] Conductor: {'online' if conductor_ok else 'offline'}")

    server = HTTPServer(("127.0.0.1", PORT), BridgeHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[VERA BRIDGE] Stopped.")


if __name__ == "__main__":
    main()
