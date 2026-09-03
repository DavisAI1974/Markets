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

THE CANONICAL READ-BACK (S122, D88 - Greg: "there is supposed to be a canonical file or a
runner, launcher file with everything"). The launcher is `native_a_arm_launch`; the read-back
is this module's CLI, the single entry that, given the artifact, its output bundle, the
finished result and the two receipts, VALIDATES (the artifact, the bundle, every receipt by
hash), ATTACHES the findings through the runner's own route, RENDERS the report with the
99-layer crosswalk beside the artifact, and BUILDS the RT handoff trio beside the result with
findings. The arm and the source manifest hash are bound off the result's identity receipt -
one arm, A_MEMORY (D86), nothing to remember:

    python3 -m research.kalshi.frankie_raw_mbo_benchmark.native_staging read-back \\
        --artifact <run>/frankie_principal_findings.json \\
        --result <run>/calculation_result.json \\
        --outputs-dir <run>/principal_outputs \\
        --delivery-receipt <run>/FRANKIE_LEDGER_DELIVERY_RECEIPT.json \\
        --knowledge-receipt <run>/KNOWLEDGE_RECEIPT.json \
        --knowledge-bundle <run>/KNOWLEDGE_BUNDLE.md \
        --prompt <run>/FRANKIE_SPAWN_PROMPT.md

It prints a JSON summary naming every hash and path it produced - `result_path`
(`calculation_result_with_findings.json`, the original never written over), `report_path`,
`crosswalk_sha256`, `handoff` (ONEWAY_HANDOFF / RT_FIRST_LOCK / RT_CONTEXT_MANIFEST, each
path and receipt hash), `first_lock` or the stated reason there is none - or `REFUSED: <why>`
and exit 1, having written nothing. Optional: `--out`, `--handoff-dir`, `--no-report`, and
the `*-sha256` forms of the two receipts when only the hash is in hand. The knowledge read
gate is wired at `KNOWLEDGE_USE_GATE`; the canonical command supplies the
exact receipt, knowledge bundle and prompt bytes it validates.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from research.kalshi.frankie_raw_mbo_benchmark.native_calculation_runner import (
    LAYER_IDENTITY,
    CalculationRunError,
    NativeCalculationRun,
    canonical_hash,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import load_registry
from research.kalshi.frankie_raw_mbo_benchmark.native_knowledge_delivery import (
    serialized_principal_input as bind_serialized_principal_input,
    validate_knowledge_use,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_principal_outputs import (
    CANONICAL_ARM,
    CONTRACT_PATH,
    PrincipalOutputError,
    validate_output_bundle_dir,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

SPAWN_REQUEST_SCHEMA = "FRANKIE_NATIVE_RAW_MBO_SPAWN_REQUEST_V1"
PRINCIPAL_FINDINGS_SCHEMA = "FRANKIE_NATIVE_RAW_MBO_PRINCIPAL_FINDINGS_V1"

#: A_MEMORY is the one arm that runs (`CANONICAL_ARM`, D86, re-exported from the outputs
#: module); A_CLEAN stays a VALID value as an inert record until its removal is discussed
#: (D60, F-28). Pinned equal to the outputs module's set by test.
ALLOWED_ARMS = frozenset({"A_CLEAN", "A_MEMORY"})
ALLOWED_ROLES = frozenset({"REAL_TIME_FRANKIE", "FORECASTER_FRANKIE"})

REQUIRED_CUTOFF_KEYS = (
    "group_index",
    "recv_ns",
    "first_lawful_availability_ns",
    "session_phase",
    "continuity_segment",
    "source_day",
    # D83 (S121 item one): the model-evaluation clock by its registry name - the F_LAST
    # receive of the group at which the principal is staged. The driver stamps it on the
    # row and on the cutoff (`native_replay_driver`, `stamp_model_evaluation`); requiring it
    # here makes it a required layer of every spawn request. It is an EVENT instant, never
    # a time we choose (Greg: "Don't make cutoff times").
    "clock_model_evaluation_ns",
)


class StagingError(ValueError):
    """A spawn could not be staged, or its artifact could not be trusted."""


#: THE KNOWLEDGE READ GATE'S SEAM (S122 slice 7). `load_principal_artifact` calls
#: `knowledge_use_gate(body, knowledge_receipt_sha256=<the receipt the coordinator delivered
#: under>)` with the whole artifact body (which carries `knowledge_use` and the artifact's own
#: `knowledge_receipt_sha256`) AFTER the artifact's structural and delivery-receipt checks and
#: BEFORE its output bundle is validated. Whatever the gate raises refuses the artifact by
#: name and the read-back writes nothing; whatever it returns (a receipt, or None) is carried
#: on the execution as `knowledge_use_receipt` and so into the result's principal block. The
#: The knowledge persona exposes `validate_knowledge_use`; `validate_staged_knowledge_use`
#: adapts this hook to it (the CLI reads the live hook) - `read_back(knowledge_use_gate=)` and
#: `load_principal_artifact(knowledge_use_gate=)` take it explicitly for callers in-process.
KnowledgeUseGate = Callable[..., Any]


def validate_staged_knowledge_use(
    body: Mapping[str, Any],
    *,
    knowledge_receipt_sha256: str | None,
    knowledge_receipt: Mapping[str, Any] | None = None,
    model_visible_context: bytes | None = None,
    serialized_principal_input: bytes | None = None,
) -> dict[str, Any]:
    """Adapt the staged artifact and its exact delivered bytes to the existing read gate."""
    if knowledge_receipt_sha256 is None:
        raise StagingError("no delivered knowledge_receipt_sha256 was supplied to the read gate")
    if knowledge_receipt is None:
        raise StagingError("the delivered knowledge receipt body is unavailable to the read gate")
    if knowledge_receipt.get("receipt_sha256") != knowledge_receipt_sha256:
        raise StagingError(
            "the knowledge receipt body does not match the knowledge_receipt_sha256 "
            "the coordinator delivered under"
        )
    if model_visible_context is None:
        raise StagingError("the model-visible knowledge bundle bytes are unavailable to the read gate")
    if serialized_principal_input is None:
        raise StagingError("the exact serialized prompt plus knowledge bundle is unavailable to the read gate")
    return validate_knowledge_use(
        body.get("knowledge_use"),
        knowledge_receipt=knowledge_receipt,
        model_visible_context=model_visible_context,
        serialized_principal_input=serialized_principal_input,
    )


KNOWLEDGE_USE_GATE: KnowledgeUseGate = validate_staged_knowledge_use


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
            f"cutoff is missing {missing}; a spawn without its lawful availability time and "
            "the model-evaluation clock it was staged at has no defensible decision point"
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
    path: Path,
    *,
    expected_evidence_hash: str,
    render_report: bool = True,
    outputs_dir: Path | None = None,
    knowledge_receipt_sha256: str | None = None,
    delivery_receipt_sha256: str | None = None,
    expected_arm: str | None = None,
    knowledge_use_gate: KnowledgeUseGate | None = None,
    knowledge_receipt: Mapping[str, Any] | None = None,
    model_visible_context: bytes | None = None,
    serialized_principal_input: bytes | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Read back what the spawn produced, or fail hard.

    `expected_arm` (S122 slice 6) is the arm the RUN was stamped with - the read-back binds
    it off the result's identity receipt - and an artifact on another arm is refused: findings
    attach to the run they were produced on. None keeps the old rule (any allowed arm).
    `knowledge_use_gate` is the seam described at `KNOWLEDGE_USE_GATE`.

    Returns `(execution, findings)` shaped for
    `NativeCalculationRun.attach_principal_findings`, so the only route into the findings
    layer runs through this validation.

    **The output bundle is validated here too (S121 slice 1).** An artifact that cites a
    `delivery_receipt_sha256` was produced with every exact ledger in hand, and on such a run
    the append-only output ledgers ARE the deliverable - so it must also cite
    `outputs_receipt_sha256`, `outputs_dir` must hold the bundle it names, and the bundle
    must validate under `native_principal_outputs.validate_output_bundle_dir` against the
    loaded registry, the committed contract, the artifact's own delivery receipt and the
    `knowledge_receipt_sha256` the coordinator delivered under. The bundle receipt the
    validator computes must equal the artifact's citation. `delivery_receipt_sha256`, when
    the coordinator states it, must be the receipt the artifact cites; it is what the bundle
    is validated against either way. An artifact without a delivery receipt keeps the old
    rule: no outputs are required, and none may be handed in unbound.

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
    if expected_arm is not None and body["arm"] != expected_arm:
        raise StagingError(
            f"the artifact is arm {body['arm']!r} and the run it cites was run as arm "
            f"{expected_arm!r} (its identity receipt); findings attach to the run they were "
            "produced on"
        )

    findings = body.get("findings")
    if not isinstance(findings, list):
        raise StagingError(f"principal artifact at {path} findings must be a list")

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

    # D81, THE DELIVERED CASE. `delivery_receipt_sha256` exists only when
    # `fetch_frankie_ledgers` verified every exact ledger into the session, so an artifact
    # citing one was produced with the ledgers in hand - and a delivered ledger the principal
    # did not read is a failed spawn, not a caveat. Without the citation the old rule stands
    # and NOT_READ is still the honest answer for a pre-delivery run.
    receipt_hashes: dict[str, str | None] = {}
    for field_name in ("delivery_receipt_sha256", "stream_receipt_sha256"):
        value = body.get(field_name)
        if value is None:
            receipt_hashes[field_name] = None
            continue
        if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
            raise StagingError(f"{field_name} must be a lowercase SHA-256, got {value!r}")
        receipt_hashes[field_name] = value
    if receipt_hashes["delivery_receipt_sha256"] is not None:
        unread = [name for name in EXACT_LEDGERS if evidence_read[name] == "NOT_READ"]
        if unread:
            raise StagingError(
                f"the artifact cites delivery receipt {receipt_hashes['delivery_receipt_sha256']}"
                f", so every exact ledger was delivered and verified, yet declares NOT_READ on "
                f"{unread}; a delivered ledger he did not read is a failed spawn (D81)"
            )

    cited_delivery = receipt_hashes["delivery_receipt_sha256"]
    if delivery_receipt_sha256 is not None:
        if _SHA256_RE.fullmatch(delivery_receipt_sha256) is None:
            raise StagingError(
                f"delivery_receipt_sha256 must be a lowercase SHA-256, got {delivery_receipt_sha256!r}"
            )
        if cited_delivery != delivery_receipt_sha256:
            raise StagingError(
                f"the run delivered its ledgers under delivery_receipt_sha256 "
                f"{delivery_receipt_sha256} and the artifact cites {cited_delivery!r}; findings "
                "are attached to the delivery they were produced against"
            )
    # THE KNOWLEDGE READ GATE'S SEAM - see `KNOWLEDGE_USE_GATE`. Before the bundle, so a
    # refused knowledge use never gets as far as validating the outputs it was not entitled to.
    knowledge_use_receipt: Any = None
    if knowledge_use_gate is not None:
        try:
            gate_inputs: dict[str, Any] = {
                "knowledge_receipt_sha256": knowledge_receipt_sha256,
            }
            if any(value is not None for value in (
                knowledge_receipt, model_visible_context, serialized_principal_input,
            )):
                gate_inputs.update({
                    "knowledge_receipt": knowledge_receipt,
                    "model_visible_context": model_visible_context,
                    "serialized_principal_input": serialized_principal_input,
                })
            knowledge_use_receipt = knowledge_use_gate(body, **gate_inputs)
        except Exception as exc:  # noqa: BLE001 - the gate's own refusal, carried by name
            raise StagingError(f"the knowledge read gate refused the artifact: {exc}") from exc
    outputs_receipt_sha256, outputs_receipt = _validate_outputs(
        body,
        cited_delivery=cited_delivery,
        outputs_dir=outputs_dir,
        knowledge_receipt_sha256=knowledge_receipt_sha256,
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
        "delivery_receipt_sha256": cited_delivery,
        "stream_receipt_sha256": receipt_hashes["stream_receipt_sha256"],
        # S121 slice 1: the output bundle's receipt, validated above, travels with the
        # attribution so the result names the outputs the findings were filed beside.
        "outputs_receipt_sha256": outputs_receipt_sha256,
        "outputs_receipt": outputs_receipt,
    }
    if knowledge_use_receipt is not None:
        execution["knowledge_use_receipt"] = knowledge_use_receipt
    if render_report:
        _render_report_beside(path)
    return execution, [dict(row) for row in findings]


def _validate_outputs(
    body: Mapping[str, Any],
    *,
    cited_delivery: str | None,
    outputs_dir: Path | None,
    knowledge_receipt_sha256: str | None,
) -> tuple[str | None, dict[str, Any] | None]:
    """The staging gate's call into the output validator. Returns (receipt sha, receipt).

    Refuses, in order: a delivered artifact with no `outputs_receipt_sha256`; a bundle handed
    in that the artifact never cites; a citation with no bundle to verify it against; a
    malformed citation; a bundle the validator refuses (its reason is carried verbatim); a
    bundle for another arm or role; and a validated bundle whose receipt is not the one cited.
    """
    cited = body.get("outputs_receipt_sha256")
    if cited is None:
        if cited_delivery is not None:
            raise StagingError(
                f"the artifact cites delivery receipt {cited_delivery}, so the principal had every "
                "exact ledger and his append-only output ledgers are the deliverable, yet it carries "
                "no `outputs_receipt_sha256`; a delivered run without its outputs is a failed spawn"
            )
        if outputs_dir is not None:
            raise StagingError(
                "an outputs directory was handed to staging and the artifact carries no "
                "`outputs_receipt_sha256`; a bundle the artifact does not bind to is a bundle from "
                "nowhere"
            )
        return None, None
    if not isinstance(cited, str) or _SHA256_RE.fullmatch(cited) is None:
        raise StagingError(f"outputs_receipt_sha256 must be a lowercase SHA-256, got {cited!r}")
    if outputs_dir is None:
        raise StagingError(
            f"the artifact cites outputs receipt {cited} and no outputs_dir was given; a citation "
            "nothing can verify is not evidence"
        )
    if knowledge_receipt_sha256 is not None and _SHA256_RE.fullmatch(knowledge_receipt_sha256) is None:
        raise StagingError(
            f"knowledge_receipt_sha256 must be a lowercase SHA-256, got {knowledge_receipt_sha256!r}"
        )
    try:
        receipt = validate_output_bundle_dir(
            outputs_dir,
            registry=load_registry(),
            contract_text=CONTRACT_PATH.read_text(encoding="utf-8"),
            knowledge_receipt_sha256=knowledge_receipt_sha256,
            delivery_receipt_sha256=cited_delivery,
        )
    except (PrincipalOutputError, OSError, ValueError) as exc:
        raise StagingError(f"the principal's output bundle was refused: {exc}") from exc
    if receipt.get("arm") != body.get("arm") or receipt.get("role") != body.get("role"):
        raise StagingError(
            f"the output bundle belongs to arm {receipt.get('arm')!r} role {receipt.get('role')!r}; "
            f"the artifact is arm {body.get('arm')!r} role {body.get('role')!r}"
        )
    if receipt["receipt_sha256"] != cited:
        raise StagingError(
            f"the artifact cites outputs receipt {cited} and the bundle under validation has receipt "
            f"{receipt['receipt_sha256']}; the findings were filed beside a different set of outputs"
        )
    return cited, receipt


def _render_report_beside(
    path: Path,
    *,
    crosswalk: Mapping[str, Any] | None = None,
    crosswalk_note: str | None = None,
) -> Path | None:
    """Write the human-readable report next to the artifact. Never fatal.

    Imported inside the function so a renderer problem can never stop an artifact from
    validating: the findings are the deliverable, the report is how anyone reads them.
    `crosswalk` / `crosswalk_note` (S121 slice 3) are appended by the renderer.
    """
    try:
        from research.kalshi.frankie_raw_mbo_benchmark.render_frankie_report import (
            write_report,
        )

        return write_report(path, crosswalk=crosswalk, crosswalk_note=crosswalk_note)
    except Exception as exc:  # noqa: BLE001 - see docstring; reported, never raised
        print(
            f"WARNING: principal artifact at {path} validated but its report could not be "
            f"rendered: {exc}",
            file=sys.stderr,
        )
        return None


#: The read-back writes `<stem>_with_findings<suffix>` beside the original result. The original
#: is the evidence the artifact cites by hash, and it is never written over.
READ_BACK_SUFFIX = "_with_findings"
READ_BACK_SCHEMA = "FRANKIE_NATIVE_RAW_MBO_READ_BACK_V1"


def _load_receipt_file(path: Path | str | None, *, label: str) -> dict[str, Any] | None:
    """A receipt JSON handed to the read-back, or None. It must at least carry its own hash."""
    if path is None:
        return None
    path = Path(path)
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise StagingError(f"no {label} at {path}") from exc
    except json.JSONDecodeError as exc:
        raise StagingError(f"{label} at {path} is not valid JSON: {exc}") from exc
    if not isinstance(body, Mapping):
        raise StagingError(f"{label} at {path} is not an object")
    sha = body.get("receipt_sha256")
    if not isinstance(sha, str) or _SHA256_RE.fullmatch(sha) is None:
        raise StagingError(f"{label} at {path} carries no receipt_sha256; it cannot be bound to the artifact")
    return dict(body)


def _load_exact_bytes(path: Path | str | None, *, label: str) -> bytes | None:
    """Read one exact staged input, or preserve its absence for the gate to refuse."""
    if path is None:
        return None
    path = Path(path)
    try:
        return path.read_bytes()
    except OSError as exc:
        raise StagingError(f"cannot read the {label} at {path}: {exc}") from exc


def _bind_receipt_sha(file_body: Mapping[str, Any] | None, stated: str | None, *, label: str) -> str | None:
    """The receipt sha the read-back works with: the file's, which a stated one must equal."""
    if file_body is None:
        return stated
    file_sha = file_body["receipt_sha256"]
    if stated is not None and stated != file_sha:
        raise StagingError(
            f"the {label} file has receipt_sha256 {file_sha} and {label.replace(' ', '_')}_sha256 "
            f"{stated} was stated; the two name different receipts"
        )
    return file_sha


def _crosswalk_for_report(
    *,
    execution: Mapping[str, Any],
    result: Mapping[str, Any],
    delivery_receipt: Mapping[str, Any] | None,
    knowledge_receipt: Mapping[str, Any] | None,
) -> tuple[dict[str, Any] | None, str | None]:
    """The 99-layer crosswalk for the report, or the reason there is none. Never raises.

    The crosswalk is part of the RENDER: the findings are the deliverable, so a crosswalk that
    cannot be computed is reported (in the report itself, and on stderr) rather than fatal.
    """
    try:
        # Imported here, not at module level: the crosswalk imports the ledger fetcher, which
        # imports this module - a top-level import would cycle.
        from research.kalshi.frankie_raw_mbo_benchmark.native_layer_crosswalk import crosswalk

        body = crosswalk(
            load_registry(),
            arm=execution["arm"],
            result=result,
            delivery_receipt=delivery_receipt,
            knowledge_receipt=knowledge_receipt,
            outputs_receipt=execution.get("outputs_receipt"),
        )
        return body, None
    except Exception as exc:  # noqa: BLE001 - see docstring; stated in the report, never raised
        note = f"crosswalk could not be computed: {exc}"
        print(f"WARNING: {note}", file=sys.stderr)
        return None, note


#: The role that hands off; the forecaster-side objects come from the forecaster's own run.
RT_ROLE = "REAL_TIME_FRANKIE"


def _identity_binding(result: Mapping[str, Any], result_path: Path) -> tuple[str, str]:
    """(arm, source_manifest_hash) off the result's identity receipt - the layer `finalize`
    writes from `RunIdentity`, inside the hash the read-back has already verified. Nothing else
    may supply either: a CLI string names a source the run may not have been computed from."""
    layers = result.get("layers")
    identity = layers.get(LAYER_IDENTITY) if isinstance(layers, Mapping) else None
    if not isinstance(identity, Mapping):
        raise StagingError(
            f"calculation result at {result_path} carries no {LAYER_IDENTITY!r} layer; the "
            "read-back binds the arm and the source_manifest_hash from it and from nothing else"
        )
    arm = identity.get("arm")
    if arm not in ALLOWED_ARMS:
        raise StagingError(
            f"the result's identity receipt names arm {arm!r}; expected one of {sorted(ALLOWED_ARMS)}"
        )
    source_manifest_hash = identity.get("source_manifest_hash")
    if not isinstance(source_manifest_hash, str) or _SHA256_RE.fullmatch(source_manifest_hash) is None:
        raise StagingError(
            f"the result's identity receipt carries no source_manifest_hash (got "
            f"{source_manifest_hash!r}); the handoff names the source the run was computed "
            "from, and nothing but the result may supply it"
        )
    return str(arm), source_manifest_hash


def _handoff_for_read_back(
    execution: Mapping[str, Any],
    *,
    outputs_dir: Path | str | None,
    source_manifest_hash: str,
    knowledge_receipt_sha256: str | None,
) -> tuple[dict[str, dict[str, Any]] | None, str | None]:
    """The handoff trio for a validated read-back, or (None, why there is none).

    No bundle (the artifact cites no delivery receipt, so nothing was validated) and a
    FORECASTER_FRANKIE artifact are STATED, not refused: the findings still attach. A bundle
    `build_handoff` refuses raises, and the read-back writes nothing.
    """
    if execution.get("outputs_receipt") is None or outputs_dir is None:
        return None, (
            "no output bundle was validated for this artifact (it cites no delivery receipt), "
            "so there is no bundle to build a handoff from"
        )
    if execution.get("role") != RT_ROLE:
        return None, (
            f"a {execution.get('role')} artifact hands nothing off; the one-way handoff runs "
            f"FROM {RT_ROLE}, and the forecaster-side objects are written from the forecaster's "
            "own output after it runs"
        )
    objects = build_handoff(
        outputs_dir,
        artifact_sha256=execution["artifact_sha256"],
        source_manifest_hash=source_manifest_hash,
        knowledge_receipt_sha256=knowledge_receipt_sha256,
        delivery_receipt_sha256=execution.get("delivery_receipt_sha256"),
    )
    return objects, None


def _first_lock_summary(
    handoff_objects: Mapping[str, Mapping[str, Any]] | None,
) -> tuple[dict[str, Any] | None, str | None]:
    """What the summary says about the first lock: the entry's identity, or why there is none."""
    if handoff_objects is None:
        return None, None
    entry = handoff_objects["RT_FIRST_LOCK"].get("first_lock")
    if entry is None:
        return None, (
            "the bundle's lock ledger carries no FIRST_LOCK entry; RT_FIRST_LOCK.first_lock is "
            "null, never a NO_LOCK dressed as a lock"
        )
    return {
        "entry_hash": entry["entry_hash"],
        "candidate_id": entry["body"].get("candidate_id"),
        "cutoff_recv_ns": entry.get("cutoff_recv_ns"),
    }, None


def read_back(
    artifact_path: Path | str,
    *,
    result_path: Path | str,
    outputs_dir: Path | str | None = None,
    out_path: Path | str | None = None,
    knowledge_receipt_sha256: str | None = None,
    delivery_receipt_sha256: str | None = None,
    delivery_receipt: Path | str | None = None,
    knowledge_receipt: Path | str | None = None,
    knowledge_bundle: Path | str | None = None,
    prompt: Path | str | None = None,
    render_report: bool = True,
    handoff_dir: Path | str | None = None,
    knowledge_use_gate: KnowledgeUseGate | None = None,
) -> dict[str, Any]:
    """Close the loop: a finished `calculation_result.json` receives the principal's findings.

    Reads the result and refuses one that does not hash to itself or already carries
    principal findings; validates the artifact and its output bundle against that result's
    hash through `load_principal_artifact`; attaches through the runner's own route
    (`NativeCalculationRun.attach_principal_findings_to_result`); writes the updated result
    BESIDE the original under `READ_BACK_SUFFIX`, never over it and never over an earlier
    read-back. Returns a summary naming every hash involved.

    `delivery_receipt` and `knowledge_receipt` are receipt FILES (S121 slice 3). Each is bound
    by hash: the delivery receipt must be the one the artifact cites, and a stated
    `*_sha256` must equal its file's. With the result and the receipts in hand the read-back
    computes the 99-layer crosswalk and the report carries it; the crosswalk is part of the
    render, so its failure is stated in the report and stays non-fatal, as a render failure
    always has. When the knowledge-use gate is supplied, `knowledge_bundle` and `prompt` are
    the exact staged files whose bytes form the principal input; absence is passed to the gate
    as absence and refused, never replaced with inferred or generated bytes.

    **The handoff (S122 slice 6).** After a successful attach the read-back builds the V2
    workmode real-time handoff trio from the VALIDATED bundle (`build_handoff`) and writes it
    with `write_handoff` - ONEWAY_HANDOFF, RT_FIRST_LOCK, RT_CONTEXT_MANIFEST - BESIDE the
    read-back output (or under `handoff_dir`), exclusive-create, never over an earlier trio;
    an existing file refuses the whole read-back before anything is written. The arm and
    `source_manifest_hash` are bound off the result's identity receipt (`layers.identity_receipt`,
    what the launch stamped from `RunIdentity`), never from a CLI string; an artifact on
    another arm than the run is refused. An artifact with no bundle (no delivery receipt) or
    a FORECASTER_FRANKIE artifact has no handoff, and the summary SAYS so; a bundle whose lock
    ledger carries no FIRST_LOCK yields a null `first_lock` and a stated note, never a
    fabricated one. `knowledge_use_gate` is the seam described at `KNOWLEDGE_USE_GATE`.
    """
    artifact_path = Path(artifact_path)
    result_path = Path(result_path)
    delivery_body = _load_receipt_file(delivery_receipt, label="delivery receipt")
    knowledge_body = _load_receipt_file(knowledge_receipt, label="knowledge receipt")
    model_visible_context = _load_exact_bytes(knowledge_bundle, label="knowledge bundle")
    prompt_bytes = _load_exact_bytes(prompt, label="spawn prompt")
    principal_input = (
        bind_serialized_principal_input(prompt_bytes, model_visible_context)
        if prompt_bytes is not None and model_visible_context is not None
        else None
    )
    delivery_receipt_sha256 = _bind_receipt_sha(delivery_body, delivery_receipt_sha256, label="delivery receipt")
    knowledge_receipt_sha256 = _bind_receipt_sha(knowledge_body, knowledge_receipt_sha256, label="knowledge receipt")
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise StagingError(f"no calculation result at {result_path}") from exc
    except json.JSONDecodeError as exc:
        raise StagingError(f"calculation result at {result_path} is not valid JSON: {exc}") from exc
    if not isinstance(result, Mapping) or not isinstance(result.get("result_hash"), str):
        raise StagingError(
            f"calculation result at {result_path} carries no result_hash; there is nothing for "
            "an artifact to cite"
        )
    recomputed = canonical_hash({k: v for k, v in result.items() if k != "result_hash"})
    if recomputed != result["result_hash"]:
        raise StagingError(
            f"calculation result at {result_path} declares result_hash {result['result_hash']} "
            f"and recomputes to {recomputed}; a result that does not hash to itself is tampered "
            "or partial and cannot receive findings"
        )
    if result.get("completion_status") != "EVIDENCE_ONLY":
        raise StagingError(
            f"calculation result at {result_path} already carries principal findings "
            f"(completion_status {result.get('completion_status')!r}); the read-back attaches to "
            "an EVIDENCE_ONLY result and never replaces a filed record"
        )
    run_arm, source_manifest_hash = _identity_binding(result, result_path)
    target = (
        Path(out_path)
        if out_path is not None
        else result_path.with_name(f"{result_path.stem}{READ_BACK_SUFFIX}{result_path.suffix}")
    )
    if target.resolve() == result_path.resolve():
        raise StagingError(
            "the read-back never writes over the original result; it is the evidence the "
            "artifact cites by hash"
        )
    if target.exists():
        raise StagingError(
            f"{target} already exists; a read-back result is written once and never rewritten - "
            "remove or rename the earlier one to redo the read-back"
        )

    execution, findings = load_principal_artifact(
        artifact_path,
        expected_evidence_hash=result["result_hash"],
        render_report=False,
        outputs_dir=None if outputs_dir is None else Path(outputs_dir),
        knowledge_receipt_sha256=knowledge_receipt_sha256,
        delivery_receipt_sha256=delivery_receipt_sha256,
        expected_arm=run_arm,
        knowledge_use_gate=knowledge_use_gate,
        knowledge_receipt=knowledge_body,
        model_visible_context=model_visible_context,
        serialized_principal_input=principal_input,
    )
    try:
        updated = NativeCalculationRun.attach_principal_findings_to_result(
            result, execution=execution, findings=findings
        )
    except CalculationRunError as exc:
        raise StagingError(f"the runner refused the findings: {exc}") from exc
    # The handoff is BUILT before anything is written, so a refusal writes nothing; the
    # target files are checked here for the same reason (write_handoff's O_EXCL still holds).
    handoff_objects, handoff_note = _handoff_for_read_back(
        execution,
        outputs_dir=outputs_dir,
        source_manifest_hash=source_manifest_hash,
        knowledge_receipt_sha256=knowledge_receipt_sha256,
    )
    handoff_target: Path | None = None
    if handoff_objects is not None:
        handoff_target = Path(handoff_dir) if handoff_dir is not None else target.parent
        for name in HANDOFF_FILES:
            if (handoff_target / f"{name}.json").exists():
                raise StagingError(
                    f"{handoff_target / f'{name}.json'} already exists; a handoff is written once "
                    "and never rewritten, so this read-back writes nothing"
                )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(updated, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8"
    )
    handoff_summary: dict[str, dict[str, str]] | None = None
    if handoff_objects is not None and handoff_target is not None:
        written_paths = write_handoff(handoff_objects, handoff_target)
        handoff_summary = {
            name: {"path": str(path), "receipt_hash": handoff_objects[name]["receipt_hash"]}
            for name, path in zip(HANDOFF_FILES, written_paths)
        }
    first_lock, first_lock_note = _first_lock_summary(handoff_objects)
    report: Path | None = None
    crosswalk_body: dict[str, Any] | None = None
    if render_report:
        crosswalk_body, crosswalk_note = _crosswalk_for_report(
            execution=execution, result=result,
            delivery_receipt=delivery_body, knowledge_receipt=knowledge_body,
        )
        report = _render_report_beside(
            artifact_path, crosswalk=crosswalk_body, crosswalk_note=crosswalk_note
        )
    return {
        "schema": READ_BACK_SCHEMA,
        "principal": execution["principal"],
        "arm": execution["arm"],
        "role": execution["role"],
        "artifact_path": str(artifact_path),
        "artifact_sha256": execution["artifact_sha256"],
        "evidence_result_path": str(result_path),
        "evidence_result_hash": result["result_hash"],
        "result_path": str(target),
        "result_hash": updated["result_hash"],
        "findings_attached": len(findings),
        "delivery_receipt_sha256": execution["delivery_receipt_sha256"],
        "knowledge_receipt_sha256": knowledge_receipt_sha256,
        "outputs_receipt_sha256": execution["outputs_receipt_sha256"],
        "source_manifest_hash": source_manifest_hash,
        "crosswalk_sha256": None if crosswalk_body is None else crosswalk_body["crosswalk_sha256"],
        "report_path": None if report is None else str(report),
        "handoff_dir": None if handoff_target is None else str(handoff_target),
        "handoff": handoff_summary,
        "handoff_note": handoff_note,
        "first_lock": first_lock,
        "first_lock_note": first_lock_note,
    }


# ------------------------------------------------------------------------------------------
# S121 slice 4: the V2 workmode handoff, re-fed from a VALIDATED output bundle
# ------------------------------------------------------------------------------------------

#: The schema strings `ng_exhaustion_two_frankies_workmode_coordinate_2day_20260825.freeze_rt`
#: writes for the real-time side of the one-way handoff. They are literals inside that function,
#: so they are restated here and PINNED by test against the committed record of the wrong-data
#: run (`prior_memory/workmode-32851909748-1/`): same schema, same key set. The hashing and the
#: self-check are that module's own `sha256_json` / `verify_self_hash`, imported, never rewritten.
HANDOFF_SCHEMA = "FRANKIE_PRIOR_SURFACE_OCT45_ONEWAY_HANDOFF_V2_WORKMODE_20260825"
RT_FIRST_LOCK_SCHEMA = "FRANKIE_PRIOR_SURFACE_OCT45_RT_FIRST_LOCK_V2_WORKMODE_20260825"
RT_CONTEXT_MANIFEST_SCHEMA = "FRANKIE_PRIOR_SURFACE_OCT45_RT_CONTEXT_MANIFEST_V2_WORKMODE_20260825"
#: Object name -> file name, as `freeze_rt` writes them into a run root.
HANDOFF_FILES = ("ONEWAY_HANDOFF", "RT_FIRST_LOCK", "RT_CONTEXT_MANIFEST")
FIRST_LOCKS_LEDGER = "output_first_locks_and_no_locks"
CANDIDATES_LEDGER = "output_candidate_discoveries"
ANSWER_WALL_LEDGER = "output_answer_wall_access_receipts"
INVOCATIONS_LEDGER = "output_provider_invocation_response_receipts"


def first_lock_entry(locks: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    """The first FIRST_LOCK entry of a lock ledger's entries, or None when there is none."""
    for entry in locks:
        body = entry.get("body")
        if isinstance(body, Mapping) and body.get("lock_state") == "FIRST_LOCK":
            return entry
    return None


def build_handoff(
    outputs_dir: Path | str,
    *,
    artifact_sha256: str,
    source_manifest_hash: str,
    knowledge_receipt_sha256: str | None = None,
    delivery_receipt_sha256: str | None = None,
) -> dict[str, dict[str, Any]]:
    """The real-time side of the one-way handoff, built from a validated output bundle.

    The bundle is validated again here - a handoff is never built from an unvalidated bundle -
    and its receipt sha256 is the frozen state's hash: `frozen_rt_state_hash` = the bundle
    receipt sha, `full_validated_rt_output_hash` = the artifact sha, `RT_FIRST_LOCK.first_lock`
    = the head entry of `output_first_locks_and_no_locks` (chain-hashed, verbatim),
    `exhaustion_events` = the `output_candidate_discoveries` entries (the new surface's
    candidate roster, verbatim), `answer_wall` SEALED read off the EMPTY answer-wall ledger,
    - `first_lock` is the FIRST entry whose `lock_state` is FIRST_LOCK, never the ledger head
    (a later NO_LOCK for another candidate is the head, not the lock), and null when the
    ledger carries no FIRST_LOCK at all: a NO_LOCK dressed as the first lock is fabricated -
    `provider_api_called` False read off every invocation receipt being an AGENT_SESSION,
    `packet_hash` = the delivery receipt the bundle was produced against (the packet he was
    handed), `source_manifest_hash` from the run's identity. Only a REAL_TIME_FRANKIE bundle
    hands off; the forecaster-side objects (`FORECASTER_FIRST_LOCK`,
    `FORECASTER_CONTEXT_MANIFEST`) are written by `finalize` from the FORECASTER's own output,
    which does not exist until the forecaster has run against this handoff.
    """
    # Imported here: the coordinator module pulls the whole prior-surface module behind it,
    # and nothing else in staging needs it.
    from research.kalshi import ng_exhaustion_two_frankies_workmode_coordinate_2day_20260825 as workmode
    from research.kalshi.frankie_raw_mbo_benchmark.native_principal_outputs import (
        ledger_entries,
        load_bundle,
    )
    from research.kalshi.frankie_role_context_profiles_20260824 import FrankieRole

    for label, value in (("artifact_sha256", artifact_sha256), ("source_manifest_hash", source_manifest_hash)):
        if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
            raise StagingError(f"{label} must be a lowercase SHA-256, got {value!r}")
    try:
        receipt = validate_output_bundle_dir(
            outputs_dir,
            registry=load_registry(),
            contract_text=CONTRACT_PATH.read_text(encoding="utf-8"),
            knowledge_receipt_sha256=knowledge_receipt_sha256,
            delivery_receipt_sha256=delivery_receipt_sha256,
        )
        bundle = load_bundle(outputs_dir)
        locks = ledger_entries(bundle, FIRST_LOCKS_LEDGER)
        candidates = ledger_entries(bundle, CANDIDATES_LEDGER)
        wall = ledger_entries(bundle, ANSWER_WALL_LEDGER)
        invocations = ledger_entries(bundle, INVOCATIONS_LEDGER)
    except (PrincipalOutputError, OSError, ValueError) as exc:
        raise StagingError(f"no handoff from a bundle the validator refuses: {exc}") from exc
    role = bundle["role"]
    if role != FrankieRole.REAL_TIME.value:
        raise StagingError(
            f"the one-way handoff runs FROM {FrankieRole.REAL_TIME.value}; a {role} bundle has "
            "nothing to hand off, and the forecaster-side objects are written from the "
            "forecaster's own output after it runs"
        )
    if wall:
        raise StagingError(f"{len(wall)} answer-wall access receipt(s); the answer wall is not sealed")
    if delivery_receipt_sha256 is None and bundle.get("delivery_receipt_sha256") is None:
        raise StagingError(
            "the bundle names no delivery receipt; a handoff states the packet he was handed and a "
            "pre-delivery bundle has none"
        )
    packet_hash = delivery_receipt_sha256 or bundle["delivery_receipt_sha256"]
    provider_api_called = any(entry["body"].get("mechanism") != "AGENT_SESSION" for entry in invocations)

    handoff: dict[str, Any] = {
        "schema": HANDOFF_SCHEMA,
        "from_role": FrankieRole.REAL_TIME.value,
        "to_role": FrankieRole.FORECASTER.value,
        "frozen_rt_state_hash": receipt["receipt_sha256"],
        "full_validated_rt_output_included": True,
        "full_validated_rt_output_hash": artifact_sha256,
        "forecaster_may_modify_rt_state": False,
        "forecaster_may_reconstruct_competing_current_state": False,
        "rt_frozen_before_forecaster": True,
    }
    handoff["receipt_hash"] = workmode.sha256_json(handoff)
    first_lock = first_lock_entry(locks)
    lock: dict[str, Any] = {
        "schema": RT_FIRST_LOCK_SCHEMA,
        "rt_output_hash": artifact_sha256,
        "first_lock": None if first_lock is None else dict(first_lock),
        "first_lock_owner": role,
        "exhaustion_events": [dict(entry) for entry in candidates],
    }
    lock["receipt_hash"] = workmode.sha256_json(lock)
    context: dict[str, Any] = {
        "schema": RT_CONTEXT_MANIFEST_SCHEMA,
        "role": role,
        "packet_hash": packet_hash,
        "source_manifest_hash": source_manifest_hash,
        "answer_wall": "SEALED",
        "provider_api_called": provider_api_called,
        "role_is_forecasting": False,
    }
    context["receipt_hash"] = workmode.sha256_json(context)
    return {"ONEWAY_HANDOFF": handoff, "RT_FIRST_LOCK": lock, "RT_CONTEXT_MANIFEST": context}


def write_handoff(objects: Mapping[str, Mapping[str, Any]], out_dir: Path | str) -> list[Path]:
    """Write the handoff objects as `<NAME>.json` under `out_dir`, exclusive-create, never over.

    Uses the coordinator module's own `write_json` (O_EXCL), so a second write is refused the
    way `freeze_rt` refuses an existing run root.
    """
    from research.kalshi import ng_exhaustion_two_frankies_workmode_coordinate_2day_20260825 as workmode

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name in HANDOFF_FILES:
        if name not in objects:
            raise StagingError(f"handoff object {name!r} is missing; build_handoff produces all of {list(HANDOFF_FILES)}")
        target = out_dir / f"{name}.json"
        try:
            workmode.write_json(target, dict(objects[name]))
        except FileExistsError as exc:
            raise StagingError(f"{target} already exists; a handoff is written once and never rewritten") from exc
        written.append(target)
    return written


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m research.kalshi.frankie_raw_mbo_benchmark.native_staging",
        description=(
            "THE CANONICAL READ-BACK. Read a principal artifact back against its finished "
            "calculation result: validate the artifact, its output bundle and every receipt, "
            "attach the findings through the runner's own route, write the result with findings "
            "beside the original, render the report with the layer crosswalk, and build the RT "
            "handoff trio from the validated bundle. One arm (A_MEMORY), bound off the result - "
            "nothing to remember. Prints a JSON summary, or REFUSED and why."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)
    rb = commands.add_parser("read-back", help="attach a validated artifact's findings to a finished result")
    rb.add_argument("--artifact", required=True, type=Path, help="the committed principal findings artifact")
    rb.add_argument("--result", required=True, type=Path, help="the run's calculation_result.json (never written over)")
    rb.add_argument("--outputs-dir", type=Path, default=None, help="the principal's output bundle directory (ledgers/ + RECEIPT.json)")
    rb.add_argument("--out", type=Path, default=None, help=f"where to write the result with findings (default: beside --result with {READ_BACK_SUFFIX!r})")
    rb.add_argument("--knowledge-receipt-sha256", default=None, help="the knowledge-delivery receipt every verdict must cite")
    rb.add_argument("--delivery-receipt-sha256", default=None, help="the ledger-delivery receipt the artifact must cite")
    rb.add_argument("--delivery-receipt", type=Path, default=None, help="FRANKIE_LEDGER_DELIVERY_RECEIPT_V1 file; bound by hash to the artifact's citation and fed to the crosswalk")
    rb.add_argument("--knowledge-receipt", type=Path, default=None, help="FRANKIE_KNOWLEDGE_DELIVERY_RECEIPT_V1 file; its hash is the one the verdicts must cite, and it feeds the crosswalk")
    rb.add_argument("--knowledge-bundle", type=Path, default=None, help="the exact model-visible KNOWLEDGE_BUNDLE.md delivered to the principal")
    rb.add_argument("--prompt", type=Path, default=None, help="the exact FRANKIE_SPAWN_PROMPT.md delivered beside the knowledge bundle")
    rb.add_argument("--handoff-dir", type=Path, default=None, help="where to write ONEWAY_HANDOFF / RT_FIRST_LOCK / RT_CONTEXT_MANIFEST (default: beside the result with findings; never over an earlier trio)")
    rb.add_argument("--no-report", action="store_true", help="do not render the findings report (and its crosswalk) beside the artifact")
    args = parser.parse_args(argv)
    try:
        summary = read_back(
            args.artifact,
            result_path=args.result,
            outputs_dir=args.outputs_dir,
            out_path=args.out,
            knowledge_receipt_sha256=args.knowledge_receipt_sha256,
            delivery_receipt_sha256=args.delivery_receipt_sha256,
            delivery_receipt=args.delivery_receipt,
            knowledge_receipt=args.knowledge_receipt,
            knowledge_bundle=args.knowledge_bundle,
            prompt=args.prompt,
            render_report=not args.no_report,
            handoff_dir=args.handoff_dir,
            knowledge_use_gate=KNOWLEDGE_USE_GATE,
        )
    except (StagingError, OSError, ValueError) as exc:
        print(f"REFUSED: {exc}")
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


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


if __name__ == "__main__":
    raise SystemExit(main())
