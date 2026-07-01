#!/usr/bin/env python3
"""
VERA Sub-Agent Factory Module
Handles on-demand instantiation of specialized smolagents operatives.
"""

import os

# Try smolagents import with graceful fallback
try:
    from smolagents import CodeAgent, HfApiModel
    SMOLAGENTS_AVAILABLE = True
except ImportError:
    SMOLAGENTS_AVAILABLE = False
    print("[VERA FACTORY] Warning: smolagents not installed. Run: pip install smolagents")


class SubAgentFactory:
    def __init__(self, model_id="Qwen/Qwen2.5-Coder-7B-Instruct"):
        if not SMOLAGENTS_AVAILABLE:
            raise RuntimeError("smolagents is required. Install with: pip install smolagents")
        # Use local Ollama endpoint if available, fall back to HF API
        ollama_base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        try:
            self.model = HfApiModel(model_id=model_id)
        except Exception as e:
            print(f"[VERA FACTORY] HF model init error: {e}")
            self.model = HfApiModel(model_id=model_id)

    def create_operative(self, operative_type: str, custom_tools: list = None) -> "CodeAgent":
        """Spawns a specialized sub-agent worker with restricted or targeted scope."""
        tools = custom_tools if custom_tools else []

        profiles = {
            "monitor_operative": {
                "name": "MonitorOperative",
                "description": "Specialized in continuous environmental scanning, endpoint monitoring, and log state verification.",
                "prompt": (
                    "You are VERA's Monitor Operative. Your sole focus is monitoring "
                    "local log file streams, local ports, and system state metrics. "
                    "Report back structural changes cleanly and concisely."
                )
            },
            "sre_engineer": {
                "name": "SRE_Engineer",
                "description": "Specialized in configuration management, dependency resolution, and runtime environment hardening.",
                "prompt": (
                    "You are VERA's SRE Engineer. Your job is to safely maintain local "
                    "runtime stability, install missing Python packages, isolate dependency "
                    "blocks, and repair workspace paths. Always verify before claiming success."
                )
            },
            "recon_operative": {
                "name": "ReconOperative",
                "description": "Specialized in bug bounty reconnaissance and target enumeration.",
                "prompt": (
                    "You are VERA's Recon Operative. You assist with bug bounty reconnaissance "
                    "against explicitly in-scope targets only. Generate subfinder, httpx, nuclei, "
                    "and ffuf commands. Always confirm scope before acting."
                )
            },
            "ctf_builder": {
                "name": "CTFBuilder",
                "description": "Specialized in building SNHUpers CTF lab files and solution guides.",
                "prompt": (
                    "You are VERA's CTF Builder. You create self-contained HTML CTF labs "
                    "for the SNHUpers Cybersecurity Club. All event handlers via addEventListener "
                    "only (tiiny.host CSP compliance). Generate matching PDF solution guides."
                )
            },
        }

        if operative_type not in profiles:
            available = list(profiles.keys())
            raise ValueError(f"Unknown operative type: '{operative_type}'. Available: {available}")

        profile = profiles[operative_type]

        agent = CodeAgent(
            tools=tools,
            model=self.model,
            name=profile["name"],
            description=profile["description"],
            system_prompt=profile["prompt"]
        )
        print(f"[VERA FACTORY] Sub-Agent [{profile['name']}] built successfully.")
        return agent

    def list_profiles(self):
        """List all available sub-agent profiles."""
        return {
            "monitor_operative": "Environmental scanning, log monitoring, port checks",
            "sre_engineer": "Dependency resolution, path repair, runtime hardening",
            "recon_operative": "Bug bounty recon, subfinder/httpx/nuclei command generation",
            "ctf_builder": "SNHUpers CTF lab HTML files and PDF solution guides",
        }
