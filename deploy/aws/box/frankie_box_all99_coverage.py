"""The all-99 coverage list of one stage, per day: every registry entry, its role, and whether it ARRIVED at what the
stage actually computed on (Greg, 2026-10-07: "make sure the 99 layers are combined for Frankie FIRST").

The retained 99-entry crosswalk (research/kalshi/frankie_boss/audits/CROSSWALK_SUNDAY_CYCLE0_FEED_33746436209_20260916.json,
schema FRANKIE_NATIVE_RAW_MBO_LAYER_CROSSWALK_V1, registry sha256 239a1480...) groups 6 canonical raw, 49 calculation/clock,
23 control/knowledge/arm, 9 sealed answers, 2 provisional shadows and 10 append-only outputs. The roles are not
interchangeable numeric layers: a sealed answer is withheld by role, a shadow is disabled by policy, an output is produced
or pending; only the raw and calculation/clock entries are market evidence that can arrive at a computation.

For the scientific stages (the scientific teacher's evidence, carried claims, today's findings, the survivor/candidate
update, the successor corrections) "what the stage computes on" is the day's completed search: its coupling rows. The
search MANIFEST carries, per day, the plane receipt (frankie_box_experiment_search.plane_summary: one row per calculation/
clock entry, the source it is read through, mapped / mapped_partial / clock / listed_missing / not_produced / ...) and
every source receipt (placed_series, placed_cells, exclusions). This module turns that, plus the operation's own tests
(which rows the claims actually read), into one list per day:

  arrived            the entry's source is placed in the search AND at least one test of this operation read a row of it
  thin               placed but partial (the search names what remains), or placed and no claim of this operation named a
                     series of it, or a knowledge entry reached only through a projection (the historical crosswalk)
  absent             not in this export / listed missing / not produced (the native pass did not complete, or an older saved
                     legacy plan ran it off; every NEW run has it ON) / built but not called; the reason
                     is the search's own; the day stays, the picture is thinner (missing-coverage rule)
  disabled           the two provisional shadows (SHADOW_DISABLED by the existing policy; never activated here)
  withheld_by_role   the nine sealed answers (R09/R10: no teacher reads an answer key or a sealed target)
  produced / pending the ten append-only outputs, by whether THIS stage wrote them (with the pin) or another owner does

Nothing is inferred from a file read: a plane counts as arrived only when a test row of this operation carries a series
the search placed from that plane's source. The embedded 99 identities are checked against the crosswalk file when the
checkout carries it (bytes bound by sha256); a difference is listed as an integrity failure and never relabelled.
Code only; no model call; no new scientific mapping (the plane-to-source reading is the search's own table).

THE ONE REGISTRY AND THE ONE SHARED FIELD (Greg, 2026-10-07: the 99 layers combined for Frankie FIRST; four copies of
the same 99 entries drifted). This module is the single source of the 99 entries; every piece imports its entry list
from here and keeps its own routes, consumers and dispositions:

  REGISTRY / GROUP_ROLES / CROSSWALK_PATH / CROSSWALK_SHA256 / CROSSWALK_BYTES / REGISTRY_SHA256   the identities
  entries(code_root=None)        the 99 as [{entry, group, policy, role, historical_delivery_status}], crosswalk order
  registry(code_root=None)       the same plus the crosswalk file pin and every integrity difference (never raises)
  field(piece, day, rows, ...)   builds and validates the shared per-piece field FRANKIE_ALL99_COVERAGE_V1:
                                 entries[] (exactly 99, registry order) each {entry, group, role, disposition, reason,
                                 consumer, piece_disposition} plus the piece's own extra keys; `disposition` is one word
                                 of VOCABULARY (LEGACY_WORDS maps every piece's old word; FIXED_WORDS settles the sealed,
                                 shadow, Memory A, A-clean and arm-profile entries); integrity[] lists every unknown name,
                                 duplicate, missing entry and group contradiction (an integrity finding, visible, never
                                 relabelled: a missing entry is listed as 'unrouted', it is not dropped and not filled in)
  derive_field(base, piece, updates, ...)  a piece's field from another piece's field (the core's) with its own rows
  validate(doc)                  the same checks on a field read back from a receipt (returns the findings)

`role` in the field is the registry's (GROUP_ROLES; causal_clocks = 'clock'); a piece's own role and word stay in its
own block and as piece_role / piece_disposition. MARKET_CARRIERS / NATIVE_SERIES settle which picture element and which
native ledger field or section carries each market entry; the shared reader and the search use them.
"""
import hashlib
import json
from pathlib import Path

SCHEMA = 'FRANKIE_ALL99_COVERAGE_V1'
CROSSWALK_PATH = 'research/kalshi/frankie_boss/audits/CROSSWALK_SUNDAY_CYCLE0_FEED_33746436209_20260916.json'
CROSSWALK_SHA256 = 'ece9c624d9969166e81876e7705d0c47054e46b6aa3e5485803a218648184de9'
CROSSWALK_BYTES = 112545
CROSSWALK_SCHEMA = 'FRANKIE_NATIVE_RAW_MBO_LAYER_CROSSWALK_V1'
REGISTRY_SHA256 = '239a14808850d9cc9ba589165e4263c0e3f11a0c574052f39bfaa133adf296b1'
PINNED_IN = 'research/kalshi/frankie_boss/knowledge/CYCLE_CALCULATION_PINS.json'
DISPOSITIONS = ('arrived', 'thin', 'absent', 'not_read_by_this_piece', 'control', 'not_applicable', 'retired', 'disabled',
                'withheld_by_role', 'produced', 'pending')
RULE = ('every registry entry listed with its role and a reason; arrived means a test row of this operation read a series '
        'the search placed from the entry\'s source; absent/thin never rejects the day (missing-coverage rule); sealed '
        'answers stay withheld by role; shadows stay disabled; an integrity difference is listed, never relabelled')

# (layer_id, group_id, policy): the 99 identities of the retained crosswalk, in its order.
REGISTRY = (
    ('controlling_rt_mission', 'binding_common_controls', 'STATIC_REQUIRED_INPUT'),
    ('native_calculation_contract', 'binding_common_controls', 'STATIC_REQUIRED_INPUT'),
    ('anchored_knowledge_manifest', 'binding_common_controls', 'STATIC_REQUIRED_INPUT'),
    ('selected_same_arm_profile', 'binding_common_controls', 'STATIC_REQUIRED_INPUT'),
    ('a_clean_promoted_positive_capsule', 'a_clean_overlay', 'ARM_REQUIRED_INPUT'),
    ('a_memory_promoted_positive_capsule', 'a_memory_overlay', 'ARM_REQUIRED_INPUT'),
    ('a_memory_prior_lessons_package', 'a_memory_overlay', 'ARM_REQUIRED_INPUT'),
    ('a_memory_prior_package_proof', 'a_memory_overlay', 'ARM_REQUIRED_INPUT'),
    ('authoritative_s135_construction', 'current_brain_runtime', 'STATIC_REQUIRED_INPUT'),
    ('complete_s105_9_brain', 'current_brain_runtime', 'STATIC_REQUIRED_INPUT'),
    ('doctrine_reasoning_play_index_evidence', 'current_brain_runtime', 'STATIC_REQUIRED_INPUT'),
    ('lawful_prior_session_carry', 'current_brain_runtime', 'STATIC_REQUIRED_INPUT'),
    ('october_outcome_wall_enforcement', 'current_brain_runtime', 'STATIC_REQUIRED_INPUT'),
    ('learned_d_structures_and_families', 'frozen_learned_structure', 'STATIC_REQUIRED_INPUT'),
    ('learned_dipoles_and_geometry', 'frozen_learned_structure', 'STATIC_REQUIRED_INPUT'),
    ('learned_pair_triplet_recurrence', 'frozen_learned_structure', 'STATIC_REQUIRED_INPUT'),
    ('learned_chains_extensions_reappearances_ancestry', 'frozen_learned_structure', 'STATIC_REQUIRED_INPUT'),
    ('phase1_discoveries_structural_falsifiers', 'frozen_learned_structure', 'STATIC_REQUIRED_INPUT'),
    ('phase2_findings_modules_timing_pox_negatives', 'frozen_learned_structure', 'STATIC_REQUIRED_INPUT'),
    ('predecessor_ancestry_unresolved_chain_state', 'frozen_learned_structure', 'STATIC_REQUIRED_INPUT'),
    ('historical_timing_lifespan_context', 'frozen_learned_structure', 'STATIC_REQUIRED_INPUT'),
    ('learned_structure_proposal_index_material', 'frozen_learned_structure', 'STATIC_REQUIRED_INPUT'),
    ('extra_agent_corrected_information_and_gap_diagnoses', 'corrected_extra_agent_carryforward', 'STATIC_REQUIRED_INPUT'),
    ('canonical_sep_nov_2021_dbn_mbo_objects', 'canonical_raw_dbn_mbo', 'CAUSAL_STREAM_REQUIRED'),
    ('october_first_source_window', 'canonical_raw_dbn_mbo', 'CAUSAL_STREAM_REQUIRED'),
    ('canonical_predecessor_bootstrap_objects', 'canonical_raw_dbn_mbo', 'CAUSAL_STREAM_REQUIRED'),
    ('native_acmrtfn_messages', 'canonical_raw_dbn_mbo', 'CAUSAL_STREAM_REQUIRED'),
    ('snapshot_bootstrap_reset_messages', 'canonical_raw_dbn_mbo', 'CAUSAL_STREAM_REQUIRED'),
    ('raw_source_identity_provenance_clocks_integrity', 'canonical_raw_dbn_mbo', 'CAUSAL_STREAM_REQUIRED'),
    ('order_lifecycle_adds', 'order_lifecycle', 'CAUSAL_STREAM_REQUIRED'),
    ('order_lifecycle_cancels', 'order_lifecycle', 'CAUSAL_STREAM_REQUIRED'),
    ('order_lifecycle_modifies', 'order_lifecycle', 'CAUSAL_STREAM_REQUIRED'),
    ('order_lifecycle_replaces', 'order_lifecycle', 'CAUSAL_STREAM_REQUIRED'),
    ('order_lifecycle_trades', 'order_lifecycle', 'CAUSAL_STREAM_REQUIRED'),
    ('order_lifecycle_fills', 'order_lifecycle', 'CAUSAL_STREAM_REQUIRED'),
    ('order_lifecycle_clears', 'order_lifecycle', 'CAUSAL_STREAM_REQUIRED'),
    ('order_identity_transitions', 'order_lifecycle', 'CAUSAL_STREAM_REQUIRED'),
    ('contract_session_roll_state', 'order_lifecycle', 'CAUSAL_STREAM_REQUIRED'),
    ('full_bid_ask_depth', 'full_book_fifo_queue', 'CAUSAL_STREAM_REQUIRED'),
    ('price_level_and_order_counts', 'full_book_fifo_queue', 'CAUSAL_STREAM_REQUIRED'),
    ('fifo_queues', 'full_book_fifo_queue', 'CAUSAL_STREAM_REQUIRED'),
    ('queue_age_and_survival', 'full_book_fifo_queue', 'CAUSAL_STREAM_REQUIRED'),
    ('queue_concentration', 'full_book_fifo_queue', 'CAUSAL_STREAM_REQUIRED'),
    ('orders_and_volume_ahead', 'full_book_fifo_queue', 'CAUSAL_STREAM_REQUIRED'),
    ('spread_and_depth_imbalance', 'full_book_fifo_queue', 'CAUSAL_STREAM_REQUIRED'),
    ('complete_state_reset_bootstrap_receipts', 'full_book_fifo_queue', 'CAUSAL_STREAM_REQUIRED'),
    ('mechanics_actions_by_side_and_level', 'microstructure_mechanics', 'CAUSAL_STREAM_REQUIRED'),
    ('aggressor_and_native_signed_flow', 'microstructure_mechanics', 'CAUSAL_STREAM_REQUIRED'),
    ('depletion_and_replenishment', 'microstructure_mechanics', 'CAUSAL_STREAM_REQUIRED'),
    ('resilience_and_recovery', 'microstructure_mechanics', 'CAUSAL_STREAM_REQUIRED'),
    ('churn_and_queue_turnover', 'microstructure_mechanics', 'CAUSAL_STREAM_REQUIRED'),
    ('price_and_book_path', 'microstructure_mechanics', 'CAUSAL_STREAM_REQUIRED'),
    ('missingness_and_integrity_flags', 'microstructure_mechanics', 'CAUSAL_STREAM_REQUIRED'),
    ('legacy_price', 'legacy_observable_crosswalk', 'CAUSAL_STREAM_REQUIRED'),
    ('legacy_native_signed_flow', 'legacy_observable_crosswalk', 'CAUSAL_STREAM_REQUIRED'),
    ('legacy_per_second_roll20', 'legacy_observable_crosswalk', 'CAUSAL_STREAM_REQUIRED'),
    ('legacy_book_imbalance', 'legacy_observable_crosswalk', 'CAUSAL_STREAM_REQUIRED'),
    ('legacy_structure_observables', 'legacy_observable_crosswalk', 'CAUSAL_STREAM_REQUIRED'),
    ('derived_roll20_and_dipole_state', 'derived_geometry', 'CAUSAL_STREAM_REQUIRED'),
    ('derived_d_family_geometry', 'derived_geometry', 'CAUSAL_STREAM_REQUIRED'),
    ('derived_open_world_predecessor_state', 'derived_geometry', 'CAUSAL_STREAM_REQUIRED'),
    ('derived_ancestry_gaps', 'derived_geometry', 'CAUSAL_STREAM_REQUIRED'),
    ('derived_unresolved_age_chain_trajectory', 'derived_geometry', 'CAUSAL_STREAM_REQUIRED'),
    ('derived_price_flow_book_paths', 'derived_geometry', 'CAUSAL_STREAM_REQUIRED'),
    ('derived_v4_mechanics_fifo_features', 'derived_geometry', 'CAUSAL_STREAM_REQUIRED'),
    ('derived_feature_availability_timestamps', 'derived_geometry', 'CAUSAL_STREAM_REQUIRED'),
    ('prebirth_predecessor_at_risk_state', 'prebirth_opportunity', 'CAUSAL_STREAM_REQUIRED'),
    ('prebirth_unresolved_chain_extension_state', 'prebirth_opportunity', 'CAUSAL_STREAM_REQUIRED'),
    ('prebirth_ancestry_successor_opportunity', 'prebirth_opportunity', 'CAUSAL_STREAM_REQUIRED'),
    ('prebirth_stopped_chain_false_context_controls', 'prebirth_opportunity', 'CAUSAL_STREAM_REQUIRED'),
    ('prebirth_negative_opportunity_cases', 'prebirth_opportunity', 'CAUSAL_STREAM_REQUIRED'),
    ('clock_event_time', 'causal_clocks', 'CAUSAL_STREAM_REQUIRED'),
    ('clock_receive_time', 'causal_clocks', 'CAUSAL_STREAM_REQUIRED'),
    ('clock_event_known_by', 'causal_clocks', 'CAUSAL_STREAM_REQUIRED'),
    ('clock_feature_availability', 'causal_clocks', 'CAUSAL_STREAM_REQUIRED'),
    ('clock_prospective_discovery_confirmation', 'causal_clocks', 'CAUSAL_STREAM_REQUIRED'),
    ('clock_model_evaluation', 'causal_clocks', 'CAUSAL_STREAM_REQUIRED'),
    ('clock_lock_time', 'causal_clocks', 'CAUSAL_STREAM_REQUIRED'),
    ('later_outcome_reveal', 'sealed_target_timing', 'SEALED_FOR_A_SCOPE'),
    ('target_ground_truth_onset_time', 'sealed_target_timing', 'SEALED_FOR_A_SCOPE'),
    ('s137_cognitive_shadow_runtime', 'provisional_shadow', 'PROVISIONAL_SHADOW'),
    ('hipporag_associative_retrieval', 'provisional_shadow', 'PROVISIONAL_SHADOW'),
    ('step1_existing_october_seconds', 'sealed_step1_answer', 'SEALED_FOR_A_SCOPE'),
    ('step1_populations', 'sealed_step1_answer', 'SEALED_FOR_A_SCOPE'),
    ('step1_crosswalks', 'sealed_step1_answer', 'SEALED_FOR_A_SCOPE'),
    ('step1_target_membership_receipts', 'sealed_step1_answer', 'SEALED_FOR_A_SCOPE'),
    ('step1_labels_and_classifications', 'sealed_step1_answer', 'SEALED_FOR_A_SCOPE'),
    ('step1_result_prefixes', 'sealed_step1_answer', 'SEALED_FOR_A_SCOPE'),
    ('step1_reconciliation_outputs', 'sealed_step1_answer', 'SEALED_FOR_A_SCOPE'),
    ('output_state_and_state_delta_movie', 'append_only_outputs', 'APPEND_ONLY_OUTPUT'),
    ('output_frankie_reasoning_movie', 'append_only_outputs', 'APPEND_ONLY_OUTPUT'),
    ('output_probability_movie', 'append_only_outputs', 'APPEND_ONLY_OUTPUT'),
    ('output_candidate_discoveries', 'append_only_outputs', 'APPEND_ONLY_OUTPUT'),
    ('output_first_locks_and_no_locks', 'append_only_outputs', 'APPEND_ONLY_OUTPUT'),
    ('output_negative_sparse_inconclusive_ledger', 'append_only_outputs', 'APPEND_ONLY_OUTPUT'),
    ('output_knowledge_retrieval_receipts', 'append_only_outputs', 'APPEND_ONLY_OUTPUT'),
    ('output_provider_invocation_response_receipts', 'append_only_outputs', 'APPEND_ONLY_OUTPUT'),
    ('output_answer_wall_access_receipts', 'append_only_outputs', 'APPEND_ONLY_OUTPUT'),
    ('output_source_state_manifest_code_model_run_hashes', 'append_only_outputs', 'APPEND_ONLY_OUTPUT'),
)
GROUP_ROLES = {
    'canonical_raw_dbn_mbo': 'raw', 'order_lifecycle': 'calculation', 'full_book_fifo_queue': 'calculation',
    'microstructure_mechanics': 'calculation', 'legacy_observable_crosswalk': 'calculation', 'derived_geometry': 'calculation',
    'prebirth_opportunity': 'calculation', 'causal_clocks': 'clock',
    'binding_common_controls': 'control', 'a_clean_overlay': 'arm', 'a_memory_overlay': 'arm',
    'current_brain_runtime': 'knowledge', 'frozen_learned_structure': 'knowledge', 'corrected_extra_agent_carryforward': 'knowledge',
    'sealed_target_timing': 'sealed_answer', 'sealed_step1_answer': 'sealed_answer', 'provisional_shadow': 'shadow',
    'append_only_outputs': 'output',
}
# The six canonical raw entries, read through the search's plane rows (the names of frankie_box_experiment_search.PLANE_COVERAGE
# beyond the registry names) and the shared-market source receipt; each names what it is read through.
RAW_ROUTES = {
    'canonical_sep_nov_2021_dbn_mbo_objects': (('sealed journal INPUT entries (every record, every field)',),
                                               'the sealed ingest of the day (journal INPUT entries) as the search placed them'),
    'october_first_source_window': (('sealed journal INPUT entries (every record, every field)',),
                                    'the day\'s own sealed source window (the trading day); the search is one day'),
    'canonical_predecessor_bootstrap_objects': (('complete_state_reset_bootstrap_receipts',),
                                                'the opening book/tail partition belongs to the ingest; the search carries the record '
                                                'snapshot flag (events.last.is_snapshot) only'),
    'native_acmrtfn_messages': (('sealed journal INPUT entries (every record, every field)', 'mechanics_actions_by_side_and_level'),
                                'every A/C/M/R/T/F/N message reaches the search as per-group action counts and the closing record'),
    'snapshot_bootstrap_reset_messages': (('complete_state_reset_bootstrap_receipts', 'order_lifecycle_clears'),
                                          'R/snapshot records through events.R_* and the snapshot flag'),
    'raw_source_identity_provenance_clocks_integrity': (('clock_event_time', 'clock_receive_time', 'missingness_and_integrity_flags'),
                                                        'identities and clocks are listed (EVENT_IDENTITY_FIELDS), the receive clock is the '
                                                        'axis, integrity counters are frames.integrity.*; identities are never searched'),
}
# The 23 control/knowledge/arm entries: how each reaches a scientific stage, by role (KNOWLEDGE_CONSUMER_COVERAGE_20261006).
KNOWLEDGE_ROUTES = {
    'controlling_rt_mission': ('policy', 'historical control/manifest input; the experiment directive and R06/R15/R17 govern; not imported as current authority'),
    'native_calculation_contract': ('policy', 'historical control/manifest input; the pinned calculation groups (CYCLE_CALCULATION_PINS) govern the ROOT, not this stage'),
    'anchored_knowledge_manifest': ('policy', 'historical control/manifest input; the brain entries selected at this boundary are the manifest this stage reads'),
    'selected_same_arm_profile': ('policy', 'historical arm policy; the 30-day plan selects no arm comparison'),
    'a_clean_promoted_positive_capsule': ('policy', 'A-clean arm overlay; the plan selects no A-clean comparison arm (NOT_APPLICABLE in the crosswalk)'),
    'a_memory_promoted_positive_capsule': ('memory_a', 'Memory A is retired (Greg, 2026-09-27); H06-H08 stay historical/not_bound in the historical claims'),
    'a_memory_prior_lessons_package': ('memory_a', 'Memory A is retired; H06-H08 stay historical/not_bound'),
    'a_memory_prior_package_proof': ('memory_a', 'Memory A is retired; H06-H08 stay historical/not_bound (DEGENERATE_PROOF_SAME_AS_SUBJECT in the crosswalk)'),
    'authoritative_s135_construction': ('historical', 'ng_brain statements reach the test only through the historical claims crosswalk (H03-H05)'),
    'complete_s105_9_brain': ('historical', 'ng_brain statements reach the test only through the historical claims crosswalk'),
    'doctrine_reasoning_play_index_evidence': ('historical', 'play-index statements are in the historical catalog; the crosswalk puts 10 of them in testable form'),
    'lawful_prior_session_carry': ('brain', 'every completed brain entry and school file selected at this boundary (learner_knowledge); Frankie\'s private answers excluded (R09)'),
    'october_outcome_wall_enforcement': ('policy', 'historical raw-source/answer policy; amended R15 governs; the causal walls are the search\'s leakage gate'),
    'learned_d_structures_and_families': ('historical', 'frozen learned structure: in the Dipole catalog; reaches the test through the historical claims crosswalk only'),
    'learned_dipoles_and_geometry': ('historical', 'frozen learned structure: H01/H02 (divergence/exhaustion) through the historical claims crosswalk'),
    'learned_pair_triplet_recurrence': ('historical', 'frozen learned structure: in the Dipole catalog; no crosswalk entry puts it in testable form'),
    'learned_chains_extensions_reappearances_ancestry': ('historical', 'frozen learned structure: in the Dipole catalog; no crosswalk entry puts it in testable form'),
    'phase1_discoveries_structural_falsifiers': ('historical', 'frozen learned structure: in the Dipole catalog; no crosswalk entry puts it in testable form'),
    'phase2_findings_modules_timing_pox_negatives': ('historical', 'frozen learned structure: in the Dipole catalog; no crosswalk entry puts it in testable form'),
    'predecessor_ancestry_unresolved_chain_state': ('historical', 'frozen learned structure: in the Dipole catalog; the teacher\'s chain columns carry its day form'),
    'historical_timing_lifespan_context': ('historical', 'frozen learned structure: in the Dipole catalog; no crosswalk entry puts it in testable form'),
    'learned_structure_proposal_index_material': ('historical', 'frozen learned structure: in the Dipole catalog; no crosswalk entry puts it in testable form'),
    'extra_agent_corrected_information_and_gap_diagnoses': ('historical', 'corrected findings are in the catalog as source material; no structured adapter in this stage'),
}
# The ten append-only outputs: which this family of stages writes (the lessons, candidates and survivors) and who owns the rest.
OUTPUT_ROUTES = {
    'output_candidate_discoveries': 'the search candidates (FRANKIE_SEARCH_FINDINGS_V1), the lessons results and the survivor/candidate update',
    'output_negative_sparse_inconclusive_ledger': 'shown_otherwise / unresolved / counts_only / untested / cannot_test_yet in every lessons result and the survivor update',
    'output_knowledge_retrieval_receipts': 'the frozen operation inputs (FRANKIE_STANDALONE_TEACHER_INPUTS_V1 / FRANKIE_TEACHER_KNOWLEDGE_INPUTS_V1 / FRANKIE_SURVIVOR_UPDATE_INPUTS_V1)',
    'output_source_state_manifest_code_model_run_hashes': 'reader sha256 pins, search manifest sha256 and claims sha256 in every lessons file and receipt',
    'output_state_and_state_delta_movie': 'the ROOT/native producers (frankie_box_experiment_root), not this stage',
    'output_frankie_reasoning_movie': 'Frankie\'s classroom ledgers (frankie_box_classroom_code), private (R09); not this stage',
    'output_probability_movie': 'the native/principal session (frankie_box_boss_session), not this stage',
    'output_first_locks_and_no_locks': 'the native lock clock (clock_lock_time, host), not on the experiment path',
    'output_provider_invocation_response_receipts': 'the Granite meeting runner (frankie_box_granite_meeting), not this stage (no model call here)',
    'output_answer_wall_access_receipts': 'the classroom/exchange answer walls (frankie_box_experiment_exchange), not this stage',
}
PLANE_STATUS = {         # the search's plane receipt words -> this list's disposition and the reason family
    'mapped': ('arrived', 'placed in the search'),
    'mapped_partial': ('thin', 'placed in the search, partially (the search names what remains)'),
    'clock': ('arrived', 'a clock: places the series / gates leakage; never searched as a series'),
    'read_without_channels': ('thin', 'source read; no series or cell placed from it'),
    'listed_missing': ('absent', 'the source is listed missing by the export'),
    'not_in_this_export': ('absent', 'the source is not in this export'),
    'not_produced': ('absent', 'not produced on this ROOT (the native pass did not complete, or an older saved legacy plan '
                             'ran it off; every NEW run has it ON) or a host clock'),
    'built_not_called': ('absent', 'an implementation exists and nothing on the experiment path calls it'),
    'produced_not_carried': ('absent', 'produced at every close and not spooled; no file this search reads carries it'),
    'computed_not_retained': ('thin', 'computed by the pinned teacher; only a projection is retained'),
    'not_requested': ('absent', 'not requested by the search configuration'),
    'native_evidence_present_layer_mapping_open': ('thin', 'exact native rows present; the registry-layer reconciliation is open'),
    'retained_not_searched': ('thin', 'retained by the search and not searched'),
    'native_carrier_without_rows': ('thin', 'native ledgers read; no series of this entry\'s own native carriers placed on '
                                            'this day (the search lists the native dispositions of its sections)'),
}

# ---------------------------------------------------------------- the settled registry (review 2026-10-07, B4 / table)
# ONE disposition vocabulary for the shared field. Every piece keeps its own word as `piece_disposition`; the field's
# `disposition` is one of these, through LEGACY_WORDS (a row may name `canonical` itself where its word is ambiguous).
VOCABULARY = {
    'arrived': 'the entry\'s own evidence reached this piece\'s computation, consumer or (for the reader) its yielded pictures',
    'exposed': 'present in what this piece received; not read by its computation (an exposure is not a use)',
    'thin': 'reached in part: a partial form, a thinner carrier, or present without its own series being read',
    'absent': 'missing coverage on this day; the instant and the day stay (missing-coverage rule)',
    'unknown': 'the piece did not record whether it read this entry (never counted as arrived)',
    'completed_only': 'a post-stream aggregate without contributing-cursor provenance; never a live value',
    'control': 'a binding control delivered and applied by the orchestrator/piece; not market evidence',
    'not_read_by_this_piece': 'not an input of this piece by role (the analogue consumer, if any, is named)',
    'withheld_by_role': 'a sealed answer/target: withheld by role (R09/R10), never missing',
    'disabled': 'a provisional shadow disabled by the existing policy; never activated',
    'retired': 'Memory A: retired by Greg (2026-09-27); H06-H08 historical / not_bound',
    'not_applicable': 'NOT_APPLICABLE in the crosswalk (the A-clean overlay; not Memory A)',
    'produced': 'an append-only output this piece wrote (or its analogue), pinned',
    'output_not_written_here': 'an append-only output owned by another stage, or not written by this operation (yet)',
    'unrouted': 'the piece supplied no row: an integrity finding, listed, never filled in',
    'integrity_failure': 'the carrier\'s evidence could not be verified (altered pinned bytes, contradictory identities): '
                         'a separate visible failure, never missing coverage and never a measurement',
}
DISPOSITIONS_V1 = tuple(VOCABULARY)
# Each piece's old words -> the one vocabulary (classroom 14, adviser ~15, ROOT admission 9, scientific 7, core, teacher).
LEGACY_WORDS = {
    'arrived': 'arrived', 'arrived_no_event': 'arrived', 'arrived_at_consumer': 'arrived', 'admitted': 'arrived',
    'operand': 'arrived', 'computed_here': 'arrived', 'knowledge_consumer': 'arrived', 'stamped': 'arrived',
    'enforced_by_rule': 'arrived', 'yielded': 'arrived', 'yielded_no_rows': 'arrived', 'searched': 'arrived',
    'exposed_not_used': 'exposed', 'carrier_present': 'exposed',
    'thin': 'thin', 'arrived_partial': 'thin',
    'absent': 'absent',
    'consumer_not_reported': 'unknown', 'not_reported_by_this_piece': 'unknown',
    'completed_only': 'completed_only',
    'control_of_orchestrator': 'control', 'control': 'control',
    'not_read_by_this_piece': 'not_read_by_this_piece', 'not_loaded_by_this_piece': 'not_read_by_this_piece',
    'not_on_experiment_path': 'not_read_by_this_piece', 'teacher_seat': 'not_read_by_this_piece',
    'not_a_core_layer': 'not_read_by_this_piece', 'knowledge': 'not_read_by_this_piece',
    'withheld_by_role': 'withheld_by_role', 'withheld_by_rule': 'withheld_by_role', 'sealed': 'withheld_by_role',
    'disabled': 'disabled', 'retired': 'retired', 'historical_not_bound': 'retired', 'not_applicable': 'not_applicable',
    'produced': 'produced', 'output_analogue': 'produced',
    'pending': 'output_not_written_here', 'output_not_produced_here': 'output_not_written_here',
    'append_only_output': 'output_not_written_here', 'output': 'output_not_written_here',
    'unmapped': 'unrouted', 'unrouted': 'unrouted',
    'integrity': 'integrity_failure', 'integrity_failure': 'integrity_failure',
    'stamped_at_boundary': 'arrived', 'stamped_not_committed': 'thin', 'discovery_only': 'thin',
    'stamped_from_model_calls': 'arrived', 'no_model_call_this_day': 'absent',
}
# The coarse class of each shared word (kept for readers that group words, e.g. frankie_box_experiment_day_reports
# reach_of): CLASS_OF maps every shared word AND every legacy word to its class; a field entry carries `class` too.
WORD_CLASS = {'arrived': 'arrived', 'exposed': 'exposed', 'thin': 'thin', 'absent': 'absent', 'unknown': 'unknown',
              'completed_only': 'completed_only', 'control': 'not_this_piece', 'not_read_by_this_piece': 'not_this_piece',
              'withheld_by_role': 'withheld', 'disabled': 'disabled', 'retired': 'retired', 'not_applicable': 'not_this_piece',
              'produced': 'output', 'output_not_written_here': 'output', 'unrouted': 'unmapped',
              'integrity_failure': 'integrity'}
CLASS_OF = dict({word: WORD_CLASS[canon] for word, canon in LEGACY_WORDS.items()}, **WORD_CLASS)
# Entries whose word is settled by the registry itself, whatever the piece: the 9 sealed answers, the 2 shadows, the 3
# Memory A entries, the A-clean overlay (NOT_APPLICABLE, not Memory A) and selected_same_arm_profile (a DELIVERED
# binding control; never 'retired'). A piece word that differs is corrected in the field and named in `listed`.
FIXED_WORDS = dict(
    [(layer, 'withheld_by_role') for layer, group, _ in REGISTRY if group in ('sealed_target_timing', 'sealed_step1_answer')]
    + [(layer, 'disabled') for layer, group, _ in REGISTRY if group == 'provisional_shadow']
    + [(layer, 'retired') for layer, group, _ in REGISTRY if group == 'a_memory_overlay']
    + [('a_clean_promoted_positive_capsule', 'not_applicable'), ('selected_same_arm_profile', 'control')])
# The settled role of causal_clocks is 'clock' (GROUP_ROLES); the current brain entries (s135 construction, s105.9 brain,
# play index) are 'not_read_by_this_piece' unless a piece reads their content (the scientific stages reach them only as
# historical claims: 'thin'); a truthy knowledge load of another kind never makes them arrive.
CURRENT_BRAIN = ('authoritative_s135_construction', 'complete_s105_9_brain', 'doctrine_reasoning_play_index_evidence')

# The settled per-entry market carriers (the classroom and adviser disagreed on fills, identity transitions, the
# session/roll state, mechanics, signed flow, roll20/dipole and three clocks). entry -> (carrier, thinner carrier or
# None). The shared reader (frankie_box_market_timeline) yields exactly these; pieces route through them.
CARRIER_ELEMENTS = {
    'input': 'picture.original_input / original_outcomes / original_applied / source_status, at.source_member_index / '
             'session_id, invalidated_state (reset / source_scope_changed)',
    'clock': 'picture.at: ts_event_ns, ts_recv_ns, raw_event_clock, raw_receive_clock, publication_frontier_ns',
    'availability': 'known_at_ns and availability_basis on every update',
    'opening': 'picture.opening_state and report.opening_state (the adapter state the ROOT legacy pass opened on)',
    'root.frames': 'updates / last_observed_state rows of source root.frames (book, FIFO, activity, integrity at each group close)',
    'root.prices': 'updates / last_observed_state rows of source root.prices (V2 provenance rows)',
    'root.structures': 'updates rows of source root.structures (describe_structure at each group close)',
    'native.member': 'updates / last_observed_state rows of source native.member (GROUP_CLOSE emissions)',
    'native.lifecycle': 'updates rows of source native.lifecycle (GROUP_CLOSE emissions; FINALIZE is post-stream only)',
    'completed': 'report.completed_sources: post-stream aggregate metadata; no value is yielded into any picture',
    'external': 'updates / published_state rows of source external.<table> (the day file; outside the 99-entry registry)',
}
MARKET_CARRIERS = {
    'canonical_sep_nov_2021_dbn_mbo_objects': ('input', None), 'october_first_source_window': ('input', None),
    'native_acmrtfn_messages': ('input', None), 'snapshot_bootstrap_reset_messages': ('input', None),
    'raw_source_identity_provenance_clocks_integrity': ('input', None),
    'canonical_predecessor_bootstrap_objects': ('opening', None),
    'order_lifecycle_adds': ('root.frames', 'input'), 'order_lifecycle_cancels': ('root.frames', 'input'),
    'order_lifecycle_modifies': ('root.frames', 'input'), 'order_lifecycle_replaces': ('root.frames', 'input'),
    'order_lifecycle_trades': ('root.prices', 'input'), 'order_lifecycle_fills': ('native.member', 'root.frames'),
    'order_lifecycle_clears': ('native.member', 'root.frames'), 'order_identity_transitions': ('root.structures', None),
    'contract_session_roll_state': ('native.member', 'input'),
    'full_bid_ask_depth': ('root.frames', None), 'price_level_and_order_counts': ('root.frames', None),
    'fifo_queues': ('root.frames', None), 'queue_age_and_survival': ('root.frames', None),
    'queue_concentration': ('root.frames', None), 'orders_and_volume_ahead': ('root.frames', None),
    'spread_and_depth_imbalance': ('root.frames', None),
    'complete_state_reset_bootstrap_receipts': ('native.member', 'root.frames'),
    'mechanics_actions_by_side_and_level': ('root.frames', None), 'aggressor_and_native_signed_flow': ('root.frames', None),
    'depletion_and_replenishment': ('native.lifecycle', 'root.frames'),
    'resilience_and_recovery': ('native.lifecycle', 'root.frames'),
    'churn_and_queue_turnover': ('root.frames', None), 'price_and_book_path': ('native.member', 'root.prices'),
    'missingness_and_integrity_flags': ('root.frames', None),
    'legacy_price': ('root.prices', None), 'legacy_native_signed_flow': ('completed', None),
    'legacy_per_second_roll20': ('completed', None), 'legacy_book_imbalance': ('root.prices', None),
    'legacy_structure_observables': ('root.structures', None),
    'derived_d_family_geometry': ('root.structures', None), 'derived_open_world_predecessor_state': ('root.structures', None),
    'derived_ancestry_gaps': ('native.lifecycle', None), 'derived_unresolved_age_chain_trajectory': ('native.lifecycle', None),
    'derived_price_flow_book_paths': ('native.member', 'root.prices'),
    'derived_v4_mechanics_fifo_features': ('native.member', 'root.frames'),
    'derived_feature_availability_timestamps': ('availability', None),
    'prebirth_predecessor_at_risk_state': ('native.lifecycle', None),
    'prebirth_unresolved_chain_extension_state': ('native.lifecycle', None),
    'prebirth_ancestry_successor_opportunity': ('native.lifecycle', None),
    'prebirth_stopped_chain_false_context_controls': ('native.lifecycle', None),
    'prebirth_negative_opportunity_cases': ('native.lifecycle', None),
    'clock_event_time': ('clock', None), 'clock_receive_time': ('clock', None), 'clock_event_known_by': ('clock', None),
    'clock_feature_availability': ('availability', None),
    'clock_prospective_discovery_confirmation': ('native.lifecycle', None),
}
# The 18 native-only entries (Greg, 2026-10-07: they reach Frankie and BOTH teachers). Their own carriers inside the two
# authoritative native ledgers, transcribed from the retained crosswalk's producer.carrier / evidence.detail for each
# entry (CROSSWALK_PATH; nothing re-derived): member = native.member row field heads (the search names them
# native.member.row.<field>...), sections = native.lifecycle emitting_section names (native.lifecycle.<section>[i]...).
# A lifecycle row emitted at STREAM_END / FINALIZE is post-stream knowledge only and never a live value.
NATIVE_SERIES = {
    'order_lifecycle_fills': dict(member=('structure.fill_disposition', 'raw_actions'), sections=()),
    'order_lifecycle_clears': dict(member=('capture_observations', 'integrity_delta', 'raw_actions'), sections=()),
    'contract_session_roll_state': dict(member=('session_phase', 'continuity_segment', 'raw_symbol', 'instrument_id'), sections=()),
    'complete_state_reset_bootstrap_receipts': dict(member=('integrity_delta', 'capture_observations', 'snapshot_bootstrap_only'),
                                                    sections=()),
    'depletion_and_replenishment': dict(member=('activity_since',), sections=('replenishment',)),
    'resilience_and_recovery': dict(member=(), sections=('replenishment', 'absorption')),
    'price_and_book_path': dict(member=('book_full', 'book_regime', 'structure.price_raw_min', 'structure.price_raw_max',
                                        'structure.price_raw_span'), sections=('ladder',)),
    'derived_ancestry_gaps': dict(member=(), sections=('lineage', 'recurrence')),
    'derived_unresolved_age_chain_trajectory': dict(member=(), sections=('lineage', 'episode')),
    'derived_price_flow_book_paths': dict(member=('book_regime', 'book_full'), sections=('flow_substrate', 'ladder')),
    'derived_v4_mechanics_fifo_features': dict(member=('activity_full', 'activity_since', 'book_full', 'capture_observations'),
                                               sections=('queue',)),
    'prebirth_predecessor_at_risk_state': dict(member=(), sections=('episode', 'candidate')),
    'prebirth_unresolved_chain_extension_state': dict(member=(), sections=('lineage',)),
    'prebirth_ancestry_successor_opportunity': dict(member=(), sections=('lineage',)),
    'prebirth_stopped_chain_false_context_controls': dict(member=(), sections=('episode', 'detector_coverage')),
    'prebirth_negative_opportunity_cases': dict(member=(), sections=('episode', 'detector_coverage')),
    'clock_prospective_discovery_confirmation': dict(member=(), sections=('episode', 'candidate')),
    'clock_model_evaluation': dict(member=('clocks.decision_ts_recv_ns', 'decision_basis', 'f_last_to_decision_delay_ns'),
                                   sections=()),
}
NATIVE_ENTRIES = tuple(NATIVE_SERIES)


def _member_head(path):
    """A member path up to its first list marker ('book_full.bid_levels_full[].fifo_queue[]' -> 'book_full.bid_levels_full')."""
    return str(path).split('[', 1)[0].rstrip('.')


def _row_has(row, path):
    node = row
    for part in _member_head(path).split('.'):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return True


def update_entries(source, row, native=None):
    """The registry entries one reader update carries: a ROOT layer row carries its layer's entries (MARKET_CARRIERS
    first carrier); a native member row carries each native entry whose own field it holds; a native lifecycle row
    carries the entries of its emitting_section. `native`: {entry: {member, sections}} (the ROOT projection plan's
    producers' crosswalk); default NATIVE_SERIES. Used by the shared reader per update; never a value."""
    carriers = native or NATIVE_SERIES
    if source == 'native.member':
        return [e for e in NATIVE_ENTRIES if any(_row_has(row, p) for p in (carriers.get(e) or {}).get('member') or ())]
    if source == 'native.lifecycle':
        section = row.get('emitting_section') if isinstance(row, dict) else None
        return [e for e in NATIVE_ENTRIES if section in ((carriers.get(e) or {}).get('sections') or ())]
    return list(_LAYER_ENTRIES.get(source, ()))


def native_series_patterns(entry, native=None):
    """Search series-name patterns of a native entry's own carriers (native.member.row.<field>, native.lifecycle.<section>[)."""
    import re
    spec = (native or NATIVE_SERIES).get(entry) or dict(member=(), sections=())
    return ([re.compile(r'native\.member\.row\.' + re.escape(_member_head(p)) + r'(\.|\[|$)') for p in spec.get('member') or ()]
            + [re.compile(r'native\.lifecycle\.' + re.escape(s) + r'(\[|\.|$)') for s in spec.get('sections') or ()])


# The BOSS teacher's own computed form of registry entries: ONE table shared by the teacher's all-99 list, the search's
# plane rows (frankie_box_experiment_search.plane_summary names it per entry) and the entry-granular series patterns,
# so they cannot drift (main_recovery, 2026-10-07). entry -> (Dipole columns (search series dipole.<column>), text).
# These are partial teacher forms computed from the APPLIED full-book observation by the pinned equation; the registry
# layer itself is carried as MARKET_CARRIERS says.
TEACHER_FORMS = {
    'derived_roll20_and_dipole_state': ((), 'the Dipole component states and values of every row (roll20 itself stays completed-only)'),
    'order_lifecycle_fills': (('far_absorption_share_64', 'far_absorption_share_1024'), 'far_absorption_share_64/1024'),
    'order_lifecycle_modifies': (('far_priority_loss_rate_64', 'far_priority_loss_rate_1024'), 'far_priority_loss_rate_64/1024'),
    'queue_concentration': (('far_size_hhi',), 'far_size_hhi'),
    'queue_age_and_survival': (('far_identity_survival_64', 'far_identity_survival_1024'), 'far_identity_survival_64/1024 (the survival columns)'),
    'depletion_and_replenishment': (('far_replenish_log1p_64', 'far_replenish_log1p_1024', 'far_absorption_share_64',
                                     'far_absorption_share_1024'), 'far_replenish_log1p_64/1024, far_absorption_share_64/1024'),
    'resilience_and_recovery': (('far_identity_survival_64', 'far_identity_survival_1024', 'far_size_retention_64',
                                 'far_size_retention_1024'), 'far_identity_survival_64/1024, far_size_retention_64/1024'),
    'derived_unresolved_age_chain_trajectory': (('unresolved_age_groups_log', 'extension_count_log', 'step_ratio_log',
                                                 'pullback_ticks_last_log', 'step_duration_groups_log', 'pullback_ticks_prev_log'),
                                                'the six chain columns (4.10 exhaustion in its teacher form)'),
    'prebirth_unresolved_chain_extension_state': (('extension_count_log', 'step_ratio_log', 'pullback_ticks_last_log',
                                                   'pullback_ticks_prev_log'), 'extension_count_log, step_ratio_log, pullback_ticks_*'),
    'missingness_and_integrity_flags': ((), 'every Dipole column\'s state and reason (PRESENT / MISSING / INVALID / ABLATED)'),
}


def teacher_form_patterns(entry):
    import re
    columns, _ = TEACHER_FORMS.get(entry, ((), ''))
    out = [re.compile(r'^dipole\.' + re.escape(c) + r'(?:\.|\[|$)') for c in columns]
    if entry == 'missingness_and_integrity_flags':
        out.append(re.compile(r'^dipole\.[^.]+\.(?:state|reason)$'))
    return out


# The 13 external points (FRANKIE_DAY_EXTERNAL_V1; Greg via Frankie, 2026-10-07: tie them to the 99). The crosswalk
# registry has no external-publication entry of its own, so this module invents none: the day file DECLARES, per point
# (table metadata) or per row (a column), the registry entries the point feeds, under one of EXTERNAL_ENTRY_KEYS. A
# declared name outside the 99 is an integrity finding, listed, never entered. A point with no declaration is outside
# the 99 (listed). An entry a point feeds arrives only when the point's value is in the picture, presented at or after
# its own publication clock (the shared reader's frontier rule; never earlier, never backfilled).
EXTERNAL_ENTRY_KEYS = ('registry_entries', 'registry_entry', 'all99_entries', 'all99_entry')


def external_point_entries(table, row=None):
    """(entries, findings) a day-file point declares it feeds: the table's own metadata, plus a per-row column of the
    same name when the row is given. Only names of the 99 enter; others are findings."""
    declared = []
    for key in EXTERNAL_ENTRY_KEYS:
        value = (table or {}).get(key)
        if value is not None:
            declared.extend([value] if isinstance(value, str) else list(value))
        if row is not None:
            columns = (table or {}).get('columns') or []
            if key in columns:
                cell = row[columns.index(key)]
                if cell is not None:
                    declared.extend([cell] if isinstance(cell, str) else list(cell))
    known = {layer for layer, _, _ in REGISTRY}
    entries, findings = [], []
    for name in declared:
        if name in known:
            if name not in entries:
                entries.append(name)
        else:
            findings.append(dict(kind='external_point_names_unknown_entry', entry=name))
    return entries, findings


# Greg, 2026-10-07: every point maps to a 99 entry (the closest one, `mapping: closest` with its reason, when no exact
# fit; nothing unmapped), and a value with no intrinsic event time sits at 14:00 ET of its trading day (event_time_basis
# 'default_1400', note 'this is not a time-specific event') unless published later, then at its publication time. The
# day file records the mapping and the times; these are the names read here (table metadata, or a per-row column):
EXTERNAL_MAPPING_KEYS = ('registry_mapping', 'mapping')                 # 'exact' | 'closest'
EXTERNAL_MAPPING_REASON_KEYS = ('registry_mapping_reason', 'mapping_reason')
EXTERNAL_EVENT_TIME_KEYS = ('event_time_ns', 'event_time')              # integer nanoseconds (UTC)
EXTERNAL_EVENT_BASIS_KEYS = ('event_time_basis',)                       # e.g. 'intrinsic' | 'default_1400'
EXTERNAL_AS_OF_KEYS = ('as_of_ns', 'as_of')
EXTERNAL_NOTE_KEYS = ('event_time_note', 'note')


def _declared(table, row, keys):
    """The first value of `keys` in the per-row column (when the row is given), else in the table metadata."""
    columns = (table or {}).get('columns') or []
    for key in keys:
        if row is not None and key in columns and row[columns.index(key)] is not None:
            return row[columns.index(key)]
    for key in keys:
        if (table or {}).get(key) is not None:
            return table[key]
    return None


def external_point_mapping(table, row=None):
    """The point's tie to the 99 and its placement times, as the day file records them: entries (validated), mapping
    ('exact' | 'closest' | None), its reason, event time and basis, as-of, the note, and findings (a name outside the
    99; a point that declares no entry: Greg's rule is that nothing is unmapped, so it is listed)."""
    entries, findings = external_point_entries(table, row)
    if not entries and not findings:
        findings.append(dict(kind='external_point_unmapped', listed='the day file declares no 99 entry for this point; '
                             'Greg\'s rule maps every point (closest entry with its reason); listed, never guessed here'))
    event = _declared(table, row, EXTERNAL_EVENT_TIME_KEYS)
    return dict(entries=entries, mapping=_declared(table, row, EXTERNAL_MAPPING_KEYS),
                mapping_reason=_declared(table, row, EXTERNAL_MAPPING_REASON_KEYS),
                event_time_ns=event if type(event) is int else None,
                event_time_basis=_declared(table, row, EXTERNAL_EVENT_BASIS_KEYS),
                as_of=_declared(table, row, EXTERNAL_AS_OF_KEYS), note=_declared(table, row, EXTERNAL_NOTE_KEYS),
                findings=findings + ([dict(kind='external_event_time_not_integer_ns', value=str(event))]
                                     if event is not None and type(event) is not int else []))


def model_clock_row(run_dir, day):
    """clock_model_evaluation for the day (remaining_consumers, 2026-10-07): frankie_box_model_clock.coverage_row on
    <run-dir>/days/<day>/model-clock.jsonl ('stamped_from_model_calls' with its pin and summary, else
    'no_model_call_this_day' with the reason). None when the module or the run directory is not given."""
    if not run_dir:
        return None
    try:
        import frankie_box_model_clock as MC
    except ImportError:
        return None
    return MC.coverage_row(run_dir, day)


# Classroom use words (main_recovery, 2026-10-07): per entry, whether it entered an operand of a named computation
# ('computed'), is only in the pictures / received inputs ('context'), or did not reach the piece ('absent'). Carried as
# an extra key `use` on field rows; validate() checks the word when present.
USE_WORDS = ('computed', 'context', 'absent')


def confirmation_clock_row(receipt_path):
    """clock_prospective_discovery_confirmation at the survivor update (school_recovery, 2026-10-07): read the update
    receipt's `confirmation_clock` (<experiment-survivors>/<run>/<boundary>/receipt.json). stamped_at_boundary and
    committed: the stamp with its pins; otherwise discovery only (no confirmation yet) or stamped_not_committed, with
    the receipt's reason. None when the receipt or the key is absent (the caller keeps its own row)."""
    try:
        clock = json.loads(Path(receipt_path).read_bytes()).get('confirmation_clock')
    except (OSError, ValueError, AttributeError):
        return None
    if not isinstance(clock, dict):
        return None
    if clock.get('status') == 'stamped_at_boundary' and clock.get('committed') is True:
        return dict(entry='clock_prospective_discovery_confirmation', disposition='stamped_at_boundary',
                    reason='the confirmation clock stamped at this boundary and committed',
                    consumer='the survivor update (survivors.json candidates[i].confirmations[j])',
                    survivors=clock.get('survivors'), entry_manifest=clock.get('entry_manifest'), counts=clock.get('counts'))
    if clock.get('status') == 'stamped_at_boundary':
        return dict(entry='clock_prospective_discovery_confirmation', disposition='stamped_not_committed',
                    reason=clock.get('reason') or 'stamped at this boundary, not committed', consumer=None)
    return dict(entry='clock_prospective_discovery_confirmation', disposition='discovery_only',
                reason='discovery only, no confirmation yet: %s' % (clock.get('reason') or 'no reason recorded'), consumer=None)


# The two market entries no picture element carries: the teacher's Dipole state is the teacher's own computation (the
# classroom's arithmetic operand) and the lock clock is the cutoff each consuming piece stamps.
NOT_MARKET_CARRIED = {
    'derived_roll20_and_dipole_state': 'the BOSS teacher\'s Dipole state rows (frankie_box_experiment_teacher), not the '
                                       'market picture; the per-second roll20 aggregate stays completed-only',
    'clock_lock_time': 'stamped by each consuming piece (its as_of / through_cursor cutoff), not a market picture element',
    'clock_model_evaluation': 'the model-evaluation clock records of the day (frankie_box_model_clock: '
                              '<run>/days/<day>/model-clock.jsonl, one record per real meeting/Jev call); the native member '
                              'field clocks.decision_ts_recv_ns stays the declared null (no model call inside the traversal)',
}

_LAYER_ENTRIES = {}
for _entry, (_first, _thin) in MARKET_CARRIERS.items():
    _LAYER_ENTRIES.setdefault(_first, []).append(_entry)

FIELD_RULE = ('exactly the 99 registry entries in crosswalk order, each with one word of the shared vocabulary (the piece\'s '
              'own word kept as piece_disposition), a reason and a consumer; a thin or absent entry keeps the instant and the '
              'day (missing-coverage rule); an unknown name, a duplicate, a missing entry or a group contradiction is an '
              'integrity finding listed apart, never relabelled; an arrival is what reached the piece, not proof that an '
              'equation used it')


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def registry(code_root=None):
    """The 99 identities, checked against the crosswalk file of the checkout when it is there. Returns
    dict(layers, crosswalk, integrity): `crosswalk` is the file pin (path, bytes, sha256) or None (not in this checkout:
    listed, the embedded identities stand); `integrity` lists every difference between the file and the embedded list
    (an integrity finding, visible, never relabelled; the embedded list is still the one used so no entry is dropped)."""
    layers = [dict(entry=layer, group=group, policy=policy, role=GROUP_ROLES[group], historical_delivery_status=None)
              for layer, group, policy in REGISTRY]
    integrity, pin = [], None
    path = Path(code_root) / CROSSWALK_PATH if code_root else None
    if path is not None and path.is_file():
        raw = path.read_bytes()
        pin = dict(path=str(path), bytes=len(raw), sha256=sha256_bytes(raw))
        if pin['sha256'] != CROSSWALK_SHA256 or pin['bytes'] != CROSSWALK_BYTES:
            integrity.append(dict(kind='crosswalk_bytes_differ', expected=dict(bytes=CROSSWALK_BYTES, sha256=CROSSWALK_SHA256),
                                  found=dict(bytes=pin['bytes'], sha256=pin['sha256']),
                                  disposition='separate visible integrity finding; the embedded identities are used'))
        try:
            doc = json.loads(raw)
            rows = [x for x in doc.get('layers') or [] if isinstance(x, dict)]
            found = [(x.get('layer_id'), x.get('group_id'), x.get('policy')) for x in rows]
            if doc.get('schema') != CROSSWALK_SCHEMA:
                integrity.append(dict(kind='crosswalk_schema_differs', expected=CROSSWALK_SCHEMA, found=doc.get('schema')))
            if doc.get('registry_sha256') != REGISTRY_SHA256:
                integrity.append(dict(kind='registry_sha256_differs', expected=REGISTRY_SHA256, found=doc.get('registry_sha256')))
            if found != list(REGISTRY):
                integrity.append(dict(kind='identities_differ', file_count=len(found), embedded_count=len(REGISTRY),
                                      only_in_file=sorted(set(map(str, (x[0] for x in found))) - set(x[0] for x in REGISTRY)),
                                      only_embedded=sorted(set(x[0] for x in REGISTRY) - set(x[0] for x in found))))
            else:
                # the crosswalk's own historical delivery status (DELIVERED, SEALED_PROVEN, ...) as recorded; history,
                # never a statement about this day
                for layer, row in zip(layers, rows):
                    layer['historical_delivery_status'] = row.get('status')
        except ValueError as error:
            integrity.append(dict(kind='crosswalk_unreadable', error=str(error)))
    elif path is not None:
        integrity.append(dict(kind='crosswalk_not_in_checkout', path=str(path),
                              disposition='listed; the embedded identities (bound to its sha256) are used'))
    return dict(layers=layers, crosswalk=pin, crosswalk_path=CROSSWALK_PATH, crosswalk_sha256=CROSSWALK_SHA256,
                crosswalk_bytes=CROSSWALK_BYTES, registry_sha256=REGISTRY_SHA256, pinned_in=PINNED_IN, integrity=integrity)


def entries(code_root=None):
    """The one entry list every piece imports: [{entry, group, policy, role, historical_delivery_status}] in crosswalk
    order (99). The identities are the embedded ones (bound to the crosswalk sha256); a checkout difference is in
    registry(code_root)['integrity']."""
    return registry(code_root)['layers']


def _field_registry(reg):
    return dict(crosswalk_path=CROSSWALK_PATH, crosswalk_sha256=CROSSWALK_SHA256, crosswalk_bytes=CROSSWALK_BYTES,
                registry_sha256=REGISTRY_SHA256, pinned_in=PINNED_IN, crosswalk=reg.get('crosswalk'),
                integrity=reg.get('integrity') or [],
                status=('pinned' if reg.get('crosswalk') and not reg.get('integrity') else
                        'integrity_difference' if any(f.get('kind') != 'crosswalk_not_in_checkout' for f in reg.get('integrity') or [])
                        else 'embedded_identities_crosswalk_not_read'))


def field(piece, day, rows, *, code_root=None, stage=None, basis=None, registry_doc=None):
    """The shared per-piece field FRANKIE_ALL99_COVERAGE_V1, built from the piece's own rows and validated.

    rows: an iterable of dicts, each {entry, disposition, reason, consumer} (optional: group, canonical = the shared word
    when the piece's own word is ambiguous, any extra keys the piece records, e.g. via/count/detail; kept as given).
    The field lists exactly the 99 registry entries in crosswalk order with the registry's group and role. Nothing
    raises for coverage: an unknown name or a duplicate is listed in `integrity` and not entered; a registry entry with
    no row is entered as 'unrouted' and listed in `integrity`; a row whose group contradicts the registry is entered
    under the registry's group and listed. A row without a reason gets the visible text 'no reason recorded by this
    piece' and is named in `listed`. The piece's word becomes
    piece_disposition; `disposition` is the shared word (a word outside LEGACY_WORDS reads 'unknown', listed; an entry
    the registry settles reads its FIXED_WORDS word, the correction listed)."""
    reg = registry_doc or registry(code_root)
    known = {layer['entry']: layer for layer in reg['layers']}
    findings, listed, given = [], [], {}
    for position, row in enumerate(rows or ()):
        name = row.get('entry') if isinstance(row, dict) else None
        if name not in known:
            findings.append(dict(kind='unknown_entry', entry=name, position=position))
            continue
        if name in given:
            findings.append(dict(kind='duplicate_entry', entry=name, position=position))
            continue
        if row.get('group') is not None and row['group'] != known[name]['group']:
            findings.append(dict(kind='group_differs', entry=name, piece_group=row['group'], registry_group=known[name]['group']))
        given[name] = row
    out = []
    for layer in reg['layers']:
        name = layer['entry']
        row = given.get(name)
        if row is None:
            findings.append(dict(kind='missing_entry', entry=name))
            item = dict(entry=name, group=layer['group'], role=layer['role'], disposition='unrouted', piece_disposition=None,
                        reason='this piece supplied no row for this registry entry (integrity finding; listed, not filled in)',
                        consumer=None, **{'class': 'unmapped'})
        else:
            item = {k: v for k, v in row.items()
                    if k not in ('entry', 'group', 'role', 'canonical', 'disposition', 'reason', 'consumer', 'class',
                                 'piece_disposition')}
            word = row.get('disposition')
            if not isinstance(word, str) or not word:
                findings.append(dict(kind='entry_without_disposition', entry=name))
                word = 'unrouted'
            reason = row.get('reason')
            if reason is None or reason == '':
                listed.append(dict(entry=name, listed='no reason recorded by this piece'))
                reason = 'no reason recorded by this piece'
            disposition = row.get('canonical') or (word if word in VOCABULARY else LEGACY_WORDS.get(word))
            if disposition not in VOCABULARY:
                listed.append(dict(entry=name, piece_disposition=word, listed='word not in the shared vocabulary; recorded as unknown'))
                disposition = 'unknown'
            fixed = FIXED_WORDS.get(name)
            if fixed is not None and disposition != fixed:
                listed.append(dict(entry=name, piece_disposition=word, was=disposition, settled=fixed,
                                   listed='the registry settles this entry\'s word (FIXED_WORDS); corrected here'))
                disposition = fixed
            if row.get('role') is not None and row['role'] != layer['role']:
                item['piece_role'] = row['role']
            item.update(entry=name, group=layer['group'], role=layer['role'], disposition=disposition, piece_disposition=word,
                        reason=str(reason) if not isinstance(reason, str) else reason, consumer=row.get('consumer'),
                        **{'class': WORD_CLASS[disposition]})
        out.append(item)
    counts, by_role = {}, {}
    for item in out:
        counts[item['disposition']] = counts.get(item['disposition'], 0) + 1
        slot = by_role.setdefault(item['role'], {})
        slot[item['disposition']] = slot.get(item['disposition'], 0) + 1
    return dict(schema=SCHEMA, piece=piece, stage=stage, day=None if day is None else str(day), basis=basis,
                registry=_field_registry(reg), vocabulary=list(DISPOSITIONS_V1), entries=out, count=len(out),
                counts=counts, by_role=by_role, integrity=findings, integrity_ok=not findings, listed=listed, rule=FIELD_RULE)


def derive_field(base, piece, updates, *, day=None, stage=None, basis=None, code_root=None):
    """A piece's field from another piece's field (e.g. the core reader's): every entry of `base` with this piece's own
    rows in `updates` ({entry: {disposition, reason, consumer, ...}}) replacing it. `base` None: only `updates`
    (missing entries become 'unrouted' and are listed). The base's own integrity findings are carried as `base_integrity`."""
    rows = {}
    for item in (base or {}).get('entries') or []:
        if isinstance(item, dict) and item.get('entry'):
            rows.setdefault(item['entry'], dict({k: v for k, v in item.items() if k not in ('role', 'piece_disposition', 'class')},
                                                disposition=item.get('piece_disposition') or item.get('disposition'),
                                                canonical=item.get('disposition')))
    for name, row in (updates or {}).items():
        rows[name] = dict(row, entry=name)
    doc = field(piece, day if day is not None else (base or {}).get('day'), list(rows.values()), code_root=code_root,
                stage=stage, basis=basis)
    doc['base'] = (None if base is None else dict(piece=base.get('piece'), stage=base.get('stage'), basis=base.get('basis')))
    doc['base_integrity'] = (base or {}).get('integrity') or []
    return doc


def validate(doc):
    """The field checks on a FRANKIE_ALL99_COVERAGE_V1 read back from a receipt: [] when it lists exactly the 99 registry
    entries once each with the registry's group and role, a disposition and a reason; otherwise every finding."""
    findings = []
    if not isinstance(doc, dict) or doc.get('schema') != SCHEMA:
        return [dict(kind='not_a_coverage_field', schema=(doc or {}).get('schema') if isinstance(doc, dict) else None)]
    known = {layer: (group, GROUP_ROLES[group]) for layer, group, _ in REGISTRY}
    seen = set()
    items = doc.get('entries') if isinstance(doc.get('entries'), list) else []
    for position, item in enumerate(items):
        name = item.get('entry') if isinstance(item, dict) else None
        if name not in known:
            findings.append(dict(kind='unknown_entry', entry=name, position=position))
            continue
        if name in seen:
            findings.append(dict(kind='duplicate_entry', entry=name, position=position))
        seen.add(name)
        if (item.get('group'), item.get('role')) != known[name]:
            findings.append(dict(kind='group_or_role_differs', entry=name, found=[item.get('group'), item.get('role')],
                                 registry=list(known[name])))
        if item.get('disposition') not in VOCABULARY or not item.get('reason'):
            findings.append(dict(kind='entry_without_shared_disposition_or_reason', entry=name,
                                 disposition=item.get('disposition')))
        elif item.get('use') is not None and item['use'] not in USE_WORDS:
            findings.append(dict(kind='use_word_unknown', entry=name, use=item['use']))
        elif name in FIXED_WORDS and item['disposition'] != FIXED_WORDS[name]:
            findings.append(dict(kind='settled_word_differs', entry=name, found=item['disposition'], settled=FIXED_WORDS[name]))
    for name in known:
        if name not in seen:
            findings.append(dict(kind='missing_entry', entry=name))
    if len(items) != len(REGISTRY):
        findings.append(dict(kind='entry_count', found=len(items), registry=len(REGISTRY)))
    if (doc.get('registry') or {}).get('registry_sha256') != REGISTRY_SHA256:
        findings.append(dict(kind='registry_sha256_differs', found=(doc.get('registry') or {}).get('registry_sha256')))
    return findings


def _plane_rows():
    """The search's own plane table (name -> source), imported lazily so this module parses without project imports."""
    import frankie_box_experiment_search as SEARCH
    return {name: dict(source=source, declared=status, mapped_by=consumed_by, remaining=remaining)
            for name, source, status, consumed_by, remaining in SEARCH.PLANE_COVERAGE}


def series_sources(sources):
    """series name -> source name, from the search manifest's source receipts (placed_series / placed_cells)."""
    out = {}
    for receipt in sources or []:
        name = receipt.get('source')
        for key in ('placed_series', 'placed_cells'):
            for series in receipt.get(key) or []:
                label = series if isinstance(series, str) else (series.get('name') or series.get('series')) if isinstance(series, dict) else None
                if label and label not in out:
                    out[label] = name
    return out


def tests_by_source(tests, by_series):
    """How many test rows of this operation read a series of each source (x and y each counted once per row)."""
    counts = {}
    for t in tests or []:
        for side in ('x', 'y'):
            source = by_series.get(t.get(side))
            if source is None:
                # the search names series as <source>.<rest>; the receipt's source names match that prefix
                source = str(t.get(side) or '').split('.', 1)[0] or None
            if source is not None:
                counts[source] = counts.get(source, 0) + 1
    return counts


# Entry-granular reading (review 2026-10-07): an entry arrives at a scientific operation only when a test row read a
# series of THAT entry, never merely a series of the same source. The patterns are the entry's own series as the
# search's plane table names them (mapped_by), with explicit forms where that text is shared or unprefixed; a native
# entry adds its own native.member / native.lifecycle carriers (NATIVE_SERIES). No pattern = not established.
EXPLICIT_SERIES = {
    'order_lifecycle_adds': (r'events\.A_',), 'order_lifecycle_cancels': (r'events\.C_',),
    'order_lifecycle_modifies': (r'events\.M_',), 'order_lifecycle_replaces': (r'events\.M_',),
    'order_lifecycle_trades': (r'events\.T_', r'prices\.', r'signed_flow\.'),
    'order_lifecycle_fills': (r'events\.F_', r'structures\.fill_disposition\.'),
    'order_lifecycle_clears': (r'events\.R_', r'events\.last\.is_snapshot'),
    'complete_state_reset_bootstrap_receipts': (r'events\.last\.is_snapshot',),
    'missingness_and_integrity_flags': (r'frames\.integrity\.',),
    'derived_roll20_and_dipole_state': (r'roll20\.',),
    'legacy_per_second_roll20': (r'roll20\.',),
    'legacy_native_signed_flow': (r'signed_flow\.',), 'aggressor_and_native_signed_flow': (r'signed_flow\.', r'frames\.input_records\['),
}
_SERIES_TOKEN = r'(?:frames|structures|prices|events|signed_flow|roll20|dipole|external|journal)\.[A-Za-z0-9_.*<>\[\]/]+'


def _token_pattern(token):
    import re
    token = token.rstrip('.,;:)')
    out = re.escape(token)
    out = re.sub(r'\\\[[a-z_]+\\\]', r'\\[\\d+\\]', out)            # [i] / [j] / [position] -> any position
    out = re.sub(r'<[^>]*>|\\<[^>]*\\>', '[^.]+', out)                 # <name> -> one segment
    out = out.replace(r'\*', '[^ ]*')                                   # * -> anything
    out = re.sub(r'([A-Za-z0-9]+)/([A-Za-z0-9]+)', r'(?:\1|\2)', out)  # bid/ask -> either
    return out


def entry_series_patterns(entry):
    """Compiled patterns of the search series that are this entry's own (see EXPLICIT_SERIES)."""
    import re
    texts = list(EXPLICIT_SERIES.get(entry, ()))
    if not texts:
        mapped = (_plane_rows().get(entry) or {}).get('mapped_by') or ''
        texts = [_token_pattern(t) for t in re.findall(_SERIES_TOKEN, mapped)]
    patterns = []
    for t in texts:
        try:
            patterns.append(re.compile('^' + t + r'(?:\.|\[|$)?'))
        except re.error:
            continue        # a plane-table phrase that is not a series name; the entry's other patterns stand
    # the teacher's own form of the entry (TEACHER_FORMS, the one shared table) and its native carriers
    return patterns + teacher_form_patterns(entry) + native_series_patterns(entry)


def tests_by_entry(tests, names, extra=None):
    """How many test rows of this operation read a series of each named entry or plane (x and y each counted). extra:
    {name: [regex text]} recorded by the search for that day (the native entries' runtime series_patterns)."""
    import re
    patterns = {name: entry_series_patterns(name) + [re.compile(x) for x in (extra or {}).get(name) or ()] for name in names}
    counts = {name: 0 for name in names}
    for t in tests or []:
        for side in ('x', 'y'):
            series = str(t.get(side) or '')
            if not series:
                continue
            for name, compiled in patterns.items():
                if any(p.match(series) for p in compiled):
                    counts[name] += 1
    return counts, {name: bool(compiled) for name, compiled in patterns.items()}


def _plane_disposition(plane, status_row, read, search_mode=False, *, has_patterns=True, tests_total=0):
    status = (status_row or {}).get('status')
    if status_row is None:
        return 'absent', 'the search manifest carries no plane row for this entry (an older search)', None
    disposition, family = PLANE_STATUS.get(status, ('absent', 'plane status %r (unknown to this reader)' % status))
    source = plane.get('source')
    reason = family
    if status_row.get('remaining'):
        reason += '; remaining: ' + str(status_row['remaining'])
    if status_row.get('native'):
        reason += '; native carriers: %s' % status_row['native'].get('summary')
    if status_row.get('external'):
        reason += '; day-file points: %s' % status_row['external'].get('summary')
    if search_mode:
        # the search itself: every placed (leakage-gated) series enters the couplings of every pair, cell and lag; a cell
        # with fewer than two steps of a series is listed in cells_not_counted by the search
        if disposition in ('arrived', 'thin') and status != 'clock':
            reason += '; placed series of this entry enter every coupling pair of this search (cells_not_counted lists the rest)'
        return disposition, reason, dict(source=source, search_status=status, tests_reading=None, mapped_by=status_row.get('mapped_by'))
    if status == 'clock':
        # a clock places every series a test reads; it arrives only when this operation read at least one test row (N7)
        if tests_total:
            reason += '; it placed every series the %d test row(s) of this operation read' % tests_total
        else:
            disposition, reason = 'thin', reason + '; no test row of this operation: nothing it placed was read here'
    elif disposition in ('arrived', 'thin'):
        if not has_patterns:
            disposition = 'thin'
            reason += '; the plane table names no series of this entry\'s own, so its arrival cannot be established per entry'
        elif read == 0:
            disposition = 'thin'
            reason += '; no test row of this operation read a series of this entry (placed, not consumed by a claim here)'
        else:
            reason += '; %d test row side(s) of this operation read a series of this entry' % read
    return disposition, reason, dict(source=source, search_status=status, tests_reading=read, mapped_by=status_row.get('mapped_by'))


def day_coverage(day, *, manifest_sha256, planes, sources, tests, knowledge_inputs, outputs, stage, code_root=None,
                 shared_market=None, search_mode=False, confirmation_clock=None, model_clock=None):
    """The all-99 list of one day for one operation of a stage (the shared field FRANKIE_ALL99_COVERAGE_V1, piece = stage).

    day / manifest_sha256 / planes / sources: the day's search (its manifest's plane receipt and source receipts, as
    frankie_box_scientific_teacher.load_searches retains them). tests: every test row the operation produced on this
    day (the claims' rows, origin evidence included: they too are rows read). knowledge_inputs: what knowledge the
    operation took (historical=dict(mapped_claims, not_testable, catalog_sha256) or None; brain_documents=int or None;
    frankie=bool; jev=bool; search_candidates=bool). outputs: {registry output entry: pin or None} for the outputs this
    operation wrote. shared_market: the manifest's shared_market source receipt (coverage / absent_layers) when present.
    search_mode: the search's own list (search_coverage): a placed series arrives at every coupling pair; tests unused.
    confirmation_clock: the survivor update's row for clock_prospective_discovery_confirmation (confirmation_clock_row of
    its receipt), replacing the plane row of that entry when given. model_clock: the day's clock_model_evaluation row
    (model_clock_row), replacing that entry's row when given."""
    reg = registry(code_root)
    rows = _plane_rows()
    by_series = series_sources(sources)
    read_counts = None if search_mode else tests_by_source(tests, by_series)
    # entry-granular reading: per calculation/clock entry and per raw route plane, the test rows that read its own series
    plane_names = [layer['entry'] for layer in reg['layers'] if layer['role'] in ('calculation', 'clock')]
    plane_names += sorted({n for names, _ in RAW_ROUTES.values() for n in names})
    by_entry, has_patterns = (({n: None for n in plane_names}, {n: True for n in plane_names}) if search_mode
                              else tests_by_entry(tests, plane_names,
                                                  {n: [x for key in ('native', 'external')
                                                       for x in ((((planes or {}).get(n) or {}).get(key) or {}).get('series_patterns') or [])]
                                                   for n in plane_names}))
    tests_total = 0 if search_mode else len(tests or [])
    planes = planes or {}
    entries = []
    computed_by = ('%s: coupling rows of every placed series' % stage if search_mode else
                   '%s: the test rows of this operation' % stage)
    for layer in reg['layers']:
        entry, role = layer['entry'], layer['role']
        via, reason, consumer = None, None, None
        if role in ('calculation', 'clock'):
            plane = rows.get(entry) or {}
            disposition, reason, via = _plane_disposition(plane, planes.get(entry), by_entry.get(entry), search_mode,
                                                          has_patterns=has_patterns.get(entry, False), tests_total=tests_total)
            consumer = computed_by if disposition in ('arrived', 'thin') else None
        elif role == 'raw':
            names, route = RAW_ROUTES[entry]
            parts = [(_plane_disposition(rows.get(n) or {}, planes.get(n), by_entry.get(n), search_mode,
                                         has_patterns=has_patterns.get(n, False), tests_total=tests_total), n) for n in names]
            order = {d: i for i, d in enumerate(('arrived', 'thin', 'absent'))}
            best = min(parts, key=lambda p: order.get(p[0][0], 9))
            disposition = best[0][0]
            consumer = computed_by if disposition in ('arrived', 'thin') else None
            reason = route + '; read through: ' + '; '.join('%s=%s (%s)' % (n, d[0], d[1]) for d, n in parts)
            via = dict(planes=[n for _, n in parts],
                       tests_reading=None if search_mode else sum((d[2] or {}).get('tests_reading', 0) for d, _ in parts))
            if shared_market is not None:
                absent = (shared_market.get('coverage') or {}).get('absent_layers') or shared_market.get('absent_layers')
                if absent:
                    reason += '; shared market read lists absent layers: ' + ', '.join(map(str, absent))
                via['shared_market_identity'] = shared_market.get('identity') or shared_market.get('shared_market_identity')
        elif role in ('control', 'arm', 'knowledge'):
            kind, route = KNOWLEDGE_ROUTES[entry]
            historical = (knowledge_inputs or {}).get('historical')
            if entry in FIXED_WORDS:
                # settled by the registry: the A-clean overlay is NOT_APPLICABLE, the arm profile a delivered binding control
                disposition, reason = FIXED_WORDS[entry], route
            elif search_mode:
                disposition, reason = 'not_read_by_this_piece', 'not an input of the search by role: ' + route
            elif kind == 'policy':
                disposition, reason = 'not_read_by_this_piece', 'not an input of this stage by role: ' + route
            elif kind == 'memory_a':
                disposition, reason = 'retired', route
            elif kind == 'brain':
                documents = (knowledge_inputs or {}).get('brain_documents')
                disposition = 'arrived' if documents else 'thin' if documents == 0 else 'absent'
                reason = route + ('; %s documents selected' % documents if documents is not None else
                                  '; no brain selection in this operation (claims given directly)')
                consumer = '%s: the learner knowledge selection' % stage if documents is not None else None
            else:
                if historical:
                    disposition = 'thin'
                    reason = route + ('; this operation tested %s mapped historical claims and carried %s not_testable statements '
                                      'by reference (catalog %s)' % (historical.get('mapped_claims'), historical.get('not_testable'),
                                                                     str(historical.get('catalog_sha256'))[:12]))
                    consumer = '%s: the historical claims crosswalk' % stage
                else:
                    disposition, reason = 'absent', route + '; no historical claims file given to this operation'
            via = dict(route=kind)
        elif role == 'sealed_answer':
            disposition, reason = 'withheld_by_role', 'a sealed answer/target (SEALED_FOR_A_SCOPE): never read by a teacher (R09/R10); withheld, not missing'
        elif role == 'shadow':
            disposition, reason = 'disabled', 'a provisional shadow (SHADOW_DISABLED by the existing policy); not activated here'
        else:
            pin = (outputs or {}).get(entry)
            owner = OUTPUT_ROUTES[entry]
            if pin:
                disposition, reason, via, consumer = 'produced', 'written by this operation: ' + owner, pin, stage
            elif entry in ('output_candidate_discoveries', 'output_negative_sparse_inconclusive_ledger',
                           'output_knowledge_retrieval_receipts', 'output_source_state_manifest_code_model_run_hashes'):
                disposition, reason = 'pending', 'this stage family writes it and this operation did not (yet): ' + owner
            else:
                disposition, reason = 'absent', 'not an output of this stage: ' + owner
        entries.append(dict(entry=entry, group=layer['group'], policy=layer['policy'], role=role,
                            disposition=disposition, reason=reason, via=via, consumer=consumer))
    for override, name in ((confirmation_clock, 'clock_prospective_discovery_confirmation'), (model_clock, 'clock_model_evaluation')):
        if isinstance(override, dict) and override.get('entry') == name:
            for item in entries:
                if item['entry'] == name:
                    item.update({k: v for k, v in override.items() if k != 'entry'})
    # The shared field: the same rows, validated against the one registry (exactly 99, no duplicate, no unknown name).
    checked = field(stage, day, entries, stage=stage, registry_doc=reg,
                    basis='search plane receipt and coupling rows' if search_mode else 'search plane receipt and the test rows of this operation')
    counts = {d: sum(1 for e in entries if e['disposition'] == d) for d in DISPOSITIONS}
    # every word present is counted, including the clock override words (stamped_at_boundary, stamped_not_committed,
    # discovery_only, stamped_from_model_calls, no_model_call_this_day) that are outside DISPOSITIONS: additive, the
    # DISPOSITIONS keys stay (zero included), so the counts sum to the entries listed
    for e in entries:
        if e['disposition'] not in counts:
            counts[e['disposition']] = sum(1 for x in entries if x['disposition'] == e['disposition'])
    by_role = {}
    for e in entries:
        by_role.setdefault(e['role'], {}).setdefault(e['disposition'], 0)
        by_role[e['role']][e['disposition']] += 1
    return dict(checked, schema=SCHEMA, day=str(day), stage=stage, search_manifest_sha256=manifest_sha256,
                registry_sha256=reg['registry_sha256'], crosswalk=reg['crosswalk'], crosswalk_sha256=reg['crosswalk_sha256'],
                registry_integrity=reg['integrity'], counts=counts, by_role=by_role, shared_counts=checked['counts'], shared_by_role=checked['by_role'],
                tests_read=None if search_mode else len(tests or []), tests_by_source=read_counts, tests_by_entry=None if search_mode else by_entry,
                absent=[e['entry'] for e in entries if e['disposition'] == 'absent'],
                thin=[e['entry'] for e in entries if e['disposition'] == 'thin'],
                rule=RULE, field_rule=FIELD_RULE)


def search_coverage(day, *, manifest_sha256, planes, sources, outputs=None, code_root=None, shared_market=None):
    """The search's own all-99 list of one day (FRANKIE_ALL99_COVERAGE_V1, piece 'search'): the plane receipt the search
    just built, with a placed series counted as arriving at the couplings (the search runs every pair, cell and lag)."""
    return day_coverage(day, manifest_sha256=manifest_sha256, planes=planes, sources=sources, tests=None,
                        knowledge_inputs=None, outputs=outputs or {}, stage='search', code_root=code_root,
                        shared_market=shared_market, search_mode=True)


def summary(coverage):
    """The compact projection a lessons file or receipt carries inline (the full list stays in the coverage file)."""
    return dict(schema=SCHEMA + '_SUMMARY', day=coverage['day'], stage=coverage['stage'],
                search_manifest_sha256=coverage['search_manifest_sha256'], counts=coverage['counts'],
                by_role=coverage['by_role'], absent=coverage['absent'], thin=coverage['thin'],
                tests_read=coverage['tests_read'], registry_integrity=coverage['registry_integrity'], rule=coverage['rule'],
                shared_counts=coverage.get('shared_counts'), integrity=coverage.get('integrity'), integrity_ok=coverage.get('integrity_ok'))


def retain(coverage, out_root):
    """Write the day's list once under <out_root>/coverage/<day>-all99-<manifest sha12>-<stage>-<content sha12>.json.
    The name carries the content hash: the same list reuses its file, a different list (another operation of the same
    owner, a successor) gets its own file beside it; nothing is overwritten and nothing refuses. Returns the pin."""
    from frankie_box_durable import write_bytes
    data = (json.dumps(coverage, indent=1, sort_keys=True) + '\n').encode()
    digest = sha256_bytes(data)
    name = '%s-all99-%s-%s-%s.json' % (coverage['day'], str(coverage['search_manifest_sha256'])[:12], coverage['stage'], digest[:12])
    path = Path(out_root) / 'coverage' / name
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError('%s exists with other bytes under its own content address (altered pinned bytes)' % path)
    else:
        write_bytes(path, data)
    return dict(path=str(path), bytes=len(data), sha256=digest, summary=summary(coverage))


def boundary(coverages):
    """The cross-day view of several days' lists (the survivor/candidate update): per entry, the days by disposition.
    Counts and day names only, never pooled into a rate."""
    per_entry = {}
    for cov in coverages:
        for e in cov['entries']:
            slot = per_entry.setdefault(e['entry'], dict(group=e['group'], role=e['role'], days={}))
            slot['days'].setdefault(e['disposition'], []).append(cov['day'])
    return dict(schema=SCHEMA + '_BOUNDARY', days=[c['day'] for c in coverages], entries=per_entry,
                files=[dict(day=c['day'], search_manifest_sha256=c['search_manifest_sha256']) for c in coverages],
                rule='days named per disposition per entry; a day absent from one entry is thinner, never dropped')


def markdown(coverage):
    """The inspection projection (one table) for a piece's one-day markdown; the reporter may embed it verbatim."""
    lines = ['| entry | role | disposition | reason | consumer |', '|---|---|---|---|---|']
    for e in coverage['entries']:
        lines.append('| %s | %s | %s | %s | %s |' % (e['entry'], e['role'], e['disposition'], str(e['reason']).replace('|', '/'),
                                                     str(e.get('consumer')).replace('|', '/')))
    return '\n'.join(lines) + '\n'
