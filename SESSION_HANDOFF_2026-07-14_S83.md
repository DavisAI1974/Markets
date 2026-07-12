# SESSION HANDOFF — S83 (2026-07-12) — META SESSION: CLAUDE.md audit/split + the three Kalshi ritual skills

Branch **`claude/kalshi-s79-kickoff-ij8t9o`** (= repo DEFAULT; push there). Harness again dropped the
session on a fresh branch at the stale **S70 tip `3c70ff5`** — diagnosed via `git ls-remote` (the local
`git branch -r` view was an incomplete fetch and MISLEADS; ls-remote is authoritative), switched to the
s79 tip `f77a65f`. Greg: everything pushes to s79 because the collector workflows live there; the stale
harness branch is left alone.

## What this session was

Greg brought two community prompts ("audit your CLAUDE.md" / "audit and rebuild your skills") and asked
to apply them to the Kalshi program. This was deliberately a META session — none of the S83 kickoff
research priorities were touched; they roll intact to S84.

## 1. CLAUDE.md audit + split (commit `0b599f6`)

The master CLAUDE.md had grown to **2,911 lines / ~254 KB**, ~95% of it the OD/crypto/physics
session-by-session record — the exact "bloated master a cheaper model silently half-ignores" failure
mode the prompt targets (its own header said "READ the handoff, not this whole file").

- **`CLAUDE_ARCHIVE_OD.md`** (NEW) = the entire pre-split master, VERBATIM, with an archive banner.
  Nothing deleted; the OD/crypto (S20–S37) + physics (S3–S25, INFO-0xx ledger) record lives there.
- **`CLAUDE.md`** rewritten lean (215 lines): read-order (latest handoff → kickoff →
  `KALSHI_TRADING.md` → `git log -1`), the load-bearing trading rules, operating discipline, the
  branch/data discipline (stale-tip trap, canonical trunk, data branches), the repo map, a compressed
  S78+ arc, and a keep-lean session-note workflow so it cannot re-bloat.
- **OD toolkit stays LIVE in CLAUDE.md** (Greg: "we have looked back a few times for pieces") — every
  `odcore/` module one-lined with its warnings (`DEPLOY_VALIDATED=False` etc.) + the crypto data
  branches for reach-backs.
- **Dipole research stays LIVE in CLAUDE.md** (Greg, commit `731c413`) — a standing section carrying
  the S36/S36b/S37 findings themselves: the divergence+exhaustion 2-factor read (oppose+exhaust 64% →
  with-trend+strengthen 49%), the not-a-direction-predictor discipline, the per-cell net-of-cost
  verdict (size-vs-fee — the same finding Kalshi S81/S82 reproduced), the FILTER(dipole)/TIMING
  (1-sec price-reversal) split + fee floor (maker ~4bps / taker ~22bps), the S37 gated-swing stack
  (provisional, one window), the centroid-dipole lineage, and the stacking meta-rules.

## 2. The three Kalshi ritual skills (commit `b522a21`) — `.claude/skills/`, harness-confirmed loading

| skill | encodes |
|-------|---------|
| `kalshi-session-start` | Stale-tip branch check (ls-remote-aware) → read order → materialize `data/kalshi-bins` + `data/pyth-ticks` locally (the exact gunzip restore loops from the workflows) → verify accrual by NEWEST TIMESTAMP, not file existence. |
| `kalshi-backtest` | The mandatory evaluation discipline as executable gates: leakage gate first (with the harnesses to copy from), settle-window exclusion, per-cell never pooled, distributions/fingerprints never means, net-of-fee at maker AND taker, honest-negative write-ups. |
| `kalshi-roll` | Pyth front-month roll: month codes → confirm Kalshi's actual settle contract → Hermes feed-id lookup → edit `FEEDS` dict + docstring in `pyth_collector.py` → 30s sanity-stream → push to trunk; old-symbol history kept; roll boundary = separate cells, never splice. |

Indexed in `KALSHI_TRADING.md` (new Skills table + CLAUDE.md row) and in CLAUDE.md's repo map.

## Data state at session close (2026-07-12 ~13:00 UTC)

- **`data/pyth-ticks` DOES NOT EXIST yet** — zero ticks accrued. The run Greg manually dispatched
  end-S82 pushes only at the end of its ~5h50m cycle, so it may still be mid-flight — or stuck again.
  **S84 FIRST ACTION: check Actions for that run's state.** If it completed without creating the
  branch, or sits `queued`, it is account-level (billing/minutes/runner cap) — Greg's click territory.
  Priority-1 (sub-second lag) and the futures-move join stay BLOCKED until ticks exist.
- **`data/kalshi-bins` healthy** — last push 2026-07-12 07:30 UTC, within the 6h cadence.

## Files this session

New: `CLAUDE_ARCHIVE_OD.md`, `.claude/skills/{kalshi-session-start,kalshi-backtest,kalshi-roll}/SKILL.md`,
this handoff, `KICKOFF_2026-07-15_S84.md`. Rewritten: `CLAUDE.md`. Updated: `KALSHI_TRADING.md`.
Commits: `0b599f6` (split) → `b522a21` (skills) → `731c413` (dipole live) → this wrap.

## NEXT (S84) — the untouched S83 priorities roll forward

1. **Verify Pyth feed** (Actions run state; does `data/pyth-ticks` exist?) → then **sub-second lag**
   on accrued ticks, per contract never pooled (the decisive test).
2. **Join the Pyth futures move onto the level-hit dataset** (`futures_move_bps`/`lag_seconds` context
   columns) — do big-run continuations concentrate on level-hits trailing a fresh futures move?
3. **Thu 7/16 EIA natgas (14:30 UTC) LIVE** — `release_book_signal.py --test --series KXNATGASD` on
   release-spanning bins; busy-day natgas lag on live NGDQ6 ticks; `consensus_poll.py` before + after.
4. **Weather scoring per regime** when the OD operator emits `(value,sigma)` — through
   `kalshi_score.py`, Denver/NY/Chicago transition cell first, vs `WEATHER_BASELINE_S82.md` baselines.
   Forecaster is Greg's spec, HANDS OFF.
5. Standing: roll re-point (WTIQ6 7/21, NGDQ6 7/29, BRENTU6 7/31 — use the `kalshi-roll` skill);
   paper-loop RSA creds.

## RULES (unchanged, load-bearing — now also encoded in the skills)

EACH TRADE INDIVIDUALLY, never average; distributions + per-trade fingerprints not means; per-cell
always; exclude the settle window; catalyst = trigger + coarse size / book+flow imbalance + exhaustion
= direction + magnitude / herd breadth = continuation, whale = scalp-only; leakage gate before any
backtest; zero synthetic; provisional-until-live; weather = Greg's spec, HANDS OFF; `--events` on
news_coupling_research = BASENAME; keep `KALSHI_TRADING.md` current; keep `CLAUDE.md` LEAN (session
detail goes in handoffs, only the headline folds into the arc).
