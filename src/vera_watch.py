#!/usr/bin/env python3
"""
VERA Proactive Awareness Engine
Monitors active projects against alert thresholds.
Surfaces relevant information without being asked.
Speaks alerts aloud using VERA voice.

Run manually: python src/vera_watch.py
Update project: python src/vera_watch.py update <project_key>
"""

import json
import os
import sys
import datetime
import subprocess
import requests
from pathlib import Path

VERA_ROOT   = Path(__file__).parent.parent
MEMORY_PATH = VERA_ROOT / "memory"
ALERTS_LOG  = VERA_ROOT / "logs" / "alerts.md"
OLLAMA_URL  = "http://localhost:11434/api/chat"
MODEL       = "qwen3.5:9b"
PYTHON      = r"C:\Users\p0ly\AppData\Local\Programs\Python\Python311\python.exe"

THRESHOLDS = {
    "ping_identity_report": {
        "description": "Ping Identity bug bounty report #3797290 (HackerOne)",
        "idle_days": 7,
        "last_activity_file": MEMORY_PATH / "ping_identity_last_activity.txt",
        "default_start": "2026-06-01",
        "priority": "HIGH",
    },
    "vera_development": {
        "description": "VERA AI development -- no git commit",
        "idle_days": 3,
        "last_activity_file": MEMORY_PATH / "vera_last_commit.txt",
        "default_start": datetime.date.today().isoformat(),
        "priority": "HIGH",
    },
    "ctf_lab_build": {
        "description": "SNHUpers CTF lab build -- next lab due",
        "idle_days": 5,
        "last_activity_file": MEMORY_PATH / "ctf_last_build.txt",
        "default_start": datetime.date.today().isoformat(),
        "priority": "MEDIUM",
    },
    "uo_razor_scripts": {
        "description": "UO Outlands Razor scripting -- no changes",
        "idle_days": 7,
        "last_activity_file": MEMORY_PATH / "uo_last_script.txt",
        "default_start": datetime.date.today().isoformat(),
        "priority": "LOW",
    },
}


def get_last_activity(project_key):
    config = THRESHOLDS[project_key]
    activity_file = Path(config["last_activity_file"])
    if activity_file.exists():
        try:
            return datetime.date.fromisoformat(activity_file.read_text(encoding="utf-8").strip())
        except ValueError:
            pass
    return datetime.date.fromisoformat(config["default_start"])


def update_last_activity(project_key, date=None):
    if date is None:
        date = datetime.date.today()
    activity_file = Path(THRESHOLDS[project_key]["last_activity_file"])
    activity_file.parent.mkdir(parents=True, exist_ok=True)
    activity_file.write_text(date.isoformat(), encoding="utf-8")
    print(f"[VERA WATCH] Updated {project_key} last activity to {date}")


def check_vera_git_activity():
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%ci"],
            capture_output=True, text=True, cwd=str(VERA_ROOT)
        )
        if result.returncode == 0 and result.stdout.strip():
            date_str = result.stdout.strip()[:10]
            last_commit = datetime.date.fromisoformat(date_str)
            update_last_activity("vera_development", last_commit)
            return last_commit
    except Exception:
        pass
    return get_last_activity("vera_development")


def check_all_projects():
    alerts = []
    today = datetime.date.today()
    check_vera_git_activity()
    for project_key, config in THRESHOLDS.items():
        last_activity = get_last_activity(project_key)
        days_idle = (today - last_activity).days
        threshold = config["idle_days"]
        if days_idle >= threshold:
            alerts.append({
                "project": project_key,
                "description": config["description"],
                "days_idle": days_idle,
                "threshold": threshold,
                "priority": config["priority"],
                "last_activity": last_activity.isoformat(),
            })
    return alerts


def format_alerts(alerts):
    if not alerts:
        return "All projects within activity thresholds. No alerts."
    lines = [
        "# VERA Proactive Alerts",
        f"## {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]
    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    alerts.sort(key=lambda a: priority_order.get(a["priority"], 3))
    for alert in alerts:
        tag = {"HIGH": "[HIGH]", "MEDIUM": "[MED]", "LOW": "[LOW]"}.get(alert["priority"], "[?]")
        lines.append(f"{tag} {alert['priority']} -- {alert['description']}")
        lines.append(f"   Idle: {alert['days_idle']} days (threshold: {alert['threshold']} days)")
        lines.append(f"   Last activity: {alert['last_activity']}")
        lines.append("")
    return "\n".join(lines)


def save_alerts(formatted_alerts):
    ALERTS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(ALERTS_LOG, "a", encoding="utf-8") as f:
        f.write("\n\n" + formatted_alerts)


def generate_vera_summary(alerts):
    if not alerts:
        return "All clear -- no projects need attention right now."
    alert_text = format_alerts(alerts)
    try:
        payload = {
            "model": MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are VERA, Josh's proactive AI assistant. "
                        "Be direct and casual. No fluff. "
                        "One sentence per alert, one concrete next action each."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"Current project alerts:\n\n{alert_text}\n\n"
                        "Brief direct briefing. One sentence per alert, "
                        "one concrete next action each. "
                        "End with the single most important thing to do right now."
                    )
                }
            ],
            "stream": False,
            "options": {"temperature": 0.2, "num_ctx": 4096},
        }
        resp = requests.post(OLLAMA_URL, data=json.dumps(payload), timeout=120)
        resp.raise_for_status()
        return resp.json()["message"]["content"]
    except Exception as e:
        return f"[VERA AI briefing unavailable: {e}]\n\n{alert_text}"


def speak_briefing():
    """Speak the latest briefing aloud using VERA voice."""
    voice_script = Path(__file__).parent / "vera_voice.py"
    if voice_script.exists():
        try:
            subprocess.run([PYTHON, str(voice_script), "alert"], timeout=60)
        except Exception as e:
            print(f"[VERA WATCH] Voice error: {e}")
    else:
        print("[VERA WATCH] Voice module not found — skipping audio.")


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "update":
        project_key = sys.argv[2]
        if project_key in THRESHOLDS:
            update_last_activity(project_key)
            print(f"[VERA WATCH] Marked {project_key} as active today.")
        else:
            print(f"Unknown project: {project_key}")
            print(f"Valid: {list(THRESHOLDS.keys())}")
        return

    print("=" * 60)
    print("VERA Proactive Awareness Engine")
    print(f"Checking: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    alerts = check_all_projects()

    if not alerts:
        print("\nAll clear -- no projects need attention.")
    else:
        print(f"\n{len(alerts)} alert(s) detected:\n")
        formatted = format_alerts(alerts)
        print(formatted)
        save_alerts(formatted)
        print(f"[saved to {ALERTS_LOG}]")

        print("\n" + "-" * 40)
        print("VERA BRIEFING:")
        print("-" * 40)
        briefing = generate_vera_summary(alerts)
        print(briefing)

        briefing_path = MEMORY_PATH / "latest_briefing.md"
        briefing_path.write_text(
            f"# VERA Briefing\n## {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n{briefing}",
            encoding="utf-8"
        )
        print(f"\n[briefing saved to {briefing_path}]")

        # Speak the briefing aloud
        print("[VERA WATCH] Speaking briefing...")
        speak_briefing()

    print("\n[VERA WATCH] To mark a project as active today:")
    for key in THRESHOLDS:
        print(f"  python src/vera_watch.py update {key}")
    print("\n[VERA WATCH] Done.")


if __name__ == "__main__":
    main()
