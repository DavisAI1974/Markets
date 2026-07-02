# SESSION HANDOFF — S52 (2026-07-02) — JOB 1 (sizing-on-winners accounting) DONE + AIRTIGHT; canonical $/hr-with-sizing matrix delivered; winner-side extensions falsified; Job 2 (Bybit) data-gated

Branch: designated `claude/crypto-liquidity-signals-s52-twxv4t`, reset to canonical `5c5vg9` at session start
(harness cut it stale from the default branch — nothing unique lost; the 2 divergent commits were the
Bybit-book + paper cron ymls that already live on the DEFAULT branch where crons fire from).
Read `S52_SIZING_MATRIX.md` (the deliverable) + the S52 delta atop `CLAUDE.md`. Coinbase books re-materialized
to `/tmp/<coin>_coinbase_book.jsonl.gz` from `data/<coin>-book`.

## Job 0 — paper run + ledger
`python scripts/paper_trade.py` → +0 new trades (no new Coinbase book window since the ledger). Ledger =
**25,845 trades** across all runs; sized_net > flat_net on ALL 5 cells forward (sol +9,225→+10,705 = +16%,
doge +47%, xrp +15%, eth +27%, btc +34%) — the OOS fact the sizing earns its keep on.

## Job 1 (Greg, the primary job) — the SIZING-ON-WINNERS accounting, made airtight (falsification-first)
Greg's S51 concern: the $/hr projections under-credit the size-up on winners. Resolved in three parts.

### 1a — is `_capacity_model._dollars()`'s `min(size×S, flow)` under-crediting sizing? **NO.**
`scripts/_s52_sizing_audit.py` (→ `_s52_sizing_audit_results.json`). Per cell (mk0, $1k/leg):

| cell | mean_size | corr(size,net) | corr(size,cap) | corr(cap,net) | cap-binds @$1k | raw lift | $/hr lift @$1k | cap-matched |
|------|-----------|----------------|----------------|---------------|----------------|----------|----------------|-------------|
| sol  | 1.071 | +0.022 | +0.075 | −0.025 | 73% | +16% | +21% | +17% |
| doge | 1.111 | +0.057 | +0.054 | +0.015 | 87% | +47% | +1%  | −3%  |
| xrp  | 1.089 | +0.015 | +0.075 | −0.023 | 76% | +15% | +7%  | +2%  |
| eth  | 1.073 | +0.023 | +0.097 | −0.031 | 54% | +27% | +51% | +44% |
| btc  | 1.068 | +0.052 | +0.083 | −0.059 | 69% | +34% | +75% | +67% |

- **corr(size,cap) > 0 on all 5** → high-conviction legs sit on slightly fatter-flow turns, so the `min()`
  model DOES credit the fat-leg concentration (it is NOT discarded). No systematic under-credit.
- Sizing lift **→0 at the flow-capped ceiling is the PHYSICAL flow wall** (can't fill more than the real
  opposing $), not a modeling artifact. At $1k/leg the cap already binds 54–87% of legs → sizing operates on
  the fat-flow minority, exactly where the conviction points.
- `corr(size,net)≈+0.03` → entry conviction loads |move|, not wins (S47 re-confirmed). That is WHY the
  absolute deploy-$/hr lift is small, not an accounting flaw.
- **Capital-matched lift** (rescale sized to flat's total notional = pure allocation skill): SOL +21%→+17%;
  the ~4pp gap is the small mean_size≈1.07 deploy-more effect. ETH/BTC % are on near-zero baselines (±$1–3/hr
  absolute) — noise, not signal. The **raw** (uncapped ledger) lift +16..+47% is the UPPER bound if flow were
  unlimited; the flow cap legitimately eats it down to the deploy-$/hr numbers.

### 1b — winner-side sizing BEYOND entry conviction: both mechanisms **FALSIFIED**
- **(i) Sequence anti-martingale** ("size up after recent winners") needs leg outcomes to PERSIST.
  `scripts/_s52_winner_persistence.py` (→ `_s52_winner_persistence_results.json`): lag-1 net autocorr ~0 on
  every cell, never significantly positive (ETH mildly ANTI-persistent, shuffle z=−3.2); prior-k mean predicts
  next-leg net at corr ≤ |0.035|, E[next|winning]−E[next|losing] ≈ 0 bps. Leg outcomes are ~independent (the
  swing regime resets each turn). **Dead.**
- **(ii) Within-leg green-adds** ("only add when the leg is green") needs green legs to offer opposing maker
  flow. `scripts/_s52_winner_fillability.py` (→ `_s52_winner_fillability_results.json`): winners' fillable $ =
  **0.32–0.65× losers'** on 4/5 cells (SOL 0.65, XRP 0.52, ETH 0.32, BTC 0.33; only thin/noisy DOGE inverts,
  1.78). The market force-feeds fill to LOSERS (S45/S51 adverse selection, re-confirmed on the cap model) → a
  green-only add STRUCTURALLY cannot load winners harder than losers. **Dead on the microstructure**, not just
  this window. Re-testable only on the Bybit venue book + queue model (Job 2), where fill-share and the
  reversed-side control can be re-run.

**Verdict:** the "size on winners" that survives falsification = **entry-conviction sizing** (already deployed,
`odcore.swing_maker.size_legs`, hi_clip=4.0), which 1a shows is correctly credited. Nothing new was wired (no
leakage gate needed — the three probes are diagnostics, not deployed signals).

### Deliverable — `S52_SIZING_MATRIX.md` (canonical, built by `scripts/_s52_build_matrix.py` from the JSONs)
Per cell × fee scenario (mk0/−1/−2, ±1.5× spread) × fill model (v1 front-of-queue, v2 queue-honest):
flat $/hr, entry-sized $/hr, sizing lift %, v2 flat/sized, ceiling. `winner-sided` column = **n/a (falsified)**
⇒ equals entry-sized. Headline SOL cells (Coinbase, $1k/leg): mk0 flat +$7 / sized +$9 (ceiling +$18);
−1bp sized +$21 (ceiling +$71); −2bp+1.5× ceiling +$142. **Cite the cell, never a single number.**

**How sizing enters the citation:** +8–21% as-deployed at $1k (mostly SOL/ETH), SHRINKING with the rebate
(uniform per-leg add lifts the flat baseline faster), →0 at the flow ceiling — a capital-constrained-regime
lever, real and kept, NOT an OOM multiplier. The OOM levers stay the REBATE (mk0→−1bp ≈3.9× SOL, super-linear)
+ venue FLOW (Bybit ~10× Coinbase tape).

## Job 2 — Bybit venue-cell measurement: **DATA-GATED, deferred**
`data/{sol,eth}-bybit-book` are NOT yet on origin (`git ls-remote` confirms no bybit refs). The cron `0 */6`
started 07-02; each run is 5h50m and pushes only at the end, and the session token can't GHA-dispatch — so
Greg may need to trigger the first `bybit_book_collectors_durable` run. Once ≥1 window lands: materialize via
`git show origin/data/<coin>-bybit-book:<coin>_bybit_book.jsonl.gz > /tmp/…` and run the full stack per
venue-cell (spread, turn structure, v1/v2 capacity at Bybit MM tiers −0.1…−1.25 bps, netting sim with
queue-honest fill) + re-test the winner-side add under the queue model. The pipeline reads venue books
unchanged (same row schema).

## Git / state
Coinbase books (all 5) re-materialized to `/tmp`. New files this session (all pushed to the designated branch):
`scripts/_s52_sizing_audit.py`, `scripts/_s52_winner_persistence.py`, `scripts/_s52_winner_fillability.py`,
`scripts/_s52_build_matrix.py`, `S52_SIZING_MATRIX.md`, result JSONs
(`_s52_sizing_audit_results.json`, `_s52_winner_persistence_results.json`, `_s52_winner_fillability_results.json`),
refreshed `_capacity_model_results.json`, this handoff + the CLAUDE.md S52 delta. **Keep canonical `5c5vg9`
synced** (the paper cron moves it) — per the hard branch rule this session pushed only to the designated
`s52-twxv4t`; sync `5c5vg9` to this tip when permitted.

## NEXT (S53)
1. **Bybit venue-cell measurement** once `data/{sol,eth}-bybit-book` lands (Job 2 — the decisive test).
2. Greg action: Bybit MM application (institutional_services@bybit.com; maker-share bar 0.03%, 1-mo trial) +
   Backpack VIP (vip@backpack.exchange).
3. DEAD, do not re-chase (S52 additions): sequence anti-martingale sizing (no persistence); within-leg
   green-adds on Coinbase (winners get 1/3–2/3 the fill of losers). All S51 DEAD items stand.
