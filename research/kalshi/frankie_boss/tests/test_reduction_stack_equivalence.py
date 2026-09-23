"""The ingestion reduction stack changes no bytes: each change is pinned to the output of the code it replaced.

1. pack(): the single-pass form equals the original recursive form on every accepted value and
   refuses the same values.
2. observe_book(): the flat copy equals asdict on the resting-order dataclass.
3. encode_block(): repr dedup keys produce the identical block bytes as canonical-byte keys.
4. CompactBuildJournal with workers: the container equals the inline one and the raw journal.
"""
import struct
from dataclasses import asdict
from types import MappingProxyType

import pytest

from c15_journal import EvidenceJournal, FrozenList, pack, unpack
from compact_build_journal import CompactBuildJournal
from compact_journal import CompactReader, encode_block
from verified_journal_reader import canonical_tagged_bytes
from c15_observer import IncrementalObservation, observe_book
from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import RestingOrder


def _reference_pack(value):
    """The original recursive pack, verbatim, kept here as the oracle."""
    if value is None:
        return ["null"]
    if type(value) is bool:
        return ["bool", value]
    if type(value) is int:
        return ["int", value]
    if type(value) is float:
        return ["float64", struct.pack(">d", value).hex()]
    if type(value) is str:
        return ["str", value]
    if type(value) is bytes:
        return ["bytes", value.hex()]
    if type(value) in (list, tuple, FrozenList):
        return ["tuple" if type(value) is tuple else "list", [_reference_pack(v) for v in value]]
    if type(value) in (dict, MappingProxyType) and all(type(k) is str for k in value):
        return ["dict", [[key, _reference_pack(val)] for key, val in value.items()]]
    raise ValueError("evidence must use explicit mappings, sequences, bytes and primitive values")


RICH = dict(i=0, n=-(2**70), t=True, f=False, z=None, x=-0.0, nan=float('nan'), inf=float('inf'),
            s='ünïcode "quoted"', b=b'\x00\xff', l=[1, 2.5, 'a', None, [True]], tu=(1, (2, 3)),
            fl=FrozenList([1, {'k': 'v'}]), m=MappingProxyType({'a': 1}), nested={'d': {'e': [{'f': b'\x01'}]}},
            orders=[dict(instrument_id=1, order_id=10**18 + k, side='B', price_raw=3100000000 + k, size=7,
                         priority_recv_ns=5, last_update_recv_ns=6, priority_sequence=k) for k in range(40)])


def test_pack_equals_the_original_recursive_form_and_refuses_the_same():
    assert pack(RICH) == _reference_pack(RICH)
    assert unpack(pack(RICH))['tu'] == (1, (2, 3))
    for bad in ({1: 'int key'}, {('t',): 1}, object(), {'ok': [set()]}):
        with pytest.raises(ValueError, match='explicit mappings'):
            pack(bad)
        with pytest.raises(ValueError, match='explicit mappings'):
            _reference_pack(bad)


def test_observe_book_flat_copy_equals_asdict():
    order = RestingOrder(instrument_id=1, order_id=2, side='B', price_raw=3, size=4, priority_recv_ns=5,
                         last_update_recv_ns=6, priority_sequence=7)
    assert dict(vars(order)) == asdict(order) and list(dict(vars(order))) == list(asdict(order))

    class Book:
        instrument_id = 1
        orders = {2: order, 1: RestingOrder(1, 1, 'A', 9, 1, 1, 1, 1)}
        levels = {'B': {3: [2]}, 'A': {9: [1]}}
        integrity = {'ok': True}
        last_sequence = 7; last_recv_ns = 6; last_event_ns = 5
    observed = observe_book(Book())
    assert observed['orders'] == [asdict(Book.orders[1]), asdict(Book.orders[2])]
    observed['orders'][0]['size'] = 99                       # a copy, never the live order
    assert Book.orders[1].size == 1


def test_incremental_observation_keeps_exact_level_order_without_resorting():
    order_a = RestingOrder(1, 2, 'B', 3, 4, 5, 6, 7)
    order_b = RestingOrder(1, 3, 'B', 5, 4, 5, 6, 8)

    class Book:
        instrument_id = 1
        orders = {2: order_a, 3: order_b}
        levels = {'B': {3: [2], 5: [3]}, 'A': {}}
        integrity = {'ok': True}
        last_sequence = 8; last_recv_ns = 6; last_event_ns = 5

    composer = IncrementalObservation(Book())
    assert composer.sorted_prices == {'B': [5, 3], 'A': []}
    before = composer.reference()
    order_a.size = 9
    composer.note(2, dict(vars(order_a), size=4), order_a, 'B', 3)
    assert composer.canonical() == composer.reference()
    assert composer.canonical() != before
    assert composer.sorted_prices == {'B': [5, 3], 'A': []}

    del composer.book.orders[3]
    composer.book.levels['B'].pop(5)
    composer.note(3, dict(vars(order_b)), None, 'B', 5)
    assert composer.sorted_prices == {'B': [3], 'A': []}
    assert composer.canonical() == composer.reference()


def test_encode_block_repr_keys_emit_identical_bytes(tmp_path):
    journal = EvidenceJournal(tmp_path / 'j.sqlite', create=True)
    shared = [dict(instrument_id=1, order_id=k, side='B', price_raw=100 + k, size=k, priority_recv_ns=1,
                   last_update_recv_ns=1, priority_sequence=k) for k in range(30)]
    for i in range(8):
        journal.append('APPLIED', dict(cursor=i, observation=dict(orders=shared[: 20 + i % 3] + [dict(shared[0], size=i)])))
    journal.close()
    import sqlite3
    with sqlite3.connect(tmp_path / 'j.sqlite') as db:
        rows = db.execute('SELECT ordinal,kind,body,digest FROM entries ORDER BY ordinal').fetchall()
    rows = [tuple(r) for r in rows]

    def reference(rows):                                     # the previous encoder, canonical-byte keys
        import json, zlib
        from compact_journal import FORMAT, _orders
        dictionary, lookup, records = [], {}, []
        for ordinal, kind, body, digest in rows:
            tree = json.loads(body); orders, indices = _orders(tree), None
            if orders is not None:
                indices = []
                for order in orders[1]:
                    key = canonical_tagged_bytes(order)
                    if key not in lookup:
                        lookup[key] = len(dictionary); dictionary.append(order)
                    indices.append(lookup[key])
                orders[1] = []
            records.append([ordinal, kind, tree, indices, digest, len(body)])
        raw = canonical_tagged_bytes([FORMAT, dictionary, records])
        c = zlib.compressobj(6, zlib.DEFLATED, 31)
        return c.compress(raw) + c.flush()
    assert encode_block(rows) == reference(rows)
    assert len({len(rows)}) == 1


def test_worker_pool_journal_equals_inline_and_raw(tmp_path):
    payloads = [dict(cursor=i, observation=dict(orders=[dict(instrument_id=1, order_id=k, side='B', price_raw=k, size=1,
                priority_recv_ns=1, last_update_recv_ns=1, priority_sequence=k) for k in range(25)]), pad='x' * 500) for i in range(40)]
    raw = EvidenceJournal(tmp_path / 'raw.sqlite', create=True)
    inline = CompactBuildJournal(tmp_path / 'inline.sqlite', block_bytes=8192)
    pooled = CompactBuildJournal(tmp_path / 'pooled.sqlite', block_bytes=8192, workers=2)
    try:
        for i, payload in enumerate(payloads):
            kind = 'INPUT' if i % 2 == 0 else 'APPLIED'
            digests = {raw.append(kind, payload), inline.append(kind, payload), pooled.append(kind, payload)}
            assert len(digests) == 1
        assert (pooled.count, pooled.head_hash) == (raw.count, raw.head_hash)
        inline.seal(); pooled.seal()
        assert pooled.worker_cpu_seconds >= 0.0 and pooled.writer.flushed_bytes == inline.writer.flushed_bytes
    finally:
        raw.close(); inline.close(); pooled.close()
    import sqlite3
    for name in ('inline.sqlite', 'pooled.sqlite'):
        with CompactReader(tmp_path / name, expected_count=raw.count, expected_head_hash=raw.head_hash) as reader:
            rows = [tuple(r) for r in reader.rows()]
        with sqlite3.connect(tmp_path / 'raw.sqlite') as db:
            assert rows == [tuple(r) for r in db.execute('SELECT ordinal,kind,body,digest FROM entries ORDER BY ordinal')]
    with sqlite3.connect(tmp_path / 'inline.sqlite') as a, sqlite3.connect(tmp_path / 'pooled.sqlite') as b:
        assert a.execute('SELECT start,count,sha256,previous,head FROM blocks ORDER BY start').fetchall() == \
            b.execute('SELECT start,count,sha256,previous,head FROM blocks ORDER BY start').fetchall()
