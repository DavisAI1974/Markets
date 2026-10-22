"""Read stored causal geometry at previously selected, indexed source offsets."""
import csv
import json
import os
import pathlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor

BASE = pathlib.Path('/opt/frankie-box/work/family-research-20261022')
OUT = BASE / 'descriptive-v1'
SOURCE = pathlib.Path('/opt/frankie-box/work/experiment-teacher-rows/20231018/host-dipole-classroom-source.c15.rows.jsonl')
db = sqlite3.connect(f'file:{BASE / "alignment.sqlite"}?mode=ro', uri=True)
contexts = list(csv.DictReader((OUT / 'group_context_receipts.csv').open()))
offsets = sorted({int(r['source_offset']) for r in contexts})
index = {offset: db.execute('SELECT source_length,input_cursor,known_by_ns,row_sha256 FROM second_set_clock WHERE source_offset=?', (offset,)).fetchone() for offset in offsets}
fd = os.open(SOURCE, os.O_RDONLY)


def extract(offset):
    length, cursor, known_by, digest = index[offset]
    raw = os.pread(fd, length, offset)
    if len(raw) != length:
        raise ValueError('indexed geometry source read truncated')
    record = json.loads(raw)
    if record['key']['input_cursor'] != cursor or record['clocks']['clock_event_known_by'] != known_by:
        raise ValueError('geometry source lookup mismatch')
    return offset, {'state': record.get('dstate'), 'raw_components': record.get('raw_components'),
                    'key': record['key'], 'row_sha256_from_index': digest}


with ThreadPoolExecutor(max_workers=8) as pool:
    records = dict(pool.map(extract, offsets))
os.close(fd)
fields = ['sample_id', 'lag_s', 'cutoff_ns', 'source_ordinal', 'input_cursor',
          'source_offset', 'known_by_ns', 'age_s', 'dstate_json', 'raw_components_json',
          'source_key_json', 'row_sha256_from_index']
with (OUT / 'geometry_contexts.csv').open('w', newline='') as output:
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for context in contexts:
        record = records[int(context['source_offset'])]
        row = {key: context[key] for key in fields if key in context}
        row.update(dstate_json=json.dumps(record['state']),
                   raw_components_json=json.dumps(record['raw_components']),
                   source_key_json=json.dumps(record['key']),
                   row_sha256_from_index=record['row_sha256_from_index'])
        writer.writerow(row)
print(json.dumps({'contexts': len(contexts), 'unique_source_offsets': len(offsets),
                  'policy': 'Stored D-state only; exact validated offsets; no reconstruction or statistical rerun.'}))
