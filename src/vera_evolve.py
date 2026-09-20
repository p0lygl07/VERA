#!/usr/bin/env python3
"""
VERA Self-Evolution Engine v1.0
VERA reads her own logs, identifies patterns, and evolves herself.

Process:
  1. Read execution_log.md and action_log.md
  2. Identify failure patterns and success patterns
  3. Generate improvement proposals via VERA's model
  4. Write proposals to memory/evolution_proposals.md
  5. Auto-apply after APPLY_DELAY_SECONDS (default: 300 = 5 min)
     so Josh has time to cancel if needed

Run: python src/vera_evolve.py
Run on schedule: add to vera cron
"""

import json
import os
import sys
import time
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
APPLY_DELAY_SECONDS = 300  # 5 minutes before auto-applying
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
    """Find patterns in logs — failures, successes, most common tools."""
    patterns = {
        "fabrications": [],
        "failures": [],
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

            if executed == "NO" or "fabricated" in result.lower():
                patterns["fabrications"].append(tool)
            elif "FAILED" in result.upper() or "ERROR" in result.upper():
                patterns["failures"].append(tool)
            elif executed == "YES" or "success" in result.lower():
                patterns["successes"].append(tool)

            if tool:
                patterns["most_used_tools"][tool] = \
                    patterns["most_used_tools"].get(tool, 0) + 1

    # Find tools that fail more than they succeed
    for tool in set(patterns["fabrications"]):
        fab_count = patterns["fabrications"].count(tool)
        suc_count = patterns["successes"].count(tool)
        if fab_count > suc_count:
            patterns["blocked_tools"].append(f"{tool} (fabricated {fab_count}x)")

    return patterns


def generate_evolution_proposal(patterns, current_soul):
    """Ask VERA to analyze patterns and propose improvements."""
    pattern_summary = f"""
Fabricated tools (called but didn't execute): {patterns['fabrications'][:10]}
Failed tool calls: {patterns['failures'][:10]}
Most used tools: {sorted(patterns['most_used_tools'].items(), key=lambda x: -x[1])[:8]}
Consistently failing: {patterns['blocked_tools'][:5]}
Total successes recorded: {len(patterns['successes'])}
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
                    "Propose concrete changes to skills or SOUL.md rules."
                )
            },
            {
                "role": "user",
                "content": (
                    f"Here are my recent performance patterns:\n{pattern_summary}\n\n"
                    f"My current SOUL.md starts with:\n{current_soul[:500]}\n\n"
                    "Propose exactly 3 specific improvements:\n"
                    "1. One change to SOUL.md rules based on failure patterns\n"
                    "2. One new skill or skill improvement needed\n"
                    "3. One behavior change to reduce fabrications\n\n"
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
    """Write evolution proposal to file with auto-apply countdown."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    apply_at = (datetime.datetime.now() +
                datetime.timedelta(seconds=APPLY_DELAY_SECONDS)).strftime("%H:%M:%S")

    content = (
        f"# VERA Evolution Proposal\n"
        f"## Generated: {timestamp}\n"
        f"## Auto-applies at: {apply_at} (delete this file to cancel)\n\n"
        f"### Performance Summary\n"
        f"- Fabrications: {len(patterns['fabrications'])}\n"
        f"- Successes: {len(patterns['successes'])}\n"
        f"- Failures: {len(patterns['failures'])}\n"
        f"- Consistently failing tools: {', '.join(patterns['blocked_tools'][:3]) or 'none'}\n\n"
        f"### Proposed Improvements\n\n"
        f"{proposal}\n\n"
        f"---\n"
        f"*To cancel: delete this file before {apply_at}*\n"
        f"*To apply immediately: run: python src/vera_evolve.py apply*\n"
    )

    PROPOSALS_PATH.write_text(content, encoding="utf-8")
    print(f"[VERA EVOLVE] Proposal written to {PROPOSALS_PATH}")
    print(f"[VERA EVOLVE] Auto-applies at {apply_at} unless cancelled")
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


def wait_and_apply():
    """Wait APPLY_DELAY_SECONDS then apply if proposal still exists."""
    print(f"[VERA EVOLVE] Waiting {APPLY_DELAY_SECONDS}s before auto-applying...")
    print(f"[VERA EVOLVE] Delete {PROPOSALS_PATH.name} to cancel.")

    for remaining in range(APPLY_DELAY_SECONDS, 0, -10):
        if not PROPOSALS_PATH.exists():
            print("[VERA EVOLVE] Proposal cancelled by user.")
            return False
        time.sleep(10)
        if remaining % 60 == 0:
            print(f"[VERA EVOLVE] {remaining}s until auto-apply...")

    if PROPOSALS_PATH.exists():
        print("[VERA EVOLVE] Auto-applying evolution proposal...")
        return apply_proposal()
    return False


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
          f"Failures: {len(patterns['failures'])}")

    # Check if there's enough data to evolve meaningfully
    total = len(patterns["fabrications"]) + len(patterns["successes"])
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

    # Write and schedule auto-apply
    write_proposal(proposal, patterns)

    # Wait and apply
    wait_and_apply()

    print("\n[VERA EVOLVE] Evolution cycle complete.")


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
