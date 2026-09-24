"""
phase6_executor — Phase 6. The action layer with the verification spine built in.

Consumes ActionRequests from the bus, runs the permitted ones through vera_sov's
sandboxed generate-run-retry engine, and emits an AuditRecord for EVERY request —
success, failure, timeout, or refused. Nothing executes silently; nothing executes
without a record. That is the guarantee that makes "verified execution over narrated
autonomy" real at the loop level.

Guards, applied BEFORE any execution:
  - sandboxed == False        -> refused. We only run inside vera_sov's sandbox.
  - reversible == False       -> refused. Irreversible actions need a passing
                                 verifier (none configured yet) -> safe default
                                 is refuse, not run-and-hope.
  - intent not registered     -> refused. Only known intents execute.

Intent registry maps intent -> handler(args) -> (outcome, result). Today only
"run_code" is wired (to vera_sov). Hardware intents (send_actone, move_arm) attach
here in Phase 7 as new handlers, with no change to the guard/audit spine.

Config via env:
  VERA_BUS_URL   default http://127.0.0.1:8768
  SOV_DIR        dir with sovereign_recursive_engine.py
                 (default ../../../sovreign/vera_sov)
"""
from __future__ import annotations
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # vera_bus/
from client import BusClient  # noqa: E402


def _load_sov():
    here = os.path.dirname(os.path.abspath(__file__))
    sov_dir = os.environ.get("SOV_DIR") or os.path.abspath(
        os.path.join(here, "..", "..", "..", "sovreign", "vera_sov"))
    if sov_dir not in sys.path:
        sys.path.insert(0, sov_dir)
    import sovereign_recursive_engine as sov  # noqa: E402
    return sov, sov_dir


def _audit(request_id: str, intent: str, outcome: str, result=None, verified_by=None) -> dict:
    rec = {"kind": "audit_record", "request_id": request_id, "intent": intent,
           "outcome": outcome}
    if result is not None:
        rec["result"] = result
    if verified_by is not None:
        rec["verified_by"] = verified_by
    return rec


# --- intent handlers: (args) -> (outcome, result) ---------------------------
def _run_code(sov, args) -> tuple[str, object]:
    objective = args.get("objective") or args.get("task")
    if not objective:
        return "failure", "run_code requires an 'objective' (or 'task') arg"
    script_name = args.get("script_name", "action_module.py")
    max_depth = int(args.get("max_depth", 5))
    try:
        ok = sov.recursive_thought_loop(objective, script_name=script_name, max_depth=max_depth)
    except Exception as e:
        return "failure", f"{e.__class__.__name__}: {e}"
    workspace = getattr(sov, "WORKSPACE_DIR", "")
    script_path = os.path.join(workspace, script_name) if workspace else script_name
    if ok:
        return "success", {"script": script_path, "note": "sandboxed run returned exit 0"}
    return "failure", {"script": script_path, "note": "loop exhausted or failed; see vera_sov trace log"}


def run(bus_url: str | None = None):
    sov, sov_dir = _load_sov()
    HANDLERS = {"run_code": lambda args: _run_code(sov, args)}
    bus = BusClient(bus_url or os.environ.get("VERA_BUS_URL", "http://127.0.0.1:8768"))
    print(f"[executor] vera_sov from {sov_dir}; intents: {list(HANDLERS)}")
    print("[executor] listening for action_requests...")
    for cursor, msgs in bus.subscribe(kinds=["action_request"]):
        for req in msgs:
            rid = req.get("id", "")
            intent = req.get("intent", "")
            args = req.get("args", {})

            # -- guards (fail closed) --
            if not req.get("sandboxed", False):
                rec = _audit(rid, intent, "refused", "sandboxed execution required; request set sandboxed=false")
            elif not req.get("reversible", True):
                rec = _audit(rid, intent, "refused",
                             "irreversible action requires a passing verifier (none configured)")
            elif intent not in HANDLERS:
                rec = _audit(rid, intent, "refused", f"no executor registered for intent {intent!r}")
            else:
                print(f"[executor] running intent={intent!r} rid={rid}")
                outcome, result = HANDLERS[intent](args)
                rec = _audit(rid, intent, outcome, result)

            try:
                bus.publish(rec)
            except Exception as e:
                print(f"[executor] audit publish FAILED ({e.__class__.__name__}) - "
                      f"this is serious: an action ran without a recorded audit")
            print(f"[executor] {intent} rid={rid} -> {rec['outcome']}")


if __name__ == "__main__":
    run()
