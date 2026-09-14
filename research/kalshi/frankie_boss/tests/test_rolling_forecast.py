"""Selection and rolling revision mechanics, using synthetic forecast artifacts."""
from dataclasses import replace
import sqlite3

import pytest

from rolling_forecast import ForecastCandidate, ForecastTarget, RollingForecastBook, select_candidate


def candidate(name='a', score=0.1, **changes):
    args = dict(candidate_id=name, target=ForecastTarget('NG', 'session-close', 1000),
                as_of=100, source_as_of=90, source_hash='a'*64, arm_hash='b'*64,
                model_hash='c'*64, forecast_artifact=b'synthetic complete forecast',
                score=score, ranker_hash='d'*64 if score is not None else None,
                ranking_policy_hash='e'*64 if score is not None else None)
    args.update(changes)
    return ForecastCandidate(**args)


def test_sole_candidate_publishes_without_confidence_or_calibration():
    item = candidate(score=None)
    assert select_candidate((item,)) == item


def test_highest_relative_score_wins_without_absolute_threshold():
    low, best = candidate('low', -1000.), candidate('best', -900.)
    assert select_candidate((low, best)) == best


def test_tie_break_is_stable_under_candidate_order():
    a, b = candidate('a'), candidate('b')
    assert select_candidate((a, b)) == select_candidate((b, a)) == a


@pytest.mark.parametrize('changes', [
    dict(target=ForecastTarget('NG', 'other-close', 1000)),
    dict(as_of=101), dict(source_as_of=91), dict(source_hash='f'*64),
    dict(arm_hash='f'*64), dict(ranker_hash='f'*64), dict(ranking_policy_hash='f'*64),
    dict(score=None, ranker_hash=None, ranking_policy_hash=None),
])
def test_noncomparable_candidates_are_not_ranked(changes):
    with pytest.raises(ValueError):
        select_candidate((candidate('a'), candidate('b', **changes)))


def test_duplicate_and_empty_candidate_sets_rejected():
    with pytest.raises(ValueError):
        select_candidate(())
    with pytest.raises(ValueError):
        select_candidate((candidate(), candidate()))


@pytest.mark.parametrize('changes', [
    dict(source_as_of=101), dict(as_of=1000), dict(score=True),
    dict(score=float('nan')), dict(score=float('inf')), dict(forecast_artifact=b''),
    dict(forecast_artifact=bytearray(b'mutable')), dict(ranker_hash=None),
])
def test_bad_artifact_scores_and_future_sources_rejected(changes):
    with pytest.raises(ValueError):
        candidate(**changes)


def test_revisions_keep_target_and_all_prior_candidates(tmp_path):
    book = RollingForecastBook(tmp_path/'forecasts.sqlite', create=True)
    a, b = candidate('a', 0.2), candidate('b', 0.4)
    first = book.publish((a, b))
    revised = replace(a, as_of=200, source_as_of=190, source_hash='f'*64,
                      model_hash='1'*64, forecast_artifact=b'revised forecast', score=0.3)
    second = book.publish((revised,))
    assert first.selected == b
    assert second.selected == revised
    assert first.revision == 1 and second.revision == 2
    assert second.previous_hash == first.receipt_hash
    assert first.selected.target == second.selected.target
    assert first.remaining_ns == 900 and second.remaining_ns == 800
    rows = list(book.journal.entries())
    assert len(rows) == 2
    assert len(rows[0]['payload']['candidates']) == 2
    assert rows[0]['payload']['candidates'][0]['forecast_artifact'] == a.forecast_artifact
    assert book.latest(a.target, arm_hash=a.arm_hash) == second
    book.close()


def test_all_intermediate_horizons_can_revise(tmp_path):
    book = RollingForecastBook(tmp_path/'forecasts.sqlite', create=True)
    for horizon in (10, 20, 50, 100, 200, 500, 1000):
        target = ForecastTarget('NG', f'target-{horizon}', 100+horizon)
        first = candidate(target=target)
        book.publish((first,))
        second = replace(first, as_of=101, source_as_of=101)
        assert book.publish((second,)).remaining_ns == horizon-1
    assert book.journal.count == 14
    book.close()


def test_same_update_retry_is_idempotent_but_changed_input_rejected(tmp_path):
    book = RollingForecastBook(tmp_path/'forecasts.sqlite', create=True)
    a, b = candidate('a'), candidate('b')
    first = book.publish((a, b))
    assert book.publish((b, a)) == first
    assert book.journal.count == 1
    with pytest.raises(ValueError, match='same as-of'):
        book.publish((replace(a, score=0.9), b))
    with pytest.raises(ValueError, match='older'):
        book.publish((replace(a, as_of=99),))
    book.close()


def test_restart_verifies_trusted_checkpoint_and_retains_old_revision(tmp_path):
    path = tmp_path/'forecasts.sqlite'
    book = RollingForecastBook(path, create=True)
    a = candidate()
    first = book.publish((a,))
    checkpoint = book.checkpoint()
    book.close()
    restored = RollingForecastBook(path, checkpoint=checkpoint)
    assert restored.publish((a,)) == first
    assert restored.publish((replace(a, as_of=200),)).previous_hash == first.receipt_hash
    restored.close()
    with pytest.raises(ValueError, match='checkpoint'):
        RollingForecastBook(path, checkpoint=checkpoint)


def test_history_cannot_be_updated_or_deleted(tmp_path):
    book = RollingForecastBook(tmp_path/'forecasts.sqlite', create=True)
    book.publish((candidate(),))
    for operation in ('DELETE FROM entries', "UPDATE entries SET kind='REPLACED'"):
        with pytest.raises(sqlite3.IntegrityError, match='append only'):
            book.journal.connection.execute(operation)
    book.close()


def test_revision_cannot_move_an_existing_target_or_regress_source_time(tmp_path):
    book = RollingForecastBook(tmp_path/'forecasts.sqlite', create=True)
    first = candidate()
    book.publish((first,))
    with pytest.raises(ValueError, match='target'):
        book.publish((replace(first, as_of=200, target=replace(first.target, target_ns=1001)),))
    with pytest.raises(ValueError, match='source'):
        book.publish((replace(first, as_of=200, source_as_of=89),))
    book.close()


def test_restore_rejects_boolean_count_and_requires_valid_hash(tmp_path):
    path = tmp_path/'forecasts.sqlite'
    book = RollingForecastBook(path, create=True)
    book.publish((candidate(),))
    checkpoint = book.checkpoint()
    book.close()
    with pytest.raises(ValueError, match='checkpoint'):
        RollingForecastBook(path, checkpoint=dict(checkpoint, count=True))
    with pytest.raises(ValueError):
        RollingForecastBook(path, checkpoint=dict(checkpoint, head_hash=None))


def test_failed_storage_exposes_no_publication_and_requires_restart(tmp_path, monkeypatch):
    book = RollingForecastBook(tmp_path/'forecasts.sqlite', create=True)
    def fail(*args):
        raise OSError('synthetic storage failure')
    monkeypatch.setattr(book.journal, 'append', fail)
    with pytest.raises(OSError):
        book.publish((candidate(),))
    assert book.latest(candidate().target, arm_hash='b'*64) is None
    with pytest.raises(ValueError, match='restart'):
        book.publish((candidate(),))
    book.close()
