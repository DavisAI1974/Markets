"""Synthetic confidence contracts; no fitted or market-performance claims."""
from dataclasses import replace
import math

import pytest

from forecast_confidence import (
    CalibrationArtifact, ConfidenceContext, ForecastErrorPolicy,
    evaluate_joint_event, resolve_confidence,
)


def policy():
    return ForecastErrorPolicy(10.0, 20.0, 5.0, 'a' * 64, 'b' * 64)


def context():
    return ConfidenceContext('c' * 64, 'd' * 64, 'NG:preopen:full', 100)


def calibration():
    return CalibrationArtifact('c' * 64, 'd' * 64, policy().digest,
                               'e' * 64, ('NG:preopen:full',), 0, 200, 1.0, 0.0)


def resolve(logit, artifact=None, **changes):
    artifact = calibration() if artifact is None else artifact
    args = dict(logit=logit, policy=policy(), context=context(),
                artifact=artifact, trusted_artifact_hash=artifact.digest)
    args.update(changes)
    return resolve_confidence(**args)


@pytest.mark.parametrize('p', [0.1, 0.6, 0.8, 0.99])
def test_probability_is_internal_and_has_no_categorical_label(p):
    result = resolve(math.log(p / (1-p)))
    assert not hasattr(result, 'label')
    assert result.probability == pytest.approx(p)
    assert result.status == 'CALIBRATED'


@pytest.mark.parametrize('logit,probability', [(-1000., 0.), (1000., 1.)])
def test_extreme_finite_logits_are_stable(logit, probability):
    assert resolve(logit).probability == probability


def test_missing_calibration_is_unknown_not_measured_zero():
    result = resolve_confidence(logit=1., policy=policy(), context=context(),
                                artifact=None, trusted_artifact_hash=None)
    assert (result.probability, result.status) == (None, 'UNCALIBRATED')
    assert not hasattr(result, 'label')


@pytest.mark.parametrize('changes,status', [
    ({'trusted_artifact_hash': 'f'*64}, 'UNTRUSTED_CALIBRATION'),
    ({'context': replace(context(), forecast_hash='f'*64)}, 'IDENTITY_MISMATCH'),
    ({'context': replace(context(), scorer_hash='f'*64)}, 'IDENTITY_MISMATCH'),
    ({'policy': replace(policy(), tau_path=6.)}, 'IDENTITY_MISMATCH'),
    ({'context': replace(context(), support_key='NG:postopen:short')}, 'OUT_OF_SUPPORT'),
    ({'context': replace(context(), as_of=200)}, 'EXPIRED_CALIBRATION'),
    ({'context': replace(context(), as_of=-1)}, 'EXPIRED_CALIBRATION'),
    ({'logit': float('nan')}, 'INVALID_SCORE'),
    ({'logit': True}, 'INVALID_SCORE'),
])
def test_invalid_calibration_never_upgrades_confidence(changes, status):
    args = {'logit': 1.}
    args.update(changes)
    result = resolve(**args)
    assert (result.probability, result.status) == (None, status)


@pytest.mark.parametrize('value', [0., -1., float('nan'), float('inf'), True, '5'])
def test_invalid_error_tolerance_rejected(value):
    with pytest.raises(ValueError):
        replace(policy(), tau_path=value)


def test_artifact_hash_covers_every_field():
    original = calibration()
    changes = dict(forecast_hash='1'*64, scorer_hash='2'*64, error_policy_hash='3'*64,
                   acceptance_report_hash='4'*64, support_keys=('OTHER',),
                   valid_from=1, valid_until=201, slope=2., intercept=0.1)
    for name, value in changes.items():
        assert replace(original, **{name: value}).digest != original.digest


def event(**changes):
    args = dict(policy=policy(), forecast_net=100., actual_net=110.,
                forecast_gap=10., actual_gap=12., gap_observed=False,
                predictions=(('q1', 2.), ('q2', 4.)),
                labels=(('q1', 3.), ('q2', 5.)),
                expected_query_ids=('q1', 'q2'),
                label_convention_hash='a'*64, audit_query_hash='b'*64)
    args.update(changes)
    return evaluate_joint_event(**args)


def test_joint_event_reconciles_queries_and_is_order_independent():
    result = event(labels=(('q2', 5.), ('q1', 3.)))
    assert result.success is True
    assert (result.expected_queries, result.scored_queries, result.missing_queries) == (2, 2, 0)


@pytest.mark.parametrize('changes', [dict(actual_net=121.), dict(actual_gap=21.),
                                      dict(labels=(('q1', 8.), ('q2', 5.)))])
def test_each_error_component_can_fail_independently(changes):
    assert event(**changes).success is False


def test_missing_label_is_unscorable_even_when_another_component_fails():
    result = event(actual_net=999., labels=(('q1', None), ('q2', 5.)))
    assert result.success is None
    assert result.status == 'MISSING_LABEL'
    assert result.scored_queries + result.missing_queries == result.expected_queries


@pytest.mark.parametrize('changes', [
    dict(predictions=(('q1', 2.),)),
    dict(labels=(('q1', 3.),)),
    dict(labels=(('q1', 3.), ('q1', 5.))),
    dict(expected_query_ids=('q1', 'q1')),
    dict(expected_query_ids=()),
    dict(label_convention_hash='f'*64),
    dict(audit_query_hash='f'*64),
    dict(predictions=(('q1', float('nan')), ('q2', 4.))),
])
def test_query_omissions_duplicates_and_protocol_drift_rejected(changes):
    with pytest.raises(ValueError):
        event(**changes)


def test_known_gap_requires_matching_certified_value():
    with pytest.raises(ValueError, match='observed gap'):
        event(gap_observed=True)
    assert event(gap_observed=True, actual_gap=10.).success is True


@pytest.mark.parametrize('changes', [dict(actual_net=None), dict(actual_gap=None)])
def test_missing_scalar_label_is_unscorable_and_does_not_change_query_counts(changes):
    result = event(**changes)
    assert result.success is None and result.status == 'MISSING_LABEL'
    assert (result.expected_queries, result.scored_queries, result.missing_queries) == (2, 2, 0)
