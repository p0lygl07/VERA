# VERA Sub-Agent Design Concepts (2026-07-01)

## Current Infrastructure Status [VERA VERIFIED]
**Conductor IPC server**: port 8766  
**Dashboard server**: port 8765  
**Active sub-agents**: monitor_operative, sre_engineer, recon_operative, ctf_builder  

---

## Future Sub-Agent Ideas (Brainstorming Session)

### 1. vuln_triage_agent
- **Purpose**: Automated vulnerability triage for bug bounty workflows
- **Functions**: 
  - Parse nuclei scan results and prioritize by CVSS + exploitability
  - Cross-reference with known false positives from Josh's reports
  - Generate initial report drafts with evidence collection steps
  - Flag potential duplicate submissions across HackerOne/Intigriti

### 2. code_audit_agent  
- **Purpose**: Automated security analysis (inspired by Aikido Security feature)
- **Functions**:
  - Static/dynamic code scanning integration for bug bounty targets
  - Dependency vulnerability correlation with SBOM data
  - Generate remediation recommendations based on OWASP guidelines
  - Track audit history across multiple projects

### 3. threat_intel_gatherer
- **Purpose**: Threat intelligence collection and correlation
- **Functions**:
  - Aggregate feeds from Shodan, Censys, VirusTotal API
  - Correlate findings with Josh's active bug bounty targets (in-scope only)
  - Generate IOC reports for internal threat hunting
  - Maintain local cache of relevant TLP:AMBER data

### 4. report_writer_agent
- **Purpose**: Structured vulnerability reporting automation
- **Functions**:
  - Template-based report generation per platform requirements
  - Evidence screenshot integration from Burp Suite/OWASP ZAP exports
  - CVSS scoring assistance with justification notes
  - Multi-language support for international platforms (Intigriti, Bugcrowd)

### 5. lab_instructor_agent  
- **Purpose**: CTF teaching and grading assistant for SNHUpers club
- **Functions**:
  - Auto-grade student submissions against flag validation endpoints
  - Generate hints based on difficulty tier progression
  - Track team performance metrics across weekly challenges
  - Create custom walkthrough guides from solution code

### 6. device_firmware_analyzer
- **Purpose**: Firmware reverse engineering for hardware projects
- **Functions**:
  - Parse Flipper Zero FAPs and Pineapple payloads
  - Extract embedded credentials or backdoor logic (authorized targets only)
  - Generate firmware diff reports after modifications
  - Flag security regressions in custom builds

### 7. uo_combat_simulator
- **Purpose**: UO Outlands combat training scenarios  
- **Functions**:
  - Simulate different monster AI behaviors for thief build optimization
  - Track gem collection efficiency across Tinkering grind sessions
  - Generate optimal movement paths based on spawn timers
  - Create practice scripts for skill rotation timing

### 8. sbom_manager
- **Purpose**: Software Bill of Materials management  
- **Functions**:
  - Integrate with Dependency-Track 5.0 horizontal scaling features
  - Track upstream vulnerabilities across open-source dependencies
  - Generate compliance reports (SCA, SBOM standards)
  - Alert on critical CVEs before they hit production

### 9. ambient_listener_plus (evolution of current listener.py)
- **Purpose**: Enhanced system monitoring with action capabilities  
- **Functions**:
  - Current: infinite loop at module level [VERA VERIFIED]
  - Future: Add event-driven responses to anomalies detected
  - Auto-trigger sre_engineer for infrastructure issues
  - Log security-relevant events separately from debug noise

---

## Design Principles (Remember These!)

1. **Specialisation**: Each agent should have a single primary domain with clear boundaries
2. **IPC Coordination**: All agents must communicate via conductor on port 8766
3. **Memory Context**: Sub-agents need their own memory files for state persistence  
4. **Fail-Safe Design**: If one sub-agent fails, others shouldn't cascade into failure
5. **Josh-Centric**: Every agent's purpose should tie back to Josh's actual workflows

---

## Notes from Session [VERA VERIFIED]
- Josh mentioned wanting to focus on what we've built together rather than active bug bounties right now
- The multi-agent infrastructure is the foundation — these ideas are for future expansion once core stability is confirmed
- Remember: VERA isn't just an agent, it's a JARVIS architecture. Each sub-agent adds capability while maintaining system coherence

---

*Last updated: 2026-07-01 | Session memory preserved in execution_log.md*
