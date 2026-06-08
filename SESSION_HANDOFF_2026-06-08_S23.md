# SESSION HANDOFF — 2026-06-08 — Session 23 (Markets: dipole runner built; data scaled + git unstuck)

WORKING BRANCH: `claude/crypto-trading-platform-plan-MpqwG` (DavisAI1974/Markets). No PR.
Commits this session: `26be859`, `b97d377`, `7ef836c` (code branch) + `aa4736d` (data/btc-bins)
+ `977f979` (data/eth-bins). Master context: `CLAUDE (5).md` (now canonical through S23).
All Operating Rules + Result Discipline in force. Zero synthetic data.

## START-OF-SESSION HYGIENE (so S24 does NOT repeat S23's slow start)
The first ~30 min of S23 were lost to git friction + file-upload churn. These are now FIXED —
do not refight them:
- **`git config --global --add safe.directory '*'` is set.** No more "dubious ownership"; do
  NOT add per-path safe.directory or prefix `-c safe.directory`.
- **Work from the worktree + git refs.** This session's worktree under
  `E:\Markets\.claude\worktrees\...` reads/writes/commits normally. For the main checkout, read
  tracked files via `git show <ref>:<path>` and commit via plumbing (temp `GIT_INDEX_FILE`).
  Do NOT fight the exFAT lock on `E:\Markets\.claude`; do NOT `Remove-Item` under `E:\Markets`.
- **These onboarding docs are IN GIT — never re-upload/paste them.** S24 just reads
  `KICKOFF_2026-06-08_S24.md` etc. from the repo. Don't over-read large files; grep to the spot.
- **Data is current in git now** (see below), so SessionStart materializes real data without
  the local drive.

## Headline
S23 priority #1 (the runner that earns the dipole validation) is BUILT and the data it runs on
went from a stale 10-day git snapshot to a current ~30-day, 15-source set. The first real
validation NUMBERS are still pending (the full run is long; it is now resumable and was
relaunched at session end).

## What was built + pushed
- **`scripts/od_trade_dipole_run.py`** (resumable runner, `26be859`/`b97d377`). Replays the
  adaptive_backtester generators (ALL gens incl. dipole — Greg's Option-2 call) on minute bars
  to get labeled trades; slices each trade's pre-entry orderflow window from the 1s BinSeries;
  builds the 15-dim c_i (`dipole_trade.trade_coupling_vector`); runs the in-sample positive
  control + embargoed walk-forward gate (`odcore/validation.py`), printing 3 standardization
  modes. **Resumable:** each source checkpoints C/labels/gross/ts to `realbins/_dipole_cache/`;
  a killed run resumes. `--eval-only` for an instant readout once cached.
- **`scripts/build_realbins.py`** (`26be859`). Merges daily collector JSONL into the merged
  `realbins/<src>_bins.json` that `load_bins` + `load_minute_bars` consume UNCHANGED.
- **`session_start.sh`** now materializes gzipped `.json.gz` (gunzip; raw fallback).

## Data architecture resolved (the big unblock)
The git `data/btc-bins`/`data/eth-bins` branches had STALLED at **2026-05-17** (~10 days), which
is why everything ran on partial data. The collectors kept writing locally to
`E:\Markets\live_data_history\<YYYY-MM-DD>\<source>_bins.jsonl` — **~2026-02-23 -> today**, **5
assets** (btc, eth, doge, link, xrp) x venues (coinbase, kraken, bybit_perp). Rebuilt **30 days
x 15 sources** locally, and pushed **gzipped** 30-day bins back to git (`aa4736d`/`977f979`;
114 MiB -> 18 M etc., under GitHub's 100-MiB/file cap). Future hooks now get current data.
Memory: see `markets-data-lives-local-not-git`.

## KEY FINDING (unresolved — for S24 to confirm at scale)
On a small/imbalanced smoke sample the in-sample control did NOT reproduce the reference convex
`c=1.309, R^2=0.943`. The quadratic term collapses to `c~=0, r2~=1` in all three modes:
- `pool` (the S22 Standardizer): full-pool mean-centering forces win/lose centroids EXACTLY
  antiparallel -> `H_a == -H_b` -> tautological r2=1. **Latent issue in the ported core**
  (`dipole_trade.fit_trade_dipole`).
- `none` (raw): a large-scale feature dominates -> `H_a ~= +H_b`.
- `scale` (÷std, no centering — the principled fix): still linear, `c~=0`.
Likely cause if it persists at full scale: the **15-dim c_i is too thin / collinear** (open
question #1 — enrich the operator basis). STRONG LEAD: `E:\Markets\_full_pipeline_winners_preentry_cs100_v2`
(2026-05-28) may already hold a richer ~100-dim labeled trade set — attach + inspect first.

## HONEST STATUS (Result Discipline) — edge still unproven
No net-of-cost edge has been demonstrated. Reproducing the algebraic R^2 is structural, not an
edge, and at smoke scale it did not even reproduce. The runner must clear `odcore/validation.py`
(net>0 after fees+slip, beat baseline + buy-hold under embargoed walk-forward, tautology z>>2-3,
small random-vs-WF gap) before any WIRE step. Healthy S23 trade counts (btc_coinbase 1311 / 9.7%
win, eth_coinbase 1502 / 10.9%, etc.) confirm the pipeline scales — but counts are not an edge.

## What is NOT done (-> S24 priority 1)
- Run the full 15-source dipole validation to completion and READ the control + gate numbers
  (resume via the cache; `--eval-only` if all cached).
- Decide on the standardization-collapse finding (confirm at scale; enrich c_i / use cs100 set).
- WIRE step remains deferred until the gate passes.

## Pointers
- Next kickoff: `KICKOFF_2026-06-08_S24.md`
- This session's CLAUDE note: `CLAUDE_session_note_2026-06-08_S23.md` (folded into `CLAUDE (5).md`)
- Prior: `SESSION_HANDOFF_2026-06-07_S22.md`, `KICKOFF_2026-06-07_S23.md`
- New tooling: `scripts/build_realbins.py`, `scripts/od_trade_dipole_run.py`

## Branch
WORKING BRANCH: `claude/crypto-trading-platform-plan-MpqwG` (DavisAI1974/Markets)
