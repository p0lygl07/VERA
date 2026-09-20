import re
import sys
import datetime
from pathlib import Path

from vera_paths import VERA_ROOT, SKILLS_DIR, LIVE_FEED_LOG
from vera_verify import verify_file_written, log_outcome


def log(msg):
    """Standard logging function for tool registry"""
    LIVE_FEED_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LIVE_FEED_LOG, 'a', encoding='utf-8-sig') as f:
        f.write(f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] [TOOLS] {msg}\n")


def _infer_entry_point(code_content: str) -> str | None:
    match = re.search(r"^def (\w+)\(", code_content, re.MULTILINE)
    return match.group(1) if match else None


def forge_tool(name, code_content, description, entry_point=None):
    """
    Create a new skill: a folder VERA's existing skill system already
    understands (skills/<name>/SKILL.md, picked up by load_skills() and
    surfaced via skills_context()/read_skill()) plus the actual callable
    code (skills/<name>/<name>.py). This replaces the older flat
    skills/{name}.py convention, which load_skills() never scanned for --
    forge_tool used to create files the rest of VERA couldn't see.

    `entry_point` names the function inside code_content that run_skill()
    should call. If omitted, the first top-level `def` in code_content is
    used. `description` is required now (used to be missing entirely) --
    it's what shows up in skills_context() so the model actually knows
    what the skill does before reading its full source.
    """
    entry_point = entry_point or _infer_entry_point(code_content)
    if not entry_point:
        log(f"[ALERT]: forge_tool('{name}') given code with no detectable entry point")
        log_outcome("forge_tool", False, "no_entry_point", name)
        return None

    log(f"Creating skill: {name} (entry_point={entry_point})")

    skill_dir = SKILLS_DIR / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    module_path = skill_dir / f"{name}.py"
    skill_md_path = skill_dir / "SKILL.md"

    # Plain (non-f) string: {ts}/{msg} must reach the generated file as
    # literal placeholders for its own f-string, not be evaluated here.
    boilerplate = (
        "import sys, datetime\n"
        "from pathlib import Path\n\n"
        "sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))\n"
        "from vera_paths import LIVE_FEED_LOG\n\n"
        "def log(msg):\n"
        "    LIVE_FEED_LOG.parent.mkdir(parents=True, exist_ok=True)\n"
        "    with open(LIVE_FEED_LOG, 'a', encoding='utf-8-sig') as f:\n"
        "        ts = datetime.datetime.now().strftime('%H:%M:%S')\n"
        "        f.write(f\"\\n[{ts}] [SKILL] {msg}\")\n\n"
    )

    skill_md = (
        "---\n"
        f"name: {name}\n"
        f"description: {description}\n"
        f"entry_point: {entry_point}\n"
        "---\n\n"
        f"# {name}\n\n"
        f"{description}\n\n"
        f"Created by forge_tool. Call it with run_skill(name=\"{name}\", "
        "kwargs={...}) -- do not import or exec the .py file directly; "
        "run_skill routes it through the same sandbox the recursive "
        "engine uses.\n"
    )

    try:
        with open(module_path, 'w', encoding='utf-8-sig') as f:
            f.write(boilerplate + code_content)
        with open(skill_md_path, 'w', encoding='utf-8') as f:
            f.write(skill_md)
    except Exception as e:
        log(f"[ALERT]: failed to write skill '{name}': {e}")
        log_outcome("forge_tool", False, "exception", str(e))
        return None

    for p in (module_path, skill_md_path):
        verified, msg = verify_file_written(p, min_bytes=1)
        if not verified:
            log(f"[ALERT]: {msg}")
            log_outcome("forge_tool", False, "verification_failed", str(p))
            return None

    log(f"[VERA VERIFIED]: Created skill '{name}' at {skill_dir}")
    log_outcome("forge_tool", True, "success", f"{name} -> {skill_dir}")
    return str(skill_dir)


def register_skill(skill_name):
    """Check whether a skill's SKILL.md exists -- the same file load_skills() reads."""
    if (SKILLS_DIR / skill_name / "SKILL.md").exists():
        log(f"[VERA VERIFIED]: Skill '{skill_name}' is registered")
        return True
    else:
        log(f"[ALERT]: Skill '{skill_name}' not found in registry")
        return False


if __name__ == "__main__":
    # Test forge_tool capability
    test_code = '''def analyze_url(url):
    """Basic URL analysis placeholder"""
    print(f"Analyzing: {url}")'''

    result_path = forge_tool(
        "url_analyzer", test_code,
        description="Basic URL analysis placeholder skill.",
    )
    log(f"Forge successful at: {result_path}" if result_path else "Forge failed.")
