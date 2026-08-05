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

## KEY INVENTORY -> see KEYS.md (names and holders only, never values)
