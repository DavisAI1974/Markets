"""Explicit cadence covers every registered horizon; this is not a live timer."""
from dataclasses import replace

import pytest

from forecast_refresh import ForecastRefreshLoop, RefreshPolicy
from rolling_forecast import ForecastTarget, RollingForecastBook
from test_rolling_forecast import candidate


def policy():
    return RefreshPolicy(((30, 1), (100, 5), (1000, 10)))


def producer(**kwargs):
    return (candidate(score=None, **kwargs),)


def publication_count(book):
    return sum(e['kind'] == 'BOSS_ROLLING_FORECAST_V1' for e in book.journal.entries())


def update(loop, as_of, **changes):
    args = dict(as_of=as_of, source_as_of=as_of, source_hash='a'*64,
                arm_hash='b'*64, generation_hash='f'*64, produce=producer)
    args.update(changes)
    return loop.update(**args)


def test_every_horizon_updates_at_its_declared_cadence(tmp_path):
    book = RollingForecastBook(tmp_path/'forecast.sqlite', create=True)
    targets = tuple(ForecastTarget('NG', f'close-{t}', t) for t in (120, 150, 300))
    loop = ForecastRefreshLoop(book, targets, policy())
    first = update(loop, 100)
    assert len(first) == 3
    assert len(update(loop, 101)) == 1
    assert len(update(loop, 105)) == 2
    assert len(update(loop, 110)) == 3
    assert all(book.latest(t, arm_hash='b'*64).selected.as_of == 110 for t in targets)
    assert all(p.refresh_policy_hash == policy().digest for p in first)
    book.close()


def test_material_data_updates_all_unmatured_targets(tmp_path):
    book = RollingForecastBook(tmp_path/'forecast.sqlite', create=True)
    targets = tuple(ForecastTarget('NG', str(t), t) for t in (101, 150, 300))
    loop = ForecastRefreshLoop(book, targets, policy())
    update(loop, 100)
    revised = update(loop, 101, material=True)
    assert {p.selected.target.target_ns for p in revised} == {150, 300}
    assert book.latest(targets[0], arm_hash='b'*64).revision == 1
    book.close()


def test_retry_returns_committed_revisions_without_regeneration(tmp_path):
    book = RollingForecastBook(tmp_path/'forecast.sqlite', create=True)
    loop = ForecastRefreshLoop(book, (ForecastTarget('NG', 'close', 300),), policy())
    first = update(loop, 100)
    def must_not_run(**kwargs):
        raise AssertionError('same completed update must not generate again')
    assert update(loop, 100, produce=must_not_run) == first
    with pytest.raises(ValueError, match='same as-of'):
        update(loop, 100, source_hash='f'*64)
    with pytest.raises(ValueError, match='same as-of'):
        update(loop, 100, generation_hash='1'*64)
    book.close()


def test_partial_batch_retry_cannot_mix_generation_versions(tmp_path):
    book = RollingForecastBook(tmp_path/'forecast.sqlite', create=True)
    targets = (ForecastTarget('NG', 'near', 120), ForecastTarget('NG', 'far', 300))
    loop = ForecastRefreshLoop(book, targets, policy())
    def partial(**kwargs):
        if kwargs['target'].target_id == 'far':
            raise RuntimeError('synthetic second-target generation failure')
        return producer(**kwargs)
    with pytest.raises(RuntimeError):
        update(loop, 100, produce=partial)
    assert publication_count(book) == 1
    with pytest.raises(ValueError, match='same as-of'):
        update(loop, 100, generation_hash='1'*64)
    completed = update(loop, 100)
    assert len(completed) == 2 and publication_count(book) == 2
    book.close()


def test_generated_candidate_must_match_requested_state_and_target(tmp_path):
    book = RollingForecastBook(tmp_path/'forecast.sqlite', create=True)
    loop = ForecastRefreshLoop(book, (ForecastTarget('NG', 'close', 300),), policy())
    def wrong(**kwargs):
        return (candidate(score=None, **dict(kwargs, as_of=kwargs['as_of']-1)),)
    with pytest.raises(ValueError):
        update(loop, 100, produce=wrong)
    assert publication_count(book) == 0
    book.close()


@pytest.mark.parametrize('bands', [(), ((100, 0),), ((100, 10), (30, 1)),
                                  ((30, 10), (100, 1)), ((True, 1),),
                                  ((30, 1.0),), ((30, 1), (30, 5))])
def test_invalid_or_reversed_cadence_policy_rejected(bands):
    with pytest.raises(ValueError):
        RefreshPolicy(bands)


def test_uncovered_horizon_is_explicit_error_before_any_publication(tmp_path):
    book = RollingForecastBook(tmp_path/'forecast.sqlite', create=True)
    targets = (ForecastTarget('NG', 'near', 120), ForecastTarget('NG', 'far', 2000))
    loop = ForecastRefreshLoop(book, targets, policy())
    with pytest.raises(ValueError, match='horizon'):
        update(loop, 100)
    assert book.journal.count == 0
    book.close()


def test_partial_material_refresh_binds_mode_and_complete_target_registry(tmp_path):
    book = RollingForecastBook(tmp_path/'forecast.sqlite', create=True)
    targets = (ForecastTarget('NG', 'one', 500), ForecastTarget('NG', 'two', 600))
    loop = ForecastRefreshLoop(book, targets, policy())
    update(loop, 100)
    calls = []
    def partial(**kwargs):
        calls.append(kwargs['target'].target_id)
        if kwargs['target'].target_id == 'two':
            raise RuntimeError('second target fails')
        return producer(**kwargs)
    with pytest.raises(RuntimeError):
        update(loop, 101, material=True, produce=partial)
    with pytest.raises(ValueError, match='refresh intent'):
        update(loop, 101, material=False)
    changed = ForecastRefreshLoop(book, targets[:1], policy())
    with pytest.raises(ValueError, match='refresh intent'):
        update(changed, 101, material=True)
    retry_calls = []
    def finish(**kwargs):
        retry_calls.append(kwargs['target'].target_id)
        return producer(**kwargs)
    assert len(update(loop, 101, material=True, produce=finish)) == 2
    assert retry_calls == ['two']
    assert publication_count(book) == 4
    book.close()


def test_first_generation_failure_binds_identity_across_restart(tmp_path):
    path = tmp_path/'forecast.sqlite'
    book = RollingForecastBook(path, create=True)
    targets = (ForecastTarget('NG', 'close', 300),)
    loop = ForecastRefreshLoop(book, targets, policy())
    def fail(**kwargs):
        raise RuntimeError('first forward fails')
    with pytest.raises(RuntimeError):
        update(loop, 100, produce=fail)
    checkpoint = book.checkpoint()
    book.close()
    restored = RollingForecastBook(path, checkpoint=checkpoint)
    retry = ForecastRefreshLoop(restored, targets, policy())
    with pytest.raises(ValueError, match='refresh intent'):
        update(retry, 100, generation_hash='1'*64)
    assert len(update(retry, 100)) == 1
    restored.close()
