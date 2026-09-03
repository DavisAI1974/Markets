"""Build the A-memory SEED: every committed output of the past runs, hashed, labelled, UNVERIFIED.

**What memory is (D86).** One arm runs and it is A_MEMORY. Memory is Frankie's OWN day-over-day
carry of his frozen outputs; on day one it is SEEDED, never faked. Greg, verbatim: *"Just give
him the canary stuff from the past runs to start it and it will build from there"* and *"And
the other stuff too. I'm not picky about this."* Then (D88): *"if you can't find the canary just
use something from the last run. like i said I'm not picky about that and it's wasting time."*
and *"we aren't running clean anymore only memory."*

**What this builds.** `A_MEMORY_SEED_20260902.json`: one entry per committed past-run output -
the last run's outputs (`principal_runs/33605852433/`), the prior workmode run
(`prior_memory/workmode-32851909748-1/`, LABELLED as the reduced WRONG-DATA run and included
AS the wrong-data run, never filtered - D76), the A-clean and A-memory positive-knowledge
capsules and their source reports, and the S119 measured knowledge. Each entry carries its
repo-relative path, sha256, bytes, a provenance label (run id, data surface, pre- or
post-correction) and the status UNVERIFIED: he verifies every lesson against the stream.

**Derived, never typed.** The historical day-one file seed remains frozen by its provenance
rules. From day two only admitted findings accumulate: every A_MEMORY findings artifact under
`principal_runs/` is read, exact duplicate ids are ignored, and an id whose content changes is
refused. Empty artifacts prove a day ran but add no memory entry. The source-day bound comes
from `raw_mbo_source_manifest.EXPECTED_ROSTER`, never a typed count.

**The mission pins the seed.** The mission's memory paragraph names the seed's path and
sha256; `--write` rewrites that one hash, `--check` verifies it. The manifest then pins both
(refresh_native_frankie_knowledge --write), the registry's `a_memory_overlay` layers bind to
the seed file (rebind_registry_knowledge_layers --write), and `register_a_memory_knowledge
--write` routes the seed ALWAYS_LOAD to the A_MEMORY profiles.

Run, in this order:
    python3 -m research.kalshi.frankie_raw_mbo_benchmark.build_a_memory_seed --write
    python3 -m research.kalshi.frankie_raw_mbo_benchmark.register_a_memory_knowledge --write
    python3 -m research.kalshi.frankie_raw_mbo_benchmark.rebind_registry_knowledge_layers --write
    python3 research/kalshi/frankie_raw_mbo_benchmark/refresh_native_frankie_knowledge.py \\
        --spec research/kalshi/agents/frankie_native_raw_mbo_knowledge/KNOWLEDGE_SOURCES_20260828.json \\
        --repo-root . --write
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from research.kalshi.frankie_raw_mbo_benchmark.native_frankie_knowledge_registry import (
    canonical_hash,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_calculation_runner import (
    CalculationRunError,
    NativeCalculationRun,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_knowledge_delivery import (
    A_MEMORY_SEED_PATH,
    REPO_ROOT,
)
from research.kalshi.frankie_raw_mbo_benchmark.raw_mbo_source_manifest import (
    EXPECTED_ROSTER,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_staging import (
    PRINCIPAL_FINDINGS_SCHEMA,
)
from research.kalshi.frankie_raw_mbo_benchmark.render_frankie_report import (
    REQUIRED_FIELDS,
)

SEED_SCHEMA = "FRANKIE_A_MEMORY_SEED_V1"
SEED_VERSION = "a-memory-seed-20260902-v1"
SEED_PATH = A_MEMORY_SEED_PATH
MISSION_PATH = "research/kalshi/agents/frankie_native_raw_mbo_oct45_realtime_mission_20260828.md"
PKG = "research/kalshi/frankie_raw_mbo_benchmark/"
PRINCIPAL_RUNS_DIR = PKG + "principal_runs/"
FINDING_ARTIFACT_NAME = "frankie_principal_findings.json"
FINDING_VETO_PATH = PKG + "A_MEMORY_FINDING_VETOES_20260903.json"
FINDING_VETO_SCHEMA = "FRANKIE_A_MEMORY_FINDING_VETOES_V1"
FINDING_MEMORY_SCHEMA = "FRANKIE_A_MEMORY_FINDINGS_V1"
KNOWLEDGE_DIR = "research/kalshi/agents/frankie_native_raw_mbo_knowledge/"
LAST_RUN_DIR = PKG + "principal_runs/33605852433/"
LAST_RUN_FINDINGS = LAST_RUN_DIR + "frankie_principal_findings.json"
WRONG_DATA_DIR = PKG + "prior_memory/workmode-32851909748-1/"
PRE_CORRECTION = "PRE_CORRECTION"
POST_CORRECTION = "POST_CORRECTION"
CORRECTIONS = (PRE_CORRECTION, POST_CORRECTION)
THE_WRONG_DATA_RUN = "THE_WRONG_DATA_RUN"
PAST_RUN_OUTPUT = "PAST_RUN_OUTPUT"
STATUS = "UNVERIFIED"

HEADER = (
    "No canary output is committed, so the last run seeds it (D88, Greg: 'if you can't find the "
    "canary just use something from the last run. like i said I'm not picky about that and it's "
    "wasting time.'). One arm, A_MEMORY (D86/D88: 'we aren't running clean anymore only memory'): "
    "day one is SEEDED with every committed output of the past runs, each file listed with its "
    "sha256, bytes and a provenance label, every lesson UNVERIFIED until Frankie verifies it "
    "against the stream; from day two the memory is his own prior-day frozen outputs plus this "
    "seed. Keep-everything (D76): nothing is filtered for him, and the reduced wrong-data run "
    "32851909748-1 is here AS the wrong-data run."
)
CORRECTION_REFERENCE = (
    "The correction is the corrected raw-MBO A-arm procedure of 2026-08-28 "
    "(corrected_a_arm_execution_gate_20260828.py: F_LAST-closed native event groups on ts_recv_ns, "
    "no reduced seconds rows), under which the reduced-seconds surface became the wrong data "
    "(F-21). PRE_CORRECTION: produced on or bound to that surface, or before the corrected "
    "procedure and its mission existed. POST_CORRECTION: produced on the corrected native raw-MBO "
    "surface. D81 (2026-09-02) is later than both and is noted per group where it applies."
)
#: The pinned slot in the mission: the seed path, then `(SHA-256 `<hex>`)`.
_MISSION_PIN_RE = re.compile(
    r"(A_MEMORY_SEED_20260902\.json`\s*\(SHA-256 `)([0-9a-f]{64})(`\))"
)
#: Never seeded: the documents that pin the seed, and the seed itself (no circularity).
FORBIDDEN_ENTRY_PATHS = frozenset(
    {
        SEED_PATH,
        MISSION_PATH,
        KNOWLEDGE_DIR + "KNOWLEDGE_MANIFEST_20260828.json",
        KNOWLEDGE_DIR + "KNOWLEDGE_SOURCES_20260828.json",
        "research/kalshi/agents/frankie_native_raw_mbo_ingestion_layer_registry_20260828.json",
    }
)


class SeedBuildError(ValueError):
    """The seed cannot be built honestly; nothing is written."""


def _load_vetoes(root: Path) -> dict[str, str]:
    path = root / FINDING_VETO_PATH
    if not path.exists():
        return {}
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SeedBuildError(f"finding veto file is not readable: {FINDING_VETO_PATH} ({exc})") from exc
    if not isinstance(body, dict) or body.get("schema") != FINDING_VETO_SCHEMA:
        raise SeedBuildError(f"finding veto file must use schema {FINDING_VETO_SCHEMA}")
    rows = body.get("vetoes")
    if not isinstance(rows, list):
        raise SeedBuildError("finding veto file vetoes must be a list")
    vetoes: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise SeedBuildError("a finding veto must be an object")
        finding_id = row.get("id")
        reason = row.get("reason")
        if not isinstance(finding_id, str) or not finding_id.strip():
            raise SeedBuildError("a finding veto requires an id")
        if row.get("status") != "VETOED":
            raise SeedBuildError(f"finding veto {finding_id!r} must carry status VETOED")
        if not isinstance(reason, str) or not reason.strip():
            raise SeedBuildError(f"finding veto {finding_id!r} requires a reason")
        if finding_id in vetoes:
            raise SeedBuildError(f"finding veto {finding_id!r} is repeated")
        vetoes[finding_id] = reason.strip()
    return vetoes


def _finding_artifacts(root: Path) -> list[tuple[int, str, Path, dict[str, Any]]]:
    expected_days = tuple(source_day for source_day, _role in EXPECTED_ROSTER)
    roster_position = {source_day: position for position, source_day in enumerate(expected_days)}
    runs = root / PRINCIPAL_RUNS_DIR
    artifacts: list[tuple[int, str, Path, dict[str, Any]]] = []
    paths = sorted(runs.glob(f"*/{FINDING_ARTIFACT_NAME}")) if runs.is_dir() else []
    for path in paths:
        try:
            body = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SeedBuildError(f"principal findings are not readable: {path} ({exc})") from exc
        if not isinstance(body, dict):
            raise SeedBuildError(f"principal findings artifact is not an object: {path}")
        # The one historical A_CLEAN artifact remains in the day-one file seed. The daily
        # loop is A_MEMORY only and never re-admits the retired arm's run-local F-01 ids.
        arm = body.get("arm")
        if arm == "A_CLEAN":
            continue
        if arm != "A_MEMORY":
            raise SeedBuildError(f"principal findings artifact {path} names unknown arm {arm!r}")
        if body.get("schema") != PRINCIPAL_FINDINGS_SCHEMA:
            raise SeedBuildError(
                f"{path} uses schema {body.get('schema')!r}, expected {PRINCIPAL_FINDINGS_SCHEMA}"
            )
        source_day = body.get("source_day")
        if source_day not in roster_position:
            raise SeedBuildError(
                f"A-memory findings name source_day {source_day!r}, outside the manifest roster"
            )
        run_id = body.get("run_id")
        if not isinstance(run_id, str) or not run_id.strip():
            raise SeedBuildError(f"{path} carries no run_id")
        artifacts.append((roster_position[source_day], run_id, path, body))
    return sorted(artifacts, key=lambda row: (row[0], row[1], row[2].as_posix()))


def build_finding_memory(root: Path | str = REPO_ROOT) -> dict[str, Any]:
    """Build the findings-only daily carry with admission, dedupe, and veto labels."""
    root = Path(root)
    expected_days = tuple(source_day for source_day, _role in EXPECTED_ROSTER)
    by_day: dict[str, dict[str, Any]] = {
        source_day: {
            "source_day": source_day,
            "artifact_status": "MISSING",
            "artifact_count": 0,
            "finding_ids_observed": [],
            "new_finding_ids": [],
        }
        for source_day in expected_days
    }
    carried: dict[str, dict[str, Any]] = {}
    artifacts = _finding_artifacts(root)
    for _position, run_id, path, body in artifacts:
        rows = body.get("findings")
        if not isinstance(rows, list):
            raise SeedBuildError(f"{path} findings must be a list")
        relative = path.relative_to(root).as_posix()
        execution = {
            "principal": body.get("principal"),
            "artifact_path": relative,
            "artifact_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "actual_principal_invocation": body.get("actual_principal_invocation"),
            "controller_only": body.get("controller_only"),
        }
        try:
            admitted = NativeCalculationRun.admit_principal_findings(
                execution=execution, findings=rows
            )
        except (CalculationRunError, TypeError) as exc:
            raise SeedBuildError(f"the existing findings admission gate refused {relative}: {exc}") from exc
        source_day = body["source_day"]
        day = by_day[source_day]
        day["artifact_count"] += 1
        day["artifact_status"] = "PRESENT_WITH_FINDINGS" if admitted else (
            "PRESENT_EMPTY" if day["artifact_status"] == "MISSING" else day["artifact_status"]
        )
        for row in admitted:
            missing = [name for name in REQUIRED_FIELDS if not str(row.get(name, "")).strip()]
            if missing:
                raise SeedBuildError(
                    f"finding {row.get('id', '<unnamed>')!r} is missing render field(s) {missing}"
                )
            for name in ("category", "confidence_basis"):
                if not str(row.get(name, "")).strip():
                    raise SeedBuildError(f"finding {row['id']!r} is missing {name}")
            if row.get("evidence") is None:
                raise SeedBuildError(f"finding {row['id']!r} is missing evidence")
            finding_id = str(row["id"])
            day["finding_ids_observed"].append(finding_id)
            prior = carried.get(finding_id)
            if prior is not None:
                prior_body = {key: value for key, value in prior.items() if key not in {"status", "served", "veto_reason", "provenance"}}
                if canonical_hash(prior_body) != canonical_hash(row):
                    raise SeedBuildError(
                        f"stable finding id {finding_id!r} names different content across runs"
                    )
                continue
            carried[finding_id] = {
                **row,
                "status": STATUS,
                "served": True,
                "provenance": {
                    "run_id": run_id,
                    "source_day": source_day,
                    "artifact_path": relative,
                    "artifact_sha256": execution["artifact_sha256"],
                },
            }
            day["new_finding_ids"].append(finding_id)

    vetoes = _load_vetoes(root)
    unknown_vetoes = sorted(set(vetoes) - set(carried))
    if unknown_vetoes:
        raise SeedBuildError(f"finding veto names unknown finding id(s): {unknown_vetoes}")
    for finding_id, reason in vetoes.items():
        carried[finding_id]["status"] = "VETOED"
        carried[finding_id]["served"] = False
        carried[finding_id]["veto_reason"] = reason

    findings = list(carried.values())
    return {
        "schema": FINDING_MEMORY_SCHEMA,
        "roster": {"source_days": list(expected_days), "day_bound": len(expected_days)},
        "days": list(by_day.values()),
        "findings": findings,
        "totals": {
            "artifacts_present": len(artifacts),
            "findings": len(findings),
            "served": sum(1 for row in findings if row["served"]),
            "vetoed": sum(1 for row in findings if not row["served"]),
        },
    }


@dataclass(frozen=True)
class SeedGroup:
    """One provenance label, shared by every file a rule places in the group."""

    group_id: str
    directory: str
    filename_pattern: str
    run_id: str
    data_surface: str
    correction: str
    included_as: str
    label: str
    basis: str

    def matches(self, relative_path: str) -> bool:
        if not relative_path.startswith(self.directory):
            return False
        name = relative_path[len(self.directory):]
        return re.fullmatch(self.filename_pattern, name) is not None


def _last_run_id(root: Path) -> str:
    """The last run's own run id, read from its committed findings, never typed."""
    findings = root / LAST_RUN_FINDINGS
    try:
        body = json.loads(findings.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SeedBuildError(f"the last run's findings are not readable: {LAST_RUN_FINDINGS} ({exc})") from exc
    run_id = body.get("run_id") if isinstance(body, dict) else None
    if not isinstance(run_id, str) or not run_id:
        raise SeedBuildError(f"{LAST_RUN_FINDINGS} carries no run_id")
    return run_id


def seed_groups(root: Path | str = REPO_ROOT) -> tuple[SeedGroup, ...]:
    """The provenance rules, in seed order. A file two rules match is a refusal (checked)."""
    root = Path(root)
    wrong_data_run_id = WRONG_DATA_DIR.rstrip("/").rsplit("/", 1)[-1].removeprefix("workmode-")
    return (
        SeedGroup(
            group_id="last_run_33605852433",
            directory=LAST_RUN_DIR,
            filename_pattern=r".+",
            run_id=_last_run_id(root),
            data_surface=(
                "the runner's calculation_result.json over glbx-mdp3-20211003.mbo.dbn.zst (Sunday "
                "2021-10-03; the ~34 MB averaged result the principal read, not the exact member "
                "ledger, which stayed on the box - D81, measured); native raw MBO through the "
                "corrected runner"
            ),
            correction=POST_CORRECTION,
            included_as=PAST_RUN_OUTPUT,
            label=(
                "THE LAST RUN'S committed outputs (findings, report, assessment, prompt): the seed "
                "of record because no canary output is committed (D88); pre-D81 division of labour "
                "(the runner calculated, he interpreted)"
            ),
            basis="principal_runs/33605852433/frankie_principal_findings.json (run_id, arm, source_day)",
        ),
        SeedGroup(
            group_id="wrong_data_run_32851909748_1",
            directory=WRONG_DATA_DIR,
            filename_pattern=r".+",
            run_id=wrong_data_run_id,
            data_surface=(
                "the reduced seconds rows (old reduced market rows) the corrected raw-MBO procedure "
                "forbids - THE WRONG DATA (F-21); its RT output was passed one-way to the Forecaster"
            ),
            correction=PRE_CORRECTION,
            included_as=THE_WRONG_DATA_RUN,
            label=(
                "THE REDUCED WRONG-DATA RUN 32851909748-1: its receipts, handoff, locks, frozen "
                "state and outputs, included AS the wrong-data run, labelled, never filtered "
                "(D86, D76); its lessons package (sha256 b487acfb...) is NOT memory"
            ),
            basis="D85/D86 (DECISIONS.md) and F-21; the directory name carries the run id",
        ),
        SeedGroup(
            group_id="aclean_first_native_replay_20260828",
            directory=PKG,
            filename_pattern=r"ACLEAN_.+_20260828\.(md|json)",
            run_id="a-clean-runtime-33161766927",
            data_surface=(
                "read-only retrospective reviews of the first A-clean native replay over the four "
                ".mbo.dbn.zst objects (daily summaries and the event-group ledger), under the "
                "original scientific RT mission"
            ),
            correction=PRE_CORRECTION,
            included_as=PAST_RUN_OUTPUT,
            label=(
                "A-clean positive-knowledge capsule SOURCE reports of 2026-08-28; four of the six "
                "promoted findings were results about roster days, which is why the method-only "
                "source of 2026-08-29 replaced them as the capsule source"
            ),
            basis="the reports' own provenance headers; ACLEAN_METHOD_ONLY_CAPSULE_SOURCE_20260829.md 'Why this file exists'",
        ),
        SeedGroup(
            group_id="aclean_method_only_capsule_source_20260829",
            directory=PKG,
            filename_pattern=r"ACLEAN_METHOD_ONLY_CAPSULE_SOURCE_20260829\.md",
            run_id="none (method-only; no measurement over the scored roster)",
            data_surface="method only, drawn from no run's results",
            correction=POST_CORRECTION,
            included_as=PAST_RUN_OUTPUT,
            label="the registered A-clean capsule source of 2026-08-29 (method-only)",
            basis="the file's own 'Status' and 'Why this file exists' sections",
        ),
        SeedGroup(
            group_id="aclean_s119_measured_knowledge_20260902",
            directory=PKG,
            filename_pattern=r"ACLEAN_S119_MEASURED_KNOWLEDGE_SOURCE_20260902\.md",
            run_id="frankie-a-clean-rt-33605852433-1",
            data_surface=(
                "numbers from the first real principal run over a complete session (run 33605852433, "
                "Sunday 2021-10-03) and the rules established by closing its sixteen-defect register"
            ),
            correction=POST_CORRECTION,
            included_as=PAST_RUN_OUTPUT,
            label="the S119 MEASURED knowledge source (2026-09-02)",
            basis="the file's own opening paragraph",
        ),
        SeedGroup(
            group_id="amemory_diagnostic_replay_20260828",
            directory=PKG,
            filename_pattern=r"AMEMORY_.+_20260828\.(md|json)",
            run_id="frankie-a-memory-rt-c7da7d257fda-1",
            data_surface=(
                "read-only retrospective and member-first recalculation reports over the A-memory "
                "diagnostic native replay, each bound to the prior wrong-data lessons package "
                "(sha256 b487acfb...)"
            ),
            correction=PRE_CORRECTION,
            included_as=PAST_RUN_OUTPUT,
            label=(
                "A-memory positive-knowledge capsule SOURCE reports and the member-first "
                "recalculation spec and receipt of 2026-08-28; every finding in them cites the "
                "wrong-data prior package as an input, so read them as PRE_CORRECTION"
            ),
            basis="the reports' own provenance sections; D85 names their derivation from run 32851909748-1",
        ),
        SeedGroup(
            group_id="aclean_positive_knowledge_capsule",
            directory=KNOWLEDGE_DIR,
            filename_pattern=r"A_CLEAN_POSITIVE_KNOWLEDGE_20260828\.md",
            run_id="generated (refresh_native_frankie_knowledge) from the A-clean capsule sources",
            data_surface="the promoted A-clean capsule rendered from its registered source sections",
            correction=POST_CORRECTION,
            included_as=PAST_RUN_OUTPUT,
            label="the A-clean promoted positive-knowledge capsule (the retired arm's capsule, kept as a record)",
            basis="KNOWLEDGE_SOURCES_20260828.json capsules[]",
        ),
        SeedGroup(
            group_id="amemory_positive_knowledge_capsule",
            directory=KNOWLEDGE_DIR,
            filename_pattern=r"A_MEMORY_POSITIVE_KNOWLEDGE_20260828\.md",
            run_id="generated (refresh_native_frankie_knowledge) from the A-memory capsule sources",
            data_surface="the promoted A-memory capsule rendered from its registered source sections",
            correction=PRE_CORRECTION,
            included_as=PAST_RUN_OUTPUT,
            label="the A-memory promoted positive-knowledge capsule; its sources are PRE_CORRECTION, so it is",
            basis="KNOWLEDGE_SOURCES_20260828.json capsules[]",
        ),
    )


def _candidates(root: Path) -> list[str]:
    """Every file the rules are answerable for, repo-relative, sorted."""
    found: set[str] = set()
    for directory in (LAST_RUN_DIR, WRONG_DATA_DIR):
        base = root / directory
        if not base.is_dir():
            raise SeedBuildError(f"past-run directory is missing: {directory}")
        found.update(p.relative_to(root).as_posix() for p in base.rglob("*") if p.is_file())
    package = root / PKG
    for prefix in ("ACLEAN_", "AMEMORY_"):
        found.update(
            p.relative_to(root).as_posix()
            for p in package.glob(prefix + "*")
            if p.is_file() and p.suffix in {".md", ".json"}
        )
    knowledge = root / KNOWLEDGE_DIR
    found.update(
        p.relative_to(root).as_posix()
        for p in knowledge.glob("A_*_POSITIVE_KNOWLEDGE_20260828.md")
        if p.is_file()
    )
    return sorted(found)


def _place(groups: tuple[SeedGroup, ...], relative: str) -> SeedGroup:
    matched = [group for group in groups if group.matches(relative)]
    if not matched:
        raise SeedBuildError(
            f"no provenance rule labels {relative!r}; a committed past-run output the seed cannot "
            "label is a refusal, not a default label"
        )
    if len(matched) > 1:
        raise SeedBuildError(f"{relative!r} matches more than one provenance rule: {[g.group_id for g in matched]}")
    return matched[0]


def seed_entry_paths(root: Path | str = REPO_ROOT) -> list[str]:
    """The entry set, derived; in seed order (group order, then path)."""
    root = Path(root)
    groups = seed_groups(root)
    placed = [(groups.index(_place(groups, relative)), relative) for relative in _candidates(root)]
    return [relative for _index, relative in sorted(placed)]


def build_seed(root: Path | str = REPO_ROOT) -> dict[str, Any]:
    root = Path(root)
    groups = seed_groups(root)
    entries: list[dict[str, Any]] = []
    for relative in seed_entry_paths(root):
        if relative in FORBIDDEN_ENTRY_PATHS:
            raise SeedBuildError(f"{relative!r} pins the seed and may not be seeded (circularity)")
        group = _place(groups, relative)
        raw = (root / relative).read_bytes()
        entries.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
                "status": STATUS,
                "provenance": {
                    "group_id": group.group_id,
                    "run_id": group.run_id,
                    "data_surface": group.data_surface,
                    "correction": group.correction,
                    "included_as": group.included_as,
                    "label": group.label,
                    "basis": group.basis,
                },
            }
        )
    if not entries:
        raise SeedBuildError("the seed would be empty; day one is seeded, never empty (D86)")
    by_group: dict[str, int] = {}
    for entry in entries:
        by_group[entry["provenance"]["group_id"]] = by_group.get(entry["provenance"]["group_id"], 0) + 1
    seed: dict[str, Any] = {
        "schema": SEED_SCHEMA,
        "version": SEED_VERSION,
        "arm": "A_MEMORY",
        "header": HEADER,
        "correction_reference": CORRECTION_REFERENCE,
        "status_vocabulary": {
            STATUS: "listed for him; he verifies it against the stream and files VERIFIED / UNVERIFIED / REFUTED",
        },
        "day_rule": {
            "day_one": "this seed, whole",
            "from_day_two": "his own prior-day frozen outputs (the append-only ledgers, the knowledge-verification verdicts, the first locks) plus this seed",
        },
        "groups": [
            {
                "group_id": group.group_id,
                "run_id": group.run_id,
                "data_surface": group.data_surface,
                "correction": group.correction,
                "included_as": group.included_as,
                "label": group.label,
                "basis": group.basis,
                "entries": by_group.get(group.group_id, 0),
            }
            for group in groups
            if group.group_id in by_group
        ],
        "entries": entries,
        "totals": {
            "entries": len(entries),
            "bytes": sum(entry["bytes"] for entry in entries),
            "by_group": by_group,
            "by_correction": {
                correction: sum(1 for e in entries if e["provenance"]["correction"] == correction)
                for correction in CORRECTIONS
            },
        },
        "seed_hash": "",
    }
    finding_memory = build_finding_memory(root)
    if finding_memory["totals"]["artifacts_present"]:
        seed["finding_memory"] = finding_memory
        seed["status_vocabulary"]["VETOED"] = (
            "retained as a run lesson and excluded from the served memory until Greg changes its label"
        )
        seed["day_rule"]["from_day_two"] = (
            "only his admitted findings, deduplicated by their stable id; an empty artifact proves "
            "the day ran and adds no memory entry"
        )
    seed["seed_hash"] = canonical_hash(seed, omit="seed_hash")
    return seed


def render_seed(seed: dict[str, Any]) -> str:
    """The committed layout: one-space indent, sorted keys, trailing newline."""
    return json.dumps(seed, indent=1, sort_keys=True, ensure_ascii=True) + "\n"


def mission_seed_sha256(mission_text: str) -> str:
    """The seed sha256 the mission pins, or a refusal when the slot is absent or repeated."""
    found = _MISSION_PIN_RE.findall(mission_text)
    if len(found) != 1:
        raise SeedBuildError(
            f"the mission must name the seed's SHA-256 exactly once beside {SEED_PATH}; found {len(found)}"
        )
    return found[0][1]


def pin_mission(mission_text: str, seed_sha256: str) -> str:
    mission_seed_sha256(mission_text)
    return _MISSION_PIN_RE.sub(lambda m: m.group(1) + seed_sha256 + m.group(3), mission_text, count=1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="exit 1 if the committed seed or the mission pin is stale")
    mode.add_argument("--write", action="store_true", help="write the seed and pin its sha256 in the mission")
    parser.add_argument("--repo-root", default=str(REPO_ROOT), help="where the past-run outputs are read from")
    parser.add_argument("--seed", default=None, help="the seed file to check or write (default: the committed one)")
    parser.add_argument("--mission", default=None, help="the mission to check or pin (default: the committed one)")
    args = parser.parse_args(argv)
    root = Path(args.repo_root)
    seed_target = Path(args.seed) if args.seed else root / SEED_PATH
    mission_target = Path(args.mission) if args.mission else root / MISSION_PATH
    try:
        rendered = render_seed(build_seed(root))
        mission_text = mission_target.read_text(encoding="utf-8")
    except (SeedBuildError, OSError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    digest = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    entries = rendered.count('"status": "UNVERIFIED"')
    if args.write:
        seed_target.parent.mkdir(parents=True, exist_ok=True)
        seed_target.write_text(rendered, encoding="utf-8")
        try:
            pinned = pin_mission(mission_text, digest)
        except SeedBuildError as exc:
            print(f"REFUSED: {exc}", file=sys.stderr)
            return 1
        mission_target.write_text(pinned, encoding="utf-8")
        print(f"wrote {seed_target} ({entries} entries, sha256 {digest}); mission pinned at {mission_target}")
        return 0
    stale: list[str] = []
    if not seed_target.is_file() or seed_target.read_text(encoding="utf-8") != rendered:
        stale.append(f"seed {seed_target} is not the generated one")
    try:
        if mission_seed_sha256(mission_text) != digest:
            stale.append(f"mission {mission_target} pins a different seed sha256")
    except SeedBuildError as exc:
        stale.append(str(exc))
    if stale:
        print("FAIL  " + "; ".join(stale) + "; run --write", file=sys.stderr)
        return 1
    print(f"PASS  {seed_target} is the generated seed ({entries} entries, sha256 {digest}); mission pinned")
    return 0


if __name__ == "__main__":
    sys.exit(main())
