"""One preparation, many reuses: equivalence, isolation, identity refusals, failure, close.

Synthetic journals and a tiny NativeTrunk only; no forward, training, service call or retained data.
"""
import pytest
import torch

from c15_journal import EvidenceJournal, pack
from c15_normalizer import IdentityNormalizer
from c15_teacher import JournalTeacher
from context_session import ContextSessionRunner
from prepared_context_cache import PreparedContextCache, own, prepare_context_cache, same_preparation
from test_c15_full_evidence import build, submit, row
from test_context_session import model


AS_OF, CURSOR = 202, 2


def session(tmp_path, teacher=True):
    builder = build(tmp_path)
    for i in range(3):
        submit(builder, row(i, oid=i + 1))
    guide = JournalTeacher({1: 1}, normalizer=IdentityNormalizer((1,))) if teacher else None
    context = ContextSessionRunner(model(), builder, entity=(1, 1), t_ctx=2, teacher=guide)
    return context


def counted(monkeypatch, context):
    calls, original = [], context._prepare
    def prepare(as_of, through_cursor):
        calls.append((as_of, through_cursor))
        return original(as_of, through_cursor)
    monkeypatch.setattr(context, '_prepare', prepare)
    return calls


def arguments(context, checkpoint):
    journal = context.builder.journal
    return dict(as_of=AS_OF, through_cursor=CURSOR,
        expected_source_checkpoint=dict(count=journal.count, head_hash=journal.head_hash),
        expected_model_hash=context._model_hash(),
        expected_teacher_binding=None if context.teacher is None else context.teacher.binding,
        checkpoint_hash=checkpoint['hash'], current_checkpoint_hash=lambda: checkpoint['hash'])


def test_one_preparation_serves_repeated_equivalent_reuse(tmp_path, monkeypatch):
    context = session(tmp_path)
    direct = context._prepare(AS_OF, CURSOR)
    calls = counted(monkeypatch, context)
    checkpoint = dict(hash='1' * 64)
    cache = prepare_context_cache(context, **arguments(context, checkpoint))
    assert calls == [(AS_OF, CURSOR)]
    served = [cache.prepare(AS_OF, CURSOR) for _ in range(3)]
    assert calls == [(AS_OF, CURSOR)]
    for tokens, info, input_hash, teacher, rows in served:
        assert input_hash == direct[2]
        assert same_preparation(tokens, direct[0]) and same_preparation(info, direct[1])
        assert same_preparation(teacher, direct[3]) and same_preparation(rows, direct[4])
        assert pack(rows) == pack(direct[4]) and pack(info) == pack(direct[1])
        assert teacher['attachment_hash'] == direct[3]['attachment_hash'] == info['teacher_hash']
        assert set(tokens) == set(direct[0]) and all(tokens[k] is not direct[0][k] for k in tokens)
    assert all(a[0]['numeric'] is not b[0]['numeric'] for a, b in zip(served, served[1:]))
    receipt = cache.receipt
    assert receipt['input_hash'] == direct[2] and receipt['preparations_performed'] == 1
    assert receipt['bindings']['checkpoint_hash'] == '1' * 64 and receipt['bindings']['t_ctx'] == 2
    assert receipt['bindings']['entity'] == (1, 1) and receipt['bindings']['next_cursor'] == 3
    assert receipt['model_forward_performed'] is False and receipt['persisted'] is False
    cache.close()


def test_returned_and_original_data_are_isolated_from_the_cache(tmp_path, monkeypatch):
    context = session(tmp_path)
    original = context._prepare
    kept = {}
    def prepare(as_of, through_cursor):
        kept['tuple'] = original(as_of, through_cursor)
        return kept['tuple']
    monkeypatch.setattr(context, '_prepare', prepare)
    checkpoint = dict(hash='1' * 64)
    cache = PreparedContextCache(context, **arguments(context, checkpoint))
    pristine = own(cache.prepare(AS_OF, CURSOR))
    tokens, info, input_hash, teacher, rows = cache.prepare(AS_OF, CURSOR)
    tokens['numeric'][0, 0, 0] += 1
    tokens['extra'] = torch.zeros(1)
    info['consumed_rows'] = 99
    info['context_cursors'] = ()
    rows[0]['raw_record']['size'] = -1
    rows.append('junk')
    teacher['targets'][0].values[0, 0, 0] += 1
    teacher['step_receipts'] = ()
    # The tuple the original _prepare returned is also not the cache's storage.
    kept['tuple'][0]['numeric'][0, 0, 0] += 5
    kept['tuple'][1]['as_of'] = 0
    kept['tuple'][4][0]['cursor'] = 42
    again = cache.prepare(AS_OF, CURSOR)
    assert same_preparation(again, pristine) and again[2] == input_hash
    assert 'extra' not in again[0] and again[1]['consumed_rows'] == 2 and len(again[4]) == 2
    cache.close()


def test_cutoff_and_identity_changes_are_refused_never_recomputed(tmp_path, monkeypatch):
    context = session(tmp_path)
    calls = counted(monkeypatch, context)
    checkpoint = dict(hash='1' * 64)
    cache = prepare_context_cache(context, **arguments(context, checkpoint))
    with pytest.raises(ValueError, match='different cutoff'):
        cache.prepare(AS_OF + 1, CURSOR)
    with pytest.raises(ValueError, match='different cutoff'):
        cache.prepare(AS_OF, CURSOR - 1)
    checkpoint['hash'] = '2' * 64
    with pytest.raises(ValueError, match='training checkpoint advanced'):
        cache.prepare(AS_OF, CURSOR)
    checkpoint['hash'] = '1' * 64
    cache.prepare(AS_OF, CURSOR)
    with torch.no_grad():
        context.model.byte_embedding.weight[0, 0] += 1
    with pytest.raises(ValueError, match='native model differs'):
        cache.prepare(AS_OF, CURSOR)
    with torch.no_grad():
        context.model.byte_embedding.weight[0, 0] -= 1
    cache.prepare(AS_OF, CURSOR)
    original_teacher = context.teacher
    context.teacher = JournalTeacher({1: 2}, normalizer=IdentityNormalizer((1,)))
    with pytest.raises(ValueError, match='teacher binding'):
        cache.prepare(AS_OF, CURSOR)
    context.teacher = original_teacher
    context.t_ctx = 3
    with pytest.raises(ValueError, match='identity differs'):
        cache.prepare(AS_OF, CURSOR)
    context.t_ctx = 2
    context.entity = (1, 2)
    with pytest.raises(ValueError, match='identity differs'):
        cache.prepare(AS_OF, CURSOR)
    context.entity = (1, 1)
    cache.prepare(AS_OF, CURSOR)
    assert calls == [(AS_OF, CURSOR)]
    cache.close()


def test_source_change_is_detected_from_the_stored_tail_without_a_journal_scan(tmp_path, monkeypatch):
    context = session(tmp_path)
    calls = counted(monkeypatch, context)
    checkpoint = dict(hash='1' * 64)
    cache = prepare_context_cache(context, **arguments(context, checkpoint))
    monkeypatch.setattr(context.builder.journal, 'entries', lambda: pytest.fail('full journal scan on reuse'))
    cache.prepare(AS_OF, CURSOR)
    other = EvidenceJournal(context.builder.journal.path)  # a second handle, invisible to the cached count
    try:
        other.append('foreign-audit', {})
    finally:
        other.close()
    assert context.builder.journal.count == 6  # the handle's cached tail did not move
    with pytest.raises(ValueError, match='trusted source checkpoint'):
        cache.prepare(AS_OF, CURSOR)
    assert calls == [(AS_OF, CURSOR)]
    cache.close()


def test_later_valid_suffix_through_the_builder_is_also_refused(tmp_path):
    context = session(tmp_path)
    checkpoint = dict(hash='1' * 64)
    cache = prepare_context_cache(context, **arguments(context, checkpoint))
    submit(context.builder, row(3, oid=4))
    with pytest.raises(ValueError, match='identity differs|source checkpoint'):
        cache.prepare(AS_OF, CURSOR)
    cache.close()


def test_creation_rejects_wrong_expectations_before_preparing(tmp_path, monkeypatch):
    context = session(tmp_path)
    calls = counted(monkeypatch, context)
    checkpoint = dict(hash='1' * 64)
    base = arguments(context, checkpoint)
    with pytest.raises(ValueError, match='training checkpoint'):
        prepare_context_cache(context, **dict(base, checkpoint_hash='9' * 64))
    with pytest.raises(ValueError, match='native model'):
        prepare_context_cache(context, **dict(base, expected_model_hash='9' * 64))
    with pytest.raises(ValueError, match='source checkpoint'):
        prepare_context_cache(context, **dict(base, expected_source_checkpoint=dict(count=4, head_hash='9' * 64)))
    with pytest.raises(ValueError, match='teacher'):
        prepare_context_cache(context, **dict(base, expected_teacher_binding=None))
    with pytest.raises(ValueError, match='teacher'):
        prepare_context_cache(context, **dict(base, expected_teacher_binding='9' * 64))
    with pytest.raises(ValueError, match='callable'):
        prepare_context_cache(context, **dict(base, current_checkpoint_hash='1' * 64))
    with pytest.raises(ValueError, match='cutoff'):
        prepare_context_cache(context, **dict(base, through_cursor=7))
    assert calls == []
    without = session(tmp_path / 'plain', teacher=False)
    plain = prepare_context_cache(without, **arguments(without, checkpoint))
    assert plain.prepare(AS_OF, CURSOR)[3] is None and plain.receipt['teacher_hash'] is None
    plain.close()


def test_failed_preparation_caches_nothing(tmp_path, monkeypatch):
    context = session(tmp_path)
    checkpoint = dict(hash='1' * 64)
    base = arguments(context, checkpoint)
    with pytest.raises(ValueError, match='future'):
        prepare_context_cache(context, **dict(base, as_of=1))
    original = context._prepare
    monkeypatch.setattr(context, '_prepare', lambda *unused: (_ for _ in ()).throw(RuntimeError('synthetic')))
    with pytest.raises(RuntimeError, match='synthetic'):
        prepare_context_cache(context, **base)
    monkeypatch.setattr(context, '_prepare', original)
    calls = counted(monkeypatch, context)
    cache = prepare_context_cache(context, **base)
    assert calls == [(AS_OF, CURSOR)] and cache.prepare(AS_OF, CURSOR)[2] == original(AS_OF, CURSOR)[2]
    cache.close()


def test_use_after_close_is_refused(tmp_path):
    context = session(tmp_path)
    checkpoint = dict(hash='1' * 64)
    with prepare_context_cache(context, **arguments(context, checkpoint)) as cache:
        cache.prepare(AS_OF, CURSOR)
    with pytest.raises(ValueError, match='closed'):
        cache.prepare(AS_OF, CURSOR)
    with pytest.raises(ValueError, match='closed'):
        cache.receipt
    cache.close()  # idempotent
    with pytest.raises(ValueError, match='closed'):
        cache.prepare(AS_OF, CURSOR)
