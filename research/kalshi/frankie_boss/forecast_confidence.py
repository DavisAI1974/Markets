"""Pure forecast-confidence rules. No fitting, promotion, or trade authority.

The caller supplies a separately approved artifact digest and a verified frozen
query plan. A digest proves identity, not calibration quality: the G15 acceptance
report and its approval must be established outside this inference module.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

try:
    from .forecast_contract import HashedContract, finite_number, sha256_digest, unique_names
except ImportError:
    from forecast_contract import HashedContract, finite_number, sha256_digest, unique_names

@dataclass(frozen=True, slots=True)
class ForecastErrorPolicy(HashedContract):
    tau_gap: float
    tau_net: float
    tau_path: float
    label_convention_hash: str
    audit_query_hash: str

    def __post_init__(self):
        for name in ('tau_gap', 'tau_net', 'tau_path'):
            finite_number(getattr(self, name), name)
            if getattr(self, name) <= 0:
                raise ValueError(f'{name} must be positive')
        sha256_digest(self.label_convention_hash, 'label_convention_hash')
        sha256_digest(self.audit_query_hash, 'audit_query_hash')


@dataclass(frozen=True, slots=True)
class ConfidenceContext:
    forecast_hash: str
    scorer_hash: str
    support_key: str
    as_of: int

    def __post_init__(self):
        sha256_digest(self.forecast_hash, 'forecast_hash')
        sha256_digest(self.scorer_hash, 'scorer_hash')
        unique_names((self.support_key,), 'support_key')
        if type(self.as_of) is not int:
            raise ValueError('as_of must be integer nanoseconds')


@dataclass(frozen=True, slots=True)
class CalibrationArtifact(HashedContract):
    forecast_hash: str
    scorer_hash: str
    error_policy_hash: str
    acceptance_report_hash: str
    support_keys: tuple[str, ...]
    valid_from: int
    valid_until: int
    slope: float
    intercept: float

    def __post_init__(self):
        for name in ('forecast_hash', 'scorer_hash', 'error_policy_hash', 'acceptance_report_hash'):
            sha256_digest(getattr(self, name), name)
        unique_names(self.support_keys, 'support_keys')
        if (type(self.valid_from) is not int or type(self.valid_until) is not int
                or self.valid_from >= self.valid_until):
            raise ValueError('calibration requires a nonempty integer validity interval')
        finite_number(self.slope, 'slope')
        finite_number(self.intercept, 'intercept')


@dataclass(frozen=True, slots=True)
class ConfidenceResult:
    probability: float | None
    status: str
    artifact_hash: str | None


def resolve_confidence(*, logit, policy, context, artifact, trusted_artifact_hash):
    """Resolve an internal probability; never impose a publication threshold.

Validity is [valid_from, valid_until). support_key must encode the approved
instrument, phase, horizon and quality stratum, using the acceptance report's
closed registry. This function does not infer a support key from arbitrary input.
"""
    if not isinstance(policy, ForecastErrorPolicy) or not isinstance(context, ConfidenceContext):
        raise ValueError('typed error policy and confidence context required')
    digest = artifact.digest if isinstance(artifact, CalibrationArtifact) else None

    def unavailable(status):
        return ConfidenceResult(None, status, digest)

    if artifact is None:
        return unavailable('UNCALIBRATED')
    if not isinstance(artifact, CalibrationArtifact) or digest != trusted_artifact_hash:
        return unavailable('UNTRUSTED_CALIBRATION')
    if (artifact.forecast_hash != context.forecast_hash or
            artifact.scorer_hash != context.scorer_hash or
            artifact.error_policy_hash != policy.digest):
        return unavailable('IDENTITY_MISMATCH')
    if not artifact.valid_from <= context.as_of < artifact.valid_until:
        return unavailable('EXPIRED_CALIBRATION')
    if context.support_key not in artifact.support_keys:
        return unavailable('OUT_OF_SUPPORT')
    try:
        finite_number(logit, 'logit')
        score = artifact.slope * logit + artifact.intercept
        finite_number(score, 'calibrated logit')
    except (ValueError, OverflowError):
        return unavailable('INVALID_SCORE')
    # Avoid exp overflow without clipping the calibrated probability.
    if score >= 0:
        probability = 1. / (1. + math.exp(-score))
    else:
        exp_score = math.exp(score)
        probability = exp_score / (1. + exp_score)
    return ConfidenceResult(probability, 'CALIBRATED', digest)


@dataclass(frozen=True, slots=True)
class JointEventResult:
    success: bool | None
    status: str
    expected_queries: int
    scored_queries: int
    missing_queries: int
    gap_error: float | None
    net_error: float | None
    max_path_error: float | None


def _query_values(rows, expected_ids, *, allow_missing):
    if type(rows) is not tuple:
        raise ValueError('query values must be an immutable tuple')
    values = {}
    for pair in rows:
        if type(pair) is not tuple or len(pair) != 2:
            raise ValueError('queries must be (id, value) pairs')
        name, value = pair
        if type(name) is not str or name in values:
            raise ValueError('duplicate or invalid query identifier')
        if not (allow_missing and value is None):
            finite_number(value, name)
        values[name] = value
    if set(values) != set(expected_ids):
        raise ValueError('queries differ from frozen expected query plan')
    return values


def evaluate_joint_event(*, policy, forecast_net, actual_net, forecast_gap,
                         actual_gap, gap_observed, predictions, labels,
                         expected_query_ids, label_convention_hash, audit_query_hash):
    """Grade one frozen forecast against all declared future query labels.

Expected ids come from the separately verified pre-reveal lock. None explicitly
records a missing label; deleting its row is a contract error. Label provenance,
query times and known/future classification must be checked by the lock consumer.
"""
    if not isinstance(policy, ForecastErrorPolicy):
        raise ValueError('typed error policy required')
    if (label_convention_hash != policy.label_convention_hash or
            audit_query_hash != policy.audit_query_hash):
        raise ValueError('label or query protocol differs from error policy')
    if type(gap_observed) is not bool:
        raise ValueError('gap_observed must be bool')
    unique_names(expected_query_ids, 'expected_query_ids')
    for name, value in (('forecast_net', forecast_net), ('forecast_gap', forecast_gap)):
        finite_number(value, name)
    for name, value in (('actual_net', actual_net), ('actual_gap', actual_gap)):
        if value is not None:
            finite_number(value, name)
    if gap_observed and (actual_gap is None or actual_gap != forecast_gap):
        raise ValueError('observed gap must equal its certified label')
    predicted = _query_values(predictions, expected_query_ids, allow_missing=False)
    actual = _query_values(labels, expected_query_ids, allow_missing=True)
    errors = [abs(predicted[k] - actual[k]) for k in expected_query_ids if actual[k] is not None]
    missing = len(expected_query_ids) - len(errors)
    gap_error = None if actual_gap is None else abs(forecast_gap - actual_gap)
    net_error = None if actual_net is None else abs(forecast_net - actual_net)
    max_error = max(errors) if errors else None
    complete = missing == 0 and gap_error is not None and net_error is not None
    success = (net_error <= policy.tau_net and gap_error <= policy.tau_gap and
               max_error <= policy.tau_path) if complete else None
    return JointEventResult(success, 'SCORED' if complete else 'MISSING_LABEL',
                            len(expected_query_ids), len(errors), missing,
                            gap_error, net_error, max_error)
