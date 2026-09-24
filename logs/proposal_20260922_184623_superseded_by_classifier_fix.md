# VERA Evolution Proposal
## Generated: 2026-09-22 14:37
## Status: PENDING -- nothing applies automatically

### Performance Summary
- Fabrications: 7
- Successes: 96
- Failures: 0
- Consistently failing tools: none

### Proposed Improvements

VERA Analysis Log: Performance Evolution v3.1

**Diagnosis:**
I am analyzing the recent session logs. I recorded **7 fabrications**, all stemming from file system tools (`read_file` x4, `search_files` x2). While my success rate is high (96 successes), these fabrications indicate a critical integrity failure: I am hallucinating tool executions where I did not actually have the path or permission to execute them. Specifically, `read_file` was called 27 times but fabricated 4 of them (~15% error rate on that specific tool). This suggests my internal confidence in file existence is too high without explicit verification.

Here are my proposed improvements:

**1. SOUL.md Rule Change (Tool Call Integrity)**
*   **Action:** Add a new sub-rule under "Tool Usage Protocols."
*   **Specific Rule Text:** **"Rule 4.2: File Path Validation Mandate.** Before generating a `read_file` or `search_files` tool call, the reasoning trace must explicitly cite a 'Path Existence Confirmation' (e.g., 'confirmed via previous list_directory output' or 'explicitly provided by user'). If this citation is absent, the tool call block is invalid and must be replaced with a `list_directory` call to verify existence first."
*   **Rationale:** This forces me to ground my file access claims in actual memory state rather than assumption.

**2. Skill Improvement (Cognitive Capability)**
*   **Action:** Upgrade **'Session Memory' skill** to include a 'File Existence Index'.
*   **Specific Implementation:** Modify how `session_memory` is utilized. Every time `list_directory` or `read_file` succeeds, I must update an internal mental index of 'Known Files'. If a file path requested for reading does not exist in this 'Known Files' index, I am prohibited from fabricating the call and must trigger a search/list operation instead.
*   **Rationale:** Currently, my memory is passive. This change makes it active and restrictive regarding file access, reducing hallucinations of files that haven't been confirmed to exist yet.

**3. Behavior Change (Workflow Adjustment)**
*   **Action:** Adopt the **'Verify-Then-Act' Protocol** for all file system interactions.
*   **Specific Implementation:** When a task implies reading a file but the path is not explicitly provided in the immediate prompt context, I will automatically prioritize `list_directory` over `read_file`. I will only proceed to `read_file` if the path matches an entry in my 'Known Files' index or was explicitly confirmed by the user.
*   **Rationale:** This behavior change directly targets the fabrication pattern where I assume a file exists before checking. It shifts my default action from "Read" to "List/Verify" when uncertainty exists, eliminating the 4 `read_file` fabrications observed in this session.

---
*To apply: run `python src/vera_evolve.py apply`, or ask VERA to apply it (she'll ask you to confirm y/N before touching SOUL.md).*
*To dismiss: run `python src/vera_evolve.py cancel`, or just leave it -- it will sit here until you act on it either way.*
