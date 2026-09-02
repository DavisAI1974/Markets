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

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

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
