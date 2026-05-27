# Markets Offensive Layer — Consolidated Plan

**Created:** 2026-05-24
**Goal:** Move Markets from defensive-only (wilson + protective stop the bleed) to net-positive PnL by stacking offensive layers that identify winning trades.
**Constraint:** Don't lose the validated defensive layer. Don't fit constants to the backtest window. Markets is for friends, not enterprise — favor surgical changes over re-architecture.

---

## 1. Anchor — what works already (do not regress)

Wilson + protective evidence gate is producing real signal. From the prior session's rerun at 3.6% of historic tape:

| Metric | Prior run @ ~7% | Rerun @ 3.6% with evidence gate |
|---|---:|---:|
| Trades | ~378 | 61 (6× fewer) |
| Bank trades | ~20 | 4 |
| Bank PnL | **-$13** | **+$210.04** |
| All PnL | -$4,318 | -$22.80 |

The defensive layer admits fewer trades and the few it does admit at bank size are net positive. That is the seed result we are scaling, not replacing.

Active backtests on the full 230h tape (do not interrupt):
- **PID 89876** — wilson mode, ~21.6% complete, baseline anchor
- **PID 96124** — protective mode, ~12.0% complete, current best baseline
- **PID 76100** — hindsight evolve worker (feeds the missed-winner queue, leave running)
- **PID 49916** — live RT on pre-evidence-gate code, do NOT restart until offensive layers validated

---

## 1.1 Per-platform bank semantics (important architectural fact)

**Each of the 3 platforms (Bybit, Coinbase, Kraken) has its own independent bank.** Up to **3 trades can be live simultaneously** — one per platform. Each trade signal must be platform-specific.

Implications for the offensive layers:
- **Phase 1 (in-flight promote)** is already platform-correct: `mock_trade_replay.close_open_for_status` filters open trades per `(status.asset, status.venue)` at line 1209. Each trade's `trade["venue"]` carries the platform identity. Promotion decisions are independent per platform — three banks compete for three slots without cross-talk.
- **Phase 2 (promoted-context allowlist)** is keyed by `(asset, venue, side, session, family)`. Entries like `BTC|bybit|buy|remaining18h` and `BTC|coinbase|buy|first6h` are distinct rows. Plumbing respects this natively.
- **Phase 3 (refrag)** must include `venue` as a high-weight identity feature in the embedding so nucleus-engine's K-NN retrieval clusters within-platform.
- **Spot-checks** must bucket per venue and assert: per-venue promoted-trade PnL is positive AND no single venue dominates more than ~70% of promotions (sanity check against single-platform over-fitting).

## 1.2 Cumulative-bank PnL accounting (start from run 1)

Bank trades use **100% of the compounding bank** each time — each win raises the floor for the next bank trade. In the simulator, per-trade notional is fixed (`fixed_mock_notional_usd` default $10,000) for comparability, but the bank EQUITY trajectory still compounds via realized PnL accumulation.

PnL comparisons in this plan are anchored to **run 1** (the initial ungated backtest that lost the full -$743k on the 67k tape), not to historical context outside the evidence-gate work. Wilson and protective improved over run 1 (the prior-session +$210 anchor); in-flight promotion adds on top of that progression.

Trajectory we track (all $10k-notional bps × N at simulator level):
```
run 1 ungated        →  -$743,679                     (baseline, full tape)
wilson v1 default    →  -$198,249  (+$545,430 saved)
protective v1        →    -$3,216  (+$740,463 saved)
in-flight promote    →    [target: bank PnL positive on full tape]
+ allowlist          →    [stack to improve further]
+ refrag             →    [strategic, parallel track]
```

In live deployment the cumulative-bank semantics matter for position-sizing; in the spot-check and historical backtest they show up as the per-bank-trade $10k-notional accounting. The simulator's bank PnL number is the right comparison metric across modes.

## 2. Honest findings from this session's diagnostics

### 2.1 Canonical-key admission gates cannot generate positive PnL at this base rate

Tested three canonical-key offensive variants this session against the 67,728-trade tape:

| Variant | Promotions on 67k tape | Reason it failed |
|---|---:|---|
| Symmetric identity-gated K-NN | 0 | K-NN identity-pooled LB never reaches global break-even |
| EV-ranker v1 (self LB only) | 0 | No shadow candidates with self_n ≥ 10 — all shadows are cold-start |
| EV-ranker v2 (identity LB fallback) | 0 | Max identity EV_LB across all 24 identity buckets = **-2.84 bps**. Floor at 0 still wouldn't promote |

**The math behind the limit:** At 8.29% base win-rate with roughly symmetric (avg_win, avg_loss) geometry, getting EV_LB > 0 requires `avg_win ≥ 11.5 × avg_loss`. No strategy in the population is structured that way. This is a fundamental property of the data + canonical-key feature space, not a tuning issue.

Files left in tree but parked: `markets_ev_ranker.py`, `replay_spotcheck_ev_ranker.py`, `replay_spotcheck_protective_v2.py`, `replay_diagnostic_knn_promote_gap.py`. Keep for reference; don't iterate further on canonical-key admission variants.

### 2.2 Where the actual signal lives (policy ground truth, `_analysis_historical_rt_trade_shapes_20260523/HISTORICAL_RT_TRADE_SHAPE_SIGNALS.md`)

Across the same 67,728 trades (5,616 winners, 8.29% base):

| Signal | Precision | Lift | Recall | Median net bps when fires |
|---|---:|---:|---:|---:|
| `hold_min_ge_runners @ 60` | **85.6 %** | **10.3×** | 20.9 % | **+22.0** |
| `hold_min_ge_runners @ 120` | 71.9 % | 8.7× | 3.0 % | +24.8 |
| `reached_20bps_within_30m` | **68.0 %** | **8.2×** | 92.1 % | +2.3 |
| `reached_20bps_within_60m` | 68.0 % | 8.2× | 93.2 % | +2.4 |
| `cover_by_15m` (NEGATIVE gate) | 33.8 % | 4.1× | 98.3 % | -3.8 |
| `reached_12bps_within_30m` | 41.3 % | 5.0× | 98.5 % | -2.8 |
| Every entry-time signal tested | 8-10 % | **1.0–1.3×** | varied | -10 to -12 |

**The shape of the answer:** entry-time observables in this ledger are essentially un-informative. Path/in-flight signals carry the 8-10× lift. The strongest single rule (`hold_min ≥ 60 + reached_20bps_within_30m`) reaches 85% precision. Winners are identifiable while the trade is open, not before it starts.

Within winners, strong (>+$10) vs weak (<+$3) cohorts have the same entry features and the same early-cover behavior. The single distinguisher is MFE attained — i.e., does the trade have "legs". Live-observable proxy: `net_bps_per_min` measured at the 10-15 min checkpoint. Strong winners ramp at ~0.7 bps/min, weak winners stall under 0.1.

### 2.3 Existing positive-EV evidence sources we have not been using

| Asset | Path | What it offers |
|---|---|---|
| Promoted contexts | `research/strategy_evolution/_study_list.json` | Validated (asset, venue, side, session) × family pairs with positive `pnl_R`. Top entries: `BTC|bybit|buy|remaining18h × buy_up_continuation` (pnl_R 195.66, 173 trades, 43% WR); `BTC|bybit|sell|remaining18h × small_move_fade` (pnl_R 123.20, 44 trades, 59% WR) |
| Missed-winner queue | `research/strategy_evolution/_hindsight_missed_winner_queue.json` | 9,098 opportunities, 7,287 oracle winners, 1,421 missed entries. **$145,825 in net PnL missed just from non-opened entries.** Top family `BUY_UP_CONTINUATION` worth $114,710 of that. Updated 2026-05-24 00:17 UTC (today, fresh) |
| Family killlist | `research/strategy_evolution/_live_family_killlist.json` | Already-disabled (family, context) pairs with audited live-mock losses. Stack on top of protective for extra reject coverage |
| Evolution queue | `research/strategy_evolution/_queue.json` | Live pipeline of strategy variants flagged for mutation. Source of next-batch hypotheses |
| Refrag stack | `E:\refrag\` | 5 layers: refrag_core (chunking/encoder/projector/retrieval/selector) + refrag_discovery (operator lifecycle/promotion/lineage) + refrag_mcp + adapters + 28 davisai-components services (nucleus-engine 5101, rankcore 5103, opportune 5104, feedbackloop 5025, nova-lang 5121, blanket 5122, etc.) |

---

## 3. The architecture — five layers, stacked

```
Trade lifecycle:
┌─────────────────────────────────────────────────────────────────┐
│  ENTRY  →  IN-FLIGHT  →  EXIT                                   │
└─────────────────────────────────────────────────────────────────┘

Layer 1: DEFENSIVE ENTRY GATE                       [SHIPPED]
  wilson + protective in oracle_winner_evidence.py + markets_evidence_knn.py
  Wilson LB vs break-even, K-NN identity-gated demote.
  Effect: reject obvious losers, 6× fewer trades.

Layer 2: OFFENSIVE ENTRY GATE                       [Phase 2]
  Read _study_list.json + _hindsight_missed_winner_queue.json at admission.
  If (asset, venue, side, session) × family is on the promoted list,
  upgrade wilson's admit_shadow → admit_bank.
  If killlist context matches, force reject (additional layer on protective).
  Effect: known winners get bank size; known losers get extra reject.

Layer 3: IN-FLIGHT PROMOTION                        [Phase 1 — DO FIRST]
  Per-tick tracking of net_unrealized_bps + elapsed_min on every open trade.
  Compute: hold_min_so_far, reached_20bps_within_30m_so_far,
           net_bps_per_min, cover_by_15m_so_far.
  On signal fire (with quality gate, see Layer 4):
      bank_allocated_notional_usd ← real_mock_notional_usd  (mid-trade promote)
  Effect: shadow trades that prove themselves get bank-size PnL attribution.

Layer 4: EXIT QUALITY FILTER                        [Phase 1.5]
  Within Layer 3: only promote when net_bps_per_min ≥ 0.3 at the
  promotion check moment. Filters weak winners (stall under 0.1 bps/min)
  from strong winners (ramp at 0.7 bps/min).
  Also: existing cover_by_15m hard-cut already in trade_exit_strategy
  semantics — verify no sticky-flag bug locks it out (pnl-review anti-pattern).

Layer 5: STRATEGIC — continuous features                  [Phase 3, parallel/slow]
  Replace canonical-key keys with refrag continuous-feature retrieval.
  Stand up nucleus-engine + rankcore + opportune + feedbackloop locally.
  Write markets_refrag_adapter.py (TradeChunker + TradeEncoder + TradeQuery).
  Index historical trades, train rankcore on outcomes, route admission through opportune.
  Effect: positive-EV subgroups invisible to canonical-key pooling may surface.
```

Layers 2 and 3 stack with Layer 1 without modifying it. Layer 1 still rejects; Layer 2 upgrades surviving shadows to bank when the context is on the allowlist; Layer 3 upgrades surviving shadows to bank when the trade proves itself in flight.

---

## 4. Existing-pieces map (what lives where)

### 4.1 Admission and lifecycle

| Module | Role | Key entry points |
|---|---|---|
| `oracle_winner_evidence.py` | Wilson ledger + decide_admission(mode=wilson\|protective) | `decide_admission`, `record_close`, `posterior`, `global_rolling_payoff` |
| `markets_evidence_knn.py` | Protective gate: Wilson + K-NN identity demote | `decide_admission_protective`, `neighbor_posterior` |
| `oracle_winner_trade_memory.py` | Canonical-key index, entry match, `_apply_evidence_gate` | `match_oracle_winner`, `oracle_winner_canonical_trade_key` |
| `mock_trade_replay.py` | Trade lifecycle: open, update, close | `maybe_open` (line ~1051), `close_trade` (line 496), `unrealized_bps` (line 598), `net_unrealized_bps` (line 602), `maybe_rotate` (line 1012), `close_open_for_status` (line 1205) |
| `live_mock_trade_replay.py` | Live mock; reads evidence_decision + bank/shadow stamping | `_bank_entry_shadow_reason_for_trade` (~line 159) |
| `trade_exit_strategy.py` | Exit profiles, hold-time floors, fee-cover semantics | `score_exit_min_hold_minutes`, `max_hold_minutes`, `profitable_exit_gate_blocks` |
| `run_historical_rt_run2.py` | Historical backtest harness with `--evidence-mode` CLI | `_prepare_settings`, scenario seeding (~line 140-160) |

### 4.2 Trade dict shape (mid-trade fields available)

From `mock_trade_replay.py`:
- `trade["ts_utc"]` — entry timestamp
- `trade["notional"]` — total notional (default 10000 USD)
- `trade["real_mock_notional_usd"]` — actual position
- `trade["bank_allocated_notional_usd"]` — bank-attributed portion (this is what we flip for promotion)
- `trade["pnl_accounting_role"]` — `"bank_allocated"` vs `"oracle_shadow"`
- `trade["hold_minutes"]`, `trade["exit_max_hold_minutes"]`, `trade["score_exit_min_hold_minutes"]`
- `elapsed_min = (now - trade["ts_utc"]) / 60.0` (computed inline at line 1213)
- `unrealized_bps`, `net_unrealized_bps` computed each tick

Fields we need to ADD for Layer 3 (per-tick state we don't currently track):
- `trade["max_net_unrealized_bps"]` — running max of `net_unrealized_bps`
- `trade["first_ts_net_bps_ge_20"]` — first timestamp `net_unrealized_bps ≥ 20`
- `trade["first_ts_fee_covered"]` — first timestamp `net_unrealized_bps ≥ 0` (or equiv fee_bps threshold)

These three augmentations to the trade dict are the entire in-flight-promotion data model.

### 4.3 Refrag stack reference

| Layer | Path | Role |
|---|---|---|
| Core pipeline | `E:\refrag\refrag_core\` | chunking, encoder, projector, retrieval, selector, metrics, cache |
| Discovery / control plane | `E:\refrag\refrag_discovery\control_plane\` | operator_lifecycle_tracker, operator_promotion_recommender, operator_lineage_tracker, task_meta_learner, cross_domain_transfer_detector |
| MCP server | `E:\refrag\refrag_mcp\` | gateway, server, public_tools (defer — direct Python import fine for local) |
| Adapters | `E:\refrag\adapters\od_refrag_adapter.py` | OD's adapter pattern. Domain provides Chunker+Encoder+Query; refrag provides projector/index/selector/decoder |
| Services (also `E:\DavisAI-Components\`) | `E:\refrag\davisai-components\` | nucleus-engine (5101), rankcore (5103), opportune (5104), feedbackloop (5025), nova-lang (5121), blanket-framework (5122), and 22 others |

Greg's directive: **use the full suite**, not cherry-picked pieces. OD adapter direction is "domain feeds refrag," not "refrag is a template."

### 4.4 The OD analogy

`E:\od_autoresearch\od_autoresearch.md` is the autoresearch PROTOCOL document. It is engine-agnostic by design. Markets needs a parallel `markets_autoresearch.md` once we have a worked Phase-1 example to codify. Autoresearch itself is a separate product (per Greg, "different product, not the od engine"); a generic driver and product README come AFTER Markets has a positive-PnL worked example.

---

## 4.5 Post-phase analysis rhythm (Greg's directive)

After every phase ships, run BOTH analyzers and discuss before starting the next phase.

### 4.5.1 `analyze_sidelined_and_losses.py` — cohort-level (fast, ~1 min)

Surfaces, per evidence mode:

1. **Sidelined big winners** — trades the mode rejected or kept-shadow that turned out to have `net_bps ≥ +15 bps`. PnL left on the table.
2. **Admitted losers** — bank-admitted trades with `net_bps < 0`. Subset flagged: **FAKEOUTS** (Signal A fired with `tte_20bps_min < 3 min` — fast spikes that reversed).
3. **Admitted winners** (context) — what the mode got right.

Fix suggestions with expected $ impact:
- **F1** Fakeout gate — require minimum elapsed before Signal A fires
- **F2** Strategy-family filter — skip promotion for net-negative families
- **F3** Allowlist upgrade — top sidelined `(asset|venue|side)` contexts → Phase 2 target
- **F4** Cover-by-15m exit — hard negative gate from policy ground truth

### 4.5.2 `analyze_chunks_winners_vs_losers.py` — chunk-level (deeper, ~3-5 min)

Picks the top 100 winners + top 100 losers by `net_bps`, slices each trade's bar path from the venue bin files, runs `MarketChunker` + `MarketChunkEncoder` on each, and reports:

1. **Chunk-level feature separability** — Cohen's d for each scalar feature (ret_mean, ret_std, dipole, OFI, vpin, realized_vol, spectral_energy, spectral_entropy, peak_frequency, spectral_centroid, etc) between winners and losers. Features with `|d| ≥ 0.5` flagged as candidate hidden signals.

2. **Per-trade aggregate comparison** — same features but averaged per trade, then compared cohort-to-cohort. Cross-checks the chunk-level finding.

3. **Hidden-signal fix suggestions** — for each top discriminator, suggests a promotion gate (e.g., "promote when mean_dipole ≥ 0.04") with the source feature name and direction.

The chunk analyzer's purpose: find signals the trade-level aggregates miss. If `mean_spectral_entropy` separates winners cleanly but isn't in our current in-flight logic, that's a candidate for v1.1 or for the refrag embedding feature list.

### Workflow per phase

1. Phase code lands → re-run cohort analyzer → re-run chunk analyzer → discuss
2. Decide: (a) refine current phase (Phase X.5), (b) move to next phase, (c) escalate to refrag
3. Loop

## 5. The plan

### Phase 0 — Remaining audit (no code, before Phase 1)

These are read-only confirmations to de-risk Phase 1 implementation:

- [ ] Verify how `mock_trade_replay` updates open trades per tick — find the loop that calls `unrealized_bps` so we know exactly where to attach max/first-time tracking
- [ ] Confirm `pnl_accounting_role` and `bank_allocated_notional_usd` are the only two fields needed to flip shadow → bank attribution (no PnL-realization side effects from flipping mid-trade)
- [ ] Read `_hindsight_missed_winner_queue.json` past the summary block — get the actionable pattern entries (canonical-key components, asset/venue/side/session, family)
- [ ] Confirm `_study_list.json` schema is stable; check whether `strategy_switcher.py` already reads it (if so, we may just need to wire its output into the bank/shadow decision instead of the routing decision)
- [ ] Skim `HANDOFF_REFRAG_EVOLUTION_CONTINUE_H48.md` + `HANDOFF_CLEAN_SLATE_STRATEGY_EVOLUTION.md` for any "refrag relay" wiring that already exists in Markets — don't duplicate
- [ ] Check the wilson/protective backtest progress; flag if either crashes or shows anomalies

### Phase 1 — In-flight promotion (Track A, biggest expected lift)

**Acceptance criteria:** promoted-shadow trades net positive in aggregate AND in every per-strategy bucket on the 67k tape. No regression in wilson/protective decisions.

**Step 1.1 — Add per-tick tracking** to `mock_trade_replay.py`'s open-trade update loop. Three new fields on the trade dict:
- `max_net_unrealized_bps` — initialized 0 on open, updated each tick: `max(prev, net_unrealized_bps)`
- `first_ts_net_bps_ge_20` — None initially; set on first tick where `net_unrealized_bps ≥ 20`
- `first_ts_fee_covered` — None initially; set on first tick where `net_unrealized_bps ≥ 0`

Guard against the pnl-review anti-pattern "sticky flags that lock out reversals": these three fields are monotonic so they don't lock out anything — they just record event occurrence.

**Step 1.2 — New module** `markets_in_flight_promote.py` with one function:

```python
def should_promote(trade, current_net_bps, current_elapsed_min, scenario) -> dict:
    """Return {promote: bool, reason: str, signal_fired: str} for shadow trades.

    Signals (from HISTORICAL_RT_TRADE_SHAPE_SIGNALS.md):
      hold_min_ge_runners @ 60: 85.64% precision, 10.3x lift, +22 bps median
      reached_20bps_within_30m: 67.96% precision, 8.20x lift, +2.3 bps median
    Quality gate: net_bps_per_min >= 0.3 (separates strong from weak winners)
    """
```

Logic:
- If trade already `bank_allocated` → return no-op.
- Compute `net_bps_per_min = current_net_bps / max(current_elapsed_min, 1.0)`.
- **Quality gate**: if `net_bps_per_min < 0.3` → no promote (avoid weak-winner stalls).
- **Signal A (hold_min ≥ 60)**: if `current_elapsed_min ≥ 60` AND `current_net_bps > 0` → promote.
- **Signal B (reached_20bps_within_30m)**: if `trade["first_ts_net_bps_ge_20"]` is not None AND that ts is within 30 min of `trade["ts_utc"]` → promote.
- All thresholds (60, 20, 30, 0.3) are derived from precision/lift research — economic/statistical, not tape-tuned.

**Step 1.3 — Wire into the update loop**. At the end of each tick's open-trade update (after `unrealized_bps` is computed), check `should_promote`. If True AND `pnl_accounting_role == "oracle_shadow"`:
- `trade["bank_allocated_notional_usd"] = trade["real_mock_notional_usd"]`
- `trade["pnl_accounting_role"] = "bank_allocated"`
- `trade["in_flight_promoted_at_ts"] = ts`
- `trade["in_flight_promoted_signal"] = signal_fired`

Wilson + protective entry decision is unchanged. The change is purely mid-trade attribution.

**Step 1.4 — Replay spot-check**. New script `replay_spotcheck_in_flight_promote.py`:
- Same incremental-index style as the existing 67k spot-checks
- For each trade in `per_trade.csv`, simulate the per-tick lifecycle using the already-recorded path metrics (`tte_20bps_min`, `hold_min`, `net_bps_per_min`)
- Compare wilson / protective / in_flight_promote bank PnL per-strategy

Pass = promoted trades net positive in aggregate AND every per-strategy bucket. If any per-strategy bucket regresses, surface the bucket; don't ship until structurally explained.

**Step 1.5 — Backtest mode**. Add `"in_flight_promote"` to `oracle_winner_evidence.decide_admission`'s mode dispatch (still uses protective for entry; new mode flags the in-flight wiring on). Add `--evidence-mode in_flight_promote` to `run_historical_rt_run2.py`. Launch parallel to existing wilson/protective backtests, separate ledger path.

**Stop conditions for Phase 1:**
- If spot-check passes: ship to backtest, await full-tape result.
- If spot-check shows promoted trades net negative: hypothesis is wrong about the quality gate or signal thresholds. Iterate on `net_bps_per_min` floor; do not iterate on signal thresholds (they come from the policy analysis).
- If still negative after one iteration: park Phase 1, escalate to Phase 3 (refrag).

### Phase 2 — Promoted-context allowlist (Track A, parallel to Phase 1)

**Acceptance criteria:** Trades upgraded by the allowlist are net positive (in aggregate) on the 67k tape AND match a context from `_study_list.json` with `pnl_R > 50 AND trades >= 20` (filters n=1 noise like the BTC|bybit|buy|first6h mean_reversion_chop entry).

**Step 2.1 — Load promoted contexts** at backtest startup:
```python
def load_promoted_contexts(min_pnl_r=50.0, min_trades=20):
    """Returns dict: (asset, venue, side, session) -> family.

    Filtered to high-conviction entries to avoid n=1 noise.
    """
```

**Step 2.2 — Honored allowlist intersection** with wilson decision:
- After wilson + protective decide, if wilson said `admit_shadow` or `admit_bank`:
  - Compute the trade's (asset, venue, side, session, family)
  - If matches an allowlisted entry: force `admit_bank`, reason `study_list_allowlist:<pnl_R>`
- Wilson `reject` is preserved.

Layer 2 does NOT touch Layer 1's reject path — it only upgrades shadow→bank or confirms bank.

**Step 2.3 — Hindsight queue intersection (optional secondary signal):**
- For shadow candidates, also check if the (canonical_key, family) is in the missed-winner queue with `promotion_state == "candidate_watch"` AND `oracle_incremental_vs_actual_usd > 5000`.
- If so: same upgrade.
- Lower-conviction signal — gate behind a separate scenario flag for A/B-able testing.

**Step 2.4 — Spot-check + backtest.** Same pattern as Phase 1.

### Phase 3 — Refrag stack (Track B, parallel/slow)

This runs in parallel with Phases 1+2. It is the strategic redesign, slower payoff.

**Step 3.1 — Stand up local services.** `cd E:\refrag\davisai-components && python scripts/run_local_stack.py`. Health-check ports 5101 (nucleus), 5103 (rankcore), 5104 (opportune), 5025 (feedbackloop). Confirm `/backends` reports local mode. No prod dependencies yet.

**Step 3.2 — Write `markets_refrag_adapter.py`** mirroring `E:\refrag\adapters\od_refrag_adapter.py`'s pattern:
- `MarketsTradeChunker` — decomposes a candidate trade into chunks (entry context features + in-flight path snapshots). Window over bar-level data; reuse logic from existing `markets_chunk_overlap.py` if applicable.
- `MarketsTradeEncoder` — converts trade-chunks to feature vectors. Uses both canonical-key components (one-hot) and numerical features (spread, depth, age, volatility, dipole).
- `MarketsTradeQuery` — builds a "would this trade win?" query from the current candidate.

**Step 3.3 — Index historical trades into nucleus-engine** via `/embed` + index API. Trades from `oracle_winner_evidence_ledger.jsonl` (and existing per_trade.csv archives) get embedded.

**Step 3.4 — Train rankcore on win/loss labels.** Each historical trade has `net_bps > 0` as the binary label. Feedbackloop `/retrain` triggers the LightGBM fit on the labeled embeddings.

**Step 3.5 — Wire `refrag` evidence mode** that calls:
1. `nucleus-engine /embed` to embed the candidate
2. `nucleus-engine /similar` for K-nearest historical trades
3. `rankcore /score` for an EV/probability estimate with SHAP factors
4. `opportune /action` to decide bank/shadow/reject
5. `feedbackloop /outcome` on close (post-trade)

**Step 3.6 — Operator-level promotion** via `refrag_discovery.control_plane.operator_promotion_recommender`: treat each canonical_key as an "operator" (an admission rule). When the operator's lifecycle is `stable` + non-drifting + EV-positive over rolling window, promote that rule from shadow to bank. This is per-operator, not per-trade — runs out-of-band (daily?).

**Acceptance criteria:** refrag mode produces ≥ as many positive-PnL bank trades as protective on 67k tape, AND surfaces at least one positive-EV subgroup invisible to canonical-key pooling.

**Stop conditions:**
- If services don't start cleanly: file an audit task; don't block Phase 1+2 on this.
- If indexing takes longer than expected: keep Phase 1+2 shipping; refrag becomes "next-gen" admission mode for follow-up sessions.

### Phase 4 — Codify (only after Phase 1 or 2 lands net positive)

Write `markets_autoresearch.md` using the OD autoresearch protocol template (`E:\od_autoresearch\od_autoresearch.md`) but for Markets. Fill in:
- Read-only: backtest harness + per_trade.csv + oracle_winner_trade_list.json
- Tunable: evidence-mode constants (n_min_for_bank, meaningful_floor_bps, hold_min_promote_threshold, net_bps_per_min_floor, allowlist filters)
- Metric: total bank PnL on tape at $10k notional
- Worked example: Phase 1 (in-flight promotion) and/or Phase 2 (allowlist) results

Phase 4 is the codification, not new research. It is the artifact future sessions inherit.

### Phase 5 — Deferred (do not start)

- Autoresearch product README — productize the protocol as a standalone DavisAI offering. Waits for Markets to be net positive (proof point).
- `operator_discovery_autoresearch.md` — apply the same autoresearch protocol structure to OD's `run_complete.py`. Greg confirmed OD stays local; Markets goes to AWS. Different deployment, same protocol.
- Generic autoresearch driver — only after two domains (OD, Markets) validate the pattern.

---

## 5.5 Refrag tool catalog — always-consider table (Greg's directive)

The full refrag suite at `E:\refrag\` is the strategic-tool palette. Every problem we hit should be checked against this catalog before building bespoke. Greg has full code for each tool separately if we want to dig into a specific implementation.

### refrag_discovery/control_plane (the "wild" tools)

| Tool | What it does | Where it applies to Markets |
|---|---|---|
| `operator_lifecycle_tracker` | candidate / stable / decaying / evolving / promoted state machine per operator | Track each canonical_key as an operator. "stable" + non-drifting key with positive EV → promote shadow→bank as a RULE (not just per-trade) |
| `operator_promotion_recommender` | scores operators for promotion: lifecycle state, drift, governance, schema breaking-change | Treat each evidence mode (wilson, protective, in_flight) as an operator; recommend promotion to live RT |
| `operator_lineage_tracker` | provenance per operator version + schema diff | Audit trail per admission decision (which mode, what evidence, what neighbors) |
| `operator_chain_builder` | compose operators into chains | Our wilson → protective → in_flight → allowlist IS an operator chain. Use chain builder to optimize sequence, not hand-order |
| `operator_composability_scorer` | scores how well operators combine | Detect when two layers are redundant or conflicting (e.g., does protective demote what in_flight would promote?) |
| `operator_gap_finder` | identifies missing operators in the current set | After Phase 1, ask: what TYPE of admission rule are we missing? Output: "you have rules for canonical-key evidence and in-flight signals; no rule for chunk-pattern matching" → guides next phase |
| `operator_graph_rewriter` | rewrites operator graphs dynamically | Adaptive: rewrite the admission pipeline when one layer starts under-performing |
| `operator_benchmark_suite` | systematic benchmark of operators | Standardized comparison of wilson vs protective vs in_flight vs refrag modes — replaces ad-hoc backtest comparison |
| `cross_domain_transfer_detector` | detect when patterns transfer across domains | BTC↔ETH, or first6h↔remaining18h, or Bybit↔Coinbase. Share evidence across correlated contexts |
| `exploration_policy_controller` | explore vs exploit tradeoff | Decides which strategies to probe (vs trust known-positive contexts). Replaces hand-coded `allow_context_probes` flag |
| `task_meta_learner` | learn what to learn / which features matter per task | **Phase 1.5 candidate**: learn which features matter for which strategy family. Replaces hand-coding "skip continuation families for Signal A" |
| `pipeline_performance_optimizer` | optimize pipeline end-to-end | Find the bottleneck operator and tune parameters |
| `production_readiness` | assess if an operator is ready for live | Required before restarting live RT with in_flight or refrag mode |
| `manifest_synthesizer` | synthesize manifests | Auto-generate the manifest/contract for new admission modes |

### davisai-components services (the layered runtime)

| Service | Port | What it does | Markets use case |
|---|---|---|---|
| `nucleus-engine` | 5101 | Embeddings + similarity + reasoning | Phase 3 — continuous-feature retrieval over historical trades |
| `civicfold` | 5102 | Signal folding operators | Compress canonical-key+in-flight signals into compact representations |
| `rankcore` | 5103 | LightGBM scoring + graph enrichment + SHAP | Phase 3 — EV scoring per candidate trade with feature attribution |
| `opportune` | 5104 | Next-best-action engine | Phase 3 — decides admit/reject/promote per trade |
| `feedbackloop` | 5025 | Outcome logging + retrain triggers | Phase 3 — replaces oracle_winner_evidence_ledger.jsonl + drives rankcore retraining |
| `actionpulse` | 5026 | Real-time event logging + high-value action detection | In-flight signals could fire through actionpulse for centralized tracking + alerting |
| `convertiq` | 5027 | A/B testing + funnel analysis + **statistical significance** | **Immediate**: rigorous comparison of wilson vs protective vs in_flight backtests with confidence intervals, not just point estimates |
| `maestro` | 5028 | Orchestrator (FREE with 5+ components) | Replace ad-hoc scenario flag system with a managed workflow |
| `quantum-signal-validator` | — | Find predictive signals in time-series + leading indicator discovery | **Immediate**: validate the chunk-analyzer's findings systematically. Find leading indicators we haven't thought of |
| `graphscout` | 5012 | Neo4j relationship discovery | Build graph of canonical_keys with edges by similarity. Find clusters K-NN misses |
| `nova-lang` | 5021 | Declarative agent-behavior DSL | Define admission rules in a DSL — easier to read/audit than scattered scenario flags |
| `blanket-framework` | 5022 | Microservices orchestration (gateway, health, config) | Service discovery + health monitoring for the refrag stack |
| `token-optimizer` | — | Token compression for LLM context | Compress trade representations for ML pipeline |
| `etl-pipeline` | 5024 | FREE — Census/Zillow/Redfin/WalkScore ETL | Pattern reuse: ingest market data sources via the same ETL framework |
| `artifacts` | — | Artifact storage | Persist trained models, indexes, replays |
| `config` | — | Shared config | Replace scattered scenario flags with one config layer |
| `credentials-vault` | 5017 | OAuth/API key storage | Live exchange credentials once we go live |
| `guarantee-system` | 5015 | Performance invariants + auto refunds/credits | **Production critical**: enforce "halt-on-drawdown" invariants when bank drops X% |
| `preintent-discovery` | — | Find sellers 30-90d before listing | Probably not applicable (RE-specific) |
| `fsbo-monitor`, `expired-resurrection`, `social-mining`, `investment-finder` | various | RE-specific lead gen | Not applicable |
| `choropleth-api`, `civic-scraper`, `civicfold` (RE side) | various | Visualization / civic data | Not applicable to trading |
| `territory-pricing`, `lead-distribution`, `renewal-engine` | various | RE monetization | Not applicable |
| `credentials-vault`, `social-scheduler`, `action-confirmation`, `ai-action-service` | various | RE automation | Not applicable except credentials-vault |

### Per-phase refrag candidates (which tools next, when)

**Phase 1.5 (refinement after Phase 1 ships):**
- `task_meta_learner` — learn the strategy-family filter rather than hand-code it
- `convertiq` — A/B test the v1.0 vs v1.1 promotion logic with proper statistical significance
- `operator_gap_finder` — identify what kind of rule is missing after we look at the cohort + chunk analyzer outputs

**Phase 2 (allowlist):**
- `operator_promotion_recommender` — operator-level promotion (each canonical_key as an operator; per-key shadow→bank rule)
- `operator_lifecycle_tracker` — stable/decaying classification per canonical_key
- `cross_domain_transfer_detector` — detect when a positive context transfers (BTC→ETH or vice versa)
- `actionpulse` — track high-value admission events centrally

**Phase 3 (refrag full integration):**
- nucleus-engine + rankcore + opportune + feedbackloop (already planned)
- `operator_chain_builder` + `operator_composability_scorer` — compose the layered stack rigorously
- `operator_benchmark_suite` — replace ad-hoc backtest comparison
- `quantum-signal-validator` — formal leading-indicator discovery
- `maestro` — orchestrate the whole pipeline
- `graphscout` — canonical_key relationship graphs

**Production (live RT restart):**
- `production_readiness` — gate the restart
- `guarantee-system` — halt-on-drawdown invariants
- `credentials-vault` — live exchange API keys
- `nova-lang` — declarative rule definitions

### What I'd want full code for first (priority order)

1. `task_meta_learner` — directly addresses the Phase 1.5 strategy-family-filter problem. If this works, we skip hand-coding the filter.
2. `convertiq` — gives us proper statistical confidence on mode comparison. We're going to compare wilson/protective/in_flight backtests soon; would rather use the rigorous tool than ad-hoc Cohen's d.
3. `operator_gap_finder` — meta-tool that tells us what kind of rule we're missing. Saves us from blindly stacking phases.
4. `quantum-signal-validator` — would replace my hand-rolled chunk analyzer's Cohen's d separability with the formal leading-indicator framework.
5. `operator_chain_builder` + `operator_composability_scorer` — for Phase 3 when we're composing the full stack.

These five would transform Phase 1.5 + Phase 2 from hand-rolled to rigorously-tooled.

## 6. What we will NOT do

- **No more EV-ranker variants** — confirmed structurally bounded (max identity EV_LB = -2.84 across all 24 buckets on 67k tape).
- **No more symmetric K-NN improvements** — confirmed structural no-op at this base rate.
- **No modifications to wilson or protective code** — defensive layer works.
- **No restart of live RT (PID 49916)** — until in_flight_promote or refrag validated.
- **No fitting any constant to the 67k tape** — every threshold must be derivable from economics, statistics, or precision/lift research, not from `replay+sweep`. Backtest is a sanity check, not a fitting target.
- **No cherry-picking from refrag stack** — Greg explicitly said use the full suite. When we wire refrag, wire enough of it to be representative.
- **No autoresearch product README before Markets is net positive** — the product story needs a proof point.

---

## 7. State to preserve across sessions

| Asset | Where | Why preserved |
|---|---|---|
| Wilson + protective code | `oracle_winner_evidence.py`, `markets_evidence_knn.py` | Defensive layer — produces the +$210 result |
| Active wilson backtest | PID 89876 (~21.6%) | Baseline anchor |
| Active protective backtest | PID 96124 (~12.0%) | Current best baseline |
| Hindsight evolve worker | PID 76100 | Maintains `_hindsight_missed_winner_queue.json` (offensive signal source) |
| Live RT | PID 49916 | Untouched until offensive validated |
| Evidence ledger | `research/strategy_evolution/oracle_winner_evidence_ledger.jsonl` | The growing corpus |
| Memory entries | `C:\Users\A\.claude\projects\E--\memory\` | Persistent principles (no-window-fit, best-outcome-not-break-even, etc.) |

This plan document itself: `E:\Markets\MARKETS_OFFENSIVE_LAYER_PLAN.md`. Single source of truth across sessions. Update it in place; don't fork.

---

## 8. Open questions to resolve in Phase 0.X audit

These don't block writing the plan but block Phase 1 implementation:

1. **The per-tick update site** — where in `mock_trade_replay.py` does an open trade get its `unrealized_bps` computed each tick? That's the hook for the three new state fields. Probably in a function called by the main run loop in `run_historical_rt_run2.py`. Find it before editing.

2. **`pnl_accounting_role` flip semantics** — does flipping `oracle_shadow → bank_allocated` mid-trade have any side effect besides accounting? Specifically: do any of the bank quality gates re-check on close and downgrade back? (See pnl-review anti-pattern: "No demotion path from bank back to shadow after quality changes.") We want bank-on-promotion to STICK if signal fires; the system should not auto-downgrade post-promotion.

3. **Existing refrag relay wiring** — `HANDOFF_CLEAN_SLATE_STRATEGY_EVOLUTION.md` mentions "Refrag relay and self-training memory". If any nucleus-engine integration already exists in Markets, Phase 3 builds on it rather than from scratch.

4. **`_study_list.json` reader** — does `strategy_switcher.py` (or another module) already load this file? If yes, the allowlist may already be available — Phase 2 may just need to plumb it into the evidence_decision instead of into routing.

5. **Wilson/protective backtest results** — when both PIDs complete, compare bank PnL. This is the baseline Phase 1+2 must beat.

---

## 9. Decision criteria summary

| Phase | Ship criterion | Stop criterion |
|---|---|---|
| 1 (in-flight promote) | Spot-check: promoted trades net positive in aggregate + every per-strategy bucket | Iterate `net_bps_per_min` floor once; if still negative, escalate to Phase 3 |
| 2 (allowlist) | Spot-check: allowlist-upgraded trades net positive AND no per-strategy regression | If allowlist trades net negative: tighten `min_pnl_r` and `min_trades` filters before retrying |
| 3 (refrag) | Backtest: positive bank PnL ≥ protective baseline AND surfaces ≥ 1 positive-EV subgroup | If services unstable: park, don't block Phases 1+2 |
| 4 (codify) | Phase 1 OR Phase 2 shipped and positive on full backtest | n/a |

---

## 10. Reference — files this plan touches or depends on

**Read-only references (do not modify):**
- `E:\Markets\_analysis_historical_rt_trade_shapes_20260523\HISTORICAL_RT_TRADE_SHAPE_SIGNALS.md` — policy ground truth
- `E:\Markets\_analysis_historical_rt_trade_shapes_20260523\per_trade.csv` — 67,728-trade tape
- `E:\od_autoresearch\od_autoresearch.md` — autoresearch protocol (template for markets_autoresearch.md)
- `E:\refrag\adapters\od_refrag_adapter.py` — adapter pattern (template for markets_refrag_adapter.py)

**Existing modules (extend, don't refactor):**
- `E:\Markets\oracle_winner_evidence.py` — add `"in_flight_promote"` mode dispatch
- `E:\Markets\mock_trade_replay.py` — add per-tick tracking + promotion hook
- `E:\Markets\live_mock_trade_replay.py` — same as mock_trade_replay for live path
- `E:\Markets\run_historical_rt_run2.py` — `--evidence-mode in_flight_promote|refrag` flags

**New modules to create:**
- `E:\Markets\markets_in_flight_promote.py` — Phase 1 promotion logic
- `E:\Markets\replay_spotcheck_in_flight_promote.py` — Phase 1 spot-check
- `E:\Markets\markets_promoted_context_allowlist.py` — Phase 2 allowlist reader + intersection
- `E:\Markets\replay_spotcheck_allowlist.py` — Phase 2 spot-check
- `E:\Markets\markets_refrag_adapter.py` — Phase 3 domain adapter
- `E:\Markets\markets_autoresearch.md` — Phase 4 codification

**Existing data files (read at admission time):**
- `E:\Markets\research\strategy_evolution\_study_list.json` — promoted contexts
- `E:\Markets\research\strategy_evolution\_hindsight_missed_winner_queue.json` — missed winners
- `E:\Markets\research\strategy_evolution\_live_family_killlist.json` — disabled contexts
- `E:\Markets\research\strategy_evolution\_queue.json` — evolution queue (informational)
- `E:\Markets\research\strategy_evolution\oracle_winner_evidence_ledger.jsonl` — evidence ledger

**Active processes (preserve, do not interrupt):**
- PID 89876 (wilson backtest), PID 96124 (protective backtest), PID 76100 (hindsight worker), PID 49916 (live RT, deferred)

---

*End of plan. Update in place as phases ship. Do not fork into multiple documents.*
