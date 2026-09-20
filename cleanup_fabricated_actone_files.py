"""
cleanup_fabricated_actone_files.py

One-time cleanup: removes the three files VERA fabricated in this
session (a simulated, non-functional duplicate of the real, tested
ACTONE task system in vera_actone_tasks.py / vera_system_tools.py).

Run once from C:\\Users\\P01yG107\\Desktop\\vera:
    python cleanup_fabricated_actone_files.py

Prints what it's about to delete and asks for confirmation before
doing anything -- this only removes files, and only these three named,
specific ones. It will not touch vera_actone_tasks.py,
vera_system_tools.py, vera_actone_devices.py, or anything else real.
"""

from pathlib import Path

VERA_ROOT = Path(__file__).parent.resolve()

FILES_TO_REMOVE = [
    VERA_ROOT / "core" / "actone_task_wrapper.py",
    VERA_ROOT / "docs" / "ACTONE_TASKS.md",
    VERA_ROOT / "core" / "test_actone_wrapper.py",
]

print("=" * 60)
print("Cleanup: fabricated ACTONE files")
print("=" * 60)
print()
print("The following files were generated as a simulated, non-functional")
print("duplicate of the real ACTONE system and will be removed:")
print()

existing = [f for f in FILES_TO_REMOVE if f.exists()]
missing = [f for f in FILES_TO_REMOVE if not f.exists()]

for f in existing:
    print(f"  [FOUND]   {f}")
for f in missing:
    print(f"  [MISSING] {f} (already gone, nothing to do)")

if not existing:
    print("\nNothing to remove -- all three are already gone.")
else:
    print()
    answer = input(f"Delete these {len(existing)} file(s)? [y/N]: ").strip().lower()
    if answer == "y":
        for f in existing:
            f.unlink()
            print(f"  Deleted: {f}")
        print("\nDone.")
    else:
        print("\nCancelled -- no files were touched.")
