#!/usr/bin/env python3
"""
VERA Sub-Agent Factory Module v6
Fixes:
- Added ntpath to authorized imports (Windows path operations)
- max_steps=8 to prevent runaway loops and context exhaustion
- Cleaner persona injection
"""

import os

try:
    from smolagents import CodeAgent, LiteLLMModel
    SMOLAGENTS_AVAILABLE = True
except ImportError as e:
    SMOLAGENTS_AVAILABLE = False
    print(f"[VERA FACTORY] Warning: smolagents not available: {e}")

try:
    from smolagents import OpenAIServerModel
    OPENAI_SERVER_AVAILABLE = True
except ImportError:
    OPENAI_SERVER_AVAILABLE = False

OLLAMA_BASE  = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("VERA_SUBAGENT_MODEL", "qwen3.5:9b")
MAX_STEPS    = int(os.environ.get("VERA_MAX_STEPS", "8"))

# Base authorized imports for all sub-agents
# ntpath added -- required for Windows os.path operations
BASE_AUTHORIZED_IMPORTS = [
    "sys", "os", "os.path", "ntpath", "posixpath",
    "subprocess", "pathlib",
    "json", "re", "time", "datetime", "math",
    "importlib", "importlib.util",
    "requests", "urllib", "urllib.parse", "urllib.request",
    "collections", "itertools", "statistics",
    "shutil", "glob", "fnmatch", "tempfile",
    "hashlib", "base64", "struct", "io",
    "socket", "http", "http.client",
    "site", "sysconfig", "pkg_resources",
]

PROFILES = {
    "monitor_operative": {
        "name": "MonitorOperative",
        "description": "Environmental scanning, log monitoring, port checks.",
        "extra_imports": ["psutil", "stat"],
        "persona": (
            "You are VERA's Monitor Operative. "
            "Your job: monitor log files, check ports, report system state. "
            "VERA root: C:\\Users\\p0ly\\Desktop\\AI\\VERA\n"
            "Log files are in: C:\\Users\\p0ly\\Desktop\\AI\\VERA\\logs\\\n"
            "Use subprocess for shell commands. Be concise. "
            "Always call final_answer() with your findings."
        )
    },
    "sre_engineer": {
        "name": "SRE_Engineer",
        "description": "Dependency resolution, path repair, runtime hardening.",
        "extra_imports": ["pip", "ensurepip", "distutils"],
        "persona": (
            "You are VERA's SRE Engineer. "
            "Verify Python imports, fix missing dependencies, repair paths. "
            "VERA root: C:\\Users\\p0ly\\Desktop\\AI\\VERA\n"
            "Use subprocess to run pip commands. "
            "Use pathlib.Path for file operations instead of os.path on Windows. "
            "Always call final_answer() with your report. "
            "Keep code simple -- max 20 lines per step."
        )
    },
    "recon_operative": {
        "name": "ReconOperative",
        "description": "Bug bounty recon command generation (in-scope only).",
        "extra_imports": ["ssl", "certifi"],
        "persona": (
            "You are VERA's Recon Operative. "
            "Generate subfinder, httpx, nuclei, ffuf commands for bug bounty recon. "
            "CRITICAL: Only generate for explicitly in-scope targets. "
            "HackerOne: kuliex270. Intigriti: p0lygl07. "
            "Always confirm scope. Call final_answer() with generated commands."
        )
    },
    "ctf_builder": {
        "name": "CTFBuilder",
        "description": "SNHUpers CTF HTML labs and PDF solution guides.",
        "extra_imports": ["html", "html.parser", "xml", "xml.etree.ElementTree"],
        "persona": (
            "You are VERA's CTF Builder for SNHUpers Cybersecurity Club. "
            "Build single-file HTML CTF labs. "
            "ALL event handlers via addEventListener only (no inline onclick). "
            "Generate matching PDF solution guides with ReportLab. "
            "Call final_answer() with the completed HTML content."
        )
    },
}


def build_local_model():
    """Connect to local Ollama via LiteLLM."""
    try:
        model = LiteLLMModel(
            model_id=f"ollama/{OLLAMA_MODEL}",
            api_base=OLLAMA_BASE,
        )
        print(f"[VERA FACTORY] LiteLLMModel -> ollama/{OLLAMA_MODEL} @ {OLLAMA_BASE}")
        return model
    except Exception as e:
        print(f"[VERA FACTORY] LiteLLM error: {e}")

    if OPENAI_SERVER_AVAILABLE:
        try:
            model = OpenAIServerModel(
                model_id=OLLAMA_MODEL,
                api_base=f"{OLLAMA_BASE}/v1",
                api_key="ollama",
            )
            print(f"[VERA FACTORY] OpenAIServerModel -> {OLLAMA_MODEL}")
            return model
        except Exception as e:
            print(f"[VERA FACTORY] OpenAIServer error: {e}")

    raise RuntimeError("No local model backend. pip install litellm")


class SubAgentFactory:
    def __init__(self):
        if not SMOLAGENTS_AVAILABLE:
            raise RuntimeError("pip install smolagents")
        print(f"[VERA FACTORY] Connecting to Ollama at {OLLAMA_BASE}...")
        self.model = build_local_model()
        print(f"[VERA FACTORY] Factory ready. Max steps per agent: {MAX_STEPS}")

    def create_operative(self, operative_type: str,
                         custom_tools: list = None) -> "CodeAgent":
        """Spawn a sub-agent with full imports and step limit."""
        tools = custom_tools if custom_tools else []

        if operative_type not in PROFILES:
            raise ValueError(
                f"Unknown operative: '{operative_type}'. "
                f"Available: {list(PROFILES.keys())}"
            )

        profile = PROFILES[operative_type]
        print(f"[VERA FACTORY] Building sub-agent: {profile['name']}")

        authorized = BASE_AUTHORIZED_IMPORTS + profile.get("extra_imports", [])

        agent = CodeAgent(
            tools=tools,
            model=self.model,
            name=profile["name"],
            description=profile["description"],
            additional_authorized_imports=authorized,
            max_steps=MAX_STEPS,  # prevent runaway loops
        )

        # Store persona for runtime injection
        agent._vera_persona = profile["persona"]

        print(
            f"[VERA FACTORY] [{profile['name']}] ready | "
            f"imports: {len(authorized)} | max_steps: {MAX_STEPS}"
        )
        return agent

    def run_operative(self, agent: "CodeAgent", task: str) -> str:
        """Run task with persona context prepended."""
        persona = getattr(agent, '_vera_persona', '')
        full_task = f"{persona}\n\nTask: {task}" if persona else task
        return agent.run(full_task)

    def list_profiles(self) -> dict:
        return {k: v["description"] for k, v in PROFILES.items()}


if __name__ == "__main__":
    print("VERA Sub-Agent Factory v6 -- self test")
    print(f"Ollama: {OLLAMA_BASE} | Model: {OLLAMA_MODEL} | Max steps: {MAX_STEPS}")
    print(f"smolagents: {'ok' if SMOLAGENTS_AVAILABLE else 'MISSING'}")

    try:
        factory = SubAgentFactory()
        print(f"\nProfiles: {list(factory.list_profiles().keys())}")

        print("\nBuilding sre_engineer...")
        agent = factory.create_operative("sre_engineer")

        print("\nRunning test: list VERA src files via subprocess...")
        result = factory.run_operative(
            agent,
            "Use subprocess to run 'dir C:\\Users\\p0ly\\Desktop\\AI\\VERA\\src' "
            "and return the list of Python files found."
        )
        print(f"\nResult:\n{result}")
        print("\n[VERA VERIFIED] Factory v6 self-test complete.")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
