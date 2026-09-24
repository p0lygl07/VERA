"""
demo_subscriber — stand-in for the KB trainer's intake. Prints observations as they land.
In Phase 4 this becomes the real claim-updating consumer.
"""
import sys
import _bootstrap  # noqa: F401  (adds vera_bus/ to sys.path)
from client import BusClient

bus = BusClient()
print("[subscriber] listening for observations...")
for cursor, msgs in bus.subscribe(kinds=["observation"]):
    for m in msgs:
        print(f"[subscriber] got {m['type']} from {m['source']}: {m['payload']}")
    sys.stdout.flush()
    break  # demo: exit after first batch so the test terminates
print("[subscriber] round-trip confirmed, exiting")
