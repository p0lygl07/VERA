"""
vera_evolve_tools.py -- VERA tool wrappers around vera_evolve.py's
self-analysis engine, with the actual gating that v1 of that engine lacked.

Merged into SYSTEM_TOOLS / SYSTEM_TOOL_FUNCTIONS by vera_system_tools.py,
same pattern as vera_kb_tools.py / vera_actone_tasks.py.

Split mirrors "visible goals, gated action" (see the comment block above
tool_review_goals in this same file):
  - review_evolution_signals: read + analyze + write a proposal to
    memory/evolution_proposals.md. Never touches SOUL.md. No confirmation
    needed -- same risk profile as review_goals.
  - apply_evolution_proposal: the ONLY thing that can write to SOUL.md.
    Requires Josh's explicit y/N confirmation, same as run_shell_command /
    run_recursive_task / run_deliberation. This is what SOUL.md's own
    Section 9 rule ("VERA can edit her own SOUL.md when Josh explicitly
    directs it") actually requires -- v1 of vera_evolve.py violated that
    rule with an unattended 5-minute auto-apply timer; this is the fix.

Cross-loop guard (added once vera_kb_tools.py existed alongside this file):
wxt/recursive_training_safety.md names "VERA training or modifying herself
specifically" as a case its own gating was never designed for -- its
existing gates (kb_train_sft/kb_train_dpo's own y/N + eval_gate's
regression check) verify a MODEL is good; nothing verifies that a SOUL.md
proposal's REASONING about that model is honest. A proposal here could cite
"the new training run showed X" as justification for a persona change --
that is the self-grading failure mode recursive_training_safety.md was
written to keep out of the model-training path, walking in through the
persona-training path instead, laundered through two individually-gated
tools that don't know about each other. _mentions_training_claim() below
is the concrete circuit breaker: apply_evolution_proposal cannot make that
crossing silent, even though it can't make the underlying judgment for
Josh either.
"""

import re
from pathlib import Path

try:
    from vera_verify import log_outcome
except ImportError:
    def log_outcome(*args, **kwargs):
        pass

import vera_evolve as _evolve


_TRAINING_CLAIM_PATTERN = re.compile(
    r"kb_train|kb_deploy|kb_merge|train_sft|train_dpo|fine-?tun|LoRA|adapter|"
    r"training run|training result|the model (showed|learned|improved|now)",
    re.IGNORECASE,
)


def _mentions_training_claim(text: str) -> bool:
    """
    True if a proposal's text cites a training/fine-tuning result as part
    of its reasoning. Deliberately broad (keyword match, not semantic) --
    the goal is to make Josh look twice, not to silently decide the
    proposal is fine. False positives (a proposal that merely mentions
    kb_status in passing) just mean one extra line of caution; a false
    negative is the failure mode this exists to prevent, so it errs wide.
    """
    return bool(_TRAINING_CLAIM_PATTERN.search(text))


def _confirm(prompt: str) -> bool:
    print(f"\n[VERA CONFIRM] {prompt}", flush=True)
    return input("Allow? [y/N]: ").strip().lower() == "y"


def tool_review_evolution_signals():
    """
    Read execution_log.md and action_log.md, identify fabrication/failure/
    success patterns, and write a proposal for 3 specific improvements
    (a SOUL.md rule change, a skill improvement, a fabrication-reduction
    behavior change) to memory/evolution_proposals.md.

    Read + analyze + append-a-proposal-file only -- this NEVER touches
    SOUL.md and needs no confirmation, same reasoning as review_goals.
    Actually applying the proposal requires a separate, explicit call to
    apply_evolution_proposal, which asks Josh to confirm first. Call this
    when asked to review VERA's own recent performance or propose
    self-improvements -- not on a timer, and not to manufacture a proposal
    when there isn't enough data (fewer than 5 fabrication+success+failure
    data points yields a clear "not enough data yet" result, which is a
    valid outcome, not a failure). Note: "fabrications" here means real
    hallucinations only (an effect VERA claimed/verified that turned out
    false) -- not ordinary errors or declined confirmations, which
    analyze_patterns tracks separately as failures/declined.
    """
    logs = _evolve.read_recent_logs(max_lines=200)
    if not logs["execution"] and not logs["action"]:
        log_outcome("review_evolution_signals", True, "no_logs", "")
        return "OK: no execution/action log entries yet -- nothing to analyze."

    patterns = _evolve.analyze_patterns(logs)
    total = len(patterns["fabrications"]) + len(patterns["successes"]) + len(patterns["failures"])
    if total < 5:
        log_outcome("review_evolution_signals", True, "insufficient_data", str(total))
        return f"OK: only {total} data point(s) so far -- need 5+ to propose meaningfully. Nothing written."

    current_soul = _evolve.SOUL_PATH.read_text(encoding="utf-8") if _evolve.SOUL_PATH.exists() else ""
    proposal = _evolve.generate_evolution_proposal(patterns, current_soul)
    _evolve.write_proposal(proposal, patterns)

    if not _evolve.PROPOSALS_PATH.exists():
        log_outcome("review_evolution_signals", False, "no_file", "")
        return f"FAILED: proposal generation ran but {_evolve.PROPOSALS_PATH} does not exist afterward."

    log_outcome("review_evolution_signals", True, "success",
                f"fab={len(patterns['fabrications'])} suc={len(patterns['successes'])}")
    return (
        f"OK: proposal written to {_evolve.PROPOSALS_PATH} [VERA VERIFIED]\n\n{proposal}\n\n"
        "This is PENDING -- nothing was applied. Applying it requires a separate "
        "apply_evolution_proposal call, which will ask Josh to confirm first."
    )


def tool_apply_evolution_proposal():
    """
    Apply the current pending proposal in memory/evolution_proposals.md --
    appends its improvements to memory/SOUL.md (VERA's own live system
    prompt) and archives the proposal. This is the ONLY tool that can
    modify SOUL.md, and it ALWAYS requires Josh's explicit y/N confirmation
    first, no exceptions -- this directly implements SOUL.md's own rule
    that self-updates only happen "when Josh explicitly directs it."

    Only call this when Josh has actually said to apply the pending
    proposal (having presumably just seen it, e.g. from
    review_evolution_signals). Never call this speculatively or as a
    followup to generating a proposal in the same turn.

    If the proposal's own reasoning cites a training/fine-tuning result
    (a kb_train_sft/kb_train_dpo run, an adapter, "the model showed...")
    as justification, the confirmation prompt says so explicitly -- that
    is a self-grading risk (VERA's own persona changing on the strength of
    VERA's own training claims) that no amount of tool-level gating can
    catch on its own; only Josh independently checking the actual training
    result (the registry entry, the eval numbers) closes it. See
    wxt/recursive_training_safety.md.
    """
    if not _evolve.PROPOSALS_PATH.exists():
        log_outcome("apply_evolution_proposal", False, "no_proposal", "")
        return "FAILED: no pending proposal (memory/evolution_proposals.md does not exist). Run review_evolution_signals first."

    proposal_text = _evolve.PROPOSALS_PATH.read_text(encoding="utf-8")

    prompt = (
        "Apply the pending evolution proposal to memory/SOUL.md "
        "(VERA's own system prompt)? Full proposal:\n" + proposal_text[:1500]
    )
    if _mentions_training_claim(proposal_text):
        prompt = (
            "*** CAUTION: this proposal cites a training/fine-tuning result as "
            "part of its reasoning. Verify that claim independently first -- "
            "check the actual kb-trainer registry entry / eval_gate numbers "
            "yourself, don't take VERA's summary of them as ground truth. This "
            "is exactly the self-grading pattern recursive_training_safety.md "
            "was written to keep out of model retraining; applying it here "
            "would let it back in through VERA's own persona instead. ***\n\n"
            + prompt
        )

    if not _confirm(prompt):
        log_outcome("apply_evolution_proposal", False, "user_declined", "")
        return "User declined. Proposal remains pending."

    soul_before = _evolve.SOUL_PATH.read_text(encoding="utf-8") if _evolve.SOUL_PATH.exists() else ""
    success = _evolve.apply_proposal()
    if not success:
        log_outcome("apply_evolution_proposal", False, "apply_failed", "")
        return "FAILED: apply_proposal() reported failure -- see console output above."

    soul_after = _evolve.SOUL_PATH.read_text(encoding="utf-8") if _evolve.SOUL_PATH.exists() else ""
    if soul_after == soul_before:
        log_outcome("apply_evolution_proposal", False, "no_change", "")
        return "FAILED: apply_proposal() ran but SOUL.md content did not actually change."

    log_outcome("apply_evolution_proposal", True, "success", "")
    return (
        f"OK: proposal applied to {_evolve.SOUL_PATH} ({len(soul_after) - len(soul_before)} chars added) "
        f"[VERA VERIFIED]. Restart VERA for the change to take effect in her system prompt."
    )


EVOLVE_TOOLS = [
    {"type": "function", "function": {
        "name": "review_evolution_signals",
        "description": tool_review_evolution_signals.__doc__.strip(),
        "parameters": {"type": "object", "properties": {}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "apply_evolution_proposal",
        "description": tool_apply_evolution_proposal.__doc__.strip(),
        "parameters": {"type": "object", "properties": {}, "required": []},
    }},
]

EVOLVE_TOOL_FUNCTIONS = {
    "review_evolution_signals": tool_review_evolution_signals,
    "apply_evolution_proposal": tool_apply_evolution_proposal,
}
