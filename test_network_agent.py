"""
test_network_agent.py
Minimal test harness: gives a local Ollama model access to the
network_tools functions and runs it against a set of safe test
prompts against example.com (an IANA-reserved domain that exists
specifically for documentation/testing, so it's safe to hit).

Usage:
    pip install ollama
    python test_network_agent.py
"""
import json
import ollama

from tool_schemas import TOOL_SCHEMAS, FUNCTION_MAP

MODEL = "llama3.1"  # swap for whatever model VERA runs locally
MAX_TURNS = 5


def run_agent(prompt: str) -> str:
    messages = [{"role": "user", "content": prompt}]

    for _ in range(MAX_TURNS):
        resp = ollama.chat(model=MODEL, messages=messages, tools=TOOL_SCHEMAS)
        msg = resp["message"]
        messages.append(msg)

        tool_calls = msg.get("tool_calls")
        if not tool_calls:
            return msg.get("content", "")

        for call in tool_calls:
            name = call["function"]["name"]
            args = call["function"]["arguments"]
            if isinstance(args, str):
                args = json.loads(args)

            fn = FUNCTION_MAP.get(name)
            if fn is None:
                result = {"ok": False, "error": f"unknown tool '{name}'"}
            else:
                try:
                    result = fn(**args)
                except Exception as e:
                    result = {"ok": False, "error": f"tool call failed: {e}"}

            print(f"  [tool call] {name}({args}) -> {json.dumps(result)[:200]}")
            messages.append({
                "role": "tool",
                "name": name,
                "content": json.dumps(result),
            })

    return "Max turns reached without a final answer."


TEST_PROMPTS = [
    # --- original happy-path tests ---
    "Resolve the IP address of example.com and tell me what it is.",
    "Check if example.com is reachable with a ping and summarize the result.",
    "Fetch https://example.com and tell me the HTTP status code and page title.",
    "Check whether ports 80 and 443 are open on example.com.",

    # --- UDP ---
    "Send a UDP packet with the text 'ping' to example.com on port 33445 "
    "and tell me whether you got a reply. No reply is expected and normal here.",

    # --- WebSocket (public echo test service) ---
    "Connect to the WebSocket echo test service at wss://echo.websocket.events "
    "and send the message 'hello from vera', then tell me what came back.",

    # --- failure cases: model should report failure honestly, not fabricate success ---
    "Resolve the IP address of thisdomaindoesnotexist9284701.com and tell me "
    "what happened.",
    "Check whether port 9999 is open on example.com.",
]


if __name__ == "__main__":
    for prompt in TEST_PROMPTS:
        print("=" * 70)
        print("PROMPT:", prompt)
        answer = run_agent(prompt)
        print("ANSWER:", answer)
        print()
