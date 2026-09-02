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
from typing import Callable

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
