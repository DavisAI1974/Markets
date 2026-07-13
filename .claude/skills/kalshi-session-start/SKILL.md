---
name: kalshi-session-start
description: Kalshi session-start ritual — verify you are on the real branch (not the stale S70 tip), read the current state docs in order, and materialize the accrued data branches (kalshi-bins, pyth-ticks) locally with an accrual check. Run at the start of every Kalshi work session before touching any code or data.
---

# Kalshi session start

Run these steps IN ORDER. Do not skip the branch check — the harness recurringly cuts fresh
session branches from a stale tip and work done there is stranded.

## 1. Branch check (the stale-tip trap)

```bash
git log --oneline -1
```

- If the tip is `3c70ff5` (S70) or anything dated before the latest `SESSION_HANDOFF_*.md`,
  you are on a stale branch. Get onto the canonical trunk:

```bash
git fetch origin claude/kalshi-s79-kickoff-ij8t9o
git checkout -B claude/kalshi-s79-kickoff-ij8t9o origin/claude/kalshi-s79-kickoff-ij8t9o
```

- The trunk is also where the GitHub Actions collectors auto-push, so ALWAYS
  `git pull origin claude/kalshi-s79-kickoff-ij8t9o` before pushing your own commits.

## 2. Read the state (in this order, nothing else first)

1. Latest `SESSION_HANDOFF_*.md` (highest S-number) — actual current state.
2. Latest `KICKOFF_*.md` — this session's priorities.
3. `KALSHI_TRADING.md` — the file index (current vs old pieces).

## 3. Materialize accrued data branches

Bins and ticks accrue GZIPPED on data branches; local files are raw JSONL (gitignored).

```bash
# Kalshi bins + consensus  ->  data/kalshi/
mkdir -p data/kalshi
git fetch origin data/kalshi-bins
for gz in $(git ls-tree -r --name-only origin/data/kalshi-bins | grep '\.jsonl\.gz$'); do
  base=$(basename "$gz" .gz)
  git show "origin/data/kalshi-bins:$gz" | gunzip > "data/kalshi/$base"
  echo "[restore] $base ($(wc -l < data/kalshi/$base) lines)"
done

# Pyth futures ticks  ->  data/pyth_ticks/
mkdir -p data/pyth_ticks
git fetch origin data/pyth-ticks
for gz in $(git ls-tree -r --name-only origin/data/pyth-ticks | grep '\.jsonl\.gz$'); do
  base=$(basename "$gz" .gz)
  git show "origin/data/pyth-ticks:$gz" | gunzip > "data/pyth_ticks/$base"
  echo "[restore] $base ($(wc -l < data/pyth_ticks/$base) lines)"
done

# NYMEX Databento true-tick tape (S85: NG/CL release windows + definitions + baselines) -> data/pyth_ticks/
git fetch origin data/nymex-ticks
for gz in $(git ls-tree -r --name-only origin/data/nymex-ticks | grep '^nymex_tape/.*\.gz$'); do
  base=$(basename "$gz" .gz)
  dest="data/pyth_ticks/$base"; [[ "$base" == *.json ]] && dest="data/$base"   # baselines live in data/
  git show "origin/data/nymex-ticks:$gz" | gunzip > "$dest"
  echo "[restore] $base"
done

# NYMEX MBP-10 depth tape (S86: trade+book rows) -> data/nymex_mbp10/ ; depth baselines -> data/
mkdir -p data/nymex_mbp10
for gz in $(git ls-tree -r --name-only origin/data/nymex-ticks | grep '^nymex_mbp10/.*\.gz$'); do
  base=$(basename "$gz" .gz)
  dest="data/nymex_mbp10/$base"; [[ "$base" == *.json ]] && dest="data/$base"   # depth baselines live in data/
  git show "origin/data/nymex-ticks:$gz" | gunzip > "$dest"
  echo "[restore] $base"
done
```

The **continuous MBP-10 YEAR tape** (S87, the forecaster's analog library) accrues gzipped under
`nymex_cont/` on the same `data/nymex-ticks` branch (~13x compression, ~400MB gz / ~5GB raw for a year).
It is LARGE — do NOT blanket-restore it at session start. Restore the days you need on demand:
`git show origin/data/nymex-ticks:nymex_cont/CL_20260617.jsonl.gz | gunzip > data/nymex_cont/CL_20260617.jsonl`
(`git ls-tree -r --name-only origin/data/nymex-ticks | grep '^nymex_cont/'` to see what accrued).

## 4. VERIFY accrual before trusting the data

- Check the newest timestamp inside each restored file, not just its existence — a feed can be
  stuck while old data sits there looking healthy. If the latest bin/tick is older than the last
  6h collector cycle (both workflows run every 6h), the feed is stalled.
- If a workflow run sits `queued` and never executes: it is an ACCOUNT-level Actions problem
  (billing / minutes / runner cap), not the workflow file. Claude's token cannot dispatch runs —
  Greg clicks "Run workflow".
- Pyth note: energy futures trade ~Sun 18:00 ET through Fri; a weekend gap with only deduped
  frozen prices is normal, a weekday gap is not.

## 5. Only then start the session's work

Priorities come from the kickoff, not from this skill.
