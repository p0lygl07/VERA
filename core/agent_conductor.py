#!/usr/bin/env python3
"""
VERA Conductor IPC Server
Multi-threaded socket server for sub-agent routing.

Port: 8766 (dashboard server uses 8765 -- do not conflict)

Usage:
  python core/agent_conductor.py          # start conductor server
  python core/agent_conductor.py status   # check if running
"""

import socket
import json
import threading
import sys
import datetime
from pathlib import Path

VERA_ROOT = Path("C:/Users/p0ly/Desktop/AI/VERA")
LOG_PATH  = VERA_ROOT / "logs" / "conductor_log.md"

# Import factory with graceful fallback
try:
    from agent_factory import SubAgentFactory
    FACTORY_AVAILABLE = True
except ImportError:
    try:
        from core.agent_factory import SubAgentFactory
        FACTORY_AVAILABLE = True
    except ImportError:
        FACTORY_AVAILABLE = False
        print("[VERA CONDUCTOR] Warning: agent_factory not found. Sub-agent routing disabled.")


def log_conductor(event, details=""):
    """Log conductor events."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"| {timestamp} | {event} | {details[:100]} |\n")


class AgentConductor:
    def __init__(self, host="127.0.0.1", port=8766):
        # NOTE: port 8766 -- dashboard server runs on 8765
        self.host = host
        self.port = port
        self.active_operatives = {}
        self.request_count = 0
        self.start_time = datetime.datetime.now()

        if FACTORY_AVAILABLE:
            try:
                self.factory = SubAgentFactory()
                print(f"[VERA CONDUCTOR] Factory initialized.")
            except Exception as e:
                print(f"[VERA CONDUCTOR] Factory init error: {e}")
                self.factory = None
        else:
            self.factory = None

    def spawn_and_route(self, agent_type: str, task: str):
        """Spawn a sub-agent if not running, then route the task."""
        if not self.factory:
            return "ERROR: smolagents factory not available. Install smolagents."

        if agent_type not in self.active_operatives:
            print(f"[VERA CONDUCTOR] Spawning sub-agent: {agent_type}")
            try:
                self.active_operatives[agent_type] = self.factory.create_operative(agent_type)
            except Exception as e:
                log_conductor("SPAWN_ERROR", f"{agent_type}: {e}")
                return f"ERROR spawning {agent_type}: {e}"

        print(f"[VERA CONDUCTOR] Routing to [{agent_type}]: {task[:80]}")
        log_conductor("ROUTE", f"{agent_type}: {task[:80]}")

        try:
            result = self.active_operatives[agent_type].run(task)
            log_conductor("RESULT", f"{agent_type}: success")
            return result
        except Exception as e:
            log_conductor("EXEC_ERROR", f"{agent_type}: {e}")
            return f"ERROR during execution: {e}"

    def _handle_socket_client(self, client_socket: socket.socket, addr):
        """Process incoming IPC command with full error isolation."""
        self.request_count += 1
        print(f"\n[VERA CONDUCTOR] Connection from {addr} (request #{self.request_count})")

        with client_socket:
            try:
                data = client_socket.recv(8192).decode("utf-8").strip()

                if not data:
                    # Silent return on empty ping
                    return

                # Parse JSON with raw string fallback
                try:
                    payload = json.loads(data)
                    print(f"[VERA CONDUCTOR] JSON payload: {str(payload)[:100]}")
                except json.JSONDecodeError:
                    # Handle raw string transmissions gracefully
                    print(f"[VERA CONDUCTOR] Raw string received: {data[:80]}")
                    payload = {
                        "origin": "raw_pipe",
                        "action": "execute",
                        "text": data,
                        "target": "sre_engineer"  # default target for raw strings
                    }

                # Extract routing fields
                target = payload.get("target")
                # Support multiple payload schemas
                task_text = (
                    payload.get("text") or
                    payload.get("task") or
                    payload.get("payload") or
                    payload.get("message")
                )

                valid_targets = ["monitor_operative", "sre_engineer",
                                 "recon_operative", "ctf_builder"]

                if target in valid_targets and task_text:
                    result = self.spawn_and_route(target, task_text)
                    response = {
                        "status": "ACK",
                        "message": f"Task completed by {target}",
                        "result": str(result),
                        "request_id": self.request_count,
                    }
                elif target and target not in valid_targets:
                    response = {
                        "status": "ERROR",
                        "message": f"Unknown target: '{target}'",
                        "valid_targets": valid_targets,
                    }
                else:
                    # Default ACK for pings or unknown payloads
                    response = {
                        "status": "ACK",
                        "message": "VERA Conductor online. Specify 'target' and 'text' to route.",
                        "conductor_uptime": str(datetime.datetime.now() - self.start_time).split(".")[0],
                        "active_operatives": list(self.active_operatives.keys()),
                    }

                client_socket.sendall(json.dumps(response).encode("utf-8"))

            except Exception as e:
                print(f"[VERA CONDUCTOR] Socket handler error: {e}")
                log_conductor("SOCKET_ERROR", str(e))
                try:
                    error_resp = json.dumps({"status": "ERROR", "message": str(e)})
                    client_socket.sendall(error_resp.encode("utf-8"))
                except Exception:
                    pass

    def start(self):
        """Start the conductor IPC server."""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            server.bind((self.host, self.port))
        except OSError as e:
            print(f"[VERA CONDUCTOR] Cannot bind to {self.host}:{self.port}: {e}")
            print(f"[VERA CONDUCTOR] Is another service already using port {self.port}?")
            sys.exit(1)

        server.listen(10)
        print("=" * 60)
        print(f"VERA Agent Conductor")
        print(f"Listening on {self.host}:{self.port}")
        print(f"Dashboard server: http://localhost:8765/vera_dashboard.html")
        print(f"Factory: {'online' if self.factory else 'offline (install smolagents)'}")
        print(f"Sub-agent profiles: monitor_operative, sre_engineer, recon_operative, ctf_builder")
        print("=" * 60)
        log_conductor("STARTUP", f"Conductor bound to {self.host}:{self.port}")

        try:
            while True:
                client_sock, addr = server.accept()
                thread = threading.Thread(
                    target=self._handle_socket_client,
                    args=(client_sock, addr),
                    daemon=True
                )
                thread.start()
        except KeyboardInterrupt:
            print("\n[VERA CONDUCTOR] Shutting down.")
            log_conductor("SHUTDOWN", "KeyboardInterrupt")
        finally:
            server.close()


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "status":
        # Quick status check
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect(("127.0.0.1", 8766))
            sock.sendall(json.dumps({"ping": True}).encode("utf-8"))
            resp = json.loads(sock.recv(4096).decode("utf-8"))
            sock.close()
            print(f"[VERA CONDUCTOR] Online: {resp}")
        except Exception as e:
            print(f"[VERA CONDUCTOR] Offline: {e}")
        return

    conductor = AgentConductor()
    conductor.start()


if __name__ == "__main__":
    main()
