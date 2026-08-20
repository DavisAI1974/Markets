"""External evaluation controls for Frankie SHADOW candidates.

These controls protect evidence about candidate quality.  They do not improve a
model, grade market truth, authorize V4, or grant promotion/execution authority.
"""
from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from frankie_cognition import CognitiveContractError, sha256_json

RELEASE_ROLES = {"RELEASE", "UNTOUCHED_FORWARD"}
OUTPUT_LEVELS = {"COUNT_ONLY", "AGGREGATE_ONLY", "ROW_LEVEL", "ERROR_EXAMPLES"}
MIN_JUDGE_CANARY_CASES = 100
SHA256_RE = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class HoldoutExposure:
    query_id: str
    consumer: str
    purpose: str
    output_level: str
    parent_hashes: tuple[str, ...]
    prior_hash: str
    exposure_hash: str


@dataclass(frozen=True)
class HoldoutExposureLedger:
    """Hash-chained record of what was learned from one split.

    Release and untouched-forward splits are one-shot: a locked evaluator may
    emit one aggregate final score.  Row-level data, examples, plots represented
    as parent artifacts, or a second score are refused rather than merely logged.
    """

    split_id: str
    split_hash: str
    role: str
    exposures: tuple[HoldoutExposure, ...] = ()

    def __post_init__(self) -> None:
        if not self.split_id.strip() or not SHA256_RE.fullmatch(self.split_hash):
            raise CognitiveContractError("holdout ledger requires split id and content hash")
        if self.role not in {"DEVELOPMENT", "CALIBRATION", *RELEASE_ROLES}:
            raise CognitiveContractError(f"invalid holdout role: {self.role}")

    def record(
        self,
        *,
        query_id: str,
        consumer: str,
        purpose: str,
        output_level: str,
        parent_hashes: Sequence[str] = (),
    ) -> "HoldoutExposureLedger":
        values = (query_id.strip(), consumer.strip(), purpose.strip())
        if not all(values) or any(item.query_id == values[0] for item in self.exposures):
            raise CognitiveContractError("holdout exposure requires unique id, consumer, and purpose")
        level = output_level.strip().upper()
        if level not in OUTPUT_LEVELS:
            raise CognitiveContractError(f"invalid holdout output level: {output_level}")
        parents = tuple(dict.fromkeys(str(value).strip() for value in parent_hashes if str(value).strip()))
        if any(not SHA256_RE.fullmatch(value) for value in parents):
            raise CognitiveContractError("holdout parent artifacts require SHA-256 hashes")

        if self.role in RELEASE_ROLES:
            if self.exposures:
                raise CognitiveContractError("release holdout is one-shot and was already consumed")
            if values[2].upper() != "FINAL_RELEASE_SCORE":
                raise CognitiveContractError("release holdout permits only the final release score")
            if level != "AGGREGATE_ONLY":
                raise CognitiveContractError("release holdout may disclose aggregate output only")

        prior_hash = self.exposures[-1].exposure_hash if self.exposures else self.split_hash
        core = {
            "split_id": self.split_id,
            "split_hash": self.split_hash,
            "role": self.role,
            "query_id": values[0],
            "consumer": values[1],
            "purpose": values[2],
            "output_level": level,
            "parent_hashes": parents,
            "prior_hash": prior_hash,
        }
        exposure = HoldoutExposure(
            query_id=values[0],
            consumer=values[1],
            purpose=values[2],
            output_level=level,
            parent_hashes=parents,
            prior_hash=prior_hash,
            exposure_hash=sha256_json(core),
        )
        return dataclasses.replace(self, exposures=(*self.exposures, exposure))

    def release_audit(self) -> dict[str, Any]:
        if self.role not in RELEASE_ROLES:
            raise CognitiveContractError("release audit requires a release-class split")
        final = [item for item in self.exposures if item.purpose.upper() == "FINAL_RELEASE_SCORE"]
        row_level = any(item.output_level in {"ROW_LEVEL", "ERROR_EXAMPLES"} for item in self.exposures)
        core = {
            "split_id": self.split_id,
            "split_hash": self.split_hash,
            "role": self.role,
            "exposure_count": len(self.exposures),
            "final_score_queries": len(final),
            "row_level_disclosed": row_level,
            "release_usable": len(self.exposures) == 1 and len(final) == 1 and not row_level,
            "ledger_tip": self.exposures[-1].exposure_hash if self.exposures else self.split_hash,
            "exposures": [dataclasses.asdict(item) for item in self.exposures],
        }
        return {**core, "audit_hash": sha256_json(core)}


def validate_release_exposure_audit(
    audit: Mapping[str, Any],
    *,
    split_id: str,
    split_hash: str,
    expected_consumer: str | None = None,
    required_parent_hashes: Sequence[str] = (),
) -> str:
    """Validate the serialized one-shot hash chain and return its audit hash."""
    core = {key: audit.get(key) for key in (
        "split_id",
        "split_hash",
        "role",
        "exposure_count",
        "final_score_queries",
        "row_level_disclosed",
        "release_usable",
        "ledger_tip",
        "exposures",
    )}
    if audit.get("audit_hash") != sha256_json(core):
        raise CognitiveContractError("holdout exposure audit hash mismatch")
    if (
        core["split_id"] != split_id
        or core["split_hash"] != split_hash
        or not SHA256_RE.fullmatch(str(core["split_hash"] or ""))
        or core["role"] not in RELEASE_ROLES
    ):
        raise CognitiveContractError("holdout exposure audit does not match the release split")
    if (
        type(core["exposure_count"]) is not int
        or core["exposure_count"] != 1
        or type(core["final_score_queries"]) is not int
        or core["final_score_queries"] != 1
        or core["row_level_disclosed"] is not False
        or core["release_usable"] is not True
        or not SHA256_RE.fullmatch(str(core["ledger_tip"] or ""))
    ):
        raise CognitiveContractError("holdout exposure firewall did not pass")

    exposures = core["exposures"]
    if not isinstance(exposures, list) or len(exposures) != 1:
        raise CognitiveContractError("release audit must serialize its one exposure")
    exposure = exposures[0]
    if not isinstance(exposure, Mapping):
        raise CognitiveContractError("release exposure receipt must be an object")
    parents_raw = exposure.get("parent_hashes")
    if not isinstance(parents_raw, (list, tuple)):
        raise CognitiveContractError("release exposure parent hashes must be serialized")
    parents = tuple(str(value) for value in parents_raw)
    if any(not SHA256_RE.fullmatch(value) for value in parents):
        raise CognitiveContractError("release exposure contains an invalid parent hash")
    exposure_core = {
        "split_id": core["split_id"],
        "split_hash": core["split_hash"],
        "role": core["role"],
        "query_id": exposure.get("query_id"),
        "consumer": exposure.get("consumer"),
        "purpose": exposure.get("purpose"),
        "output_level": exposure.get("output_level"),
        "parent_hashes": parents,
        "prior_hash": exposure.get("prior_hash"),
    }
    expected_exposure_hash = sha256_json(exposure_core)
    if (
        exposure.get("prior_hash") != core["split_hash"]
        or exposure.get("exposure_hash") != expected_exposure_hash
        or core["ledger_tip"] != expected_exposure_hash
        or exposure.get("purpose") != "FINAL_RELEASE_SCORE"
        or exposure.get("output_level") != "AGGREGATE_ONLY"
    ):
        raise CognitiveContractError("release exposure hash chain is invalid")
    if expected_consumer is not None and exposure.get("consumer") != expected_consumer:
        raise CognitiveContractError("release exposure consumer does not match the locked evaluator")
    required = tuple(str(value) for value in required_parent_hashes)
    if any(not SHA256_RE.fullmatch(value) for value in required):
        raise CognitiveContractError("required release parent hashes must be SHA-256 values")
    missing = sorted(set(required) - set(parents))
    if missing:
        raise CognitiveContractError(
            "release exposure is missing required parent artifacts: " + ", ".join(missing)
        )
    return str(audit["audit_hash"])


def evaluate_judge_independence_canary(
    rows: Sequence[Mapping[str, Any]],
    *,
    max_order_flip_rate: float = 0.01,
    max_length_control_flip_rate: float = 0.01,
    max_truth_disagreement_rate: float = 0.05,
    judge_id: str = "UNBOUND",
    judge_version_hash: str | None = None,
    canary_manifest_hash: str | None = None,
) -> dict[str, Any]:
    """Audit a judge with answer-order, length, and objective-truth controls.

    Choices must already be normalized to stable candidate ids; answer-position
    labels such as A/B are not accepted.  A canary can revoke grading authority,
    never grant promotion authority.
    """
    tolerances = (
        max_order_flip_rate,
        max_length_control_flip_rate,
        max_truth_disagreement_rate,
    )
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not 0.0 <= float(value) <= 1.0
        for value in tolerances
    ):
        raise CognitiveContractError("judge canary tolerances must be numeric within [0, 1]")
    if len(rows) < MIN_JUDGE_CANARY_CASES:
        raise CognitiveContractError(
            f"judge canary requires at least {MIN_JUDGE_CANARY_CASES} cases"
        )
    seen: set[str] = set()
    order_flips = 0
    length_flips = 0
    truth_disagreements = 0
    for row in rows:
        case_id = str(row.get("case_id") or "").strip()
        if not case_id or case_id in seen:
            raise CognitiveContractError("judge canary requires unique case ids")
        seen.add(case_id)
        truth = str(row.get("truth_choice") or "").strip()
        forward = str(row.get("forward_choice") or "").strip()
        reversed_choice = str(row.get("reversed_choice") or "").strip()
        length_control = str(row.get("length_control_choice") or "").strip()
        if not all((truth, forward, reversed_choice, length_control)):
            raise CognitiveContractError(f"judge canary case {case_id} is incomplete")
        order_flips += int(forward != reversed_choice)
        length_flips += int(forward != length_control)
        truth_disagreements += int(forward != truth or reversed_choice != truth)

    rates = {
        "order_flip_rate": order_flips / len(rows),
        "length_control_flip_rate": length_flips / len(rows),
        "truth_disagreement_rate": truth_disagreements / len(rows),
    }
    blockers = []
    if rates["order_flip_rate"] > max_order_flip_rate:
        blockers.append("answer-order bias exceeded tolerance")
    if rates["length_control_flip_rate"] > max_length_control_flip_rate:
        blockers.append("length/verbosity control exceeded tolerance")
    if rates["truth_disagreement_rate"] > max_truth_disagreement_rate:
        blockers.append("objective-truth disagreement exceeded tolerance")
    core = {
        "judge_id": str(judge_id).strip(),
        "judge_version_hash": judge_version_hash,
        "canary_manifest_hash": canary_manifest_hash,
        "case_set_hash": sha256_json([dict(row) for row in rows]),
        "cases": len(rows),
        "rates": rates,
        "tolerances": {
            "order_flip_rate": max_order_flip_rate,
            "length_control_flip_rate": max_length_control_flip_rate,
            "truth_disagreement_rate": max_truth_disagreement_rate,
        },
        "verdict": "JUDGE_AUTHORITY_RETAINED" if not blockers else "JUDGE_AUTHORITY_REVOKED",
        "blockers": blockers,
        "promotion_authority": "NONE",
    }
    if not core["judge_id"] or core["judge_id"] == "UNBOUND":
        blockers.append("judge identity is not bound")
    if not SHA256_RE.fullmatch(str(judge_version_hash or "")):
        blockers.append("judge version hash is not bound")
    if not SHA256_RE.fullmatch(str(canary_manifest_hash or "")):
        blockers.append("canary manifest hash is not bound")
    core["verdict"] = "JUDGE_AUTHORITY_RETAINED" if not blockers else "JUDGE_AUTHORITY_REVOKED"
    core["blockers"] = blockers
    return {**core, "canary_hash": sha256_json(core)}
