"""
vera_bus.client — the ~a-dozen-lines every node uses to talk to the bus.
Stdlib urllib only, so it runs unchanged on desktop, Jetson, or Pi.
"""
from __future__ import annotations
import json
import urllib.request

from validate import stamp  # nodes stamp+validate locally before sending


class BusClient:
    def __init__(self, base: str = "http://127.0.0.1:8768"):
        self.base = base.rstrip("/")

    def publish(self, msg: dict) -> dict:
        stamp(msg)  # fills id/ts, validates locally -> fail fast before the network hop
        data = json.dumps(msg).encode()
        req = urllib.request.Request(self.base + "/publish", data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.load(r)

    def subscribe(self, kinds=None, cursor=0):
        """Generator yielding (cursor, [messages]) — long-polls forever."""
        q = f"?cursor={cursor}"
        if kinds:
            q += "&kinds=" + ",".join(kinds)
        while True:
            with urllib.request.urlopen(self.base + "/subscribe" + q, timeout=40) as r:
                out = json.load(r)
            cursor = out["cursor"]
            q = f"?cursor={cursor}" + ("&kinds=" + ",".join(kinds) if kinds else "")
            if out["messages"]:
                yield cursor, out["messages"]

    def health(self) -> dict:
        with urllib.request.urlopen(self.base + "/health", timeout=5) as r:
            return json.load(r)
