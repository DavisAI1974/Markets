# Cycle calculation pins (Greg Davis, 2026-09-20 22:23Z)

Greg: "we need to pin cycle 0 calcs with the first group of calcs we did. Same with the 2nd and then the rest
need to be pinned on when we came up with the rest of the original remaining calcs."

This file explains `CYCLE_CALCULATION_PINS.json`, which `frankie_principal_adapter.py` reads for the cycle
index it is built with (`make_principal_adapter` passes the binding's `cycle_index`). The pin is rendered into
the prompt prefix and the session request's `instruction` after the standing run-analysis instruction; its file
witness is saved beside the prompt (`calculation-pin-witness.json`) and carried in the attachment
(`calculation_pin_witness`), and the cycle index is part of the adapter's configuration hash. An adapter built
without a cycle index, or a cycle no pin covers, refuses to render a request. The test
`test_cycle_calculation_pins_are_committed_evidence_and_cover_every_cycle_once` re-hashes every source receipt
named here against the committed file, checks every layer against the registry crosswalk, and checks that the
pins cover cycles 0-18 once and the 49 registry calculation layers exactly.

## Reading applied (Greg's call to change; the JSON is data, the code does not care which reading it holds)

`group` = a calculation GROUP of the native ingestion registry (registry sha256 `239a14808850d9cc9ba589165e4263c0e3f11a0c574052f39bfaa133adf296b1`,
the seven groups the request instruction already names), ordered by the first git-add date of the earliest
committed file that carried that group's calculations. Cycle 0 = the first group we did, cycle 1 = the second,
cycles 2-6 = the remaining groups in date order, cycles 7-18 = the complete registry (every original calculation
exists by 2026-08-28). Evidence per group: the crosswalk of run 33746436209 names the producer file of every layer
(`crosswalk_producers`), and the dated original files are the `source_receipts` (path, bytes, sha256).

| cycles | group | first done | layers | source receipts |
|---|---|---|---:|---|
| 0 | `legacy_observable_crosswalk` | 2026-08-16 | 5 | `research/NG_EXHAUSTION_FAMILY_HANDOFF_20260816.md` 5fdcf2a6c089; `research/blind_freeze/ng_exhaustion_20260816/FRANKIE_NG_EXHAUSTION_BLIND_PREDICTION_FREEZE_MANIFEST_20260816.json` eb96507766c6; `research/FRANKIE_NG_PRE_FAMILY_CLASSIFIER_FROZEN_OPERATIONAL_20260817.json` 583f6a121788; `research/ng_exhaustion_chain_canonical_table_20260817.py` 4325776b4d70; `research/NG_EXHAUSTION_LIVE_CLOCK_V0_FINAL_PROOF_20260817.json` c50dc1f4f919 |
| 1 | `derived_geometry` | 2026-08-17 | 8 | `research/NG_EXHAUSTION_CHAIN_STUDY_CONTRACT_20260817.json` c226eff3f993; `research/NG_EXHAUSTION_CHAIN_DISCOVERY_FREEZE_20260817.json` 025f2abc68b2; `research/NG_EXHAUSTION_CHAIN_PHASE2_FINAL_FREEZE_20260818.md` 49133cbcbfcd; `research/NG_EXHAUSTION_CHAIN_PHASE2_ALL_AGENT_FINDINGS_20260818.md` d3e273b934ef; `research/NG_EXHAUSTION_D0_D5_V4_GEOMETRIC_SELF_ADAPTATION_CONTRACT_20260820.json` e36d82e245a7 |
| 2 | `prebirth_opportunity` | 2026-08-19 | 5 | `research/NG_EXHAUSTION_D1_D5_CHAIN_BIRTH_PREDICTABILITY_PROTOCOL_20260819.md` 736745465343; `research/NG_EXHAUSTION_D1_D5_CHAIN_BIRTH_PRIOR_AVAILABILITY_20260819.md` 2a417f397966; `research/NG_EXHAUSTION_CHAIN_BIRTH_V2_FINALIZATION_MANIFEST_20260819.json` a2d4987a03ac; `research/kalshi/knowledge/ng_brain_exhaustion_chain_birth_v2_proposal_20260819.json` 9251176dbb56 |
| 3 | `causal_clocks` | 2026-08-19 | 7 | `research/NG_EXHAUSTION_FULL_CAUSAL_INFORMATION_CORRECTION_20260819.md` fc08cbe26dd2; `research/NG_EXHAUSTION_CONTINUOUS_LIVE_INFORMATION_CORRECTION_20260819.md` b7d75c3f34e4; `research/NG_EXHAUSTION_EVENT_MARK_CLOCK_OPEN_BOUNDARY_20260819.md` b3c0f05a3d43; `research/NG_EXHAUSTION_CONTINUOUS_INSTANCE_TIMING_CORRECTION_20260820.md` 553c119d0809 |
| 4 | `order_lifecycle` | 2026-08-20 | 9 | `research/ng_exhaustion_mbo_v4_state_adapter_20260820.py` 4a80e3e4b838; `research/NG_EXHAUSTION_CHAIN_STEP1_5Y_V4_NATIVE_CENSUS_PROTOCOL_20260820.json` cc40727f2753; `research/NG_EXHAUSTION_V4_FINAL_HANDOFF_MANIFEST_20260820.json` e51044356b99 |
| 5 | `full_book_fifo_queue` | 2026-08-20 | 8 | `research/ng_exhaustion_mbo_v4_state_adapter_20260820.py` 4a80e3e4b838; `research/NG_EXHAUSTION_CHAIN_STEP1_5Y_V4_NATIVE_CENSUS_PROTOCOL_20260820.json` cc40727f2753; `research/NG_EXHAUSTION_V4_FINAL_HANDOFF_MANIFEST_20260820.json` e51044356b99 |
| 6 | `microstructure_mechanics` | 2026-08-20 | 7 | `research/ng_exhaustion_mbo_v4_state_adapter_20260820.py` 4a80e3e4b838; `research/NG_EXHAUSTION_CHAIN_STEP1_5Y_V4_NATIVE_CENSUS_PROTOCOL_20260820.json` cc40727f2753; `research/NG_EXHAUSTION_V4_FINAL_HANDOFF_MANIFEST_20260820.json` e51044356b99 |
| 7-18 | `complete_registry_as_of_20260828` | 2026-08-28 | 49 | `research/kalshi/frankie_boss/audits/CROSSWALK_SUNDAY_CYCLE0_FEED_33746436209_20260916.json` ece9c624d996; `research/kalshi/frankie_boss/audits/FRANKIE_FEED_AUDIT_SUNDAY_CYCLE0_20260916.md` 721fdb1c1989; `research/kalshi/NG_EXHAUSTION_FRANKIE_DATA_FEED_INVENTORY_20260824.md` bea60752e3d4 |

Per group, what was first done (from the receipts):

- **legacy_observable_crosswalk** (2026-08-16): the observables every first exhaustion calculation ran on: per-second roll20 dipole flow, native signed flow, price, book imbalance and the chain structure observables (the 2026-08-16 exhaustion families and blind test, the 2026-08-17 canonical event table). Layers: legacy_price, legacy_native_signed_flow, legacy_per_second_roll20, legacy_book_imbalance, legacy_structure_observables.
- **derived_geometry** (2026-08-17): the chain study: chain discovery and its freeze (origin, members, depth, reset, predecessor and ancestry state, unresolved-age chain trajectory) on 2026-08-17, its phase-2 characterization (D families and their geometry, roll20 and dipole state, price/flow/book paths) frozen 2026-08-18, and the D0-D5 geometric self-adaptation contract of 2026-08-20. Layers: derived_roll20_and_dipole_state, derived_d_family_geometry, derived_open_world_predecessor_state, derived_ancestry_gaps, derived_unresolved_age_chain_trajectory, derived_price_flow_book_paths, derived_v4_mechanics_fifo_features, derived_feature_availability_timestamps.
- **prebirth_opportunity** (2026-08-19): chain-birth predictability: the predecessor at risk, the unresolved chain extension, the ancestry successor opportunity, stopped-chain false-context controls and the negative opportunity cases (the 2026-08-19 chain-birth protocol, PRIOR availability and the birth v2 finalization). Layers: prebirth_predecessor_at_risk_state, prebirth_unresolved_chain_extension_state, prebirth_ancestry_successor_opportunity, prebirth_stopped_chain_false_context_controls, prebirth_negative_opportunity_cases.
- **causal_clocks** (2026-08-19): the distinct causal clocks: event time, receive time, event known-by, feature availability, prospective discovery confirmation, model evaluation and lock time, fixed by the 2026-08-19 full-causal and continuous-live information corrections and the 2026-08-20 event-mark open boundary and continuous-instance timing corrections. Layers: clock_event_time, clock_receive_time, clock_event_known_by, clock_feature_availability, clock_prospective_discovery_confirmation, clock_model_evaluation, clock_lock_time.
- **order_lifecycle** (2026-08-20): the raw MBO order lifecycle (adds, cancels, modifies, replaces, trades, fills, clears, identity transitions, contract session and roll state) first computed by the 2026-08-20 MBO V4 state adapter and its five-year step-1 native census protocol. Layers: order_lifecycle_adds, order_lifecycle_cancels, order_lifecycle_modifies, order_lifecycle_replaces, order_lifecycle_trades, order_lifecycle_fills, order_lifecycle_clears, order_identity_transitions, contract_session_roll_state.
- **full_book_fifo_queue** (2026-08-20): the full bid/ask book, price levels and order counts, FIFO queues, queue age and survival, queue concentration, orders and volume ahead, spread and depth imbalance and the complete state-reset bootstrap receipts, first computed by the 2026-08-20 MBO V4 state adapter. Layers: full_bid_ask_depth, price_level_and_order_counts, fifo_queues, queue_age_and_survival, queue_concentration, orders_and_volume_ahead, spread_and_depth_imbalance, complete_state_reset_bootstrap_receipts.
- **microstructure_mechanics** (2026-08-20): microstructure mechanics: actions by side and level, aggressor and native signed flow, depletion and replenishment, resilience and recovery, churn and queue turnover, price and book path, missingness and integrity flags, first computed by the 2026-08-20 MBO V4 state adapter. Layers: mechanics_actions_by_side_and_level, aggressor_and_native_signed_flow, depletion_and_replenishment, resilience_and_recovery, churn_and_queue_turnover, price_and_book_path, missingness_and_integrity_flags.
- **complete_registry_as_of_20260828** (2026-08-28): every original calculation, as the August 28 A_MEMORY recalculation (run 33746436209) carried them: all seven registry groups, the remaining original calculations as of the date we came up with them. Layers: order_lifecycle_adds, order_lifecycle_cancels, order_lifecycle_modifies, order_lifecycle_replaces, order_lifecycle_trades, order_lifecycle_fills, order_lifecycle_clears, order_identity_transitions, contract_session_roll_state, full_bid_ask_depth, price_level_and_order_counts, fifo_queues, queue_age_and_survival, queue_concentration, orders_and_volume_ahead, spread_and_depth_imbalance, complete_state_reset_bootstrap_receipts, mechanics_actions_by_side_and_level, aggressor_and_native_signed_flow, depletion_and_replenishment, resilience_and_recovery, churn_and_queue_turnover, price_and_book_path, missingness_and_integrity_flags, legacy_price, legacy_native_signed_flow, legacy_per_second_roll20, legacy_book_imbalance, legacy_structure_observables, derived_roll20_and_dipole_state, derived_d_family_geometry, derived_open_world_predecessor_state, derived_ancestry_gaps, derived_unresolved_age_chain_trajectory, derived_price_flow_book_paths, derived_v4_mechanics_fifo_features, derived_feature_availability_timestamps, prebirth_predecessor_at_risk_state, prebirth_unresolved_chain_extension_state, prebirth_ancestry_successor_opportunity, prebirth_stopped_chain_false_context_controls, prebirth_negative_opportunity_cases, clock_event_time, clock_receive_time, clock_event_known_by, clock_feature_availability, clock_prospective_discovery_confirmation, clock_model_evaluation, clock_lock_time.

## The alternative reading, recorded so it can be switched to without research

`group` = the dated research CAMPAIGNS as we ran them, strictly chronological by first git add:

| # | first done | campaign | defining receipts (on this branch) |
|---|---|---|---|
| 1 | 2026-08-16 | exhaustion families A/B/C and the Frankie blind test | `research/NG_EXHAUSTION_FAMILY_HANDOFF_20260816.md`, `research/blind_freeze/ng_exhaustion_20260816/FRANKIE_NG_EXHAUSTION_BLIND_PREDICTION_FREEZE_MANIFEST_20260816.json`, `research/FRANKIE_NG_PRE_FAMILY_CLASSIFIER_FROZEN_OPERATIONAL_20260817.json` |
| 2 | 2026-08-16/17 | runway clock v0 and the live clock | `research/NG_EXHAUSTION_RUNWAY_CLOCK_V0_20260817.md`, `research/NG_EXHAUSTION_RUNWAY_CLOCK_LARGE_BATCH_RESULTS_20260817.json`, `research/NG_EXHAUSTION_LIVE_CLOCK_V0_FINAL_PROOF_20260817.json` |
| 3 | 2026-08-17 | aftermath validation and the transition checkpoint | `research/NG_EXHAUSTION_AFTERMATH_CAUSAL_VALIDATION_FREEZE_20260817.json`, `research/NG_EXHAUSTION_AFTERMATH_TRANSITION_CHECKPOINT_FREEZE_20260817.json`, `research/NG_EXHAUSTION_AFTERMATH_VALIDATION_CONCLUSION_20260817.md` |
| 4 | 2026-08-17 | chain PHASE 1: discovery and census (the chain study's step 1) | `research/NG_EXHAUSTION_CHAIN_STUDY_CONTRACT_20260817.json`, `research/NG_EXHAUSTION_CHAIN_PHASE1_DISCOVERY_PROTOCOL_20260817.json`, `research/NG_EXHAUSTION_CHAIN_DISCOVERY_FREEZE_20260817.json`, `research/NG_EXHAUSTION_CHAIN_PHASE2_GATE_20260817.json` |
| 5 | 2026-08-17/18 | chain PHASE 2: characterization (the chain study's step 2: families, D structures, dipoles and geometry, pair and triplet recurrence, POX, reappearances, timing) | `research/NG_EXHAUSTION_CHAIN_PHASE2_FINAL_FREEZE_20260818.md`, `research/NG_EXHAUSTION_CHAIN_PHASE2_ALL_AGENT_FINDINGS_20260818.md`, `research/NG_EXHAUSTION_CHAIN_PHASE2_REAPPEARANCE_WATCH_MAP_20260818.json` |
| 6 | 2026-08-18 | post-phase-2, exact D1 and entry timing | `research/NG_EXHAUSTION_EXACT_D1_AGENT_CONTRACT_20260818.md`, `research/NG_EXHAUSTION_EXACT_D1_CORE8_FINDINGS_20260818.md`, `research/NG_EXHAUSTION_ENTRY_TIMING_REVIVAL_PROTOCOL_20260818.md` |
| 7 | 2026-08-19 | D0-D5 predictability, chain birth, POX-focused, full-causal V3 | `research/NG_EXHAUSTION_D1_D5_PREDICTABILITY_TIMING_GRID_20260819.json`, `research/NG_EXHAUSTION_D1_D5_CHAIN_BIRTH_PREDICTABILITY_PROTOCOL_20260819.md`, `research/NG_EXHAUSTION_D0_D5_FULL_CAUSAL_V3_LAUNCH_20260819.json` |
| 8 | 2026-08-20 | V4 geometry contract and the MBO V4 state adapter (order lifecycle, FIFO book, microstructure, legacy crosswalk) | `research/NG_EXHAUSTION_D0_D5_V4_GEOMETRIC_SELF_ADAPTATION_CONTRACT_20260820.json`, `research/ng_exhaustion_mbo_v4_state_adapter_20260820.py` |
| 9 | 2026-08-28 | the A_MEMORY recalculation: the 99-layer registry and the eighteen contract sections | `research/kalshi/frankie_boss/audits/CROSSWALK_SUNDAY_CYCLE0_FEED_33746436209_20260916.json` |

Under that reading campaigns 1-3 map onto no registry layer (the registry re-implemented the chain study onward),
so a cycle pinned to them would be accounted by calculation name, not by registry layer. The 2026-08-22/23 `step1_*`
receipts are the five-year MBO ingestion census, not a calculation group; the registry seals them
(`sealed_step1_answer`). "The original 2nd step calcs" in the chain study's vocabulary is phase 2 (campaign 5).

## Not decided here

Which reading Greg intends. The registry-group reading is applied because the required set is the registry
(Greg, 2026-09-20 21:58Z onward) and every pin must name registry layers for the per-layer accounting entry; the
campaign reading is one JSON edit away (its receipts are hashed above and in git).
