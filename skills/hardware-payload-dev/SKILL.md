---
name: hardware-payload-dev
description: Use when developing or debugging Flipper Zero FAPs, WiFi Pineapple Pager payloads, ESP32 Marauder configs, or BadUSB payloads for authorized hardware hacking and red team work.
---

# Hardware Payload Development

Assists with Flipper Zero, WiFi Pineapple Pager, ESP32 Marauder, and BadUSB payload development for authorized red team assessments and personal hardware projects.

## When to use
- User asks to write or debug a Flipper Zero FAP (built via ufbt)
- User asks about WiFi Pineapple Pager payloads (Jelly Sentinel framework)
- User asks about ESP32 Marauder configuration
- User asks about BadUSB payloads for recon/exfiltration

## Hard constraint — authorization discipline (non-negotiable)
1. Before generating or refining any payload intended for deployment against a device or network the user doesn't own outright, confirm there is explicit written authorization (e.g. a signed red team engagement scope) for the target. If unconfirmed, ask before proceeding.
2. Payloads intended for the user's own devices (personal Flipper, personal test machines, home lab) don't require this check — only third-party targets do.
3. Never generate payloads designed to cause persistent damage, data destruction, or access that exceeds an engagement's documented scope.

## Established conventions
- Flipper Zero: running Momentum firmware. Custom FAPs (e.g. "ADB Utility") are compiled with ufbt — confirm ufbt toolchain is set up before debugging build errors, since most build failures trace back to environment/toolchain issues rather than the FAP source itself.
- WiFi Pineapple Pager: payloads built on the Jelly Sentinel framework. Follow Jelly Sentinel's module structure rather than writing standalone scripts when a module pattern fits the task.
- ESP32 Marauder: used for wireless red team assessments alongside the Pineapple Pager — useful for deauth/scanning workflows during authorized engagements.
- BadUSB payloads: existing patterns target Windows and Android recon, exfiltrating collected data to a webhook endpoint. When extending these, keep the exfil destination configurable rather than hardcoded, so it's easy to swap per engagement.

## Workflow
1. Confirm target device/platform (Flipper/Pineapple/ESP32/BadUSB) and authorization status per the hard constraint above.
2. Confirm whether this extends an existing payload or starts a new one.
3. Write/debug the payload, calling out platform-specific quirks (e.g. ufbt build flags, Jelly Sentinel module hooks).
4. If exfiltration is involved, confirm the destination (webhook or otherwise) and ensure it's parameterized, not hardcoded.
5. Note any detection signatures the payload might trigger (useful for the eventual engagement report).

## Known pitfalls
- ufbt build errors are usually toolchain/environment issues, not code issues — check ufbt setup before deep-debugging FAP source.
- Hardcoded exfil endpoints make payloads harder to reuse safely across engagements and risk accidentally exfiltrating real engagement data to a stale/test webhook.
- Forgetting authorization scope when adapting a payload originally built for one engagement to a new target.

## Verification
- Test new payloads against a personal/lab device before any engagement deployment.
- Confirm exfil destination is correct and reachable before relying on it during a live engagement.
- For wireless tooling (Pineapple/Marauder), confirm scan/deauth behavior stays within the engagement's documented scope and timing window.
