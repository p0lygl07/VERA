"""
screen_copilot_adapter — Phase 3. Turns a completed Screen Copilot analysis into
an Observation on the bus. This retires demo_publisher: Screen Copilot becomes the
first real limb of the unified loop.

It knows nothing about Screen Copilot internals. It only receives the result dict
that CopilotAnalyzer's on_result hook passes, maps it to the Observation contract,
and publishes. If the bus is down, it drops the message and keeps the copilot alive
(perception must never crash because the bus blinked) — graceful degradation.

Wiring (in the Screen Copilot launcher / overlay app, where CopilotAnalyzer is built):

    from vera_bus_hook import make_hook          # this file, importable on that box
    analyzer = CopilotAnalyzer(..., on_result=make_hook())

That's the whole integration: one import, one kwarg.
"""
from __future__ import annotations
import sys
import os

# make vera_bus importable no matter where the copilot app launches from
_VERA_BUS = os.path.dirname(os.path.abspath(__file__))
if _VERA_BUS not in sys.path:
    sys.path.insert(0, _VERA_BUS)

from client import BusClient
from validate import ValidationError


def _to_observation(result: dict) -> dict:
    """Map a Screen Copilot result dict to an Observation payload.
    result keys: title, process, tier, task, context, suggestion, region."""
    return {
        "kind": "observation",
        "source": "screen_copilot",
        "type": "screen_activity",
        "payload": {
            "window_title": result.get("title"),
            "process": result.get("process"),
            "activity": result.get("task"),        # the copilot's activity guess
            "context": result.get("context"),
            "suggestion": result.get("suggestion"),
            "region": result.get("region"),
            "tier": result.get("tier"),            # which model produced it
        },
    }


def make_hook(bus_url: str = "http://127.0.0.1:8768", verbose: bool = True):
    """Return an on_result(result) callback wired to a BusClient.
    Failures are swallowed with a log line — the copilot keeps running."""
    bus = BusClient(bus_url)

    def hook(result: dict) -> None:
        obs = _to_observation(result)
        try:
            ack = bus.publish(obs)
            if verbose:
                print(f"[vera_bus] published observation id={ack.get('id')} "
                      f"cursor={ack.get('cursor')}")
        except ValidationError as e:
            # our own bad mapping — worth seeing loudly, it's a code bug
            print(f"[vera_bus] REFUSED (validation): {e}")
        except Exception as e:
            # bus down / network — expected sometimes, never fatal to perception
            if verbose:
                print(f"[vera_bus] publish skipped ({e.__class__.__name__}: {e}) - bus offline?")

    return hook


if __name__ == "__main__":
    # standalone smoke test: publish one synthetic result exactly as the hook would
    print("[adapter] smoke test - emitting one synthetic screen_activity observation")
    hook = make_hook()
    hook({
        "title": "Burp Suite - Repeater", "process": "java.exe", "tier": "deep",
        "task": "web app testing", "context": "editing an HTTP request in Repeater",
        "suggestion": "Send the modified request and diff the response length",
        "region": "center",
    })
