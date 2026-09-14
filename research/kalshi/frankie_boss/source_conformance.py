"""Explicit source-coordinate conformance over the unchanged C15 builder.

Caller source hashes are declarations, not proof of native extraction. No source
is opened and no mapping is inferred here. All operational gates remain external.
"""
from dataclasses import asdict, dataclass

try:
    from .c15_builder import C15Builder
    from .c15_journal import evidence_hash, pack
    from .causal_prefix import SourceScope
    from .causal_prefix_records import RecordInput, RecordPrefixChain
except ImportError:
    from c15_builder import C15Builder
    from c15_journal import evidence_hash, pack
    from causal_prefix import SourceScope
    from causal_prefix_records import RecordInput, RecordPrefixChain


@dataclass(frozen=True)
class SourceCompletion:
    schema: str
    scope_kind: str
    scope_hash: str
    record_count: int
    member_counts: tuple[int, ...]
    group_count: int
    source_prefix_hash: str
    journal_count: int
    journal_hash: str
    builder_state_hash: str

    @property
    def digest(self):
        return evidence_hash(asdict(self))


class SourceConformanceDriver:
    """Single-writer owner of a C15 journal; no implicit retry or source repair."""

    def __init__(self, scope, journal_path, *, expected_scope_hash):
        self._check_scope(scope, expected_scope_hash)
        self._builder = C15Builder(scope, journal_path)
        self._stopped = self._completed = self._closed = False

    @staticmethod
    def _check_scope(scope, expected_hash):
        if not isinstance(scope, SourceScope) or scope.genesis_hash() != expected_hash:
            raise ValueError("source scope differs from independently trusted identity")

    @property
    def scope(self):
        return self._builder.scope

    def _active(self, *, writing=False):
        if self._closed or self._stopped:
            raise ValueError("source driver is stopped or closed; explicit recovery required")
        if writing and self._completed:
            raise ValueError("source stream is completed")

    def append(self, record, *, cursor, source_member_index, source_sha256,
               session_id, raw_symbol=None, source_dbn_object=None):
        self._active(writing=True)
        try:
            if type(cursor) is not int or cursor != self._builder.chain.next_cursor:
                raise ValueError("source cursor differs from next physical cursor")
            if (type(source_member_index) is not int
                    or not 0 <= source_member_index < len(self.scope.members)):
                raise ValueError("source member outside declared scope")
            start, end = self.scope.member_cursor_bounds(source_member_index)
            if not start <= cursor < end:
                raise ValueError("source cursor outside declared member bounds")
            if source_sha256 != self.scope.members[source_member_index].sha256:
                raise ValueError("source digest differs from declared member")
            return self._builder.apply(record, source_member_index=source_member_index,
                session_id=session_id, raw_symbol=raw_symbol,
                source_dbn_object=source_dbn_object)
        except Exception:
            self._stopped = True
            raise

    def _verified_checkpoint(self):
        self._active()
        state = self._builder.export_state()  # Also requires every group closed.
        chain = RecordPrefixChain(self.scope)
        counts = [0] * len(self.scope.members)
        pending = None
        for entry in self._builder.journal.entries():
            payload = entry["payload"]
            if entry["kind"] == "INPUT":
                if (pending is not None or payload["cursor"] != chain.next_cursor
                        or payload["scope_genesis_hash"] != self.scope.genesis_hash()):
                    raise ValueError("source journal input continuity mismatch")
                pending = (entry["ordinal"], payload)
            elif entry["kind"] == "APPLIED":
                if pending is None:
                    raise ValueError("source journal has unpaired applied evidence")
                ordinal, submitted = pending
                if (payload["input_ordinal"] != ordinal
                        or pack(payload["raw_record"]) != pack(submitted["record"])
                        or any(payload[key] != submitted[key] for key in
                               ("cursor", "source_member_index", "session_id"))
                        or any(payload["normalized"][key] != submitted[key] for key in
                               ("raw_symbol", "source_dbn_object"))):
                    raise ValueError("source journal applied evidence differs from submission")
                receipt = chain.advance(RecordInput(payload["cursor"],
                    payload["source_member_index"], payload["normalized"],
                    self.scope.adapter_revision))
                if (payload["terminal_prefix_hash"] != chain.prefix_hash
                        or payload["record_count"] != chain.next_cursor
                        or payload["group_count"] != chain.next_global_group_ordinal
                        or pack(payload["receipt"]) != pack(
                            None if receipt is None else receipt.public_dict())):
                    raise ValueError("source journal prefix or group receipt mismatch")
                counts[payload["source_member_index"]] += 1
                pending = None
            else:
                raise ValueError("source journal contains failed or unknown evidence")
        if (pending is not None or chain.export_state() != state["prefix"]
                or state["journal_count"] != 2 * chain.next_cursor
                or state["journal_hash"] != self._builder.journal.head_hash):
            raise ValueError("source journal and builder terminal state differ")
        return state, tuple(counts)

    def checkpoint(self):
        """Export existing C15 state after complete journal conformance checks."""
        return self._verified_checkpoint()[0]

    @classmethod
    def restore(cls, scope, journal_path, state, *, expected_scope_hash,
                expected_state_hash):
        cls._check_scope(scope, expected_scope_hash)
        driver = cls.__new__(cls)
        driver._builder = C15Builder.restore(scope, journal_path, state,
                                             expected_hash=expected_state_hash)
        driver._stopped = driver._completed = driver._closed = False
        try:
            driver._verified_checkpoint()
        except Exception:
            driver.close()
            raise
        return driver

    def complete(self):
        """Verify the full declared stream and return an immutable software receipt."""
        self._active()
        expected = tuple(member.mbo_records for member in self.scope.members)
        if self._builder.chain.next_cursor != sum(expected):
            raise ValueError("source record count is incomplete")
        state, counts = self._verified_checkpoint()
        if counts != expected:
            raise ValueError("source member counts do not reconcile")
        receipt = SourceCompletion("BOSS_SOURCE_CONFORMANCE_V1", self.scope.kind.value,
            self.scope.genesis_hash(), sum(counts), counts,
            self._builder.chain.next_global_group_ordinal,
            self._builder.chain.prefix_hash, state["journal_count"],
            state["journal_hash"], state["state_hash"])
        self._completed = True
        return receipt

    def evidence_stream(self, *, through_cursor=None):
        self._active()
        return self._builder.evidence_stream(through_cursor=through_cursor)

    def close(self):
        if not self._closed:
            self._builder.journal.close()
            self._closed = True
