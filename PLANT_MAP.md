# PLANT_MAP.md — what runs where (the "two buildings" fix, S110)

One page. Every standing process, its host, its branch, its trigger, its heartbeat. If a process is
not on this map it is not a standing process. Update on any change (SOP change control applies).

## HOSTS

| host | what it is | reaches |
|---|---|---|
| THE SESSION (Claude container, or Greg's box working a clone) | the operating seat: walk runs, builds, audits, refine/blind spawns. **The seat is a CHECKOUT, never a location** (D34, S112): git = code and records, S3 = data, `data/` disposable — so no artifact may name a local path, and a session on any machine is equivalent to a session on any other | git, HTTPS APIs. CANNOT reach live market gateways (raw TCP blocked) — structural, measured S100 |
| EC2 `i-08cee7171c0a76a04` (t3.xlarge, us-east-2) | the data box: year pulls, redecodes, live-feed smoke (7.7 ms median to GLBX) | Databento live + historical, S3 |
| (planned) the LIVE BOX (us-east-2) | paper/live loop host: collector-as-a-service + the daily decision loop | Databento live, Kalshi API, S3 |
| GitHub Actions (account-level) | durable collectors (kalshi bins, consensus) — dispatch by Greg when queued-stuck | public APIs |

## BRANCHES (the two buildings)

| branch | role |
|---|---|
| `claude/kalshi-agents-coordinator-guard-1175nr` | THE WALK + the plant (SOP, states, forecasts, brain, memo, this map) — the working trunk since S104 |
| `claude/kalshi-s79-kickoff-ij8t9o` | the OLD trunk: GitHub-Actions collectors auto-push data commits here (kalshi-bins accrual); do not develop here |
| `data/*` branches | historical crypto-era data (dormant) |
| S3 `bento-568968024170-us-east-2-*` | ALL raw tape + stores (git holds NO bento data) |
| private repo `DavisAI1974/Agent-Davis` | gold-vault off-site copy #3 |

## STANDING PROCESSES

| process | host | trigger | heartbeat / check |
|---|---|---|---|
| kalshi collectors (durable) | GH Actions on the old trunk | 6h cron (Greg dispatches when queued-stuck) | branch accrual check (kalshi-session-start skill) |
| pyth collector | GH Actions on the old trunk | RETIRED (D14): free era ended 2026-07-31, not gas | verify workflow disabled when the trunk is next touched |
| ng_live_collector + watchdog | the live box (designed for systemd) | NOT YET A SERVICE (G3). Installer EXISTS (`deploy/aws/install-ng-live.sh`) — TRAP: it pins `CODE_BRANCH=chatgpt/rt-ng-mbp10-collector` (a third building, stale). Re-point to the working trunk before any deploy. | health.json (built, unwired) |
| the walk (blind/refine per group) | the session | per SOP RUN_SOP.md | batch record (to build) + task list |
| session bootstrap / substrate restore | the session | session start, keys pasted | session_bootstrap --verify-only |
| paper loop (G2) | the live box | NOT YET BUILT | plant_status.py line (to build) |

## THE CONTROL TOOLS (every `.py` the SOP names — gated, see below)

The SOP tells you WHAT runs at each station. This says WHERE it runs and WHEN. A tool the spec book
names but the plant map does not place is a step nobody knows the host for.

| tool | station / when | host |
|---|---|---|
| `session_bootstrap.py` | session start, one command from empty to ready | the session |
| `restore_substrate.py` | session start, rebuilds the whole `data/` plane (gitignored, does NOT survive) | the session (needs keys) |
| `verify_gold.py` | BEFORE any spawn — hard-fails a run on a tampered vault | the session |
| `group_config.py` | staging: the group's window, legs, roll map | the session |
| `flow_read.py` / `tape_reconcile.py` | staging: tape stats, and the reconciliation that catches an off-instrument leg | the session |
| `forecast_harness.py` | staging: builds the decision state the specialists read | the session |
| `build_causal_slices.py` | staging: makes the future ABSENT (hole #11) | the session |
| `archive_blind.py` | between rounds — archives by MOVE so a missing posterior hard-fails | the session |
| `group_coordinate_blind.py` / `group_coordinate_refine.py` | BLD/RFN stations: SELECT and ASSEMBLE only, guarded | the session |
| `merge_perday.py` | assembling the per-day posterior | the session |
| `due_gate.py` | serves the REGISTERED FORWARD TESTS into a run and refuses a silent pass — announce in the blind coordinator, HARD in the refine (S114; `merge_gate` claimed the coordinators did this and a grep of both returned zero) | the session |
| `brain_schema.py` | the brain's shape: `validate` runs the play checks AND the SECTION-INDEX GATE — every top-level section must be declared in `meta.sections` with `is`, `read_by` and `roles`, so a section cannot be added silently or serve to nobody. A section need not fit the play schema; declaration is the requirement | the session |
| `brain_view.py` | serves the brain SCOPED to a role and a phase, and declares what it withheld. One brain doc, many views (S114): `briefing` = the mission, rendered into the spawn prompt; `working` = what stays in view while the curve is drawn; `post_outcome` = the failure taxonomy, never during a forecast | the session |
| `blind_score_nonpooled.py` | scoring — all four numbers together, never a pooled mean | the session |
| `decision_trace.py` | binds reasoning to the decision; `verify` fails any unresolved id | the session |
| `brain_audit.py` | brain evidence audit + the D34 desktop-path guard (`fixpaths`) | the session |
| `plant_status.py` | THE ANDON BOARD — run at bring-up and before close-out | the session |

## THE STORE AND THE UNATTENDED PLANT (S112)

| tool | what it governs | gate |
|---|---|---|
| `store.py` | ONE STORE, GENERATED VIEWS (A-7). `DECISIONS.md`, the SOP appendix, `OPEN_ITEMS.md` and the file index are RENDERS; `docs` holds the DOCUMENT REGISTRY | `check` fails the line on render drift OR on a document content gate; `render_decisions` REFUSES a newline in a table cell (that defect landed twice) |
| `data_registry.py` | THE MASTER DATA-POINT LIST (A-22) - four tiers: SERVED, HELD-not-served, PLANNED (harvested from the registry), IDENTIFIED-not-committed. Every row labelled READ or NOT READ | `build` refuses to write an empty list; `unread` is the triage view. Named by SOP Station 0 |
| `chatgpt_handoff.py` | the external-research brief that ships with the drop-in (A-25), generated from the registry | a selftest fails the build if a DONE item appears, or if an item is re-asked without declaring its prior delegation |
| `spawn.py` | fills every SOP slot BY LOOKUP, templates loaded from the store — NC-1 is structurally unreachable | 17/17 selftest incl. the NC-1 regression |
| `merge_gate.py` | SOP gates 2 and 3: objective admissibility -> PROVISIONAL merge with a REGISTERED forward test -> settle, retirement scoped per D31 | a registered test cannot be forgotten |
| `plant_calendar.py` | the plant's clock from RULES, not a hardcoded table (`flow_calendar.CME_HOLIDAYS` ends 2027-02-15). 1031 sessions, cal+0..cal+3, wrapping to cal+0 day 1 | 8/8 selftest; reproduces 16/16 committed holidays |
| `coal_prices.py` | G-11 weekly accrual — the EIA window is a rolling FIVE WEEKS and the history is proprietary, so a week not captured is lost permanently | needs a weekly schedule; currently by hand |

## DOCUMENT DISCIPLINE (S112, Greg: "so one doesn't get forgotten about")

`research/kalshi/store/documents.json` is the registry: every working document, its CLASS
(LIVE / RENDER / VAULT / RECORD / ARCHIVE), what triggers an update, and whether a gate exists.
`python research/kalshi/store.py docs` prints it and runs the gates; `store.py check` fails on them,
so the andon stops the line.

**The gates are CONTENT gates, because mtime is not staleness.** Measured the day they were built:
55 of 151 tracked `research/kalshi/*.py` were absent from `KALSHI_TRADING.md` — the index whose
stated job is to name every one — and this file had been **edited that same session** while naming
none of the tools the SOP itself names. A document can be current by timestamp and silently missing
what it exists to list.

**The close-out trio** — `CLAUDE.md`, the session handoff, the drop-in — is written LAST and is
excluded from mid-session sweeps by design.

## KEY INVENTORY -> see KEYS.md (names and holders only, never values)
