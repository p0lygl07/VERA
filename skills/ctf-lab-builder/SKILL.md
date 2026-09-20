---
name: ctf-lab-builder
description: Use when building self-contained HTML CTF labs for SNHUpers Cybersecurity Club weekly challenges, including matching staff solution guides.
---

# CTF Lab Builder

Builds self-contained, single-file HTML CTF labs for the SNHUpers Cybersecurity Club, plus a matching staff solution guide PDF.

## When to use
- User asks to build/draft a CTF lab, challenge, or weekly exercise for SNHUpers
- User references lab topics like CORS exploitation, Blue Team log analysis, OSINT threat attribution, or similar offensive/defensive security training scenarios
- User asks for a "staff solution guide" or answer key to accompany a lab

## Hard constraints (do not deviate)
1. **tiiny.host CSP compliance** — all event handlers must be wired via `addEventListener`, never inline `onclick=""` or similar attributes. Inline event handlers will be blocked by tiiny.host's Content Security Policy.
2. **Self-contained single file** — the lab must be a single HTML file with embedded CSS/JS, no external dependencies that won't survive a static host.
3. **Normalized answer matching** — when checking a user's submitted answer, normalize input (trim whitespace, case-insensitive compare) and apply word-boundary protection so partial substring matches don't produce false positives/negatives.
4. **Staff solution guide as PDF** — generate the accompanying solution guide using ReportLab, matching the visual styling used in prior weeks (consistent header/footer, consistent typography — confirm current style reference with user if unclear).

## Workflow
1. Confirm the week's topic and learning objective with the user if not already clear.
2. Draft the lab scenario/narrative first — CTF labs should have a short framing story consistent with prior weeks' tone.
3. Build the HTML lab file:
   - Embed all CSS/JS inline
   - Use addEventListener for every interactive element
   - Implement the answer-check logic with normalized matching + word-boundary protection
   - Test the answer logic against both the correct answer and plausible near-miss wrong answers
4. Generate the staff solution guide as a PDF via ReportLab, including the correct answer, explanation of the vulnerability/technique, and any relevant screenshots or code snippets.
5. Confirm both files together before considering the task complete — a lab without its solution guide is incomplete.

## Known pitfalls
- Inline event handlers silently fail on tiiny.host due to CSP — always addEventListener.
- Naive substring answer matching causes false positives (e.g. "admin" matching inside "administrator123"). Always apply word-boundary checks.
- Forgetting to normalize case/whitespace causes legitimate correct answers to fail.

## Verification
- Open the HTML file standalone (no server) and confirm all interactivity works with no console errors.
- Submit the exact correct answer and confirm it passes.
- Submit a near-miss wrong answer and confirm it correctly fails.
- Open the generated PDF and confirm it matches the established visual style.
