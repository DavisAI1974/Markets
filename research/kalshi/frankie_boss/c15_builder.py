"""Complete C15 evidence, without candidate-column or rolling-window reductions.

The existing V4 book performs every calculation. This opt-in builder adds an
append-only journal, complete per-event model-facing evidence, and checkpoint
bindings. It is not a 19-column target builder or an installed model provider.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import (
    ADAPTER_REVISION, InstrumentBook, V4MboAdapter,
)

try:
    from .causal_prefix_records import RecordInput, RecordPrefixChain
    from .c15_journal import EvidenceJournal, OBSERVATION_SENTINEL, PrePacked, SCHEMA, SerializedObservation, evidence_hash, pack, unpack
    from .c15_observer import IncrementalObservation, observe_book, order_rank
    from .c15_registry import implementation_identity
    from .mbo_resume_state import export_adapter_state, restore_adapter_state
except ImportError:
    from causal_prefix_records import RecordInput, RecordPrefixChain
    from c15_journal import EvidenceJournal, OBSERVATION_SENTINEL, PrePacked, SCHEMA, SerializedObservation, evidence_hash, pack, unpack
    from c15_observer import IncrementalObservation, observe_book, order_rank
    from c15_registry import implementation_identity
    from mbo_resume_state import export_adapter_state, restore_adapter_state


@dataclass(frozen=True)
class AppliedEvidence:
    frame: dict | None
    legacy_rows: list
    receipt: object | None
    observation: dict | None
    evidence: dict


# The incremental observation's differential check runs at each instrument composer's FIRST observation and every
# OBSERVATION_CHECK_EVERY-th after it (the chat-9 ship review: the count is per composer, not per builder). Between checks
# up to OBSERVATION_CHECK_EVERY - 1 observations are appended unchecked; a drift that persists is refused at the next
# check with those bodies already in the container (completion is then impossible: complete() refuses a FAILED entry),
# and the codec re-parses every spliced body at flush and refuses a non-canonical one. The full-path differential test
# (test_compact_build_journal) is the proof the composer needs no window at all; the check is the guard on the day.
OBSERVATION_CHECK_EVERY = 64


class C15Builder:
    def __init__(self, scope, journal_path):
        self.scope = scope
        self.chain = RecordPrefixChain(scope)
        self.adapter = V4MboAdapter()
        self.identity = implementation_identity()
        self.journal = EvidenceJournal(journal_path, create=True)
        self._sessions = {}
        self._failed = False

    def apply(self, record, *, source_member_index, session_id,
              raw_symbol=None, source_dbn_object=None):
        """Preserve and process one explicit raw MBO mapping, with all its fields.

        Returns evidence for EVERY record, including non-F_LAST, missing
        references, snapshots, fill/trade details and reset messages. Consumers
        must consume this stream, not just the optional completed-group frame.
        """
        if self._failed:
            raise ValueError("builder stopped after failure; retained evidence requires explicit recovery")
        if type(record) is not dict:
            raise ValueError("supply an explicit raw MBO mapping; no implicit field projection")
        # Own the complete original, including extra fields and exact float bits.
        raw = unpack(pack(record))
        cursor = self.chain.next_cursor
        input_ordinal = self.journal.count
        try:
            self.journal.append("INPUT", dict(record=raw, cursor=cursor,
                source_member_index=source_member_index, session_id=session_id,
                raw_symbol=raw_symbol, source_dbn_object=source_dbn_object,
                scope_genesis_hash=self.scope.genesis_hash()))
        except Exception:
            self._failed = True
            raise
        try:
            if type(session_id) is not str or not session_id:
                raise ValueError("explicit session identity required")
            if type(source_member_index) is not int or not 0 <= source_member_index < len(self.scope.members):
                raise ValueError("member outside declared source identity")
            msg = self.adapter.normalize(raw, raw_symbol, source_dbn_object,
                                          self.scope.members[source_member_index].sha256)
            previous_session = self._sessions.get(msg.instrument_id)
            if (msg.instrument_id in self.chain.open_instruments
                    and session_id != previous_session):
                raise ValueError("session changed inside an unfinished group")
            previous_member = self.chain.member_index if cursor else None
            receipt = self.chain.advance(RecordInput(cursor, source_member_index,
                                                     msg.public_dict(), ADAPTER_REVISION))
            book = self.adapter.books.setdefault(msg.instrument_id, InstrumentBook(msg.instrument_id))
            old = book.orders.get(msg.order_id)
            before = None if old is None else asdict(old)
            rank_before = order_rank(book, old)
            # This is the existing V4MboAdapter dispatch using the same public
            # InstrumentBook.apply, retaining its ApplyEffect instead of dropping it.
            effect, frame, legacy = book.apply(msg)
            self.adapter.record_count += 1
            if frame is not None:
                self.adapter.completed_event_group_count += 1
            if (receipt is None) != (frame is None):
                raise ValueError("adapter and prefix disagree on F_LAST closure")
            new = book.orders.get(msg.order_id)
            spliced = None
            if getattr(self.journal, 'accepts_spliced', False):
                # the compact path (Greg, 2026-09-22): the observation's bytes maintained incrementally and spliced by the
                # writer; the raw path below still packs observe_book, and the two are proven byte-identical by test
                composers = self.__dict__.setdefault('_composers', {})
                composer = composers.get(msg.instrument_id)
                if composer is None:
                    composer = composers[msg.instrument_id] = IncrementalObservation(book)
                elif effect.action == 'R' or (effect.action == 'A' and effect.removed):
                    composer.rebuild()                      # the book was cleared (a reset, or the one-side clear)
                else:
                    composer.note(msg.order_id, before, new, msg.side, msg.price_raw)
                if receipt is not None:
                    every = self.__dict__.get('observation_check_every', OBSERVATION_CHECK_EVERY)
                    spliced = composer.checked() if composer.observations % every == 0 else composer.canonical()
                    composer.observations += 1
                observation = OBSERVATION_SENTINEL if receipt is not None else None
            else:
                observation = self._prepacked(observe_book(book)) if receipt is not None else None
            evidence = dict(input_ordinal=input_ordinal, cursor=cursor, raw_record=raw,
                            source_member_index=source_member_index, session_id=session_id,
                            normalized=msg.public_dict(), effect=asdict(effect),
                            order_before=before, order_after=None if new is None else asdict(new),
                            rank_before=rank_before, rank_after=order_rank(book, new),
                            observation=observation, frame=frame, legacy_rows=legacy,
                            receipt=None if receipt is None else receipt.public_dict(),
                            integrity=dict(book.integrity),
                            boundary=dict(previous_member_index=previous_member,
                                          previous_session=previous_session),
                            terminal_prefix_hash=self.chain.prefix_hash,
                            record_count=self.adapter.record_count,
                            group_count=self.adapter.completed_event_group_count)
            if spliced is not None:
                self.journal.append("APPLIED", evidence, spliced=spliced)
                observation = evidence['observation'] = SerializedObservation(spliced)
            else:
                self.journal.append("APPLIED", evidence)
            self._sessions[msg.instrument_id] = session_id
            return AppliedEvidence(frame, legacy, receipt, observation, evidence)
        except Exception as exc:
            self._failed = True
            self.journal.append("FAILED", dict(input_ordinal=input_ordinal, cursor=cursor,
                                               error_type=type(exc).__name__, error=str(exc)))
            raise

    def _prepacked(self, observation):
        """The observation with its tagged tree built from a cache of the previous observation's order and level
        subtrees (Greg, 2026-09-22: the ingest must take minutes). The book changes by one order per record while
        pack() walked every field of every resting order on every closed group. A subtree is reused only for an
        identical field tuple (RestingOrder is mutated in place, so identity is not enough), the cache holds the
        current book only, and every other node is pack()ed as before, so the tree equals pack(observation) node
        for node and the journal bytes are unchanged."""
        orders_cache = self.__dict__.get('_packed_orders') or {}
        levels_cache = self.__dict__.get('_packed_levels') or {}
        new_orders, new_levels, items = {}, {}, []
        for key, value in observation.items():
            if key == 'orders':
                packed = []
                for order in value:
                    k = tuple(order.values())
                    node = orders_cache.get(k)
                    if node is None:
                        node = pack(order)
                    new_orders[k] = node
                    packed.append(node)
                node = ['list', packed]
            elif key == 'levels':
                sides = []
                for side, levels in value.items():
                    packed = []
                    for level in levels:
                        k = (side, level['price_raw'], tuple(level['order_ids']))
                        node = levels_cache.get(k)
                        if node is None:
                            node = pack(level)
                        new_levels[k] = node
                        packed.append(node)
                    sides.append([side, ['list', packed]])
                node = ['dict', sides]
            else:
                node = pack(value)
            items.append([key, node])
        self._packed_orders, self._packed_levels = new_orders, new_levels
        wrapped = PrePacked(observation)
        wrapped.tree = ['dict', items]
        return wrapped

    def evidence_stream(self, *, through_cursor=None):
        """Every applied event in source order. Optional bound is causal, not retention.

        Full raw fields and all original outputs are delivered, not only IDs
        or archive pointers. No availability mask discards incomplete orders.
        """
        if self._failed:
            raise ValueError("unprocessed evidence exists; cannot present a complete consumer stream")
        for entry in self.journal.entries():
            if entry["kind"] == "APPLIED":
                evidence = entry["payload"]
                if through_cursor is None or evidence["cursor"] <= through_cursor:
                    yield evidence

    def order_history(self, *, instrument_id, publisher_id, order_id, through_cursor=None):
        """All observations of the ID across members/sessions; no lifecycle pruning."""
        for evidence in self.evidence_stream(through_cursor=through_cursor):
            msg = evidence["normalized"]
            if ((msg["instrument_id"], msg["publisher_id"]) == (instrument_id, publisher_id)
                    and (msg["order_id"] == order_id or msg["action"] == "R")):
                yield evidence

    def export_state(self):
        if self._failed:
            raise ValueError("cannot checkpoint failed processing as completed")
        adapter, prefix = export_adapter_state(self.adapter), self.chain.export_state()
        if (adapter["record_count"] != prefix["next_cursor"]
                or adapter["completed_event_group_count"] != prefix["next_global_group_ordinal"]):
            raise ValueError("adapter and prefix counts disagree")
        payload = dict(schema=SCHEMA, scope_genesis_hash=self.scope.genesis_hash(),
                       implementation=self.identity, adapter=adapter, prefix=prefix,
                       sessions=[[iid, session] for iid, session in sorted(self._sessions.items())],
                       journal_count=self.journal.count, journal_hash=self.journal.head_hash)
        return {**payload, "state_hash": evidence_hash(payload)}

    @classmethod
    def restore(cls, scope, journal_path, state, *, expected_hash):
        """The expected hash comes from the trusted outer checkpoint receipt."""
        state = unpack(pack(state))
        keys = {"schema", "scope_genesis_hash", "implementation", "adapter", "prefix",
                "sessions", "journal_count", "journal_hash", "state_hash"}
        if type(state) is not dict or set(state) != keys:
            raise ValueError("invalid full-evidence checkpoint fields")
        body = {k: v for k, v in state.items() if k != "state_hash"}
        if (state["state_hash"] != expected_hash or evidence_hash(body) != expected_hash
                or state["schema"] != SCHEMA or state["scope_genesis_hash"] != scope.genesis_hash()
                or state["implementation"] != implementation_identity()):
            raise ValueError("full-evidence checkpoint identity mismatch")
        builder = cls.__new__(cls)
        builder.scope, builder.identity = scope, implementation_identity()
        builder.chain = RecordPrefixChain.restore(scope, state["prefix"])
        builder.adapter = restore_adapter_state(state["adapter"])
        builder._sessions = dict(state["sessions"])
        builder._failed = False
        builder.journal = EvidenceJournal(journal_path)
        try:
            builder.journal.verify(count=state["journal_count"], head_hash=state["journal_hash"])
            if builder.journal.count != 2 * builder.chain.next_cursor:
                raise ValueError("checkpoint does not account for every input and applied record")
            if builder.export_state() != state:
                raise ValueError("checkpoint state is inconsistent or noncanonical")
        except Exception:
            builder.journal.close()
            raise
        return builder
