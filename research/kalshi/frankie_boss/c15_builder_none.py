"""C15Builder with no full-book observation at a group close: the experiment's journal (Greg, 2026-09-29: "Do 1-5 now",
item 4; "We can break my gold standard").

A subclass, so c15_builder.py keeps its bytes and the builder identity (c15_registry.implementation_identity hashes
c15_builder.py) that Frankie's full-run paths pin stays the same (the read-only review of 959c5e12, finding 10). apply()
is c15_builder.C15Builder.apply line for line except the observation: always None, never composed, never spliced. Every
other field of the INPUT and APPLIED entries is the parent's. Nothing else is overridden.
"""
from dataclasses import asdict

try:
    from .c15_builder import AppliedEvidence, C15Builder
    from .c15_journal import pack, unpack
    from .c15_observer import order_rank
    from .causal_prefix_records import RecordInput
except ImportError:   # flat import
    from c15_builder import AppliedEvidence, C15Builder
    from c15_journal import pack, unpack
    from c15_observer import order_rank
    from causal_prefix_records import RecordInput
from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import ADAPTER_REVISION, InstrumentBook


class C15BuilderNoObservation(C15Builder):
    observation_mode = 'none'

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
            # the experiment's journal: no full-book copy at a group close (observation None); the book is the INPUT
            # records replayed from opening-book.c15.json (observation_replay.py rebuilds it for a reader that needs it)
            observation = None
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
            self.journal.append("APPLIED", evidence)
            self._sessions[msg.instrument_id] = session_id
            return AppliedEvidence(frame, legacy, receipt, observation, evidence)
        except Exception as exc:
            self._failed = True
            self.journal.append("FAILED", dict(input_ordinal=input_ordinal, cursor=cursor,
                                               error_type=type(exc).__name__, error=str(exc)))
            raise
