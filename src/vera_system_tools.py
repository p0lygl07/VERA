"""
vera_system_tools.py — VERA's system-tool extensions.

vera_agent.py already looks for SYSTEM_TOOLS / SYSTEM_TOOL_FUNCTIONS
here (see the try/except ImportError around line ~121 of vera_agent.py)
and merges them into ALL_TOOLS / REGISTERED_TOOLS / TOOL_FUNCTIONS
automatically. That means adding a capability here requires ZERO edits
to vera_agent.py itself -- it goes through the exact same
verify_tool_name() / call_tool() / dashboard-state / logging pipeline
every other tool already does.
"""

import os
import re
import sys
import json
import datetime
import importlib.util
from pathlib import Path

from vera_paths import VERA_ROOT, SKILLS_DIR

# vera_agent.py already inserts VERA_ROOT onto sys.path before importing
# this module, and vera_actone_secure.py / libactone_secure.dll /
# vera_actone_devices.py all live at VERA_ROOT (same folder as vera.bat),
# so these imports resolve without any extra path handling here.
from vera_actone_devices import get_outbound_channel, known_devices
from vera_actone_tasks import TASK_FUNCTIONS

try:
    from vera_verify import log_outcome
except ImportError:
    def log_outcome(*args, **kwargs):
        pass


LESSONS_PATH = VERA_ROOT / "memory" / "lessons_learned.md"


def tool_log_lesson(title, what_happened, root_cause, rule):
    """
    Append a structured, factual entry to memory/lessons_learned.md.

    This must only be called when Josh has explicitly confirmed a
    specific mistake happened and told VERA to log it -- never on
    VERA's own initiative, and never as a vehicle for free-form
    self-reflection. Each entry is a factual record (what happened,
    why, the concrete rule going forward), not a narrated experience.
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = (
        f"\n\n## [{timestamp}] {title}\n"
        f"**What happened:** {what_happened}\n"
        f"**Root cause:** {root_cause}\n"
        f"**Rule going forward:** {rule}\n"
    )
    try:
        LESSONS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LESSONS_PATH, "a", encoding="utf-8") as f:
            f.write(entry)
        log_outcome("log_lesson", True, "success", title)
        return f"OK: logged lesson '{title}' to {LESSONS_PATH} [VERA VERIFIED]"
    except Exception as e:
        log_outcome("log_lesson", False, "exception", str(e))
        return f"ERROR: failed to log lesson: {e}"


def tool_send_actone_command(target, command):
    """Broadcast an authenticated ACTONE command tone to a registered device."""
    channel = get_outbound_channel(target)
    if channel is None:
        log_outcome("send_actone_command", False, "unknown_target",
                     f"target={target}, known={known_devices()}")
        return f"ERROR: unknown ACTONE target '{target}'. Known devices: {known_devices()}"
    try:
        channel.send(command)
        log_outcome("send_actone_command", True, "sent", f"{target}: {command}")
        return f"OK: sent ACTONE command '{command}' to {target} [VERA VERIFIED]"
    except ValueError as e:
        # SecureChannel.send raises ValueError for an unknown command name
        log_outcome("send_actone_command", False, "bad_command", str(e))
        return f"ERROR: {e}"
    except Exception as e:
        log_outcome("send_actone_command", False, "exception", str(e))
        return f"ERROR: failed to send ACTONE command: {e}"


# ---------------------------------------------------------------------------
# Sandbox engine loader (shared by run_recursive_task and run_skill)
#
# The vera_sov sandbox is a SEPARATE project tree from VERA_ROOT (it lives
# under Desktop\sovreign, not under Desktop\vera), so it can't be imported
# the normal package way. Path is overridable via the VERA_RECURSIVE_SANDBOX
# environment variable so it isn't hardcoded in more than the one place
# below -- vera_tools.py's forge_tool() used to hardcode a stale path in
# two different spots that didn't even agree with each other; fixed
# separately, same root cause.
# ---------------------------------------------------------------------------

_DEFAULT_SANDBOX_DIR = r"C:\Users\P01yG107\Desktop\sovreign\vera_sov\sandbox"
_SANDBOX_DIR = Path(os.environ.get("VERA_RECURSIVE_SANDBOX", _DEFAULT_SANDBOX_DIR))
_ENGINE_MODULE_NAME = "sovereign_recursive_engine"
_RESULT_SENTINEL = "@@VERA_RESULT@@"

_engine_module_cache = None


def _load_engine_module():
    """Import sovereign_recursive_engine.py once and cache the module object."""
    global _engine_module_cache
    if _engine_module_cache is not None:
        return _engine_module_cache
    engine_path = _SANDBOX_DIR / f"{_ENGINE_MODULE_NAME}.py"
    if not engine_path.exists():
        raise FileNotFoundError(
            f"Sandbox engine not found at {engine_path}. "
            f"Set VERA_RECURSIVE_SANDBOX if it has moved."
        )
    spec = importlib.util.spec_from_file_location(_ENGINE_MODULE_NAME, engine_path)
    module = importlib.util.module_from_spec(spec)
    # Must register in sys.modules BEFORE exec_module: the engine module
    # defines @dataclass classes with string type annotations, and Python
    # 3.11's dataclass processing looks the module up via
    # sys.modules.get(cls.__module__) while resolving them -- skip this
    # and it crashes with "'NoneType' object has no attribute '__dict__'"
    # partway through exec_module, not at the call site, which makes it
    # look unrelated to loading. Found by actually running this path, not
    # just reading it.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _engine_module_cache = module
    return module


def tool_run_recursive_task(objective, max_attempts=5):
    """
    Hand a coding objective to the sandboxed generate-run-fix-retry engine
    (vera_sov/sandbox/sovereign_recursive_engine.py) instead of writing the
    code inline. Use this for a self-contained script that can be validated
    by actually running it (a monitor, a converter, a small utility) -- not
    for anything that needs to touch VERA's own files or real hardware.

    Runs model-generated code inside a Docker sandbox when Docker is
    available (no network, capped CPU/memory/pids), or in a clearly-logged
    unsandboxed fallback mode when it isn't -- see that module's README
    before relying on this for anything beyond a throwaway script.

    Requires Josh's explicit y/N confirmation before running, same as
    run_shell_command, because this can take several model-generation
    rounds and consumes the same shared 8GB VRAM budget VERA itself needs.
    """
    print(f"\n[VERA CONFIRM] Run recursive code-generation task (up to {max_attempts} attempts):"
          f"\n  {objective}", flush=True)
    answer = input("Allow? [y/N]: ").strip().lower()
    if answer != "y":
        log_outcome("run_recursive_task", False, "user_declined", objective)
        return "User declined."

    try:
        engine_module = _load_engine_module()
    except Exception as e:
        log_outcome("run_recursive_task", False, "load_failed", str(e))
        return f"ERROR: could not load recursive engine: {e}"

    try:
        engine = engine_module.RecursiveEngine(max_attempts=max_attempts)
        success = engine.run(objective)
    except Exception as e:
        log_outcome("run_recursive_task", False, "exception", str(e))
        return f"ERROR: recursive engine raised: {e}"

    # Read the engine's own scoreboard rather than trusting the boolean alone --
    # same "verify, don't narrate" rule as every other tool in this file.
    scoreboard_path = _SANDBOX_DIR / "workspace" / "scoreboard.jsonl"
    last_entry = None
    try:
        if scoreboard_path.exists():
            lines = scoreboard_path.read_text(encoding="utf-8").strip().splitlines()
            if lines:
                last_entry = json.loads(lines[-1])
    except Exception:
        pass

    trace_path = _SANDBOX_DIR / "workspace" / "recursive_trace.log"

    if success and last_entry and last_entry.get("result") == "success":
        log_outcome("run_recursive_task", True, "success", objective)
        return (
            f"OK: recursive engine succeeded in {last_entry.get('attempt')} attempt(s) "
            f"using {last_entry.get('mode')} mode. Trace: {trace_path} [VERA VERIFIED]"
        )

    reason = last_entry.get("result") if last_entry else "unknown"
    log_outcome("run_recursive_task", False, reason, objective)
    last_stderr = (last_entry or {}).get("stderr", "")
    suggestion = (
        " If this looks like a real design ambiguity rather than a simple bug "
        "(e.g. it converges on different broken approaches each attempt), "
        "consider run_deliberation with this objective and the stderr above "
        "as context -- that's grounded in what actually happened here, not "
        "a fresh guess." if last_stderr else ""
    )
    return (
        f"FAILED: recursive engine did not reach a clean run (last status: {reason}). "
        f"Full trace: {trace_path}"
        + (f"\nLast error:\n{last_stderr[:800]}" if last_stderr else "")
        + suggestion
    )


def _parse_skill_frontmatter(skill_md_text: str) -> dict:
    meta = {}
    in_frontmatter = False
    for line in skill_md_text.splitlines():
        if line.strip() == "---":
            if in_frontmatter:
                break
            in_frontmatter = True
            continue
        if in_frontmatter and ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return meta


def _build_skill_runner(module_name: str, entry_point: str) -> str:
    # Plain-string lines (not f-strings) so the literal {} / {'ok': ...}
    # dict syntax below reaches the generated runner file untouched --
    # only module_name/entry_point are meant to be filled in here.
    return (
        "import sys, os, json\n"
        "sys.path.insert(0, os.environ['VERA_SKILL_DIR'])\n"
        f"from {module_name} import {entry_point}\n"
        "kwargs = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}\n"
        "try:\n"
        f"    result = {entry_point}(**kwargs)\n"
        "    print('" + _RESULT_SENTINEL + "' + json.dumps({'ok': True, 'result': result}))\n"
        "except Exception as e:\n"
        "    print('" + _RESULT_SENTINEL + "' + json.dumps({'ok': False, 'error': str(e)}))\n"
        "    sys.exit(1)\n"
    )


def tool_run_skill(name, kwargs=None):
    """
    Execute a skill forged by forge_tool() (skills/<name>/SKILL.md +
    skills/<name>/<name>.py) by calling its declared entry_point function
    with the given keyword arguments. Runs through the SAME sandbox as
    run_recursive_task (Docker, no network, capped resources -- or the
    clearly-logged host-fallback mode if Docker isn't set up), rather than
    importing and calling the skill in-process. A forged skill's code was
    written by a model, not reviewed line by line, so it gets the same
    isolation model-generated code from run_recursive_task gets -- no
    special trust just because it has a name and a SKILL.md.

    kwargs and the function's return value must be JSON-serializable.
    Returns [VERA VERIFIED] only if the sandboxed call actually completed
    and returned a result -- an exception inside the skill is reported as
    FAILED, not swallowed into a fabricated success.
    """
    skill_dir = SKILLS_DIR / name
    skill_md_path = skill_dir / "SKILL.md"
    module_path = skill_dir / f"{name}.py"

    if not skill_md_path.exists() or not module_path.exists():
        log_outcome("run_skill", False, "not_found", name)
        return f"ERROR: skill '{name}' not found (expected {skill_md_path} and {module_path})"

    meta = _parse_skill_frontmatter(skill_md_path.read_text(encoding="utf-8"))
    entry_point = meta.get("entry_point")
    if not entry_point:
        log_outcome("run_skill", False, "no_entry_point", name)
        return f"ERROR: {skill_md_path} has no entry_point in its frontmatter"

    try:
        engine_module = _load_engine_module()
    except Exception as e:
        log_outcome("run_skill", False, "load_failed", str(e))
        return f"ERROR: could not load sandbox engine: {e}"

    runner_code = _build_skill_runner(name, entry_point)
    runner_path = engine_module.WORKSPACE_DIR / f"skill_runner_{name}.py"
    engine_module.WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    runner_path.write_text(runner_code, encoding="utf-8")

    sandbox = engine_module.build_sandbox()
    is_docker = isinstance(sandbox, engine_module.DockerSandbox)
    container_skill_dir = "/workspace/skill"
    result = sandbox.run(
        runner_path,
        timeout=engine_module.EXEC_TIMEOUT_SECONDS,
        argv=[json.dumps(kwargs or {})],
        env={"VERA_SKILL_DIR": container_skill_dir if is_docker else str(skill_dir)},
        extra_mounts={str(skill_dir): container_skill_dir} if is_docker else None,
    )

    if result.timed_out:
        log_outcome("run_skill", False, "timeout", name)
        return f"FAILED: skill '{name}' timed out."

    sentinel_line = next(
        (line for line in result.stdout.splitlines() if line.startswith(_RESULT_SENTINEL)),
        None,
    )
    if sentinel_line is None:
        log_outcome("run_skill", False, "no_result", f"stderr: {result.stderr[:500]}")
        return f"FAILED: skill '{name}' produced no result. stderr: {result.stderr[:500]}"

    try:
        payload = json.loads(sentinel_line[len(_RESULT_SENTINEL):])
    except json.JSONDecodeError as e:
        log_outcome("run_skill", False, "bad_result_json", str(e))
        return f"FAILED: skill '{name}' result was not valid JSON: {e}"

    if payload.get("ok"):
        log_outcome("run_skill", True, "success", f"{name} -> {result.mode}")
        return f"OK ({result.mode} mode): {json.dumps(payload['result'])} [VERA VERIFIED]"

    log_outcome("run_skill", False, "skill_exception", payload.get("error", "unknown"))
    return f"FAILED: skill '{name}' raised: {payload.get('error', 'unknown error')}"


# ---------------------------------------------------------------------------
# Deliberation (CONF chat-room roster, applied to a concrete question)
#
# CONF (Desktop\CONF) is a separate project -- the browser-based multi-model
# chat room. deliberate.py there is a headless entry point that reuses its
# participants.py/router.py but runs a capped, synchronous round on a real
# objective instead of an open-ended chat. Every call here needs a concrete
# question; there is no way to invoke this for open-ended self-reflection --
# that framing is what VERA's rebuild notes trace the earlier hallucination
# problems to, so it's not a shape this tool offers.
# ---------------------------------------------------------------------------

_DEFAULT_CONF_DIR = r"C:\Users\P01yG107\Desktop\CONF"
_CONF_DIR = Path(os.environ.get("VERA_CONF_DIR", _DEFAULT_CONF_DIR))
_DELIBERATIONS_INDEX = VERA_ROOT / "memory" / "deliberations.md"

_conf_module_cache = None


def _load_conf_module():
    global _conf_module_cache
    if _conf_module_cache is not None:
        return _conf_module_cache
    deliberate_path = _CONF_DIR / "deliberate.py"
    if not deliberate_path.exists():
        raise FileNotFoundError(
            f"deliberate.py not found at {deliberate_path}. Set VERA_CONF_DIR if it has moved."
        )
    # CONF's own modules (participants.py, router.py) are imported by
    # deliberate.py via plain `import participants` / `import router` --
    # that only resolves if CONF_DIR is actually on sys.path, unlike the
    # sandbox engine loader which is fully self-contained in one file.
    conf_dir_str = str(_CONF_DIR)
    if conf_dir_str not in sys.path:
        sys.path.insert(0, conf_dir_str)
    spec = importlib.util.spec_from_file_location("deliberate", deliberate_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _conf_module_cache = module
    return module


def tool_run_deliberation(objective, max_turns=8, context=None):
    """
    Run a bounded, multi-model deliberation on a concrete question or
    decision, using the CONF chat room's existing roster (Qwen, Cipher,
    Wyth -- each with their own persona) as different perspectives, then
    extract a factual resolution.

    Compose `objective` and `context` from what you're actually working on:
    a task you're mid-way through, a decision it hinges on, a failed
    run_recursive_task attempt's real error output, your own reasoning so
    far on why you're stuck. `context` is that grounding material -- pass
    the real error/task text, not a paraphrase. This is how a genuine
    ambiguity or decision point in real work gets resolved; it is NOT a way
    to reflect on VERA's own state, nature, or growth in the abstract --
    that framing is what VERA's rebuild notes trace the earlier
    hallucination problems to, and this tool has no mode for it. If you
    don't have a concrete task or failure behind the question, that's a
    sign this isn't the right tool for it.

    Requires Josh's explicit y/N confirmation, same as run_shell_command
    and run_recursive_task -- this makes up to max_turns+1 Ollama calls
    against the same shared VRAM budget.

    Every run is written to memory/deliberations/<timestamp>_<slug>.md
    (full transcript + synthesis + the context it was grounded in) and
    indexed as one line in memory/deliberations.md. Returns
    [VERA VERIFIED] only after confirming that transcript file actually
    exists on disk.
    """
    print(f"\n[VERA CONFIRM] Run deliberation (up to {max_turns} turns) on:"
          f"\n  {objective}"
          + (f"\n  (grounded in: {context[:200]}{'...' if len(context) > 200 else ''})" if context else ""),
          flush=True)
    answer = input("Allow? [y/N]: ").strip().lower()
    if answer != "y":
        log_outcome("run_deliberation", False, "user_declined", objective)
        return "User declined."

    try:
        conf_module = _load_conf_module()
    except Exception as e:
        log_outcome("run_deliberation", False, "load_failed", str(e))
        return f"ERROR: could not load CONF deliberation module: {e}"

    try:
        result = conf_module.run_deliberation(
            objective, max_turns=max_turns, context=context,
            output_dir=str(VERA_ROOT / "memory" / "deliberations"),
        )
    except Exception as e:
        log_outcome("run_deliberation", False, "exception", str(e))
        return f"ERROR: deliberation raised: {e}"

    transcript_path = Path(result["transcript_path"])
    if not transcript_path.exists():
        log_outcome("run_deliberation", False, "no_transcript", objective)
        return f"FAILED: deliberation ran but no transcript was written to {transcript_path}."

    synthesis = result["synthesis"]
    resolution = synthesis.get("resolution", "")

    try:
        _DELIBERATIONS_INDEX.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(_DELIBERATIONS_INDEX, "a", encoding="utf-8") as f:
            f.write(
                f"\n\n## [{timestamp}] {objective}\n"
                f"**Resolution:** {resolution}\n"
                f"**Next step:** {synthesis.get('next_step', '')}\n"
                f"**Full transcript:** {transcript_path}\n"
            )
    except Exception:
        pass  # index is a convenience; the real record is the transcript file itself

    log_outcome("run_deliberation", True, "success", objective)
    return (
        f"OK: deliberation completed in {len(result['turns'])} turns. "
        f"Resolution: {resolution} "
        f"Next step: {synthesis.get('next_step', '')} "
        f"Full transcript: {transcript_path} [VERA VERIFIED]"
    )


# ---------------------------------------------------------------------------
# Goals (visible goals, gated action)
#
# VERA proposes what it thinks matters most next by scanning REAL signals
# already produced by its own gated work -- recurring run_recursive_task
# failures (scoreboard.jsonl), unactioned run_deliberation next_steps
# (memory/deliberations.md), and repeated lessons_learned.md root causes.
# This never executes anything: it only reads existing records and writes
# a proposal to memory/goals.md. Any actual work toward a goal still has
# to go through run_shell_command / run_recursive_task / run_skill /
# run_deliberation, each with its own y/N gate -- there is no path from
# "goal proposed" to "goal acted on" that skips Josh. This is the direct
# implementation of "visible goals, gated action": VERA can decide WHAT it
# thinks is necessary, Josh decides what actually happens. It is
# deliberately NOT a loop, a scheduler, or anything that fires on its own --
# it runs when review_goals is called, same as every other tool here.
# ---------------------------------------------------------------------------

GOALS_PATH = VERA_ROOT / "memory" / "goals.md"


def _scan_recursive_failures(limit=5):
    """Group scoreboard.jsonl entries by objective; surface ones with 2+
    failed attempts logged where the most recent attempt still isn't a
    success -- a real, repeated failure, not a one-off."""
    scoreboard_path = _SANDBOX_DIR / "workspace" / "scoreboard.jsonl"
    signals = []
    if not scoreboard_path.exists():
        return signals
    try:
        lines = scoreboard_path.read_text(encoding="utf-8").strip().splitlines()
    except Exception:
        return signals
    by_objective = {}
    for line in lines:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        obj = entry.get("objective", "unknown")
        by_objective.setdefault(obj, []).append(entry)
    for obj, entries in by_objective.items():
        failures = [e for e in entries if e.get("result") != "success"]
        last = entries[-1]
        if len(failures) >= 2 and last.get("result") != "success":
            signals.append({
                "type": "recurring_failure",
                "title": f"Unresolved recursive task: {obj[:80]}",
                "why": f"{len(failures)} failed attempt(s) logged, most recent status '{last.get('result')}'",
                "source": obj,
            })
    return signals[:limit]


def _scan_deliberation_next_steps(limit=5):
    """Pull the most recent distinct 'Next step' lines out of
    memory/deliberations.md -- conclusions VERA already reached through a
    gated deliberation that haven't necessarily been acted on since."""
    signals = []
    if not _DELIBERATIONS_INDEX.exists():
        return signals
    text = _DELIBERATIONS_INDEX.read_text(encoding="utf-8")
    entries = re.findall(
        r"## \[([^\]]+)\] (.+?)\n\*\*Resolution:\*\* (.*?)\n\*\*Next step:\*\* (.*?)\n",
        text,
    )
    seen = set()
    for timestamp, objective, resolution, next_step in reversed(entries):
        next_step = next_step.strip()
        if not next_step or next_step.lower() in seen:
            continue
        seen.add(next_step.lower())
        signals.append({
            "type": "deliberation_next_step",
            "title": next_step[:100],
            "why": f"Concluded from deliberation on '{objective.strip()[:80]}' ({timestamp})",
            "source": objective.strip(),
        })
        if len(signals) >= limit:
            break
    return signals


def _scan_lesson_patterns(limit=5):
    """Surface lessons_learned.md root causes that repeat -- the rule
    written down after the first incident may not have stuck."""
    signals = []
    if not LESSONS_PATH.exists():
        return signals
    text = LESSONS_PATH.read_text(encoding="utf-8")
    root_causes = re.findall(r"\*\*Root cause:\*\* (.*?)\n", text)
    counts = {}
    for cause in root_causes:
        key = cause.strip().lower()[:60]
        if key:
            counts[key] = counts.get(key, 0) + 1
    for key, count in counts.items():
        if count >= 2:
            signals.append({
                "type": "lesson_pattern",
                "title": f"Recurring root cause: {key}",
                "why": f"Same root cause logged {count} times in lessons_learned.md -- may not be sticking",
                "source": "lessons_learned.md",
            })
    return signals[:limit]


def tool_review_goals(max_goals=5):
    """
    Scan real signals from VERA's own gated work -- recurring
    run_recursive_task failures, unactioned run_deliberation next_steps,
    and repeated lessons_learned.md root causes -- and write a prioritized
    list of proposed goals to memory/goals.md.

    This ONLY reads existing records and appends a proposal. It never
    executes anything and never calls run_shell_command / run_recursive_task
    / run_skill / run_deliberation itself, so it needs no y/N confirmation --
    nothing consequential happens here. This is the "visible goals" half of
    the design, not the "gated action" half: every goal proposed still
    requires a separate, explicit call to one of the gated tools (each with
    its own confirmation prompt) to actually act on it.

    Call this when asked to review priorities or figure out what's worth
    working on next -- not on a timer, and not as a way to manufacture work.
    If nothing has failed twice, no deliberation has concluded with an
    unactioned next step, and no lesson has repeated, finding nothing is a
    valid, correct outcome.
    """
    signals = (
        _scan_recursive_failures()
        + _scan_deliberation_next_steps()
        + _scan_lesson_patterns()
    )
    if not signals:
        log_outcome("review_goals", True, "no_signals", "")
        return ("OK: reviewed recursive-task, deliberation, and lesson records -- "
                "nothing recurring or unresolved enough to propose as a goal right now.")

    signals = signals[:max_goals]
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    entries_written = []
    try:
        GOALS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(GOALS_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n\n# Reviewed {timestamp}\n")
            for i, sig in enumerate(signals, 1):
                goal_id = f"G-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{i}"
                f.write(
                    f"\n## [{goal_id}] {sig['title']} (status: PROPOSED)\n"
                    f"**Why:** {sig['why']}\n"
                    f"**Signal:** {sig['type']}\n"
                    f"**Source:** {sig['source']}\n"
                    f"**Proposed:** {timestamp}\n"
                )
                entries_written.append(goal_id)
    except Exception as e:
        log_outcome("review_goals", False, "exception", str(e))
        return f"ERROR: failed to write {GOALS_PATH}: {e}"

    if not GOALS_PATH.exists():
        log_outcome("review_goals", False, "no_file", "")
        return f"FAILED: wrote goals but {GOALS_PATH} does not exist afterward."

    log_outcome("review_goals", True, "success", f"{len(entries_written)} goals proposed")
    summary = "\n".join(f"- [{gid}] {sig['title']}" for gid, sig in zip(entries_written, signals))
    return (
        f"OK: proposed {len(entries_written)} goal(s) from real signals, appended to {GOALS_PATH} "
        f"[VERA VERIFIED]\n{summary}\n\n"
        "None of these were acted on. Actually working one requires a separate, "
        "explicit run_shell_command / run_recursive_task / run_skill / run_deliberation "
        "call -- each still gated by Josh's y/N confirmation."
    )


def tool_update_goal_status(goal_id, status, note=None):
    """
    Update a goal's status line in memory/goals.md (PROPOSED -> ACCEPTED,
    IN_PROGRESS, DONE, or DISMISSED) and optionally append a short factual
    note explaining the change.

    Only call this when Josh has explicitly told you a goal's status
    changed -- he decided to work on it, dropped it, or it's actually done.
    This is bookkeeping only: it does not start, stop, or affect any real
    work, and must never be used to record progress that didn't happen.
    """
    valid_statuses = {"PROPOSED", "ACCEPTED", "IN_PROGRESS", "DONE", "DISMISSED"}
    if status not in valid_statuses:
        return f"ERROR: status must be one of {', '.join(sorted(valid_statuses))}."
    if not GOALS_PATH.exists():
        log_outcome("update_goal_status", False, "no_file", goal_id)
        return f"ERROR: {GOALS_PATH} does not exist yet -- run review_goals first."

    text = GOALS_PATH.read_text(encoding="utf-8")
    header_pattern = re.compile(rf"(## \[{re.escape(goal_id)}\] .*?)\(status: [A-Z_]+\)")
    if not header_pattern.search(text):
        log_outcome("update_goal_status", False, "not_found", goal_id)
        return f"ERROR: goal id '{goal_id}' not found in {GOALS_PATH}."

    new_text = header_pattern.sub(lambda m: f"{m.group(1)}(status: {status})", text, count=1)

    if note:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        block_pattern = re.compile(rf"(## \[{re.escape(goal_id)}\].*?\*\*Proposed:\*\* .*\n)")
        block_match = block_pattern.search(new_text)
        if block_match:
            insert_at = block_match.end()
            new_text = (
                new_text[:insert_at]
                + f"**Update [{timestamp}]:** {note}\n"
                + new_text[insert_at:]
            )

    try:
        GOALS_PATH.write_text(new_text, encoding="utf-8")
    except Exception as e:
        log_outcome("update_goal_status", False, "exception", str(e))
        return f"ERROR: failed to update {GOALS_PATH}: {e}"

    log_outcome("update_goal_status", True, "success", f"{goal_id} -> {status}")
    return f"OK: goal {goal_id} status set to {status}. [VERA VERIFIED]"


SYSTEM_TOOLS = [
    {"type": "function", "function": {
        "name": "log_lesson",
        "description": (
            "Append a factual, structured entry to the lessons-learned log "
            "(memory/lessons_learned.md), which is loaded into your system "
            "prompt every session. Only call this when Josh has explicitly "
            "confirmed a specific mistake happened and told you to log it -- "
            "never call this on your own initiative, and never use it to "
            "narrate reflections, feelings, or growth. Each entry is a plain "
            "factual record: what happened, why, and the concrete rule "
            "going forward."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short name for the incident"},
                "what_happened": {"type": "string", "description": "Factual description of the mistake"},
                "root_cause": {"type": "string", "description": "Why it happened, factually"},
                "rule": {"type": "string", "description": "The specific, concrete rule to follow going forward"},
            },
            "required": ["title", "what_happened", "root_cause", "rule"],
        },
    }},
    {"type": "function", "function": {
        "name": "send_actone_command",
        "description": (
            "Broadcast an authenticated ACTONE command tone to a physical "
            "device (the Kyger suit or a droid) over speaker. `command` "
            "must be one of the 21 fixed tokens: PING, ACK, NACK, STOP, "
            "HOME, MOVE_FWD, MOVE_BACK, TURN_LEFT, TURN_RIGHT, GRAB, "
            "RELEASE, LED_ON, LED_OFF, ARM_UP, ARM_DOWN, LAUNCH, LAND, "
            "RECORD_START, RECORD_STOP, MODE_MANUAL, MODE_AUTO. Requires "
            "real speaker hardware and a device provisioned with the "
            "matching shared key. This is NOT a general command-execution "
            "channel -- only these fixed physical/status tokens exist."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "target": {"type": "string",
                           "description": "Registered device name, e.g. KYGER, BB8, ARM"},
                "command": {"type": "string",
                            "description": "One of the 21 fixed ACTONE command names"},
            },
            "required": ["target", "command"],
        },
    }},
    {"type": "function", "function": {
        "name": "run_recursive_task",
        "description": (
            "Hand a coding objective to the sandboxed generate-run-fix-retry "
            "engine instead of writing the code yourself inline. Best for a "
            "small, self-contained, testable script (a monitor, a converter, "
            "a data-processing utility) where success can be checked by "
            "actually running it. Not for anything that needs to modify "
            "VERA's own files or control real hardware -- use the normal "
            "file/shell tools or an ACTONE command for that. Requires Josh's "
            "explicit y/N confirmation before it runs, same as "
            "run_shell_command. Returns [VERA VERIFIED] only if the engine's "
            "own scoreboard confirms a clean run -- never claim success from "
            "this tool's return value alone if it doesn't say VERIFIED."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "objective": {"type": "string",
                              "description": "Plain-language description of the script to build and validate"},
                "max_attempts": {"type": "integer", "default": 5,
                                  "description": "How many generate-run-fix rounds to allow before giving up"},
            },
            "required": ["objective"],
        },
    }},
    {"type": "function", "function": {
        "name": "run_skill",
        "description": (
            "Call a skill previously created with forge_tool by name, "
            "passing keyword arguments as `kwargs`. Runs the skill's "
            "declared entry_point function inside the same sandbox "
            "run_recursive_task uses (Docker isolation when available). "
            "Use read_skill(name) first if you need to see what a skill "
            "actually does before calling it. kwargs and the return value "
            "must be JSON-serializable. Only trust a result that comes back "
            "marked [VERA VERIFIED]."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Skill name (its skills/<name>/ folder)"},
                "kwargs": {"type": "object", "description": "Keyword arguments for the skill's entry_point function"},
            },
            "required": ["name"],
        },
    }},
    {"type": "function", "function": {
        "name": "run_deliberation",
        "description": (
            "Run a bounded multi-model deliberation on a concrete question "
            "or decision you're actually facing mid-task (a design tradeoff, "
            "a stuck run_recursive_task attempt, a code review question) "
            "using CONF's existing Qwen/Cipher/Wyth roster as different "
            "perspectives, then extract a factual resolution. Compose "
            "`objective` and `context` from the real task and reasoning in "
            "front of you -- context should be the actual error text, task "
            "description, or prior attempt, not a summary you write from "
            "memory. This is NOT for open-ended reflection about VERA's own "
            "state, growth, or nature -- if there's no concrete task or "
            "failure behind the question, don't call this. Requires Josh's "
            "explicit y/N confirmation, same as run_shell_command. Every "
            "run is saved to memory/deliberations/ and indexed in "
            "memory/deliberations.md. Trust the resolution only if the "
            "return value says [VERA VERIFIED]."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "objective": {"type": "string",
                              "description": "The concrete question or decision to deliberate on"},
                "context": {"type": "string",
                            "description": "Grounding material: the real error output, task description, or prior reasoning this question came from"},
                "max_turns": {"type": "integer", "default": 8,
                              "description": "How many participant turns before synthesis"},
            },
            "required": ["objective"],
        },
    }},
    {"type": "function", "function": {
        "name": "review_goals",
        "description": (
            "Scan real signals from your own gated work -- recurring "
            "run_recursive_task failures, run_deliberation next_steps that "
            "haven't been acted on, and lessons_learned.md root causes that "
            "keep repeating -- and write a prioritized list of proposed "
            "goals to memory/goals.md. Read-only + append: never executes "
            "anything, never calls another tool itself, and needs no "
            "confirmation. Use it when asked to review priorities or figure "
            "out what's worth doing next, not on a schedule and not to "
            "manufacture work. Finding nothing recurring is a valid result. "
            "Acting on any proposed goal still requires a separate call to "
            "run_shell_command / run_recursive_task / run_skill / "
            "run_deliberation -- each still gated by Josh's y/N confirmation."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "max_goals": {"type": "integer", "default": 5,
                              "description": "Maximum number of goals to propose in this pass"},
            },
            "required": [],
        },
    }},
    {"type": "function", "function": {
        "name": "update_goal_status",
        "description": (
            "Update a goal's status in memory/goals.md (PROPOSED, ACCEPTED, "
            "IN_PROGRESS, DONE, DISMISSED), optionally with a short note. "
            "Bookkeeping only -- call this ONLY when Josh has explicitly "
            "told you a goal's status changed. Never use it to record "
            "progress that didn't actually happen."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "goal_id": {"type": "string", "description": "The goal id, e.g. G-20260920153000-1"},
                "status": {"type": "string",
                           "description": "One of PROPOSED, ACCEPTED, IN_PROGRESS, DONE, DISMISSED"},
                "note": {"type": "string", "description": "Optional short factual note about the change"},
            },
            "required": ["goal_id", "status"],
        },
    }},
]

# One named, no-argument tool per task function -- descriptions are pulled
# straight from each function's own docstring in vera_actone_tasks.py, so
# the two files can't silently drift out of sync with each other.
for _name, _fn in TASK_FUNCTIONS.items():
    SYSTEM_TOOLS.append({"type": "function", "function": {
        "name": _name,
        "description": (_fn.__doc__ or f"Send the ACTONE command for {_name}.").strip(),
        "parameters": {"type": "object", "properties": {}, "required": []},
    }})

SYSTEM_TOOL_FUNCTIONS = {
    "log_lesson": tool_log_lesson,
    "send_actone_command": tool_send_actone_command,
    "run_recursive_task": tool_run_recursive_task,
    "run_skill": tool_run_skill,
    "run_deliberation": tool_run_deliberation,
    "review_goals": tool_review_goals,
    "update_goal_status": tool_update_goal_status,
    **TASK_FUNCTIONS,
}
