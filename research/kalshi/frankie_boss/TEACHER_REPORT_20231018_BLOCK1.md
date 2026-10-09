# TEACHER REPORT, 20231018 block 1

My own account of block 1 of the trading day 20231018, in my words: every sentence is a recorded number or a listed name of my sealed block or of the second set Frankie read beside it, and the field it came from is given in brackets.

## What I read in this block

- I read the teacher rows with cursors 0 to 1587, 1588 rows in all [blocks/1.json cursor_range, rows].
- The block covers the receive clock from 2023-10-17T22:00:00.000000Z up to (not including) 2023-10-17T22:05:00.000000Z [blocks/1.json clock_range].
- The first row I read was received at 2023-10-17T21:00:00.190837Z and the last at 2023-10-17T22:04:51.013993Z; my as_of for this block is 2023-10-17T22:04:51.013993Z [blocks/1.json first_row_clock, last_row_clock, teacher_as_of].
- 490 rows arrived out of receive order and are listed, not moved [blocks/1.json late_rows].
- I published 1588 Dipole rows of the day's instrument in this block, as sidecar bytes 12139 to 217036960 with sha256 40293ae593c91a5ef49c25f484733412feadd8168a25c4fff4f8625e1fc77544 [blocks/1.json sidecar].
- Sealed in 35.29 seconds, mode merge [blocks/1.json seal_seconds, mode].

## The pinned columns in this block

| component | PRESENT rows | sum of PRESENT values | states |
|---|---|---|---|
| extension_count_log | 627 | 88.02969217300415 | MISSING 961, PRESENT 627 |
| far_absorption_share_1024 | 627 | 17.822162670083344 | MISSING 961, PRESENT 627 |
| far_absorption_share_64 | 627 | 257.54566502571106 | MISSING 961, PRESENT 627 |
| far_front_age_log | 627 | 1648.264478652558 | MISSING 961, PRESENT 627 |
| far_identity_survival_1024 | 627 | 626.0884345173836 | MISSING 961, PRESENT 627 |
| far_identity_survival_64 | 627 | 621.2393012046814 | MISSING 961, PRESENT 627 |
| far_priority_loss_rate_1024 | 517 | 465.29348278045654 | MISSING 1071, PRESENT 517 |
| far_priority_loss_rate_64 | 397 | 299.8830498158932 | MISSING 1191, PRESENT 397 |
| far_queue_age_p90_log | 627 | 7072.980315208435 | MISSING 961, PRESENT 627 |
| far_replenish_log1p_1024 | 627 | -390.5100466310978 | MISSING 961, PRESENT 627 |
| far_replenish_log1p_64 | 627 | 330.09439769759774 | MISSING 961, PRESENT 627 |
| far_size_hhi | 627 | 6.8303890125826 | MISSING 961, PRESENT 627 |
| far_size_retention_1024 | 627 | 626.0884345173836 | MISSING 961, PRESENT 627 |
| far_size_retention_64 | 627 | 621.1653226613998 | MISSING 961, PRESENT 627 |
| pullback_ticks_last_log | 127 | 139.52376317977905 | MISSING 1461, PRESENT 127 |
| pullback_ticks_prev_log | 0 | 0.0 | MISSING 1588 |
| step_duration_groups_log | 127 | 392.5623998641968 | MISSING 1461, PRESENT 127 |
| step_ratio_log | 0 | 0.0 | MISSING 1588 |
| unresolved_age_groups_log | 627 | 1848.3154064416885 | MISSING 961, PRESENT 627 |

[blocks/1.json pinned_sums]

## The second set beside every row

- Frankie read 1588 rows of my second set for this block; each row carries every role but the counts below [second_set.json rows, carried].
  - book_columns on 1588 rows [second_set.json carried.book_columns].
  - clocks on 1588 rows [second_set.json carried.clocks].
  - clocks_absent on 1588 rows [second_set.json carried.clocks_absent].
  - coverage on 1588 rows [second_set.json carried.coverage].
  - invalidated on 1588 rows [second_set.json carried.invalidated].
  - key on 1588 rows [second_set.json carried.key].
  - match on 1588 rows [second_set.json carried.match].
  - planes on 1588 rows [second_set.json carried.planes].
  - planes_absent on 1588 rows [second_set.json carried.planes_absent].
  - planes_state on 1588 rows [second_set.json carried.planes_state].
  - state_split on 1588 rows [second_set.json carried.state_split].
- Match status of the pictures against my rows: {"matched": 1588}; 0 rows mismatched [second_set.json match_status, mismatched_rows].

### The planes, present and absent

| plane entry | rows with references | references | rows carried by the row itself | rows absent | absent reasons |
|---|---|---|---|---|---|
| aggressor_and_native_signed_flow | 923 | 2428 | 0 | 665 | no root.frames row was placed at this instant (665) |
| canonical_predecessor_bootstrap_objects | 0 | 0 | 1588 | 0 |  |
| canonical_sep_nov_2021_dbn_mbo_objects | 0 | 0 | 1588 | 0 |  |
| churn_and_queue_turnover | 922 | 922 | 0 | 666 | no root.frames row was placed at this instant (666) |
| clock_event_known_by | 0 | 0 | 1588 | 0 |  |
| clock_event_time | 0 | 0 | 1588 | 0 |  |
| clock_feature_availability | 0 | 0 | 1588 | 0 |  |
| clock_prospective_discovery_confirmation | 0 | 0 | 0 | 1588 | no native.lifecycle row was placed at this instant (1588) |
| clock_receive_time | 0 | 0 | 1588 | 0 |  |
| complete_state_reset_bootstrap_receipts | 922 | 922 | 0 | 666 | no native.member row was placed at this instant (666) |
| contract_session_roll_state | 999 | 149060 | 0 | 589 | no native.member row was placed at this instant (589) |
| depletion_and_replenishment | 905 | 17543 | 0 | 683 | no native.lifecycle row was placed at this instant (683) |
| derived_ancestry_gaps | 922 | 1406 | 0 | 666 | no native.lifecycle row was placed at this instant (666) |
| derived_d_family_geometry | 922 | 922 | 0 | 666 | no root.structures row was placed at this instant (666) |
| derived_feature_availability_timestamps | 0 | 0 | 1588 | 0 |  |
| derived_open_world_predecessor_state | 922 | 922 | 0 | 666 | no root.structures row was placed at this instant (666) |
| derived_price_flow_book_paths | 922 | 6657 | 0 | 666 | no native.member row was placed at this instant (666) |
| derived_unresolved_age_chain_trajectory | 1 | 484 | 0 | 1587 | no native.lifecycle row was placed at this instant (1587) |
| derived_v4_mechanics_fifo_features | 922 | 1250 | 0 | 666 | no native.member row was placed at this instant (666) |
| fifo_queues | 922 | 922 | 0 | 666 | no root.frames row was placed at this instant (666) |
| full_bid_ask_depth | 922 | 922 | 0 | 666 | no root.frames row was placed at this instant (666) |
| legacy_book_imbalance | 54 | 55 | 0 | 1534 | no root.prices row was placed at this instant (1534) |
| legacy_native_signed_flow | 0 | 0 | 0 | 1588 | completed-only: a post-stream aggregate (report.completed_sources), never a value in a live picture (1588) |
| legacy_per_second_roll20 | 0 | 0 | 0 | 1588 | completed-only: a post-stream aggregate (report.completed_sources), never a value in a live picture (1588) |
| legacy_price | 54 | 55 | 0 | 1534 | no root.prices row was placed at this instant (1534) |
| legacy_structure_observables | 922 | 922 | 0 | 666 | no root.structures row was placed at this instant (666) |
| mechanics_actions_by_side_and_level | 922 | 922 | 0 | 666 | no root.frames row was placed at this instant (666) |
| missingness_and_integrity_flags | 922 | 922 | 0 | 666 | no root.frames row was placed at this instant (666) |
| native_acmrtfn_messages | 0 | 0 | 1588 | 0 |  |
| october_first_source_window | 0 | 0 | 1588 | 0 |  |
| order_identity_transitions | 922 | 922 | 0 | 666 | no root.structures row was placed at this instant (666) |
| order_lifecycle_adds | 922 | 922 | 0 | 666 | no root.frames row was placed at this instant (666) |
| order_lifecycle_cancels | 922 | 922 | 0 | 666 | no root.frames row was placed at this instant (666) |
| order_lifecycle_clears | 922 | 922 | 0 | 666 | no native.member row was placed at this instant (666) |
| order_lifecycle_fills | 922 | 922 | 0 | 666 | no native.member row was placed at this instant (666) |
| order_lifecycle_modifies | 922 | 922 | 0 | 666 | no root.frames row was placed at this instant (666) |
| order_lifecycle_replaces | 922 | 922 | 0 | 666 | no root.frames row was placed at this instant (666) |
| order_lifecycle_trades | 54 | 55 | 0 | 1534 | no root.prices row was placed at this instant (1534) |
| orders_and_volume_ahead | 922 | 922 | 0 | 666 | no root.frames row was placed at this instant (666) |
| prebirth_ancestry_successor_opportunity | 1 | 484 | 0 | 1587 | no native.lifecycle row was placed at this instant (1587) |
| prebirth_negative_opportunity_cases | 1 | 1 | 0 | 1587 | no native.lifecycle row was placed at this instant (1587) |
| prebirth_predecessor_at_risk_state | 0 | 0 | 0 | 1588 | no native.lifecycle row was placed at this instant (1588) |
| prebirth_stopped_chain_false_context_controls | 1 | 1 | 0 | 1587 | no native.lifecycle row was placed at this instant (1587) |
| prebirth_unresolved_chain_extension_state | 1 | 484 | 0 | 1587 | no native.lifecycle row was placed at this instant (1587) |
| price_and_book_path | 999 | 150904 | 0 | 589 | no native.member row was placed at this instant (589) |
| price_level_and_order_counts | 922 | 922 | 0 | 666 | no root.frames row was placed at this instant (666) |
| queue_age_and_survival | 922 | 922 | 0 | 666 | no root.frames row was placed at this instant (666) |
| queue_concentration | 922 | 922 | 0 | 666 | no root.frames row was placed at this instant (666) |
| raw_source_identity_provenance_clocks_integrity | 0 | 0 | 1588 | 0 |  |
| resilience_and_recovery | 922 | 2184 | 0 | 666 | no native.lifecycle row was placed at this instant (666) |
| snapshot_bootstrap_reset_messages | 0 | 0 | 1588 | 0 |  |
| spread_and_depth_imbalance | 922 | 922 | 0 | 666 | no root.frames row was placed at this instant (666) |

[second_set.json planes]

### The clocks

- clock_event_known_by carried on 1588 rows [second_set.json clocks].
- clock_event_time carried on 1588 rows [second_set.json clocks].
- clock_feature_availability carried on 999 rows; absent: no layer update was placed at this instant on 589 rows [second_set.json clocks].
- clock_lock_time carried on 0 rows; absent: teacher_as_of (lock time does not exist before Frankie reads): not a picture element; the teacher's as_of is stamped at publication on 1588 rows [second_set.json clocks].
- clock_model_evaluation carried on 922 rows; absent: no native.member row was placed at this instant on 666 rows [second_set.json clocks].
- clock_prospective_discovery_confirmation carried on 922 rows; absent: no native.lifecycle row was placed at this instant on 666 rows [second_set.json clocks].
- clock_receive_time carried on 1588 rows [second_set.json clocks].
- My lock time on these rows is my as_of for this block (lock time does not exist before Frankie reads) [second_set.json clock_lock_time].

### The book columns

- Book read status per row: {"GROUP": 922, "NOT_F_LAST": 666} [second_set.json book_columns.status_rows].
- At the 21 anchor rows of the block (each component's first, last, minimum and maximum PRESENT row) the planes were read by their references: {"from_cache": 563, "lines_read": 546273, "re_reads": 67, "resolved": 197, "unresolved": 0} [second_set.json anchors_resolved.resolver].
- The entries the picture does not carry, with the reason, are listed whole in my header: 47 entries [second_set.json entries_not_carried].

## What I carry into the next block

- book_running: {} [blocks/1.json carried_state.book_running].
- group_labels: 923 [blocks/1.json carried_state.group_labels].
- normalizer: identity (stateless) [blocks/1.json carried_state.normalizer].
- r3_windows: the short (64-group) and long (1024-group) R3 windows of later rows reach back into this block's book groups (held by reference) [blocks/1.json carried_state.r3_windows].
- receive_clock_known_by: 1697580291013992434 [blocks/1.json carried_state.receive_clock_known_by].
- teacher_as_of: 1697580291013992434 [blocks/1.json carried_state.teacher_as_of].
- walk: the classroom carry, cutoff tracker and the row pass continuation continue on the walk (saved with its position) [blocks/1.json carried_state.walk].

## The classroom session on this block

- Status complete, mode TEACH, 1588 rows, 19 components answered; key 1a24ef3d8d20913d2215ec79ab399597664660eeef494f77119e3ed009f7e4d9 built from this block's rows [blocks/1/session.json].
- The external section: {"cutoff_ns": 1697580291013992434, "history_entries": 0, "section": "052d6fe90ba24d753b3029388105d812ea6644e307e755e0959913f310caecc7", "status": "complete"} [blocks/1/session.json external].

## What the day report adds at day end

- learner reading (SOCRATIC / VERIFY): these modes read Frankie's own walk of the whole sealed journal (frankie_box_classroom_reader.read_day); a block session in those modes is listed, not run.
- shared market context and the native entry arithmetic (K.market_context): one full ordered read of the shared market timeline to the day's last anchor picture; the block answers take the second set at the block's anchors instead.
- exhaustion/D facts (K.exhaustion_d_facts): computed from the ROOT's whole-day bedrock layers (not block-scoped data).
- the teacher's account (teacher-account.json) as a lesson input: written by the teacher's final publication from the whole day's second set.
- the brain entry <day>-cycle-00: one entry per day (R16: a second entry of the same day declines); each block's checked lesson is kept in blocks/<n>/brain-update.json for it and the entry is published once the day's classroom completes.
- Jev's material, the exchange, the meeting, the school and the day reports: per day after the last block (they read the complete teacher publication).
- My account from the receipt (FRANKIE_TEACHER_ACCOUNT_V1), discovery and correlations (frankie_box_teacher_findings) and my actions: written by my final publication from the whole day's second set and rendered in TEACHER REPORT #N.
