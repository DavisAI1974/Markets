"""The full-book observation of an 'observation none' journal, rebuilt at read time (Greg, 2026-09-29: "Do 1-5 now",
item 4: the experiment's journal stores no full-book copy at a group close; a reader that needs it rebuilds it here).

A journal written with observation mode 'none' carries every INPUT record and every APPLIED entry with observation None.
The observation the full-mode builder would have stored at a group close is observe_book(book) of the book right after
that record, where the book is the day's opening book (opening-book.c15.json beside the journal, sha256 in the
ingestion receipt) with every INPUT record applied in order. This generator replays exactly that and puts the
observation back into each APPLIED payload that closes a group (receipt not None); nothing else in an entry changes.
The pinned teacher (c15_teacher_r3.py) reads e['observation'] and is not edited: the teacher-only step feeds it these
entries instead of the stored ones (swap, never edit). The values are the book's; the key ORDER of the integrity counter
map may differ from a full-mode run's stored bytes, because the opening book is restored from its canonical export.
"""
try:
    from .c15_observer import observe_book
    from .mbo_resume_state import restore_adapter_state
except ImportError:   # flat import
    from c15_observer import observe_book
    from mbo_resume_state import restore_adapter_state
from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import InstrumentBook


def with_observations(entries, opening_book_state, *, member_sha256):
    """entries: verified envelopes in order (dict with kind and payload). opening_book_state: the adapter state of
    opening-book.c15.json (unpacked). member_sha256: the scope's member sha256 by member index (the builder normalises
    with it). Yields the envelopes, each group-closing APPLIED payload with its observation rebuilt."""
    adapter = restore_adapter_state(opening_book_state)
    adapter.record_count = adapter.completed_event_group_count = 0
    book = None
    for entry in entries:
        kind, payload = entry['kind'], entry['payload']
        if kind == 'INPUT':
            record = payload['record']
            msg = adapter.normalize(record, payload.get('raw_symbol'), payload.get('source_dbn_object'),
                                    member_sha256[payload['source_member_index']])
            book = adapter.books.setdefault(msg.instrument_id, InstrumentBook(msg.instrument_id))
            book.apply(msg)
        elif kind == 'APPLIED':
            if payload.get('observation') is not None:
                raise ValueError('this entry already carries its observation (a full-mode journal): nothing to rebuild')
            if payload.get('receipt') is not None:
                entry = dict(entry, payload=dict(payload, observation=observe_book(book)))
        yield entry
