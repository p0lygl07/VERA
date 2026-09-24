#!/usr/bin/env python3
"""
VERA Self-Evolution Engine v2.1
VERA reads her own logs, identifies patterns, and PROPOSES changes to
herself. Applying a proposal is a separate, explicit, gated step -- never
automatic.

v2.1: analyze_patterns() classified ANY row with Executed=NO as a
"fabrication", full stop. Checked every log_outcome() call site across the
whole codebase (vera_agent.py, vera_system_tools.py, vera_kb_tools.py,
vera_evolve_tools.py) -- there are ~35 distinct Executed=NO result strings
in real use (not_found, exception, timeout, user_declined,
user_declined_self_mod, load_failed, no_entry_point, bad_result_json,
unknown_target, ...) and exactly ONE of them ("fabricated", from
verify_file_written / verify_tool_name in vera_verify.py) is an actual
fabrication signal. Every other Executed=NO row is a legitimate, correctly
-handled outcome: a real error being honestly reported, or a safety gate
correctly declining. Counting all of them as "fabrications" has been
silently inflating and mischaracterizing every evolution proposal this
engine has ever produced -- e.g. a proposal generated 2026-09-22 reported
"7 fabrications" that were actually read_file/search_files calls on
nonexistent paths, each one correctly caught and reported as an ERROR by
the tool itself (see tool_read_file's `if not p.exists()` check) -- not a
single hallucinated tool call among them. This version separates true
fabrications (the "fabricated" tag) from ordinary failures (any other
Executed=NO) and declines (a user or self-gate saying no, which is the
system working as intended, not a failure at all), so future proposals
diagnose what's actually happening instead of drowning real signal in
false positives.

REDESIGN NOTE (v1 -> v2): v1 auto-applied a proposal to memory/SOUL.md
(VERA's own live system prompt) after a 5-minute timer, cancellable only by
deleting the proposal file in that window. That is exactly the self-grading
+ ungated self-modification pattern the wxt recursive-training project's
eval gate exists to prevent -- and it directly contradicted SOUL.md's own
stated rule ("VERA can edit her own SOUL.md when Josh explicitly directs
it"). v2 removes the timer and the auto-apply path entirely. A proposal
is now ONLY ever applied by:
  - Josh running `python src/vera_evolve.py apply` himself, or
  - Josh telling VERA to apply it, which calls
    tool_apply_evolution_proposal() in vera_evolve_tools.py -- gated by
    the same y/N confirmation every other consequential tool uses.
There is no code path left in this file that writes to SOUL.md without
one of those two things having already happened.

Process:
  1. Read execution_log.md and action_log.md
  2. Identify failure patterns and success patterns
  3. Generate an improvement proposal via VERA's model
  4. Write the proposal to memory/evolution_proposals.md
  5. STOP. Applying it is a separate, explicit, human-confirmed step.

Run: python src/vera_evolve.py            (analyze + write proposal, stop)
Run: python src/vera_evolve.py apply      (apply the pending proposal now)
Do NOT put this on a scheduler that also auto-applies -- if you ever want
scheduled proposal *generation*, that's fine (it only writes a file for a
human to read), but scheduled *application* recreates the exact problem
this redesign removed.
"""

import json
import os
import sys
import datetime
import requests
from pathlib import Path

VERA_ROOT           = Path(__file__).parent.parent
LOG_PATH            = VERA_ROOT / "logs" / "execution_log.md"
ACTION_LOG          = VERA_ROOT / "logs" / "action_log.md"
SOUL_PATH           = VERA_ROOT / "memory" / "SOUL.md"
SKILLS_PATH         = VERA_ROOT / "skills"
PROPOSALS_PATH      = VERA_ROOT / "memory" / "evolution_proposals.md"
EVOLUTION_LOG       = VERA_ROOT / "logs" / "evolution_log.md"
OLLAMA_URL          = "http://localhost:11434/api/chat"
MODEL               = "qwen3.5:9b"


def read_recent_logs(max_lines=100):
    """Read recent entries from execution and action logs."""
    logs = {}

    for log_path, key in [(LOG_PATH, "execution"), (ACTION_LOG, "action")]:
        if log_path.exists():
            lines = log_path.read_text(encoding="utf-8").strip().split("\n")
            # Get last max_lines table rows
            rows = [l for l in lines if l.startswith("|") and "Date" not in l]
            logs[key] = rows[-max_lines:]
        else:
            logs[key] = []

    return logs


def analyze_patterns(logs):
    """Find patterns in logs — fabrications, failures, declines, successes,
    most common tools.

    Classification order matters -- checked most-specific-first:
      1. "fabricated" in result -> fabrications. This is the ONLY real
         hallucination signal: VERA claimed/verified an effect that
         independently checking the real world (a file, a command's
         output) proved false. Comes from verify_file_written /
         verify_tool_name in vera_verify.py, nowhere else.
      2. "declined" in result (user_declined, user_declined_self_mod) ->
         declined. A confirmation gate asked, Josh said no. That is the
         safety system working exactly as designed -- the opposite of a
         failure, and definitely not a fabrication.
      3. Executed == "NO", anything else -> failures. A real, honestly-
         reported error: not_found, exception, timeout, load_failed,
         no_entry_point, bad_result_json, and every other non-fabrication
         "no" outcome in the codebase. The tool ran (or correctly refused
         to invent a result) and told the truth about not succeeding.
      4. Executed == "YES" (or a stray "success"/"FAILED" text on a row
         without a clean YES/NO, kept as a fallback for older log rows) ->
         successes / failures respectively.
    """
    patterns = {
        "fabrications": [],
        "failures": [],
        "declined": [],
        "successes": [],
        "most_used_tools": {},
        "blocked_tools": [],
    }

    for row in logs.get("execution", []):
        parts = [p.strip() for p in row.split("|") if p.strip()]
        if len(parts) >= 4:
            tool = parts[1] if len(parts) > 1 else ""
            executed = parts[2] if len(parts) > 2 else ""
            result = parts[3] if len(parts) > 3 else ""
            result_l = result.lower()

            if "fabricated" in result_l:
                patterns["fabrications"].append(tool)
            elif "declined" in result_l:
                patterns["declined"].append(tool)
            elif executed == "NO":
                patterns["failures"].append(tool)
            elif executed == "YES":
                patterns["successes"].append(tool)
            elif "FAILED" in result.upper() or "ERROR" in result.upper():
                patterns["failures"].append(tool)
            elif "success" in result_l:
                patterns["successes"].append(tool)

            if tool:
                patterns["most_used_tools"][tool] = \
                    patterns["most_used_tools"].get(tool, 0) + 1

    # Find tools that genuinely fabricate more than they succeed --
    # scoped to real fabrications only, never ordinary failures/declines.
    for tool in set(patterns["fabrications"]):
        fab_count = patterns["fabrications"].count(tool)
        suc_count = patterns["successes"].count(tool)
        if fab_count > suc_count:
            patterns["blocked_tools"].append(f"{tool} (fabricated {fab_count}x)")

    return patterns


def generate_evolution_proposal(patterns, current_soul):
    """Ask VERA to analyze patterns and propose improvements."""
    pattern_summary = f"""
Fabricated tools (claimed/verified an effect that turned out false -- real hallucinations only): {patterns['fabrications'][:10]}
Failed tool calls (real errors honestly reported -- not fabrications): {patterns['failures'][:10]}
Declined by a confirmation gate (Josh or a safety gate said no -- working as intended): {patterns['declined'][:10]}
Most used tools: {sorted(patterns['most_used_tools'].items(), key=lambda x: -x[1])[:8]}
Consistently failing (fabricates more than it succeeds): {patterns['blocked_tools'][:5]}
Total successes recorded: {len(patterns['successes'])}
Total failures recorded: {len(patterns['failures'])}
Total declines recorded: {len(patterns['declined'])}
Total fabrications recorded: {len(patterns['fabrications'])}
"""

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are VERA analyzing your own performance logs to evolve and improve. "
                    "Be specific, actionable, and honest about failures. "
                    "Fabrications and failures are NOT the same thing and must not be "
                    "conflated: a fabrication is a claimed/verified effect that turned out "
                    "false (a real hallucination); a failure is a real error you honestly "
                    "reported (file not found, exception, timeout); a decline is a "
                    "confirmation gate correctly saying no. Only fabrications indicate you "
                    "are making things up -- failures and declines indicate the safety "
                    "systems are working. Propose concrete changes to skills or SOUL.md rules."
                )
            },
            {
                "role": "user",
                "content": (
                    f"Here are my recent performance patterns:\n{pattern_summary}\n\n"
                    f"My current SOUL.md starts with:\n{current_soul[:500]}\n\n"
                    "Propose exactly 3 specific improvements:\n"
                    "1. One change to SOUL.md rules based on failure patterns (only if "
                    "failures/fabrications actually indicate a real gap -- if the numbers "
                    "show the system is working as designed, say so instead of inventing "
                    "a rule to justify the exercise)\n"
                    "2. One new skill or skill improvement needed\n"
                    "3. One behavior change to reduce actual fabrications (not failures or "
                    "declines -- if fabrications are 0 or near-0, say the fabrication rate "
                    "is healthy rather than proposing a fix for a problem that isn't there)\n\n"
                    "Be specific — name the exact rule to add/change, not general advice."
                )
            }
        ],
        "stream": False,
        "options": {"temperature": 0.3, "num_ctx": 4096},
    }

    try:
        resp = requests.post(f"{OLLAMA_URL.rstrip('/api/chat')}/api/chat",
                            data=json.dumps(payload), timeout=120)
        resp.raise_for_status()
        return resp.json()["message"]["content"]
    except Exception as e:
        return f"[Evolution proposal unavailable: {e}]"


def write_proposal(proposal, patterns):
    """Write evolution proposal to file. Nothing about this applies it --
    apply_proposal() is a separate call, gated behind an explicit human
    decision (CLI 'apply' or the confirmed tool_apply_evolution_proposal())."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    content = (
        f"# VERA Evolution Proposal\n"
        f"## Generated: {timestamp}\n"
        f"## Status: PENDING -- nothing applies automatically\n\n"
        f"### Performance Summary\n"
        f"- Fabrications (real hallucinations only): {len(patterns['fabrications'])}\n"
        f"- Successes: {len(patterns['successes'])}\n"
        f"- Failures (real errors, honestly reported -- not fabrications): {len(patterns['failures'])}\n"
        f"- Declined (a confirmation gate correctly said no): {len(patterns['declined'])}\n"
        f"- Consistently failing tools: {', '.join(patterns['blocked_tools'][:3]) or 'none'}\n\n"
        f"### Proposed Improvements\n\n"
        f"{proposal}\n\n"
        f"---\n"
        f"*To apply: run `python src/vera_evolve.py apply`, or ask VERA to "
        f"apply it (she'll ask you to confirm y/N before touching SOUL.md).*\n"
        f"*To dismiss: run `python src/vera_evolve.py cancel`, or just leave "
        f"it -- it will sit here until you act on it either way.*\n"
    )

    PROPOSALS_PATH.write_text(content, encoding="utf-8")
    print(f"[VERA EVOLVE] Proposal written to {PROPOSALS_PATH}")
    print(f"[VERA EVOLVE] PENDING -- run 'apply' yourself when/if you want it applied.")
    return content


def apply_proposal():
    """Apply the current evolution proposal."""
    if not PROPOSALS_PATH.exists():
        print("[VERA EVOLVE] No proposal to apply.")
        return False

    proposal = PROPOSALS_PATH.read_text(encoding="utf-8")

    # Extract the proposed improvements section
    if "### Proposed Improvements" in proposal:
        improvements = proposal.split("### Proposed Improvements")[1].split("---")[0].strip()
    else:
        improvements = proposal

    # Append to SOUL.md as a learned rule
    if SOUL_PATH.exists():
        soul = SOUL_PATH.read_text(encoding="utf-8")
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        update = (
            f"\n\n----------------------------------------------------------------\n"
            f"SELF-EVOLUTION UPDATE: {timestamp}\n"
            f"----------------------------------------------------------------\n"
            f"{improvements[:1000]}\n"
        )
        SOUL_PATH.write_text(soul + update, encoding="utf-8")
        print(f"[VERA EVOLVE] Applied improvements to SOUL.md")

    # Log the evolution
    EVOLUTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(EVOLUTION_LOG, "a", encoding="utf-8") as f:
        f.write(f"\n## Evolution: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(improvements[:500] + "\n")

    # Archive the proposal
    archive_path = VERA_ROOT / "logs" / f"proposal_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.md"
    PROPOSALS_PATH.rename(archive_path)
    print(f"[VERA EVOLVE] Proposal archived to {archive_path}")
    return True


def run_evolution_cycle():
    """Full evolution cycle: read logs -> analyze -> propose -> wait -> apply."""
    print("=" * 60)
    print("VERA Self-Evolution Engine v1.0")
    print(f"Running: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # Read logs
    print("\n[VERA EVOLVE] Reading performance logs...")
    logs = read_recent_logs(max_lines=200)
    print(f"[VERA EVOLVE] Found {len(logs['execution'])} execution entries, "
          f"{len(logs['action'])} action entries")

    if not logs["execution"] and not logs["action"]:
        print("[VERA EVOLVE] No logs yet -- run VERA more to generate data.")
        return

    # Analyze patterns
    print("[VERA EVOLVE] Analyzing patterns...")
    patterns = analyze_patterns(logs)
    print(f"[VERA EVOLVE] Fabrications: {len(patterns['fabrications'])} | "
          f"Successes: {len(patterns['successes'])} | "
          f"Failures: {len(patterns['failures'])} | "
          f"Declined: {len(patterns['declined'])}")

    # Check if there's enough data to evolve meaningfully. Scoped to
    # fabrications + successes + failures (real signal about what
    # happened) -- deliberately excludes "declined", since a gate saying
    # no isn't evidence about VERA's own performance either way.
    total = len(patterns["fabrications"]) + len(patterns["successes"]) + len(patterns["failures"])
    if total < 5:
        print(f"[VERA EVOLVE] Only {total} data points -- need 5+ to evolve meaningfully.")
        print("[VERA EVOLVE] Keep using VERA to build the dataset.")
        return

    # Generate proposal
    print("[VERA EVOLVE] Generating evolution proposal...")
    current_soul = SOUL_PATH.read_text(encoding="utf-8") if SOUL_PATH.exists() else ""
    proposal = generate_evolution_proposal(patterns, current_soul)
    print("\n[VERA EVOLVE] PROPOSAL:")
    print("-" * 40)
    print(proposal)
    print("-" * 40)

    # Write the proposal and STOP. Applying it is a separate, explicit,
    # human-confirmed step (CLI 'apply', or tool_apply_evolution_proposal()
    # via VERA, which asks for y/N first) -- never automatic.
    write_proposal(proposal, patterns)

    print("\n[VERA EVOLVE] Evolution cycle complete. Proposal is PENDING -- nothing was applied.")


def main():
    if len(sys.argv) >= 2:
        cmd = sys.argv[1].lower()
        if cmd == "apply":
            apply_proposal()
        elif cmd == "status":
            if PROPOSALS_PATH.exists():
                print(PROPOSALS_PATH.read_text(encoding="utf-8"))
            else:
                print("[VERA EVOLVE] No pending proposal.")
        elif cmd == "cancel":
            if PROPOSALS_PATH.exists():
                PROPOSALS_PATH.unlink()
                print("[VERA EVOLVE] Proposal cancelled.")
            else:
                print("[VERA EVOLVE] No proposal to cancel.")
        elif cmd == "analyze":
            logs = read_recent_logs()
            patterns = analyze_patterns(logs)
            print(json.dumps({k: v for k, v in patterns.items()
                             if k != "most_used_tools"}, indent=2))
            print("\nMost used tools:",
                  sorted(patterns["most_used_tools"].items(), key=lambda x: -x[1])[:8])
    else:
        run_evolution_cycle()


if __name__ == "__main__":
    main()
