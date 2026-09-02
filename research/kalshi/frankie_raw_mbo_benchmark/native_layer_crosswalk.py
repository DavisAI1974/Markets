"""The 99-layer crosswalk: registry layer -> producing code -> carrier -> delivery evidence.

**Why this exists.** The S120 close measured that 91 of the registry's layers bind their
evidence hash to one markdown document and that the pre-call gate stamps every layer's status
OFF ITS POLICY (`native_a_arm_launch.build_pre_call_receipt`): a static layer reads AVAILABLE
because its group says STATIC_REQUIRED_INPUT, a stream layer reads READY_CAUSAL_STREAM because
its group says so. That receipt proved the document was unchanged and nothing about ingestion
or delivery. Greg's standing rule (2026-09-02): *a gate that reads status off a policy is not a
gate; "done" is a row from a real run naming the layer, the carrier and the receipt hash.*

**What this module holds.** `LAYER_PRODUCERS` names, for EVERY layer the registry carries
(the key set is asserted equal to the registry's layer set at test time - no count is a spec),
the code that produces it with file and symbol, and the carrier that would deliver it: a row
field path on the exact member ledger, a lifecycle-ledger section, a legacy-row key, a
knowledge file, a receipt, a sealed object set, or his own output ledger. `NO_PRODUCER_FOUND`
is an allowed, honest answer that says what was searched. Every carrier declaration is
verified BY EXECUTION in the tests against a row a real traversal wrote, censused with
`native_mbo_field_census.MboFieldCensus`, whose paths are the vocabulary used here.

**The measurement this table records, and it is the one Greg's ruling 2 turns on.** The exact
member row carries 48 top-level fields and NO `raw_actions`: `native_replay_driver._on_group`
skips the frame's `raw_actions` when carrying frame keys onto the row with a comment saying
the member row already holds them, and `native_clocks.member_clock_row` - which builds the
row - returns no such key. So the per-record A/C/M/R/T/F/N messages with their order ids,
prices, sizes, flags, sequences, per-record clocks, per-record `book_effect` and per-record
`source_dbn_object` / `source_dbn_sha256` are PRODUCED (the hash-locked adapter's
`NormalizedMbo.public_dict`, the capture wrapper's `book_effect`) and then DROPPED before the
ledger. What survives per group is state and aggregates: `book_full` with its FIFO queues,
the `activity` windows, the `structure` descriptor, `integrity`, `clocks`. The order-lifecycle
layers therefore have a producer and no carrier, and the per-group delivery receipt that names
them under the member carrier over-claims. The records below say so, the tests pin the
absence so a fix cannot go unnoticed, and the computed status (`RECEIPTED_CARRIER_ABSENT`)
names it on every render.

**The seven clocks, against the code as it is.** The registry's `causal_clocks` group names
seven; the row's `clocks` object has five fields and the group receipt four keys. The mapping
(`SEVEN_CLOCKS`) says which of the seven each covers and which have none. Lock time is
Frankie's OUTPUT and has no input producer. These rows, and the activity-window rows, are
expected to change at merge when the clock producers and the window removal land.

Line numbers in the records are informational and move; the tests verify file and symbol.
Repo-relative paths, S3 keys and hashes only (D34).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import (
    load_registry,
)

REPO_ROOT = Path(__file__).resolve().parents[3]

PRODUCER_KINDS = frozenset({
    "ROW_FIELD", "LEDGER", "SECTION", "FILE", "RECEIPT", "PRINCIPAL_OUTPUT",
    "SEALED_OBJECT", "SHADOW", "NO_PRODUCER_FOUND",
})

MEMBER_LEDGER = "exact_member_ledger"
LIFECYCLE_LEDGER = "exact_lifecycle_and_runway_ledger"
LEGACY_LEDGER = "legacy_observable_rows"

# --- the files the producers live in, repo-relative --------------------------------------
V4 = "research/ng_exhaustion_mbo_v4_state_adapter_20260820.py"
"""Hash-locked (D61). Cited, never edited."""
PKG = "research/kalshi/frankie_raw_mbo_benchmark/"
FCA = PKG + "native_full_capture_adapter.py"
DRV = PKG + "native_replay_driver.py"
CLK = PKG + "native_clocks.py"
BRG = PKG + "native_book_regime.py"
STRUCT = PKG + "a_memory_member_first_recalculation_20260828.py"
ROLL = PKG + "native_roll20.py"
STREAM = PKG + "native_causal_stream.py"
REG = PKG + "native_ingestion_layer_registry.py"
LAUNCH = PKG + "native_a_arm_launch.py"
ROSTER = PKG + "raw_mbo_source_manifest.py"
FLOW = PKG + "native_flow_substrate.py"
CAND = PKG + "native_candidate.py"
RECOG = PKG + "native_recognition.py"
RTBOOK = PKG + "native_rt_book.py"
REGISTRY_JSON = "research/kalshi/agents/frankie_native_raw_mbo_ingestion_layer_registry_20260828.json"
FEED_DOC = "research/kalshi/NG_EXHAUSTION_FRANKIE_DATA_FEED_INVENTORY_20260824.md"
SOURCE_DOC = "research/kalshi/NG_EXHAUSTION_FRANKIE_SOURCE_FILE_INVENTORY_20260824.md"
KNOWLEDGE_DIR = "research/kalshi/agents/frankie_native_raw_mbo_knowledge/"
KNOWLEDGE_MANIFEST = KNOWLEDGE_DIR + "KNOWLEDGE_MANIFEST_20260828.json"

RAW_ACTIONS_DROP = (
    "PRODUCED and then DROPPED: `NormalizedMbo.public_dict` builds every per-record field and "
    "`FullCaptureAdapter.apply` attaches the per-record `book_effect`, but "
    "`native_replay_driver._on_group` skips `raw_actions` when carrying frame keys onto the "
    "member row ('excluded only because the member row already holds it') and "
    "`native_clocks.member_clock_row`, which builds the row, returns no `raw_actions`. The "
    "exact member ledger carries no per-record message. The per-group delivery receipt names "
    "this layer under the member carrier, so the receipt over-claims."
)
INVENTORY_BOUND = (
    "BOUND TO THE INVENTORY DOCUMENT: the registry's only source path for this layer is the "
    "feed-inventory markdown, so today its producer is that document and its evidence hash "
    "proves the document was unchanged, not that any knowledge reached him. Another persona is "
    "rebinding the knowledge layers to the KEEP files of the source-file inventory; this record "
    "is updated when that lands."
)


def _record(kind: str, *, module: str | None = None, symbol: str | None = None,
            file: str | None = None, line: int | None = None, carrier: str, notes: str,
            **extra: Any) -> dict[str, Any]:
    if kind not in PRODUCER_KINDS:
        raise ValueError(f"unknown producer kind {kind!r}")
    record: dict[str, Any] = {
        "kind": kind, "module": module, "symbol": symbol, "file": file, "line": line,
        "carrier": carrier, "notes": notes,
    }
    record.update(extra)
    return record


def _row(*, module: str, symbol: str, file: str, line: int, carrier: str, notes: str,
         member_paths: tuple[str, ...] = (), lifecycle_sections: tuple[str, ...] = (),
         legacy_keys: tuple[str, ...] = (), ledgers: tuple[str, ...] = (MEMBER_LEDGER,),
         **extra: Any) -> dict[str, Any]:
    return _record("ROW_FIELD", module=module, symbol=symbol, file=file, line=line,
                   carrier=carrier, notes=notes, member_paths=member_paths,
                   lifecycle_sections=lifecycle_sections, legacy_keys=legacy_keys,
                   ledgers=ledgers, **extra)


def _ledger(*, module: str, symbol: str, file: str, line: int, carrier: str, notes: str,
            lifecycle_sections: tuple[str, ...] = (), legacy_keys: tuple[str, ...] = (),
            member_paths: tuple[str, ...] = (), ledgers: tuple[str, ...] = (LIFECYCLE_LEDGER,),
            **extra: Any) -> dict[str, Any]:
    return _record("LEDGER", module=module, symbol=symbol, file=file, line=line,
                   carrier=carrier, notes=notes, member_paths=member_paths,
                   lifecycle_sections=lifecycle_sections, legacy_keys=legacy_keys,
                   ledgers=ledgers, **extra)


def _inventory_bound(section_heading: str, line: int, notes: str = "") -> dict[str, Any]:
    return _record(
        "SECTION", module=None, symbol=section_heading, file=FEED_DOC, line=line,
        carrier=f"{FEED_DOC}#{section_heading}",
        notes=(INVENTORY_BOUND + (" " + notes if notes else "")),
        carrier_paths=(FEED_DOC,), bound_to_inventory_document=True,
    )


def _sealed(notes: str) -> dict[str, Any]:
    return _record(
        "SEALED_OBJECT", module="native_ingestion_layer_registry", symbol="SEALED_LAYER_IDS",
        file=REG, line=69, carrier="sealed_object_set(registry, repo_root): ABSENT from the prompt and every delivered path",
        notes=("SEALED_FOR_A_SCOPE (native_ingestion_layer_registry.SEALED_LAYER_IDS). The producer is the "
               "sealed object set this module derives; the proof is its ABSENCE from the emitted prompt and "
               "the delivered and knowledge path lists (prove_sealed_absent). " + notes),
    )


def _output(symbol_line: int, notes: str) -> dict[str, Any]:
    return _record(
        "PRINCIPAL_OUTPUT", module="native_principal_outputs", symbol=None, file=REGISTRY_JSON,
        line=symbol_line, carrier="his append-only ledger whose ledger id equals this layer id",
        notes=("Frankie's OUTPUT, his to write; not an input at pre-call. The output-ledger module "
               "is being built this session under ledger ids equal to the registry layer ids; an "
               "outputs receipt naming this id files it. " + notes),
    )


# --------------------------------------------------------------------------------------
# The table. Grouped as the registry groups them; every registry layer id appears once.
# --------------------------------------------------------------------------------------
LAYER_PRODUCERS: dict[str, dict[str, Any]] = {
    # ---- binding_common_controls (STATIC_REQUIRED_INPUT, both arms) ----------------------
    "controlling_rt_mission": _record(
        "FILE", module="native_a_arm_launch", symbol="MISSION_PATH", file=LAUNCH, line=76,
        carrier="research/kalshi/agents/frankie_native_raw_mbo_oct45_realtime_mission_20260828.md",
        carrier_paths=("research/kalshi/agents/frankie_native_raw_mbo_oct45_realtime_mission_20260828.md",),
        notes="The mission. Its sha256 is bound at launch (RunIdentity.mission_sha256) and re-checked and "
              "named in the spawn prompt by emit_frankie_spawn.emit; one of the two layers that reached him "
              "on run 33605852433. A knowledge receipt row is what marks it delivered.",
    ),
    "native_calculation_contract": _record(
        "FILE", module="native_a_arm_launch", symbol="CONTRACT_PATH", file=LAUNCH, line=79,
        carrier="research/kalshi/agents/frankie_native_raw_mbo_calculation_contract_20260828.md",
        carrier_paths=("research/kalshi/agents/frankie_native_raw_mbo_calculation_contract_20260828.md",),
        notes="The calculation contract. sha256 bound at launch and named in the spawn prompt; the second "
              "of the two layers that reached him.",
    ),
    "anchored_knowledge_manifest": _record(
        "FILE", module="native_a_arm_launch", symbol="KNOWLEDGE_MANIFEST_PATH", file=LAUNCH, line=82,
        carrier=KNOWLEDGE_MANIFEST, carrier_paths=(KNOWLEDGE_MANIFEST,),
        notes="Bound by hash only (RunIdentity.knowledge_manifest_hash from the manifest's manifest_hash); "
              "the spawn prompt never names it, so nothing has carried it to him.",
    ),
    "selected_same_arm_profile": _record(
        "FILE", module=None, symbol=None, file=KNOWLEDGE_DIR + "KNOWLEDGE_SOURCES_20260828.json", line=1,
        carrier=KNOWLEDGE_DIR + "KNOWLEDGE_SOURCES_20260828.json",
        carrier_paths=(KNOWLEDGE_DIR + "KNOWLEDGE_SOURCES_20260828.json",),
        notes="The profile file itself is the only producer: no module in the package reads "
              "KNOWLEDGE_SOURCES_20260828.json (searched the package for the file name) and the spawn prompt "
              "does not name it.",
    ),
    # ---- a_clean_overlay / a_memory_overlay (ARM_REQUIRED_INPUT) -------------------------
    "a_clean_promoted_positive_capsule": _record(
        "FILE", module=None, symbol="A_CLEAN_POSITIVE_KNOWLEDGE_20260828.md", file=KNOWLEDGE_MANIFEST, line=60,
        carrier=KNOWLEDGE_DIR + "A_CLEAN_POSITIVE_KNOWLEDGE_20260828.md",
        carrier_paths=(KNOWLEDGE_DIR + "A_CLEAN_POSITIVE_KNOWLEDGE_20260828.md",),
        notes="Named by the knowledge manifest (its only reader in the package); not named in the spawn "
              "prompt, so it has not reached him.",
    ),
    "a_memory_promoted_positive_capsule": _record(
        "FILE", module=None, symbol="A_MEMORY_POSITIVE_KNOWLEDGE_20260828.md", file=KNOWLEDGE_MANIFEST, line=76,
        carrier=KNOWLEDGE_DIR + "A_MEMORY_POSITIVE_KNOWLEDGE_20260828.md",
        carrier_paths=(KNOWLEDGE_DIR + "A_MEMORY_POSITIVE_KNOWLEDGE_20260828.md",),
        notes="Named by the knowledge manifest; A_MEMORY only; not named in the spawn prompt.",
    ),
    "a_memory_prior_lessons_package": _record(
        "RECEIPT", module="native_a_arm_launch", symbol="EXTERNAL_SOURCE_IDENTITIES", file=LAUNCH, line=86,
        carrier="external:a_memory_prior_lessons_package (pinned sha256, no repository bytes)",
        notes="An external identity the mission pins; evidence_receipt_sha256 substitutes the pinned hash "
              "for file bytes. A_MEMORY only. Nothing carries the package itself into a run.",
    ),
    "a_memory_prior_package_proof": _record(
        "RECEIPT", module="native_a_arm_launch", symbol="EXTERNAL_SOURCE_IDENTITIES", file=LAUNCH, line=86,
        carrier="external:a_memory_prior_lessons_package_proof (pinned sha256, no repository bytes)",
        notes="The proof receipt of the prior package, pinned the same way. A_MEMORY only.",
    ),
    # ---- current_brain_runtime (STATIC_REQUIRED_INPUT; all bound to the inventory doc) -----
    "authoritative_s135_construction": _inventory_bound("## 1. Current Frankie brain and runtime feed", 8),
    "complete_s105_9_brain": _inventory_bound(
        "## 1. Current Frankie brain and runtime feed", 8,
        "The real file is knowledge/ng_brain.json (s105.9, 90 plays); the registry does not name it.",
    ),
    "doctrine_reasoning_play_index_evidence": _inventory_bound("## 1. Current Frankie brain and runtime feed", 8),
    "lawful_prior_session_carry": _inventory_bound("## 1. Current Frankie brain and runtime feed", 8),
    "october_outcome_wall_enforcement": _inventory_bound("## 1. Current Frankie brain and runtime feed", 8),
    # ---- frozen_learned_structure (STATIC_REQUIRED_INPUT; all bound to the inventory doc) --
    "learned_d_structures_and_families": _inventory_bound("## 2. Frozen 54/55-week learned-structure feed", 18),
    "learned_dipoles_and_geometry": _inventory_bound("## 2. Frozen 54/55-week learned-structure feed", 18),
    "learned_pair_triplet_recurrence": _inventory_bound("## 2. Frozen 54/55-week learned-structure feed", 18),
    "learned_chains_extensions_reappearances_ancestry": _inventory_bound(
        "## 2. Frozen 54/55-week learned-structure feed", 18),
    "phase1_discoveries_structural_falsifiers": _inventory_bound("## 2. Frozen 54/55-week learned-structure feed", 18),
    "phase2_findings_modules_timing_pox_negatives": _inventory_bound(
        "## 2. Frozen 54/55-week learned-structure feed", 18),
    "predecessor_ancestry_unresolved_chain_state": _inventory_bound(
        "## 2. Frozen 54/55-week learned-structure feed", 18),
    "historical_timing_lifespan_context": _inventory_bound("## 2. Frozen 54/55-week learned-structure feed", 18),
    "learned_structure_proposal_index_material": _inventory_bound(
        "## 2. Frozen 54/55-week learned-structure feed", 18,
        "Greg 2026-09-02: the proposal lineage goes in WHOLE, its 'do not promote' language disregarded; "
        "every lesson carries VERIFIED / UNVERIFIED / REFUTED and only the refuted comes out.",
    ),
    # ---- corrected_extra_agent_carryforward (STATIC_REQUIRED_INPUT, three real files) -----
    "extra_agent_corrected_information_and_gap_diagnoses": _record(
        "FILE", module="native_ingestion_layer_registry", symbol="ALLOWED_V3_SOURCE_PATHS", file=REG, line=62,
        carrier="research/NG_EXHAUSTION_V3_EXTRA_AGENT_INFORMATION_FINDINGS_20260820.json + .md + "
                "research/NG_EXHAUSTION_V3_NONAUTHORITATIVE_RESULTS_EXTRA_AGENT_V4_CARRYFORWARD_20260820.md",
        carrier_paths=(
            "research/NG_EXHAUSTION_V3_EXTRA_AGENT_INFORMATION_FINDINGS_20260820.json",
            "research/NG_EXHAUSTION_V3_EXTRA_AGENT_INFORMATION_FINDINGS_20260820.md",
            "research/NG_EXHAUSTION_V3_NONAUTHORITATIVE_RESULTS_EXTRA_AGENT_V4_CARRYFORWARD_20260820.md",
        ),
        notes="The only v3-derived layer; its three paths are the registry's allowlist and are real files. "
              "Not named in the spawn prompt, so not yet carried to him.",
    ),
    # ---- canonical_raw_dbn_mbo (CAUSAL_STREAM_REQUIRED; member carrier) ------------------
    "canonical_sep_nov_2021_dbn_mbo_objects": _row(
        module="native_replay_driver", symbol="_source_day", file=DRV, line=305,
        carrier="source_day (+ raw_symbol, instrument_id); the roster identity is raw_mbo_source_manifest",
        member_paths=("source_day", "raw_symbol", "instrument_id"),
        notes="The row names its source day and instrument; the object roster is pinned by "
              "evidence_identity.source_manifest_hash. The PER-RECORD object name and sha256 "
              "(V4MboAdapter.normalize -> NormalizedMbo.source_dbn_object / source_dbn_sha256, on "
              "raw_actions) are dropped with raw_actions - see native_acmrtfn_messages.",
        structurally_absent=("raw_actions[].source_dbn_object", "raw_actions[].source_dbn_sha256"),
    ),
    "october_first_source_window": _row(
        module="raw_mbo_source_manifest", symbol="EXPECTED_ROSTER", file=ROSTER, line=33,
        carrier="source_day; the window [2021-10-01, 2021-11-01) is the roster's",
        member_paths=("source_day",),
        notes="EXPECTED_ROSTER fixes the four October days in stream order; the row carries the day.",
    ),
    "canonical_predecessor_bootstrap_objects": _row(
        module="ng_exhaustion_mbo_v4_state_adapter_20260820", symbol="event_frame", file=V4, line=722,
        carrier="snapshot_bootstrap_only, source_role",
        member_paths=("snapshot_bootstrap_only", "source_role"),
        notes="No predecessor object is traversed by the A-arm run: every roster day carries one role "
              "(SCORED_FINDINGS_DAY, native_replay_driver.identity_role; mission section 2). The frame says "
              "whether a group was snapshot bootstrap only. A predecessor bootstrap object, if one is ever "
              "added to the roster, would be identified by source_day / source_role.",
    ),
    "native_acmrtfn_messages": _row(
        module="ng_exhaustion_mbo_v4_state_adapter_20260820", symbol="NormalizedMbo.public_dict", file=V4, line=149,
        carrier="raw_actions[] (action, side, price_raw, size, order_id, flags, sequence, ts_event_ns, ts_recv_ns) - NOT ON THE ROW",
        notes=RAW_ACTIONS_DROP + " Surviving aggregates: structure.action_string, structure.action_counts, "
              "activity.<window>.action_count.",
        structurally_absent=("raw_actions[]", "raw_actions[].action", "raw_actions[].order_id"),
        aggregates_present=("structure.action_string", "structure.action_counts", "activity.*.action_count"),
    ),
    "snapshot_bootstrap_reset_messages": _row(
        module="native_full_capture_adapter", symbol="_observe_before", file=FCA, line=148,
        carrier="snapshot_bootstrap_only; capture_observations (book_clear*, tob_side_wipe*); integrity",
        member_paths=("snapshot_bootstrap_only", "capture_observations", "integrity"),
        notes="Snapshot-only groups are flagged on the frame (event_frame); an R clear is counted with what it "
              "destroyed by the capture wrapper. The per-record is_snapshot flag rides on raw_actions and is "
              "dropped with it.",
        structurally_absent=("raw_actions[].is_snapshot",),
    ),
    "raw_source_identity_provenance_clocks_integrity": _row(
        module="ng_exhaustion_mbo_v4_state_adapter_20260820", symbol="event_frame", file=V4, line=703,
        carrier="schema, adapter_revision, census_view, instrument_id, raw_symbol, publisher_id, channel_id, "
                "sequence, ts_event_ns, ts_recv_ns, ts_in_delta_ns, integrity",
        member_paths=("adapter_revision", "census_view", "publisher_id", "channel_id", "sequence",
                      "ts_event_ns", "ts_recv_ns", "ts_in_delta_ns", "integrity"),
        notes="The F_LAST record's identity and clocks plus the book's cumulative integrity counters. The "
              "per-record provenance (source_dbn_sha256) is on raw_actions and dropped with it.",
        structurally_absent=("raw_actions[].source_dbn_sha256",),
    ),
    # ---- order_lifecycle (CAUSAL_STREAM_REQUIRED; member carrier) -------------------------
    "order_lifecycle_adds": _row(
        module="ng_exhaustion_mbo_v4_state_adapter_20260820", symbol="_add_order", file=V4, line=415,
        carrier="raw_actions[] where action == A, with raw_actions[].book_effect - NOT ON THE ROW",
        notes=RAW_ACTIONS_DROP + " Surviving aggregates: structure.action_counts.A, activity.<window>.action_qty.A.",
        structurally_absent=("raw_actions[]",),
        aggregates_present=("structure.action_counts.A", "activity.*.action_qty.A"),
    ),
    "order_lifecycle_cancels": _row(
        module="ng_exhaustion_mbo_v4_state_adapter_20260820", symbol="_cancel", file=V4, line=433,
        carrier="raw_actions[] where action == C, with raw_actions[].book_effect (removed, size_delta) - NOT ON THE ROW",
        notes=RAW_ACTIONS_DROP + " Surviving aggregates: structure.action_counts.C, activity.<window>.action_qty.C, "
              "capture_observations.over_cancel*.",
        structurally_absent=("raw_actions[]",),
        aggregates_present=("structure.action_counts.C", "activity.*.action_qty.C"),
    ),
    "order_lifecycle_modifies": _row(
        module="ng_exhaustion_mbo_v4_state_adapter_20260820", symbol="_modify", file=V4, line=451,
        carrier="raw_actions[] where action == M, with raw_actions[].book_effect (priority_lost) - NOT ON THE ROW",
        notes=RAW_ACTIONS_DROP + " Surviving aggregates: structure.action_counts (M when present), "
              "activity.<window>.priority_lost_modify_count.",
        structurally_absent=("raw_actions[]",),
        aggregates_present=("structure.action_counts", "activity.*.priority_lost_modify_count"),
    ),
    "order_lifecycle_replaces": _row(
        module="ng_exhaustion_mbo_v4_state_adapter_20260820", symbol="_modify", file=V4, line=472,
        carrier="activity.<window>.priority_lost_modify_count (a replace is an M that loses priority: "
                "price change or size increase)",
        member_paths=("activity.*.priority_lost_modify_count",),
        notes="The feed has no distinct replace action (VALID_ACTIONS = ACMRTFN); a replace is a modify that "
              "re-queues, which _modify decides (priority_lost) and the activity windows count. The per-record "
              "priority_lost flag rides on raw_actions[].book_effect and is dropped with it.",
        structurally_absent=("raw_actions[].book_effect",),
    ),
    "order_lifecycle_trades": _row(
        module="ng_exhaustion_mbo_v4_state_adapter_20260820", symbol="_legacy_control_row", file=V4, line=744,
        carrier="legacy_observable_rows (one ten-level projection per T action) + activity.<window>.trade_*_aggressor_qty; "
                "raw_actions[] where action == T is NOT ON THE ROW",
        member_paths=("activity.*.trade_buy_aggressor_qty", "activity.*.trade_sell_aggressor_qty"),
        legacy_keys=("action", "price", "size", "ts_recv"),
        ledgers=(MEMBER_LEDGER, LEGACY_LEDGER),
        notes="Trades are the one action class whose per-record row survives, as the legacy ten-level projection "
              "the adapter emits per T (legacy_observable_rows). The native per-record T with its order id and "
              "flags is dropped with raw_actions.",
        structurally_absent=("raw_actions[]",),
        aggregates_present=("structure.action_counts.T",),
    ),
    "order_lifecycle_fills": _row(
        module="a_memory_member_first_recalculation_20260828", symbol="fill_disposition", file=STRUCT, line=176,
        carrier="structure.fill_disposition (filled / cancelled / modified / unresolved fill order ids); "
                "raw_actions[] where action == F is NOT ON THE ROW",
        member_paths=("structure.fill_disposition", "structure.fill_disposition.class",
                      "structure.fill_disposition.filled_order_ids"),
        notes="The group-level fill disposition survives on structure; the per-record F (F mutates nothing in this "
              "feed) is dropped with raw_actions.",
        structurally_absent=("raw_actions[]",),
        aggregates_present=("structure.action_counts.F",),
    ),
    "order_lifecycle_clears": _row(
        module="native_full_capture_adapter", symbol="_observe_before", file=FCA, line=148,
        carrier="capture_observations.book_clear / book_clear_orders_removed / book_clear_qty_removed; integrity_delta",
        member_paths=("capture_observations", "integrity_delta"),
        notes="An R clear is counted with the orders and quantity it destroyed (cumulative, on every row); "
              "the per-record R with cleared_orders / cleared_qty rides on raw_actions[].book_effect and is dropped.",
        structurally_absent=("raw_actions[].book_effect",),
    ),
    "order_identity_transitions": _row(
        module="a_memory_member_first_recalculation_20260828", symbol="describe_structure", file=STRUCT, line=187,
        carrier="structure.order_ids[], structure.distinct_order_id_count, structure.fill_disposition; "
                "integrity.duplicate_add_order_id / modify_side_change / modify_missing_treated_as_add",
        member_paths=("structure.order_ids[]", "structure.distinct_order_id_count", "structure.fill_disposition"),
        notes="Which order ids a group touched and how their fills resolved, per group. The per-record "
              "order_id sequence is on raw_actions and dropped with it.",
        structurally_absent=("raw_actions[].order_id",),
    ),
    "contract_session_roll_state": _row(
        module="native_replay_driver", symbol="ExchangeSessionRule", file=DRV, line=117,
        carrier="session_phase, continuity_segment (ExchangeSessionRule via member_clock_row); raw_symbol, instrument_id",
        member_paths=("session_phase", "continuity_segment", "raw_symbol", "instrument_id"),
        notes="Session phase and continuity segment are the exchange rule's on event time; the contract is "
              "instrument_id + raw_symbol. No explicit roll-state field exists: a run is one instrument-day.",
    ),
    # ---- full_book_fifo_queue (CAUSAL_STREAM_REQUIRED; member carrier) --------------------
    "full_bid_ask_depth": _row(
        module="native_full_capture_adapter", symbol="_enrich", file=FCA, line=184,
        carrier="book_full.bid_levels_full[] / ask_levels_full[] (whole book), book_full.bid_depth_full / ask_depth_full",
        member_paths=("book_full.bid_levels_full[]", "book_full.ask_levels_full", "book_full.bid_depth_full",
                      "book_full.ask_depth_full"),
        notes="book_snapshot(include_full_depth=True, include_order_ids=True) via the capture wrapper; the base "
              "frame's `book` is the ten-level projection. Restored under D61 by wrapping, not editing.",
    ),
    "price_level_and_order_counts": _row(
        module="ng_exhaustion_mbo_v4_state_adapter_20260820", symbol="book_snapshot", file=V4, line=676,
        carrier="book_full.bid_price_level_count_full / ask_price_level_count_full, bid_order_count_full / "
                "ask_order_count_full, book_full.bid_levels_full[].order_count",
        member_paths=("book_full.bid_price_level_count_full", "book_full.ask_price_level_count_full",
                      "book_full.bid_order_count_full", "book_full.ask_order_count_full",
                      "book_full.bid_levels_full[].order_count"),
        notes="Per side and per level, read off the book at F_LAST.",
    ),
    "fifo_queues": _row(
        module="ng_exhaustion_mbo_v4_state_adapter_20260820", symbol="InstrumentBook._level", file=V4, line=626,
        carrier="book_full.bid_levels_full[].fifo_queue[] (order_id, size, volume_ahead, priority_recv_ns, "
                "priority_sequence, priority_age_s)",
        member_paths=("book_full.bid_levels_full[].fifo_queue[].order_id",
                      "book_full.bid_levels_full[].fifo_queue[].size",
                      "book_full.bid_levels_full[].fifo_queue[].volume_ahead",
                      "book_full.bid_levels_full[].fifo_queue[].priority_recv_ns",
                      "book_full.bid_levels_full[].fifo_queue[].priority_sequence"),
        notes="The reconstructed FIFO queue at every level; include_order_ids=True is what the capture wrapper "
              "turns on (the base frame asserted fifo_priority_reconstructed while carrying none of it).",
    ),
    "queue_age_and_survival": _row(
        module="ng_exhaustion_mbo_v4_state_adapter_20260820", symbol="InstrumentBook._level", file=V4, line=620,
        carrier="book_full.bid_levels_full[].front_order_age_s / queue_age_median_s / queue_age_p90_s, "
                "fifo_queue[].priority_age_s; survival: lifecycle `queue` rows (4.6)",
        member_paths=("book_full.bid_levels_full[].front_order_age_s", "book_full.bid_levels_full[].queue_age_median_s",
                      "book_full.bid_levels_full[].queue_age_p90_s",
                      "book_full.bid_levels_full[].fifo_queue[].priority_age_s"),
        lifecycle_sections=("queue",), ledgers=(MEMBER_LEDGER, LIFECYCLE_LEDGER),
        notes="Ages are read off priority_recv_ns at F_LAST; survival terminals come from 4.6 "
              "(QueueGroupAdapter over native_rt_book.ReplayBook, advanced action by action).",
    ),
    "queue_concentration": _row(
        module="ng_exhaustion_mbo_v4_state_adapter_20260820", symbol="InstrumentBook._level", file=V4, line=624,
        carrier="book_full.bid_levels_full[].largest_order_share (+ front_order_size)",
        member_paths=("book_full.bid_levels_full[].largest_order_share", "book_full.bid_levels_full[].front_order_size"),
        notes="Largest resting order as a share of the level; the whole queue is beside it in fifo_queue.",
    ),
    "orders_and_volume_ahead": _row(
        module="ng_exhaustion_mbo_v4_state_adapter_20260820", symbol="InstrumentBook._level", file=V4, line=633,
        carrier="book_full.bid_levels_full[].fifo_queue[].volume_ahead (orders ahead = position in fifo_queue); "
                "at the instant an order rests: native_rt_book.ReplayBook.view_with_basis for 4.6",
        member_paths=("book_full.bid_levels_full[].fifo_queue[].volume_ahead",),
        notes="volume_ahead accumulates down the FIFO queue at F_LAST; the queue position at the instant of "
              "resting is computed by the replay book for 4.6 (lifecycle `queue` rows).",
    ),
    "spread_and_depth_imbalance": _row(
        module="ng_exhaustion_mbo_v4_state_adapter_20260820", symbol="book_snapshot", file=V4, line=665,
        carrier="book_full.spread / mid / depth_imbalance_n / depth_imbalance_full; book_regime.relative_imbalance",
        member_paths=("book_full.spread", "book_full.mid", "book_full.depth_imbalance_n",
                      "book_full.depth_imbalance_full", "book_regime.relative_imbalance"),
        notes="Spread and both imbalances at F_LAST; 4.2's book_regime snapshot repeats the full-book imbalance "
              "with a null where a side is absent.",
    ),
    "complete_state_reset_bootstrap_receipts": _row(
        module="native_full_capture_adapter", symbol="_enrich", file=FCA, line=191,
        carrier="integrity_delta (per group), capture_observations (cumulative), snapshot_bootstrap_only",
        member_paths=("integrity_delta", "capture_observations", "snapshot_bootstrap_only"),
        notes="Which group an R clear, a TOB side wipe or a snapshot bootstrap belongs to (integrity_delta) and "
              "what it destroyed (capture_observations).",
    ),
    # ---- microstructure_mechanics (CAUSAL_STREAM_REQUIRED; member carrier) ----------------
    "mechanics_actions_by_side_and_level": _row(
        module="ng_exhaustion_mbo_v4_state_adapter_20260820", symbol="_RollingActivityWindow.snapshot", file=V4, line=252,
        carrier="activity.<window>.action_count / action_qty / action_side_qty; activity_full.<window>.action_side_count / "
                "top_level_qty_by_action; structure.action_counts / side_counts",
        member_paths=("activity.*.action_count", "activity.*.action_qty", "activity.*.action_side_qty",
                      "activity_full.*.action_side_count", "activity_full.*.top_level_qty_by_action",
                      "structure.side_counts"),
        notes="By side, and by LEVEL only as top-of-book versus not (top_level_*). The window keys are the "
              "hardcoded ACTIVITY_WINDOWS_S (1, 5, 20, 60, 300) - see HARDCODED_WINDOWS; the row shape changes "
              "when the removal lands.",
    ),
    "aggressor_and_native_signed_flow": _row(
        module="ng_exhaustion_mbo_v4_state_adapter_20260820", symbol="_RollingActivityWindow.snapshot", file=V4, line=253,
        carrier="activity.<window>.trade_buy_aggressor_qty / trade_sell_aggressor_qty / trade_aggressor_imbalance; "
                "per second: lifecycle `flow_substrate` rows (window_signed_flow, polarity)",
        member_paths=("activity.*.trade_buy_aggressor_qty", "activity.*.trade_sell_aggressor_qty",
                      "activity.*.trade_aggressor_imbalance"),
        lifecycle_sections=("flow_substrate",), ledgers=(MEMBER_LEDGER, LIFECYCLE_LEDGER),
        notes="Aggressor side is the T's side (T_B buy, T_A sell) inside each window; the per-second signed flow "
              "is the roll20 binner's, fed to 4.0 (native_flow_substrate.complete_second).",
    ),
    "depletion_and_replenishment": _ledger(
        module="native_replay_driver", symbol="replenishment", file=DRV, line=1058,
        carrier="lifecycle `replenishment` rows (4.7 removals, refills, matured horizons); "
                "activity.<window>.top_level_cancel_qty_derived",
        lifecycle_sections=("replenishment",), member_paths=("activity.*.top_level_cancel_qty_derived",),
        ledgers=(LIFECYCLE_LEDGER, MEMBER_LEDGER),
        notes="4.7 observes removals and refills per group and matures its horizon in stream time "
              "(replenishment_horizon_ns=60 s at launch - a hardcoded horizon, see HARDCODED_WINDOWS).",
    ),
    "resilience_and_recovery": _ledger(
        module="native_replay_driver", symbol="absorption", file=DRV, line=1233,
        carrier="lifecycle `replenishment` (time-to-restoration) and `absorption` (4.8 runways) rows",
        lifecycle_sections=("replenishment", "absorption"),
        notes="Restoration after a removal (4.7) and absorption runways (4.8), both closed at their own boundaries.",
    ),
    "churn_and_queue_turnover": _row(
        module="ng_exhaustion_mbo_v4_state_adapter_20260820", symbol="_RollingActivityWindow.snapshot", file=V4, line=265,
        carrier="activity.<window>.add_cancel_churn / priority_lost_modify_count / event_count",
        member_paths=("activity.*.add_cancel_churn", "activity.*.priority_lost_modify_count", "activity.*.event_count"),
        notes="Cancel quantity over add-plus-cancel quantity, per hardcoded window.",
    ),
    "price_and_book_path": _row(
        module="native_book_regime", symbol="observe_snapshot", file=BRG, line=225,
        carrier="book_full.best_bid / best_ask / mid; book_regime.* (4.2 per group); structure.price_raw_min / "
                "price_raw_max / price_raw_span; lifecycle `ladder` rows (4.9)",
        member_paths=("book_full.best_bid", "book_full.best_ask", "book_full.mid", "book_regime.best_bid",
                      "book_regime.total_depth", "structure.price_raw_span"),
        lifecycle_sections=("ladder",), ledgers=(MEMBER_LEDGER, LIFECYCLE_LEDGER),
        notes="The touch and depth at every F_LAST, the group's own price span, and 4.9's ladder transitions.",
    ),
    "missingness_and_integrity_flags": _row(
        module="native_full_capture_adapter", symbol="_observe_before", file=FCA, line=127,
        carrier="integrity, integrity_delta, capture_observations (sequence_gap*, over_cancel*, book_clear*, "
                "tob_side_wipe*), activity_full.<window>.receive_order_clean, activity.<window>.missing_reference_count, "
                "sequence_contiguous",
        member_paths=("integrity", "integrity_delta", "capture_observations", "activity_full.*.receive_order_clean",
                      "activity.*.missing_reference_count", "sequence_contiguous"),
        notes="Cumulative counters from the locked book, per-group deltas and anomaly magnitudes from the capture "
              "wrapper, sequence contiguity from the clock row.",
    ),
    # ---- legacy_observable_crosswalk (CAUSAL_STREAM_REQUIRED; LEGACY carrier) -------------
    "legacy_price": _ledger(
        module="ng_exhaustion_mbo_v4_state_adapter_20260820", symbol="_legacy_control_row", file=V4, line=768,
        carrier="legacy_observable_rows[].price, bid_px_00, ask_px_00 (per T action and at group end)",
        legacy_keys=("price", "bid_px_00", "ask_px_00"), ledgers=(LEGACY_LEDGER,),
        notes="The ten-level MBP-10 projection the adapter emits; the legacy price surface the 54/55-week "
              "structures were learned on.",
    ),
    "legacy_native_signed_flow": _ledger(
        module="native_roll20", symbol="NATIVE_SOURCE_FIELDS", file=ROLL, line=50,
        carrier="legacy_observable_rows[].action / price / size / bid_px_00 / ask_px_00 / ts_recv -> per-second "
                "buy and sell volume by touch (SecondBinner); lifecycle `flow_substrate` rows",
        legacy_keys=("action", "price", "size", "bid_px_00", "ask_px_00", "ts_recv"),
        lifecycle_sections=("flow_substrate",), ledgers=(LEGACY_LEDGER, LIFECYCLE_LEDGER),
        notes="Signed by which touch a trade printed at, on the declared clock (RECV_CLOCK).",
    ),
    "legacy_per_second_roll20": _ledger(
        module="native_roll20", symbol="roll20", file=ROLL, line=222,
        carrier="lifecycle `flow_substrate` rows (roll20_value per completed second) computed from the legacy rows",
        legacy_keys=("action", "size", "ts_recv"), lifecycle_sections=("flow_substrate",),
        ledgers=(LEGACY_LEDGER, LIFECYCLE_LEDGER),
        notes="(b - s) / (b + s) over a trailing DEFAULT_WINDOW = 20 seconds - a LEGACY observable by definition, "
              "flagged as such in HARDCODED_WINDOWS rather than as a horizon.",
    ),
    "legacy_book_imbalance": _ledger(
        module="ng_exhaustion_mbo_v4_state_adapter_20260820", symbol="_legacy_control_row", file=V4, line=777,
        carrier="legacy_observable_rows[].bid_sz_00..09 / ask_sz_00..09 / bid_ct_00..09 / ask_ct_00..09",
        legacy_keys=("bid_sz_00", "ask_sz_00", "bid_ct_00", "ask_ct_00", "bid_sz_09", "ask_sz_09"),
        ledgers=(LEGACY_LEDGER,),
        notes="The ten-level ladder; the driver's own test records that this layer cannot be computed from "
              "anything else the traversal keeps.",
    ),
    "legacy_structure_observables": _row(
        module="a_memory_member_first_recalculation_20260828", symbol="describe_structure", file=STRUCT, line=170,
        carrier="structure.candidate_family_id / action_string / side_string / discovery_status / "
                "matches_carried_native_family / mirror (member row); lifecycle `lineage` and `episode` rows",
        member_paths=("structure.candidate_family_id", "structure.action_string", "structure.discovery_status",
                      "structure.matches_carried_native_family", "structure.mirror.orientation"),
        lifecycle_sections=("lineage", "episode"), fixture_dependent_sections=("episode",),
        ledgers=(MEMBER_LEDGER, LIFECYCLE_LEDGER),
        notes="D/dipole/family/chain/predecessor observables ride on the MEMBER row and the lifecycle ledger, "
              "while native_causal_stream.LAYER_CARRIERS declares the legacy_observable_crosswalk group carried by "
              "the LEGACY lines only - the receipt hashes the wrong bytes for this layer.",
    ),
    # ---- derived_geometry (CAUSAL_STREAM_REQUIRED; member + lifecycle carriers) -----------
    "derived_roll20_and_dipole_state": _ledger(
        module="native_flow_substrate", symbol="complete_second", file=FLOW, line=428,
        carrier="lifecycle `flow_substrate` rows (roll20_value, window_signed_flow, polarity per second); "
                "dipole state: lifecycle `episode` rows (4.12)",
        lifecycle_sections=("flow_substrate", "episode"), fixture_dependent_sections=("episode",),
        notes="Per-second roll20 and polarity for every completed second; the dipole runway state exists only "
              "once a candidate opens an episode (needs the candidate lane's 900 s warmup and real flow).",
    ),
    "derived_d_family_geometry": _row(
        module="a_memory_member_first_recalculation_20260828", symbol="describe_structure", file=STRUCT, line=200,
        carrier="structure.candidate_family_id / action_string / side_string / mirror.*; lifecycle `lineage` rows (4.13)",
        member_paths=("structure.candidate_family_id", "structure.side_string", "structure.mirror.orientation",
                      "structure.mirror.mirror_pair_key"),
        lifecycle_sections=("lineage",), ledgers=(MEMBER_LEDGER, LIFECYCLE_LEDGER),
        notes="The canonical family descriptor hashed into candidate_family_id, and D-depth lineage from 4.13.",
    ),
    "derived_open_world_predecessor_state": _row(
        module="a_memory_member_first_recalculation_20260828", symbol="describe_structure", file=STRUCT, line=207,
        carrier="structure.discovery_status (CARRIED_SEED_MATCH | OPEN_WORLD_CANDIDATE), "
                "structure.carried_native_family; result layers.open_world_indexes",
        member_paths=("structure.discovery_status", "structure.carried_native_family",
                      "structure.matches_carried_native_family"),
        notes="Whether a group matched a carried native family or is novel, per group.",
    ),
    "derived_ancestry_gaps": _ledger(
        module="native_replay_driver", symbol="LineageGraph", file=DRV, line=451,
        carrier="lifecycle `lineage` rows (4.13, ORDER_ID_LINEAGE_V1) and `recurrence` rows (4.14 gaps)",
        lifecycle_sections=("lineage", "recurrence"),
        notes="Lineage is rebuilt at every continuity boundary (LINEAGE_SEGMENT_SCOPE); gaps come from 4.14.",
    ),
    "derived_unresolved_age_chain_trajectory": _ledger(
        module="native_replay_driver", symbol="_retain_episode_rows", file=DRV, line=788,
        carrier="lifecycle `lineage` rows (still-open lineages) and `episode` rows (4.10 exhaustion state)",
        lifecycle_sections=("lineage", "episode"), fixture_dependent_sections=("episode",),
        notes="Chain trajectory lives in 4.13's open lineages and 4.10's episode phases; episodes need a candidate.",
    ),
    "derived_price_flow_book_paths": _row(
        module="native_book_regime", symbol="observe_snapshot", file=BRG, line=168,
        carrier="book_regime.* per group; book_full.best_bid / mid; lifecycle `flow_substrate` and `ladder` rows",
        member_paths=("book_regime.best_bid", "book_regime.total_depth", "book_regime.order_count", "book_full.mid"),
        lifecycle_sections=("flow_substrate", "ladder"), ledgers=(MEMBER_LEDGER, LIFECYCLE_LEDGER),
        notes="Book path per F_LAST (4.2), flow path per second (4.0), ladder transitions (4.9).",
    ),
    "derived_v4_mechanics_fifo_features": _row(
        module="native_full_capture_adapter", symbol="_window_extras", file=FCA, line=201,
        carrier="activity_full.<window>.* ; book_full.bid_levels_full[].fifo_queue[]; capture_observations; "
                "lifecycle `queue` rows (4.6)",
        member_paths=("activity_full.*.top_level_qty_by_action", "activity_full.*.action_side_count",
                      "book_full.bid_levels_full[].fifo_queue[]", "capture_observations"),
        lifecycle_sections=("queue",), ledgers=(MEMBER_LEDGER, LIFECYCLE_LEDGER),
        notes="Everything the V4 adapter computed and discarded, restored by the capture wrapper.",
    ),
    "derived_feature_availability_timestamps": _row(
        module="native_clocks", symbol="member_clock_row", file=CLK, line=202,
        carrier="clocks.first_lawful_availability_ns, causal_availability_clock (member); lifecycle rows: the "
                "delivery-time rule native_causal_stream.lifecycle_availability, NOT a stamped field",
        member_paths=("clocks.first_lawful_availability_ns", "causal_availability_clock"),
        notes="One availability stamp per member group (= F_LAST ts_recv_ns). No per-FEATURE timestamp exists; "
              "lifecycle rows carry no uniform stamp and are placed by a declared rule at delivery.",
    ),
    # ---- prebirth_opportunity (CAUSAL_STREAM_REQUIRED; lifecycle carriers) ----------------
    "prebirth_predecessor_at_risk_state": _ledger(
        module="native_replay_driver", symbol="_open_candidate", file=DRV, line=737,
        carrier="lifecycle `episode` rows (4.10 exhaustion state, 4.12 dipole runway) opened at a candidate's "
                "available_second",
        lifecycle_sections=("episode", "candidate"), fixture_dependent_sections=("episode", "candidate"),
        notes="Exists only when the candidate lane fires (CausalPeakDetector: warmup_seconds=900, "
              "min_threshold_observations=600 - hardcoded, see HARDCODED_WINDOWS). Absent on a short fixture; "
              "the Sunday run decides whether any row exists.",
    ),
    "prebirth_unresolved_chain_extension_state": _ledger(
        module="native_replay_driver", symbol="LineageGraph", file=DRV, line=451,
        carrier="lifecycle `lineage` rows (open, extended, censored lineages)",
        lifecycle_sections=("lineage",),
        notes="4.13's open lineages are the unresolved chain-extension state as of each group.",
    ),
    "prebirth_ancestry_successor_opportunity": _ledger(
        module="native_replay_driver", symbol="LINEAGE_SIGNATURE", file=DRV, line=151,
        carrier="lifecycle `lineage` rows: a group's initiating order id parents the ids it touched first",
        lifecycle_sections=("lineage",),
        notes="Ancestry by order-id lineage (ORDER_ID_LINEAGE_V1), one continuity segment at a time.",
    ),
    "prebirth_stopped_chain_false_context_controls": _ledger(
        module="native_recognition", symbol="note_failed_state", file=RECOG, line=80,
        carrier="lifecycle `episode` rows carrying 4.11 failed_states; `detector_coverage` rows (4.0b rejections)",
        lifecycle_sections=("detector_coverage", "episode"), fixture_dependent_sections=("episode",),
        notes="Earlier ambiguous or refuted causal states are kept on the recognition record; detector rejections "
              "are accounted per second by 4.0b.",
    ),
    "prebirth_negative_opportunity_cases": _ledger(
        module="native_recognition", symbol="mark_missed", file=RECOG, line=102,
        carrier="lifecycle `episode` rows with MISSED / CENSORED outcomes (4.11) and `detector_coverage` rows",
        lifecycle_sections=("detector_coverage", "episode"), fixture_dependent_sections=("episode",),
        notes="Every candidate counts, detected or not; the population report never returns a detected-only mean.",
    ),
    # ---- causal_clocks (CAUSAL_STREAM_REQUIRED; member carrier) ---------------------------
    "clock_event_time": _row(
        module="native_clocks", symbol="member_clock_row", file=CLK, line=199,
        carrier="clocks.first_component_ts_event_ns; ts_event_ns (F_LAST record); receipt clocks.event_time_ns",
        member_paths=("clocks.first_component_ts_event_ns", "ts_event_ns"),
        notes="The exchange's event time of the first and last component of the group.",
    ),
    "clock_receive_time": _row(
        module="native_clocks", symbol="member_clock_row", file=CLK, line=200,
        carrier="clocks.first_component_ts_recv_ns, clocks.f_last_ts_recv_ns; ts_recv_ns; receipt clocks.receive_time_ns",
        member_paths=("clocks.first_component_ts_recv_ns", "clocks.f_last_ts_recv_ns", "ts_recv_ns"),
        notes="The causal clock the whole traversal orders on.",
    ),
    "clock_event_known_by": _row(
        module="native_clocks", symbol="member_clock_row", file=CLK, line=202,
        carrier="clocks.first_lawful_availability_ns (= clocks.f_last_ts_recv_ns); receipt clocks.availability_time_ns",
        member_paths=("clocks.first_lawful_availability_ns", "clocks.f_last_ts_recv_ns"),
        notes="A group is knowable when its F_LAST is received, so event-known-by is the F_LAST receive clock. "
              "IDENTICAL BY CONSTRUCTION to the feature-availability clock (both are f_last_recv); no distinct "
              "per-record event-known-by exists.",
    ),
    "clock_feature_availability": _row(
        module="native_clocks", symbol="member_clock_row", file=CLK, line=202,
        carrier="clocks.first_lawful_availability_ns (member features); candidate rows: available_second; other "
                "lifecycle rows: native_causal_stream.lifecycle_availability at delivery",
        member_paths=("clocks.first_lawful_availability_ns",),
        notes="Covers the member row's own features with one stamp. Candidate rows carry available_second "
              "(native_candidate.Candidate); every other lifecycle row is placed by a delivery-time rule and "
              "carries no stamp of its own. Partial.",
    ),
    "clock_prospective_discovery_confirmation": _ledger(
        module="native_recognition", symbol="record_call", file=RECOG, line=83,
        carrier="lifecycle `episode` rows: recognized_recv_ns (first lawful call) and precursor_recv_ns; "
                "`candidate` rows: available_second. NOT on the member row the receipt names for this group",
        lifecycle_sections=("episode", "candidate"), fixture_dependent_sections=("episode", "candidate"),
        notes="Discovery time is the first lawful call (record_call, never overwritten) and the candidate's "
              "available_second. No distinct CONFIRMATION time is produced anywhere. LAYER_CARRIERS declares the "
              "causal_clocks group carried by the member line, which has no such field: the receipt over-claims.",
    ),
    "clock_model_evaluation": _row(
        module="native_clocks", symbol="member_clock_row", file=CLK, line=203,
        carrier="clocks.decision_ts_recv_ns with decision_basis (REPLAY_EARLIEST_LAWFUL_AVAILABILITY by default); "
                "receipt clocks.decision_time_ns",
        member_paths=("clocks.decision_ts_recv_ns", "decision_basis", "f_last_to_decision_delay_ns"),
        notes="A CONVENTION, not an observation: no caller passes an observed decision time, so the row adopts "
              "F_LAST as the decision instant (delay 0) and says so in decision_basis. An observed "
              "model-evaluation time - when Frankie actually evaluated the group - has no producer today.",
    ),
    "clock_lock_time": _record(
        "NO_PRODUCER_FOUND", module=None, symbol=None, file=None, line=None,
        carrier="none in the ingestion path; lock time is Frankie's OUTPUT",
        notes="Lock time is the instant Frankie files a first lock or no-lock, which is his output ledger "
              "output_first_locks_and_no_locks (being built this session). Searched native_clocks (five clock "
              "fields, none a lock), native_causal_stream (four receipt clock keys, none a lock), "
              "native_recognition (recognition, not lock), native_replay_driver (invocation cutoffs, not locks) and "
              "the registry validator: no input producer exists and none should.",
        ledgers=(), member_paths=(),
    ),
    # ---- sealed_target_timing + sealed_step1_answer (SEALED_FOR_A_SCOPE) ------------------
    "later_outcome_reveal": _sealed("The later realized outcome, revealed only after his outputs freeze (D68)."),
    "target_ground_truth_onset_time": _sealed("Answer-derived onset time, distinct from any causal candidate onset."),
    "step1_existing_october_seconds": _sealed("Step-1 October seconds (the shard .seconds.jsonl.gz objects)."),
    "step1_populations": _sealed("Step-1 populations (V4_NATIVE_FULL_POPULATION / LEGACY_CONTROL_POPULATION)."),
    "step1_crosswalks": _sealed("Step-1 crosswalks (DUAL_CENSUS_CROSSWALK, *_CROSSWALK_INDEX)."),
    "step1_target_membership_receipts": _sealed("Receipts that reveal target membership (STEP1_DUAL_CENSUS_RECEIPT)."),
    "step1_labels_and_classifications": _sealed("Step-1 labels and classifications."),
    "step1_result_prefixes": _sealed("The S3 result prefixes under nymex/ng_mbo_5y_v0/step1_census/."),
    "step1_reconciliation_outputs": _sealed("Step-1 reconciliation outputs (overlap mismatches, finalizer results)."),
    # ---- provisional_shadow (PROVISIONAL_SHADOW) -----------------------------------------
    "s137_cognitive_shadow_runtime": _record(
        "SHADOW", module="frankie_s137_cognitive_runtime", symbol=None,
        file="research/kalshi/frankie_s137_cognitive_runtime.py", line=1,
        carrier="none: SHADOW_DISABLED, nothing opts it in",
        notes="D5 keeps discovery out of the run; native_a_arm_launch.build_pre_call_receipt stamps SHADOW_DISABLED.",
    ),
    "hipporag_associative_retrieval": _record(
        "SHADOW", module="frankie_hipporag_p0_retrieval", symbol=None,
        file="research/kalshi/frankie_hipporag_p0_retrieval.py", line=1,
        carrier="none: SHADOW_DISABLED, nothing opts it in",
        notes="D5; SHADOW_DISABLED on every run to date.",
    ),
    # ---- append_only_outputs (APPEND_ONLY_OUTPUT): his to write --------------------------
    "output_state_and_state_delta_movie": _output(283, "State and state-delta movie with book and FIFO per cutoff."),
    "output_frankie_reasoning_movie": _output(287, "His reasoning movie."),
    "output_probability_movie": _output(291, "His probability movie."),
    "output_candidate_discoveries": _output(295, "Candidate discoveries."),
    "output_first_locks_and_no_locks": _output(299, "First locks and no-locks; the lock-time clock lives here."),
    "output_negative_sparse_inconclusive_ledger": _output(303, "Abstentions, negatives, sparse and inconclusive cases."),
    "output_knowledge_retrieval_receipts": _output(307, "Knowledge retrieval receipts."),
    "output_provider_invocation_response_receipts": _output(311, "Provider invocation and response receipts."),
    "output_answer_wall_access_receipts": _output(315, "Answer-wall no-access receipts; must be empty and say so."),
    "output_source_state_manifest_code_model_run_hashes": _output(319, "Source, state, manifest, code, model and run hashes."),
}


# --------------------------------------------------------------------------------------
# The seven clocks against the code as it is. Expected to change at merge.
# --------------------------------------------------------------------------------------
SEVEN_CLOCKS: dict[str, dict[str, Any]] = {
    "clock_event_time": {
        "clock": "event time", "producer": True,
        "row_fields": ("clocks.first_component_ts_event_ns", "ts_event_ns"),
        "receipt_key": "event_time_ns", "coverage": "FULL: exchange event time of first and last component",
    },
    "clock_receive_time": {
        "clock": "receive time", "producer": True,
        "row_fields": ("clocks.first_component_ts_recv_ns", "clocks.f_last_ts_recv_ns", "ts_recv_ns"),
        "receipt_key": "receive_time_ns", "coverage": "FULL: the traversal's causal clock",
    },
    "clock_event_known_by": {
        "clock": "event_known_by", "producer": True,
        "row_fields": ("clocks.first_lawful_availability_ns",),
        "receipt_key": "availability_time_ns",
        "coverage": "FULL AT GROUP LEVEL, but identical by construction to feature availability (both = F_LAST ts_recv_ns)",
    },
    "clock_feature_availability": {
        "clock": "feature availability", "producer": True,
        "row_fields": ("clocks.first_lawful_availability_ns",),
        "receipt_key": "availability_time_ns",
        "coverage": "PARTIAL: one stamp per member group; candidate rows carry available_second; other lifecycle "
                    "rows are placed by a delivery-time rule and carry no stamp",
    },
    "clock_prospective_discovery_confirmation": {
        "clock": "prospective discovery / confirmation", "producer": True,
        "row_fields": (), "receipt_key": None,
        "coverage": "DISCOVERY ONLY, off the member row: episode rows recognized_recv_ns (first lawful call) and "
                    "candidate available_second; no confirmation time is produced; the receipt's member carrier "
                    "does not hold it",
    },
    "clock_model_evaluation": {
        "clock": "model evaluation", "producer": True,
        "row_fields": ("clocks.decision_ts_recv_ns",), "receipt_key": "decision_time_ns",
        "coverage": "BY CONVENTION ONLY: decision_basis REPLAY_EARLIEST_LAWFUL_AVAILABILITY adopts F_LAST as the "
                    "decision instant (delay 0); no observed evaluation time exists",
    },
    "clock_lock_time": {
        "clock": "lock time", "producer": False,
        "row_fields": (), "receipt_key": None,
        "coverage": "NONE: Frankie's output (output_first_locks_and_no_locks); no input producer exists",
    },
}


# --------------------------------------------------------------------------------------
# Helpers used by the tests and by the crosswalk
# --------------------------------------------------------------------------------------
def registry_layers(registry: Mapping[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    """layer_id -> {"group": group, "entry": entry}, read off the registry. Never a literal count."""
    active = load_registry() if registry is None else registry
    out: dict[str, dict[str, Any]] = {}
    for group in active["groups"]:
        for entry in group["entries"]:
            out[entry["layer_id"]] = {"group": group, "entry": entry}
    return out


def _pattern_regex(pattern: str) -> re.Pattern[str]:
    """`*` matches exactly one path segment, so a window key is never written into a citation.
    Brackets are literal: `[]` is the census's list marker, not a character class."""
    parts = [re.escape(part) for part in pattern.split("*")]
    return re.compile("^" + "[^.]+".join(parts) + "$")


def path_present(pattern: str, paths: Iterable[str]) -> bool:
    if "*" not in pattern:
        return pattern in set(paths)
    regex = _pattern_regex(pattern)
    return any(regex.match(path) for path in paths)
