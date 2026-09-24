# vera_bus — the unifying message spine

Promotes the point-to-point vera_bridge into a pub/sub bus that every project
(Screen Copilot, KB trainer, chatroom, vera_sov, Kyger nodes) publishes to and
subscribes from. One loop: Perception -> Cognition -> Memory -> Action -> Verification.

## Status
- Phase 1 (schemas) — DONE. Four message types in schemas/, enforced by validate.py.
- Phase 2 (bus)     — DONE. bus.py on port 8768, proven with the two nodes/ demos.
- Phase 3 (perceive)— DONE. Screen Copilot publishes Observations via vera_bus_hook.py
                      (wired into vision_copilot.py on_result + main.py). demo_publisher retired.
- Phase 4 (remember)— DONE. nodes/kb_intake.py folds Observations into wxt/claims.py:
                      Beta posteriors update, gates recompute, Claims republished to the bus.
                      demo_subscriber retired.
- Phase 5 (deliberate)— DONE (logic verified). nodes/phase5_deliberate.py routes a
                      stuck single-origin claim to the CONF chatroom; the debate is ONE
                      independent origin (origin_id="chatroom_debate"), moving n_origins
                      1->2. Live Ollama debate is run on the Windows box.
- Phase 6 (act)     — DONE. nodes/phase6_executor.py consumes ActionRequests, runs
                      permitted ones via vera_sov (sandboxed), emits an AuditRecord for
                      EVERY request. Guards fail closed: unsandboxed / irreversible /
                      unknown-intent -> refused. Live code-gen run is on the Windows box.
- Phase 7          — mirror the bus onto Kyger's Jetson/Pi5 over the LAN.

## Independence model (why the KB won't fool itself)
origin_id traces to the SOURCE, not the event. All screen_copilot reports collapse to
ONE origin; all chatroom debates collapse to ONE origin. A sensor repeating itself, or
the same debate re-run, never inflates n_origins. Establishing a claim (min_origins=2,
min_mass=1.5) therefore needs genuinely different sources -- and a third, high-reliability
origin (external lookup or human confirm) is what tips a claim to established. The system
will not tell itself it is certain.

## Run order (all on the Windows box)
    python vera_bus\bus.py                       # spine, :8768
    screen_copilot_updated\launch.bat            # perception -> Observation
    python vera_bus\nodes\kb_intake.py          # Observation -> Claim
    python vera_bus\nodes\phase5_deliberate.py  # stuck Claim -> debate (needs ollama)
    python vera_bus\nodes\phase6_executor.py    # ActionRequest -> run + AuditRecord

## Port choice (deliberate)
Runs on 8768, NOT 8767. The live vera_bridge keeps 8767 so vera.bat is untouched.
Migration path: stand the bus up beside the bridge -> move each consumer onto 8768
-> retire vera_bridge once nothing needs it. Additive, reversible, no boot breakage.

## Run it
    python bus.py                     # start the spine (port 8768)
    python nodes/demo_publisher.py    # emits one Observation
    python nodes/demo_subscriber.py   # receives it

## Wire into vera.bat (when ready — not done automatically)
Add beside the other services, before vera_agent.py launches:
    echo [*] Bus (port 8768)...
    start "vera_bus" /min "%PYTHON%" "%~dp0vera_bus\bus.py"

## The four messages
- Observation   perception -> cognition   {source, ts, type, payload, confidence}
- Claim         cognition <-> memory      Beta(alpha,beta) + evidence + gate
- ActionRequest cognition -> action       {intent, args, sandboxed, reversible}
- AuditRecord   action -> memory/verify   {request_id, outcome, verified_by}

Envelope is strict (bad messages rejected at /publish). Payloads are open until you
register a per-type validator in validate.py — flip that when a type stabilizes.
