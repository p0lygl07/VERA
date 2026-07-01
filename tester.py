import subprocess, sys
def test_skill(script_name):
    path = f"C:\\Users\\p0ly\\Desktop\\AI\\VERA\\skills\\{script_name}"
    result = subprocess.run([sys.executable, path], capture_output=True, text=True)
    return result.returncode == 0