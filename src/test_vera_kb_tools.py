"""Offline tests for vera_kb_tools.py -- mocks subprocess.run (so no real
vera_tool.py/venv is needed) and input() (so no real y/N prompt blocks the
test). Run with a stub vera_verify module on the path (see conftest below)."""
import json
import sys
import types
from argparse import Namespace
from unittest.mock import patch

# Stub out vera_verify before import, since it's not on this machine.
stub = types.ModuleType("vera_verify")
stub.log_outcome = lambda *a, **kw: None
sys.modules["vera_verify"] = stub

import vera_kb_tools as kb


def fake_result(stdout_obj, returncode=0):
    return Namespace(returncode=returncode, stdout=json.dumps(stdout_obj), stderr="")


def test_status_reports_ok():
    with patch("vera_kb_tools.subprocess.run", return_value=fake_result({"ok": True, "total_claims": 3})), \
         patch("vera_kb_tools.KB_TRAINER_PYTHON") as fake_py:
        fake_py.exists.return_value = True
        result = kb.tool_kb_status()
    assert "VERIFIED" in result
    assert "total_claims" in result


def test_status_reports_failure_when_venv_missing():
    with patch("vera_kb_tools.KB_TRAINER_PYTHON") as fake_py:
        fake_py.exists.return_value = False
        result = kb.tool_kb_status()
    assert "FAILED" in result


def test_ingest_passes_through_and_reports_status():
    with patch("vera_kb_tools.subprocess.run",
               return_value=fake_result({"ok": True, "claim_id": "Earth|age|4.5b", "status": "established_true", "evidence_count": 2})), \
         patch("vera_kb_tools.KB_TRAINER_PYTHON") as fake_py:
        fake_py.exists.return_value = True
        result = kb.tool_kb_ingest("Earth", "age", "4.5b", [{"source": "t", "origin_id": "o1", "stance": "support", "strength": 1.0, "reliability": 0.9}])
    assert "established_true" in result
    assert "VERIFIED" in result


def test_train_sft_declines_without_confirmation():
    with patch("builtins.input", return_value="n"), \
         patch("vera_kb_tools.subprocess.run") as mock_run:
        result = kb.tool_kb_train_sft()
    assert result == "User declined."
    mock_run.assert_not_called()


def test_train_sft_runs_only_after_confirmation():
    with patch("builtins.input", return_value="y"), \
         patch("vera_kb_tools.subprocess.run", return_value=fake_result({"ok": True})) as mock_run, \
         patch("vera_kb_tools.KB_TRAINER_PYTHON") as fake_py:
        fake_py.exists.return_value = True
        result = kb.tool_kb_train_sft()
    assert "OK" in result
    # confirm the --confirm flag actually reached vera_tool.py's CLI
    called_args = mock_run.call_args[0][0]
    assert "--confirm" in called_args
    assert "train_sft" in called_args


def test_train_dpo_passes_force_base_flag_only_when_set():
    with patch("builtins.input", return_value="y"), \
         patch("vera_kb_tools.subprocess.run", return_value=fake_result({"ok": True})) as mock_run, \
         patch("vera_kb_tools.KB_TRAINER_PYTHON") as fake_py:
        fake_py.exists.return_value = True
        kb.tool_kb_train_dpo(force_base=True)
    called_args = mock_run.call_args[0][0]
    assert "--force-base" in called_args


def test_deploy_declines_without_confirmation_even_with_force_flag():
    # force_overwrite_active alone should never bypass the y/N gate
    with patch("builtins.input", return_value="n"), \
         patch("vera_kb_tools.subprocess.run") as mock_run:
        result = kb.tool_kb_deploy("merged/v2.gguf", "kb-trainer-v1", force_overwrite_active=True)
    assert result == "User declined."
    mock_run.assert_not_called()


def test_evaluate_needs_no_confirmation():
    # evaluate can only judge/record, never train/deploy -- no input() call at all
    with patch("builtins.input", side_effect=AssertionError("evaluate must not prompt")), \
         patch("vera_kb_tools.subprocess.run",
               return_value=fake_result({"ok": True, "pass_rate": 1.0, "promote": True, "reason": "clean", "active_version_now": "kb-trainer-v1"})), \
         patch("vera_kb_tools.KB_TRAINER_PYTHON") as fake_py:
        fake_py.exists.return_value = True
        result = kb.tool_kb_evaluate("kb-trainer-v1", parent=None)
    assert "PROMOTED" in result


def test_vera_tool_failure_surfaces_stderr_not_silent_success():
    with patch("vera_kb_tools.subprocess.run", return_value=fake_result({"ok": False, "error": "no anchor set"})), \
         patch("vera_kb_tools.KB_TRAINER_PYTHON") as fake_py:
        fake_py.exists.return_value = True
        result = kb.tool_kb_evaluate("bad-model")
    assert "FAILED" in result


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
