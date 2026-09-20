import subprocess, sys, shutil

def check_tool(name):
    return shutil.which(name) is not None

def install_tool(manager, package):
    # This generates the command for you to run
    print(f"VERA_PROPOSAL: Run '{manager} install {package}' to proceed.")


def manage_tool(tool_name, manager="choco"):
    """
    Check whether tool_name is on PATH; if not, return the proposed install
    command as data rather than printing it. Never runs the install itself --
    same behavior install_tool() always had, just returned instead of only
    printed, so run_skill() can hand the result back instead of losing it.
    """
    if check_tool(tool_name):
        return {"tool": tool_name, "status": "installed"}
    return {
        "tool": tool_name,
        "status": "missing",
        "proposed_command": f"{manager} install {tool_name}",
    }


if __name__ == "__main__":
    if len(sys.argv) > 1:
        tool = sys.argv[1]
        if check_tool(tool):
            print(f"STATUS: {tool} is already installed.")
        else:
            print(f"STATUS: {tool} not found.")
            install_tool("choco", tool)  # Defaulting to Chocolatey for Windows
