"""Stable per-record DBN provenance for newly prepared experiment ingests.

The physical journal is still pinned at completion. It is not the DBN object
whose hash belongs on a new native record. Absence of this policy means the
historical journal-stamped contract, including on every retained resume.
"""
from bisect import bisect_right
from dataclasses import asdict


SCHEMA = 'FRANKIE_NATIVE_DBN_MEMBER_PROVENANCE_V1'
OBJECT_RULE = 'dbn:<trading_day>:<member_key>'


def binding(manifest, day):
    from research.kalshi.frankie_boss.block_source_scope import block_source_scope
    scope = block_source_scope(manifest, expected_manifest_hash=manifest['manifest_hash'])
    day = str(day)
    if (len(day) != 8 or not day.isdigit() or not day.startswith('20')
            or manifest.get('trading_day') != day):
        raise ValueError('native member provenance requires the manifest trading day')
    return dict(schema=SCHEMA, trading_day=day, manifest_hash=manifest['manifest_hash'],
                scope_genesis_hash=scope.genesis_hash(), object_rule=OBJECT_RULE,
                total_mbo_records=manifest['total_mbo_records'],
                members=[asdict(member) for member in scope.members])


def require_binding(selected, manifest, day):
    expected = binding(manifest, day)
    if selected != expected:
        raise ValueError('native record provenance differs from the selected DBN manifest')
    return expected


class MemberSource:
    """Use original global INPUT ordinals, also when a saved reader seeks ahead.

    The manifest counts are trading-day takes, not whole partition counts.
    The day prefix preserves the pinned driver's first-date source-day rule
    even when the first physical member is the preceding UTC partition.
    No growing prefix hash, renamed journal or end-of-day digest enters rows.
    """
    def __init__(self, selected):
        from research.kalshi.frankie_boss.causal_prefix import SourceMember
        if (not isinstance(selected, dict) or selected.get('schema') != SCHEMA
                or selected.get('object_rule') != OBJECT_RULE):
            raise ValueError('unsupported native member provenance')
        self.selected = selected
        self.members = tuple(SourceMember(**row) for row in selected['members'])
        self.ends = []
        end = 0
        for index, member in enumerate(self.members):
            if member.member_index != index:
                raise ValueError('native members must retain original replay order')
            end += member.mbo_records
            self.ends.append(end)
        if not self.members or end != selected['total_mbo_records']:
            raise ValueError('native member counts differ from the full source denominator')
        self.total = end
        self.objects = tuple('dbn:%s:%s' % (selected['trading_day'], member.member_key)
                             for member in self.members)

    def member_at(self, cursor):
        if type(cursor) is not int or not 0 <= cursor < self.total:
            raise ValueError('native INPUT cursor is outside the declared day')
        return self.members[bisect_right(self.ends, cursor)]

    def verify_input(self, payload, cursor):
        """Bind the original INPUT envelope before its observation is spooled.

        This observes an append; it does not claim APPLIED success or conformance.
        Publication still waits for the existing committed/conformant boundary.
        """
        member = self.member_at(cursor)
        if (type(payload) is not dict or type(payload.get('cursor')) is not int
                or payload['cursor'] != cursor
                or type(payload.get('source_member_index')) is not int
                or payload['source_member_index'] != member.member_index
                or payload.get('source_dbn_object') != member.member_key
                or payload.get('scope_genesis_hash') != self.selected['scope_genesis_hash']):
            raise ValueError('native INPUT envelope differs from its original member/cursor binding')

    def stamp(self, records, start_cursor=0):
        if type(start_cursor) is not int or not 0 <= start_cursor <= self.total:
            raise ValueError('native start cursor is outside the declared day')
        for cursor, record in enumerate(records, start_cursor):
            member = self.member_at(cursor)
            stamped = dict(record)
            stamped['source_dbn_object'] = self.objects[member.member_index]
            stamped['source_dbn_sha256'] = member.sha256
            stamped['raw_symbol'] = record.get('raw_symbol') or record.get('symbol') or None
            yield stamped
