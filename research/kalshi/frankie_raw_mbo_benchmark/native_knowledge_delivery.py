"""The knowledge Frankie receives: classified from the inventory, bound to real files, receipted.

**The defect this closes (S120, measured).** Of the 99 registry layers, 91 bound their
evidence hash to ONE markdown document, `NG_EXHAUSTION_FRANKIE_DATA_FEED_INVENTORY_20260824.md`.
The pre-call gate therefore proved the document was unchanged and nothing about what reached
Frankie. The knowledge layers - the nine frozen-learned-structure layers and the five
current-brain layers - are the ones whose evidence is a FILE he can read, and none of them
named one.

**Greg's rulings that govern this module (2026-09-02, DROP_IN_S121 item zero).**

1. The proposal lineage goes in WHOLE. Its own "do not promote / proposal-only / research
   memory" language is disregarded: every lesson carries VERIFIED / UNVERIFIED / REFUTED,
   Frankie verifies against the stream, and only the refuted comes out later. The language
   is COUNTED in the receipt (`totals.disregarded_do_not_promote_language`) and excludes
   nothing.
2. No historical number is a spec. Not 149, not 15, not 99. The inventory rows are parsed
   from the document, the knowledge layer set is derived from the registry, and a test that
   wants a count computes it independently.
3. Nothing is dropped without discussion (D60); keep-everything is a first-class answer
   (D76). Every inventory path that is NOT delivered is listed with its classification and
   its reason. A KEEP path that no layer delivers is a refusal, not an omission.
4. No desktop paths anywhere (D34). Every path here is repository-relative.
5. A gate that reads status off a policy is not a gate. "Delivered" is a receipt row naming
   the layer, the carrier file and its sha256, computed from the bytes on disk.

**Why the classification is a table of RULES rather than a JSON of rows.** The 2026-08-24
source-file inventory is a dated record and is never rewritten; its classification is a
DATED ADDENDUM rendered by `render_source_inventory_addendum.py` from `classify_inventory`.
The rows are derived from the document at build time, so a bullet the rules do not cover
FAILS CLOSED (`no classification rule`) instead of quietly inheriting nothing, and a KEEP
path that does not exist on disk fails closed too, because a KEEP path is a promise to
deliver bytes. A hand-typed JSON of rows would drift from the document the first time the
document grew; rules cannot.

**Classification vocabulary (fixed by the S121 task, five values).**

- `KEEP`       knowledge he receives: sections C, D, E, F, the brain (B), and the two
               inventories themselves (A), which are the canonical list and are not superseded.
- `CODE`       runtime, not knowledge: B's S120-S135 construction code, G/H runtime and
               replay code, I's receipts and audits of that code, J's PROVISIONAL_SHADOW
               components (excluded from knowledge by registry policy, named here), and every
               test (the inventory's own note: tests are verification references).
- `SUPERSEDED` the Sol-era / four-helper-era handoffs and reviews of section A (D54, D63,
               D64, D70).
- `SEALED`     section K, the October Step-1 answer material: never delivered.
- `OBSOLETE`   section L's transport bridge and canary records, and M's forbidden substitute.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from research.kalshi.frankie_raw_mbo_benchmark.native_frankie_knowledge_registry import (
    KnowledgeRegistryError,
    bind_principal_knowledge_use,
    build_model_visible_context,
    load_and_validate_manifest,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import (
    canonical_hash,
    load_registry,
)

REPO_ROOT = Path(__file__).resolve().parents[3]

SOURCE_INVENTORY_PATH = "research/kalshi/NG_EXHAUSTION_FRANKIE_SOURCE_FILE_INVENTORY_20260824.md"
ADDENDUM_PATH = (
    "research/kalshi/NG_EXHAUSTION_FRANKIE_SOURCE_FILE_INVENTORY_20260824_ADDENDUM_20260902.md"
)
FEED_INVENTORY_PATH = "research/kalshi/NG_EXHAUSTION_FRANKIE_DATA_FEED_INVENTORY_20260824.md"
BRAIN_PATH = "research/kalshi/knowledge/ng_brain.json"

KEEP = "KEEP"
CODE = "CODE"
SUPERSEDED = "SUPERSEDED"
SEALED = "SEALED"
OBSOLETE = "OBSOLETE"
CLASSIFICATIONS = (KEEP, CODE, SUPERSEDED, SEALED, OBSOLETE)

INVENTORY_SECTIONS = tuple("ABCDEFGHIJKLM")
_SECTION_HEADING_RE = re.compile(r"^## ([A-Z])\. ")
_PATH_BULLET_RE = re.compile(r"^- `([^`]+)`")


class KnowledgeDeliveryError(ValueError):
    """The knowledge delivery cannot be classified, built or proven complete."""


# --------------------------------------------------------------------------------------
# The inventory document, parsed
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class InventoryBullet:
    """One bullet of sections A-M of the 2026-08-24 source-file inventory."""

    section: str
    line: int
    bullet: str
    path: str | None


def parse_source_inventory(text: str) -> list[InventoryBullet]:
    """Every `- ` bullet under a `## <Letter>. ` heading, in document order.

    A bullet that names a repository path in backticks carries it as `path`; a prose bullet
    (section K's "Step-1 seconds, populations, ..." line, which names products located by the
    Step-1 manifests rather than a file) carries `path=None` and is still a row, because a
    bullet the map lists is a bullet the classification must answer for.
    """
    bullets: list[InventoryBullet] = []
    section: str | None = None
    for number, line in enumerate(text.splitlines(), start=1):
        heading = _SECTION_HEADING_RE.match(line)
        if heading:
            section = heading.group(1)
            continue
        if line.startswith("## "):
            section = None
            continue
        if section is None or not line.startswith("- "):
            continue
        match = _PATH_BULLET_RE.match(line)
        bullets.append(
            InventoryBullet(
                section=section,
                line=number,
                bullet=line[2:].strip(),
                path=match.group(1) if match else None,
            )
        )
    return bullets


# --------------------------------------------------------------------------------------
# The classification rules
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ClassifiedPath:
    section: str
    line: int
    bullet: str
    path: str | None
    classification: str
    reason: str
    exists: bool


def _is_test(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return "/tests/" in path or name.startswith("test_")


def _rule_a(bullet: InventoryBullet) -> tuple[str, str]:
    if bullet.path == FEED_INVENTORY_PATH:
        return KEEP, (
            "canonical input list: the feed inventory is the registry's source_authority; "
            "index material, not superseded"
        )
    if bullet.path == SOURCE_INVENTORY_PATH:
        return KEEP, (
            "canonical input list: the corpus map this addendum classifies; index material, "
            "not superseded"
        )
    if bullet.path and "ROLE_CONTEXT_PROFILES" in bullet.path.upper():
        return SUPERSEDED, (
            "four-helper-era role/context profiles (D64); the KNOWLEDGE_SOURCES_20260828.json "
            "profiles supersede them"
        )
    if bullet.path and "STEP1_STRUCTURAL_CENSUS_METHOD" in bullet.path:
        return SUPERSEDED, (
            "Sol-era operational method for the Step-1 census; the frozen census protocol "
            "in section C carries the method as knowledge"
        )
    return SUPERSEDED, (
        "Sol-era / four-helper-era operational handoff or review (D54, D63, D64, D70); the "
        "corrected raw-MBO runner supersedes it"
    )


def _rule_b(bullet: InventoryBullet) -> tuple[str, str]:
    if bullet.path == BRAIN_PATH:
        return KEEP, (
            "the current NG brain (meta, reasoning_method, plays, doctrine, mechanisms, "
            "run_findings); the five current_brain_runtime layers bind to it"
        )
    if bullet.path and _is_test(bullet.path):
        return CODE, "test: a verification reference, not a knowledge source (inventory B's own note)"
    return CODE, (
        "S120-S135 runtime construction code: it assembles and gates the runtime that LOADS "
        "the brain; runtime, not knowledge"
    )


def _rule_c(bullet: InventoryBullet) -> tuple[str, str]:
    if bullet.path and bullet.path.endswith(".py"):
        return KEEP, (
            "construction/helper implementation of the frozen 54/55-week corpus: the exact "
            "definition of the legacy observables and structures he must recreate (feed "
            "section 8)"
        )
    return KEEP, "frozen 54/55-week structural corpus: a freeze, protocol or finding record"


def _rule_d(bullet: InventoryBullet) -> tuple[str, str]:
    return KEEP, (
        "proposal lineage: goes in whole (Greg, 2026-09-02); every lesson UNVERIFIED until "
        "verified against the stream, its do-not-promote language disregarded"
    )


def _rule_e(bullet: InventoryBullet) -> tuple[str, str]:
    return KEEP, (
        "V4 governing contract or correction: controls how the learned structures are "
        "interpreted (the inventory: corrections control when older addenda conflict)"
    )


def _rule_f(bullet: InventoryBullet) -> tuple[str, str]:
    return KEEP, (
        "post-correction V3 carryforward control record: the sole admissible V3-derived "
        "material, bound by extra_agent_corrected_information_and_gap_diagnoses"
    )


def _rule_g(bullet: InventoryBullet) -> tuple[str, str]:
    if bullet.path and _is_test(bullet.path):
        return CODE, "test: a verification reference, not a knowledge source"
    if bullet.path and bullet.path.endswith(".py"):
        return CODE, (
            "canonical raw-MBO replay / V4 state adapter runtime: the causal stream delivers "
            "the data itself (feed section 4); code, not knowledge"
        )
    return CODE, (
        "raw-object provenance manifest, status or receipt: provenance rides in the stream "
        "receipt (feed section 4), not in his knowledge"
    )


def _rule_h(bullet: InventoryBullet) -> tuple[str, str]:
    return CODE, (
        "V4 causal runtime module; runtime, not knowledge (its focused tests are "
        "verification references per the inventory)"
    )


def _rule_i(bullet: InventoryBullet) -> tuple[str, str]:
    return CODE, (
        "receipt, audit or state decision of the V4 runtime modules (H): a verification "
        "record of code, not knowledge"
    )


def _rule_j(bullet: InventoryBullet) -> tuple[str, str]:
    return CODE, (
        "PROVISIONAL_SHADOW (registry group provisional_shadow, route SHADOW_ONLY): excluded "
        "from knowledge by policy; a shadow component, never S135 or primary-lock authority"
    )


def _rule_k(bullet: InventoryBullet) -> tuple[str, str]:
    if bullet.path is None:
        return SEALED, (
            "SEALED_TARGET_ANSWER: Step-1 products located by the Step-1 manifests/runtime, "
            "no repository path; never delivered"
        )
    return SEALED, (
        "SEALED_TARGET_ANSWER: October Step-1 answer material (registry groups "
        "sealed_step1_answer / sealed_target_timing); never delivered"
    )


def _rule_l(bullet: InventoryBullet) -> tuple[str, str]:
    return OBSOLETE, (
        "obsolete transport bridge or canary record: forensic reference only, never the "
        "corrected runner's foundation"
    )


def _rule_m(bullet: InventoryBullet) -> tuple[str, str]:
    return OBSOLETE, (
        "FORBIDDEN substitute: consumes prebuilt SQS Frankie events, not the raw-MBO/V4 "
        "path; never a foundation"
    )


SECTION_RULES: dict[str, Callable[[InventoryBullet], tuple[str, str]]] = {
    "A": _rule_a,
    "B": _rule_b,
    "C": _rule_c,
    "D": _rule_d,
    "E": _rule_e,
    "F": _rule_f,
    "G": _rule_g,
    "H": _rule_h,
    "I": _rule_i,
    "J": _rule_j,
    "K": _rule_k,
    "L": _rule_l,
    "M": _rule_m,
}
"""One rule per inventory section. A bullet in a section absent here fails closed."""


def classify_bullet(bullet: InventoryBullet) -> tuple[str, str]:
    rule = SECTION_RULES.get(bullet.section)
    if rule is None:
        raise KnowledgeDeliveryError(
            f"no classification rule for inventory section {bullet.section!r} "
            f"(line {bullet.line}: {bullet.bullet[:80]!r})"
        )
    classification, reason = rule(bullet)
    if classification not in CLASSIFICATIONS:
        raise KnowledgeDeliveryError(f"rule for section {bullet.section} produced {classification!r}")
    return classification, reason


def classify_inventory(repo_root: Path | str = REPO_ROOT) -> list[ClassifiedPath]:
    """Every bullet of the inventory, classified, in document order.

    Fails closed on a section without a rule and on a KEEP path that does not exist on disk:
    a KEEP path is a promise to deliver bytes, and a promise the tree cannot keep is a
    refusal here rather than a MISSING discovered at spawn time.
    """
    root = Path(repo_root)
    inventory = root / SOURCE_INVENTORY_PATH
    if not inventory.is_file():
        raise KnowledgeDeliveryError(f"source-file inventory is missing: {SOURCE_INVENTORY_PATH}")
    rows: list[ClassifiedPath] = []
    for bullet in parse_source_inventory(inventory.read_text(encoding="utf-8")):
        classification, reason = classify_bullet(bullet)
        exists = bullet.path is not None and (root / bullet.path).is_file()
        if classification == KEEP and not exists:
            raise KnowledgeDeliveryError(
                f"KEEP path does not exist under the repository root: {bullet.path!r} "
                f"(section {bullet.section}, line {bullet.line})"
            )
        rows.append(
            ClassifiedPath(
                section=bullet.section,
                line=bullet.line,
                bullet=bullet.bullet,
                path=bullet.path,
                classification=classification,
                reason=reason,
                exists=exists,
            )
        )
    return rows


# --------------------------------------------------------------------------------------
# The knowledge layers, bound to the KEEP files by content
# --------------------------------------------------------------------------------------
KNOWLEDGE_INPUT_POLICIES = frozenset({"STATIC_REQUIRED_INPUT", "ARM_REQUIRED_INPUT"})
"""The registry policies whose layers are inputs he reads before the call (pre-call, DIRECT)."""


@dataclass(frozen=True)
class LayerBinding:
    """Which KEEP files carry one registry knowledge layer, and why.

    `content_terms` is a regular expression every bound file must match. It is a NECESSARY
    condition the test suite checks - the file speaks about what the layer names - not a
    proof of sufficiency; the `why` clause carries the judgment, file by file, in words.
    """

    layer_id: str
    content_terms: str
    why: str
    paths: tuple[str, ...]
    description: str | None = None
    """When set, the rebind rewrites the registry entry's `description` too (S122: the
    a_memory_overlay layers said 'Verified ... prior lessons package' of a wrong-data package;
    a description that names the retired thing is a record that lies). None leaves it alone."""


_R = "research/"
_K = "research/kalshi/knowledge/"
_CHAIN_STUDY_CONTRACT = _R + "NG_EXHAUSTION_CHAIN_STUDY_CONTRACT_20260817.json"
_P2_FINAL_FREEZE = _R + "NG_EXHAUSTION_CHAIN_PHASE2_FINAL_FREEZE_20260818.md"
_P2_ALL_AGENT = _R + "NG_EXHAUSTION_CHAIN_PHASE2_ALL_AGENT_FINDINGS_20260818.md"
_P2_FINDINGS = _R + "NG_EXHAUSTION_CHAIN_PHASE2_FINDINGS_20260817.md"
_P2_TIMING = _R + "NG_EXHAUSTION_CHAIN_PHASE2_TIMING_CONTEXT_FINDINGS_20260818.md"
_P2_MODULE_NOVELTY = _R + "NG_EXHAUSTION_CHAIN_PHASE2_MODULE_NOVELTY_FINDINGS_20260818.md"
_P2_POSTEXIT = _R + "NG_EXHAUSTION_CHAIN_PHASE2_POSTEXIT_RECURRENCE_FINDINGS_20260818.md"
_P2_PARALLEL = _R + "NG_EXHAUSTION_CHAIN_PHASE2_PARALLEL_RECURRENCE_RECONCILIATION_20260818.md"
_P2_POX_ADDENDUM = _R + "NG_EXHAUSTION_CHAIN_PHASE2_FINDINGS_ADDENDUM_POX_20260818.md"
_P2_POX_BRANCH = _R + "NG_EXHAUSTION_CHAIN_PHASE2_POX_BRANCH_RECONCILIATION_V2_20260818.md"
_P2_POX_SAME = _R + "NG_EXHAUSTION_CHAIN_PHASE2_POX_SAME_POSTEXIT_REEXPRESSION_20260818.md"
_P2_WATCH_MAP = _R + "NG_EXHAUSTION_CHAIN_PHASE2_REAPPEARANCE_WATCH_MAP_20260818.json"
_P2_CHECKLIST = _R + "NG_EXHAUSTION_CHAIN_PHASE2_FINALIZATION_CHECKLIST_20260818.json"
_STEP1_FILE_MAP = _R + "NG_EXHAUSTION_CHAIN_STEP1_ORIGINAL_FILE_MAP_20260820.md"
_STEP1_CENSUS_MD = _R + "NG_EXHAUSTION_CHAIN_STEP1_5Y_V4_NATIVE_CENSUS_PROTOCOL_20260820.md"
_STEP1_CENSUS_JSON = _R + "NG_EXHAUSTION_CHAIN_STEP1_5Y_V4_NATIVE_CENSUS_PROTOCOL_20260820.json"
_CANONICAL_TABLE = _R + "ng_exhaustion_chain_canonical_table_20260817.py"
_CHARACTERIZE = _R + "ng_exhaustion_chain_phase2_characterize_20260817.py"
_PARALLEL_AGENTS = _R + "ng_exhaustion_chain_phase2_parallel_agents_20260818.py"
_STATE_ENRICH = _R + "ng_exhaustion_chain_state_enrich_20260817.py"
_CHAIN_STATE_ROSTER = _R + "ng_exhaustion_week_chain_state_roster_20260817.py"
_CONTINUOUS_ROSTER = _R + "ng_exhaustion_week_continuous_roster_20260817.py"
_PROPOSAL_INDEX = _R + "NG_EXHAUSTION_BRAIN_PROPOSAL_INDEX_20260818.md"
_PROPOSAL_INDEX_ADDENDUM = _R + "NG_EXHAUSTION_BRAIN_PROPOSAL_INDEX_ADDENDUM_20260820.md"
_CLEAN_SOURCE_CURRENT = _R + "NG_EXHAUSTION_V4_BRAIN_TRADE_PROPOSAL_CLEAN_SOURCE_CURRENT_20260820.md"
_V3_V4_ADDENDUM = _R + "NG_EXHAUSTION_V3_V4_BRAIN_TRADE_PROPOSAL_ADDENDUM_20260820.md"
_V3_V4_FINAL_ADDENDUM = _R + "NG_EXHAUSTION_V3_V4_BRAIN_TRADE_PROPOSAL_FINAL_ADDENDUM_20260820.md"
_P2_PROPOSAL_JSON = _K + "ng_brain_exhaustion_chain_phase2_proposal_20260818.json"
_BIRTH_V2_JSON = _K + "ng_brain_exhaustion_chain_birth_v2_proposal_20260819.json"
_ENTRY_TIMING_JSON = _K + "ng_brain_exhaustion_entry_timing_extension_20260818.json"
_POX_FOCUSED_JSON = _K + "ng_brain_exhaustion_pox_focused_proposal_20260819.json"
_INTERPRETATION_CORRECTION = _R + "NG_EXHAUSTION_V4_INTERPRETATION_CORRECTION_20260820.md"
_WALKFORWARD_CONTRACT = _R + "NG_EXHAUSTION_V4_CONTINUOUS_ADAPTIVE_WALKFORWARD_CONTRACT_20260820.md"
_D0_D5_CONTRACT_MD = _R + "NG_EXHAUSTION_D0_D5_V4_GEOMETRIC_SELF_ADAPTATION_CONTRACT_20260820.md"
_D0_D5_CONTRACT_JSON = _R + "NG_EXHAUSTION_D0_D5_V4_GEOMETRIC_SELF_ADAPTATION_CONTRACT_20260820.json"
_EVENT_MARK_CLOCK = _R + "NG_EXHAUSTION_EVENT_MARK_CLOCK_OPEN_BOUNDARY_20260819.md"
_PRELAUNCH_GATES = _R + "NG_EXHAUSTION_V4_CLEAN_SOURCE_PRELAUNCH_GATES_20260820.md"
_INSTANCE_TIMING_CORRECTION = _R + "NG_EXHAUSTION_CONTINUOUS_INSTANCE_TIMING_CORRECTION_20260820.md"
_LIVE_INFORMATION_CORRECTION = _R + "NG_EXHAUSTION_CONTINUOUS_LIVE_INFORMATION_CORRECTION_20260819.md"
_FULL_CAUSAL_CORRECTION = _R + "NG_EXHAUSTION_FULL_CAUSAL_INFORMATION_CORRECTION_20260819.md"
_PRIOR_MODEL_PRICE_CORRECTION = _R + "NG_EXHAUSTION_PRIOR_MODEL_PRICE_CORRECTION_20260819.md"
_POLARITY_CORRECTION = _R + "NG_EXHAUSTION_POLARITY_NOT_PRIMARY_TARGET_CORRECTION_20260819.md"

KNOWLEDGE_LAYER_SOURCES: tuple[LayerBinding, ...] = (
    # --- frozen_learned_structure (authority FROZEN_LEARNED_KNOWLEDGE) ------------------
    LayerBinding(
        layer_id="learned_d_structures_and_families",
        content_terms=r"\bD[0-5]\b|D-structure|D structure|famil(?:y|ies)",
        why=(
            "the D-depth structures (D1-D5) and D families as frozen by phase 2: the chain study "
            "contract that defines them, the phase-2 freeze and findings that count them, the "
            "canonical table that computes them, the weekly rosters that carry them, and the D0-D5 "
            "geometric contract that governs their V4 representation"
        ),
        paths=(
            _CHAIN_STUDY_CONTRACT, _P2_FINAL_FREEZE, _P2_ALL_AGENT, _P2_FINDINGS, _P2_TIMING,
            _CANONICAL_TABLE, _CHAIN_STATE_ROSTER, _CONTINUOUS_ROSTER,
            _D0_D5_CONTRACT_MD, _D0_D5_CONTRACT_JSON,
        ),
    ),
    LayerBinding(
        layer_id="learned_dipoles_and_geometry",
        content_terms=r"dipole|geometr",
        why=(
            "the roll20/dipole polarity computation in the canonical table, the geometric "
            "representation and flow/dipole semantics of the current proposal, the D0-D5 geometric "
            "self-adaptation contract, and the event-mark clock boundary fixing when dipole polarity "
            "may be read"
        ),
        paths=(
            _CANONICAL_TABLE, _CLEAN_SOURCE_CURRENT, _D0_D5_CONTRACT_MD, _D0_D5_CONTRACT_JSON,
            _EVENT_MARK_CLOCK,
        ),
    ),
    LayerBinding(
        layer_id="learned_pair_triplet_recurrence",
        content_terms=r"\bpair\b|triplet|recurrence",
        why=(
            "the pair/triplet module recurrence of phase 2 (PP|S, PO|S, OO|F, ...) in the freeze, "
            "all-agent, timing-context and post-exit findings, its four-lane parallel reconciliation "
            "and runner, the recurrence atlas of the proposal index, and the modular_recurrence "
            "lessons of the phase-2 proposal"
        ),
        paths=(
            _P2_FINAL_FREEZE, _P2_ALL_AGENT, _P2_TIMING, _P2_POSTEXIT, _P2_PARALLEL,
            _PARALLEL_AGENTS, _PROPOSAL_INDEX, _P2_PROPOSAL_JSON,
        ),
    ),
    LayerBinding(
        layer_id="learned_chains_extensions_reappearances_ancestry",
        content_terms=r"\bchain|extension|reappear|ancestr|successor|lineage|continuity",
        why=(
            "the chain study contract, the phase-2 chain/extension/re-expression findings, the "
            "reappearance watch map, the phase-1 lineage and continuity implementations, the "
            "chain-state enrichment and roster, and the proposal index, phase-2 and chain-birth "
            "proposals that carry chain doctrine"
        ),
        paths=(
            _CHAIN_STUDY_CONTRACT, _P2_FINAL_FREEZE, _P2_ALL_AGENT, _P2_POSTEXIT, _P2_POX_SAME,
            _P2_WATCH_MAP,
            _R + "ng_exhaustion_chain_phase1_lineage_54w_20260817.py",
            _R + "ng_exhaustion_chain_phase1_continuity_54w_20260817.py",
            _STATE_ENRICH, _CHAIN_STATE_ROSTER,
            _PROPOSAL_INDEX, _P2_PROPOSAL_JSON, _BIRTH_V2_JSON,
        ),
    ),
    LayerBinding(
        layer_id="phase1_discoveries_structural_falsifiers",
        content_terms=r"phase.?1|falsif|discover|54w|54-week",
        why=(
            "the phase-1 54/55-week base freeze, execution, causal and discovery protocols, "
            "mechanism addendum and reconcile launch, the phase-1 discovery / causal / continuity / "
            "falsifier / lineage / structural / reconcile implementations, the canonical 54-week "
            "merge and shard that built the base, and the original file map"
        ),
        paths=(
            _CHAIN_STUDY_CONTRACT,
            _R + "NG_EXHAUSTION_CHAIN_PHASE1_54W_BASE_FREEZE_20260817.json",
            _R + "NG_EXHAUSTION_CHAIN_PHASE1_54W_EXECUTION_PROTOCOL_20260817.json",
            _R + "NG_EXHAUSTION_CHAIN_PHASE1_CAUSAL_PROTOCOL_20260817.json",
            _R + "NG_EXHAUSTION_CHAIN_PHASE1_DISCOVERY_PROTOCOL_20260817.json",
            _R + "NG_EXHAUSTION_CHAIN_PHASE1_MECHANISM_ADDENDUM_20260817.json",
            _R + "NG_EXHAUSTION_CHAIN_PHASE1_55W_RECONCILE_LAUNCH_20260817.json",
            _STEP1_FILE_MAP,
            _R + "ng_exhaustion_chain_canonical_54w_merge_20260817.py",
            _R + "ng_exhaustion_chain_canonical_54w_shard_20260817.py",
            _R + "ng_exhaustion_chain_phase1_discovery_20260817.py",
            _R + "ng_exhaustion_chain_phase1_causal_54w_20260817.py",
            _R + "ng_exhaustion_chain_phase1_continuity_54w_20260817.py",
            _R + "ng_exhaustion_chain_phase1_falsifier_54w_20260817.py",
            _R + "ng_exhaustion_chain_phase1_lineage_54w_20260817.py",
            _R + "ng_exhaustion_chain_phase1_structural_54w_20260817.py",
            _R + "ng_exhaustion_chain_phase1_reconcile_55w_20260817.py",
        ),
    ),
    LayerBinding(
        layer_id="phase2_findings_modules_timing_pox_negatives",
        content_terms=(
            r"phase.?2|\bPOX\b|P-O-X|negative|stopped|persistent_exhaustion|collapsed_opposite"
        ),
        why=(
            "every phase-2 finding record (final freeze, all-agent, module novelty, timing context, "
            "post-exit recurrence, the POX addendum and branch reconciliations, same-post-exit "
            "re-expression), the reappearance watch map and finalization checklist, the "
            "characterize and parallel-lane implementations (the latter defines the S/O/P/X state "
            "vocabulary), and the phase-2, POX-focused and entry-timing proposals with their "
            "negative and stopped-chain cases"
        ),
        paths=(
            _P2_FINAL_FREEZE, _P2_ALL_AGENT, _P2_FINDINGS, _P2_TIMING, _P2_MODULE_NOVELTY,
            _P2_POSTEXIT, _P2_PARALLEL, _P2_POX_ADDENDUM, _P2_POX_BRANCH, _P2_POX_SAME,
            _P2_WATCH_MAP, _P2_CHECKLIST, _CHARACTERIZE, _PARALLEL_AGENTS,
            _P2_PROPOSAL_JSON, _POX_FOCUSED_JSON, _ENTRY_TIMING_JSON,
        ),
    ),
    LayerBinding(
        layer_id="predecessor_ancestry_unresolved_chain_state",
        content_terms=r"predecessor|unresolved",
        why=(
            "predecessor and unresolved-chain state: the phase-1 causal protocol, the Step-1 native "
            "census protocol, the current proposal's unresolved predecessor lifecycle, prelaunch "
            "gate 5, the D0-D5 contract's active-instance lifecycle, the PRIOR-model and full-causal "
            "information corrections, the phase-2 findings and characterize implementation, and the "
            "chain-birth proposal's predecessor-relative PRIOR rule"
        ),
        paths=(
            _R + "NG_EXHAUSTION_CHAIN_PHASE1_CAUSAL_PROTOCOL_20260817.json",
            _STEP1_CENSUS_MD, _STEP1_CENSUS_JSON, _CLEAN_SOURCE_CURRENT, _PRELAUNCH_GATES,
            _D0_D5_CONTRACT_MD, _PRIOR_MODEL_PRICE_CORRECTION, _FULL_CAUSAL_CORRECTION,
            _P2_FINDINGS, _CHARACTERIZE, _BIRTH_V2_JSON,
        ),
    ),
    LayerBinding(
        layer_id="historical_timing_lifespan_context",
        content_terms=r"timing|lifespan|runway|clock",
        why=(
            "timing and lifespan as CONTEXT, never a target clock: the phase-2 timing-context "
            "findings, the continuous-instance timing correction, the walk-forward contract (timing "
            "is an output), the event-mark clock boundary, the clock-separation and PRIOR "
            "corrections, the current proposal's causal knowledge clocks, the characterize "
            "implementation's timing families, and the chain-birth, entry-timing and phase-2 "
            "proposals' timing lessons"
        ),
        paths=(
            _P2_TIMING, _INSTANCE_TIMING_CORRECTION, _WALKFORWARD_CONTRACT, _EVENT_MARK_CLOCK,
            _FULL_CAUSAL_CORRECTION, _CLEAN_SOURCE_CURRENT, _PRIOR_MODEL_PRICE_CORRECTION,
            _CHARACTERIZE, _BIRTH_V2_JSON, _ENTRY_TIMING_JSON, _P2_PROPOSAL_JSON,
        ),
    ),
    LayerBinding(
        layer_id="learned_structure_proposal_index_material",
        content_terms=r"proposal|index|correction|contract|inventory|interpret|clarif",
        why=(
            "the proposal lineage WHOLE (index, index addendum, clean current source, the two V3-V4 "
            "addenda and the four JSON proposals - Greg, 2026-09-02), every V4 governing contract "
            "and correction that controls how the structures are interpreted, the original file "
            "map, and the two canonical inventories as the index of the corpus"
        ),
        paths=(
            _PROPOSAL_INDEX, _PROPOSAL_INDEX_ADDENDUM, _CLEAN_SOURCE_CURRENT,
            _V3_V4_ADDENDUM, _V3_V4_FINAL_ADDENDUM,
            _P2_PROPOSAL_JSON, _BIRTH_V2_JSON, _ENTRY_TIMING_JSON, _POX_FOCUSED_JSON,
            _INTERPRETATION_CORRECTION, _WALKFORWARD_CONTRACT, _D0_D5_CONTRACT_MD,
            _D0_D5_CONTRACT_JSON, _EVENT_MARK_CLOCK, _PRELAUNCH_GATES,
            _INSTANCE_TIMING_CORRECTION, _LIVE_INFORMATION_CORRECTION, _FULL_CAUSAL_CORRECTION,
            _PRIOR_MODEL_PRICE_CORRECTION, _POLARITY_CORRECTION,
            _STEP1_FILE_MAP, FEED_INVENTORY_PATH, SOURCE_INVENTORY_PATH,
        ),
    ),
    # --- current_brain_runtime (authority CURRENT_BRAIN) ------------------------------------
    LayerBinding(
        layer_id="authoritative_s135_construction",
        content_terms=r"built_pass|merge_log|changelog",
        why=(
            "the brain the S135 runtime constructs and loads; its meta carries the construction "
            "record (built_pass, merge_log, changelog, sections). The S120-S135 runtime modules that "
            "apply it are CODE (addendum note 2); whether that construction code should ALSO be "
            "delivered is a D60 item for Greg, recorded not decided"
        ),
        paths=(BRAIN_PATH,),
    ),
    LayerBinding(
        layer_id="complete_s105_9_brain",
        content_terms=r"\"plays\"|\"version\"",
        why="the complete brain file: version, every play body, mechanisms, open_frontier, fingerprints",
        paths=(BRAIN_PATH,),
    ),
    LayerBinding(
        layer_id="doctrine_reasoning_play_index_evidence",
        content_terms=r"doctrine|reasoning_method|falsifier",
        why=(
            "the brain's doctrine, reasoning_method, play index and each play's falsifier, support, "
            "instances and corpus fields (negatives and contradictions live inside them)"
        ),
        paths=(BRAIN_PATH,),
    ),
    LayerBinding(
        layer_id="lawful_prior_session_carry",
        content_terms=r"prior session|handoff_out|carry",
        why=(
            "the brain's handoff_out_schema and the prior-session rules inside plays and doctrine; "
            "the mission (bound in binding_common_controls) states what one run may carry"
        ),
        paths=(BRAIN_PATH,),
    ),
    LayerBinding(
        layer_id="october_outcome_wall_enforcement",
        content_terms=r"ruled_out_by_target|reveal|sealed|wall|outcome",
        why=(
            "the brain's ruled_out_by_target, the walk-forward contract's outcome-reveal timing, "
            "prelaunch gates 7 and 8 (immutable ledger, sealed handoff), the D0-D5 contract's "
            "post-reveal self-edit boundary and the current proposal's immutable ledger and sealed "
            "handoff: the wall the October run enforces (the answer itself is section K, SEALED)"
        ),
        paths=(
            BRAIN_PATH, _WALKFORWARD_CONTRACT, _PRELAUNCH_GATES, _D0_D5_CONTRACT_MD,
            _CLEAN_SOURCE_CURRENT,
        ),
    ),
)
"""Layer -> KEEP files, by content. `extra_agent_corrected_information_and_gap_diagnoses` is not
here because it already binds its three section-F files; the binding inputs (mission, contract,
manifest, profile, capsules) already bind real files too. Every C/D/E/F KEEP file lands in at
least one binding - the test suite derives that set from the inventory and checks it."""


A_MEMORY_SEED_PATH = "research/kalshi/frankie_raw_mbo_benchmark/A_MEMORY_SEED_20260902.json"
"""The A-memory seed (D86/D88), built by `build_a_memory_seed.py`: every committed output of the
past runs, provenance-labelled, UNVERIFIED. Not an inventory KEEP path - it is a generated record
of the package - so its bindings live beside KNOWLEDGE_LAYER_SOURCES, not inside it."""

A_MEMORY_SEED_LAYER_SOURCES: tuple[LayerBinding, ...] = (
    LayerBinding(
        layer_id="a_memory_prior_lessons_package",
        content_terms=r"UNVERIFIED|32851909748|provenance",
        why=(
            "D86/D88: memory is his own day-over-day carry, seeded on day one with every committed "
            "output of the past runs (the last run 33605852433, the reduced wrong-data run "
            "32851909748-1 AS the wrong-data run, the capsules and their sources, the S119 measured "
            "knowledge), each with sha256, bytes and a provenance label, every lesson UNVERIFIED; "
            "the wrong-data lessons package (external:a_memory_prior_lessons_package, sha256 "
            "b487acfb...) is retired from the registry"
        ),
        paths=(A_MEMORY_SEED_PATH,),
        description=(
            "A-memory seed memory: every committed output of the past runs, provenance-labelled, "
            "UNVERIFIED (D86, D88); from day two his own prior-day frozen outputs plus the seed"
        ),
    ),
    LayerBinding(
        layer_id="a_memory_prior_package_proof",
        content_terms=r"\"sha256\"|seed_hash",
        why=(
            "the proof of the seed is the seed itself: its per-entry sha256 and byte counts and its "
            "seed_hash, verified by build_a_memory_seed --check against the bytes on disk and pinned "
            "by hash in the mission and the knowledge manifest; no external proof receipt exists "
            "(external:a_memory_prior_lessons_package_proof, sha256 d54c6191..., is retired)"
        ),
        paths=(A_MEMORY_SEED_PATH,),
        description=(
            "Proof of the A-memory seed: its per-entry sha256 and byte list and seed_hash, bound as "
            "the seed file's own bytes (no external binding)"
        ),
    ),
)

ALL_LAYER_SOURCES: tuple[LayerBinding, ...] = KNOWLEDGE_LAYER_SOURCES + A_MEMORY_SEED_LAYER_SOURCES
"""Every binding the rebind applies: the KEEP-file bindings and the seed bindings."""


def layers_bound_only_to(
    registry: Mapping[str, Any], path: str, *, policies: frozenset[str] | None = None
) -> list[str]:
    """Layer ids whose ONLY source path is `path` - the S120 defect, made measurable.

    With `path` = the registry's `source_authority` and `policies` = the pre-call input
    policies, this is the list of knowledge layers that would be "delivered" by proving a
    document unchanged. It must be empty.
    """
    found: list[str] = []
    for group in registry.get("groups", []):
        if policies is not None and group.get("policy") not in policies:
            continue
        for entry in group.get("entries", []):
            if set(entry.get("source_paths", [])) == {path}:
                found.append(entry["layer_id"])
    return found


# --------------------------------------------------------------------------------------
# S122 slice 3: the knowledge delivery RECEIPT, from the existing pipeline, per layer
# --------------------------------------------------------------------------------------
KNOWLEDGE_DIR = "research/kalshi/agents/frankie_native_raw_mbo_knowledge/"
MANIFEST_PATH = KNOWLEDGE_DIR + "KNOWLEDGE_MANIFEST_20260828.json"
SPEC_PATH = KNOWLEDGE_DIR + "KNOWLEDGE_SOURCES_20260828.json"
KNOWLEDGE_RECEIPT_SCHEMA = "FRANKIE_KNOWLEDGE_DELIVERY_RECEIPT_V1"
"""The per-layer receipt `native_layer_crosswalk._static_status` consumes: `layers[]` rows of
`layer_id`, `status` and `files[] {path, sha256, bytes}`. Produced here, from the EXISTING
pipeline (`build_context_bundle` -> `build_model_visible_context`), never hand-written."""
KNOWLEDGE_USE_SCHEMA = "FRANKIE_PRINCIPAL_KNOWLEDGE_USE_V1"
"""What the principal's artifact carries under `knowledge_use`: one disposition per delivered
artifact id, INSPECTED or UNINSPECTED, each with a reason; validated by `validate_knowledge_use`
through the EXISTING read gate `bind_principal_knowledge_use`."""
KNOWLEDGE_BUNDLE_FILENAME = "KNOWLEDGE_BUNDLE.md"
KNOWLEDGE_RECEIPT_FILENAME = "KNOWLEDGE_RECEIPT.json"
KNOWLEDGE_PRECALL_FILENAME = "KNOWLEDGE_PRECALL_RECEIPT.json"
MANIFEST_ARTIFACT = "MANIFEST_ARTIFACT"
"""A file delivered as a manifest artifact routed to the profile: its hash is the manifest's."""
BINDING_DOCUMENT = "BINDING_DOCUMENT"
"""The two documents that PIN the delivery and so cannot be artifacts of it - the manifest and
the sources spec - delivered by their own bytes hashed on disk, with the manifest's
`manifest_hash` bound in the context receipt and the profile selected from it."""
DISPOSITIONS = ("INSPECTED", "UNINSPECTED")
DELIVERED = "DELIVERED"
NOT_DELIVERED = "NOT_DELIVERED"


@dataclass(frozen=True)
class KnowledgeDelivery:
    """One arm/role's knowledge as the pipeline built it, plus the per-layer receipt over it."""

    arm: str
    role: str
    profile_id: str
    receipt: dict[str, Any]
    pre_call: dict[str, Any]
    model_visible_context: bytes


def _profile_for(manifest: Mapping[str, Any], arm: str, role: str) -> str:
    """The profile is DERIVED from arm and role; exactly one must exist."""
    found = [pid for pid, p in manifest["profiles"].items() if p["arm"] == arm and p["role"] == role]
    if len(found) != 1:
        raise KnowledgeDeliveryError(
            f"the manifest carries {len(found)} knowledge profile(s) for arm {arm!r} role {role!r}; exactly one is required"
        )
    return found[0]


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_manifest_bytes(manifest: Mapping[str, Any], root: Path) -> None:
    """A receipt names bytes on disk; a manifest row whose file drifted is a refusal here."""
    for row in manifest["artifacts"]:
        target = root / row["path"]
        if not target.is_file():
            raise KnowledgeDeliveryError(f"manifest artifact missing on disk: {row['path']}")
        if target.stat().st_size != row["bytes"] or _file_sha256(target) != row["sha256"]:
            raise KnowledgeDeliveryError(
                f"manifest artifact {row['id']} ({row['path']}) does not hash to the manifest's sha256; "
                "the knowledge on disk is not the knowledge the manifest pins"
            )


def build_knowledge_delivery(
    *,
    arm: str = "A_MEMORY",
    role: str = "REAL_TIME_FRANKIE",
    registry: Mapping[str, Any] | None = None,
    manifest: Mapping[str, Any] | None = None,
    repo_root: Path | str = REPO_ROOT,
) -> KnowledgeDelivery:
    """Run the EXISTING pipeline for one arm/role and translate it into the per-layer receipt.

    `build_context_bundle` concatenates the profile's ALWAYS_LOAD artifacts and receipts the
    whole retrieval catalog; `build_model_visible_context` appends the hash-bound retrieval
    index and binds external proofs (none since the wrong-data binding was retired, D86).
    Each applicable knowledge layer of the registry (policies STATIC_REQUIRED_INPUT and
    ARM_REQUIRED_INPUT, arm in the group's arms) is then answered path by path off its own
    `source_paths`: a path that is a routed manifest artifact is delivered with the
    manifest's hash; the manifest and the sources spec - the two documents that pin the
    delivery - are delivered by their own bytes; anything else is MISSING and the layer reads
    NOT_DELIVERED. Nothing is read off a policy.
    """
    root = Path(repo_root)
    active = load_registry() if registry is None else registry
    try:
        loaded = (
            load_and_validate_manifest(root / MANIFEST_PATH, root) if manifest is None else dict(manifest)
        )
    except KnowledgeRegistryError as exc:
        raise KnowledgeDeliveryError(f"knowledge manifest refused: {exc}") from exc
    _verify_manifest_bytes(loaded, root)
    profile_id = _profile_for(loaded, arm, role)
    try:
        model_visible_context, pre_call = build_model_visible_context(
            loaded, profile_id, root, external_proofs={}
        )
    except KnowledgeRegistryError as exc:
        raise KnowledgeDeliveryError(f"context bundle refused for {profile_id}: {exc}") from exc
    context_receipt = pre_call["context_receipt"]
    artifacts: list[dict[str, Any]] = []
    for load_mode, rows in (("ALWAYS_LOAD", context_receipt["loaded_artifacts"]),
                            ("RETRIEVAL", context_receipt["retrieval_catalog"])):
        for row in rows:
            artifacts.append({**row, "load_mode": load_mode})
    by_path = {row["path"]: row for row in artifacts}
    binding_documents: dict[str, dict[str, Any]] = {}
    for relative in (MANIFEST_PATH, SPEC_PATH):
        target = root / relative
        if not target.is_file():
            raise KnowledgeDeliveryError(f"binding document missing on disk: {relative}")
        binding_documents[relative] = {"sha256": _file_sha256(target), "bytes": target.stat().st_size}

    layers: list[dict[str, Any]] = []
    for group in active["groups"]:
        if group["policy"] not in KNOWLEDGE_INPUT_POLICIES or arm not in group["arms"]:
            continue
        for entry in group["entries"]:
            files: list[dict[str, Any]] = []
            missing: list[str] = []
            for path in entry["source_paths"]:
                if path in by_path:
                    row = by_path[path]
                    files.append({
                        "path": path, "sha256": row["sha256"], "bytes": row["bytes"],
                        "delivery": MANIFEST_ARTIFACT, "artifact_id": row["id"], "load_mode": row["load_mode"],
                    })
                elif path in binding_documents:
                    files.append({
                        "path": path, **binding_documents[path],
                        "delivery": BINDING_DOCUMENT, "artifact_id": None, "load_mode": None,
                    })
                else:
                    missing.append(path)
            layers.append({
                "layer_id": entry["layer_id"],
                "group_id": group["group_id"],
                "policy": group["policy"],
                "status": DELIVERED if files and not missing else NOT_DELIVERED,
                "files": files,
                "missing": missing,
            })
    memory_findings: list[dict[str, Any]] = []
    seed_path = root / A_MEMORY_SEED_PATH
    if arm == "A_MEMORY" and seed_path.is_file():
        try:
            seed_body = json.loads(seed_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise KnowledgeDeliveryError(f"A-memory seed is not valid JSON: {exc}") from exc
        memory_findings = served_memory_findings(seed_body)
    receipt: dict[str, Any] = {
        "schema": KNOWLEDGE_RECEIPT_SCHEMA,
        "arm": arm,
        "role": role,
        "profile_id": profile_id,
        "registry_sha256": active["registry_sha256"],
        "manifest_path": MANIFEST_PATH,
        "manifest_hash": loaded["manifest_hash"],
        "manifest_file_sha256": binding_documents[MANIFEST_PATH]["sha256"],
        "spec_path": SPEC_PATH,
        "spec_file_sha256": binding_documents[SPEC_PATH]["sha256"],
        "context_receipt_hash": context_receipt["receipt_hash"],
        "pre_call_receipt_hash": pre_call["pre_call_receipt_hash"],
        "context_bundle_sha256": context_receipt["context_bundle_sha256"],
        "context_bundle_bytes": context_receipt["context_bundle_bytes"],
        "model_visible_context_sha256": pre_call["model_visible_context_sha256"],
        "model_visible_context_bytes": pre_call["model_visible_context_bytes"],
        "retrieval_index_sha256": pre_call["retrieval_index_sha256"],
        "bundle_filename": KNOWLEDGE_BUNDLE_FILENAME,
        "artifacts": artifacts,
        "memory_findings": memory_findings,
        "layers": layers,
        "totals": {
            "layers": len(layers),
            "delivered": sum(1 for row in layers if row["status"] == DELIVERED),
            "not_delivered": sum(1 for row in layers if row["status"] != DELIVERED),
            "artifacts": len(artifacts),
            "always_load": sum(1 for a in artifacts if a["load_mode"] == "ALWAYS_LOAD"),
            "retrieval": sum(1 for a in artifacts if a["load_mode"] == "RETRIEVAL"),
            "files": sum(len(row["files"]) for row in layers),
            "missing": sum(len(row["missing"]) for row in layers),
        },
        "pre_call": pre_call,
        "receipt_sha256": "",
    }
    receipt["receipt_sha256"] = canonical_hash(receipt, omit="receipt_sha256")
    return KnowledgeDelivery(
        arm=arm, role=role, profile_id=profile_id, receipt=receipt, pre_call=pre_call,
        model_visible_context=model_visible_context,
    )


def write_knowledge_delivery(delivery: KnowledgeDelivery, out_dir: Path | str) -> dict[str, Path]:
    """Write the bundle, the receipt and the pre-call receipt BESIDE the prompt (fixed names)."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    bundle = out / KNOWLEDGE_BUNDLE_FILENAME
    receipt = out / KNOWLEDGE_RECEIPT_FILENAME
    pre_call = out / KNOWLEDGE_PRECALL_FILENAME
    bundle.write_bytes(delivery.model_visible_context)
    receipt.write_text(json.dumps(delivery.receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    pre_call.write_text(json.dumps(delivery.pre_call, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"bundle": bundle, "receipt": receipt, "pre_call": pre_call}


def serialized_principal_input(prompt_bytes: bytes, model_visible_context: bytes) -> bytes:
    """The principal's input as the read gate sees it: the prompt file and the bundle file.

    He is spawned as an agent session over committed files (D70), so the input is two files
    beside each other, not one string. Both sides of the gate build the same bytes this way,
    and `bind_principal_knowledge_use` proves the exact model-visible context is inside.
    """
    return bytes(prompt_bytes) + b"\n" + bytes(model_visible_context)


def render_knowledge_block(receipt: Mapping[str, Any]) -> str:
    """The prompt section naming every delivered knowledge file with its sha256 and the receipt.

    Knowledge layer ids and KEEP paths only - no sealed token can appear here, and the
    sealed-absence proof scans this text anyway.
    """
    if receipt.get("schema") != KNOWLEDGE_RECEIPT_SCHEMA:
        raise KnowledgeDeliveryError(f"not a {KNOWLEDGE_RECEIPT_SCHEMA}")
    lines: list[str] = []
    add = lines.append
    add("## Your knowledge, delivered and receipted")
    add("")
    add(f"Knowledge receipt `{receipt['receipt_sha256']}` (`{KNOWLEDGE_RECEIPT_SCHEMA}`), profile")
    add(f"`{receipt['profile_id']}` (arm `{receipt['arm']}`, role `{receipt['role']}`), from the hash-bound")
    add(f"manifest `{receipt['manifest_path']}` (manifest_hash `{receipt['manifest_hash']}`, file sha256")
    add(f"`{receipt['manifest_file_sha256']}`) and the profile spec `{receipt['spec_path']}` (sha256")
    add(f"`{receipt['spec_file_sha256']}`). Registry sha256 `{receipt['registry_sha256']}`.")
    add("")
    add(f"Your model-visible context is the file `{receipt['bundle_filename']}` beside this prompt")
    add(f"(sha256 `{receipt['model_visible_context_sha256']}`, {int(receipt['model_visible_context_bytes']):,} bytes):")
    add("every ALWAYS_LOAD artifact inline, then the hash-bound retrieval index. **Read it in full")
    add("first.** RETRIEVAL artifacts are read by path; each is named below with the sha256 its")
    add("bytes must have.")
    add("")
    totals = receipt["totals"]
    add(f"### Knowledge layers: {totals['delivered']} of {totals['layers']} applicable DELIVERED")
    add("")
    add("| layer | group | status | files |")
    add("|---|---|---|---|")
    for row in receipt["layers"]:
        files = "; ".join(f"`{f['path']}` `{f['sha256'][:12]}`" for f in row["files"])
        missing = ("; MISSING: " + ", ".join(f"`{m}`" for m in row["missing"])) if row["missing"] else ""
        add(f"| `{row['layer_id']}` | {row['group_id']} | {row['status']} | {files}{missing} |")
    add("")
    add(f"### Delivered artifacts: {totals['artifacts']} ({totals['always_load']} inline, {totals['retrieval']} by path)")
    add("")
    add("| artifact id | load | path | sha256 | bytes |")
    add("|---|---|---|---|---:|")
    for artifact in receipt["artifacts"]:
        add(f"| `{artifact['id']}` | {artifact['load_mode']} | `{artifact['path']}` | `{artifact['sha256']}` | {int(artifact['bytes']):,} |")
    add("")
    seeds = [a for a in receipt["artifacts"] if a["path"] == A_MEMORY_SEED_PATH]
    if seeds:
        add("### Memory")
        add("")
        add(f"`{A_MEMORY_SEED_PATH}` (sha256 `{seeds[0]['sha256']}`) is your day-one memory (D86, D88):")
        add("every committed output of the past runs, provenance-labelled, every lesson UNVERIFIED")
        add("until you verify it against the stream. From day two only admitted new findings")
        add("accumulate. Empty findings artifacts remain run receipts and add no memory entry.")
        add("The reduced wrong-data run 32851909748-1 remains labelled as the wrong-data run.")
        add("")
    memory_findings = receipt.get("memory_findings", [])
    if memory_findings:
        add("### Admitted day-over-day findings served now")
        add("")
        add("Only findings whose committed label permits service appear here. Vetoed findings")
        add("remain in the seed as run evidence and are never rendered into this served list.")
        add("")
        for row in memory_findings:
            add(f"#### {row['id']} — {row['status']}")
            add(f"- claim: {row['claim']}")
            add(f"- evidence: {json.dumps(row['evidence'], sort_keys=True, ensure_ascii=True)}")
            add(f"- falsifier: {row['falsifier']}")
            add(f"- confidence_basis: {row['confidence_basis']}")
            provenance = row.get("provenance", {})
            add(f"- source: run `{provenance.get('run_id')}`, day `{provenance.get('source_day')}`")
            add("")
    add("### What you return about knowledge")
    add("")
    add(f"`knowledge_receipt_sha256` is `{receipt['receipt_sha256']}`. `knowledge_use` is an object of")
    add(f"schema `{KNOWLEDGE_USE_SCHEMA}` carrying `knowledge_receipt_sha256`, `profile_id`, `arm`,")
    add("`role`, `manifest_hash`, `context_bundle_sha256` exactly as receipted, and `dispositions`:")
    add("**one entry per artifact id in the table above**, each `{\"disposition\": \"INSPECTED\" |")
    add("\"UNINSPECTED\", \"reason\": \"<why>\"}`. An artifact missing from the inventory, an id nobody")
    add("delivered, a disposition other than those two, or an empty reason is refused by the staging")
    add("gate through the read gate (`bind_principal_knowledge_use`). UNINSPECTED with an honest")
    add("reason is a valid answer; a claimed inspection is not. Every lesson you receive is")
    add(f"UNVERIFIED until you file its verdict in `output_knowledge_verification` citing this receipt.")
    add("")
    return "\n".join(lines)


def served_memory_findings(seed: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return only findings whose persistent seed label permits serving."""
    memory = seed.get("finding_memory", seed)
    rows = memory.get("findings", []) if isinstance(memory, Mapping) else []
    if not isinstance(rows, list):
        raise KnowledgeDeliveryError("A-memory seed finding_memory.findings must be a list")
    served: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise KnowledgeDeliveryError("an A-memory finding is not an object")
        status = row.get("status")
        is_served = row.get("served")
        if status == "VETOED":
            if is_served is not False:
                raise KnowledgeDeliveryError(f"vetoed finding {row.get('id')!r} is marked served")
            continue
        if status != "UNVERIFIED" or is_served is not True:
            raise KnowledgeDeliveryError(
                f"finding {row.get('id')!r} has unsupported service label {status!r}/{is_served!r}"
            )
        served.append(dict(row))
    return served


def complete_knowledge_use(
    receipt: Mapping[str, Any], *, disposition: str = "INSPECTED", reason: str = "read in full"
) -> dict[str, Any]:
    """A `knowledge_use` with one disposition per delivered artifact. For tests and examples."""
    return {
        "schema": KNOWLEDGE_USE_SCHEMA,
        "knowledge_receipt_sha256": receipt["receipt_sha256"],
        "profile_id": receipt["profile_id"],
        "arm": receipt["arm"],
        "role": receipt["role"],
        "manifest_hash": receipt["manifest_hash"],
        "context_bundle_sha256": receipt["context_bundle_sha256"],
        "dispositions": {
            artifact["id"]: {"disposition": disposition, "reason": reason} for artifact in receipt["artifacts"]
        },
    }


def _require_knowledge_receipt(receipt: Any) -> dict[str, Any]:
    if not isinstance(receipt, Mapping) or receipt.get("schema") != KNOWLEDGE_RECEIPT_SCHEMA:
        raise KnowledgeDeliveryError(f"knowledge receipt is not a {KNOWLEDGE_RECEIPT_SCHEMA}")
    if receipt.get("receipt_sha256") != canonical_hash(receipt, omit="receipt_sha256"):
        raise KnowledgeDeliveryError("knowledge receipt fails its own receipt_sha256; tampered or partial")
    return dict(receipt)


def validate_knowledge_use(
    knowledge_use: Mapping[str, Any],
    *,
    knowledge_receipt: Mapping[str, Any],
    model_visible_context: bytes,
    serialized_principal_input: bytes,
) -> dict[str, Any]:
    """The artifact's `knowledge_use`, validated through the EXISTING read gate.

    Every delivered artifact (ALWAYS_LOAD and RETRIEVAL alike) must carry INSPECTED or
    UNINSPECTED with a reason; a missing id, an undelivered id, another word, or an empty
    reason is refused BY NAME. The retrieval dispositions then go through
    `bind_principal_knowledge_use`, which proves the exact model-visible context sits inside
    the serialized principal input and binds profile, manifest and bundle hashes. Returns the
    registry's USE receipt extended with the always-load dispositions and the knowledge
    receipt hash, re-hashed over the extended body (`bound_use_receipt_hash` keeps the
    registry's own).
    """
    receipt = _require_knowledge_receipt(knowledge_receipt)
    if not isinstance(knowledge_use, Mapping):
        raise KnowledgeDeliveryError("knowledge_use must be an object")
    if knowledge_use.get("schema") != KNOWLEDGE_USE_SCHEMA:
        raise KnowledgeDeliveryError(f"knowledge_use schema must be {KNOWLEDGE_USE_SCHEMA}")
    if knowledge_use.get("knowledge_receipt_sha256") != receipt["receipt_sha256"]:
        raise KnowledgeDeliveryError(
            f"knowledge_use cites knowledge_receipt_sha256 {knowledge_use.get('knowledge_receipt_sha256')!r}; "
            f"the delivered receipt is {receipt['receipt_sha256']}"
        )
    for field in ("profile_id", "arm", "role", "manifest_hash", "context_bundle_sha256"):
        if knowledge_use.get(field) != receipt[field]:
            raise KnowledgeDeliveryError(f"knowledge_use.{field} {knowledge_use.get(field)!r} is not the receipted {receipt[field]!r}")
    dispositions = knowledge_use.get("dispositions")
    if not isinstance(dispositions, Mapping):
        raise KnowledgeDeliveryError("knowledge_use.dispositions must be an object of artifact id -> {disposition, reason}")
    delivered = {artifact["id"]: artifact for artifact in receipt["artifacts"]}
    missing = sorted(set(delivered) - set(dispositions))
    if missing:
        raise KnowledgeDeliveryError(f"knowledge_use carries no disposition for delivered artifact(s): {missing}")
    extra = sorted(set(dispositions) - set(delivered))
    if extra:
        raise KnowledgeDeliveryError(f"knowledge_use disposes of artifact(s) nobody delivered: {extra}")
    clean: dict[str, dict[str, str]] = {}
    for artifact_id in delivered:
        value = dispositions[artifact_id]
        if not isinstance(value, Mapping):
            raise KnowledgeDeliveryError(f"knowledge_use.dispositions[{artifact_id!r}] must be an object")
        disposition = value.get("disposition")
        if disposition not in DISPOSITIONS:
            raise KnowledgeDeliveryError(
                f"knowledge_use.dispositions[{artifact_id!r}].disposition {disposition!r} is not one of {list(DISPOSITIONS)}"
            )
        reason = value.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise KnowledgeDeliveryError(f"knowledge_use.dispositions[{artifact_id!r}] carries no reason")
        clean[artifact_id] = {"disposition": disposition, "reason": reason}
    retrieval_ids = [a["id"] for a in receipt["artifacts"] if a["load_mode"] == "RETRIEVAL"]
    always_ids = [a["id"] for a in receipt["artifacts"] if a["load_mode"] == "ALWAYS_LOAD"]
    response_binding = {
        "profile_id": receipt["profile_id"],
        "arm": receipt["arm"],
        "role": receipt["role"],
        "manifest_hash": receipt["manifest_hash"],
        "context_bundle_sha256": receipt["context_bundle_sha256"],
        "retrieval_dispositions": {artifact_id: clean[artifact_id]["disposition"] for artifact_id in retrieval_ids},
    }
    try:
        bound = bind_principal_knowledge_use(
            receipt["pre_call"],
            model_visible_context=model_visible_context,
            serialized_principal_input=serialized_principal_input,
            response_binding=response_binding,
        )
    except KnowledgeRegistryError as exc:
        raise KnowledgeDeliveryError(f"the read gate refused knowledge_use: {exc}") from exc
    result: dict[str, Any] = {key: value for key, value in bound.items() if key != "knowledge_use_receipt_hash"}
    result["bound_use_receipt_hash"] = bound["knowledge_use_receipt_hash"]
    result["knowledge_receipt_sha256"] = receipt["receipt_sha256"]
    result["always_load_dispositions"] = {artifact_id: clean[artifact_id] for artifact_id in always_ids}
    result["retrieval_reasons"] = {artifact_id: clean[artifact_id]["reason"] for artifact_id in retrieval_ids}
    result["knowledge_use_receipt_hash"] = ""
    result["knowledge_use_receipt_hash"] = canonical_hash(result, omit="knowledge_use_receipt_hash")
    return result


def validate_knowledge_use_files(
    knowledge_use: Mapping[str, Any],
    *,
    knowledge_receipt_path: Path | str,
    bundle_path: Path | str,
    prompt_path: Path | str,
) -> dict[str, Any]:
    """`validate_knowledge_use` over the three files the emitter wrote beside each other."""
    paths = {"knowledge receipt": Path(knowledge_receipt_path), "bundle": Path(bundle_path), "prompt": Path(prompt_path)}
    for label, path in paths.items():
        if not path.is_file():
            raise KnowledgeDeliveryError(f"{label} file is missing: {path.name}")
    try:
        receipt = json.loads(paths["knowledge receipt"].read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise KnowledgeDeliveryError(f"knowledge receipt is not JSON: {exc}") from exc
    bundle = paths["bundle"].read_bytes()
    return validate_knowledge_use(
        knowledge_use,
        knowledge_receipt=receipt,
        model_visible_context=bundle,
        serialized_principal_input=serialized_principal_input(paths["prompt"].read_bytes(), bundle),
    )
