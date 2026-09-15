from research.kalshi.frankie_boss.mbo_source import ingest_sources
from research.kalshi.frankie_boss.causal_prefix import SourceScope, ScopeKind
from research.kalshi.frankie_boss.causal_prefix_records import SUPPORTED_ADAPTER_REVISION
from test_frankie_source_mapping import inputs


def test_ingestion_reports_only_committed_records_and_completed_checkpoint(tmp_path):
    args, _ = inputs(tmp_path)
    scope = SourceScope(ScopeKind.RESULT_BEARING, 'a' * 64,
        (args['source_member'],), SUPPORTED_ADAPTER_REVISION)
    seen = []
    result = ingest_sources(scope, (args['source_path'],), tmp_path/'journal.sqlite',
        args['extraction_pin'], expected_scope_hash=scope.genesis_hash(),
        session_ids=('supplied-source',), event=seen.append)
    assert seen[0] == dict(phase='ingestion', records=0, total_records=3)
    assert seen[-2] == dict(phase='source_verification', records=3, total_records=3)
    assert seen[-1]['phase'] == 'source_saved'
    assert seen[-1]['journal_hash'] == result.completion.journal_hash
    assert seen[-1]['records'] == result.completion.record_count == 3
