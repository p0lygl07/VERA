

## [2026-09-13 17:50] Fabricated file duplication
**What happened:** Wrote core/actone_task_wrapper.py as a simulated stand-in that never called real ACTONE functions, then wired a new bb8_task_wrapper.py into it instead of using the already-tested bb8_led_on() etc. from vera_actone_tasks.py
**Root cause:** Built new code before searching for existing functionality; the simulation looked plausible enough that debugging it produced honest-looking failures that were not actually meaningful
**Rule going forward:** Before writing any new function, search_files for its likely name or purpose FIRST. If a real, tested implementation already exists, use it directly instead of building a wrapper around it or beside it.
