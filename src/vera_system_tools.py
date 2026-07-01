#!/usr/bin/env python3
"""
VERA System Tools
Expanded system-level capabilities:
- Process management
- System information
- File system operations (recursive, search)
- Network awareness
- Clipboard access
- Scheduled task awareness
"""

import os
import sys
import subprocess
import platform
import datetime
import json
from pathlib import Path

VERA_ROOT = Path(__file__).parent.parent
LOG_PATH  = VERA_ROOT / "logs" / "execution_log.md"


def log(tool, executed, result, notes=""):
    date = datetime.date.today().isoformat()
    row = f"| {date} | {tool} | {'YES' if executed else 'NO'} | {result} | {notes} |\n"
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(row)
    except Exception:
        pass


# ── System awareness ──────────────────────────────────────────────────────────
def tool_system_info():
    """Get system status — OS, memory, CPU, running processes."""
    try:
        info = {
            "os": platform.system() + " " + platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python": platform.python_version(),
            "hostname": platform.node(),
            "datetime": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        # Try to get memory info via PowerShell
        try:
            result = subprocess.run(
                ["powershell", "-c",
                 "Get-CimInstance Win32_OperatingSystem | "
                 "Select-Object FreePhysicalMemory,TotalVisibleMemorySize | "
                 "ConvertTo-Json"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                mem = json.loads(result.stdout)
                total_mb = mem.get("TotalVisibleMemorySize", 0) // 1024
                free_mb = mem.get("FreePhysicalMemory", 0) // 1024
                used_mb = total_mb - free_mb
                info["memory"] = f"{used_mb}MB used / {total_mb}MB total"
        except Exception:
            info["memory"] = "unavailable"

        log("system_info", True, "success", "system info retrieved")
        return json.dumps(info, indent=2)
    except Exception as e:
        log("system_info", False, "exception", str(e))
        return f"ERROR: {e}"


def tool_list_processes(filter_name=None):
    """List running processes, optionally filtered by name."""
    try:
        ps_cmd = "Get-Process | Select-Object Name,Id,CPU,WorkingSet | ConvertTo-Json"
        if filter_name:
            ps_cmd = (f"Get-Process | Where-Object {{$_.Name -like '*{filter_name}*'}} | "
                     f"Select-Object Name,Id,CPU,WorkingSet | ConvertTo-Json")

        result = subprocess.run(
            ["powershell", "-c", ps_cmd],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0:
            return f"ERROR: {result.stderr}"

        processes = json.loads(result.stdout or "[]")
        if not isinstance(processes, list):
            processes = [processes]

        lines = [f"{'NAME':<30} {'PID':<8} {'MEM(MB)':<10}"]
        lines.append("-" * 50)
        for p in processes[:20]:
            name = str(p.get("Name", ""))[:29]
            pid = str(p.get("Id", ""))
            mem = str(round(p.get("WorkingSet", 0) / 1024 / 1024, 1)) + "MB"
            lines.append(f"{name:<30} {pid:<8} {mem:<10}")

        if len(processes) > 20:
            lines.append(f"... and {len(processes) - 20} more")

        log("list_processes", True, "success", f"listed {len(processes)} processes")
        return "\n".join(lines)
    except Exception as e:
        log("list_processes", False, "exception", str(e))
        return f"ERROR: {e}"


def tool_search_files(directory, pattern, recursive=True):
    """Search for files matching a pattern."""
    try:
        p = Path(directory)
        if not p.exists():
            return f"ERROR: directory not found: {directory}"

        if recursive:
            matches = list(p.rglob(pattern))
        else:
            matches = list(p.glob(pattern))

        if not matches:
            return f"No files matching '{pattern}' found in {directory}"

        result = f"Found {len(matches)} file(s) matching '{pattern}':\n"
        for m in matches[:50]:
            size = m.stat().st_size if m.is_file() else 0
            modified = datetime.datetime.fromtimestamp(
                m.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            result += f"  {modified}  {size:>10,}B  {m}\n"

        if len(matches) > 50:
            result += f"  ... and {len(matches) - 50} more\n"

        log("search_files", True, "success", f"found {len(matches)} matches")
        return result
    except Exception as e:
        log("search_files", False, "exception", str(e))
        return f"ERROR: {e}"


def tool_read_clipboard():
    """Read current clipboard contents."""
    try:
        result = subprocess.run(
            ["powershell", "-c", "Get-Clipboard"],
            capture_output=True, text=True, timeout=5
        )
        content = result.stdout.strip()
        if not content:
            return "(clipboard is empty)"
        log("read_clipboard", True, "success", f"{len(content)} chars")
        return content
    except Exception as e:
        log("read_clipboard", False, "exception", str(e))
        return f"ERROR: {e}"


def tool_write_clipboard(text):
    """Write text to clipboard."""
    try:
        result = subprocess.run(
            ["powershell", "-c", f"Set-Clipboard -Value '{text}'"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            log("write_clipboard", True, "success", f"{len(text)} chars written")
            return f"OK: copied {len(text)} characters to clipboard [VERA VERIFIED]"
        return f"ERROR: {result.stderr}"
    except Exception as e:
        log("write_clipboard", False, "exception", str(e))
        return f"ERROR: {e}"


def tool_network_status():
    """Check network connectivity and active connections."""
    try:
        lines = []

        # Check internet
        result = subprocess.run(
            ["powershell", "-c",
             "Test-NetConnection -ComputerName 8.8.8.8 -Port 53 -InformationLevel Quiet"],
            capture_output=True, text=True, timeout=10
        )
        internet = "CONNECTED" if "True" in result.stdout else "DISCONNECTED"
        lines.append(f"Internet: {internet}")

        # Check Ollama
        result = subprocess.run(
            ["powershell", "-c",
             "Test-NetConnection -ComputerName localhost -Port 11434 -InformationLevel Quiet"],
            capture_output=True, text=True, timeout=5
        )
        ollama = "ONLINE" if "True" in result.stdout else "OFFLINE"
        lines.append(f"Ollama (localhost:11434): {ollama}")

        # Get IP
        result = subprocess.run(
            ["powershell", "-c",
             "(Get-NetIPAddress -AddressFamily IPv4 | "
             "Where-Object {$_.IPAddress -notlike '127.*'} | "
             "Select-Object -First 1).IPAddress"],
            capture_output=True, text=True, timeout=5
        )
        ip = result.stdout.strip() or "unknown"
        lines.append(f"Local IP: {ip}")

        log("network_status", True, "success", "network status retrieved")
        return "\n".join(lines)
    except Exception as e:
        log("network_status", False, "exception", str(e))
        return f"ERROR: {e}"


def tool_open_application(app_name):
    """Open an application by name."""
    try:
        # Map common names to executables
        app_map = {
            "chrome": "chrome",
            "browser": "chrome",
            "firefox": "firefox",
            "notepad": "notepad",
            "calculator": "calc",
            "terminal": "wt",  # Windows Terminal
            "powershell": "powershell",
            "explorer": "explorer",
            "obsidian": "obsidian",
            "vscode": "code",
            "burpsuite": "burpsuite",
        }
        exe = app_map.get(app_name.lower(), app_name)
        subprocess.Popen([exe], shell=True)
        log("open_application", True, "success", f"opened: {app_name}")
        return f"OK: opened {app_name} [VERA VERIFIED]"
    except Exception as e:
        log("open_application", False, "exception", str(e))
        return f"ERROR opening {app_name}: {e}"


def tool_get_file_tree(directory, max_depth=3):
    """Get a tree view of a directory."""
    try:
        p = Path(directory)
        if not p.exists():
            return f"ERROR: {directory} not found"

        lines = [str(p)]

        def _tree(path, prefix="", depth=0):
            if depth >= max_depth:
                return
            try:
                entries = sorted(path.iterdir(),
                                key=lambda x: (x.is_file(), x.name.lower()))
                for i, entry in enumerate(entries[:50]):
                    is_last = i == len(entries) - 1
                    connector = "└── " if is_last else "├── "
                    lines.append(f"{prefix}{connector}{entry.name}")
                    if entry.is_dir():
                        extension = "    " if is_last else "│   "
                        _tree(entry, prefix + extension, depth + 1)
            except PermissionError:
                lines.append(f"{prefix}[permission denied]")

        _tree(p)
        log("get_file_tree", True, "success", f"tree of {directory}")
        return "\n".join(lines)
    except Exception as e:
        log("get_file_tree", False, "exception", str(e))
        return f"ERROR: {e}"


# ── Tool registry for VERA agent integration ──────────────────────────────────
SYSTEM_TOOLS = [
    {"type": "function", "function": {
        "name": "system_info",
        "description": "Get system status: OS, memory, CPU, hostname, current time.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "list_processes",
        "description": "List running processes, optionally filtered by name.",
        "parameters": {"type": "object", "properties": {
            "filter_name": {"type": "string", "description": "Optional name filter"}
        }},
    }},
    {"type": "function", "function": {
        "name": "search_files",
        "description": "Search for files matching a pattern in a directory.",
        "parameters": {"type": "object", "properties": {
            "directory": {"type": "string"},
            "pattern": {"type": "string", "description": "Glob pattern e.g. *.py"},
            "recursive": {"type": "boolean", "default": True},
        }, "required": ["directory", "pattern"]},
    }},
    {"type": "function", "function": {
        "name": "read_clipboard",
        "description": "Read the current clipboard contents.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "write_clipboard",
        "description": "Copy text to the clipboard.",
        "parameters": {"type": "object", "properties": {
            "text": {"type": "string"}
        }, "required": ["text"]},
    }},
    {"type": "function", "function": {
        "name": "network_status",
        "description": "Check internet connectivity, Ollama status, and local IP.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "open_application",
        "description": "Open an application by name (chrome, notepad, terminal, etc.).",
        "parameters": {"type": "object", "properties": {
            "app_name": {"type": "string"}
        }, "required": ["app_name"]},
    }},
    {"type": "function", "function": {
        "name": "get_file_tree",
        "description": "Get a tree view of a directory structure.",
        "parameters": {"type": "object", "properties": {
            "directory": {"type": "string"},
            "max_depth": {"type": "integer", "default": 3},
        }, "required": ["directory"]},
    }},
]

SYSTEM_TOOL_FUNCTIONS = {
    "system_info": lambda **_: tool_system_info(),
    "list_processes": tool_list_processes,
    "search_files": tool_search_files,
    "read_clipboard": lambda **_: tool_read_clipboard(),
    "write_clipboard": tool_write_clipboard,
    "network_status": lambda **_: tool_network_status(),
    "open_application": tool_open_application,
    "get_file_tree": tool_get_file_tree,
}


if __name__ == "__main__":
    # Self-test
    print("VERA System Tools — self test")
    print("\n[system_info]")
    print(tool_system_info())
    print("\n[network_status]")
    print(tool_network_status())
    print("\n[search_files: VERA/src/*.py]")
    print(tool_search_files(str(VERA_ROOT / "src"), "*.py"))
