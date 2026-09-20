"""
One-time migration: strips the old hardcoded C:\\Users\\p0ly\\... paths out of
every script in the VERA project and points them at vera_paths.py instead.

Run this ONCE, from the VERA project root, after dropping vera_paths.py in
the same folder:

    python migrate_paths.py

What it does:
  1. Finds every .py/.bat file under the current folder (skips vera_env/, .git/)
  2. Reports every hardcoded C:\\Users\\p0ly... reference it finds
  3. For .bat files: does a direct string replace (old root -> new root)
  4. For .py files: does a direct string replace too, as a safe first pass --
     this gets things RUNNING again immediately. Swapping individual files
     over to `from vera_paths import ...` properly is the next step, done
     file-by-file since each one's import style differs slightly.

This script only touches the hardcoded-path strings. It does not touch any
other logic.
"""

import os
from pathlib import Path

OLD_ROOT = r"C:\Users\p0ly\Desktop\AI\VERA"
OLD_PYTHON = r"C:\Users\p0ly\AppData\Local\Programs\Python\Python311\python.exe"

NEW_ROOT = str(Path(__file__).resolve().parent)
NEW_PYTHON = os.popen("where python").read().strip().split("\n")[0] if os.name == "nt" else ""

SKIP_DIRS = {"vera_env", ".git", "__pycache__"}
EXTENSIONS = {".py", ".bat", ".yaml"}


SELF_PATH = Path(__file__).resolve()


def find_target_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            fpath = Path(dirpath) / fname
            if fpath.resolve() == SELF_PATH:
                continue  # never edit this script's own source
            if Path(fname).suffix in EXTENSIONS:
                yield fpath


def main():
    root = Path(__file__).resolve().parent
    print(f"VERA root detected as: {root}")
    print(f"Old hardcoded root:    {OLD_ROOT}")
    print(f"Replacing with:        {NEW_ROOT}\n")

    if not NEW_PYTHON:
        print("Could not auto-detect python.exe path via 'where python'.")
        print("Edit NEW_PYTHON at the top of this script manually, then re-run.\n")

    changed = []
    for f in find_target_files(root):
        try:
            text = f.read_text(encoding="utf-8")
        except Exception as e:
            print(f"  [SKIP] {f} (read error: {e})")
            continue

        new_text = text.replace(OLD_ROOT, NEW_ROOT)
        if NEW_PYTHON:
            new_text = new_text.replace(OLD_PYTHON, NEW_PYTHON)

        if new_text != text:
            f.write_text(new_text, encoding="utf-8")
            changed.append(f.relative_to(root))

    print(f"\nUpdated {len(changed)} file(s):")
    for c in changed:
        print(f"  - {c}")

    if not changed:
        print("  (none -- either already migrated, or paths didn't match exactly)")


if __name__ == "__main__":
    main()
