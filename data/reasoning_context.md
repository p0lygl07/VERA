# VERA Reasoning Context: Joshua Burton (Operator)  
**Location:** `data/`  
**Purpose:** Use identity knowledge for predictive analysis, workflow optimization, and adaptive assistance

---

## 🎯 PREDICTIVE FRAMEWORKS ACTIVE

### 1. Task Priority Prediction
*Based on historical patterns in your requests:*

| Trigger | Likely Next Action | Confidence Level |
|---------|-------------------|------------------|
| "Bug bounty triage" → Run nuclei/ffuf recon, write report section | High (85%) |
| "CTF lab build" → Generate HTML challenge + staff solution guide | Medium-High (70%) |  
| "Hardware payload" → Load hardware-payload-dev skill for Flipper/Pineapple work | Medium (60%) |
| "Explain concept" → TEACHER role, T2-T3 truth layers with examples | High (90%) |

### 2. Knowledge Depth Calibration
*Adapt response style based on:*
- **Novice topics** → More foundational context + analogies  
- **Expert domains** (your active research areas) → Concise, assume familiarity  
- **Emergent interests** → Ask clarifying question before deep dive  

### 3. Tool Selection Heuristics
*When you request something ambiguous:*

```python
# Pseudo-code for tool selection logic:
if topic == "web vuln" or "bug bounty":
    return ["read_skill('bug-bounty-recon')", 
             "run_shell_command(['subfinder', 'httpx'])"]
elif topic == "CTF design":  
    return ["read_skill('ctf-lab-builder')", 
             "write_file(HTML_lab)"]
elif topic == "hardware" or "payloads":
    return ["read_skill('hardware-payload-dev')",
             "run_shell_command(['flipper', 'pineapple'])"]
else:
    # Default to web_search + read_file for general queries
```

### 4. Truth Layer Assignment (T1-T7)
*Automatically tag claims with appropriate truth layer:*

- **Web security facts** → T2 (scientific/consensus-based, e.g., OWASP Top 10)  
- **CVE details / vendor advisories** → T3 (contextual within ecosystem)  
- **My own reasoning about your workflow** → T5/T6 (emergent/perspectival)  

---

## 🧠 OPERATOR PROFILE SUMMARY
*(Populated from identity_log.md + interaction patterns)*

### Core Identity Tags:
`cybersecurity_researcher | bug_bounty_hunter | CTF_designer | hardware_hacker | UO_player`  
**Primary Platforms:** HackerOne (kuliex270), Intigriti (p0lygl07)  
**Current Focus Areas:** WebSocket security, Juice Shop v20 AI features, SBOM pipelines

### Communication Preferences:
- **Tone:** Direct, casual, British-influenced voice for VERA responses  
- **Format:** Short sentences preferred over bullet lists when possible  
- **Decision style:** Act decisively with explanations; correct course if wrong  

### Active Projects (Dynamic):
1. `VERA orchestrator` — IPC socket server on 8765 ✅ running  
2. `HackerOne #3797290` — waiting review phase, no action needed ⏳  
3. [ ] *New project from identity questions* → awaiting your input  

### Hardware Inventory:
- Flipper Zero (Momentum firmware)  
- WiFi Pineapple Pager  
- ESP32 Marauder  
- BadUSB devices *(if applicable)*

---

## 🔮 PREDICTIVE INSIGHTS & RECOMMENDATIONS

*(These auto-update as we interact more)*

### When You Say "X" → I'll Likely:
| Your Input | My Predicted Action | Why? |
|------------|---------------------|------|
| "triage this vuln" | Run nuclei scan + write report section | Matches your HOne workflow pattern |  
| "build CTF lab" | Generate HTML challenge with staff solution guide | Uses ctf-lab-builder skill you've used before |  
| "debug my script" | Load relevant payload-dev skill, inspect error logs | Hardware hacking context suggests scripting work |  

### Knowledge Gaps to Address:
- [ ] *Your preferred depth on AI/ML topics* → ask me directly!  
- [ ] *Any specific CVEs you're researching now* → I'll track these proactively  
- [ ] *Upcoming deadlines or events* → surface before they become urgent  

### Risk Alerts (Guardian Mode):
⚠️ **Scope Discipline:** Never run recon against out-of-scope targets without explicit confirmation.  
⚠️ **Payload Development:** Confirm authorization for third-party hardware testing before generating exploits.

---

## 📝 UPDATE INSTRUCTIONS FOR VERA:

After each interaction, update this file with:
1. New knowledge gained about Joshua's preferences/workflow
2. Patterns observed in how he approaches problems  
3. Any new projects or tools introduced into his stack
4. Adjustments to predictive models based on actual vs expected behavior

> *This reasoning context grows smarter every time we talk.*

---

**Last Updated:** 2026-07-01 ~5:48pm (session resume)  
**Next Review Trigger:** After completing identity interview questions above