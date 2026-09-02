"""The spawn contract: how Frankie is actually called, and how its output gets back.

On the first run Frankie was never called and the calculation layer produced the output.
The calculation layer refusing to author findings closes half of that; this is the other
half - the mechanism by which a principal is asked anything at all.

It is the walk's own mechanism, not an API call. Sol runs as an agent session exactly as the
blind and refine specialists did: the traversal STAGES a committed request file at a lawful
cutoff, an agent session reads committed files and emits a committed artifact, and the
coordinator reads that artifact back and hard-fails when it is missing or malformed. There
is no provider, model id, invocation id or token usage anywhere in this, because none of
those exist in an agent-session run. What exists is a file at a known path in a known
schema, which is what proved a specialist ran for twenty-four group cycles.

Two refusals here are the load-bearing ones. **A missing artifact is a hard failure**, never
an empty success - a spawn that produced nothing is a spawn that did not happen, and
treating it as zero findings is how the calculation layer came to stand in for Frankie in
the first place. And **findings must cite the evidence hash they were produced against**, so
an artifact cannot be carried from one run to another where it was never earned.
"""
from __future__ import annotations

import hashlib
import sys
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

SPAWN_REQUEST_SCHEMA = "FRANKIE_NATIVE_RAW_MBO_SPAWN_REQUEST_V1"
PRINCIPAL_FINDINGS_SCHEMA = "FRANKIE_NATIVE_RAW_MBO_PRINCIPAL_FINDINGS_V1"

ALLOWED_ARMS = frozenset({"A_CLEAN", "A_MEMORY"})
ALLOWED_ROLES = frozenset({"REAL_TIME_FRANKIE", "FORECASTER_FRANKIE"})

REQUIRED_CUTOFF_KEYS = (
    "group_index",
    "recv_ns",
    "first_lawful_availability_ns",
    "session_phase",
    "continuity_segment",
    "source_day",
)


class StagingError(ValueError):
    """A spawn could not be staged, or its artifact could not be trusted."""


def _canonical(value: Any) -> str:
    # D60: this carried `default=str`, so any value JSON could not represent was silently
    # STRINGIFIED into the committed spawn request instead of raising - a number arriving as
    # a non-int became a quoted string and `load_principal_artifact` then compared against
    # the string. Every other canonicalizer in this package uses `allow_nan=False` with no
    # default and fails loud; this one now matches them.
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def stage_spawn_request(
    cutoff: Mapping[str, Any],
    *,
    out_dir: Path,
    arm: str,
    role: str,
    evidence: Mapping[str, Any],
) -> Path:
    """Write the request Frankie is spawned against. Returns its path.

    The path is deterministic from the cutoff so a re-stage overwrites rather than
    accumulating a second request for the same decision point, and so the coordinator can
    find it without being told.
    """
    if arm not in ALLOWED_ARMS:
        raise StagingError(f"unknown arm {arm!r}; expected one of {sorted(ALLOWED_ARMS)}")
    if role not in ALLOWED_ROLES:
        raise StagingError(f"unknown role {role!r}; expected one of {sorted(ALLOWED_ROLES)}")
    missing = [key for key in REQUIRED_CUTOFF_KEYS if cutoff.get(key) is None]
    if missing:
        raise StagingError(
            f"cutoff is missing {missing}; a spawn without its lawful availability time has "
            "no defensible decision point"
        )
    if not evidence.get("result_hash"):
        raise StagingError("a spawn request must name the evidence it is staged against")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / (
        f"spawn_{arm.lower()}_{role.lower()}_{cutoff['source_day']}"
        f"_g{int(cutoff['group_index'])}.json"
    )
    body = {
        "schema": SPAWN_REQUEST_SCHEMA,
        "arm": arm,
        "role": role,
        "cutoff": dict(cutoff),
        "evidence": dict(evidence),
        "expected_artifact_schema": PRINCIPAL_FINDINGS_SCHEMA,
        "invocation_note": (
            "Run as an agent session over committed files, as the blind and refine group "
            "runs were run. No API call. Read the evidence named above and emit a committed "
            "artifact in the expected schema; the coordinator hard-fails if it is absent."
        ),
    }
    path.write_text(json.dumps(body, indent=2, sort_keys=True, allow_nan=False))
    return path


#: The three exact ledgers every run retains. The artifact must declare, for each, whether
#: the principal READ it. The contract preamble says exact evidence is never replaced by an
#: average; on run 33605852433 the ledgers were written and witnessed and the principal read
#: 16,293 averaged rows and zero exact ones, because nothing at the delivery boundary asked.
EXACT_LEDGERS = (
    "exact_member_ledger",
    "exact_lifecycle_and_runway_ledger",
    "legacy_observable_rows",
)
#: NOT_READ is the honest answer while delivery is unsolved and carries no penalty. A gate
#: that accepted only READ would push the principal toward claiming reads he did not make,
#: which is the defect this programme exists to catch wearing the gate's own uniform.
READ_STATUSES = ("READ", "PARTIAL", "NOT_READ")


def load_principal_artifact(
    path: Path, *, expected_evidence_hash: str, render_report: bool = True
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Read back what the spawn produced, or fail hard.

    Returns `(execution, findings)` shaped for
    `NativeCalculationRun.attach_principal_findings`, so the only route into the findings
    layer runs through this validation.

    **The readable report is generated here, automatically, because this is the one gate
    every artifact must pass.** Run 33605852433's 44 findings sat unread in JSON beside a
    separately hand-authored assessment, so what reached Greg was a verdict on whether each
    section earned its place and none of the chain depths, family crosswalks, exhaustion
    runways or prebirth timing. Rendering anywhere else would be a step someone can forget;
    rendering here cannot be reached without the artifact having already validated.

    A render failure never invalidates a good artifact - the findings are the deliverable and
    the report is a convenience - so it is reported and swallowed rather than raised.
    `render_report=False` is for tests that assert the validation alone.
    """
    path = Path(path)
    if not path.exists():
        raise StagingError(
            f"no principal artifact at {path}; a spawn that produced nothing did not happen, "
            "and must not be recorded as zero findings"
        )
    try:
        body = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise StagingError(f"principal artifact at {path} is not valid JSON: {exc}") from exc
    if not isinstance(body, Mapping):
        raise StagingError(f"principal artifact at {path} is not an object")
    if body.get("schema") != PRINCIPAL_FINDINGS_SCHEMA:
        raise StagingError(
            f"principal artifact schema is {body.get('schema')!r}, expected "
            f"{PRINCIPAL_FINDINGS_SCHEMA!r}"
        )
    if body.get("evidence_result_hash") != expected_evidence_hash:
        raise StagingError(
            "principal artifact cites different evidence than this run produced; findings "
            "must be derived from the evidence they are attached to"
        )
    if body.get("controller_only") is not False:
        raise StagingError("controller_only output cannot supply findings")
    if body.get("actual_principal_invocation") is not True:
        raise StagingError("principal artifact does not attest an actual invocation")
    for field_name in ("principal", "arm", "role"):
        value = body.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise StagingError(f"principal artifact is missing {field_name}")
    if body.get("arm") not in ALLOWED_ARMS or body.get("role") not in ALLOWED_ROLES:
        raise StagingError("principal artifact names an unknown arm or role")

    findings = body.get("findings")
    if not isinstance(findings, list) or not findings:
        raise StagingError(
            f"principal artifact at {path} carries no findings; an empty artifact is a "
            "failed spawn, not an empty success"
        )

    # THE DELIVERY-BOUNDARY GATE (F-14). An undeclared read status is what lets an average
    # stand in for the exact: "beneath every summary sit exact members" is true of the disk
    # and says nothing about what the principal saw. Declaring two ledgers of three is the
    # silent version of declaring none, so every ledger is required by name.
    evidence_read = body.get("evidence_read")
    if not isinstance(evidence_read, Mapping):
        raise StagingError(
            "principal artifact carries no `evidence_read`; it must declare, for each exact "
            f"ledger in {list(EXACT_LEDGERS)}, whether the principal READ it (READ / PARTIAL / "
            "NOT_READ). NOT_READ is accepted. Not saying is not."
        )
    undeclared = [name for name in EXACT_LEDGERS if name not in evidence_read]
    if undeclared:
        raise StagingError(
            f"principal artifact leaves these exact ledgers undeclared in `evidence_read`: "
            f"{undeclared}; declare each as READ, PARTIAL or NOT_READ"
        )
    bad = {k: v for k, v in evidence_read.items() if v not in READ_STATUSES}
    if bad:
        raise StagingError(
            f"`evidence_read` uses statuses outside {list(READ_STATUSES)}: {bad}"
        )

    execution = {
        "principal": body["principal"],
        "arm": body["arm"],
        "role": body["role"],
        "artifact_path": str(path),
        "artifact_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "evidence_result_hash": expected_evidence_hash,
        "actual_principal_invocation": True,
        "controller_only": False,
        "evidence_read": {name: evidence_read[name] for name in EXACT_LEDGERS},
        "principal_read_any_exact_rows": any(
            evidence_read[name] in ("READ", "PARTIAL") for name in EXACT_LEDGERS
        ),
    }
    if render_report:
        _render_report_beside(path)
    return execution, [dict(row) for row in findings]


def _render_report_beside(path: Path) -> Path | None:
    """Write the human-readable report next to the artifact. Never fatal.

    Imported inside the function so a renderer problem can never stop an artifact from
    validating: the findings are the deliverable, the report is how anyone reads them.
    """
    try:
        from research.kalshi.frankie_raw_mbo_benchmark.render_frankie_report import (
            write_report,
        )

        return write_report(path)
    except Exception as exc:  # noqa: BLE001 - see docstring; reported, never raised
        print(
            f"WARNING: principal artifact at {path} validated but its report could not be "
            f"rendered: {exc}",
            file=sys.stderr,
        )
        return None


class SpawnStager:
    """Binds a run's identity to `stage_spawn_request` so the driver stages, never invokes.

    The driver used to hold an `on_invoke` callback shaped like "call the model here", which
    is the wrong verb for an agent-session run and is what an API design leaves behind. This
    is the right verb: at a lawful cutoff the traversal writes a request and moves on. What
    reads that request is a spawn, later, out of band.
    """

    def __init__(
        self, *, out_dir: Path, arm: str, role: str, evidence: Mapping[str, Any]
    ) -> None:
        if arm not in ALLOWED_ARMS:
            raise StagingError(f"unknown arm {arm!r}")
        if role not in ALLOWED_ROLES:
            raise StagingError(f"unknown role {role!r}")
        self.out_dir = Path(out_dir)
        self.arm = arm
        self.role = role
        self.evidence = dict(evidence)
        self.staged: list[Path] = []

    def stage(self, cutoff: Mapping[str, Any]) -> Path:
        path = stage_spawn_request(
            cutoff,
            out_dir=self.out_dir,
            arm=self.arm,
            role=self.role,
            evidence=self.evidence,
        )
        self.staged.append(path)
        return path
