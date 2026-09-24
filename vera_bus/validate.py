"""
vera_bus.validate — dependency-free validation for the four bus message types.

Why hand-rolled instead of the `jsonschema` package: the envelopes are small and
fixed, and a zero-dependency validator means every node (desktop, Jetson, Pi5) runs
the same check with nothing to install. The JSON schema files in schemas/ remain the
canonical spec and the documentation; this module enforces the subset that matters at
runtime and stays deliberately strict on the envelope, open on the body.

Public API:
    validate(msg) -> msg            # raises ValidationError on any problem
    register_payload_validator(type_name, fn)   # opt-in strict body checks
"""
from __future__ import annotations
import re
import uuid
import time

SOURCE_RE = re.compile(r"^[a-z0-9_]+(\.[a-z0-9_]+)*$")


class ValidationError(ValueError):
    """Raised when a message fails envelope or payload validation."""


# --- per-type / per-intent body validators (opt-in; empty by default) ---------
# This is the flag from the design decision: bodies are OPEN until you drop a
# callable in here. Register one and that type's body becomes strict. Nothing
# else in the system changes.
_PAYLOAD_VALIDATORS: dict[str, callable] = {}


def register_payload_validator(type_name: str, fn) -> None:
    """fn(payload_dict) should raise ValidationError (or any Exception) if invalid."""
    _PAYLOAD_VALIDATORS[type_name] = fn


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise ValidationError(msg)


def _check_source(val) -> None:
    _require(isinstance(val, str) and bool(SOURCE_RE.match(val)),
             f"source must be a namespaced lowercase id, got {val!r}")


def _check_ts(val) -> None:
    _require(isinstance(val, int) and not isinstance(val, bool) and val >= 0,
             f"ts must be a non-negative int (epoch ms), got {val!r}")


def _validate_observation(m: dict) -> None:
    allowed = {"v", "kind", "id", "source", "ts", "type", "payload", "confidence"}
    _require(set(m) <= allowed, f"unexpected keys: {set(m) - allowed}")
    _check_source(m["source"])
    _check_ts(m["ts"])
    types = {"screen_activity", "object_detection", "network_event",
             "audio_transcript", "system_metric"}
    _require(m.get("type") in types, f"type must be one of {types}, got {m.get('type')!r}")
    _require(isinstance(m.get("payload"), dict), "payload must be an object")
    if "confidence" in m:
        c = m["confidence"]
        _require(isinstance(c, (int, float)) and not isinstance(c, bool) and 0 <= c <= 1,
                 f"confidence must be in [0,1], got {c!r}")


def _validate_claim(m: dict) -> None:
    allowed = {"v", "kind", "id", "statement", "posterior", "gate", "evidence", "ts"}
    _require(set(m) <= allowed, f"unexpected keys: {set(m) - allowed}")
    _require(isinstance(m.get("id"), str) and m["id"], "claim id must be a non-empty string")
    _require(isinstance(m.get("statement"), str) and m["statement"], "statement must be non-empty")
    p = m.get("posterior")
    _require(isinstance(p, dict) and set(p) == {"alpha", "beta"}, "posterior needs exactly alpha,beta")
    for k in ("alpha", "beta"):
        _require(isinstance(p[k], (int, float)) and not isinstance(p[k], bool) and p[k] > 0,
                 f"posterior.{k} must be > 0, got {p[k]!r}")
    gates = {"unresolved", "contested", "established", "stale"}
    _require(m.get("gate") in gates, f"gate must be one of {gates}, got {m.get('gate')!r}")
    _check_ts(m["ts"])
    for i, ev in enumerate(m.get("evidence", []) or []):
        _require(isinstance(ev, dict) and {"source", "weight", "supports"} <= set(ev),
                 f"evidence[{i}] needs source,weight,supports")
        _require(isinstance(ev["weight"], (int, float)) and ev["weight"] >= 0,
                 f"evidence[{i}].weight must be >= 0")
        _require(isinstance(ev["supports"], bool), f"evidence[{i}].supports must be bool")


def _validate_action_request(m: dict) -> None:
    allowed = {"v", "kind", "id", "source", "intent", "args", "sandboxed", "reversible", "ts"}
    _require(set(m) == allowed, f"action_request keys must be exactly {allowed}, got {set(m)}")
    _check_source(m["source"])
    _require(isinstance(m.get("intent"), str) and m["intent"], "intent must be non-empty")
    _require(isinstance(m.get("args"), dict), "args must be an object")
    _require(isinstance(m.get("sandboxed"), bool), "sandboxed must be bool")
    _require(isinstance(m.get("reversible"), bool), "reversible must be bool")
    _check_ts(m["ts"])


def _validate_audit_record(m: dict) -> None:
    allowed = {"v", "kind", "id", "request_id", "intent", "outcome", "result", "verified_by", "ts"}
    _require(set(m) <= allowed, f"unexpected keys: {set(m) - allowed}")
    _require(isinstance(m.get("request_id"), str) and m["request_id"], "request_id must be non-empty")
    outcomes = {"success", "failure", "refused", "timeout"}
    _require(m.get("outcome") in outcomes, f"outcome must be one of {outcomes}, got {m.get('outcome')!r}")
    _check_ts(m["ts"])


_DISPATCH = {
    "observation": _validate_observation,
    "claim": _validate_claim,
    "action_request": _validate_action_request,
    "audit_record": _validate_audit_record,
}


def validate(msg: dict) -> dict:
    """Validate a message in place and return it. Raises ValidationError on failure."""
    _require(isinstance(msg, dict), "message must be a dict")
    _require(msg.get("v") == 1, f"unsupported envelope version v={msg.get('v')!r} (this node speaks v=1)")
    kind = msg.get("kind")
    _require(kind in _DISPATCH, f"unknown kind {kind!r}; expected one of {set(_DISPATCH)}")
    _DISPATCH[kind](msg)
    # opt-in strict body check, keyed on observation.type (extendable to intents)
    if kind == "observation" and msg["type"] in _PAYLOAD_VALIDATORS:
        _PAYLOAD_VALIDATORS[msg["type"]](msg["payload"])
    return msg


def stamp(msg: dict) -> dict:
    """Fill in id and ts if the emitter left them out, then validate. Convenience for nodes."""
    msg.setdefault("v", 1)
    msg.setdefault("id", uuid.uuid4().hex)
    msg.setdefault("ts", int(time.time() * 1000))
    return validate(msg)
