"""Actual synthetic native refresh -> verified ledger -> approved Frankie record."""
from dataclasses import replace
import pytest
from frankie_forecast_consumer import consume_forecast
from rolling_forecast import RollingForecastBook
from test_native_forecast_refresh import build_refresh, update, H
from test_forecast_bridge import metadata


def context():
    return {**metadata(), 'date': '19691231'}


def test_enabled_consumes_native_publication_and_verified_restart(tmp_path):
    bridge, sessions = build_refresh(tmp_path); published = update(bridge, sessions)
    records = [consume_forecast(enabled=True, legacy=None, book=bridge.book,
                publication_hash=p.receipt_hash, metadata=context()) for p in published]
    assert all(r.payload['confidence'] is None and not r.payload['state_defects_and_gaps_reported'] for r in records)
    assert [r.publication_hash for r in records] == [p.receipt_hash for p in published]
    assert [r.artifact_digest for r in records] == [p.selected.candidate_id for p in published]
    checkpoint = bridge.book.checkpoint(); bridge.book.close()
    restored = RollingForecastBook(tmp_path/'forecasts.sqlite', checkpoint=checkpoint)
    assert consume_forecast(enabled=True, legacy=None, book=restored,
           publication_hash=published[0].receipt_hash, metadata=context()).to_json() == records[0].to_json()


def test_missing_publication_produces_complete_safe_abstain(tmp_path):
    bridge, _ = build_refresh(tmp_path)
    record = consume_forecast(enabled=True, legacy=None, book=bridge.book, publication_hash=H, metadata=context())
    p = record.payload
    assert p['confidence'] is None and p['disposition'] == 'ABSTAIN'
    assert p['guessed_net_usd'] == p['overnight_gap_usd'] == 0
    assert p['path_p50_curve'] == [[20., 0.], [24., 0.]]
    assert p['state_defects_and_gaps_reported'] and record.artifact_digest is None


def test_mismatched_source_cannot_reuse_forecast_bytes(tmp_path):
    bridge, sessions = build_refresh(tmp_path); original = update(bridge, sessions)[0]
    other = RollingForecastBook(tmp_path/'other.sqlite', create=True)
    bad = other.publish((replace(original.selected, source_hash='b'*64),))
    result = consume_forecast(enabled=True, legacy=None, book=other, publication_hash=bad.receipt_hash, metadata=context())
    assert result.payload['state_defects_and_gaps_reported']
    assert result.payload['guessed_net_usd'] == 0


def test_disabled_consumer_never_touches_ledger_or_metadata():
    sentinel = object()
    assert consume_forecast(legacy=lambda: sentinel, book=object(), metadata=object(), publication_hash=object()) is sentinel


def test_known_fatal_defects_keep_complete_safety_fallback(tmp_path):
    bridge, sessions = build_refresh(tmp_path); pub = update(bridge, sessions)[0]
    meta = {**context(), 'state_defects_and_gaps_reported': ['causal source unavailable']}
    result = consume_forecast(enabled=True, legacy=None, book=bridge.book, publication_hash=pub.receipt_hash, metadata=meta)
    assert result.payload['state_defects_and_gaps_reported'] == ['causal source unavailable']
    assert result.payload['guessed_net_usd'] == 0


def test_earlier_revision_remains_readable_after_native_update(tmp_path):
    from test_c15_full_evidence import submit, row
    bridge, sessions = build_refresh(tmp_path); first = update(bridge, sessions)[0]
    old = consume_forecast(enabled=True, legacy=None, book=bridge.book, publication_hash=first.receipt_hash, metadata=context())
    submit(bridge.context.builder, row(1))
    refreshed = tuple((t, replace(s, event_cutoff_ns=101, receive_cutoff_ns=102,
                       source_hash=bridge.context.builder.chain.prefix_hash)) for t, s in sessions)
    second = update(bridge, refreshed)[0]
    again = consume_forecast(enabled=True, legacy=None, book=bridge.book, publication_hash=first.receipt_hash, metadata=context())
    latest = consume_forecast(enabled=True, legacy=None, book=bridge.book, publication_hash=second.receipt_hash, metadata=context())
    assert again.to_json() == old.to_json()
    assert latest.publication_hash != old.publication_hash
    assert latest.artifact_digest != old.artifact_digest


def test_timeout_returns_safe_record_without_using_legacy():
    class UnavailableBook:
        def publication(self, _): raise TimeoutError('synthetic timeout')
    result = consume_forecast(enabled=True, legacy=lambda: pytest.fail('legacy fallback'),
        book=UnavailableBook(), publication_hash=H, metadata=context())
    assert result.payload['disposition'] == 'ABSTAIN'
    assert 'TimeoutError' in result.payload['state_defects_and_gaps_reported'][0]


def test_untrusted_newer_ledger_terminal_is_not_adopted(tmp_path):
    from c15_journal import EvidenceJournal
    bridge, sessions = build_refresh(tmp_path); first = update(bridge, sessions)[0]
    external = EvidenceJournal(tmp_path/'forecasts.sqlite')
    external.append('unexpected writer', {'synthetic': True}); external.close()
    result = consume_forecast(enabled=True, legacy=None, book=bridge.book,
                              publication_hash=first.receipt_hash, metadata=context())
    assert result.artifact_digest is None and result.payload['state_defects_and_gaps_reported']


def test_missing_book_returns_safe_record():
    result = consume_forecast(enabled=True, legacy=None, metadata=context())
    assert result.artifact_digest is None and result.payload['state_defects_and_gaps_reported']


def test_qsv_same_forward_receipt_is_accepted(tmp_path):
    from test_context_qsv import make_case, runner
    from b1_reasoner import B1Reasoner, B1Config
    bridge, sessions = build_refresh(tmp_path)
    qsv_path = tmp_path/'qsv'; qsv_path.mkdir()
    builder, model, qsv = make_case(qsv_path)
    boss = B1Reasoner(model, B1Config(k_max=1, k_fixed=1)).double().eval()
    bridge.context = runner(builder, boss, qsv)
    sessions = tuple((t, replace(s, source_hash=builder.chain.prefix_hash)) for t, s in sessions)
    publication = update(bridge, sessions)[0]
    result = consume_forecast(enabled=True, legacy=None, book=bridge.book,
        publication_hash=publication.receipt_hash, metadata=context())
    assert result.artifact_digest == publication.selected.candidate_id
    assert not result.payload['state_defects_and_gaps_reported']


@pytest.mark.parametrize('payload', [b'[]', b'null', b'["dict", []]', b'["float64", ""]'])
def test_malformed_artifact_returns_safe_record(tmp_path, payload):
    bridge, sessions = build_refresh(tmp_path); original = update(bridge, sessions)[0]
    other = RollingForecastBook(tmp_path/'other.sqlite', create=True)
    bad = other.publish((replace(original.selected, forecast_artifact=payload),))
    result = consume_forecast(enabled=True, legacy=None, book=other,
        publication_hash=bad.receipt_hash, metadata=context())
    assert result.artifact_digest is None and result.payload['state_defects_and_gaps_reported']


@pytest.mark.parametrize('mutation', ['packet', 'missing_recurrence', 'missing_context_field', 'schema'])
def test_inconsistent_computation_receipt_returns_safe_record(tmp_path, mutation):
    import json
    from c15_journal import canonical_bytes, pack, unpack
    from forecast_artifact import NativeForecastArtifact
    bridge, sessions = build_refresh(tmp_path); original = update(bridge, sessions)[0]
    artifact = NativeForecastArtifact.from_payload(original.selected.forecast_artifact,
        expected_digest=original.selected.candidate_id)
    binding = unpack(json.loads(artifact.context_receipt))
    binding.pop('publication_validation', None)  # Exercise legacy, unattested receipt validation.
    if mutation == 'packet': binding['recurrence']['packet_hash'] = 'b'*64
    elif mutation == 'missing_recurrence': del binding['recurrence']
    elif mutation == 'missing_context_field': del binding['context']['packet_hashes']
    else: binding['recurrence']['schema'] = 'unknown'
    changed = replace(artifact, context_receipt=canonical_bytes(pack(binding)))
    other = RollingForecastBook(tmp_path/'other.sqlite', create=True)
    bad = other.publish((replace(original.selected, candidate_id=changed.digest, forecast_artifact=changed.payload),))
    result = consume_forecast(enabled=True, legacy=None, book=other,
        publication_hash=bad.receipt_hash, metadata=context())
    assert result.artifact_digest is None and result.payload['state_defects_and_gaps_reported']
