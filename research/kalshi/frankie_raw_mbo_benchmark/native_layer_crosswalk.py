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
        aggregates_present=("structure.action_string", "structure.action_counts", "activity_since.*.action_count"),
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
        aggregates_present=("structure.action_counts.A", "activity_since.*.action_qty.A"),
    ),
    "order_lifecycle_cancels": _row(
        module="ng_exhaustion_mbo_v4_state_adapter_20260820", symbol="_cancel", file=V4, line=433,
        carrier="raw_actions[] where action == C, with raw_actions[].book_effect (removed, size_delta) - NOT ON THE ROW",
        notes=RAW_ACTIONS_DROP + " Surviving aggregates: structure.action_counts.C, activity.<window>.action_qty.C, "
              "capture_observations.over_cancel*.",
        structurally_absent=("raw_actions[]",),
        aggregates_present=("structure.action_counts.C", "activity_since.*.action_qty.C"),
    ),
    "order_lifecycle_modifies": _row(
        module="ng_exhaustion_mbo_v4_state_adapter_20260820", symbol="_modify", file=V4, line=451,
        carrier="raw_actions[] where action == M, with raw_actions[].book_effect (priority_lost) - NOT ON THE ROW",
        notes=RAW_ACTIONS_DROP + " Surviving aggregates: structure.action_counts (M when present), "
              "activity.<window>.priority_lost_modify_count.",
        structurally_absent=("raw_actions[]",),
        aggregates_present=("structure.action_counts", "activity_since.*.priority_lost_modify_count"),
    ),
    "order_lifecycle_replaces": _row(
        module="ng_exhaustion_mbo_v4_state_adapter_20260820", symbol="_modify", file=V4, line=472,
        carrier="activity.<window>.priority_lost_modify_count (a replace is an M that loses priority: "
                "price change or size increase)",
        member_paths=("activity_since.*.priority_lost_modify_count",),
        notes="The feed has no distinct replace action (VALID_ACTIONS = ACMRTFN); a replace is a modify that "
              "re-queues, which _modify decides (priority_lost) and the activity windows count. The per-record "
              "priority_lost flag rides on raw_actions[].book_effect and is dropped with it.",
        structurally_absent=("raw_actions[].book_effect",),
    ),
    "order_lifecycle_trades": _row(
        module="ng_exhaustion_mbo_v4_state_adapter_20260820", symbol="_legacy_control_row", file=V4, line=744,
        carrier="legacy_observable_rows (one ten-level projection per T action) + activity.<window>.trade_*_aggressor_qty; "
                "raw_actions[] where action == T is NOT ON THE ROW",
        member_paths=("activity_since.*.trade_buy_aggressor_qty", "activity_since.*.trade_sell_aggressor_qty"),
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
        member_paths=("activity_since.*.action_count", "activity_since.*.action_qty", "activity_since.*.action_side_qty",
                      "activity_since.*.action_side_count", "activity_since.*.top_level_qty_by_action",
                      "structure.side_counts"),
        notes="By side, and by LEVEL only as top-of-book versus not (top_level_*). The window keys are the "
              "hardcoded ACTIVITY_WINDOWS_S (1, 5, 20, 60, 300) - see HARDCODED_WINDOWS; the row shape changes "
              "when the removal lands.",
    ),
    "aggressor_and_native_signed_flow": _row(
        module="ng_exhaustion_mbo_v4_state_adapter_20260820", symbol="_RollingActivityWindow.snapshot", file=V4, line=253,
        carrier="activity.<window>.trade_buy_aggressor_qty / trade_sell_aggressor_qty / trade_aggressor_imbalance; "
                "per second: lifecycle `flow_substrate` rows (window_signed_flow, polarity)",
        member_paths=("activity_since.*.trade_buy_aggressor_qty", "activity_since.*.trade_sell_aggressor_qty",
                      "activity_since.*.trade_aggressor_imbalance"),
        lifecycle_sections=("flow_substrate",), ledgers=(MEMBER_LEDGER, LIFECYCLE_LEDGER),
        notes="Aggressor side is the T's side (T_B buy, T_A sell) inside each window; the per-second signed flow "
              "is the roll20 binner's, fed to 4.0 (native_flow_substrate.complete_second).",
    ),
    "depletion_and_replenishment": _ledger(
        module="native_replay_driver", symbol="replenishment", file=DRV, line=1058,
        carrier="lifecycle `replenishment` rows (4.7 removals, refills, matured horizons); "
                "activity.<window>.top_level_cancel_qty_derived",
        lifecycle_sections=("replenishment",), member_paths=("activity_since.*.top_level_cancel_qty_derived",),
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
        member_paths=("activity_since.*.add_cancel_churn", "activity_since.*.priority_lost_modify_count", "activity_since.*.event_count"),
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
        member_paths=("integrity", "integrity_delta", "capture_observations", "activity_since.*.receive_order_clean",
                      "activity_since.*.missing_reference_count", "sequence_contiguous"),
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
        member_paths=("activity_since.*.top_level_qty_by_action", "activity_since.*.action_side_count",
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


# ======================================================================================
# Slice 2: the computed crosswalk. STATUS IS COMPUTED, NEVER READ OFF THE POLICY.
# ======================================================================================
import argparse  # noqa: E402
import contextlib  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402

from research.kalshi.frankie_raw_mbo_benchmark.fetch_frankie_ledgers import (  # noqa: E402
    LEDGER_FILES,
    RECEIPT_SCHEMA as DELIVERY_RECEIPT_SCHEMA,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_causal_stream import (  # noqa: E402
    LAYER_CARRIERS,
    STREAM_RECEIPT_SCHEMA,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import (  # noqa: E402
    ALLOWED_ARMS,
    canonical_hash,
)

CROSSWALK_SCHEMA = "FRANKIE_NATIVE_RAW_MBO_LAYER_CROSSWALK_V1"
KNOWLEDGE_RECEIPT_SCHEMA = "FRANKIE_KNOWLEDGE_DELIVERY_RECEIPT_V1"
OUTPUTS_RECEIPT_SCHEMA = "FRANKIE_NATIVE_RAW_MBO_PRINCIPAL_OUTPUTS_RECEIPT_V1"
SEALED_PROOF_SCHEMA = "FRANKIE_SEALED_ABSENCE_PROOF_V1"

INPUT_POLICIES = frozenset({"STATIC_REQUIRED_INPUT", "ARM_REQUIRED_INPUT", "CAUSAL_STREAM_REQUIRED"})
"""The policies whose layers are INPUTS to the principal; the spawn gate is over these."""

STATUS_MEANING: dict[str, str] = {
    "DELIVERED": "a receipt row names this layer's carrier AND the carrier is present in the run (field census, "
                 "lifecycle section rows or legacy rows); for static layers, a knowledge receipt row DELIVERED with files",
    "RECEIPTED_CARRIER_ABSENT": "a VERIFIED receipt names this layer, and the run's own evidence shows the cited carrier "
                                "is not there - the receipt over-claims (a structural drop, or 0 rows on this run)",
    "BOUND_TO_INVENTORY_DOCUMENT": "the layer's only source path is the feed-inventory markdown; a named defect, never DELIVERED",
    "PRODUCED_NOT_DELIVERED": "a producer exists and no VERIFIED receipt covers this layer on this run",
    "NO_PRODUCER_FOUND": "nothing in the ingestion path produces it; the record says what was searched",
    "SEALED_PROVEN": "a sealed-absence proof with all_absent true covers the run",
    "SEALED_UNPROVEN": "no sealed-absence proof, or one that found a token",
    "SHADOW_DISABLED": "PROVISIONAL_SHADOW and nothing opts it in (D5)",
    "OUTPUT_PENDING": "his output ledger; not named by an outputs receipt",
    "OUTPUT_FILED": "his output ledger, named by an outputs receipt",
    "NOT_APPLICABLE": "the arm is not in the layer's group arms",
}
STATUSES = frozenset(STATUS_MEANING)

LEDGER_TO_CARRIER = {MEMBER_LEDGER: "member", LIFECYCLE_LEDGER: "lifecycle", LEGACY_LEDGER: "legacy"}
"""Ledger name -> the carrier vocabulary native_causal_stream.LAYER_CARRIERS declares in."""

#: How a pre-call policy stamp and a computed status relate. A stamp AGREES with the computed
#: status only when the measurement would have justified it; the rest is the disagreement the
#: whole item exists to make visible.
STAMP_AGREES_WITH: dict[str, frozenset[str]] = {
    "AVAILABLE": frozenset({"DELIVERED"}),
    "READY_CAUSAL_STREAM": frozenset({"DELIVERED"}),
    "SEALED": frozenset({"SEALED_PROVEN"}),
    "SHADOW_DISABLED": frozenset({"SHADOW_DISABLED"}),
    "SHADOW_READY": frozenset(),
    "NOT_APPLICABLE": frozenset({"NOT_APPLICABLE"}),
    "PENDING": frozenset({"OUTPUT_PENDING"}),
}

FIXTURE_RENDER_PATH = PKG + "LAYER_CROSSWALK_FIXTURE_RENDER_20260902.md"
SUNDAY_CLI = (
    "python3 -m research.kalshi.frankie_raw_mbo_benchmark.native_layer_crosswalk "
    "--result <calculation_result.json> --delivery-receipt <FRANKIE_LEDGER_DELIVERY_RECEIPT.json> "
    "--arm A_CLEAN --out <LAYER_CROSSWALK_<run>.md> [--json <crosswalk.json>] [--stream-receipt <stream_receipt.json>] "
    "[--knowledge-receipt <...>] [--outputs-receipt <...>] [--sealed-proof <...>] [--ledger-dir <delivered/>]"
)


class CrosswalkError(ValueError):
    """A receipt or result could not be read as what it claims to be."""


class CrosswalkGateError(CrosswalkError):
    """The spawn gate refused: an arm-applicable input layer is not DELIVERED."""


def _evidence(kind: str, receipt_sha256: str | None, carrier: str | None, detail: str) -> dict[str, Any]:
    return {"kind": kind, "receipt_sha256": receipt_sha256, "carrier": carrier, "detail": detail}


def _require_receipt(receipt: Any, schema: str, label: str, *, verify_hash: bool) -> dict[str, Any]:
    if not isinstance(receipt, Mapping):
        raise CrosswalkError(f"{label} must be a mapping")
    if receipt.get("schema") != schema:
        raise CrosswalkError(f"{label} is not a {schema} (schema={receipt.get('schema')!r})")
    sha = receipt.get("receipt_sha256")
    if not isinstance(sha, str) or not sha:
        raise CrosswalkError(f"{label} carries no receipt_sha256")
    if verify_hash and sha != canonical_hash(receipt, omit="receipt_sha256"):
        raise CrosswalkError(f"{label} fails its own receipt_sha256")
    return dict(receipt)


# --- what the run actually carried --------------------------------------------------------
def observed_carriers(
    result: Mapping[str, Any] | None, *, delivery_receipt: Mapping[str, Any] | None = None,
    ledger_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Read, off the result and the delivered files, what carriers the run holds.

    Member paths come from the result's own field census (exact over every member row);
    lifecycle sections from the sink's per-section row counts; legacy keys from the first rows
    of the delivered legacy file when it is reachable, else from the sink's sampled field table.
    Nothing here is asserted from a policy.
    """
    out: dict[str, Any] = {
        "member_paths": None, "member_rows": None, "lifecycle_rows_by_section": None,
        "legacy_keys": None, "legacy_keys_source": None, "legacy_rows": None, "sink_sha256": {},
    }
    if result is None:
        return out
    layers = result.get("layers") or {}
    member = layers.get(MEMBER_LEDGER) or {}
    census = member.get("field_census")
    if isinstance(census, Mapping) and isinstance(census.get("fields"), list):
        out["member_paths"] = {
            str(row["field"]) for row in census["fields"] if isinstance(row, Mapping) and "field" in row
        }
        out["member_rows"] = census.get("rows_observed")
    retention = result.get("ledger_retention") or {}
    for ledger in (MEMBER_LEDGER, LIFECYCLE_LEDGER, LEGACY_LEDGER):
        sink = retention.get(ledger)
        if isinstance(sink, Mapping) and isinstance(sink.get("sha256"), str):
            out["sink_sha256"][ledger] = sink["sha256"]
    lifecycle = retention.get(LIFECYCLE_LEDGER)
    if isinstance(lifecycle, Mapping) and isinstance(lifecycle.get("rows_by_section"), Mapping):
        out["lifecycle_rows_by_section"] = {
            str(section): int(count) for section, count in lifecycle["rows_by_section"].items()
        }
    legacy = retention.get(LEGACY_LEDGER)
    if isinstance(legacy, Mapping):
        out["legacy_rows"] = legacy.get("row_count")
    path: Path | None = None
    if delivery_receipt is not None:
        entry = (delivery_receipt.get("ledgers") or {}).get(LEGACY_LEDGER) or {}
        local = entry.get("local_path") if isinstance(entry, Mapping) else None
        if isinstance(local, str) and local:
            candidate = Path(local)
            if not candidate.is_absolute() and ledger_dir is not None and not candidate.is_file():
                candidate = Path(ledger_dir) / candidate
            if candidate.is_file():
                path = candidate
    if path is None and ledger_dir is not None:
        candidate = Path(ledger_dir) / LEDGER_FILES[LEGACY_LEDGER]
        if candidate.is_file():
            path = candidate
    if path is not None:
        keys: set[str] = set()
        with path.open("r", encoding="utf-8") as handle:
            for index, line in enumerate(handle):
                if line.strip():
                    keys.update(json.loads(line).keys())
                if index >= 999:
                    # The legacy row schema is fixed by the hash-locked `_legacy_control_row`;
                    # a thousand rows settle the key set without reading a 10 GB file.
                    break
        out["legacy_keys"] = keys
        out["legacy_keys_source"] = "DELIVERED_LEDGER_FIRST_ROWS"
    elif isinstance(legacy, Mapping):
        sample = ((legacy.get("field_bytes_estimated") or {}).get("bytes_by_field") or {})
        if isinstance(sample, Mapping) and sample:
            out["legacy_keys"] = set(sample)
            out["legacy_keys_source"] = "SINK_FIELD_SAMPLE"
    return out


# --- per-policy status --------------------------------------------------------------------
def _causal_status(
    record: Mapping[str, Any], *, result_present: bool, observed: Mapping[str, Any],
    receipt: Mapping[str, Any] | None, receipt_sha: str | None,
) -> tuple[str, dict[str, Any]]:
    if record["kind"] == "NO_PRODUCER_FOUND":
        return "NO_PRODUCER_FOUND", _evidence("NONE", None, None, record["notes"])
    ledgers = tuple(record.get("ledgers", ()))
    problems: list[str] = []
    for ledger in ledgers:
        if receipt is None:
            problems.append(f"no VERIFIED delivery receipt for {ledger}")
            continue
        entry = (receipt.get("ledgers") or {}).get(ledger)
        status = entry.get("status") if isinstance(entry, Mapping) else None
        if status != "VERIFIED":
            problems.append(f"{ledger} delivery status {status!r}, not VERIFIED")
            continue
        delivered_sha = entry.get("plain_sha256_observed")
        sink_sha = observed["sink_sha256"].get(ledger)
        if isinstance(delivered_sha, str) and isinstance(sink_sha, str) and delivered_sha != sink_sha:
            problems.append(
                f"{ledger}: delivered sha256 {delivered_sha[:12]} is not the run's sink sha256 "
                f"{sink_sha[:12]}; the delivered file is not this run's ledger"
            )
    if not result_present:
        detail = (
            "no run result supplied; the carrier cannot be checked"
            if receipt is not None else "no run result and no delivery receipt supplied"
        )
        kind = "DELIVERY_RECEIPT" if receipt is not None else "NONE"
        return "PRODUCED_NOT_DELIVERED", _evidence(kind, receipt_sha, record["carrier"], detail)

    present: list[str] = []
    absent: list[str] = []
    member_paths = observed["member_paths"]
    for pattern in record.get("member_paths", ()):
        if member_paths is None:
            absent.append(f"{pattern} (the result carries no field census)")
        elif path_present(pattern, member_paths):
            present.append(pattern)
        else:
            absent.append(f"{pattern} not in the field census")
    rows_by_section = observed["lifecycle_rows_by_section"] or {}
    for section in record.get("lifecycle_sections", ()):
        rows = int(rows_by_section.get(section, 0))
        if rows > 0:
            present.append(f"lifecycle `{section}` ({rows} rows)")
        else:
            absent.append(f"lifecycle section `{section}`: 0 rows on this run")
    legacy_keys = tuple(record.get("legacy_keys", ()))
    if legacy_keys:
        legacy_rows = int(observed["legacy_rows"] or 0)
        if observed["legacy_keys"] is not None:
            for key in legacy_keys:
                if key in observed["legacy_keys"]:
                    present.append(f"legacy `{key}`")
                else:
                    absent.append(f"legacy key `{key}` not on the delivered rows")
        elif legacy_rows > 0:
            present.append(f"legacy rows ({legacy_rows}; keys unmeasured, schema fixed by _legacy_control_row)")
        else:
            absent.append("legacy ledger: 0 rows on this run")
    lost = [f"{pattern} not on the row (produced and dropped before the ledger)"
            for pattern in record.get("structurally_absent", ())
            if member_paths is None or not path_present(pattern, member_paths)]
    declared = bool(record.get("member_paths") or record.get("lifecycle_sections") or record.get("legacy_keys"))
    if not declared:
        absent.extend(lost or ["no carrier declared"])
        lost = []
    carriers_ok = declared and not absent
    verified = not problems
    lost_note = ("; per-record fields lost: " + "; ".join(lost)) if lost else ""
    if verified and carriers_ok:
        detail = "carriers present: " + ", ".join(present) + lost_note
        return "DELIVERED", _evidence("DELIVERY_RECEIPT", receipt_sha, record["carrier"], detail)
    if verified:
        detail = "the delivery receipt names this layer; absent from the run: " + "; ".join(absent)
        if present:
            detail += "; present: " + ", ".join(present)
        return "RECEIPTED_CARRIER_ABSENT", _evidence("DELIVERY_RECEIPT", receipt_sha, record["carrier"], detail + lost_note)
    kind = "DELIVERY_RECEIPT" if receipt is not None else "NONE"
    if carriers_ok:
        detail = "carrier present in the result; " + "; ".join(problems) + lost_note
    else:
        detail = "; ".join(problems + absent) + lost_note
    return "PRODUCED_NOT_DELIVERED", _evidence(kind, receipt_sha, record["carrier"], detail)


def _static_status(
    layer_id: str, record: Mapping[str, Any], *, knowledge_rows: Mapping[str, Mapping[str, Any]],
    knowledge_sha: str | None,
) -> tuple[str, dict[str, Any]]:
    row = knowledge_rows.get(layer_id)
    if row is not None:
        status = row.get("status")
        files = row.get("files") or []
        paths = [str(f.get("path")) for f in files if isinstance(f, Mapping) and f.get("path")]
        if status == "DELIVERED" and paths:
            return "DELIVERED", _evidence(
                "KNOWLEDGE_RECEIPT", knowledge_sha, ", ".join(paths),
                f"knowledge receipt: DELIVERED, {len(paths)} file(s)",
            )
        if status == "DELIVERED":
            return "PRODUCED_NOT_DELIVERED", _evidence(
                "KNOWLEDGE_RECEIPT", knowledge_sha, record["carrier"],
                "knowledge receipt says DELIVERED with no files; not believed",
            )
        return "PRODUCED_NOT_DELIVERED", _evidence(
            "KNOWLEDGE_RECEIPT", knowledge_sha, record["carrier"], f"knowledge receipt: {status}",
        )
    if record.get("bound_to_inventory_document"):
        return "BOUND_TO_INVENTORY_DOCUMENT", _evidence(
            "INVENTORY_DOCUMENT", None, record["carrier"],
            "the registry's only source path is the feed-inventory markdown; no knowledge receipt names this layer",
        )
    if record["kind"] == "NO_PRODUCER_FOUND":
        return "NO_PRODUCER_FOUND", _evidence("NONE", None, None, record["notes"])
    return "PRODUCED_NOT_DELIVERED", _evidence(
        "NONE", None, record["carrier"], "producer found; no knowledge receipt names this layer",
    )


def _outputs_named(receipt: Mapping[str, Any] | None) -> tuple[dict[str, Any], str | None]:
    if receipt is None:
        return {}, None
    ledgers = receipt.get("ledgers")
    if isinstance(ledgers, Mapping):
        return {str(k): v for k, v in ledgers.items()}, "mapping"
    if isinstance(ledgers, list):
        return {str(item): None for item in ledgers}, "list"
    raise CrosswalkError("outputs receipt `ledgers` is neither a mapping of ledger id -> record nor a list of ids")


# --- the crosswalk --------------------------------------------------------------------------
def crosswalk(
    registry: Mapping[str, Any] | None, *, arm: str, result: Mapping[str, Any] | None = None,
    delivery_receipt: Mapping[str, Any] | None = None, stream_receipt: Mapping[str, Any] | None = None,
    knowledge_receipt: Mapping[str, Any] | None = None, outputs_receipt: Mapping[str, Any] | None = None,
    sealed_proof: Mapping[str, Any] | None = None, ledger_dir: Path | str | None = None,
) -> dict[str, Any]:
    """One row per registry layer with a COMPUTED status. See the module docstring."""
    if arm not in ALLOWED_ARMS:
        raise CrosswalkError(f"unknown arm {arm!r}; one of {sorted(ALLOWED_ARMS)}")
    active = load_registry() if registry is None else registry
    if delivery_receipt is not None:
        delivery_receipt = _require_receipt(delivery_receipt, DELIVERY_RECEIPT_SCHEMA, "delivery receipt", verify_hash=True)
    if stream_receipt is not None:
        stream_receipt = _require_receipt(stream_receipt, STREAM_RECEIPT_SCHEMA, "stream receipt", verify_hash=True)
    if knowledge_receipt is not None:
        knowledge_receipt = _require_receipt(knowledge_receipt, KNOWLEDGE_RECEIPT_SCHEMA, "knowledge receipt", verify_hash=False)
    if outputs_receipt is not None:
        outputs_receipt = _require_receipt(outputs_receipt, OUTPUTS_RECEIPT_SCHEMA, "outputs receipt", verify_hash=False)
    if sealed_proof is not None:
        sealed_proof = _require_receipt(sealed_proof, SEALED_PROOF_SCHEMA, "sealed-absence proof", verify_hash=False)

    knowledge_rows: dict[str, Mapping[str, Any]] = {}
    if knowledge_receipt is not None:
        for row in knowledge_receipt.get("layers") or []:
            if isinstance(row, Mapping) and isinstance(row.get("layer_id"), str):
                knowledge_rows[row["layer_id"]] = row
    outputs_named, outputs_shape = _outputs_named(outputs_receipt)
    observed = observed_carriers(result, delivery_receipt=delivery_receipt, ledger_dir=ledger_dir)
    delivery_sha = delivery_receipt["receipt_sha256"] if delivery_receipt is not None else None
    knowledge_sha = knowledge_receipt["receipt_sha256"] if knowledge_receipt is not None else None
    outputs_sha = outputs_receipt["receipt_sha256"] if outputs_receipt is not None else None
    sealed_sha = sealed_proof["receipt_sha256"] if sealed_proof is not None else None
    stream_claims = stream_receipt.get("layer_carriers") if stream_receipt is not None else None

    layers: list[dict[str, Any]] = []
    mismatches = 0
    for group in active["groups"]:
        policy = group["policy"]
        applicable = arm in group["arms"]
        for entry in group["entries"]:
            layer_id = entry["layer_id"]
            record = LAYER_PRODUCERS.get(layer_id)
            if record is None:
                raise CrosswalkError(f"registry layer {layer_id!r} has no producer record; add it to LAYER_PRODUCERS")
            if not applicable:
                status, evidence = "NOT_APPLICABLE", _evidence(
                    "REGISTRY", None, None, f"arm {arm} is not in the group's arms {list(group['arms'])}",
                )
            elif policy == "CAUSAL_STREAM_REQUIRED":
                status, evidence = _causal_status(
                    record, result_present=result is not None, observed=observed,
                    receipt=delivery_receipt, receipt_sha=delivery_sha,
                )
                if isinstance(stream_claims, Mapping) and record["kind"] != "NO_PRODUCER_FOUND":
                    claimed = [str(c) for c in (stream_claims.get(group["group_id"]) or [])]
                    declared = [LEDGER_TO_CARRIER[l] for l in record.get("ledgers", ()) if l in LEDGER_TO_CARRIER]
                    missing = [c for c in declared if c not in claimed]
                    if missing:
                        mismatches += 1
                        evidence["detail"] += (
                            f"; carrier claim mismatch: the stream receipt carries group `{group['group_id']}` on "
                            f"{claimed} but this layer rides on {declared}"
                        )
            elif policy in ("STATIC_REQUIRED_INPUT", "ARM_REQUIRED_INPUT"):
                status, evidence = _static_status(
                    layer_id, record, knowledge_rows=knowledge_rows, knowledge_sha=knowledge_sha,
                )
            elif policy == "SEALED_FOR_A_SCOPE":
                if sealed_proof is not None and sealed_proof.get("all_absent") is True:
                    status, evidence = "SEALED_PROVEN", _evidence(
                        "SEALED_ABSENCE_PROOF", sealed_sha, record["carrier"],
                        f"all_absent true over {sealed_proof.get('tokens_checked')} tokens",
                    )
                elif sealed_proof is not None:
                    status, evidence = "SEALED_UNPROVEN", _evidence(
                        "SEALED_ABSENCE_PROOF", sealed_sha, record["carrier"], "the sealed-absence proof did not find every token absent",
                    )
                else:
                    status, evidence = "SEALED_UNPROVEN", _evidence(
                        "NONE", None, record["carrier"], "no sealed-absence proof supplied for this run",
                    )
            elif policy == "PROVISIONAL_SHADOW":
                status, evidence = "SHADOW_DISABLED", _evidence(
                    "NONE", None, record["carrier"], "D5: nothing opts the shadow component in",
                )
            elif policy == "APPEND_ONLY_OUTPUT":
                if layer_id in outputs_named:
                    named = outputs_named[layer_id]
                    head = named.get("head_hash") if isinstance(named, Mapping) else None
                    carrier = f"ledger `{layer_id}`" + (f" head_hash {head}" if isinstance(head, str) else "")
                    status, evidence = "OUTPUT_FILED", _evidence(
                        "OUTPUTS_RECEIPT", outputs_sha, carrier, f"named by the outputs receipt ({outputs_shape} shape)",
                    )
                elif outputs_receipt is not None:
                    status, evidence = "OUTPUT_PENDING", _evidence(
                        "OUTPUTS_RECEIPT", outputs_sha, record["carrier"],
                        f"not named by the outputs receipt ({outputs_shape} shape)",
                    )
                else:
                    status, evidence = "OUTPUT_PENDING", _evidence("NONE", None, record["carrier"], "no outputs receipt")
            else:
                raise CrosswalkError(f"unsupported registry policy {policy!r}")
            layers.append({
                "layer_id": layer_id,
                "group_id": group["group_id"],
                "policy": policy,
                "arm_applicable": applicable,
                "producer": {
                    key: record.get(key) for key in ("kind", "module", "symbol", "file", "line", "carrier")
                },
                "status": status,
                "evidence": evidence,
            })

    by_status = {status: 0 for status in sorted(STATUSES)}
    by_group: dict[str, dict[str, int]] = {}
    for row in layers:
        by_status[row["status"]] += 1
        bucket = by_group.setdefault(row["group_id"], {})
        bucket[row["status"]] = bucket.get(row["status"], 0) + 1
    inputs = [row for row in layers if row["arm_applicable"] and row["policy"] in INPUT_POLICIES]
    totals = {
        "registered": len(layers),
        "applicable": sum(1 for row in layers if row["arm_applicable"]),
        "not_applicable": by_status["NOT_APPLICABLE"],
        "inputs_applicable": len(inputs),
        "inputs_delivered": sum(1 for row in inputs if row["status"] == "DELIVERED"),
        "inputs_not_delivered": sum(1 for row in inputs if row["status"] != "DELIVERED"),
        "delivered": by_status["DELIVERED"],
        "receipted_carrier_absent": by_status["RECEIPTED_CARRIER_ABSENT"],
        "bound_to_inventory_document": by_status["BOUND_TO_INVENTORY_DOCUMENT"],
        "produced_not_delivered": by_status["PRODUCED_NOT_DELIVERED"],
        "no_producer_found": by_status["NO_PRODUCER_FOUND"],
        "sealed_proven": by_status["SEALED_PROVEN"],
        "sealed_unproven": by_status["SEALED_UNPROVEN"],
        "shadow_disabled": by_status["SHADOW_DISABLED"],
        "outputs_filed": by_status["OUTPUT_FILED"],
        "outputs_pending": by_status["OUTPUT_PENDING"],
        "carrier_claim_mismatches": mismatches,
        "by_status": by_status,
        "by_group": by_group,
    }
    body: dict[str, Any] = {
        "schema": CROSSWALK_SCHEMA,
        "arm": arm,
        "registry_sha256": active.get("registry_sha256"),
        "result_hash": result.get("result_hash") if isinstance(result, Mapping) else None,
        "result_verdict": result.get("verdict") if isinstance(result, Mapping) else None,
        "delivery_receipt_sha256": delivery_sha,
        "stream_receipt_sha256": stream_receipt["receipt_sha256"] if stream_receipt is not None else None,
        "stream_complete": stream_receipt.get("complete") if stream_receipt is not None else None,
        "knowledge_receipt_sha256": knowledge_sha,
        "outputs_receipt_sha256": outputs_sha,
        "sealed_proof_sha256": sealed_sha,
        "member_rows_censused": observed["member_rows"],
        "legacy_keys_source": observed["legacy_keys_source"],
        "layers": layers,
        "totals": totals,
        "crosswalk_sha256": "",
    }
    body["crosswalk_sha256"] = canonical_hash(body, omit="crosswalk_sha256")
    return body


# --- the gate the coordinator wires at spawn (item 7) -------------------------------------
def gate_applicable_inputs(crosswalk_body: Mapping[str, Any]) -> None:
    """Refuse the spawn unless every arm-applicable INPUT layer is DELIVERED.

    Lists every offender with its computed status. Never consults the policy, never reads a
    stamp: the only thing that satisfies it is a row computed from a receipt and the run.
    """
    refused = [
        (row["layer_id"], row["status"])
        for row in crosswalk_body["layers"]
        if row["arm_applicable"] and row["policy"] in INPUT_POLICIES and row["status"] != "DELIVERED"
    ]
    if not refused:
        return None
    total = sum(1 for row in crosswalk_body["layers"] if row["arm_applicable"] and row["policy"] in INPUT_POLICIES)
    raise CrosswalkGateError(
        f"spawn refused for arm {crosswalk_body['arm']}: {len(refused)} of {total} applicable input layers "
        "are not DELIVERED: " + ", ".join(f"{layer_id}={status}" for layer_id, status in refused)
    )


# --- the measurement: policy stamp against computed status --------------------------------
def pre_call_status_computed(
    crosswalk_body: Mapping[str, Any], *, registry: Mapping[str, Any] | None = None, repo_root: Path = REPO_ROOT,
) -> list[dict[str, Any]]:
    """What `build_pre_call_receipt` would stamp, beside what the crosswalk computed."""
    from research.kalshi.frankie_raw_mbo_benchmark.native_a_arm_launch import build_pre_call_receipt

    active = load_registry() if registry is None else registry
    receipt = build_pre_call_receipt(arm=crosswalk_body["arm"], run_id="crosswalk", registry=active, repo_root=repo_root)
    stamps = {row["layer_id"]: row["status"] for row in receipt["layers"]}
    out: list[dict[str, Any]] = []
    for row in crosswalk_body["layers"]:
        stamp = stamps.get(row["layer_id"])
        computed = row["status"]
        out.append({
            "layer_id": row["layer_id"],
            "policy_stamp": stamp,
            "computed_status": computed,
            "agree": computed in STAMP_AGREES_WITH.get(stamp, frozenset()),
        })
    return out


# --- the render ---------------------------------------------------------------------------
def _cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _short(sha: str | None) -> str:
    return "-" if not sha else sha[:12]


def render_crosswalk_table(crosswalk_body: Mapping[str, Any], *, registry: Mapping[str, Any] | None = None) -> str:
    """Markdown: header, totals, status by group, the status vocabulary, one row per layer.

    Rows are sorted by the registry's group ORDER (the registry groups inputs before outputs and
    sealed layers deliberately) and then by layer id. Repo-relative paths and hashes only.
    """
    active = load_registry() if registry is None else registry
    order = {group["group_id"]: index for index, group in enumerate(active["groups"])}
    rows = sorted(crosswalk_body["layers"], key=lambda row: (order.get(row["group_id"], len(order)), row["layer_id"]))
    totals = crosswalk_body["totals"]
    lines: list[str] = []
    add = lines.append
    add(f"# Frankie native raw-MBO layer crosswalk ({crosswalk_body['arm']})")
    add("")
    add(f"- schema `{crosswalk_body['schema']}`")
    add(f"- registry sha256 `{crosswalk_body['registry_sha256']}`")
    add(f"- result_hash `{crosswalk_body['result_hash']}` (verdict `{crosswalk_body['result_verdict']}`)")
    add(f"- delivery receipt sha256 `{crosswalk_body['delivery_receipt_sha256']}`")
    add(f"- stream receipt sha256 `{crosswalk_body['stream_receipt_sha256']}` (complete: `{crosswalk_body['stream_complete']}`)")
    add(f"- knowledge receipt sha256 `{crosswalk_body['knowledge_receipt_sha256']}`")
    add(f"- outputs receipt sha256 `{crosswalk_body['outputs_receipt_sha256']}`")
    add(f"- sealed-absence proof sha256 `{crosswalk_body['sealed_proof_sha256']}`")
    add(f"- member rows censused `{crosswalk_body['member_rows_censused']}`; legacy keys from `{crosswalk_body['legacy_keys_source']}`")
    add(f"- crosswalk sha256 `{crosswalk_body['crosswalk_sha256']}`")
    add("")
    add("Status is COMPUTED from receipts and from the run's own field census, section row counts and")
    add("legacy rows. Nothing here is read off a registry policy. Every count is derived at render time.")
    add("")
    add("## Totals")
    add("")
    add("| total | value |")
    add("|---|---:|")
    for key, value in totals.items():
        if key in ("by_status", "by_group"):
            continue
        add(f"| {key} | {value} |")
    add("")
    add("## Status by group")
    add("")
    statuses = sorted(STATUSES)
    add("| group | " + " | ".join(statuses) + " |")
    add("|---|" + "---:|" * len(statuses))
    for group_id in sorted(totals["by_group"], key=lambda g: order.get(g, len(order))):
        counts = totals["by_group"][group_id]
        add(f"| {group_id} | " + " | ".join(str(counts.get(status, 0)) for status in statuses) + " |")
    add("")
    add("## Status vocabulary")
    add("")
    add("| status | meaning |")
    add("|---|---|")
    for status in statuses:
        add(f"| {status} | {_cell(STATUS_MEANING[status]).replace(chr(96), '')} |")
    add("")
    add("## Layers (sorted by registry group order, then layer id)")
    add("")
    add("| group | layer | policy | arm | status | producer | carrier | evidence | detail |")
    add("|---|---|---|---|---|---|---|---|---|")
    for row in rows:
        producer = row["producer"]
        where = ""
        if producer.get("file"):
            where = f" {producer['file']}" + (f":{producer['line']}" if producer.get("line") else "")
        symbol = f" `{producer['symbol']}`" if producer.get("symbol") else ""
        evidence = row["evidence"]
        add(
            f"| {row['group_id']} | `{row['layer_id']}` | {row['policy']} | {'yes' if row['arm_applicable'] else 'no'} "
            f"| {row['status']} | {producer['kind']}{_cell(where)}{_cell(symbol)} | {_cell(producer.get('carrier'))} "
            f"| {evidence['kind']} {_short(evidence['receipt_sha256'])} | {_cell(evidence['detail'])} |"
        )
    add("")
    return "\n".join(lines)


# --- the fixture render (not the Sunday run) -----------------------------------------------
def fixture_render(groups: int = 12) -> tuple[str, dict[str, Any]]:
    """Run the real launch path over the shared synthetic slice and cross-walk it.

    Everything is computed under a temporary working directory with RELATIVE paths, so no
    absolute path reaches any hash or the render (D34) and the render is reproducible byte for
    byte. Returns the markdown (with a header saying it is a fixture) and the crosswalk.
    """
    import tempfile

    from research.kalshi.frankie_raw_mbo_benchmark import native_a_arm_launch as launcher
    from research.kalshi.frankie_raw_mbo_benchmark.native_causal_stream import CausalGroupStream
    from research.kalshi.frankie_raw_mbo_benchmark.tests.test_native_a_arm_launch import slice_records

    registry = load_registry()
    with tempfile.TemporaryDirectory() as tmp, contextlib.chdir(tmp):
        run_dir = Path("run")
        result = launcher.launch(
            arm="A_CLEAN", run_id="crosswalk-fixture", sources=[],
            source_manifest={"manifest_hash": "e" * 64, "total_mbo_records": 5_667_689},
            out_dir=run_dir, code_commit="cafebabe", limit_records=groups * 4,
            checkpoint_every_records=10**9, cadence_groups=10**9,
            records=slice_records(groups), stream_ledgers=True,
        )
        ledgers: dict[str, dict[str, Any]] = {}
        for name, plain in LEDGER_FILES.items():
            path = Path(result["ledger_retention"][name]["path"])
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            ledgers[name] = {
                "file": plain, "object": plain + ".gz", "status": "VERIFIED", "local_path": str(path),
                "gz_bytes_expected": None, "gz_bytes_observed": None,
                "plain_bytes_expected": path.stat().st_size, "plain_bytes_observed": path.stat().st_size,
                "plain_sha256_expected": digest, "plain_sha256_observed": digest,
            }
        receipt: dict[str, Any] = {
            "schema": DELIVERY_RECEIPT_SCHEMA, "run_id": "crosswalk-fixture", "run_prefix": "fixture/prefix",
            "bucket": "fixture-bucket", "manifest_sha256": "f" * 64, "fetched_at": "2026-09-02T00:00:00Z",
            "out_dir": str(run_dir / "ledgers"), "ledgers": ledgers, "objects": {},
            "all_ledgers_verified": True, "receipt_sha256": "",
        }
        receipt["receipt_sha256"] = canonical_hash(receipt, omit="receipt_sha256")
        exact = result["evidence_identity"]["exact_ledgers"]
        stream = CausalGroupStream(
            exact["exact_member_rows"], exact["exact_lifecycle_rows"], exact["legacy_observable_rows"],
            run_id="crosswalk-fixture", arm="A_CLEAN", registry=registry,
        )
        list(stream.iterate())
        stream_receipt = stream.stream_receipt()
        body = crosswalk(registry, arm="A_CLEAN", result=result, delivery_receipt=receipt, stream_receipt=stream_receipt)
    header = [
        "# LAYER CROSSWALK - FIXTURE RENDER (2026-09-02)",
        "",
        "**This is a FIXTURE render, not the Sunday run.** It is computed by running the real launch path",
        f"(`native_a_arm_launch.launch`) over the shared synthetic slice (`slice_records({groups})`, {groups} F_LAST",
        "groups of four actions), streaming the three ledgers it wrote through `CausalGroupStream`, and cross-walking",
        "the result against a delivery receipt built over those very files. It exists so the table below is rendered",
        "from a run, not written by hand, and so the coordinator can see the shape before the Sunday",
        "`calculation_result.json` is in the container. Candidate, episode and response sections need the candidate",
        "lane's warmup and real flow, so on this fixture they show 0 rows; the Sunday run decides them.",
        "",
        "Regenerate: `python3 -m research.kalshi.frankie_raw_mbo_benchmark.native_layer_crosswalk --fixture-render "
        f"{FIXTURE_RENDER_PATH}`",
        "",
        "Run it on the Sunday result when it is in the container (one line):",
        "",
        f"`{SUNDAY_CLI}`",
        "",
    ]
    return "\n".join(header) + render_crosswalk_table(body, registry=registry), body


# --- CLI ----------------------------------------------------------------------------------
def _load_json(path: str | None) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        body = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CrosswalkError(f"cannot read {path}: {exc}") from exc
    if not isinstance(body, dict):
        raise CrosswalkError(f"{path} is not a JSON object")
    return body


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cross-walk every registry layer against a run's receipts and render it.")
    parser.add_argument("--result", default=None, help="the run's calculation_result.json")
    parser.add_argument("--delivery-receipt", default=None, help="FRANKIE_LEDGER_DELIVERY_RECEIPT_V1 from fetch_frankie_ledgers")
    parser.add_argument("--stream-receipt", default=None, help="FRANKIE_NATIVE_RAW_MBO_CAUSAL_STREAM_RECEIPT_V1 from the stream")
    parser.add_argument("--knowledge-receipt", default=None, help="FRANKIE_KNOWLEDGE_DELIVERY_RECEIPT_V1")
    parser.add_argument("--outputs-receipt", default=None, help="FRANKIE_NATIVE_RAW_MBO_PRINCIPAL_OUTPUTS_RECEIPT_V1")
    parser.add_argument("--sealed-proof", default=None, help="FRANKIE_SEALED_ABSENCE_PROOF_V1")
    parser.add_argument("--ledger-dir", default=None, help="directory holding the delivered plain ledgers")
    parser.add_argument("--arm", default="A_CLEAN", choices=sorted(ALLOWED_ARMS))
    parser.add_argument("--out", default=None, help="write the markdown render here")
    parser.add_argument("--json", default=None, help="write the crosswalk JSON here")
    parser.add_argument("--enforce-gate", action="store_true", help="exit 3 when an applicable input is not DELIVERED")
    parser.add_argument("--fixture-render", default=None, metavar="OUT", help="render the synthetic fixture run to OUT and stop")
    args = parser.parse_args(argv)
    try:
        if args.fixture_render:
            text, body = fixture_render()
            Path(args.fixture_render).write_text(text, encoding="utf-8")
            print(json.dumps({"fixture_render": args.fixture_render, "totals": body["totals"],
                              "crosswalk_sha256": body["crosswalk_sha256"]}, sort_keys=True))
            return 0
        if args.out is None and args.json is None:
            raise CrosswalkError("pass --out and/or --json (or --fixture-render)")
        registry = load_registry()
        body = crosswalk(
            registry, arm=args.arm, result=_load_json(args.result),
            delivery_receipt=_load_json(args.delivery_receipt), stream_receipt=_load_json(args.stream_receipt),
            knowledge_receipt=_load_json(args.knowledge_receipt), outputs_receipt=_load_json(args.outputs_receipt),
            sealed_proof=_load_json(args.sealed_proof), ledger_dir=args.ledger_dir,
        )
    except CrosswalkError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    if args.out:
        Path(args.out).write_text(render_crosswalk_table(body, registry=registry), encoding="utf-8")
    if args.json:
        Path(args.json).write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    gate: dict[str, Any] = {"passed": True, "refused": []}
    try:
        gate_applicable_inputs(body)
    except CrosswalkGateError as exc:
        gate = {"passed": False, "refused": [
            f"{row['layer_id']}={row['status']}" for row in body["layers"]
            if row["arm_applicable"] and row["policy"] in INPUT_POLICIES and row["status"] != "DELIVERED"
        ], "message": str(exc)}
    print(json.dumps({"schema": body["schema"], "arm": body["arm"], "totals": body["totals"],
                      "crosswalk_sha256": body["crosswalk_sha256"], "gate": gate}, sort_keys=True))
    if args.enforce_gate and not gate["passed"]:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
