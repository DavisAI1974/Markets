"""The authorized single source is its own scope, independent of calendar rosters.

This is a declared physical identity, not an extraction or calculation receipt.
Ingestion separately verifies all bytes and the complete record denominator.
"""
from .causal_prefix import SourceMember, SourceScope, ScopeKind
from .causal_prefix_records import SUPPORTED_ADAPTER_REVISION
from .raw_mbo_source_manifest import manifest_hash


def source_manifest():
    body = dict(schema='BOSS_SINGLE_SOURCE_MANIFEST_V1',
        source_kind='NATIVE_DBN_MBO', role='DEVELOPMENT_TRAINING',
        causal_clock='ts_recv_ns', sampled=False, canonical_source_rewritten=False,
        sources=[dict(member_index=0, member_key='glbx-mdp3-20211003.mbo.dbn.zst',
            sha256='4380bd9ba83a5badc4839e12785aa464817b87e3fac11176b951e7b474446d88',
            size_bytes=973355, mbo_records=57027)])
    return dict(body, manifest_hash=manifest_hash(body))


def source_scope(manifest, *, expected_manifest_hash):
    """Bind the complete user-selected source; no four-date or warmup gate."""
    if isinstance(manifest, dict) and manifest.get('schema') == 'BOSS_BLOCK_SOURCE_MANIFEST_V1':
        from .block_source_scope import block_source_scope
        return block_source_scope(manifest, expected_manifest_hash=expected_manifest_hash)
    if (manifest != source_manifest()
            or expected_manifest_hash != manifest['manifest_hash']):
        raise ValueError('source differs from the independently pinned single-source scope')
    return SourceScope(ScopeKind.RESULT_BEARING, expected_manifest_hash,
        tuple(SourceMember(**member) for member in manifest['sources']),
        SUPPORTED_ADAPTER_REVISION)
