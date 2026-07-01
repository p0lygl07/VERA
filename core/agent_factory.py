#!/usr/bin/env python3
"""VERA Sub-Agent Factory Module for smolagents deployment."""

import os
from smolagents import CodeAgent, HfApiModel

class SubAgentFactory:
    def __init__(self, model_id="Qwen/Qwen2.5-Coder-7B-Instruct"):
        # Utilizing local/configured inference endpoint via HfApiModel or similar smolagents provider
        self.model = HfApiModel(model_id=model_id)

    def create_operative(self, operative_type: str, custom_tools: list = None) -> CodeAgent:
        """Spawns a specialized sub-agent worker with restricted or targeted scope."""
        tools = custom_tools if custom_tools else []
        
        profiles = {
            "monitor_operative": {
                "name": "MonitorOperative",
                "description": "Specialized in continuous environmental scanning, endpoint monitoring, and log state verification.",
                "prompt": "You are VERA's Monitor Operative. Your sole focus is monitoring local log file streams, local ports, and system state metrics. Report back structural changes cleanly."
            },
            "sre_engineer": {
                "name": "SRE_Engineer",
                "description": "Specialized in configuration management, dependency resolution, and runtime environment hardening.",
                "prompt": "You are VERA's SRE Engineer. Your job is to safely maintain local runtime stability, install missing python packages, isolate dependency blocks, and repair workspace paths."
            }
        }
        
        if operative_type not in profiles:
            raise ValueError(f"Unknown operative profile type: {operative_type}")
            
        profile = profiles[operative_type]
        
        # Instantiate smolagents CodeAgent
        agent = CodeAgent(
            tools=tools,
            model=self.model,
            name=profile["name"],
            description=profile["description"],
            system_prompt=profile["prompt"]
        )
        print(f"[+] Sub-Agent [{profile['name']}] successfully built via factory matrix.")
        return agent