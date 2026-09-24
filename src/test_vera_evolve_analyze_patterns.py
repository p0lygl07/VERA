"""Regression test for vera_evolve.py's analyze_patterns() classifier.

Written after finding that analyze_patterns() classified ANY log row with
Executed=NO as a "fabrication" -- when a grep across every log_outcome()
call site in the codebase (vera_agent.py, vera_system_tools.py,
vera_kb_tools.py, vera_evolve_tools.py) turned up ~35 distinct Executed=NO
result strings, of which exactly ONE ("fabricated", from
verify_file_written/verify_tool_name in vera_verify.py) is an actual
fabrication signal. Every other Executed=NO row (not_found, exception,
timeout, user_declined, load_failed, ...) is a legitimate, honestly-
reported outcome. This test locks in the fix using the exact scenario that
triggered a real, live evolution proposal on 2026-09-22 misreporting
"7 fabrications" that were actually read_file/search_files calls on
nonexistent paths -- each one correctly caught by tool_read_file's own
`if not p.exists()` check, not a single hallucinated tool call among them.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import vera_evolve as ve


def _row(tool, executed, result, note="note"):
    return f"| 2026-09-22 | {tool} | {executed} | {result} | {note} |"


def test_not_found_and_declines_are_not_fabrications():
    """The exact bug: read_file/search_files hitting a nonexistent path,
    and a confirmation gate correctly declining, must NOT count as
    fabrications -- they're the system working as designed."""
    rows = (
        [_row("read_file", "YES", "success")] * 23
        + [_row("read_file", "NO", "not_found")] * 4
        + [_row("search_files", "YES", "success")] * 8
        + [_row("search_files", "NO", "not_found")] * 2
        + [_row("run_shell_command", "NO", "user_declined")]
        + [_row("write_file", "NO", "user_declined_self_mod")]
        + [_row("file_write", "NO", "fabricated",
                "claimed to write x.txt but file does not exist")]
    )
    patterns = ve.analyze_patterns({"execution": rows, "action": []})

    assert patterns["fabrications"] == ["file_write"], (
        f"expected exactly 1 real fabrication, got {patterns['fabrications']}"
    )
    assert sorted(patterns["failures"]) == sorted(["read_file"] * 4 + ["search_files"] * 2), (
        patterns["failures"]
    )
    assert sorted(patterns["declined"]) == sorted(["run_shell_command", "write_file"]), (
        patterns["declined"]
    )
    assert len(patterns["successes"]) == 31
    # blocked_tools is scoped to real fabrications vs successes -- read_file
    # and search_files must NOT appear here despite their not_found rows.
    assert patterns["blocked_tools"] == [] or all(
        "read_file" not in b and "search_files" not in b for b in patterns["blocked_tools"]
    )


def test_genuinely_unreliable_tool_still_flagged():
    """A tool that actually fabricates more than it succeeds must still
    show up in blocked_tools -- the fix narrows what counts as a
    fabrication, it doesn't blunt detection of a real one."""
    rows = (
        [_row("sketchy_tool", "NO", "fabricated", "claimed success, verification failed")] * 4
        + [_row("sketchy_tool", "YES", "success")] * 1
    )
    patterns = ve.analyze_patterns({"execution": rows, "action": []})
    assert patterns["fabrications"].count("sketchy_tool") == 4
    assert any("sketchy_tool" in b for b in patterns["blocked_tools"])


def test_declined_rows_never_leak_into_failures_or_fabrications():
    rows = [_row("run_recursive_task", "NO", "user_declined")] * 5
    patterns = ve.analyze_patterns({"execution": rows, "action": []})
    assert patterns["declined"] == ["run_recursive_task"] * 5
    assert patterns["failures"] == []
    assert patterns["fabrications"] == []


def test_empty_logs_produce_empty_patterns():
    patterns = ve.analyze_patterns({"execution": [], "action": []})
    assert patterns["fabrications"] == []
    assert patterns["failures"] == []
    assert patterns["declined"] == []
    assert patterns["successes"] == []
    assert patterns["blocked_tools"] == []


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    passed, failed = 0, 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {type(e).__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
