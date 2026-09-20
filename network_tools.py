"""
network_tools.py
Core network-protocol functions exposed as callable tools for an
LLM agent (designed for Ollama's OpenAI-style tool-calling API).

Each function returns a plain dict so results serialize cleanly
into a tool-response message.
"""
import socket
import subprocess
import platform
import ssl
import urllib.request
import urllib.error


# ---------------------------------------------------------------------
# DNS
# ---------------------------------------------------------------------
def dns_resolve(hostname: str) -> dict:
    """Resolve a hostname to its IPv4/IPv6 addresses."""
    try:
        infos = socket.getaddrinfo(hostname, None)
        addrs = sorted({info[4][0] for info in infos})
        return {"ok": True, "hostname": hostname, "addresses": addrs}
    except socket.gaierror as e:
        return {"ok": False, "hostname": hostname, "error": str(e)}


# ---------------------------------------------------------------------
# Reachability (system ping; raw ICMP needs root so we shell out instead)
# ---------------------------------------------------------------------
def ping(host: str, count: int = 3, timeout: int = 2) -> dict:
    """Check host reachability and latency using the system ping utility."""
    is_windows = platform.system().lower() == "windows"
    count_flag = "-n" if is_windows else "-c"
    timeout_flag = "-w" if is_windows else "-W"
    cmd = ["ping", count_flag, str(count), timeout_flag, str(timeout), host]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout * count + 5
        )
        return {
            "ok": result.returncode == 0,
            "host": host,
            "output": result.stdout.strip()[-1000:],
        }
    except Exception as e:
        return {"ok": False, "host": host, "error": str(e)}


# ---------------------------------------------------------------------
# TCP
# ---------------------------------------------------------------------
def tcp_request(host: str, port: int, data: str = "", timeout: float = 5.0,
                 recv_bytes: int = 4096) -> dict:
    """Open a TCP connection, optionally send data, and read a response."""
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            if data:
                sock.sendall(data.encode("utf-8", errors="replace"))
            sock.settimeout(timeout)
            try:
                response = sock.recv(recv_bytes)
            except socket.timeout:
                response = b""
            return {
                "ok": True, "host": host, "port": port,
                "sent_bytes": len(data),
                "received": response.decode("utf-8", errors="replace"),
            }
    except Exception as e:
        return {"ok": False, "host": host, "port": port, "error": str(e)}


def tcp_port_check(host: str, port: int, timeout: float = 3.0) -> dict:
    """Check whether a single TCP port is open (connect-only, no banner grab)."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return {"ok": True, "host": host, "port": port, "open": True}
    except Exception as e:
        return {"ok": True, "host": host, "port": port, "open": False, "detail": str(e)}


# ---------------------------------------------------------------------
# UDP
# ---------------------------------------------------------------------
def udp_send_recv(host: str, port: int, data: str = "", timeout: float = 3.0,
                   recv_bytes: int = 4096) -> dict:
    """Send a UDP datagram and wait briefly for a reply (no reply is normal for many UDP services)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout)
            sock.sendto(data.encode("utf-8", errors="replace"), (host, port))
            try:
                response, _ = sock.recvfrom(recv_bytes)
                return {"ok": True, "host": host, "port": port,
                        "received": response.decode("utf-8", errors="replace")}
            except socket.timeout:
                return {"ok": True, "host": host, "port": port, "received": None,
                        "note": "no response within timeout"}
    except Exception as e:
        return {"ok": False, "host": host, "port": port, "error": str(e)}


# ---------------------------------------------------------------------
# HTTP / HTTPS
# ---------------------------------------------------------------------
def http_request(url: str, method: str = "GET", headers: dict = None,
                  body: str = None, timeout: float = 10.0) -> dict:
    """Perform an HTTP/HTTPS request; returns status, headers, and up to 1MB of body text."""
    headers = headers or {}
    try:
        req = urllib.request.Request(
            url, method=method.upper(), headers=headers,
            data=body.encode("utf-8") if body else None,
        )
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read(1_000_000)
            return {
                "ok": True, "url": url, "status": resp.status,
                "headers": dict(resp.getheaders()),
                "body": raw.decode("utf-8", errors="replace"),
            }
    except urllib.error.HTTPError as e:
        return {"ok": False, "url": url, "status": e.code, "error": str(e)}
    except Exception as e:
        return {"ok": False, "url": url, "error": str(e)}


# ---------------------------------------------------------------------
# WebSocket (optional: pip install websocket-client)
# ---------------------------------------------------------------------
def websocket_send_recv(url: str, message: str, timeout: float = 5.0) -> dict:
    """Send one message over a WebSocket connection and return the first reply."""
    try:
        import websocket
    except ImportError:
        return {"ok": False, "error": "websocket-client not installed (pip install websocket-client)"}
    try:
        ws = websocket.create_connection(url, timeout=timeout)
        ws.send(message)
        reply = ws.recv()
        ws.close()
        return {"ok": True, "url": url, "sent": message, "received": reply}
    except Exception as e:
        return {"ok": False, "url": url, "error": str(e)}
