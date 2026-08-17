"""Deterministic NG exhaustion runway clock (isolated V0).

This module deliberately keeps direction separate from exhaustion. Family A uses the
frozen 61-dimensional post-state classifier at the legal +60 second boundary and
maps the resulting state to frozen reveal duration baselines. Families B/C remain
low-confidence fallbacks. No future price or realized outcome is consumed here.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

EXPECTED_CLASSIFIER_SHA256 = "698b956f2a9aad4b99ccb9afab916e7219123d10c82408b8d9340137c266ecb9"
A_LEGAL_CONFIRMATION_S = 60.0
SCALES = ("3t", "5t", "8t", "13t")

A_FAST_COLLAPSE = "A-fast-collapse"
A_PERSISTENT = "A-persistent"
A_STATE_PENDING = "A_STATE_PENDING"
A_STATE_UNAVAILABLE = "A_STATE_UNAVAILABLE"
B_UNRESOLVED = "B_UNRESOLVED"
C_SCALE_TRANSITION_PROVISIONAL = "C_SCALE_TRANSITION_PROVISIONAL"

# Frozen reveal operational duration baselines. Do not retune to held-out medians.
FROZEN_REVEAL_BASELINES_S: dict[str, dict[str, float]] = {
    A_FAST_COLLAPSE: {"3t": 358.0, "5t": 993.0, "8t": 1802.0, "13t": 4386.0},
    A_PERSISTENT: {"3t": 700.0, "5t": 1802.0, "8t": 3455.0, "13t": 6836.0},
    B_UNRESOLVED: {"3t": 353.0, "5t": 995.0, "8t": 1615.0, "13t": 4543.0},
    C_SCALE_TRANSITION_PROVISIONAL: {"3t": 377.0, "5t": 1159.0, "8t": 1713.0, "13t": 4320.0},
}

# Operational confidence policy, not calibrated probabilities. Values are explicit so
# there are no hidden weights. Microstructure may change confidence only, never seconds.
BASE_CONFIDENCE = {
    A_FAST_COLLAPSE: 0.70,
    A_PERSISTENT: 0.70,
    B_UNRESOLVED: 0.25,
    C_SCALE_TRANSITION_PROVISIONAL: 0.35,
}
MICROSTRUCTURE_CONFIDENCE_MODIFIER = {
    "same_side": 0.10,
    "mixed": 0.00,
    "opposite": -0.15,
    "unavailable": -0.05,
}

EXPECTED_HELDOUT_A_COUNTS = {A_FAST_COLLAPSE: 831, A_PERSISTENT: 785}
EXPECTED_HELDOUT_DAYS = ("20250717", "20250923", "20250930", "20251001")


class RunwayClockError(RuntimeError):
    """Base contract error for the isolated clock."""


class ClassifierIntegrityError(RunwayClockError):
    """Raised when the frozen classifier bytes or schema drift."""


class ClassifierInputError(RunwayClockError):
    """Raised when a legal A classifier window cannot be evaluated."""


class ReplayValidationError(RunwayClockError):
    """Raised when committed held-out validation facts drift."""


@dataclass(frozen=True)
class ClassificationResult:
    post_state: str
    normalized_curve: tuple[float, ...]
    distances: tuple[float, float]
    raw_cluster_index: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "post_state": self.post_state,
            "normalized_curve": list(self.normalized_curve),
            "distances": list(self.distances),
            "raw_cluster_index": self.raw_cluster_index,
        }


@dataclass(frozen=True)
class FrozenAClassifier:
    """Byte-locked wrapper around the recovered pre-blind A classifier."""

    artifact: Mapping[str, Any]
    artifact_sha256: str
    centroids: tuple[tuple[float, ...], tuple[float, ...]]
    labels_by_cluster: tuple[str, str]

    @classmethod
    def load(cls, path: str | Path) -> "FrozenAClassifier":
        raw = Path(path).read_bytes()
        digest = sha256(raw).hexdigest()
        if digest != EXPECTED_CLASSIFIER_SHA256:
            raise ClassifierIntegrityError(
                f"classifier SHA256 drift: expected {EXPECTED_CLASSIFIER_SHA256}, got {digest}"
            )
        try:
            artifact = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ClassifierIntegrityError(f"classifier JSON invalid: {exc}") from exc

        contract = artifact.get("input_contract", {})
        if contract.get("feature_count") != 61:
            raise ClassifierIntegrityError("classifier feature_count must be exactly 61")
        if contract.get("slice") != "[60:]":
            raise ClassifierIntegrityError("classifier slice drift: expected [60:]")
        if contract.get("additional_scaling") is not None:
            raise ClassifierIntegrityError("classifier additional scaling must remain null")
        if contract.get("custom_threshold") is not None:
            raise ClassifierIntegrityError("classifier custom threshold must remain null")
        if contract.get("custom_tie_rule") is not None:
            raise ClassifierIntegrityError("classifier custom tie rule must remain null")

        raw_centroids = artifact.get("centroids_raw_cluster_order")
        if not isinstance(raw_centroids, list) or len(raw_centroids) != 2:
            raise ClassifierIntegrityError("classifier must contain exactly two centroids")
        centroids = tuple(tuple(float(x) for x in row) for row in raw_centroids)
        if any(len(row) != 61 for row in centroids):
            raise ClassifierIntegrityError("each classifier centroid must have 61 dimensions")

        mapping = artifact.get("cluster_mapping", {})
        expected_mapping = {A_FAST_COLLAPSE: 0, A_PERSISTENT: 1}
        labels: list[str | None] = [None, None]
        for label, index in expected_mapping.items():
            entry = mapping.get(label, {})
            if entry.get("raw_cluster_index") != index:
                raise ClassifierIntegrityError(f"cluster mapping drift for {label}")
            labels[index] = label
        if tuple(labels) != (A_FAST_COLLAPSE, A_PERSISTENT):
            raise ClassifierIntegrityError("cluster label order drift")

        return cls(
            artifact=artifact,
            artifact_sha256=digest,
            centroids=(centroids[0], centroids[1]),
            labels_by_cluster=(A_FAST_COLLAPSE, A_PERSISTENT),
        )

    @staticmethod
    def normalize_t0_to_plus60(values: Sequence[float]) -> tuple[float, ...]:
        if len(values) != 61:
            raise ClassifierInputError(f"expected 61 t=0..+60 samples, got {len(values)}")
        try:
            samples = tuple(float(x) for x in values)
        except (TypeError, ValueError) as exc:
            raise ClassifierInputError("classifier samples must be numeric") from exc
        if not all(math.isfinite(x) for x in samples):
            raise ClassifierInputError("classifier samples must be finite")
        t0 = samples[0]
        if t0 == 0.0:
            raise ClassifierInputError("cannot normalize A classifier window when t=0 is zero")
        normalized = tuple(x / t0 for x in samples)
        if not all(math.isfinite(x) for x in normalized):
            raise ClassifierInputError("normalized classifier samples must be finite")
        return normalized

    def classify_t0_to_plus60(self, values: Sequence[float]) -> ClassificationResult:
        normalized = self.normalize_t0_to_plus60(values)
        distances = (
            math.dist(normalized, self.centroids[0]),
            math.dist(normalized, self.centroids[1]),
        )
        # sklearn KMeans.predict resolves an exact argmin tie to the first cluster.
        cluster = 0 if distances[0] <= distances[1] else 1
        return ClassificationResult(
            post_state=self.labels_by_cluster[cluster],
            normalized_curve=normalized,
            distances=distances,
            raw_cluster_index=cluster,
        )

    def classify_full_minus60_to_plus60(self, values: Sequence[float]) -> ClassificationResult:
        if len(values) != 121:
            raise ClassifierInputError(f"expected 121 t=-60..+60 samples, got {len(values)}")
        return self.classify_t0_to_plus60(values[60:])


def _clip_confidence(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 6)


def _make_runways(
    post_state: str,
    elapsed_s: float,
    microstructure: str,
) -> dict[str, dict[str, Any]]:
    baselines = FROZEN_REVEAL_BASELINES_S[post_state]
    base_confidence = BASE_CONFIDENCE[post_state]
    modifier = MICROSTRUCTURE_CONFIDENCE_MODIFIER[microstructure]
    confidence = _clip_confidence(base_confidence + modifier)
    result: dict[str, dict[str, Any]] = {}
    for scale in SCALES:
        baseline = float(baselines[scale])
        remaining = max(0.0, baseline - elapsed_s)
        result[scale] = {
            "baseline_total_s": baseline,
            "elapsed_since_t0_s": elapsed_s,
            "remaining_s": remaining,
            "remaining_fraction": 0.0 if baseline == 0 else remaining / baseline,
            "confidence": confidence,
            "confidence_kind": "explicit_operational_policy_not_calibrated_probability",
            "basis": f"frozen_reveal_{post_state}",
            "baseline_exhausted": remaining == 0.0,
        }
    return result


class ExhaustionRunwayClock:
    """Finite, deterministic V0 clock. It never reads future price."""

    def __init__(self, classifier: FrozenAClassifier):
        self.classifier = classifier

    @classmethod
    def from_classifier_path(cls, path: str | Path) -> "ExhaustionRunwayClock":
        return cls(FrozenAClassifier.load(path))

    def update(
        self,
        *,
        event_id: str,
        session_id: str,
        t0: str | float | int,
        family: str,
        elapsed_s: float,
        a_t0_to_plus60: Sequence[float] | None = None,
        microstructure: str = "unavailable",
        data_flags: Mapping[str, bool] | None = None,
    ) -> dict[str, Any]:
        if family not in {"A", "B", "C"}:
            raise RunwayClockError(f"family must be A, B, or C; got {family!r}")
        elapsed = float(elapsed_s)
        if not math.isfinite(elapsed) or elapsed < 0.0:
            raise RunwayClockError("elapsed_s must be finite and non-negative")
        if microstructure not in MICROSTRUCTURE_CONFIDENCE_MODIFIER:
            raise RunwayClockError(
                "microstructure must be same_side, mixed, opposite, or unavailable"
            )

        flags = dict(data_flags or {})
        data_gaps: list[str] = [name for name, available in sorted(flags.items()) if not available]
        reasons: list[str] = []
        classification: ClassificationResult | None = None
        confirmed_at_s: float | None = None

        if family == "A":
            if elapsed < A_LEGAL_CONFIRMATION_S:
                post_state = A_STATE_PENDING
                reasons.append("A_STATE_LEGAL_GATE_PRE60")
            elif a_t0_to_plus60 is None:
                post_state = A_STATE_UNAVAILABLE
                data_gaps.append("a_classifier_window")
                reasons.append("A_CLASSIFIER_INPUT_UNAVAILABLE")
            else:
                try:
                    classification = self.classifier.classify_t0_to_plus60(a_t0_to_plus60)
                except ClassifierInputError as exc:
                    post_state = A_STATE_UNAVAILABLE
                    data_gaps.append("a_classifier_window_invalid")
                    reasons.append(f"A_CLASSIFIER_INPUT_INVALID:{exc}")
                else:
                    post_state = classification.post_state
                    confirmed_at_s = A_LEGAL_CONFIRMATION_S
                    reasons.append("A_STATE_FROZEN_61D_CLASSIFIER")
        elif family == "B":
            post_state = B_UNRESOLVED
            reasons.append("B_UNRESOLVED_LOW_CONFIDENCE_FALLBACK")
        else:
            post_state = C_SCALE_TRANSITION_PROVISIONAL
            reasons.append("C_PROVISIONAL_SCALE_TRANSITION_FALLBACK")

        if microstructure == "same_side":
            reasons.append("MICROSTRUCTURE_CONFIDENCE_UP")
        elif microstructure == "opposite":
            reasons.append("MICROSTRUCTURE_CONFIDENCE_DOWN")
        elif microstructure == "mixed":
            reasons.append("MICROSTRUCTURE_CONFIDENCE_NEUTRAL")
        else:
            reasons.append("MICROSTRUCTURE_UNAVAILABLE")
            if "microstructure" not in data_gaps:
                data_gaps.append("microstructure")

        runway_capable = post_state in FROZEN_REVEAL_BASELINES_S
        runways = _make_runways(post_state, elapsed, microstructure) if runway_capable else {
            scale: {
                "baseline_total_s": None,
                "elapsed_since_t0_s": elapsed,
                "remaining_s": None,
                "remaining_fraction": None,
                "confidence": 0.0,
                "confidence_kind": "unavailable_until_legal_state",
                "basis": post_state,
                "baseline_exhausted": None,
            }
            for scale in SCALES
        }

        return {
            "event_id": str(event_id),
            "session_id": str(session_id),
            "t0": t0,
            "family": family,
            "post_state": post_state,
            "state_confirmed": post_state in {A_FAST_COLLAPSE, A_PERSISTENT},
            "confirmed_at_s": confirmed_at_s,
            "elapsed_s": elapsed,
            "classifier_sha256": self.classifier.artifact_sha256,
            "classifier_distances": list(classification.distances) if classification else None,
            "normalized_exhaustion_curve": list(classification.normalized_curve) if classification else None,
            "runways": runways,
            "microstructure_confirmation": microstructure,
            "confidence_modifier": MICROSTRUCTURE_CONFIDENCE_MODIFIER[microstructure],
            "data_gap_status": sorted(set(data_gaps)),
            "falsifier_status": "NOT_EVALUATED_WITHOUT_REALIZED_ENDPOINT",
            "reason_codes": reasons,
            "future_price_accessed": False,
        }


def validate_committed_replay_metrics(metrics_or_path: Mapping[str, Any] | str | Path) -> dict[str, Any]:
    """Validate frozen held-out facts without rerunning or retuning the blind experiment."""
    if isinstance(metrics_or_path, Mapping):
        metrics = dict(metrics_or_path)
    else:
        metrics = json.loads(Path(metrics_or_path).read_text(encoding="utf-8"))

    def require(condition: bool, message: str) -> None:
        if not condition:
            raise ReplayValidationError(message)

    require(metrics.get("frozen_a_classifier_sha256") == EXPECTED_CLASSIFIER_SHA256, "held-out classifier SHA drift")
    require(metrics.get("a_classifier_refit_after_reveal") is False, "held-out artifact says classifier was refit")
    require(metrics.get("freeze_verified_before_actual_reveal") is True, "blind freeze verification drift")
    require(metrics.get("frankie_brain_or_schema_mutated") is False, "blind artifact reports permanent Frankie mutation")

    groups = metrics.get("by_group", {})
    for state, expected_n in EXPECTED_HELDOUT_A_COUNTS.items():
        actual_n = groups.get(state, {}).get("n")
        require(actual_n == expected_n, f"held-out {state} count drift: expected {expected_n}, got {actual_n}")

    ordering = metrics.get("a_state_runway_ordering", {})
    for scale in SCALES:
        scale_data = ordering.get(scale, {})
        require(scale_data.get("days_pass") == 4, f"{scale} held-out days_pass must be 4")
        require(scale_data.get("persistent_gt_fast") is True, f"{scale} aggregate persistent>fast ordering failed")
        by_day = scale_data.get("by_day", {})
        require(set(by_day) == set(EXPECTED_HELDOUT_DAYS), f"{scale} held-out day set drift")
        for day in EXPECTED_HELDOUT_DAYS:
            row = by_day.get(day, {})
            require(row.get("persistent_gt_fast") is True, f"{scale} {day} ordering flag failed")
            p = row.get("persistent_median_s")
            f = row.get("fast_median_s")
            require(isinstance(p, (int, float)) and isinstance(f, (int, float)) and p > f, f"{scale} {day} persistent median must exceed fast median")

    duration = metrics.get("duration_by_group_scale", {})
    for state in (A_FAST_COLLAPSE, A_PERSISTENT):
        for scale in SCALES:
            predicted = duration.get(state, {}).get(scale, {}).get("predicted_duration_median_s")
            expected = FROZEN_REVEAL_BASELINES_S[state][scale]
            require(predicted == expected, f"{state} {scale} blind baseline drift: expected {expected}, got {predicted}")

    return {
        "status": "PASS",
        "classifier_sha256": EXPECTED_CLASSIFIER_SHA256,
        "heldout_a_counts": dict(EXPECTED_HELDOUT_A_COUNTS),
        "heldout_a_total": sum(EXPECTED_HELDOUT_A_COUNTS.values()),
        "scales": list(SCALES),
        "days": list(EXPECTED_HELDOUT_DAYS),
        "persistent_gt_fast_all_scales_all_days": True,
        "frozen_reveal_baselines_preserved": True,
        "blind_experiment_rerun": False,
        "future_price_accessed_by_clock": False,
    }
