#!/usr/bin/env python3
"""
VERA Ambient Intelligence v1.1
Fixes:
  - Screenshot: uses BytesIO buffer instead of temp file (WinError 32)
  - USB scan: null check on device names (NoneType error)
  - Network: filters VirtualBox/VMware adapters to find real network
  - Self-repair: integrated error diagnosis and logging
"""

import json
import os
import sys
import io
import time
import datetime
import subprocess
import threading
import socket
import base64
import requests
from pathlib import Path

VERA_ROOT     = Path(__file__).parent.parent
MEMORY_PATH   = VERA_ROOT / "memory"
DEVICES_FILE  = MEMORY_PATH / "known_devices.json"
SCREEN_LOG    = VERA_ROOT / "logs" / "screen_context.md"
OLLAMA_URL    = "http://localhost:11434/api/chat"
MODEL         = "qwen3.5:9b"

# ── Import self-repair engine ─────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
try:
    from vera_repair import safe_call, VERARepairContext, log_repair
    REPAIR_AVAILABLE = True
except ImportError:
    REPAIR_AVAILABLE = False
    def safe_call(fn, *args, fallback=None, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            print(f"[ERROR] {e}")
            return fallback

    class VERARepairContext:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False


# ── Device signatures ─────────────────────────────────────────────────────────
DEVICE_SIGNATURES = {
    "wifi_pineapple": {
        "name": "WiFi Pineapple Pager",
        "check_ports": [1471, 8080, 80],
        "check_paths": ["/api/status", "/api/"],
    },
    "octoprint": {
        "name": "OctoPrint (3D Printer)",
        "check_ports": [5000, 80],
        "check_paths": ["/api/version"],
    },
    "home_assistant": {
        "name": "Home Assistant",
        "check_ports": [8123],
        "check_paths": ["/api/"],
    },
}

# VM adapter prefixes to skip during network discovery
VM_ADAPTER_PREFIXES = ["172.17.", "172.18.", "172.19.", "172.20.",
                        "172.21.", "172.22.", "172.23.", "172.24.",
                        "172.25.", "172.26.", "172.27.", "172.28.",
                        "172.29.", "172.30.", "172.31.",
                        "192.168.56.", "192.168.99.",  # VirtualBox
                        "10.0.75.", "10.0.76.",        # Docker/Hyper-V
                        ]


# ── Network utilities ─────────────────────────────────────────────────────────
def get_local_network():
    """Get real local network range, filtering out VM adapters."""
    try:
        result = subprocess.run(
            ["powershell", "-c",
             "Get-NetIPAddress -AddressFamily IPv4 | "
             "Select-Object IPAddress,PrefixLength | ConvertTo-Json"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            if not isinstance(data, list):
                data = [data]

            candidates = []
            for item in data:
                ip = item.get("IPAddress", "") or ""
                prefix = item.get("PrefixLength", 24)

                # Skip loopback and link-local
                if ip.startswith("127.") or ip.startswith("169.254."):
                    continue

                # Skip VM adapters
                is_vm = any(ip.startswith(p) for p in VM_ADAPTER_PREFIXES)
                if is_vm:
                    print(f"[VERA DISCOVER] Skipping VM adapter: {ip}")
                    continue

                parts = ip.split(".")
                if len(parts) == 4:
                    candidates.append(f"{parts[0]}.{parts[1]}.{parts[2]}")

            if candidates:
                # Prefer 192.168.x.x then 10.x.x.x
                for c in candidates:
                    if c.startswith("192.168."):
                        return c
                return candidates[0]

    except Exception as e:
        print(f"[VERA DISCOVER] Network detection error: {e}")

    return "192.168.1"  # fallback


def ping_host(ip, timeout=500):
    """Quick ping to check if host is alive."""
    try:
        result = subprocess.run(
            ["ping", "-n", "1", "-w", str(timeout), ip],
            capture_output=True, timeout=3
        )
        return result.returncode == 0
    except Exception:
        return False


def check_port(ip, port, timeout=1):
    """Check if a port is open."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def http_get(url, timeout=3):
    """Quick HTTP GET."""
    try:
        resp = requests.get(url, timeout=timeout,
                           headers={"User-Agent": "VERA-Agent/1.0"})
        return resp.status_code, resp.text[:500]
    except Exception:
        return None, None


# ── USB device scan ───────────────────────────────────────────────────────────
def check_usb_devices():
    """Scan USB devices for known hardware. Fixed: null check on device names."""
    devices = []
    try:
        result = subprocess.run(
            ["powershell", "-c",
             "Get-PnpDevice -Status OK | "
             "Select-Object FriendlyName,InstanceId | "
             "Where-Object {$_.FriendlyName -ne $null} | "
             "ConvertTo-Json"],
            capture_output=True, text=True, timeout=15
        )

        if result.returncode != 0 or not result.stdout.strip():
            return devices

        pnp_devices = json.loads(result.stdout)
        if not isinstance(pnp_devices, list):
            pnp_devices = [pnp_devices]

        for dev in pnp_devices:
            # FIX: null check before calling .lower()
            name = dev.get("FriendlyName") or ""
            inst = dev.get("InstanceId") or ""

            name_lower = name.lower()
            inst_lower = inst.lower()

            if "flipper" in name_lower or ("0483" in inst_lower and "5740" in inst_lower):
                devices.append({
                    "type": "flipper_zero",
                    "name": "Flipper Zero",
                    "connection": "USB",
                    "friendly_name": name,
                    "status": "connected",
                    "api_type": "serial",
                    "note": "Serial connection available for control",
                })

            elif "esp32" in name_lower or "cp210" in name_lower or "ch340" in name_lower:
                devices.append({
                    "type": "esp32",
                    "name": "ESP32 Device",
                    "connection": "USB",
                    "friendly_name": name,
                    "status": "connected",
                    "api_type": "serial",
                    "note": "May be ESP32 Marauder or similar",
                })

            elif "pineapple" in name_lower:
                devices.append({
                    "type": "wifi_pineapple",
                    "name": "WiFi Pineapple (USB)",
                    "connection": "USB",
                    "friendly_name": name,
                    "status": "connected",
                })

    except json.JSONDecodeError:
        # Single device returns object not array
        try:
            data = json.loads(result.stdout)
            pnp_devices = [data] if isinstance(data, dict) else []
        except Exception:
            pass
    except Exception as e:
        print(f"[VERA DISCOVER] USB scan error: {e}")
        if REPAIR_AVAILABLE:
            from vera_repair import identify_known_fix
            fix = identify_known_fix(str(e))
            if fix:
                print(f"[VERA REPAIR] {fix['fix']}")

    return devices


# ── Device identification ─────────────────────────────────────────────────────
def check_pineapple(ip):
    for port in [1471, 8080, 80]:
        if check_port(ip, port):
            status, body = http_get(f"http://{ip}:{port}/api/status")
            if status == 200:
                return {
                    "type": "wifi_pineapple",
                    "name": "WiFi Pineapple Pager",
                    "ip": ip, "port": port,
                    "api_base": f"http://{ip}:{port}",
                    "status": "confirmed",
                }
            if port == 1471 and check_port(ip, port):
                return {
                    "type": "wifi_pineapple",
                    "name": "WiFi Pineapple Pager (likely)",
                    "ip": ip, "port": port,
                    "api_base": f"http://{ip}:{port}",
                    "status": "likely",
                }
    return None


def check_octoprint(ip):
    for port in [5000, 80]:
        if check_port(ip, port):
            status, body = http_get(f"http://{ip}:{port}/api/version")
            if status == 200 and body:
                try:
                    data = json.loads(body)
                    return {
                        "type": "octoprint",
                        "name": f"OctoPrint 3D Printer",
                        "ip": ip, "port": port,
                        "api_base": f"http://{ip}:{port}",
                        "status": "confirmed",
                    }
                except Exception:
                    pass
    return None


def check_ha(ip):
    if check_port(ip, 8123):
        status, body = http_get(f"http://{ip}:8123/api/")
        if status in [200, 401]:
            return {
                "type": "home_assistant",
                "name": "Home Assistant",
                "ip": ip, "port": 8123,
                "api_base": f"http://{ip}:8123",
                "status": "discovered",
                "note": "Requires API token",
            }
    return None


# ── Main discovery ────────────────────────────────────────────────────────────
def discover_devices(network=None, speak_fn=None):
    """Scan network and USB for devices. VERA auto-configures to talk to them."""
    print("=" * 60)
    print("VERA Device Autodiscovery v1.1")
    print(f"Running: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    found_devices = []

    # USB scan
    print("\n[VERA DISCOVER] Scanning USB devices...")
    usb_devices = check_usb_devices()
    for dev in usb_devices:
        print(f"[VERA DISCOVER] Found USB: {dev['name']}")
        found_devices.append(dev)
    if not usb_devices:
        print("[VERA DISCOVER] No known USB devices")

    # Network scan
    if not network:
        network = get_local_network()
    print(f"\n[VERA DISCOVER] Scanning network: {network}.x")

    if speak_fn:
        speak_fn("Scanning your network for connected devices.")

    # Parallel ping
    responsive = []
    lock = threading.Lock()

    def ping_worker(ip):
        if ping_host(ip):
            with lock:
                responsive.append(ip)

    threads = []
    for i in range(1, 50):
        ip = f"{network}.{i}"
        t = threading.Thread(target=ping_worker, args=(ip,))
        t.daemon = True
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=5)

    print(f"[VERA DISCOVER] {len(responsive)} hosts responded")

    checkers = [check_pineapple, check_octoprint, check_ha]
    for ip in responsive:
        for checker in checkers:
            with VERARepairContext(f"check device at {ip}"):
                result = checker(ip)
                if result:
                    print(f"[VERA DISCOVER] Identified: {result['name']} at {ip}")
                    found_devices.append(result)
                    break

    # Save
    MEMORY_PATH.mkdir(parents=True, exist_ok=True)
    DEVICES_FILE.write_text(json.dumps(found_devices, indent=2), encoding="utf-8")
    write_device_context(found_devices)

    if speak_fn:
        if found_devices:
            speak_fn(f"Found {len(found_devices)} connected devices.")
        else:
            speak_fn("No known devices found on the network.")

    return found_devices


def write_device_context(devices):
    if not devices:
        return
    context_path = MEMORY_PATH / "device_context.md"
    lines = ["# VERA Connected Devices",
             f"## {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}", ""]
    for dev in devices:
        lines.append(f"### {dev.get('name', 'Unknown')}")
        for k, v in dev.items():
            if k != "name" and v:
                lines.append(f"- {k}: {v}")
        lines.append("")
    context_path.write_text("\n".join(lines), encoding="utf-8")


def load_known_devices():
    if DEVICES_FILE.exists():
        try:
            return json.loads(DEVICES_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


# ── Screenshot: FIX uses BytesIO to avoid WinError 32 ────────────────────────
def take_screenshot_b64():
    """Take screenshot and return as base64. Uses BytesIO to avoid file locking."""
    import pyautogui
    from PIL import Image

    # Capture to PIL Image directly
    screenshot = pyautogui.screenshot()

    # Save to BytesIO buffer -- no temp file, no file locking
    buffer = io.BytesIO()
    screenshot.save(buffer, format="PNG")
    buffer.seek(0)
    img_bytes = buffer.read()

    return base64.b64encode(img_bytes).decode("utf-8")


def analyze_screen(question="What is the user currently working on? Be specific and brief."):
    """Use VERA's vision to understand the current screen."""
    with VERARepairContext("screen analysis", fallback=None):
        img_b64 = take_screenshot_b64()
        payload = {
            "model": MODEL,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                    {"type": "text", "text": question}
                ]
            }],
            "stream": False,
            "options": {"temperature": 0.2, "num_ctx": 4096},
        }
        resp = requests.post(OLLAMA_URL, data=json.dumps(payload), timeout=30)
        resp.raise_for_status()
        return resp.json()["message"]["content"]

    return "Screen analysis unavailable."


def generate_ambient_suggestion(screen_context, previous_context=None):
    if previous_context and screen_context == previous_context:
        return None
    try:
        payload = {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": (
                    "You are VERA, Josh's ambient AI. You see his screen. "
                    "Josh is a cybersecurity student, bug bounty researcher, "
                    "CTF designer, hardware hacker, and VERA developer. "
                    "Generate ONE brief, specific, useful suggestion or question. "
                    "If nothing useful, return exactly: SILENT"
                )},
                {"role": "user", "content": (
                    f"Screen: {screen_context}\n"
                    f"Previous: {previous_context or 'none'}\n\n"
                    "One useful thing to say? Or SILENT."
                )}
            ],
            "stream": False,
            "options": {"temperature": 0.4, "num_ctx": 2048},
        }
        resp = requests.post(OLLAMA_URL, data=json.dumps(payload), timeout=20)
        resp.raise_for_status()
        result = resp.json()["message"]["content"].strip()
        return None if result == "SILENT" else result
    except Exception:
        return None


def log_screen_context(context):
    SCREEN_LOG.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(SCREEN_LOG, "a", encoding="utf-8") as f:
        f.write(f"\n[{timestamp}] {context[:200]}\n")


def ambient_monitor_loop(interval=30, speak_fn=None, verbose=False):
    """Monitor screen and offer proactive help."""
    print("=" * 60)
    print("VERA Ambient Screen Monitor v1.1")
    print(f"Interval: {interval}s | Ctrl+C to stop")
    print("=" * 60)

    previous_context = None

    if speak_fn:
        speak_fn("Ambient monitoring active.")

    while True:
        try:
            time.sleep(interval)
            context = analyze_screen()
            if not context or "unavailable" in context.lower():
                continue

            if verbose:
                print(f"[VERA AMBIENT] {context[:80]}...")

            log_screen_context(context)
            suggestion = generate_ambient_suggestion(context, previous_context)

            if suggestion:
                ts = datetime.datetime.now().strftime("%H:%M")
                print(f"\n[VERA AMBIENT {ts}] {suggestion}")
                if speak_fn:
                    speak_fn(suggestion)

            previous_context = context

        except KeyboardInterrupt:
            print("\n[VERA AMBIENT] Monitor stopped.")
            break
        except Exception as e:
            print(f"[VERA AMBIENT] Error: {e}")
            time.sleep(5)


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    if len(sys.argv) >= 2:
        cmd = sys.argv[1].lower()

        if cmd == "discover":
            devices = discover_devices()
            print(f"\nFound {len(devices)} device(s):")
            for d in devices:
                loc = f"@ {d['ip']}" if d.get("ip") else "USB"
                print(f"  - {d['name']} ({d.get('type', '?')}) {loc}")

        elif cmd == "devices":
            devices = load_known_devices()
            if devices:
                print(f"Known devices ({len(devices)}):")
                for d in devices:
                    print(f"\n  {d['name']}")
                    if d.get("ip"):
                        print(f"    IP: {d['ip']}:{d.get('port', '')}")
                    print(f"    Status: {d.get('status', 'unknown')}")
            else:
                print("No known devices. Run: vera_ambient.py discover")

        elif cmd == "monitor":
            interval = int(sys.argv[2]) if len(sys.argv) > 2 else 30
            ambient_monitor_loop(interval=interval, verbose=True)

        elif cmd == "screen":
            question = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else \
                      "What is the user working on right now? Be specific."
            print("[VERA VISION] Analyzing screen...")
            result = analyze_screen(question)
            print(f"\nVERA sees: {result}")

        elif cmd == "test":
            print("Testing VERA ambient systems v1.1...")
            print("\n1. Screenshot (BytesIO fix):")
            try:
                b64 = take_screenshot_b64()
                print(f"   Screenshot captured: {len(b64)} bytes (base64)")
            except Exception as e:
                print(f"   Error: {e}")

            print("\n2. USB device scan (null check fix):")
            usb = check_usb_devices()
            print(f"   Found {len(usb)} USB devices")
            for d in usb:
                print(f"   - {d['name']} ({d.get('connection', '?')})")

            print("\n3. Network detection (VM filter fix):")
            network = get_local_network()
            print(f"   Real network: {network}.x")

            print("\n4. Screen vision:")
            result = analyze_screen("What application is visible? One sentence.")
            print(f"   VERA sees: {result[:100]}")

            print("\nAll tests complete.")
        else:
            print("Commands: discover | devices | monitor [s] | screen [q] | test")
    else:
        print("VERA Ambient Intelligence v1.1")
        print("Commands: discover | devices | monitor | screen | test")


if __name__ == "__main__":
    main()
