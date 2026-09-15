from research.kalshi.frankie_boss.c15_builder import C15Builder, ADAPTER_REVISION
from research.kalshi.frankie_boss.causal_prefix import SourceScope, SourceMember, ScopeKind
from research.kalshi.frankie_boss.online_source_prefix import snapshot_closed_prefix
from research.kalshi.frankie_boss import online_source_prefix


def test_online_copy_preserves_envelopes_and_excludes_later_commits(tmp_path):
    scope = SourceScope(ScopeKind.PROBE_ONLY, 'a'*64,
        (SourceMember(0, 'synthetic', 'b'*64, 112, 2),), ADAPTER_REVISION)
    builder = C15Builder(scope, tmp_path/'source.sqlite')
    record = dict(instrument_id=1, publisher_id=1, channel_id=1, order_id=1,
        action='A', side='A', price=100, size=1, flags=128, sequence=0,
        ts_event=1, ts_recv=2, ts_in_delta=1)
    builder.apply(record, source_member_index=0, session_id='synthetic')
    original = list(builder.journal.connection.execute('SELECT * FROM entries ORDER BY ordinal'))
    view, receipt = snapshot_closed_prefix(builder.journal.path, tmp_path/'prefix.sqlite', scope, group_index=0)
    builder.apply(dict(record, order_id=2, sequence=1, ts_event=3, ts_recv=4),
                  source_member_index=0, session_id='synthetic')
    assert list(view.journal.connection.execute('SELECT * FROM entries ORDER BY ordinal')) == original
    assert receipt['records_in_prefix'] == 1 and receipt['source_records_expected'] == 2
    assert not receipt['full_source_complete'] and view.chain.next_cursor == 1
    assert len(list(view.journal.entries())) == 2
    view.journal.close()
    builder.journal.close()


def test_online_decode_releases_read_lock_before_writer_commit(tmp_path, monkeypatch):
    scope = SourceScope(ScopeKind.PROBE_ONLY, 'a'*64,
        (SourceMember(0, 'synthetic', 'b'*64, 112, 2),), ADAPTER_REVISION)
    builder = C15Builder(scope, tmp_path/'source.sqlite')
    record = dict(instrument_id=1, publisher_id=1, channel_id=1, order_id=1,
        action='A', side='A', price=100, size=1, flags=128, sequence=0,
        ts_event=1, ts_recv=2, ts_in_delta=1)
    builder.apply(record, source_member_index=0, session_id='synthetic')
    unpack, calls = online_source_prefix.unpack, []
    def decode(value):
        if not calls:
            calls.append(True)
            builder.apply(dict(record, order_id=2, sequence=1, ts_event=3, ts_recv=4),
                          source_member_index=0, session_id='synthetic')
        return unpack(value)
    monkeypatch.setattr(online_source_prefix, 'unpack', decode)
    view, receipt = snapshot_closed_prefix(builder.journal.path, tmp_path/'prefix.sqlite', scope, group_index=0)
    assert builder.chain.next_cursor == 2 and receipt['records_in_prefix'] == 1
    view.journal.close()
    builder.journal.close()
