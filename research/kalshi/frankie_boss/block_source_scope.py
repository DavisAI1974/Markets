"""Bind a staged multi-day block manifest to a SourceScope, the way selected_source_scope binds Sunday.

The block manifest (operations/stage_block_sources.py, schema BOSS_BLOCK_SOURCE_MANIFEST_V1) carries
its members in the Sunday shape (member_index, member_key, sha256, size_bytes, mbo_records) plus the
seam checks the builder depends on: every member seam and every 21:00Z halt boundary must close an
F_LAST group, because the builder refuses a member transition or a session change inside an open
group. This module binds what the committed manifest declares and refuses anything else; it does
not open a source, count a record or infer a roster.
"""
try:
    from .causal_prefix import SourceMember, SourceScope, ScopeKind
    from .causal_prefix_records import SUPPORTED_ADAPTER_REVISION
    from .raw_mbo_source_manifest import manifest_hash
except ImportError:   # flat import, as the tests do
    from causal_prefix import SourceMember, SourceScope, ScopeKind
    from causal_prefix_records import SUPPORTED_ADAPTER_REVISION
    from raw_mbo_source_manifest import manifest_hash

SCHEMA = 'BOSS_BLOCK_SOURCE_MANIFEST_V1'
_MEMBER_KEYS = frozenset({'member_index', 'member_key', 'sha256', 'size_bytes', 'mbo_records'})


def block_source_scope(manifest, *, expected_manifest_hash):
    """The block's declared physical identity as a RESULT_BEARING scope; member order is replay order."""
    if type(manifest) is not dict or manifest.get('schema') != SCHEMA:
        raise ValueError('block source manifest required')
    if (type(expected_manifest_hash) is not str or manifest.get('manifest_hash') != expected_manifest_hash
            or manifest_hash(manifest) != expected_manifest_hash):
        raise ValueError('block manifest differs from the independently pinned hash')
    if (manifest.get('source_kind') != 'NATIVE_DBN_MBO' or manifest.get('causal_clock') != 'ts_recv_ns'
            or manifest.get('sampled') is not False or manifest.get('canonical_source_rewritten') is not False):
        raise ValueError('block manifest is not a native, unsampled, unrewritten MBO source')
    if manifest.get('member_seams_close_groups') is not True or manifest.get('halt_boundaries_close_groups') is not True:
        raise ValueError('block manifest does not declare F_LAST-closed member seams and halt boundaries')
    sources = manifest.get('sources')
    if type(sources) is not list or not sources:
        raise ValueError('block manifest declares no sources')
    members = []
    for expected_index, raw in enumerate(sources):
        if type(raw) is not dict or set(raw) != _MEMBER_KEYS or raw['member_index'] != expected_index:
            raise ValueError('block manifest members must carry exactly the Sunday member fields, in replay order')
        members.append(SourceMember(**raw))
    if sum(member.mbo_records for member in members) != manifest.get('total_mbo_records'):
        raise ValueError('block manifest record total differs from its members')
    return SourceScope(ScopeKind.RESULT_BEARING, expected_manifest_hash, tuple(members), SUPPORTED_ADAPTER_REVISION)
