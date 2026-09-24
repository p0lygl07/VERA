"""
demo_publisher — stand-in for Screen Copilot. Emits one screen_activity Observation.
In Phase 3 this file gets replaced by the real Screen Copilot adapter; the emit shape
stays identical.
"""
import _bootstrap  # noqa: F401  (adds vera_bus/ to sys.path)
from client import BusClient

bus = BusClient()
obs = {
    "kind": "observation",
    "source": "screen_copilot",
    "type": "screen_activity",
    "payload": {"window_title": "Kali - Terminal", "app": "wt.exe", "guess": "pentesting"},
    "confidence": 0.82,
}
ack = bus.publish(obs)
print(f"[publisher] sent observation id={ack['id']} cursor={ack['cursor']}")
