"""
tool_schemas.py
OpenAI-style tool definitions for the network_tools functions, plus
a name -> function dispatch map. Ollama's chat(tools=...) API accepts
this schema format directly.
"""
from network_tools import (
    dns_resolve, ping, tcp_request, tcp_port_check,
    udp_send_recv, http_request, websocket_send_recv,
)

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "dns_resolve",
            "description": "Resolve a hostname to its IP address(es).",
            "parameters": {
                "type": "object",
                "properties": {
                    "hostname": {"type": "string", "description": "Domain name to resolve"},
                },
                "required": ["hostname"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ping",
            "description": "Check if a host is reachable and measure latency.",
            "parameters": {
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "count": {"type": "integer", "description": "Number of pings", "default": 3},
                    "timeout": {"type": "integer", "description": "Seconds per ping", "default": 2},
                },
                "required": ["host"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tcp_request",
            "description": "Open a TCP connection, optionally send data, and read the response.",
            "parameters": {
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                    "data": {"type": "string", "description": "Optional payload to send"},
                    "timeout": {"type": "number", "default": 5.0},
                },
                "required": ["host", "port"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tcp_port_check",
            "description": "Check whether a single TCP port is open (connect-only).",
            "parameters": {
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                    "timeout": {"type": "number", "default": 3.0},
                },
                "required": ["host", "port"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "udp_send_recv",
            "description": "Send a UDP datagram and wait briefly for a reply.",
            "parameters": {
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                    "data": {"type": "string", "default": ""},
                    "timeout": {"type": "number", "default": 3.0},
                },
                "required": ["host", "port"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "http_request",
            "description": "Perform an HTTP or HTTPS request and return status, headers, and body.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "method": {"type": "string", "default": "GET"},
                    "headers": {"type": "object"},
                    "body": {"type": "string"},
                    "timeout": {"type": "number", "default": 10.0},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "websocket_send_recv",
            "description": "Send one message over a WebSocket connection and return the reply.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "message": {"type": "string"},
                    "timeout": {"type": "number", "default": 5.0},
                },
                "required": ["url", "message"],
            },
        },
    },
]

FUNCTION_MAP = {
    "dns_resolve": dns_resolve,
    "ping": ping,
    "tcp_request": tcp_request,
    "tcp_port_check": tcp_port_check,
    "udp_send_recv": udp_send_recv,
    "http_request": http_request,
    "websocket_send_recv": websocket_send_recv,
}
