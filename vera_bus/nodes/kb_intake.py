"""
kb_intake — Phase 4. The memory layer's ear on the bus.

Subscribes to Observations and folds them into the KB trainer's real claim store
(wxt/claims.py). This retires demo_subscriber: perception now becomes memory.

Mapping decision (the one real judgment call, made explicit so it's easy to change):
  a screen_activity observation ->
      Claim(subject=process, relation="user_activity", obj=activity_guess)
      + Evidence(source="screen_copilot", origin_id=observation_id,
                 stance="support", strength=confidence, reliability=SC_RELIABILITY)
Screen Copilot's guess is SOFT evidence (a vision model's read, not structured data),
so SC_RELIABILITY is deliberately modest: by claims.py's own gate math a single soft
source can't reach "established" alone — it needs corroboration. That's correct.

After upserting, it recomputes the gate via claims.status() and republishes a Claim
message onto the bus, so downstream (deliberation in Phase 5) can react to contested
claims. The bus Claim carries a coarse 4-value gate; the KB store keeps full fidelity.

Config via env:
  VERA_BUS_URL   default http://127.0.0.1:8768
  KB_MODULE_DIR  dir containing claims.py   (default: ../../wxt relative to Desktop)
  KB_DB_PATH     sqlite path                (default: <KB_MODULE_DIR>/kb.sqlite)
"""
from __future__ import annotations
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # vera_bus/
from client import BusClient  # noqa: E402

SC_RELIABILITY = 0.5   # trust assigned to a Screen Copilot activity guess (soft evidence)

# stopwords dropped when normalizing an activity's detail into a claim key,
# so "python dependency management via pip" and "python dependency management"
# resolve to the same claim instead of fragmenting.
_STOP = {"via", "the", "a", "an", "to", "of", "in", "on", "for", "with",
         "and", "or", "using", "use", "by", "from", "at", "as", "into"}


def normalize_activity(activity: str) -> str:
    """Copilot emits 'CATEGORY - detail'. Key the claim on
    category + the first 3 content words of the detail. Deterministic, no model
    calls; a clean seam to later swap in embedding-based clustering. The full
    original string is preserved in the evidence pointer, so nothing is lost.
    """
    if " - " in activity:
        category, detail = activity.split(" - ", 1)
    else:
        category, detail = activity, ""
    cat = " ".join(category.lower().split())
    toks = [t for t in "".join(c if c.isalnum() else " " for c in detail.lower()).split()
            if t not in _STOP]
    key_detail = " ".join(toks[:3])
    return f"{cat}: {key_detail}".strip().rstrip(":").strip()


def _load_kb():
    """Import the real claims.py. Path configurable; guarded so failure is legible."""
    kb_dir = os.environ.get("KB_MODULE_DIR")
    if not kb_dir:
        # default: Desktop/wxt, reached from Desktop/vera/vera_bus/nodes
        here = os.path.dirname(os.path.abspath(__file__))
        kb_dir = os.path.abspath(os.path.join(here, "..", "..", "..", "wxt"))
    if kb_dir not in sys.path:
        sys.path.insert(0, kb_dir)
    import claims  # noqa: E402
    return claims, kb_dir


# coarse gate for the bus Claim message <- claims.status()'s richer vocabulary
_GATE_MAP = {
    "candidate": "unresolved",
    "provisional": "unresolved",
    "contested": "contested",
    "established_true": "established",
    "established_false": "established",
    "stale": "stale",
}


def _observation_to_claim(claims, store, obs: dict):
    """Fold one screen_activity observation into the store. Returns the Claim or None."""
    p = obs.get("payload", {})
    activity = p.get("activity")
    if not activity:
        return None  # no activity guess -> nothing to assert
    subject = p.get("process") or p.get("window_title") or "unknown"
    obj = normalize_activity(activity)
    cid = f"{subject}|user_activity|{obj}"

    claim = store.load(cid)
    if claim is None:
        claim = claims.Claim(subject=subject, relation="user_activity", obj=obj,
                             ttl_days=1.0)  # activity is ephemeral -> expires
    ev = claims.Evidence(
        source="screen_copilot",
        origin_id=obs.get("id", f"obs-{int(time.time()*1000)}"),
        stance="support",
        strength=float(obs.get("confidence", 0.7)),
        reliability=SC_RELIABILITY,
        pointer={"activity_full": activity, "suggestion": p.get("suggestion"),
                 "tier": p.get("tier")},
    )
    claim.evidence.append(ev)
    store.save(claim)
    return claim


def _claim_to_bus_msg(claims, claim) -> dict:
    post = claims.posterior(claim)
    gate = _GATE_MAP.get(claims.status(claim), "unresolved")
    return {
        "kind": "claim",
        "id": claim.cid,
        "statement": f"{claim.subject} {claim.relation} {claim.obj}",
        "posterior": {"alpha": post.alpha, "beta": post.beta},
        "gate": gate,
        "evidence": [
            {"source": e.source, "weight": e.weight, "supports": e.stance == "support"}
            for e in claim.evidence
        ],
    }


def run(bus_url: str | None = None):
    claims, kb_dir = _load_kb()
    db_path = os.environ.get("KB_DB_PATH") or os.path.join(kb_dir, "kb.sqlite")
    store = claims.Store(db_path)
    bus = BusClient(bus_url or os.environ.get("VERA_BUS_URL", "http://127.0.0.1:8768"))
    print(f"[kb_intake] claims.py from {kb_dir}, db {db_path}")
    print("[kb_intake] listening for observations...")
    try:
        for cursor, msgs in bus.subscribe(kinds=["observation"]):
            for obs in msgs:
                if obs.get("type") != "screen_activity":
                    continue
                claim = _observation_to_claim(claims, store, obs)
                if claim is None:
                    continue
                bus_msg = _claim_to_bus_msg(claims, claim)
                try:
                    bus.publish(bus_msg)
                except Exception as e:
                    print(f"[kb_intake] claim publish skipped ({e.__class__.__name__})")
                print(f"[kb_intake] {claim.cid}  gate={bus_msg['gate']}  "
                      f"mean={claims.posterior(claim).mean:.2f}  "
                      f"mass={claims.posterior(claim).mass:.2f}")
    finally:
        store.close()


if __name__ == "__main__":
    run()
