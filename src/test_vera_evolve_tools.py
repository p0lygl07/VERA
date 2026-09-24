"""Offline test of the redesigned vera_evolve.py + vera_evolve_tools.py gating.
Runs against a real temp VERA_ROOT (real file I/O), with only the Ollama
HTTP call and input() mocked -- this exercises the actual code path, not a
reimplementation of it."""
import os
import shutil
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import patch

stub = types.ModuleType("vera_verify")
stub.log_outcome = lambda *a, **kw: None
sys.modules["vera_verify"] = stub

sys.path.insert(0, "/tmp/vera_build")
sys.path.insert(0, "/mnt/user-data/outputs/vera/src")


def make_tmp_vera_root():
    tmp = tempfile.mkdtemp()
    (Path(tmp) / "logs").mkdir()
    (Path(tmp) / "memory").mkdir()
    soul = Path(tmp) / "memory" / "SOUL.md"
    soul.write_text("# SOUL v3.0\nOriginal content.\n", encoding="utf-8")
    exec_log = Path(tmp) / "logs" / "execution_log.md"
    rows = "\n".join(
        f"| 2026-09-2{i%9} | some_tool | {'NO' if i % 3 == 0 else 'YES'} | "
        f"{'fabricated' if i % 3 == 0 else 'success'} | note |" for i in range(8)
    )
    exec_log.write_text("| Date | Tool | Executed | Result | Notes |\n" + rows, encoding="utf-8")
    return tmp


def test_review_writes_pending_proposal_never_touches_soul():
    tmp = make_tmp_vera_root()
    try:
        with patch.dict(sys.modules):
            import importlib
            os.chdir(tmp)
            (Path(tmp) / "src").mkdir(exist_ok=True)
            # vera_evolve.py resolves VERA_ROOT as Path(__file__).parent.parent,
            # so import it from a src/ subfolder of our tmp root.
            shutil.copy("/mnt/user-data/outputs/vera/src/vera_evolve.py", Path(tmp) / "src" / "vera_evolve.py")
            sys.path.insert(0, str(Path(tmp) / "src"))
            import vera_evolve
            importlib.reload(vera_evolve)
            import vera_evolve_tools
            importlib.reload(vera_evolve_tools)

            soul_before = vera_evolve.SOUL_PATH.read_text(encoding="utf-8")
            with patch("vera_evolve.generate_evolution_proposal", return_value="1. Do X\n2. Do Y\n3. Do Z"):
                result = vera_evolve_tools.tool_review_evolution_signals()

            soul_after = vera_evolve.SOUL_PATH.read_text(encoding="utf-8")
            assert soul_after == soul_before, "review must NEVER modify SOUL.md"
            assert vera_evolve.PROPOSALS_PATH.exists()
            assert "PENDING" in result
            assert "VERIFIED" in result
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_apply_declines_without_confirmation_and_soul_unchanged():
    tmp = make_tmp_vera_root()
    try:
        import importlib
        os.chdir(tmp)
        (Path(tmp) / "src").mkdir(exist_ok=True)
        shutil.copy("/mnt/user-data/outputs/vera/src/vera_evolve.py", Path(tmp) / "src" / "vera_evolve.py")
        sys.path.insert(0, str(Path(tmp) / "src"))
        import vera_evolve
        importlib.reload(vera_evolve)
        import vera_evolve_tools
        importlib.reload(vera_evolve_tools)

        with patch("vera_evolve.generate_evolution_proposal", return_value="1. Do X\n2. Do Y\n3. Do Z"):
            vera_evolve_tools.tool_review_evolution_signals()

        soul_before = vera_evolve.SOUL_PATH.read_text(encoding="utf-8")
        with patch("builtins.input", return_value="n"):
            result = vera_evolve_tools.tool_apply_evolution_proposal()
        soul_after = vera_evolve.SOUL_PATH.read_text(encoding="utf-8")

        assert result == "User declined. Proposal remains pending."
        assert soul_after == soul_before
        assert vera_evolve.PROPOSALS_PATH.exists(), "declined apply must leave the proposal pending, not consume it"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_apply_confirmed_actually_changes_soul_and_archives_proposal():
    tmp = make_tmp_vera_root()
    try:
        import importlib
        os.chdir(tmp)
        (Path(tmp) / "src").mkdir(exist_ok=True)
        shutil.copy("/mnt/user-data/outputs/vera/src/vera_evolve.py", Path(tmp) / "src" / "vera_evolve.py")
        sys.path.insert(0, str(Path(tmp) / "src"))
        import vera_evolve
        importlib.reload(vera_evolve)
        import vera_evolve_tools
        importlib.reload(vera_evolve_tools)

        with patch("vera_evolve.generate_evolution_proposal", return_value="1. Do X\n2. Do Y\n3. Do Z"):
            vera_evolve_tools.tool_review_evolution_signals()

        soul_before = vera_evolve.SOUL_PATH.read_text(encoding="utf-8")
        with patch("builtins.input", return_value="y"):
            result = vera_evolve_tools.tool_apply_evolution_proposal()
        soul_after = vera_evolve.SOUL_PATH.read_text(encoding="utf-8")

        assert "OK" in result and "VERIFIED" in result
        assert soul_after != soul_before
        assert "Do X" in soul_after
        assert not vera_evolve.PROPOSALS_PATH.exists(), "applied proposal should be archived (renamed), not left pending"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_review_with_insufficient_data_writes_nothing():
    tmp = tempfile.mkdtemp()
    try:
        (Path(tmp) / "logs").mkdir()
        (Path(tmp) / "memory").mkdir()
        (Path(tmp) / "memory" / "SOUL.md").write_text("# SOUL\n", encoding="utf-8")
        import importlib
        os.chdir(tmp)
        (Path(tmp) / "src").mkdir(exist_ok=True)
        shutil.copy("/mnt/user-data/outputs/vera/src/vera_evolve.py", Path(tmp) / "src" / "vera_evolve.py")
        sys.path.insert(0, str(Path(tmp) / "src"))
        import vera_evolve
        importlib.reload(vera_evolve)
        import vera_evolve_tools
        importlib.reload(vera_evolve_tools)

        result = vera_evolve_tools.tool_review_evolution_signals()
        assert "no execution/action log" in result or "OK" in result
        assert not vera_evolve.PROPOSALS_PATH.exists()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_caution_banner_shown_when_proposal_cites_training_result():
    """The cross-loop guard: a proposal reasoning from a kb_train_* result
    must make Josh look twice before it can touch SOUL.md, since no tool-
    level gate can judge whether that reasoning is honest -- only Josh
    checking the real training result can. See vera_evolve_tools.py's
    module docstring and wxt/recursive_training_safety.md."""
    tmp = make_tmp_vera_root()
    try:
        import importlib
        os.chdir(tmp)
        (Path(tmp) / "src").mkdir(exist_ok=True)
        shutil.copy("/mnt/user-data/outputs/vera/src/vera_evolve.py", Path(tmp) / "src" / "vera_evolve.py")
        sys.path.insert(0, str(Path(tmp) / "src"))
        import vera_evolve
        importlib.reload(vera_evolve)
        import vera_evolve_tools
        importlib.reload(vera_evolve_tools)

        proposal = ("Based on the recent kb_train_dpo run, the model showed "
                    "improved accuracy -- VERA should adopt a more confident tone.")
        with patch("vera_evolve.generate_evolution_proposal", return_value=proposal):
            vera_evolve_tools.tool_review_evolution_signals()

        captured = {}
        real_print = print
        def fake_print(*args, **kw):
            if args:
                captured["text"] = args[0]
            real_print(*args, **kw)
        with patch("builtins.print", side_effect=fake_print), patch("builtins.input", return_value="n"):
            vera_evolve_tools.tool_apply_evolution_proposal()

        assert "CAUTION" in captured.get("text", ""), "expected caution banner for a training-citing proposal"
        assert "kb_train_dpo" in captured["text"]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_no_caution_banner_for_ordinary_proposal():
    tmp = make_tmp_vera_root()
    try:
        import importlib
        os.chdir(tmp)
        (Path(tmp) / "src").mkdir(exist_ok=True)
        shutil.copy("/mnt/user-data/outputs/vera/src/vera_evolve.py", Path(tmp) / "src" / "vera_evolve.py")
        sys.path.insert(0, str(Path(tmp) / "src"))
        import vera_evolve
        importlib.reload(vera_evolve)
        import vera_evolve_tools
        importlib.reload(vera_evolve_tools)

        proposal = "Suggest VERA be more concise when explaining CTF lab setups."
        with patch("vera_evolve.generate_evolution_proposal", return_value=proposal):
            vera_evolve_tools.tool_review_evolution_signals()

        captured = {}
        real_print = print
        def fake_print(*args, **kw):
            if args:
                captured["text"] = args[0]
            real_print(*args, **kw)
        with patch("builtins.print", side_effect=fake_print), patch("builtins.input", return_value="n"):
            vera_evolve_tools.tool_apply_evolution_proposal()

        assert "CAUTION" not in captured.get("text", "")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    passed, failed = 0, 0
    orig_cwd = os.getcwd()
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {type(e).__name__}: {e}")
            failed += 1
        finally:
            os.chdir(orig_cwd)
    print(f"\n{passed} passed, {failed} failed")
