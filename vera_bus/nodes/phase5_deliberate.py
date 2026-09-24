"""
phase5_deliberate — Phase 5. The deliberation layer: gives a stuck claim a
second, independent origin so it can actually resolve.

Watches Claim messages on the bus. When a claim is blocked from establishing
ONLY by lack of a second independent origin (mass + variance already satisfied,
n_origins < min_origins), it routes the claim's STATEMENT (text, not the
original screenshot) into the CONF chatroom via deliberate.run_deliberation().
The debate's verdict comes back as ONE new Evidence with a distinct origin_id,
which is what moves n_origins 1 -> 2 and lets claims.status() reach established.

Independence, honestly:
  - The debate reasons over the claim TEXT; the observation came from a VISION
    model reading pixels. Different evidence path -> errors less correlated.
  - The CONF roster (qwen3.5, qwen2.5-coder, qwythos) are DIFFERENT models from
    the copilot's vision models.
  - The whole debate contributes ONE origin, not one-per-participant. Three
    correlated LLMs are not three independent witnesses; treating them as one
    keeps n_origins honest.
  - This is still LLM-vs-LLM: a real second path, not an oracle. Stronger
    origins (external lookup, human confirm) slot in later as origin 3+.

Config via env:
  VERA_BUS_URL    default http://127.0.0.1:8768
  KB_MODULE_DIR   dir with claims.py    (default ../../wxt)
  KB_DB_PATH      sqlite path           (default <KB_MODULE_DIR>/kb.sqlite)
  CONF_DIR        dir with deliberate.py(default ../../CONF)
  DEBATE_COOLDOWN seconds between debates of the same claim (default 1800)
"""
from __future__ import annotations
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # vera_bus/
from client import BusClient  # noqa: E402

DEBATE_RELIABILITY = 0.6
COOLDOWN = float(os.environ.get("DEBATE_COOLDOWN", "1800"))


def _load_deps():
    here = os.path.dirname(os.path.abspath(__file__))
    kb_dir = os.environ.get("KB_MODULE_DIR") or os.path.abspath(
        os.path.join(here, "..", "..", "..", "wxt"))
    conf_dir = os.environ.get("CONF_DIR") or os.path.abspath(
        os.path.join(here, "..", "..", "..", "CONF"))
    for d in (kb_dir, conf_dir):
        if d not in sys.path:
            sys.path.insert(0, d)
    import claims  # noqa: E402
    import deliberate  # noqa: E402
    return claims, deliberate, kb_dir, conf_dir


def _worth_debating(claims, claim) -> bool:
    """True iff a single sensor has reported this claim repeatedly but it still
    has only one origin. Because origin-collapse caps a single source's mass
    below the establish threshold, the trigger is 'seen >=2 times, still
    single-origin' -- the point at which a second, independent opinion is what
    the claim is actually missing. The cooldown in run() bounds compute cost."""
    cfg = claims.GateConfig()
    p = claims.posterior(claim)
    gate = claims.status(claim, cfg)
    if gate not in ("candidate", "provisional"):
        return False  # established/stale = done; contested = different handling
    seen = len(claim.evidence)                 # raw reports, pre-collapse
    return seen >= 2 and p.n_origins < cfg.min_origins


def _parse_verdict(synthesis: dict) -> tuple[str, float]:
    """Return (stance, strength). stance in {'support','refute','abstain'}.
    The objective asks the resolution to OPEN with SUPPORTED/REFUTED/UNCLEAR."""
    res = (synthesis.get("resolution") or "").strip().upper()
    disagreement = (synthesis.get("disagreement") or "").strip()
    strength = 0.85 if len(disagreement) < 20 else 0.6  # consensus -> stronger
    if res.startswith("SUPPORTED"):
        return "support", strength
    if res.startswith("REFUTED"):
        return "refute", strength
    return "abstain", 0.0


def _debate_objective(statement: str) -> str:
    return (
        f"Evaluate whether this claim about the user's activity is true: "
        f"\"{statement}\". Begin your resolution with exactly one word — "
        f"SUPPORTED, REFUTED, or UNCLEAR — then briefly justify."
    )


def run(bus_url: str | None = None):
    claims, deliberate, kb_dir, conf_dir = _load_deps()
    db_path = os.environ.get("KB_DB_PATH") or os.path.join(kb_dir, "kb.sqlite")
    store = claims.Store(db_path)
    bus = BusClient(bus_url or os.environ.get("VERA_BUS_URL", "http://127.0.0.1:8768"))
    last_debate: dict[str, float] = {}  # cid -> ts, debounce
    print(f"[deliberate] claims from {kb_dir}, CONF from {conf_dir}, db {db_path}")
    print(f"[deliberate] listening for claims (cooldown {COOLDOWN:.0f}s)...")
    try:
        for cursor, msgs in bus.subscribe(kinds=["claim"]):
            for cmsg in msgs:
                cid = cmsg.get("id")
                claim = store.load(cid)
                if claim is None or not _worth_debating(claims, claim):
                    continue
                now = time.time()
                if now - last_debate.get(cid, 0) < COOLDOWN:
                    continue  # debated recently, let it be
                last_debate[cid] = now
                statement = cmsg.get("statement", cid)
                print(f"[deliberate] debating: {statement!r}")
                try:
                    result = deliberate.run_deliberation(
                        objective=_debate_objective(statement),
                        context=f"Claim id: {cid}. It has one soft source "
                                f"(a screen-vision model) and needs an independent check.",
                    )
                except Exception as e:
                    print(f"[deliberate] deliberation failed ({e.__class__.__name__}: {e})")
                    continue
                stance, strength = _parse_verdict(result.get("synthesis", {}))
                if stance == "abstain":
                    print(f"[deliberate] verdict UNCLEAR -> no evidence added")
                    continue
                ev = claims.Evidence(
                    source="chatroom_debate",
                    # all debates share one origin (a debate is one KIND of
                    # source): repeated debates collapse, so they can't inflate
                    # n_origins. This debate is origin #2; origin #3 must be a
                    # genuinely different source. transcript kept in pointer.
                    origin_id="chatroom_debate",
                    stance=stance,
                    strength=strength,
                    reliability=DEBATE_RELIABILITY,
                    pointer={"transcript": result.get("transcript_path")},
                )
                claim.evidence.append(ev)
                store.save(claim)
                new_gate = claims.status(claim)
                print(f"[deliberate] verdict {stance.upper()} (str={strength}) -> "
                      f"{cid}: gate now {new_gate}, "
                      f"mean={claims.posterior(claim).mean:.2f}, "
                      f"origins={claims.posterior(claim).n_origins}")
                # republish the updated claim so the loop sees the new state
                try:
                    p = claims.posterior(claim)
                    bus.publish({
                        "kind": "claim", "id": cid, "statement": statement,
                        "posterior": {"alpha": p.alpha, "beta": p.beta},
                        "gate": {"candidate": "unresolved", "provisional": "unresolved",
                                 "contested": "contested", "established_true": "established",
                                 "established_false": "established", "stale": "stale"}.get(new_gate, "unresolved"),
                        "evidence": [{"source": e.source, "weight": e.weight,
                                      "supports": e.stance == "support"} for e in claim.evidence],
                    })
                except Exception as e:
                    print(f"[deliberate] republish skipped ({e.__class__.__name__})")
    finally:
        store.close()


if __name__ == "__main__":
    run()
