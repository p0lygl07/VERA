import sys
import datetime
from pathlib import Path

# recon_core.py lives at skills/bug-bounty-recon/recon_core.py -- three
# .parent calls up is VERA_ROOT, same convention forge_tool()'s generated
# skills use, so vera_paths is importable whether this runs standalone,
# imported by vera_agent.py, or invoked through run_skill()'s sandbox
# (which only puts the skill's own folder on sys.path, not VERA_ROOT).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from vera_paths import EXECUTION_LOG


def log_event(target, findings):
    """Append a recon/finding note for `target` to the shared execution log."""
    EXECUTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(EXECUTION_LOG, 'a', encoding="utf-8") as f:
        f.write(f"\n## [{timestamp}] Recon Task: {target}\n- Findings: {findings}\n")
    return {"logged": True, "target": target, "path": str(EXECUTION_LOG)}


if __name__ == "__main__":
    # Placeholder for automated Recon logic
    print("RECON_MODULE_ACTIVE")
