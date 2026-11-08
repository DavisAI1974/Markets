"""Check ROOT frame, trade and structure membership against raw tape in SQLite."""

import base64
from collections import Counter, defaultdict
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

CODE = Path(__file__).resolve().parent
sys.path.insert(0, str(CODE))
from research.kalshi.frankie_boss.c15_journal import unpack

def rows(path, fields=None):
    with path.open('rb') as stream:
        for line in stream:
            tree = json.loads(line)
            if fields is None:
                yield unpack(tree)
            else:
                if tree[0] != 'dict':
                    raise ValueError('ROOT frame must be a tagged mapping')
                yield {key: unpack(value) for key, value in tree[1] if key in fields}

def family_from_wire(records):
    actions = [r['action'] for r in records]
    sides = [r['side'] for r in records]
    prices = {r['price'] for r in records if abs(r['price']) < 9_000_000_000_000_000_000}
    ids = {r['order_id'] for r in records if r['order_id']}
    filled, cancelled, modified = (
        {r['order_id'] for r in records if r['action'] == action and r['order_id']}
        for action in ('F', 'C', 'M')
    )
    descriptor = dict(
        action_string=''.join(actions), side_string=''.join(sides),
        action_counts=dict(Counter(actions)), side_counts=dict(Counter(sides)),
        terminal_action=actions[-1], terminal_side=sides[-1],
        component_count=len(records), distinct_price_count=len(prices),
        distinct_order_id_count=len(ids), fill_disposition_signature=dict(
            fill_id_count=len(filled), cancelled_fill_id_count=len(filled & cancelled),
            modified_fill_id_count=len(filled & modified),
            same_id_cancel_modify_count=len(filled & cancelled & modified),
            unresolved_fill_id_count=len(filled - cancelled - modified),
        ),
    )
    encoded = json.dumps(descriptor, sort_keys=True, separators=(',', ':')).encode()
    return 'ow-' + hashlib.sha256(encoded).hexdigest()[:20]


def check(day, result, output):
    receipt = json.loads((result / 'work/derive.json').read_bytes())
    declared = json.loads((CODE / f'{day}-input-receipt.json').read_bytes())
    source = CODE / f'{day}-input.jsonl'
    payload = source.read_bytes()
    if hashlib.sha256(payload).hexdigest() != declared['sha256']:
        raise ValueError('bounded tape extraction differs from its recorded hash')
    tape = [json.loads(line) for line in payload.splitlines()]
    if len(tape) != declared['rows'] or len(tape) != receipt['input_records']:
        raise ValueError('source and producer counts differ')
    if output.exists():
        raise FileExistsError(output)
    spools = result / 'work/derived/.rows'
    db = sqlite3.connect(output)
    db.executescript("""
        CREATE TABLE frames(input_cursor INTEGER PRIMARY KEY, instrument_id INTEGER NOT NULL,
            receive_ns INTEGER NOT NULL, event_ns INTEGER NOT NULL, members INTEGER NOT NULL) STRICT;
        CREATE TABLE trades(input_index INTEGER PRIMARY KEY, close_index INTEGER NOT NULL REFERENCES frames,
            receive_ns INTEGER NOT NULL, event_ns INTEGER NOT NULL, price_raw INTEGER NOT NULL,
            size INTEGER NOT NULL) STRICT;
        CREATE TABLE structures(input_cursor INTEGER PRIMARY KEY REFERENCES frames, family TEXT NOT NULL) STRICT;
        CREATE VIEW family_first AS SELECT family, min(input_cursor) AS input_cursor FROM structures GROUP BY family;
        PRAGMA foreign_keys=ON;
    """)
    pending, expected = defaultdict(list), {}
    for index, record in enumerate(tape):
        iid = record['instrument_id']
        pending[iid].append(index)
        if record['flags'] & 128:
            expected[index] = pending.pop(iid)
    with db:
        seen = set()
        frame_fields = {'input_cursor', 'input_record_indices', 'input_records', 'ts_recv_ns', 'ts_event_ns'}
        for frame in rows(spools / 'frames.jsonl', frame_fields):
            index = frame['input_cursor']
            indices = expected[index]
            if frame['input_record_indices'] != indices:
                raise ValueError(f'group members differ at {index}')
            close = tape[index]
            if (frame['ts_recv_ns'], frame['ts_event_ns']) != (close['ts_recv'], close['ts_event']):
                raise ValueError(f'group clocks differ at {index}')
            members = frame['input_records']
            if len(members) != len(indices):
                raise ValueError(f'group length differs at {index}')
            for member_index, member in zip(indices, members):
                raw = tape[member_index]
                if (member['dbn_wire_bytes'] != base64.b64decode(raw['dbn_wire_b64']) or
                    any(member[key] != val for key, val in raw.items() if key != 'dbn_wire_b64')):
                    raise ValueError(f'group wire or values differ at {member_index}')
            db.execute('INSERT INTO frames VALUES (?,?,?,?,?)',
                       (index, close['instrument_id'], close['ts_recv'], close['ts_event'], len(indices)))
            seen.add(index)
        if seen != expected.keys():
            raise ValueError('frame coverage differs')
        seen_trades = set()
        for trade in rows(spools / 'prices.jsonl'):
            provenance = trade['provenance']
            index, close_index = provenance['input_index'], provenance['group_close_input_index']
            raw = tape[index]
            if (raw['action'] != 'T' or index not in expected[close_index] or
                (raw['ts_recv'] / 1e9, raw['ts_event'] / 1e9, raw['size'], raw['price']) !=
                (trade['ts_recv'], trade['ts_event'], trade['size'], Decimal(str(trade['price'])) * 1_000_000_000)):
                raise ValueError(f'trade clock, price or membership differs at {index}')
            db.execute('INSERT INTO trades VALUES (?,?,?,?,?,?)',
                       (index, close_index, raw['ts_recv'], raw['ts_event'], raw['price'], raw['size']))
            seen_trades.add(index)
        all_closed_trades = {i for v in expected.values() for i in v if tape[i]['action'] == 'T'}
        if seen_trades != all_closed_trades:
            raise ValueError('closed trade coverage differs')
        for structure in rows(spools / 'structures.jsonl'):
            provenance = structure['provenance']
            index = provenance['input_cursor']
            family = family_from_wire([tape[i] for i in expected[index]])
            if (provenance['input_record_indices'] != expected[index] or
                structure['candidate_family_id'] != family):
                raise ValueError(f'structure identity or members differ at {index}')
            db.execute('INSERT INTO structures VALUES (?,?)', (index, structure['candidate_family_id']))
        counts = {key: db.execute(f'SELECT count(*) FROM {key}').fetchone()[0]
                  for key in ('frames','trades','structures','family_first')}
        if counts['structures'] != counts['frames']:
            raise ValueError('structure coverage differs')
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('SQLite integrity failed')
    db.close()
    return dict(input_records=len(tape), closed_group_members=sum(map(len, expected.values())),
                open_group_members=sum(map(len, pending.values())), **counts)

if __name__ == '__main__':
    day, result, output = sys.argv[1:]
    print(json.dumps(check(day, Path(result), Path(output)), indent=2))