import subprocess, sys, shutil

def check_tool(name):
    return shutil.which(name) is not None

def install_tool(manager, package):
    # This generates the command for you to run
    print(f"VERA_PROPOSAL: Run '{manager} install {package}' to proceed.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        tool = sys.argv[1]
        if check_tool(tool):
            print(f"STATUS: {tool} is already installed.")
        else:
            print(f"STATUS: {tool} not found.")
            install_tool("choco", tool) # Defaulting to Chocolatey for Windows