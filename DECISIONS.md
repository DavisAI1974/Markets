# DECISIONS.md — the binding-decision ledger (append-only)

Born S110 (turnaround memo 2.5). One line per binding decision. **Status vocabulary:**
DECIDED (stated, nothing enforces it yet) -> BUILT (mechanism exists) -> WIRED (mechanism is in the
live path) -> VERIFIED (negative-tested / proven executing) | RETIRED (no longer binding, reason).
**"Enforced by: doc-only" is the dangerous class** — the conformance sweep flags any DECIDED/doc-only
line older than two sessions, because decided-then-dropped-then-relitigated is the disease this file
kills. Never delete a line; supersede it with a new one.

| # | session | decision (verbatim where possible) | status | enforced by |
|---|---|---|---|---|
| D1 | S107 (Greg) | Keys do NOT rotate during the walk; rotation happens after, as its own item | DECIDED | doc (CLAUDE.md AWS section + every drop-in) — expires at walk end, then becomes paper-trading item G5 |
| D2 | S102/S105 (Greg) | The blind's ONLY deliberate mask is the PRICE CURVE; anything else missing is a DEFECT | VERIFIED | state_health hard gates + the data doctrine in agents/README.md |
| D3 | S109 | Causality is physics, not a mask: specialists run on per-day causal slices; a second job with an earlier decision point gets its own earlier slice | VERIFIED | build_causal_slices.py self-audit + forward_stamps + SOP STEP 3 |
| D4 | S108 (Greg) | NEVER average above and below; report per-day, sum-abs-err, drift AND survival together | WIRED | blind_score_nonpooled.py + SOP STEP 3.5 |
| D5 | S105 (Greg) | One group at a time; stage all, run one; windows Sunday -> second Friday | WIRED | SOP + group_config |
| D6 | S97 (Greg) | Refined rules NEVER override blind-applicable ones; the blind-vs-refined gap IS the measurement | WIRED | brain play schema (requires/scope/forward_evidence) + merge adjudication |
| D7 | S105 (Greg) | Blind and refine are ONE engine; no blind-specific rule file may exist | VERIFIED | verify_gold runtime-drift wall + the deleted blind stack |
| D8 | S104/S105 | Brain merges are PROPOSAL FILES + adjudication, incumbents byte-identical; never a direct edit | WIRED | merge protocol + backups (ng_brain_*_backup.json) |
| D9 | S108 | Before any refine, the blind archives by MOVE; a refine posterior byte-identical to its blind archive is rejected | VERIFIED | archive_blind.py + assert_not_the_blind (negative-tested on the G21 near-miss) |
| D10 | S110 (Greg) | NOTHING runs off-SOP: gap -> STOP -> propose diff -> Greg go -> version log -> execute; deviations are recorded nonconformances; gates cannot be skipped or softened | WIRED | agents/RUN_SOP.md v1.1 CHANGE CONTROL + this ledger |
| D11 | S110 | No fix is DONE until a test proves the fixed path EXECUTES and the guard fires on the original defect (the f2 lesson: S108's fix was verified on one reader, dead on the other, gate watching the wrong reader for two groups) | DECIDED | SOP v1.2 STEP 2 (this session) — becomes VERIFIED when the first fix ships under it |
| D12 | S110 | A feed enters the decision state only with a NAMED CONSUMER (play, specialist directive, or another feed that reads it) or an explicit PARK note | DECIDED | SOP v1.2 (this session); enforcement mechanism = the consumer map sweep in the QC checklist |
| D13 | S110 (Greg) | Gas only — the platform scopes to NG/KXNATGASD/Henry Hub until further notice | DECIDED | doc-only (memo + this ledger) — acceptable: it is a scope statement, checked by the QC sweep against new non-gas builds |
| D14 | S110 (memo, Greg go) | Pyth collectors (WTI/XAU/XAG) RETIRED — free era ended 2026-07-31, not gas | DECIDED | pending: workflow retirement on the trunk branch (needs a trunk touch; queued) |
| D15 | S110 (memo, Greg go) | The live-orchestrator open item is CLOSED — the sequenced spawn has run five groups without an ordering failure; the S105 escalation clause self-reactivates if waves misbehave | RETIRED | this ledger line supersedes the S105/S108 open-list entries |
| D16 | S110 (memo, Greg go) | G21 round 2: CLOSED as not-run; the r1 result stands on its own record | RETIRED | this ledger line supersedes the S109 open-list entry |
| D17 | S109 (Greg) | Audit and forecast are SEPARATE roles; the auditor reads the whole block, emits no numbers, and runs BEFORE every blind | WIRED | agents/state_auditor.md + SOP STEP 1 |
| D18 | S110 (Greg) | Paper trading go-plan approved; Greg provisions the Kalshi demo account/keys (G0); dock builds run in parallel while the walk finishes G22/G23 | DECIDED | memo Part 3 + task list — G0 in flight with Greg |
| D19 | S106/S103 (Greg) | Scoreboard = forward-curve error per day, never daily hit-rate alone; P&L framing per-event only | WIRED | blind_score_nonpooled + render rules |
| D20 | S98 (Greg) | The futures->Kalshi LAG is ESTABLISHED (S80/S81/S91); never retest it — live telemetry only | VERIFIED | gate doc section 0c + kalshi_fill_model/lag_execution_map headers refuse relitigation |
