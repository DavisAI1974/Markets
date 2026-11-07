import hashlib
import sqlite3
import unittest

from export_oct17_liquidity import DAY, load_codec, project, verified_entries


def book(bids, asks):
    result = dict(instrument_id=7, integrity={'sequence_gap': 1}, orders=[], levels={'B': [], 'A': []})
    for side, levels in [('B', bids), ('A', asks)]:
        for price, size in levels:
            oid = len(result['orders']) + 1
            result['orders'].append(dict(order_id=oid, side=side, price_raw=price, size=size))
            result['levels'][side].append(dict(price_raw=price, order_ids=[oid]))
    return result


def fixture():
    rows = []
    clock = 1697522400000000001
    for cursor, (action, group, cursors, observation) in enumerate([
        ('T', None, None, None),
        ('F', 0, [0, 1], book([(3002, 1), (3001, 9)], [(3003, 10)])),
        ('C', 1, [2], book([(3001, 9)], [(3003, 10)])),
    ]):
        raw = dict(action=action, source_value=b'\x01')
        source = dict(session_id=DAY, source_member_index=0, cursor=cursor)
        receipt = None if group is None else dict(global_group_ordinal=group, instrument_id=7,
            record_cursors=cursors, terminal_ts_recv_ns=clock + cursor)
        rows.append(('INPUT', dict(source, record=raw)))
        rows.append(('APPLIED', dict(source, input_ordinal=2 * cursor, raw_record=raw,
            normalized=dict(action=action, instrument_id=7, ts_event_ns=clock + cursor - 2,
                            ts_recv_ns=clock + cursor), effect={'missing_reference': cursor == 2},
            order_before=None, order_after=None, integrity={'sequence_gap': 1},
            observation=observation, receipt=receipt)))
    return rows


class Oct17ExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.codec, pack = load_codec()
        cls.pack = staticmethod(pack)

    def compact_reader(self):
        codec = self.codec
        rows = []
        head = codec.GENESIS_HASH
        for i, (kind, payload) in enumerate(fixture()):
            envelope = dict(schema=codec.SCHEMA, ordinal=i, previous_hash=head, kind=kind, payload=payload)
            body = codec.canonical_tagged_bytes(self.pack(envelope))
            head = hashlib.sha256(codec.DIGEST_PREFIX + body).hexdigest()
            rows.append((i, kind, body, head))
        reader = codec.CompactReader.__new__(codec.CompactReader)
        reader.db = sqlite3.connect(':memory:')
        reader.count, reader.head_hash = len(rows), head
        reader.db.execute('CREATE TABLE seal (format, count, head)')
        reader.db.execute('INSERT INTO seal VALUES (?,?,?)', (codec.FORMAT, reader.count, head))
        reader.db.execute('CREATE TABLE blocks (start, count, body, sha256)')
        for start in (0, 3):
            block = codec.encode_block(rows[start:start + 3])
            reader.db.execute('INSERT INTO blocks VALUES (?,?,?,?)', (start, 3, block, hashlib.sha256(block).hexdigest()))
        return reader

    def test_verified_block_stream_preserves_raw_trade_and_nontrade_refs(self):
        with self.compact_reader() as reader:
            rows = list(project(verified_entries(reader, self.codec), self.pack, expected_records=3, expected_groups=2))
        self.assertEqual(rows[0]['source_action_refs'], [[0, 0, 1], [1, 2, 3]])
        retained = rows[0]['original_trade_and_missing_reference_rows'][0]
        self.assertEqual(retained['receive_ns'], 1697522400000000001)
        self.assertEqual(rows[0]['known_by_ns'], 1697522400000000002)
        self.assertEqual(retained['original_tagged'][1][0], ['raw_record', self.pack(fixture()[0][1]['record'])])
        self.assertEqual(rows[1]['original_trade_and_missing_reference_rows'][0]['source_action'], 'C')
        self.assertEqual(rows[1]['source_observation_integrity'], {'sequence_gap': 1})

    def test_fixed_prices_use_full_observation_without_inventing_an_open(self):
        with self.compact_reader() as reader:
            old, new = project(verified_entries(reader, self.codec), self.pack, expected_records=3, expected_groups=2)
        self.assertIsNone(old['sides']['B']['current_best_size_in_prior_full_book'])
        self.assertEqual(new['sides']['B']['prior_best_size_in_current_full_book'], 0)
        self.assertEqual(new['sides']['B']['current_best_size_in_prior_full_book'], 9)
        self.assertEqual(new['sides']['B']['first_ten'], [[3001, 9, 1]])

    def test_bad_block_and_unfinished_session_cannot_complete(self):
        with self.compact_reader() as reader:
            reader.db.execute("UPDATE blocks SET sha256='wrong' WHERE start=3")
            with self.assertRaisesRegex(ValueError, 'block identity'):
                list(project(verified_entries(reader, self.codec), self.pack, expected_records=3, expected_groups=2))
        with self.compact_reader() as reader:
            with self.assertRaisesRegex(ValueError, 'record/group totals'):
                list(project(verified_entries(reader, self.codec), self.pack, expected_records=4, expected_groups=2))


if __name__ == '__main__':
    unittest.main()
