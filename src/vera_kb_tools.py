"""
vera_kb_tools.py -- VERA's bridge into the recursive-training system
(claims KB + LoRA/DPO training + eval gate) at C:\\Users\\P01yG107\\Desktop\\wxt.

Merged into SYSTEM_TOOLS / SYSTEM_TOOL_FUNCTIONS by vera_system_tools.py,
same pattern as vera_actone_tasks.py's TASK_FUNCTIONS -- zero edits needed
to vera_agent.py.

Every function here shells out to that project's own vera_tool.py CLI
(JSON in, JSON out) rather than importing its modules directly, because
that project runs in its own venv (transformers/peft/bitsandbytes/torch --
a different, much heavier dependency set than VERA's own venv needs).

Gating mirrors vera_tool.py's own GATED_COMMANDS split, plus VERA's house
y/N confirmation pattern (matching run_shell_command / run_recursive_task /
run_deliberation) for anything that trains, merges, or deploys a model --
those are exactly the same commands vera_tool.py itself gates behind
--confirm, so this is a second, independent confirmation layer, not a
redundant one: Josh confirms once here (VERA's side), and that confirmation
is what causes this module to pass --confirm through to vera_tool.py.
Neither side can be skipped by the other.

See recursive_training_safety.md (in the wxt project) for the full
rationale. Short version: kb_evaluate is the ONLY command that can move a
model to "active," and it does so via that project's decide() gate logic
(pass-rate threshold + zero regressions vs. the previous version) -- never
by a flag anything in this file passes. This module cannot make that
decision any easier to short-circuit than the CLI already allows.
"""

import json
import subprocess
from pathlib import Path

try:
    from vera_verify import log_outcome
except ImportError:
    def log_outcome(*args, **kwargs):
        pass

KB_TRAINER_DIR = Path(r"C:\Users\P01yG107\Desktop\wxt")
KB_TRAINER_PYTHON = KB_TRAINER_DIR / "venv" / "Scripts" / "python.exe"

# Generous timeouts: training/merge/deploy are real GPU work on an 8GB card,
# not instantaneous calls. Read-only/KB-only commands get a short timeout
# because they should never legitimately take long.
_SHORT_TIMEOUT = 60
_LONG_TIMEOUT = 3600


def _run_vera_tool(args, timeout=_SHORT_TIMEOUT):
    """Shells out to wxt's vera_tool.py, returns (ok, parsed_json_or_None, raw_stdout, raw_stderr)."""
    if not KB_TRAINER_PYTHON.exists():
        return False, None, "", f"KB trainer venv not found at {KB_TRAINER_PYTHON}"
    cmd = [str(KB_TRAINER_PYTHON), "vera_tool.py"] + args
    try:
        result = subprocess.run(
            cmd, cwd=str(KB_TRAINER_DIR), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, None, "", f"vera_tool.py {' '.join(args)} timed out after {timeout}s"
    except Exception as e:
        return False, None, "", str(e)

    parsed = None
    try:
        parsed = json.loads(result.stdout)
    except Exception:
        pass
    ok = (result.returncode == 0) and (parsed is not None) and parsed.get("ok", False)
    return ok, parsed, result.stdout, result.stderr


def _confirm(prompt: str) -> bool:
    print(f"\n[VERA CONFIRM] {prompt}", flush=True)
    return input("Allow? [y/N]: ").strip().lower() == "y"


# --- read-only / KB-only (no y/N gate -- same reasoning as review_goals:
# nothing here trains, deploys, or overwrites a live model) -----------------

def tool_kb_status():
    """
    Report the recursive-training system's current state: claim counts by
    status (candidate/provisional/established/contested/stale), and which
    model version is currently active/promoted in its eval-gate registry.
    Read-only -- call this any time you need to know where that system
    stands before deciding what to do next (e.g. before proposing to train
    a new version, check whether one is already promoted).
    """
    ok, parsed, out, err = _run_vera_tool(["status"])
    log_outcome("kb_status", ok, "success" if ok else "failed", (parsed or err)[:200] if isinstance(parsed or err, str) else str(parsed)[:200])
    if not ok:
        return f"FAILED: could not get KB status. {err[:500] if err else out[:500]}"
    return f"OK: {json.dumps(parsed, indent=2)} [VERA VERIFIED]"


def tool_kb_ingest(subject, relation, obj, evidence):
    """
    Add evidence to a claim in the recursive-training KB. `evidence` must be
    a list of objects, each with source/origin_id/stance("support" or
    "refute")/strength(0-1)/reliability(0-1) -- e.g. from a web_search call
    you already made, or from another verified source you're citing.

    This tool does NOT go fetch evidence itself -- you (or a human) supply
    already-obtained evidence. That boundary is deliberate: a system that
    both decides what's true and goes finds "evidence" for it on its own is
    a self-confirming loop, which is exactly what this project's gates
    exist to prevent. Never call this with evidence you invented or
    inferred rather than actually observed from a real source.
    """
    data = json.dumps({"subject": subject, "relation": relation, "obj": obj, "evidence": evidence})
    ok, parsed, out, err = _run_vera_tool(["ingest", "--data", data])
    log_outcome("kb_ingest", ok, "success" if ok else "failed", f"{subject}|{relation}|{obj}")
    if not ok:
        return f"FAILED: {err[:500] if err else out[:500]}"
    return f"OK: claim '{parsed['claim_id']}' now status={parsed['status']} ({parsed['evidence_count']} evidence items) [VERA VERIFIED]"


def tool_kb_resolve(evidence_by_claim, batch_size=None):
    """
    Apply already-gathered evidence to specific provisional/contested claims
    (recycling uncertain claims toward resolution), re-checking their status
    and escalation. `evidence_by_claim` is an object mapping claim_id
    ("Subject|relation|object") to a list of evidence objects, same shape
    as kb_ingest's `evidence` argument. Like kb_ingest, this never fetches
    evidence on its own -- only applies what you supply.
    """
    data = {"evidence_by_claim": evidence_by_claim}
    if batch_size is not None:
        data["batch_size"] = batch_size
    ok, parsed, out, err = _run_vera_tool(["resolve", "--data", json.dumps(data)])
    log_outcome("kb_resolve", ok, "success" if ok else "failed", f"{len(evidence_by_claim)} claims")
    if not ok:
        return f"FAILED: {err[:500] if err else out[:500]}"
    escalations = parsed.get("escalations", [])
    note = f" ESCALATED (stuck + high-impact, needs your review): {escalations}" if escalations else ""
    return f"OK: resolved {len(parsed['resolved'])} claim(s).{note} [VERA VERIFIED]\n{json.dumps(parsed['resolved'], indent=2)}"


def tool_kb_dataset():
    """
    Rebuild the training dataset (SFT + DPO examples) and the eval gate's
    anchor set from the KB's current claims. Call this after ingesting or
    resolving claims and before proposing a training run -- it's what turns
    KB state into the files kb_train_sft/kb_train_dpo/kb_evaluate actually
    read. Idempotent and side-effect-free beyond writing those files; safe
    to call as often as you want.
    """
    ok, parsed, out, err = _run_vera_tool(["dataset"])
    log_outcome("kb_dataset", ok, "success" if ok else "failed", str(parsed.get("counts")) if parsed else err[:200])
    if not ok:
        return f"FAILED: {err[:500] if err else out[:500]}"
    return f"OK: {json.dumps(parsed, indent=2)} [VERA VERIFIED]"


def tool_kb_evaluate(model, parent=None):
    """
    Run the eval gate against a real Ollama model (already deployed via
    kb_deploy) and record the result in the training system's version
    registry. This is the ONLY tool that can promote a model to "active" --
    and it does so purely by that project's decide() logic (pass-rate
    threshold AND zero regressions vs. `parent`'s recorded results), never
    by any argument this tool accepts. Pass `parent` (the previous version's
    name) whenever one exists, so regressions actually get checked -- an
    evaluation with no parent only checks the absolute threshold. No y/N
    confirmation needed: this can only judge and record, never deploy,
    train, or overwrite anything on its own.
    """
    args = ["evaluate", "--model", model]
    if parent:
        args += ["--parent", parent]
    ok, parsed, out, err = _run_vera_tool(args, timeout=_LONG_TIMEOUT)
    log_outcome("kb_evaluate", ok, "success" if ok else "failed", model)
    if not ok:
        return f"FAILED: {err[:500] if err else out[:500]}"
    verdict = "PROMOTED" if parsed["promote"] else "BLOCKED"
    return (
        f"OK: {model} pass_rate={parsed['pass_rate']:.2f} -> {verdict} ({parsed['reason']}). "
        f"Active version is now: {parsed['active_version_now']} [VERA VERIFIED]"
    )


# --- gated: trains, merges, or deploys a model -- Josh's y/N required, and
# that confirmation is what causes --confirm to be passed to vera_tool.py --

def tool_kb_train_sft():
    """
    Runs SFT (LoRA) training on the current sft.jsonl (built by kb_dataset)
    from the base model, producing adapters/v1. This is real GPU work on
    Josh's 8GB card and can take several minutes. Requires Josh's explicit
    y/N confirmation, same as run_shell_command/run_recursive_task --
    training is exactly the kind of consequential, hard-to-interrupt action
    those tools already gate. A successful run does NOT make anything
    active -- the result still has to go through kb_deploy then
    kb_evaluate before it can be promoted.
    """
    if not _confirm("Run SFT (LoRA) training on the recursive-training system "
                     "(GPU work, several minutes, produces adapters/v1)."):
        log_outcome("kb_train_sft", False, "user_declined", "")
        return "User declined."
    ok, parsed, out, err = _run_vera_tool(["train_sft", "--confirm"], timeout=_LONG_TIMEOUT)
    log_outcome("kb_train_sft", ok, "success" if ok else "failed", "")
    if not ok:
        return f"FAILED: {(err or out)[-1500:]}"
    return f"OK: SFT training completed. [VERA VERIFIED]\n{out[-1000:]}"


def tool_kb_train_dpo(force_base=False):
    """
    Runs DPO training on the current dpo.jsonl (contested claims, built by
    kb_dataset), continuing from the currently ACTIVE/promoted adapter,
    producing the next adapter version. Refuses to run if no version is
    currently promoted, unless `force_base=True` -- that refusal is the
    actual mechanism stopping a chain from training on top of something
    that never passed the eval gate. Only pass force_base=True if Josh
    explicitly said to train from an unpromoted base anyway. Requires
    Josh's y/N confirmation, same as kb_train_sft.
    """
    if not _confirm("Run DPO training on the recursive-training system "
                     f"(GPU work{', forcing an unpromoted base' if force_base else ''})."):
        log_outcome("kb_train_dpo", False, "user_declined", "")
        return "User declined."
    args = ["train_dpo", "--confirm"]
    if force_base:
        args.append("--force-base")
    ok, parsed, out, err = _run_vera_tool(args, timeout=_LONG_TIMEOUT)
    log_outcome("kb_train_dpo", ok, "success" if ok else "failed", "")
    if not ok:
        return f"FAILED: {(err or out)[-1500:]}"
    return f"OK: DPO training completed. [VERA VERIFIED]\n{out[-1000:]}"


def tool_kb_merge(adapter, out_dir):
    """
    Merges a trained adapter (e.g. "adapters/v2") into the base model's
    weights, producing a standalone model directory (e.g. "merged/v2")
    ready for GGUF conversion. Real GPU/CPU work, a few minutes. Requires
    Josh's y/N confirmation.
    """
    if not _confirm(f"Merge adapter '{adapter}' into base weights, output to '{out_dir}'."):
        log_outcome("kb_merge", False, "user_declined", adapter)
        return "User declined."
    ok, parsed, out, err = _run_vera_tool(["merge", "--confirm", "--adapter", adapter, "--out", out_dir], timeout=_LONG_TIMEOUT)
    log_outcome("kb_merge", ok, "success" if ok else "failed", adapter)
    if not ok:
        return f"FAILED: {(err or out)[-1500:]}"
    return f"OK: merged {adapter} -> {out_dir}. [VERA VERIFIED]\n{out[-500:]}"


def tool_kb_deploy(gguf, name, force_overwrite_active=False):
    """
    Converts a merged model to GGUF (if not already) and runs
    `ollama create <name>` from it -- makes a candidate model actually
    runnable, but does NOT promote it. Refuses to overwrite the name of the
    currently active/promoted version unless `force_overwrite_active=True`
    -- deploy a candidate under its own distinct name (e.g. "kb-trainer-v3")
    and let kb_evaluate decide whether it should become active. Requires
    Josh's y/N confirmation.
    """
    if not _confirm(f"Deploy '{gguf}' as Ollama model '{name}'"
                     f"{' (OVERWRITING the currently active version)' if force_overwrite_active else ''}."):
        log_outcome("kb_deploy", False, "user_declined", name)
        return "User declined."
    args = ["deploy", "--confirm", "--gguf", gguf, "--name", name]
    if force_overwrite_active:
        args.append("--force-overwrite-active")
    ok, parsed, out, err = _run_vera_tool(args, timeout=_LONG_TIMEOUT)
    log_outcome("kb_deploy", ok, "success" if ok else "failed", name)
    if not ok:
        return f"FAILED: {(err or out)[-1500:]}"
    return f"OK: deployed Ollama model '{name}'. [VERA VERIFIED]\n{out[-500:]}"


KB_TOOLS = [
    {"type": "function", "function": {
        "name": "kb_status",
        "description": tool_kb_status.__doc__.strip(),
        "parameters": {"type": "object", "properties": {}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "kb_ingest",
        "description": tool_kb_ingest.__doc__.strip(),
        "parameters": {
            "type": "object",
            "properties": {
                "subject": {"type": "string"},
                "relation": {"type": "string"},
                "obj": {"type": "string"},
                "evidence": {
                    "type": "array",
                    "description": "List of {source, origin_id, stance, strength, reliability} objects",
                    "items": {"type": "object"},
                },
            },
            "required": ["subject", "relation", "obj", "evidence"],
        },
    }},
    {"type": "function", "function": {
        "name": "kb_resolve",
        "description": tool_kb_resolve.__doc__.strip(),
        "parameters": {
            "type": "object",
            "properties": {
                "evidence_by_claim": {"type": "object", "description": "claim_id -> list of evidence objects"},
                "batch_size": {"type": "integer", "description": "Max claims to process this call"},
            },
            "required": ["evidence_by_claim"],
        },
    }},
    {"type": "function", "function": {
        "name": "kb_dataset",
        "description": tool_kb_dataset.__doc__.strip(),
        "parameters": {"type": "object", "properties": {}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "kb_evaluate",
        "description": tool_kb_evaluate.__doc__.strip(),
        "parameters": {
            "type": "object",
            "properties": {
                "model": {"type": "string", "description": "Ollama model name to evaluate"},
                "parent": {"type": "string", "description": "Previous version's name, to check regressions against"},
            },
            "required": ["model"],
        },
    }},
    {"type": "function", "function": {
        "name": "kb_train_sft",
        "description": tool_kb_train_sft.__doc__.strip(),
        "parameters": {"type": "object", "properties": {}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "kb_train_dpo",
        "description": tool_kb_train_dpo.__doc__.strip(),
        "parameters": {
            "type": "object",
            "properties": {
                "force_base": {"type": "boolean", "default": False,
                               "description": "Allow training from an unpromoted base (only if Josh explicitly said to)"},
            },
            "required": [],
        },
    }},
    {"type": "function", "function": {
        "name": "kb_merge",
        "description": tool_kb_merge.__doc__.strip(),
        "parameters": {
            "type": "object",
            "properties": {
                "adapter": {"type": "string", "description": "Adapter dir, e.g. adapters/v2"},
                "out_dir": {"type": "string", "description": "Output dir, e.g. merged/v2"},
            },
            "required": ["adapter", "out_dir"],
        },
    }},
    {"type": "function", "function": {
        "name": "kb_deploy",
        "description": tool_kb_deploy.__doc__.strip(),
        "parameters": {
            "type": "object",
            "properties": {
                "gguf": {"type": "string", "description": "Path to the .gguf file"},
                "name": {"type": "string", "description": "Ollama model name to create"},
                "force_overwrite_active": {"type": "boolean", "default": False,
                                            "description": "Allow overwriting the currently active version's name"},
            },
            "required": ["gguf", "name"],
        },
    }},
]

KB_TOOL_FUNCTIONS = {
    "kb_status": tool_kb_status,
    "kb_ingest": tool_kb_ingest,
    "kb_resolve": tool_kb_resolve,
    "kb_dataset": tool_kb_dataset,
    "kb_evaluate": tool_kb_evaluate,
    "kb_train_sft": tool_kb_train_sft,
    "kb_train_dpo": tool_kb_train_dpo,
    "kb_merge": tool_kb_merge,
    "kb_deploy": tool_kb_deploy,
}
