# Fingerprint reproduction-gap diagnosis — provenance findings (S35, 2026-06-21)

Settles kickoff step 0: is the canary's reproduction failure a benign window/bar-source
mismatch, or look-ahead in the stored bucket values? And: does fixing it force a coeff re-run?

## TL;DR
- **The 6 cheap micros are look-ahead-contaminated** (mid-trade snapshots). **The 128-dim OD
  coeffs are NOT** — the deployable lineage (`_preentry` / `cs2000_clean` / `cand_sp`) is computed
  over a **strictly pre-entry 30-min window**. So the micro fix does **not** force a coeff re-run.
- The two tiers were computed by **different code paths** with **different windows**, but share one
  **fuzzy entry anchor** (`entry_ts = min(ts_utc per asset|venue|chunk_id|side)`; `chunk_id` recurs
  across episodes → ~40% of winner keys are multi-episode). That anchor weakness — not look-ahead —
  is the only thing that could justify re-running coeffs.

## Evidence

### 1. The micros are mid-trade snapshots (look-ahead) — `_diag_lookahead.py`
48/48 sampled clean-bucket WIN entries matched **exactly** to their provenance row in
`research/strategy_evolution/_live_mock_opportunities.jsonl` (source `live_mock_trade_replay`):
- **37/48** were captured at `trade_age_chunks > 0` / stage `late`/`mature` (median age 2, max 14).
- Exemplar `BTC|kraken|542895950c288339|sell`: stored `trade_current_chunk_bps = 98.4` came from
  the **age-11** snapshot at `ts_utc=1779569371`, ~10.2 h after the recorded `entry_ts_utc`. The
  micros describe a trade **already +98 bps in profit** — not a pre-entry state.

Mechanism (git `c486d3b`, `mock_trade_replay.py`):
- `apply_trade_context` (L877-888): `onset_price` is frozen when the side first appears (age 0);
  `trade_from_onset_bps`/`trade_current_chunk_bps`/`trade_recent_2chunk_bps` then **accumulate the
  post-onset move** as `age_chunks` increments. The bucket builder selected the best-looking
  (mid-trade) snapshot → look-ahead.
- The audit `build_live_hindsight_missed_winner_audit.py` (git `75a4268`, L667-670) **passes the
  micros through verbatim** from the opportunity row; it only computes the oracle label
  (`_future_outcome`, which legitimately looks ahead). So the micros' provenance is the runtime
  opportunity log, snapshotted mid-trade.

### 2. The `entry_ts` anchor is mis-patched and chunk_id-ambiguous
- `_patch_win_buckets_entry_ts.py`: `entry_ts_utc = min(ts_utc per unique_key)`,
  `unique_key = asset|venue|chunk_id|side`.
- `chunk_id` is a content/position hash that **recurs across episodes** (the exemplar chunk_id
  appears at timestamps spanning ~32 h). So `min(ts_utc)` can point to an **earlier unrelated
  occurrence**, 10–33 h before the snapshot whose micros were stored.
- Quantified over the audit CSV (4,422 winner keys): **52.5%** are a single tight occurrence
  (span ≤ 5 min, anchor ≈ true onset); **40.3%** span >1 episode (>20-min gap) → ambiguous anchor;
  36.6% span >60 min.

### 3. The coeffs are strictly PRE-ENTRY — `refrag/adapters/markets_refrag_adapter.py:553-558`
```python
if args.pre_entry_minutes > 0:        # _preentry / cand_sp / cs2000_clean used 30
    window_lo = entry_ts - 1800       # 30 min BEFORE entry
    window_hi = entry_ts              # ends AT entry — NO post-entry bars
else:                                 # ORIGINAL _win lineage used this:
    window_lo = entry_ts
    window_hi = exit_ts               # [entry, exit] = hold period = LOOK-AHEAD
```
- Coeffs are OD operator-coefficients of the **log-returns of the 30 min before `entry_ts`** — no
  favorable-move contamination.
- Two lineages exist: `markets_<cell>_win` (post-entry `[entry,exit]` → **look-ahead, do NOT
  deploy**) vs `markets_<cell>_win_preentry` / `cs2000_clean` / `cand_sp` (pre-entry → clean, the
  ~1,919-signature deliverable). Confirmed via `evidence_graph_metadata.supporting_documents`
  carrying the same `source_id` as the bucket entry.
- The live `_markets_gate_v2.py` `GateV2.recompute_coefs` also uses a pre-entry 30-min slice →
  train/serve **consistent** for the heavy tier.

## Verdict
- **Benign vs serious:** SERIOUS for the micros (look-ahead, by construction — not a window-recon
  error), CLEAN for the coeffs (pre-entry, verified).
- **Re-anchored canary** (`_canary_fingerprint_v2.py`): re-anchoring the encoder to each snapshot's
  own `chunk_end_ts_utc` (vs the mis-patched `entry_ts`) brought magnitudes into line and produced
  several **perfect 6/6 reproductions** → the encoder math/chunker/bar-source are fundamentally
  correct; v1's failure was dominated by the anchor + mid-trade selection.

## Does this force a coeff re-run?
- **For look-ahead: NO.** Coeffs are already pre-entry. The fix = recompute the **6 micros** at the
  coeffs' existing anchor (`entry_ts`/first-admission, age-0 snapshot) so the cheap tier matches the
  heavy tier. Today they describe different moments of the trade — that mismatch is the bug.
- **Only if we tighten the entry definition** (replace the chunk_id-ambiguous `min(ts_utc)` anchor
  with a true per-episode onset) would coeffs need re-running — and only for the ~40% multi-episode
  keys whose onset moves. That is an optional rigor upgrade, not required to remove look-ahead.

## Fix (matches Greg's "have them in there 2 times")
- **Entry fingerprint** (the predictor input): micros computed ONCE at `entry_ts`, pre-entry, on the
  same anchor as the coeffs — paired with the pre-entry 128-dim coeff. This is what trains/serves.
- **Live/current snapshot**: the existing mid-trade micros, kept for trade management/exit.
- Do NOT wire the encoder into a SignalGenerator until the entry-fingerprint canary passes.
