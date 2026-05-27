# Handoff for next chat — REAL DATA ONLY, original data group only

## CRITICAL — read this first

**The other chat handles `markets_btc_bybit_*` (BTC on Bybit, both sides).
DO NOT TOUCH THOSE BUCKETS.** Greg is splitting work across two parallel
chat sessions; running the same scope here would collide on shared on-disk
state (evidence graph load-merge-save, lineage history append, policy
history append, control plane state files).

**Your scope = MY ORIGINAL DATA GROUP** (everything EXCEPT BTC Bybit):

| Bucket | Files in legacy (real-data, migrated) |
|---|---|
| `markets_btc_coinbase_buy` | 181 |
| `markets_btc_coinbase_sell` | 53 |
| `markets_btc_kraken_buy` | 205 |
| `markets_btc_kraken_sell` | 86 |
| `markets_eth_bybit_buy` | 120 |
| `markets_eth_bybit_sell` | 102 |
| `markets_eth_coinbase_buy` | 285 |
| `markets_eth_coinbase_sell` | 2 |
| `markets_eth_kraken_buy` | 294 |
| `markets_eth_kraken_sell` | 13 |
| `quantum_two_bath_exc_dT0` | 100 |
| `quantum_two_bath_exc_dTon` | 717 |
| `quantum_two_bath_sup_dT0` | 100 |
| `quantum_two_bath_sup_dTon` | 717 |
| `fixture` | 83 |

**OFF LIMITS (other chat):** `markets_btc_bybit_buy`, `markets_btc_bybit_sell`.

## Rule: REAL DATA ONLY

Greg has been clear and repeatedly: no synthetic data, no synthetic verifiers,
no "wiring tests." Every pipeline run must consume real input from:

- **Crypto markets:** winners listed in
  `E:\Markets\research\strategy_evolution\oracle_winner_trade_list.json`
  (3553 entries), with raw bars from
  `E:\Markets\live_data_history\<YYYY-MM-DD>\<asset>_<venue>_bins.jsonl`.
  The markets adapter at `E:\refrag\adapters\markets_refrag_adapter.py`
  already does this end-to-end and derives the granular domain via
  `winner_domain(asset, venue, side)` →
  `markets_<asset>_<venue>_<side>`. **Do not modify it.**
- **Quantum:** the source_id format
  `sb_twobath_Tavg-<T>_DeltaT-<dT>_lambda-<λ>_gamma-<γ>_init-<state>`
  is used by `quantum_refrag_adapter.py`. Verify the adapter derives
  granular `quantum_<sub_family>_<init>_<dT_regime>` per call. If not, fix
  it before running.

**If you write a "verifier" or "smoke test" that fabricates input series
(linear ramps, sinusoids, anything not from disk), STOP. That's the
mistake the prior chat made; Greg had me scrub everything. Use the adapters.**

## How to run YOUR scope without colliding with the other chat

The markets adapter currently iterates over all `(asset, venue)` pairs in
`BIN_AV` (BTC and ETH × kraken/coinbase/bybit). To avoid touching the
other chat's BTC Bybit buckets, you have two options:

**Option A — filter winners pre-flight (preferred, no code change to
adapter):** wrap the adapter call to skip any winner whose
`(asset, venue) == ("BTC", "Bybit")`. Run only on the other 5 venue/asset
combos for markets, plus quantum/fixture.

**Option B — temporarily edit `BIN_AV` in `markets_refrag_adapter.py`** to
omit `("BTC", "Bybit")` for the duration of your run, then revert.

Either way, use `--resume` so already-migrated discoveries are skipped:

```
python E:\refrag\adapters\markets_refrag_adapter.py --resume
```

For quantum, locate the spin-boson sim outputs (likely under
`E:\refrag\_full_pipeline_quantum\` or similar — survey before running)
and feed via `quantum_refrag_adapter.py`. Same rule: real data only.

## Current on-disk state (post-scrub, 2026-05-25)

- `discoveries/operator_discoveries/` — 3502 files across 16 buckets.
  3477 are real-data legacy (migrated from
  `artifacts/discoveries.legacy_20260525T020813Z/`). The extra 25 are
  the other chat's real-data outputs in BTC Bybit (preserve, do not
  touch).
- `discoveries/evidence_graphs/` — 2 files
  (`markets_btc_bybit_buy_evidence.json`,
  `markets_btc_bybit_sell_evidence.json`) — both from the other chat,
  do not touch. All other buckets have empty accumulators; your runs
  will create them as `<your_domain>_evidence.json`.
- `discoveries/index.json` — 3502 entries, current as of 2026-05-25T03:18.
- `discoveries/cross_domain_transfers/` — empty (Phase 4 populates).
- `discoveries/pipeline_discoveries/` — empty (Phase 2+ populates).
- `registry/lineage/od_spectral_retrieval_pipeline.json` — 1303 history
  entries (912 pre-session + 391 from other chat). My session entries
  were trimmed during the scrub.
- `artifacts/` — `policy_history.jsonl`, `execution_traces.jsonl`,
  benchmark + control_loop, plus the 6 CP state files — all from the
  other chat post-scrub. Don't delete; they're real-data accumulations.
- `artifacts/discoveries.legacy_20260525T020813Z/` — 3477 real-data
  legacy originals, preserved for reversibility. Don't delete.

## Source-code state — what landed in MY work (real, keep)

These are pure infrastructure, no synthetic-data assumptions baked in:

- `refrag_discovery/runtime/operator_orchestrator.py` — `domain=` kwarg
  threaded through; production writes route to
  `discoveries/operator_discoveries/<domain>/<run_id>.json`;
  per-domain evidence graphs at
  `discoveries/evidence_graphs/<domain>_evidence.json`; lineage routing
  fix (registry/lineage/ in production, sandboxed in artifacts_dir mode).
- `refrag_discovery/runtime/od_spectral_retrieval_pipeline.py` — forwards
  `domain=`.
- `refrag_discovery/paths.py` — `REGISTRY_DIR`, `DISCOVERIES_DIR` etc.
  per arch §3.1 / §4.
- `refrag_discovery/control_plane/storage.py` — `operator_state_path`
  routes lineage to `registry/lineage/` when `artifacts_dir is None`.
- `refrag_discovery/registry/manifest_validator.py` — type reference
  resolution for `array<...>`, `map<...>`, `enum(...)`.
- `schema/spectral_chunk.schema.json`, `schema/operator_candidate.schema.json`.
- `scripts/build_registry_indexes.py`, `scripts/build_registry_embeddings.py`,
  `scripts/migrate_legacy_discoveries.py`, `scripts/build_discoveries_index.py`.
- `tests/test_registry_build.py`, `tests/test_discoveries_layout.py`.
- `tests/test_refrag_mcp_server.py` — autouse `_sandbox_discoveries`
  fixture so MCP tests don't leak production discoveries.
- `adapters/markets_refrag_adapter.py` — granular `winner_domain` helper
  (other chat added this; **do not modify**).

## Things that were DELETED in the scrub (don't recreate)

- `scripts/verify_phase1_roundtrip.py` — was synthetic-data wiring check.
  If you need a verification harness, build it to drive the **real
  adapters** end-to-end on **real winners**, not synthetic seeds.
- All session-generated handoff docs (PART5, PART6, PART7).
- All synthetic verifier discovery files + evidence graphs.

## Open questions / known issues

1. **Sparse buckets** — `markets_eth_coinbase_sell` has 2 legacy files,
   `markets_eth_kraken_sell` has 13. May need more sell-side ETH
   captures from the live data archive. Run the adapter with `--resume`
   so any new winners that have landed since the original capture get
   processed.
2. **Closed-loop iteration** — orchestrator currently writes
   `"termination_condition": "single_pass_bootstrap"` with one iteration.
   Arch §2 expects iteration until `posterior_width < threshold`. This
   is the main Phase 2 gap.
3. **Quantum adapter granular domain** — verify
   `quantum_refrag_adapter.py` derives
   `quantum_<sub_family>_<init>_<dT_regime>` correctly from its source_id
   format. Markets adapter is confirmed updated; quantum adapter needs
   a quick check.
4. **MCP test sandbox** — was added late in the session via autouse
   fixture. Confirm by running `pytest tests/test_refrag_mcp_server.py`
   and checking no new files land in `discoveries/operator_discoveries/`.

## Coordination protocol with the other chat

- Greg is the dispatcher. Don't probe the other chat directly.
- If you finish your scope and want to extend into BTC Bybit, ASK GREG
  first — the other chat may still be working that scope.
- If state looks unfamiliar mid-run (e.g., new evidence graph files
  appearing under buckets you didn't run), STOP and ask Greg. The other
  chat may have started something.

## End of handoff
