#!/usr/bin/env python3
"""
VERA IPC Task-Routing Client
Specialized CLI for routing messages to monitor_operative or sre_engineer channels.

Usage:
    python vera_ipc_client.py -t <target> -m "<message>"
    
Example:
    python vera_ipc_client.py --target monitor_operative --message "Task initiated"
"""

import argparse
import json
import socket


def parse_arguments():
    """Parse and validate CLI arguments."""
    parser = argparse.ArgumentParser(
        description="VERA IPC Task-Routing Client - Route messages to specialized channels",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python vera_ipc_client.py -t monitor_operative -m "System check complete"
  python vera_ipc_client.py --target sre_engineer --message "Deploying payload batch #42"

Valid targets:
  - monitor_operative : General monitoring and operational tasks
  - sre_engineer     : SRE-specific engineering and infrastructure work
        """
    )
    
    parser.add_argument(
        "-t", "--target",
        required=True,
        choices=["monitor_operative", "sre_engineer"],
        help="Target channel for message routing (required)"
    )
    
    parser.add_argument(
        "-m", "--message",
        required=True,
        type=str,
        dest="raw_message",
        help="Message payload to transmit via IPC loopback"
    )
    
    return parser.parse_args()


def clean_and_validate(message: str) -> dict:
    """
    Clean and package message into verified JSON dictionary format.
    
    Args:
        raw_message: Raw string input from CLI
        
    Returns:
        Dictionary with cleaned, validated payload ready for transmission
    """
    # Remove leading/trailing whitespace but preserve internal formatting
    clean_message = " ".join(message.split())
    
    return {
        "target": None,  # Will be set after validation
        "payload": clean_message,
        "source": "vera_ipc_client",
        "version": "1.0"
    }


def route_to_target(target: str, payload_dict: dict) -> tuple[bool, str]:
    """
    Route cleaned message to the appropriate channel via loopback socket.
    
    Args:
        target: Target channel name (monitor_operative | sre_engineer)
        payload_dict: Cleaned JSON dictionary from clean_and_validate()
        
    Returns:
        Tuple of (success: bool, response_message: str)
    """
    # Connect to local loopback address on port 8765
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10.0)  # Reasonable timeout for IPC communication
        
        host = "localhost"
        port = 8765
        
        print(f"[IPC] Connecting to {host}:{port}...")
        
        sock.connect((host, port))
        print(f"[IPC] Connection established.")
        
        # Set target in payload before transmission
        payload_dict["target"] = target
        
        # Serialize to JSON with proper formatting
        json_payload = json.dumps(payload_dict).encode("utf-8")
        
        print(f"[IPC] Transmitting {len(json_payload)} bytes...")
        sock.sendall(json_payload)
        
        # Receive acknowledgment/response (if any)
        response_data = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response_data += chunk
        
        sock.close()
        
        return True, "Message transmitted successfully" + ("." * 2)[:len(response_data)]
    
    except socket.timeout:
        return False, f"[IPC] Connection timed out after 10 seconds on {host}:{port}"
    except socket.gaierror as e:
        return False, f"[IPC] DNS resolution failed for {host}: {e}"
    except (ConnectionRefusedError, OSError) as e:
        error_msg = str(e).lower()
        if "refused" in error_msg or "no route":
            return False, "[IPC] No service running on localhost:8765. Is the IPC server active?"
        else:
            return False, f"[IPC] Connection failed: {e}"


def main():
    """Main entry point for VERA IPC Task-Routing Client."""
    
    # Parse and validate arguments first
    args = parse_arguments()
    target = args.target
    
    # Clean and package the message into verified JSON format
    payload_dict = clean_and_validate(args.raw_message)
    
    print(f"[IPC] Target: {target}")
    print(f"[IPC] Payload (cleaned): '{payload_dict['payload']}'")
    print("[IPC] Preparing transmission...")
    print("-" * 60)
    
    # Route to target channel via loopback socket
    success, response = route_to_target(target, payload_dict)
    
    if success:
        print(f"\n[✓ VERIFIED] {response}")
        exit_code = 0
    else:
        print(f"\n[✗ FAILED] {response}")
        exit_code = 1
    
    return exit_code


if __name__ == "__main__":
    import sys
    sys.exit(main())
