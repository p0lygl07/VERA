"""
vera_bus.bus — the message bus that unifies the projects.

This is the promotion of vera_bridge (port 8767) from a point bridge into a
pub/sub spine every node publishes to and subscribes from. Stdlib only.

Wire protocol (HTTP, JSON bodies):
  POST /publish        body = one message dict     -> {"ok":true,"id":...} or 400 with error
  GET  /subscribe?kinds=observation,claim&cursor=N -> long-polls up to ~25s,
                       returns {"cursor":M,"messages":[...]} (may be empty on timeout)
  GET  /log?since=0                                -> full ring buffer from a cursor (audit/debug)
  GET  /health                                     -> {"ok":true,"count":N}

Design choices that matter:
- Every /publish is validated by vera_bus.validate at the door. Garbage never
  enters the log. This is the "reject at the bus" guarantee.
- The log is an in-memory ring buffer with a monotonic cursor. Subscribers track
  their own cursor, so a slow node never blocks a fast one and reconnects resume
  cleanly. Swap the ring for an append-only file later without touching nodes.
- Long-poll (not websockets) keeps every node a dozen lines of urllib. Works the
  same from a Python script, the Jetson, or a Pi over the LAN.
"""
from __future__ import annotations
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from validate import validate, ValidationError

HOST = "127.0.0.1"
PORT = 8768
RING_SIZE = 10000          # messages retained in memory
LONGPOLL_SECONDS = 25      # how long /subscribe blocks waiting for new messages


class _Log:
    """Thread-safe monotonic ring buffer with a condition for long-pollers."""
    def __init__(self, size: int):
        self._buf: list[dict] = []
        self._size = size
        self._base = 0                    # cursor of _buf[0]
        self._cv = threading.Condition()

    def append(self, msg: dict) -> int:
        with self._cv:
            self._buf.append(msg)
            if len(self._buf) > self._size:
                drop = len(self._buf) - self._size
                self._buf = self._buf[drop:]
                self._base += drop
            cursor = self._base + len(self._buf)
            self._cv.notify_all()
            return cursor

    def since(self, cursor: int, kinds: set[str] | None) -> tuple[int, list[dict]]:
        with self._cv:
            start = max(0, cursor - self._base)
            out = self._buf[start:]
            newcur = self._base + len(self._buf)
        if kinds:
            out = [m for m in out if m.get("kind") in kinds]
        return newcur, out

    def wait_for(self, cursor: int, kinds: set[str] | None, timeout: float):
        deadline = time.time() + timeout
        while True:
            newcur, msgs = self.since(cursor, kinds)
            if msgs or time.time() >= deadline:
                return newcur, msgs
            with self._cv:
                self._cv.wait(timeout=min(1.0, deadline - time.time()))


LOG = _Log(RING_SIZE)


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, obj: dict):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass  # silence default stderr spam; nodes have their own logging

    def do_POST(self):
        if urlparse(self.path).path != "/publish":
            return self._send(404, {"ok": False, "error": "not found"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            msg = json.loads(self.rfile.read(length))
        except Exception as e:
            return self._send(400, {"ok": False, "error": f"bad json: {e}"})
        try:
            validate(msg)
        except ValidationError as e:
            return self._send(400, {"ok": False, "error": f"validation: {e}"})
        cursor = LOG.append(msg)
        self._send(200, {"ok": True, "id": msg.get("id"), "cursor": cursor})

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/health":
            cur, _ = LOG.since(0, None)
            return self._send(200, {"ok": True, "count": cur})
        kinds = set(q["kinds"][0].split(",")) if "kinds" in q else None
        cursor = int(q.get("cursor", [0])[0]) if u.path == "/subscribe" else int(q.get("since", [0])[0])
        if u.path == "/subscribe":
            newcur, msgs = LOG.wait_for(cursor, kinds, LONGPOLL_SECONDS)
            return self._send(200, {"cursor": newcur, "messages": msgs})
        if u.path == "/log":
            newcur, msgs = LOG.since(cursor, kinds)
            return self._send(200, {"cursor": newcur, "messages": msgs})
        self._send(404, {"ok": False, "error": "not found"})


def serve(host: str = HOST, port: int = PORT):
    srv = ThreadingHTTPServer((host, port), Handler)
    print(f"[vera_bus] listening on http://{host}:{port}  (publish/subscribe/log/health)")
    srv.serve_forever()


if __name__ == "__main__":
    serve()
