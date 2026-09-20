"""
VERA Execution Verifier
The core differentiator — verifies tool calls actually executed
before claiming success. Logs every outcome to execution_log.md.
"""

import os
import json
import datetime
import subprocess
from pathlib import Path

LOG_PATH = Path(__file__).parent.parent / "logs" / "execution_log.md"
VERA_ROOT = Path(__file__).parent.parent

def log_outcome(tool_name, executed, result, notes=""):
    date = datetime.date.today().isoformat()
    row = f"| {date} | {tool_name} | {'YES' if executed else 'NO'} | {result} | {notes} |\n"
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(row)

def verify_file_written(path, min_bytes=1):
    """Verify a file actually exists and has content after a write claim."""
    p = Path(path)
    if not p.exists():
        log_outcome("file_write", False, "fabricated", f"claimed to write {path} but file does not exist")
        return False, f"VERIFICATION FAILED: {path} does not exist"
    if p.stat().st_size < min_bytes:
        log_outcome("file_write", False, "empty", f"{path} exists but is empty")
        return False, f"VERIFICATION FAILED: {path} is empty"
    log_outcome("file_write", True, "success", f"verified {path} exists with {p.stat().st_size} bytes")
    return True, f"VERIFIED: {path} exists ({p.stat().st_size} bytes)"

def verify_command_output(command, expected_contains=None, timeout=30):
    """Run a command and verify it produces real output."""
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True,
            text=True, timeout=timeout
        )
        output = result.stdout + result.stderr
        if result.returncode != 0 and not output.strip():
            log_outcome("shell_command", False, "failed", f"command returned {result.returncode} with no output")
            return False, f"FAILED: command exited {result.returncode} with no output"
        if expected_contains and expected_contains not in output:
            log_outcome("shell_command", False, "unexpected_output",
                       f"expected '{expected_contains}' not found in output")
            return False, f"FAILED: expected output not found"
        log_outcome("shell_command", True, "success", f"command produced {len(output)} chars of output")
        return True, output.strip()
    except subprocess.TimeoutExpired:
        log_outcome("shell_command", False, "timeout", f"command timed out after {timeout}s")
        return False, f"FAILED: command timed out"
    except Exception as e:
        log_outcome("shell_command", False, "exception", str(e))
        return False, f"FAILED: {e}"

def verify_tool_name(tool_name, registered_tools):
    """Check tool name exists in registered schema before calling."""
    if tool_name not in registered_tools:
        log_outcome(tool_name, False, "fabricated",
                   f"tool '{tool_name}' not in registered schema — fabrication prevented")
        return False, f"VERA BLOCKED: '{tool_name}' is not a registered tool. Registered: {list(registered_tools.keys())}"
    return True, f"tool '{tool_name}' verified in schema"

def fabrication_check(claimed_action, actual_verification_fn, *args, **kwargs):
    """
    Wrapper that runs verification after any claimed action.
    If verification fails, the action is logged as fabricated.
    """
    verified, message = actual_verification_fn(*args, **kwargs)
    if not verified:
        print(f"\n[VERA] ⚠ FABRICATION DETECTED: {claimed_action}")
        print(f"[VERA] {message}")
        return False, message
    print(f"\n[VERA] ✓ VERIFIED: {claimed_action}")
    print(f"[VERA] {message}")
    return True, message


if __name__ == "__main__":
    # Self-test
    print("VERA Execution Verifier — self test")

    # Test 1: verify this file itself exists
    ok, msg = verify_file_written(__file__)
    print(f"Test 1 (self): {msg}")

    # Test 2: verify a non-existent file fails correctly
    ok, msg = verify_file_written("/nonexistent/path/fake.txt")
    print(f"Test 2 (fake): {msg}")

    # Test 3: verify a real command executes
    ok, msg = verify_command_output("echo VERA_TEST", expected_contains="VERA_TEST")
    print(f"Test 3 (echo): {msg}")

    # Test 4: tool name check
    registered = {"file_write": None, "shell_command": None, "skill_view": None}
    ok, msg = verify_tool_name("execute_command", registered)
    print(f"Test 4 (fake tool): {msg}")
    ok, msg = verify_tool_name("shell_command", registered)
    print(f"Test 5 (real tool): {msg}")