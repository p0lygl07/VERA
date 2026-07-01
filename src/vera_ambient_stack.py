#!/usr/bin/env python3
"""
VERA Ambient Stack - Unified Background Awareness Launcher

Imports and starts all ambient awareness components as background threads:
- listener.py (WebSocket traffic capture)
- observer_daemon.py (network observation daemon)  
- port_scanner.py (active port scanning)
- recon_automated.py (reconnaissance automation)

Usage: python src\vera_ambient_stack.py
"""

import threading
import time
from pathlib import Path


def start_thread(module_path, name):
    """Start a module as a background thread."""
    try:
        from importlib.util import spec_from_file_location, module_from_spec
        
        # Get absolute path for dynamic imports
        abs_path = str(Path(__file__).parent / "ambient" / Path(name))
        
        spec = spec_from_file_location(f"{name}", abs_path)
        if not spec:
            print(f"[{name}] FAILED to load specification")
            return False
        
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Start thread with daemon=True for background operation
        t = threading.Thread(target=module.main, name=f"{name}-Thread", daemon=True)
        t.start()
        
        print(f"[{name}] Started as background thread")
        return True
        
    except Exception as e:
        print(f"[{name}] FAILED to start: {e}")
        return False


def main():
    """Start all ambient components."""
    
    # Ambient stack modules (relative paths from src directory)
    AMBIENT_MODULES = [
        ("listener.py", "WebSocket Listener"),
        ("observer_daemon.py", "Observer Daemon"),
        ("port_scanner.py", "Port Scanner"), 
        ("recon_automated.py", "Recon Automation")
    ]
    
    print("=" * 60)
    print("VERA AMBIENT STACK INITIALIZATION")
    print("=" * 60)
    print()
    
    # Start all modules as threads
    for module_path, display_name in AMBIENT_MODULES:
        success = start_thread(module_path, module_path)
        
        if not success:
            time.sleep(2)  # Wait before retrying failed starts
    
    print()
    print("=" * 60)
    print("AMBIENT STACK ACTIVE")
    print(f"Threads running: {threading.active_count()}")
    print("=" * 60)


if __name__ == "__main__":
    main()
