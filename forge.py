import re
import sys
from pathlib import Path

from vera_paths import SKILLS_DIR
from vera_verify import verify_file_written


def _infer_entry_point(code_content: str):
    match = re.search(r"^def (\w+)\(", code_content, re.MULTILINE)
    return match.group(1) if match else None


def forge_tool(name, code_content, description, entry_point=None):
    """CLI twin of vera_tools.forge_tool -- same skills/<name>/{SKILL.md,<name>.py} package."""
    entry_point = entry_point or _infer_entry_point(code_content)
    if not entry_point:
        print("FORGE_FAILED: no top-level 'def' found in code_content to use as entry_point")
        return None

    skill_dir = SKILLS_DIR / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    module_path = skill_dir / f"{name}.py"
    skill_md_path = skill_dir / "SKILL.md"

    boilerplate = (
        "import sys, datetime\n"
        "from pathlib import Path\n\n"
        "sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))\n"
        "from vera_paths import LIVE_FEED_LOG\n\n"
        "def log(msg):\n"
        "    LIVE_FEED_LOG.parent.mkdir(parents=True, exist_ok=True)\n"
        "    with open(LIVE_FEED_LOG, 'a', encoding='utf-8-sig') as f:\n"
        "        ts = datetime.datetime.now().strftime('%H:%M:%S')\n"
        f"        f.write(f\"\\n[{{ts}}] [{name.upper()}] {{msg}}\")\n\n"
    )

    skill_md = (
        "---\n"
        f"name: {name}\n"
        f"description: {description}\n"
        f"entry_point: {entry_point}\n"
        "---\n\n"
        f"# {name}\n\n{description}\n\n"
        f"Created by forge.py. Call it with run_skill(name=\"{name}\", kwargs={{...}}).\n"
    )

    with open(module_path, 'w', encoding='utf-8-sig') as f:
        f.write(boilerplate + code_content)
    with open(skill_md_path, 'w', encoding='utf-8') as f:
        f.write(skill_md)

    for p in (module_path, skill_md_path):
        verified, msg = verify_file_written(p, min_bytes=1)
        if not verified:
            print(f"FORGE_FAILED: {msg}")
            return None

    print(f"FORGE_SUCCESS: {skill_dir}")
    return str(skill_dir)


if __name__ == "__main__":
    # Allows: python forge.py tool_name "description here" "code_here"
    if len(sys.argv) < 4:
        print("Usage: python forge.py <name> <description> <code_content> [entry_point]")
        sys.exit(1)
    name, description, content = sys.argv[1], sys.argv[2], sys.argv[3]
    entry_point = sys.argv[4] if len(sys.argv) > 4 else None
    forge_tool(name, content, description, entry_point)
