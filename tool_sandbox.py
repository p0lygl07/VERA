import os
import subprocess
import venv
import shutil
from typing import Dict, Any

class VeraToolSandbox:
    def __init__(self, workspace_dir: str = "/tmp/vera_sandbox"):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.venv_dir = os.path.join(self.workspace_dir, "vera_env")
        self.tools_dir = os.path.join(self.workspace_dir, "installed_tools")
        
        # Ensure directories exist
        os.makedirs(self.tools_dir, exist_ok=True)
        self._initialize_venv()

    def _initialize_venv(self):
        """Creates a dedicated virtual environment for Vera's tools."""
        if not os.path.exists(self.venv_dir):
            venv.create(self.venv_dir, with_pip=True)
        
        # Determine path to env's python/pip executable
        if os.name == 'nt':
            self.pip_executable = os.path.join(self.venv_dir, 'Scripts', 'pip.exe')
            self.python_executable = os.path.join(self.venv_dir, 'Scripts', 'python.exe')
        else:
            self.pip_executable = os.path.join(self.venv_dir, 'bin', 'pip')
            self.python_executable = os.path.join(self.venv_dir, 'bin', 'python')

    def run_command(self, cmd: list, cwd: str = None) -> Dict[str, Any]:
        """Safely executes a shell command within the workspace."""
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd or self.workspace_dir,
                capture_output=True,
                text=True,
                timeout=300 # Prevent infinite loops
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        except Exception as e:
            return {"success": False, "stdout": "", "stderr": str(e)}

    def install_pip_package(self, package_name: str) -> Dict[str, Any]:
        """Allows Vera to pip install tools."""
        cmd = [self.pip_executable, "install", package_name]
        return self.run_command(cmd)

    def clone_git_repo(self, repo_url: str, repo_name: str) -> Dict[str, Any]:
        """Allows Vera to clone any public tool repository."""
        target_path = os.path.join(self.tools_dir, repo_name)
        if os.path.exists(target_path):
            shutil.rmtree(target_path) # Clean slate or pull changes
            
        cmd = ["git", "clone", repo_url, target_path]
        res = self.run_command(cmd)
        
        # Automatically attempt to install requirements.txt if present
        req_path = os.path.join(target_path, "requirements.txt")
        if res["success"] and os.path.exists(req_path):
            self.run_command([self.pip_executable, "install", "-r", req_path], cwd=target_path)
            
        return res

    def execute_tool(self, script_path: str, args: list = None) -> Dict[str, Any]:
        """Runs an installed script using the virtual environment python interpreter."""
        # Force execution within the sandboxed environment
        full_script_path = os.path.abspath(script_path)
        if not full_script_path.startswith(self.workspace_dir):
            return {"success": False, "stdout": "", "stderr": "Security Exception: Out of bounds execution."}
            
        cmd = [self.python_executable, full_script_path] + (args or [])
        return self.run_command(cmd, cwd=os.path.dirname(full_script_path))