# Handoff — Part 2: Quantum, Cross-Domain, Opsec, Hyperliquid (2026-05-24)

Continues from `HANDOFF_SESSION_20260524_FULL_PIPELINE_ADAPTER.md` (part 1).

## TL;DR

Markets full pipeline now covers 1690/1709 winners (was 505) via durable JSONL bin loader. Pipeline's 7 (nodes, edges) signatures = natural horizon-class taxonomy, NOT a bug. Fee-inclusive analysis shows long holds (11,53) dominate post-fee economics; short classes on Kraken/Coinbase mathematically lose. Quantum adapter built and 648 trajectories recovered after kill — needs `--resume` to finish remaining ~912. Cross-domain spectral_similarity mode shipped on the doc-sanctioned operator. Hyperliquid chosen as US-onshore execution venue with hard opsec rules around visibility.

## Recommended new-chat opener

> Continue Part 2 handoff. First action: resume the quantum run.
> `python E:\refrag\adapters\quantum_refrag_adapter.py --resume`
> Expected: ~912 remaining trajectories, ~15-30 min if policy_history wiped first (see "Performance optimization" below), ~60 min if not. After it completes, run the cross-domain match.

## What shipped this session

### 1. Durable bins loader — `E:\refrag\adapters\markets_bar_loader.py` (NEW)
Reads JSONL archive at `E:\Markets\live_data_history\<YYYY-MM-DD>\<asset>_<venue>_bins.jsonl` (append-only, date-partitioned, NEVER trimmed). Unions in `live_data\*.json` for most-current bars. Dedupes by ts. Solves the rolling-window LRU problem that caused 68% skip rate on the first full run. Coverage went from 30% → 100%.

### 2. `markets_refrag_adapter.py` — UPDATED
- Switched bin loading to use `markets_bar_loader.load_closes(asset, venue, t_min, t_max)`.
- Added `--resume` flag that reads existing summary.json, computes skip_set from already-processed `trade_source_id`s, processes only the rest, merges results back into the same summary.json.
- Used `--resume` to take Markets from 505 → 1690 processed (1185 new winners, 0 errors, 0 no_coverage, 16 too_short).

### 3. `markets_refrag_batched_adapter.py` — UPDATED then NEUTRALIZED
- Initially added `--key-depth N` flag for archetype batching.
- Greg pushed back on knobs not sanctioned by the arch doc. Per `feedback_arch_doc_authority.md`, this adapter is no longer the recommended path — it pre-aggregates trades before the runtime plane sees them, which the doc doesn't sanction. File still exists; just don't run it.

### 4. `quantum_refrag_adapter.py` — NEW
Sibling of markets_refrag_adapter.py. Calls SAME `OperatorOrchestrator.execute(pipeline_id="od_spectral_retrieval_pipeline")` Markets uses. Feeds `Re(rho[t, 0, 0])` (excited-state population) per quantum trajectory as the 1D float series. Default reads from `E:\operator_discovery\twobath_data\` (1560 trajectories, parameter sweep Tavg × DeltaT × lambda × gamma × init). Parses both SB QD3SET-1 and twobath filename conventions for metadata. Has `--resume`.

### 5. `cross_domain_transfer_detector.py` — EXTENDED
Added `comparison_mode="spectral_similarity"` branch alongside the legacy capability-Jaccard path. Reads per-domain summary.json via small registry (markets / quantum / spin_boson aliases), loads per-trade operator_coefficients vectors from referenced discovery files, L2-normalizes, builds `refrag_core.FaissIndex` over the target side, queries from source, returns matches above manifest's `similarity_threshold=0.7` default. `top_k=8` inherited from pipeline's own query default — not a new knob.

### 6. `_recover_quantum_session.py` — NEW (one-shot)
Scans `E:\refrag\artifacts\discoveries\` for files where the document node's source_id starts with `sb_twobath_`, reconstructs summary entries, merges into quantum summary.json. Used after `bxv6uyj6z` was killed mid-run. Recovered 648 trajectories.

## Current background state (verify at chat start)

- **No background processes running** at handoff time. Quantum task `bxv6uyj6z` was killed; recovery script `boplqiplh` completed.
- `E:\Markets\_full_pipeline_winners\summary.json`: 1690 results
- `E:\refrag\_full_pipeline_quantum\summary.json`: 648 results (recovered, marked `recovered: True`)
- `E:\refrag\artifacts\discoveries\`: 2428 total discovery files (1690 markets + 648 quantum + 90 misc)

## Pending todos — priority order

### 1. Resume quantum run (~15-60 min)
```
python E:\refrag\adapters\quantum_refrag_adapter.py --resume
```
Processes the remaining ~912 trajectories. Skips the 648 already recovered.

**Performance optimization** (optional but recommended): rotate `policy_history.jsonl` before the run to avoid architect risk #3 (orchestrator reads + rewrites entire file per call). Find via `glob E:\refrag\**\policy_history.jsonl`. Move to `.bak`. Per earlier observation, all runs picked `spectral_target` mode anyway, so wiping policy history loses no operational signal. Halves the remaining runtime.

### 2. Cross-domain match: Markets vs quantum
```python
from refrag_discovery.control_plane.cross_domain_transfer_detector import detect_cross_domain_transfer
out = detect_cross_domain_transfer(
    source_domain='markets', target_domain='quantum',
    comparison_mode='spectral_similarity', similarity_threshold=0.7,
)
print(out['source_n'], out['target_n'], len(out['transfer_candidates']))
```
**Hypothesis to test** (from earlier analysis): cross-domain signal should cluster in the 6 small-graph minority classes (11min - 49min horizons), NOT in the dominant (11,53) saturated long-hold class. The saturated class trades hit the FAISS retrieval cap (~11 chunks max) and lose structural detail; the smaller-graph classes are where the actual mathematical fingerprint lives, and that's the regime spin-boson trajectories (401-step finite dynamics) sit in too.

### 3. Wire `pipeline_marker = (n_nodes, n_edges)` into Markets adapter
Greg's reframe: the 7 evidence_graph signatures ARE the pipeline's natural taxonomy. The current `canonical_trade_key` (strategy|asset|side|...|13-field human key) is a guess at what matters; the pipeline says there are 7 horizon classes. Add `pipeline_marker` as an authoritative field in each summary entry. Don't replace canonical_trade_key — both stay for traceability.

### 4. Add incremental flush to adapters
5-line change to both `markets_refrag_adapter.py` and `quantum_refrag_adapter.py`: write summary.json every N=50 records, not just at end. Future kill+restart loses at most 50 records instead of everything. Architect risk #3 mitigation.

### 5. Finish admission-code investigation
Started but paused. Confirmed: `live_mock_trade_replay.py:114` does pure `net_bps / horizon` with NO fee deduction. Threshold checks (`ORACLE_WINNER_MIN_BANK_ENTRY_NET_BPS = 15.0`, `ORACLE_WINNER_MIN_BANK_ENTRY_NET_BPS_PER_MIN = 0.30`) are against gross. **One open question before recommending the fix**: is `match.get("avg_net_bps")` at line 102 actually net (already deducted) or gross? Need to trace upstream to oracle_winner_trade_memory.py or wherever `avg_net_bps` is set. If it's already net, double-subtraction is a bug. If it's gross, the field name is misleading and the gate IS using gross.

### 6. Hyperliquid data collector
Half-day effort. New file `E:\Markets\hyperliquid_collector.py` parallel to existing perp collectors. Writes bins in same schema as Bybit/Coinbase/Kraken so markets_bar_loader picks it up. Backfill from public REST history. Then re-run Markets refrag pipeline with Hyperliquid bars included → richer multi-venue analysis.

### 7. Hyperliquid executor + risk plumbing (later)
Only after data side validates. Multi-week effort. Must incorporate the opsec/cap constraints from day 1 (see "Opsec rules" below).

## Key findings this session

### Markets data
- **1690/1709 winners covered** (16 too_short, 0 no_coverage, 0 errors) — full reach via JSONL archive
- **All 1690 used `spectral_target` retrieval mode** — no policy exploration happening
- **validity_probability is tight: stdev 0.024, 93% in [0.30, 0.40)** — uniform across the winner set
- **Inverse net_bps↔validity_probability correlation seen in 505 was sample-skew** — disappeared at full sample (Δ=0.028 → Δ=0.014, n=423/quartile)

### Pipeline's natural taxonomy (the 7 signatures)
| sig | n | mean_hz | mean_bps | mean_vp |
|---|---|---|---|---|
| (5, 8) | 26 | 11min | 9 | 0.459 |
| (6, 13) | 33 | 19min | 12 | 0.411 |
| (7, 19) | 15 | 28min | 13 | 0.376 |
| (8, 26) | 21 | 25min | 13 | 0.347 |
| (9, 34) | 14 | 39min | 13 | 0.325 |
| (10, 43) | 22 | 34min | 16 | 0.308 |
| **(11, 53)** | **1559 (92%)** | **258min** | **189** | **0.314** |

Monotonic: more nodes/edges = longer hold = bigger net_bps. The validity_probability scalar IS the horizon-class marker disguised as a probability. (11,53) is "saturated" — FAISS retrieval cap reached, so any trade with enough chunks lands there regardless of underlying detail. The 6 minority classes are where finer structure lives. **Refrag: 7 classes are clean delineations, not noisy clusters** (intra-class stdev ≤ 0.008 on validity_prob).

### Fee-inclusive per-(venue, sig) analysis
Per-venue round-trip fee anchors: Bybit=4bp, Coinbase=10bp, Kraken=20bp.

Operational rule that falls out:
- **Bybit**: take any signature (4bp clears all classes)
- **Coinbase**: only (11,53) viable in practice; (10,43) marginal
- **Kraken**: only (11,53) viable; all 6 short classes mathematically lose

Best post-fee bps/min cells: top 4 are all (11,53) holds on Bybit/Coinbase/Kraken (~0.64-0.68 bps/min); short classes on Bybit clear but with tiny n.

### Hyperliquid (chosen execution venue)
- 1.5bp maker / 4.5bp taker → ~3-9bp round-trip. Cheapest US-onshore perp option.
- No KYC, BTC/ETH/SOL/many alts, EIP-712 signed orders, official Python SDK (`hyperliquid-python-sdk`)
- Uses Coinbase Wallet (NEW wallet, NOT Greg's existing `gergd.base.eth` address — that's already publicly tied to his identity and using the same wallet doxxes the entire trading history)
- USDC on Arbitrum is the deposit rail. Coinbase exchange → withdraw USDC to Arbitrum-network address.
- CFTC enforcement risk exists for DEX perps in US (dYdX v3 was settled $1.8M late 2024). Hyperliquid hasn't been targeted publicly but framework can shift.

## Opsec rules (must shape executor design from day 1)

### 1. Never crown the leaderboard — top/bottom 90% is fine
Saved as `feedback_trading_visibility_opsec.md`. **Refined this session**: Greg wants the BEST trades the strategy generates (don't deliberately leave alpha on the table) — but never appear as #1 best long OR #1 best short OR #worst long OR #worst short on any public leaderboard. Top ~10% is anonymous among many; literal #1 generates press attention. **Four separate leaderboard cells to avoid**, not two.

Implications for executor:
- Leaderboard monitor is part of the executor stack, not optional. Polls Hyperliquid's public leaderboard endpoints continuously, knows current #1-#10 thresholds for winners AND losers, feeds those numbers back into position/PnL caps dynamically.
- Caps are tied to leaderboard distance, not absolute size. As leaderboard moves, caps move.
- Multi-wallet sharding when total capital approaches visibility band.
- Wallet rotation triggers when trailing PnL or position size climbs toward leaderboard rank.

### 2. $20k start-of-day cap per platform (NOT YET SAVED TO MEMORY — Greg interrupted save)
Hard rule. Each platform's start-of-day USD balance must be ≤ $20,000. Intraday gains can accumulate (end-of-day balance can exceed $20k). Excess gets banked (withdrawn) before next session.

Why: Greg explicit: "i don't want to be the signal" — his account size shouldn't BE the signal that other traders watch. $20k per venue keeps each wallet firmly in the noise on major venues.

Implications for executor:
- Pre-session sweep script (mandatory): query each venue balance, withdraw excess above $20k to banking destination, BLOCK trading on over-capped account until sweep confirms.
- Position sizing math uses $20k as denominator, not current intraday balance — otherwise strategy compounds mid-day and surfaces as large position by afternoon.
- Banking destination per venue needs decision (probably Coinbase exchange or cold storage; confirm before wiring).
- Multi-venue scaling: total capital > N × $20k requires adding venues, not adding capital to existing venues.

**Action for new chat**: write this as a formal memory entry (`feedback_per_platform_capital_cap.md`) — Greg interrupted the save mid-session but the rule stands.

### 3. Net numbers only in all analysis
Saved as `feedback_fees_in_rate_analysis.md`. Greg explicit: "we need net #s. i only care about price with fees." All bps/min, EV, and comparison-across-strategies analysis must include venue-specific fees from the start. Don't compute gross and call it done.

### 4. Wallet hygiene
- New wallet for Hyperliquid, NOT linked to `gergd.base.eth` (already public Coinbase identity)
- Don't bridge funds from `gergd.base.eth` wallet directly to HL wallet (chain analysis walks it in one hop)
- Fund HL wallet via direct withdrawal from Coinbase exchange (Coinbase knows destination but it's not linked to `gergd.base.eth`)
- Handle: random alphanumeric, never DavisAI-brand

### 5. Arch doc is authoritative
Saved as `feedback_arch_doc_authority.md`. When working in refrag, follow the v2.1 spec. Don't invent knobs the doc doesn't sanction. Workarounds belong in adapters/control-plane operators, not in synthetic pre-aggregation.

## Open questions to resolve in new chat

1. **Is `avg_net_bps` already net of fees, or gross?** (blocks the admission gate fix recommendation)
2. **Where do nightly bank-down withdrawals go?** (per-venue banking destination — Coinbase exchange? Cold storage? Multiple?)
3. **Hyperliquid handle**: pick a random alphanumeric one before account creation
4. **Onboarding sequence**: Greg needs to create new wallet, fund USDC on Arbitrum, connect to app.hyperliquid.xyz, generate API wallet — before any executor code is useful

## Live constraints (anti-drift)

- **DO NOT** use `E:\Markets\live_data\*.json` directly — always go through `markets_bar_loader.load_closes(asset, venue, ...)` which unions the JSONL archive
- **DO NOT** restart quantum without `--resume` flag — would reprocess 648 already-done trajectories
- **DO NOT** invoke `markets_refrag_batched_adapter.py` — neutralized this session as doc-incompatible
- **DO NOT** modify refrag-core (Rule 7) or refrag_discovery runtime operators (extension is fine: e.g., the spectral_similarity mode in cross_domain_transfer_detector is an extension, not modification)
- **DO** use net numbers in any rate analysis (fees included from the start)
- **DO** save the $20k cap memory at the start of the new chat — it's a hard rule that should govern all executor work
- **DO** verify `policy_history.jsonl` size/location before restarting quantum — rotating it saves significant time
- **DO NOT** push to git unless Greg explicitly asks (his standing rule)

## Files of interest

| Path | Role |
|---|---|
| `E:\refrag\adapters\markets_bar_loader.py` | **NEW** — canonical bin loader |
| `E:\refrag\adapters\markets_refrag_adapter.py` | **UPDATED** — uses loader, has --resume |
| `E:\refrag\adapters\markets_refrag_batched_adapter.py` | NEUTRALIZED — don't run |
| `E:\refrag\adapters\quantum_refrag_adapter.py` | **NEW** — quantum sibling adapter |
| `E:\refrag\adapters\winner_archetype_indexer.py` | From part 1, untouched |
| `E:\refrag\adapters\markets_inflight_predictor.py` | From part 1, untouched |
| `E:\refrag\adapters\_recover_quantum_session.py` | **NEW** — one-shot recovery (used this session) |
| `E:\refrag\refrag_discovery\control_plane\cross_domain_transfer_detector.py` | **EXTENDED** with spectral_similarity mode |
| `E:\Markets\_full_pipeline_winners\summary.json` | 1690 Markets winner results |
| `E:\refrag\_full_pipeline_quantum\summary.json` | 648 quantum results (recovered) |
| `E:\refrag\artifacts\discoveries\{run_id}.json` | 2428 per-run discoveries (1690 markets + 648 quantum + 90 other) |
| `E:\Markets\live_data_history\<UTC-date>\*.jsonl` | **THE** durable bin source — never trimmed |

## Memory entries (this session)

Saved:
- `feedback_arch_doc_authority.md` (NEW)
- `feedback_fees_in_rate_analysis.md` (NEW)
- `feedback_trading_visibility_opsec.md` (NEW → refined for long/short distinction)
- `reference_markets_bar_archive.md` (NEW)
- `project_markets_bin_coverage_gap.md` (UPDATED → marked SUPERSEDED with pointer to new reference)

**Pending save** (Greg interrupted, but the rule is real):
- `feedback_per_platform_capital_cap.md` — $20k start-of-day cap per platform

## End of handoff

Next chat: resume quantum, run cross-domain match, then either move to Hyperliquid data collector OR back to admission-code investigation depending on Greg's call.
