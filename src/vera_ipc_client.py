#!/usr/bin/env python3
"""
VERA IPC Task-Routing Client
Direct CLI for routing tasks to VERA sub-agents via loopback socket.

Port: 8766 (conductor server)

Usage:
  python src/vera_ipc_client.py -t monitor_operative -m "Check system health"
  python src/vera_ipc_client.py -t sre_engineer -m "Verify Python dependencies"
  python src/vera_ipc_client.py -t recon_operative -m "Enumerate subdomains for target.com"
  python src/vera_ipc_client.py -t ctf_builder -m "Build a CORS exploitation CTF lab"
  python src/vera_ipc_client.py --status
"""

import argparse
import json
import socket
import sys
import datetime

# NOTE: port 8766 for conductor -- dashboard runs on 8765
CONDUCTOR_HOST = "127.0.0.1"
CONDUCTOR_PORT = 8766
TIMEOUT        = 300  # seconds -- sub-agents need time for LLM calls


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="VERA IPC Task-Routing Client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python vera_ipc_client.py -t monitor_operative -m "Check all VERA log files for errors"
  python vera_ipc_client.py -t sre_engineer -m "Install missing packages and verify imports"
  python vera_ipc_client.py -t recon_operative -m "Generate subfinder commands for pingidentity.com"
  python vera_ipc_client.py -t ctf_builder -m "Build week 10 CORS exploitation lab"
  python vera_ipc_client.py --status

Valid targets:
  monitor_operative  -- Environmental scanning, log monitoring, port checks
  sre_engineer       -- Dependency resolution, path repair, runtime hardening
  recon_operative    -- Bug bounty recon command generation (in-scope only)
  ctf_builder        -- SNHUpers CTF HTML lab and PDF solution guide builder
        """
    )

    parser.add_argument(
        "-t", "--target",
        choices=["monitor_operative", "sre_engineer", "recon_operative", "ctf_builder"],
        help="Target sub-agent to route task to"
    )

    parser.add_argument(
        "-m", "--message",
        type=str,
        dest="raw_message",
        help="Task payload to send to the sub-agent"
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help="Check if conductor server is online"
    )

    parser.add_argument(
        "--host",
        default=CONDUCTOR_HOST,
        help=f"Conductor host (default: {CONDUCTOR_HOST})"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=CONDUCTOR_PORT,
        help=f"Conductor port (default: {CONDUCTOR_PORT})"
    )

    return parser.parse_args()


def build_payload(target: str, message: str) -> dict:
    """Build verified JSON payload for conductor."""
    clean_message = " ".join(message.split())
    return {
        "target": target,
        "payload": clean_message,
        "text": clean_message,  # include both schemas for compatibility
        "source": "vera_ipc_client",
        "version": "1.1",
        "timestamp": datetime.datetime.now().isoformat(),
    }


def send_to_conductor(payload: dict, host: str, port: int) -> tuple:
    """Send payload to conductor and return (success, response)."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(TIMEOUT)

        print(f"[IPC] Connecting to {host}:{port}...")
        sock.connect((host, port))
        print(f"[IPC] Connected.")

        json_bytes = json.dumps(payload).encode("utf-8")
        print(f"[IPC] Sending {len(json_bytes)} bytes to {payload.get('target', 'conductor')}...")
        sock.sendall(json_bytes)

        # Receive full response (may be large for sub-agent output)
        response_data = b""
        sock.settimeout(TIMEOUT)
        while True:
            try:
                chunk = sock.recv(8192)
                if not chunk:
                    break
                response_data += chunk
            except socket.timeout:
                break

        sock.close()

        if not response_data:
            return False, "No response received from conductor"

        try:
            response = json.loads(response_data.decode("utf-8"))
            return True, response
        except json.JSONDecodeError:
            return False, f"Malformed response: {response_data[:200]}"

    except socket.timeout:
        return False, f"Timeout after {TIMEOUT}s — sub-agent may still be running"
    except ConnectionRefusedError:
        return False, (
            f"Connection refused at {host}:{port}. "
            f"Start conductor: python core/agent_conductor.py"
        )
    except OSError as e:
        return False, f"Socket error: {e}"


def check_status(host: str, port: int):
    """Quick conductor status check."""
    success, response = send_to_conductor({"ping": True}, host, port)
    if success:
        print(f"[IPC] VERA Conductor ONLINE at {host}:{port}")
        if isinstance(response, dict):
            uptime = response.get("conductor_uptime", "unknown")
            operatives = response.get("active_operatives", [])
            print(f"[IPC] Uptime: {uptime}")
            print(f"[IPC] Active operatives: {operatives if operatives else 'none'}")
    else:
        print(f"[IPC] VERA Conductor OFFLINE: {response}")


def main():
    args = parse_arguments()

    if args.status:
        check_status(args.host, args.port)
        return 0

    if not args.target or not args.raw_message:
        print("[IPC] ERROR: --target and --message are required.")
        print("[IPC] Use --status to check conductor health.")
        print("[IPC] Use --help for usage examples.")
        return 1

    payload = build_payload(args.target, args.raw_message)

    print(f"[IPC] Target:  {args.target}")
    print(f"[IPC] Message: {payload['payload'][:80]}{'...' if len(payload['payload']) > 80 else ''}")
    print("-" * 60)

    success, response = send_to_conductor(payload, args.host, args.port)

    if success:
        status = response.get("status", "UNKNOWN")
        message = response.get("message", "")
        result = response.get("result", "")

        print(f"\n[IPC] Status: {status}")
        print(f"[IPC] Message: {message}")

        if result:
            print(f"\n{'=' * 60}")
            print(f"SUB-AGENT OUTPUT [{args.target}]:")
            print(f"{'=' * 60}")
            print(result)
            print(f"{'=' * 60}")

        print(f"\n[VERA VERIFIED] Task routed and completed.")
        return 0
    else:
        print(f"\n[IPC FAILED] {response}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
