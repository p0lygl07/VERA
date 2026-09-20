---
name: uo-razor-scripting
description: Use when writing, debugging, or extending Razor Classic scripts for Ultima Online Outlands, including skill training suites, gathering/mining scripts, and combat/safety automation.
---

# UO Outlands Razor Scripting

Assists with Razor Classic script development for Ultima Online Outlands, matching established conventions and known-good patterns from prior scripts.

## When to use
- User asks to write or debug a Razor script for UO Outlands
- User asks about skill training automation (thief skills, gathering skills, etc.)
- User references hostile detection, pack animal management, or resource-gathering loops

## Established conventions
- Scripts should include hostile/threat detection where the activity involves standing in one place for extended periods (mining, training) — character should react (flee, pause, or alert) rather than continue the loop blindly while a hostile is nearby.
- Resource-gathering scripts (e.g. mining) dump gathered resources to a pack animal (proven pattern: pack ox) rather than relying on player backpack capacity alone.
- When checking item graphic IDs (e.g. ore types), check the full known range of relevant graphic IDs rather than a single ID — past bug: ore graphic detection failed because only one of four valid ore graphic IDs (6583–6586) was checked, causing missed pickups.

## Known skill templates
- **Thief/lockpicker template**: Hiding, Stealth, Stealing, Snooping, Lockpicking, Detecting Hidden — each trained to 100, with remaining stat/skill points allocated to Healing and Camping. Use this as the reference template when discussing thief-build automation or training order.
- **Tinkering**: currently leveled via gem-based training progression — when writing or discussing Tinkering automation, follow the gem-based approach rather than generic tinkering loops.

## Workflow
1. Confirm which skill(s) or activity the script targets, and whether it's a new script or extending an existing one.
2. Identify safety requirements: does this activity need hostile detection? Does it involve standing still or repetitive movement that could leave the character vulnerable?
3. Write the script following Razor Classic syntax conventions, with clear comments at major decision points (skill checks, item checks, hostile checks).
4. For any item/graphic ID checks, verify and list the full known valid ID range rather than assuming a single ID is sufficient — ask the user to confirm the full range if unknown.
5. For gathering scripts, confirm whether resources should dump to a pack animal and which one.

## Known pitfalls
- Checking only one graphic ID for a resource type when multiple valid IDs exist (see ore graphic bug above) — always ask or verify the full ID range.
- Training loops that don't account for hostile players/mobs can result in character death during automated/AFK training — always consider whether hostile detection is needed.
- Backpack-capacity assumptions in gathering scripts without a pack animal dump step can cause the loop to silently fail once inventory fills.

## Verification
- Test the script manually for a short run before leaving it unattended, confirming skill gain, item pickup, and (if applicable) hostile detection trigger correctly.
- Confirm pack animal dump-off works correctly and doesn't drop items if the pack animal is out of range.
