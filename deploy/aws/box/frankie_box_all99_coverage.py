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
  absent             not in this export / listed missing / not produced (bedrock off) / built but not called; the reason
                     is the search's own; the day stays, the picture is thinner (missing-coverage rule)
  disabled           the two provisional shadows (SHADOW_DISABLED by the existing policy; never activated here)
  withheld_by_role   the nine sealed answers (R09/R10: no teacher reads an answer key or a sealed target)
  produced / pending the ten append-only outputs, by whether THIS stage wrote them (with the pin) or another owner does

Nothing is inferred from a file read: a plane counts as arrived only when a test row of this operation carries a series
the search placed from that plane's source. The embedded 99 identities are checked against the crosswalk file when the
checkout carries it (bytes bound by sha256); a difference is listed as an integrity failure and never relabelled.
Code only; no model call; no new scientific mapping (the plane-to-source reading is the search's own table).
"""
import hashlib
import json
from pathlib import Path

SCHEMA = 'FRANKIE_ALL99_COVERAGE_V1'
CROSSWALK_PATH = 'research/kalshi/frankie_boss/audits/CROSSWALK_SUNDAY_CYCLE0_FEED_33746436209_20260916.json'
CROSSWALK_SHA256 = 'ece9c624d9969166e81876e7705d0c47054e46b6aa3e5485803a218648184de9'
REGISTRY_SHA256 = '239a14808850d9cc9ba589165e4263c0e3f11a0c574052f39bfaa133adf296b1'
DISPOSITIONS = ('arrived', 'thin', 'absent', 'disabled', 'withheld_by_role', 'produced', 'pending')
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
    'not_produced': ('absent', 'not produced on the experiment path (bedrock off / host clock)'),
    'built_not_called': ('absent', 'an implementation exists and nothing on the experiment path calls it'),
    'produced_not_carried': ('absent', 'produced at every close and not spooled; no file this search reads carries it'),
    'computed_not_retained': ('thin', 'computed by the pinned teacher; only a projection is retained'),
    'not_requested': ('absent', 'not requested by the search configuration'),
    'native_evidence_present_layer_mapping_open': ('thin', 'exact native rows present; the registry-layer reconciliation is open'),
    'retained_not_searched': ('thin', 'retained by the search and not searched'),
}


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def registry(code_root=None):
    """The 99 identities, checked against the crosswalk file of the checkout when it is there. Returns
    dict(layers, crosswalk, integrity): `crosswalk` is the file pin (path, bytes, sha256) or None (not in this checkout:
    listed, the embedded identities stand); `integrity` lists every difference between the file and the embedded list
    (an integrity finding, visible, never relabelled; the embedded list is still the one used so no entry is dropped)."""
    layers = [dict(entry=layer, group=group, policy=policy, role=GROUP_ROLES[group]) for layer, group, policy in REGISTRY]
    integrity, pin = [], None
    path = Path(code_root) / CROSSWALK_PATH if code_root else None
    if path is not None and path.is_file():
        raw = path.read_bytes()
        pin = dict(path=str(path), bytes=len(raw), sha256=sha256_bytes(raw))
        if pin['sha256'] != CROSSWALK_SHA256:
            integrity.append(dict(kind='crosswalk_bytes_differ', expected=CROSSWALK_SHA256, found=pin['sha256'],
                                  disposition='separate visible integrity finding; the embedded identities are used'))
        try:
            doc = json.loads(raw)
            found = [(x.get('layer_id'), x.get('group_id'), x.get('policy')) for x in doc.get('layers') or []]
            if doc.get('registry_sha256') != REGISTRY_SHA256:
                integrity.append(dict(kind='registry_sha256_differs', expected=REGISTRY_SHA256, found=doc.get('registry_sha256')))
            if found != list(REGISTRY):
                integrity.append(dict(kind='identities_differ', file_count=len(found), embedded_count=len(REGISTRY),
                                      only_in_file=sorted(set(x[0] for x in found) - set(x[0] for x in REGISTRY)),
                                      only_embedded=sorted(set(x[0] for x in REGISTRY) - set(x[0] for x in found))))
        except ValueError as error:
            integrity.append(dict(kind='crosswalk_unreadable', error=str(error)))
    elif path is not None:
        integrity.append(dict(kind='crosswalk_not_in_checkout', path=str(path),
                              disposition='listed; the embedded identities (bound to its sha256) are used'))
    return dict(layers=layers, crosswalk=pin, crosswalk_sha256=CROSSWALK_SHA256, registry_sha256=REGISTRY_SHA256,
                integrity=integrity)


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


def _plane_disposition(plane, status_row, read_counts, by_series):
    status = (status_row or {}).get('status')
    if status_row is None:
        return 'absent', 'the search manifest carries no plane row for this entry (an older search)', None
    disposition, family = PLANE_STATUS.get(status, ('absent', 'plane status %r (unknown to this reader)' % status))
    source = plane.get('source')
    read = read_counts.get(source, 0) if source else 0
    reason = family
    if status_row.get('remaining'):
        reason += '; remaining: ' + str(status_row['remaining'])
    if disposition == 'arrived' and status != 'clock':
        if read == 0:
            disposition = 'thin'
            reason += '; no test of this operation read a series of source %r (placed, not consumed by a claim here)' % source
        else:
            reason += '; %d test row(s) of this operation read source %r' % (read, source)
    elif disposition == 'thin' and read:
        reason += '; %d test row(s) of this operation read source %r' % (read, source)
    return disposition, reason, dict(source=source, search_status=status, tests_reading=read, mapped_by=status_row.get('mapped_by'))


def day_coverage(day, *, manifest_sha256, planes, sources, tests, knowledge_inputs, outputs, stage, code_root=None,
                 shared_market=None):
    """The all-99 list of one day for one operation of a stage.

    day / manifest_sha256 / planes / sources: the day's search (its manifest's plane receipt and source receipts, as
    frankie_box_scientific_teacher.load_searches retains them). tests: every test row the operation produced on this
    day (the claims' rows, origin evidence included: they too are rows read). knowledge_inputs: what knowledge the
    operation took (historical=dict(mapped_claims, not_testable, catalog_sha256) or None; brain_documents=int or None;
    frankie=bool; jev=bool; search_candidates=bool). outputs: {registry output entry: pin or None} for the outputs this
    operation wrote. shared_market: the manifest's shared_market source receipt (coverage / absent_layers) when present."""
    reg = registry(code_root)
    rows = _plane_rows()
    by_series = series_sources(sources)
    read_counts = tests_by_source(tests, by_series)
    planes = planes or {}
    entries = []
    for layer in reg['layers']:
        entry, role = layer['entry'], layer['role']
        via, reason = None, None
        if role in ('calculation', 'clock'):
            plane = rows.get(entry) or {}
            disposition, reason, via = _plane_disposition(plane, planes.get(entry), read_counts, by_series)
        elif role == 'raw':
            names, route = RAW_ROUTES[entry]
            parts = [(_plane_disposition(rows.get(n) or {}, planes.get(n), read_counts, by_series), n) for n in names]
            order = {d: i for i, d in enumerate(('arrived', 'thin', 'absent'))}
            best = min(parts, key=lambda p: order.get(p[0][0], 9))
            disposition = best[0][0]
            reason = route + '; read through: ' + '; '.join('%s=%s (%s)' % (n, d[0], d[1]) for d, n in parts)
            via = dict(planes=[n for _, n in parts], tests_reading=sum((d[2] or {}).get('tests_reading', 0) for d, _ in parts))
            if shared_market is not None:
                absent = (shared_market.get('coverage') or {}).get('absent_layers') or shared_market.get('absent_layers')
                if absent:
                    reason += '; shared market read lists absent layers: ' + ', '.join(map(str, absent))
                via['shared_market_identity'] = shared_market.get('identity') or shared_market.get('shared_market_identity')
        elif role in ('control', 'arm', 'knowledge'):
            kind, route = KNOWLEDGE_ROUTES[entry]
            historical = (knowledge_inputs or {}).get('historical')
            if kind == 'policy':
                disposition, reason = 'absent', 'not an input of this stage by role: ' + route
            elif kind == 'memory_a':
                disposition, reason = 'disabled', route
            elif kind == 'brain':
                documents = (knowledge_inputs or {}).get('brain_documents')
                disposition = 'arrived' if documents else 'thin' if documents == 0 else 'absent'
                reason = route + ('; %s documents selected' % documents if documents is not None else
                                  '; no brain selection in this operation (claims given directly)')
            else:
                if historical:
                    disposition = 'thin'
                    reason = route + ('; this operation tested %s mapped historical claims and carried %s not_testable statements '
                                      'by reference (catalog %s)' % (historical.get('mapped_claims'), historical.get('not_testable'),
                                                                     str(historical.get('catalog_sha256'))[:12]))
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
                disposition, reason, via = 'produced', 'written by this operation: ' + owner, pin
            elif entry in ('output_candidate_discoveries', 'output_negative_sparse_inconclusive_ledger',
                           'output_knowledge_retrieval_receipts', 'output_source_state_manifest_code_model_run_hashes'):
                disposition, reason = 'pending', 'this stage family writes it and this operation did not (yet): ' + owner
            else:
                disposition, reason = 'absent', 'not an output of this stage: ' + owner
        entries.append(dict(entry=entry, group=layer['group'], policy=layer['policy'], role=role,
                            disposition=disposition, reason=reason, via=via))
    counts = {d: sum(1 for e in entries if e['disposition'] == d) for d in DISPOSITIONS}
    by_role = {}
    for e in entries:
        by_role.setdefault(e['role'], {}).setdefault(e['disposition'], 0)
        by_role[e['role']][e['disposition']] += 1
    return dict(schema=SCHEMA, day=str(day), stage=stage, search_manifest_sha256=manifest_sha256,
                registry_sha256=reg['registry_sha256'], crosswalk=reg['crosswalk'], crosswalk_sha256=reg['crosswalk_sha256'],
                registry_integrity=reg['integrity'], entries=entries, counts=counts, by_role=by_role,
                tests_read=len(tests or []), tests_by_source=read_counts,
                absent=[e['entry'] for e in entries if e['disposition'] == 'absent'],
                thin=[e['entry'] for e in entries if e['disposition'] == 'thin'],
                rule=RULE)


def summary(coverage):
    """The compact projection a lessons file or receipt carries inline (the full list stays in the coverage file)."""
    return dict(schema=SCHEMA + '_SUMMARY', day=coverage['day'], stage=coverage['stage'],
                search_manifest_sha256=coverage['search_manifest_sha256'], counts=coverage['counts'],
                by_role=coverage['by_role'], absent=coverage['absent'], thin=coverage['thin'],
                tests_read=coverage['tests_read'], registry_integrity=coverage['registry_integrity'], rule=coverage['rule'])


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
    lines = ['| entry | role | disposition | reason |', '|---|---|---|---|']
    for e in coverage['entries']:
        lines.append('| %s | %s | %s | %s |' % (e['entry'], e['role'], e['disposition'], str(e['reason']).replace('|', '/')))
    return '\n'.join(lines) + '\n'
