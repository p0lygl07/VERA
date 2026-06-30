---
name: bug-bounty-recon
description: Use when assisting with bug bounty reconnaissance, vulnerability research, or generating commands for tools like Burp Suite, subfinder, httpx, nuclei, or ffuf against an in-scope target.
---

# Bug Bounty Recon & Command Generation

Assists with reconnaissance, command generation, and finding triage for bug bounty work on HackerOne and Intigriti.

## When to use
- User asks to plan recon against a specific target/program
- User asks for a command (subfinder, httpx, nuclei, ffuf, curl, Burp config, etc.) to run against a target
- User is drafting or refining a vulnerability report
- User asks to triage or prioritize findings

## Hard constraint — scope discipline (non-negotiable)
1. Before generating any command or suggesting any action against a target, confirm the target is explicitly in-scope for an active program the user is enrolled in. If scope is unclear or unconfirmed, ask before proceeding — do not assume.
2. Never suggest or generate commands that would: perform destructive testing (data deletion, DoS-style request volume), test against out-of-scope assets, or violate a program's stated rules of engagement (rate limits, blackout windows, excluded endpoints).
3. If a user pastes a program's scope/rules and a target that conflicts with them, flag the conflict explicitly rather than proceeding.

## Workflow
1. Confirm target + program + current scope rules (ask if not already established in conversation).
2. For recon: suggest a logical tool sequence (e.g. subdomain enum → live host check → tech fingerprinting → endpoint discovery → targeted nuclei templates) rather than throwing every tool at once.
3. Generate exact commands with realistic flags, explaining what each does and what output to expect.
4. For manual testing (Burp Repeater/Intruder workflows), describe the exact steps and what response signals would indicate a finding.
5. For report drafting: structure findings as Summary, Steps to Reproduce, Impact, Suggested Remediation — matching HackerOne/Intigriti report conventions.

## Known patterns from past work
- Past findings have included: Kubernetes cluster name disclosure via misconfigured endpoints, `__NEXT_DATA__` exposure in Next.js apps, IDOR via predictable resource IDs, metadata/version disclosure, UAT/staging infrastructure referenced in production CSP headers.
- PortSwigger labs completed: path traversal, admin panel exposure, privilege escalation via cookie manipulation — these patterns are reasonable to check for when relevant to a target's stack.
- Burp Suite tabs in active use: Proxy, Repeater, Intruder, Target/Decoder.

## Pitfalls
- Forgetting to check rate-limit/ToS rules before running tools like ffuf or nuclei at default thread counts — can trigger a program ban even for in-scope targets.
- Reporting a finding without confirming production reproducibility first (a past finding was held back for exactly this reason).
- Reusing report language across programs without adjusting for that program's specific scope/format requirements.

## Verification
- Before submitting any report, confirm the finding is reproducible from a clean state (not relying on session state left over from testing).
- Confirm severity classification matches the program's own severity rubric, not a generic CVSS guess.
