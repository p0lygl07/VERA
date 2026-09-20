---
name: sys-admin-core
description: Check whether a command-line tool is installed on this machine, and get the install command for it if it isn't. Does not install anything -- it only proposes the command for Josh to run himself.
entry_point: manage_tool
---

# sys-admin-core

Checks whether a named CLI tool is available on PATH. If it's missing,
returns the install command (Chocolatey by default) as data -- it does not
run that command. Josh runs it himself, the same way run_shell_command
already requires an explicit y/N before anything executes.

## Usage
run_skill(name="sys-admin-core", kwargs={"tool_name": "nmap"})
run_skill(name="sys-admin-core", kwargs={"tool_name": "nmap", "manager": "winget"})

## Notes
- This had no SKILL.md before, which meant load_skills() never surfaced it
  and it wasn't reachable at all -- env_manager.py's check_tool()/install_tool()
  were real, working code with no way to call them.
- install_tool() still only prints a proposed command and always has --
  manage_tool() wraps that same behavior and returns it as data instead of
  losing it to stdout, but changes nothing about what actually executes.
- The script's own `if __name__ == "__main__":` block still works standalone:
  `python env_manager.py <tool_name>`.
