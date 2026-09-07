"""Pure §5 gates for BOSS_GRANITE_STRUCTURED_OUTPUT_PLAN_V1.

Consumes 200 supplied paired outputs; it never runs a model or pins an identity.
Callers own source authorization and proof of Oct-1 time-disjoint training and
validation windows. The scope declaration and hash-disjoint inventory checked
here cannot prove chronology, particularly for overlapping source prefixes.
Content diversity is a deterministic format guard, not factual correctness.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
import re
from typing import Iterable

from .granite_output_schema import validate_schema
from .granite_parser import Verdict, parse_json_object, score
from .state_serialization import SerializedState

VALIDATION_SIZE = 200
VALIDATION_SCOPE = '2021-10-01/PROBE_ONLY'


@dataclass(frozen=True)
class DecodeOutput:
    """Final JSON text (thinking already stripped), measured duration and budget."""
    text: str
    decode_seconds: float
    token_budget: int


@dataclass(frozen=True)
class EvaluationPair:
    snapshot: SerializedState
    base: DecodeOutput
    tuned: DecodeOutput


@dataclass(frozen=True)
class ModelMetrics:
    l4_count: int
    l4_rate: float
    snapshot_hash_mismatch_count: int
    snapshot_hash_mismatch_rate: float
    snapshot_hash_unverified_count: int
    schema_valid_count: int
    distinct_content_strings: int
    disposition_counts: tuple[tuple[str, int], ...]
    max_disposition_share: float | None
    total_decode_seconds: float


@dataclass(frozen=True)
class EvaluationReport:
    """Local gates only; a passing report grants no data or promotion authority.

    Disposition shares use schema-valid (L3/L4) output count as denominator.
    Missing/unparseable hash echoes reduce L4 acceptance, but are not counted
    as foreign hashes; they are reported as unverified echoes. Zero observed
    mismatches therefore does not prove zero mismatches among unverified outputs.
    Any parsed object with a present unequal echo counts as
    a mismatch, including objects failing the key-set or schema checks.
    Latency compares total measured decode seconds across equal-size pairs.
    """
    validation_scope: str
    sample_count: int
    token_budget: int
    base: ModelMetrics
    tuned: ModelMetrics
    l4_improvement: float
    latency_ratio: float
    failures: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.failures


def _metrics(pairs: tuple[EvaluationPair, ...], side: str) -> ModelMetrics:
    accepted = mismatched = unverified = valid = 0
    strings: set[str] = set()
    dispositions: Counter[str] = Counter()
    seconds = []
    for pair in pairs:
        output = getattr(pair, side)
        _, verdict = score(output.text, pair.snapshot)
        accepted += verdict is Verdict.L4
        obj = parse_json_object(output.text)
        unverified += obj is None or 'snapshot_hash' not in obj
        if obj is not None:
            mismatched += 'snapshot_hash' in obj and obj['snapshot_hash'] != pair.snapshot.hash
            if validate_schema(obj):
                valid += 1
                strings.update(item['note'] for item in obj['contradictions'])
                strings.update(obj['missing_evidence'])
                dispositions[obj['disposition']] += 1
        seconds.append(output.decode_seconds)
    try:
        total = math.fsum(seconds)
    except OverflowError as exc:
        raise ValueError('aggregate decode time must be finite') from exc
    if not math.isfinite(total):
        raise ValueError('aggregate decode time must be finite')
    return ModelMetrics(
        accepted, accepted / len(pairs), mismatched, mismatched / len(pairs),
        unverified, valid, len(strings), tuple(sorted(dispositions.items())),
        max(dispositions.values()) / valid if valid else None, total,
    )


def evaluate(
    pairs: Iterable[EvaluationPair], *, training_snapshot_hashes: Iterable[str],
    validation_scope: str,
) -> EvaluationReport:
    """Evaluate supplied measurements against all four independent plan gates.

    Invalid evaluation inventories/measurements raise ValueError. Poor generated
    outputs are scored by the shared parser and produce a failed report. Training
    hashes must be explicit and nonempty; this verifies identity disjointness,
    not time disjointness. The fixed token budget must match every observation.
    """
    pairs = tuple(pairs)
    if len(pairs) != VALIDATION_SIZE:
        raise ValueError('evaluation requires exactly 200 paired states')
    if validation_scope != VALIDATION_SCOPE:
        raise ValueError('validation scope must be 2021-10-01/PROBE_ONLY')
    training = frozenset(training_snapshot_hashes)
    if not training or any(
        not isinstance(h, str) or re.fullmatch(r'[0-9a-f]{64}', h) is None
        for h in training
    ):
        raise ValueError('training snapshot hashes must be a nonempty SHA256 inventory')
    identities = [pair.snapshot.hash for pair in pairs]
    if len(set(identities)) != VALIDATION_SIZE:
        raise ValueError('validation states must have 200 unique identities')
    if training.intersection(identities):
        raise ValueError('validation states overlap declared training identities')
    budget = pairs[0].base.token_budget
    for pair in pairs:
        for output in (pair.base, pair.tuned):
            if type(output.token_budget) is not int or output.token_budget <= 0 or output.token_budget != budget:
                raise ValueError('every decode must use the same positive integer token budget')
            if type(output.decode_seconds) not in (int, float) or not math.isfinite(output.decode_seconds) or output.decode_seconds <= 0:
                raise ValueError('decode seconds must be finite and positive')
            if not isinstance(output.text, str):
                raise ValueError('decode text must be a string')
    base, tuned = _metrics(pairs, 'base'), _metrics(pairs, 'tuned')
    failures = []
    # Count comparisons preserve exact inclusive 10%, 95%, 60%, 90% boundaries.
    if tuned.l4_count - base.l4_count < 20 and tuned.l4_count < 190:
        failures.append('acceptance')
    if tuned.snapshot_hash_mismatch_count:
        failures.append('snapshot_hash')
    if 5 * tuned.distinct_content_strings < 3 * base.distinct_content_strings:
        failures.append('content_diversity')
    if not tuned.schema_valid_count or 10 * max(dict(tuned.disposition_counts).values()) > 9 * tuned.schema_valid_count:
        failures.append('disposition_collapse')
    if tuned.total_decode_seconds > 1.2 * base.total_decode_seconds:
        failures.append('latency')
    return EvaluationReport(
        validation_scope, len(pairs), budget, base, tuned,
        (tuned.l4_count - base.l4_count) / len(pairs),
        tuned.total_decode_seconds / base.total_decode_seconds, tuple(failures),
    )
