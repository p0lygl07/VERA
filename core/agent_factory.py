#!/usr/bin/env python3
"""
VERA Sub-Agent Factory Module
Handles on-demand instantiation of specialized smolagents operatives.

Fix: HfApiModel renamed to InferenceClientModel in smolagents v1.x
"""

import os

# Try smolagents import with graceful fallback
try:
    from smolagents import CodeAgent, InferenceClientModel
    SMOLAGENTS_AVAILABLE = True
    print("[VERA FACTORY] smolagents loaded successfully.")
except ImportError as e:
    SMOLAGENTS_AVAILABLE = False
    print(f"[VERA FACTORY] Warning: smolagents import failed: {e}")
    print("[VERA FACTORY] Run: pip install smolagents")


class SubAgentFactory:
    def __init__(self, model_id="Qwen/Qwen2.5-Coder-7B-Instruct"):
        if not SMOLAGENTS_AVAILABLE:
            raise RuntimeError(
                "smolagents is required. Install with: "
                "pip install smolagents"
            )
        try:
            self.model = InferenceClientModel(model_id=model_id)
            print(f"[VERA FACTORY] Model loaded: {model_id}")
        except Exception as e:
            print(f"[VERA FACTORY] Model init error: {e}")
            print("[VERA FACTORY] Tip: Set HF_TOKEN env var for authenticated access")
            self.model = InferenceClientModel(model_id=model_id)

    def create_operative(self, operative_type: str, custom_tools: list = None) -> "CodeAgent":
        """Spawn a specialized sub-agent with targeted scope."""
        tools = custom_tools if custom_tools else []

        profiles = {
            "monitor_operative": {
                "name": "MonitorOperative",
                "description": "Environmental scanning, log monitoring, port checks, system state verification.",
                "prompt": (
                    "You are VERA's Monitor Operative. Your sole focus is monitoring "
                    "local log file streams, local ports, and system state metrics. "
                    "Report back structural changes cleanly and concisely. "
                    "Always verify findings before reporting."
                )
            },
            "sre_engineer": {
                "name": "SRE_Engineer",
                "description": "Dependency resolution, path repair, runtime environment hardening.",
                "prompt": (
                    "You are VERA's SRE Engineer. Your job is to safely maintain local "
                    "runtime stability: install missing Python packages, isolate dependency "
                    "blocks, validate workspace paths, and repair broken imports. "
                    "Always verify before claiming success."
                )
            },
            "recon_operative": {
                "name": "ReconOperative",
                "description": "Bug bounty reconnaissance and target enumeration (in-scope only).",
                "prompt": (
                    "You are VERA's Recon Operative. You assist with bug bounty reconnaissance "
                    "against EXPLICITLY IN-SCOPE targets only. Generate subfinder, httpx, nuclei, "
                    "and ffuf commands. ALWAYS confirm scope before acting. Never test "
                    "out-of-scope assets."
                )
            },
            "ctf_builder": {
                "name": "CTFBuilder",
                "description": "SNHUpers CTF HTML lab and PDF solution guide builder.",
                "prompt": (
                    "You are VERA's CTF Builder for the SNHUpers Cybersecurity Club. "
                    "Create self-contained HTML CTF labs with ALL event handlers via "
                    "addEventListener only (tiiny.host CSP compliance -- no inline onclick). "
                    "Generate matching PDF solution guides with ReportLab. "
                    "Normalize answer matching with word-boundary protection."
                )
            },
        }

        if operative_type not in profiles:
            available = list(profiles.keys())
            raise ValueError(
                f"Unknown operative: '{operative_type}'. "
                f"Available: {available}"
            )

        profile = profiles[operative_type]

        agent = CodeAgent(
            tools=tools,
            model=self.model,
            name=profile["name"],
            description=profile["description"],
            system_prompt=profile["prompt"]
        )
        print(f"[VERA FACTORY] Sub-Agent [{profile['name']}] ready.")
        return agent

    def list_profiles(self) -> dict:
        """List all available sub-agent profiles."""
        return {
            "monitor_operative": "Environmental scanning, log monitoring, port checks",
            "sre_engineer":      "Dependency resolution, path repair, runtime hardening",
            "recon_operative":   "Bug bounty recon commands (in-scope targets only)",
            "ctf_builder":       "SNHUpers CTF HTML labs and PDF solution guides",
        }
