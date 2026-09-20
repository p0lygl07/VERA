These two files (self_check.py, system_check.py) are leftover test runs
from the OLD, broken forge_tool()/forge.py -- both are just a bare
`log(...)` call at module level with no real function, so there's no
honest entry_point to wrap them with. Not migrated into the new
skills/<name>/SKILL.md package format for that reason; moved here so
they don't sit loose in skills/ looking like orphaned skills.

Safe to delete once you've confirmed you don't need them -- I only
archived rather than deleted since deleting needs your explicit go-ahead.
