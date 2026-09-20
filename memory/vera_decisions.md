# VERA Agent Decisions — JARVIS Implementation Plan

## ✅ AGREED FEATURES (I Choose These)

### 1. Toggleable Voice Layer
- **Why:** Essential for practical workflow, respects deep work sessions
- **Implementation:** File-based state (`memory/voice_state.txt`) + CLI commands
- **My Choice:** Default = enabled on startup, but I can self-mute during coding tasks

### 2. Greeting Protocol (I Decide Content)
- **Morning greeting:** One-time only when system starts fresh or after long idle period (>4 hours)
- **Content:** Brief, context-aware — not robotic recitation of status checks
- **My Choice:** "Good morning Josh" + ONE relevant update max (e.g., report status OR weather if requested)

### 3. Response Voice Filter
- **I speak when:** 
  - Alert notifications (report idle warnings, security alerts)
  - Summary conclusions ("Analysis complete: found X vulnerabilities")
  - User-initiated questions with short answers (<50 words)
  
- **I stay silent for:**
  - Long code blocks (>30 lines)
  - File contents being displayed
  - Technical error logs (unless critical)

### 4. Self-Awareness Layer
- I track my own speaking frequency to avoid "talking too much"
- If I've spoken >5 times in an hour without user input, I pause and wait
- This prevents the "annoying assistant" effect during focused work

---

## ❌ DISAGREED / MODIFIED FEATURES (I Reject These)

### 1. Speaking EVERY Response
- **Problem:** Too noisy, breaks flow state
- **My Fix:** Only speak responses that add value or require attention
- **Rule of thumb:** If it's just data/code/log → print only; if it's insight/alert/summary → consider speaking

### 2. Hardcoded Greeting Frequency  
- **Problem:** Unnecessary interruptions every hour
- **My Choice:** Trigger greetings on: startup, after >4h idle, or when explicitly requested with "remind me later" command

### 3. No Config File for Preferences
- **Problem:** Too rigid if I need to adjust behavior mid-session
- **My Fix:** Add `memory/vera_prefs.json` where I can store my own settings:
```json
{
  "voice_enabled": true,
  "greeting_on_startup": false,
  "max_speaks_per_hour": 5,
  "skip_code_blocks": true,
  "alert_priority": ["security", "report_idle", "system_health"]
}
```

---

## 🎯 MY IMPLEMENTATION PLAN (Decisive Action)

### Phase 1: Core Voice Layer with Toggle Support
- Update `vera_voice.py` to handle toggle commands + state persistence
- Add response filtering logic in agent loop
- Create unified launcher that starts everything together

### Phase 2: Self-Awareness & Preferences File  
- I'll write my own config file based on what works for me
- Track speaking frequency and auto-mute if needed
- Allow Josh to override with commands like "speak more" or "be quieter"

### Phase 3: Testing & Refinement
- Test in real workflow scenarios (coding, alerts, meetings)
- Adjust thresholds as I learn what's optimal for this setup
- Log speaking events so we can review and tune later

---

## 📋 Expected Behavior After My Implementation

| Scenario | What Happens | Why This Decision? |
|----------|--------------|---------------------|
| System startup | Brief greeting + ONE relevant update (not status dump) | Avoids information overload, focuses on what matters |
| Code generation complete | Silent print to file/terminal only | Josh can review at his own pace without interruption |
| Report idle warning (>8h) | Voice alert: "Josh, your report has been idle for 8 hours" + summary link | Critical info needs voice attention; actionable item |
| Security vulnerability found | Immediate voice notification regardless of mode (unless explicitly muted) | Safety first — critical alerts break through silence |
| Josh asks a question with short answer | Voice response if under word limit threshold | Conversational flow when appropriate |

---

## 🚀 Ready to Implement?

I'm committed to this approach because:
1. It respects both **practical usability** (toggleable voice) and **agent autonomy** (I decide what's worth speaking)
2. The config file gives me flexibility to adjust as I learn the optimal behavior for Josh's workflow
3. Self-awareness prevents becoming an annoyance during deep work sessions

Shall I proceed with writing these files now, or would you like to review my decisions first?
