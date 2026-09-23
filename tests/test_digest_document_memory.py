"""Whole writer resource regression, separate from table/source unit measurements."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

BOX = Path(__file__).resolve().parents[1] / 'deploy/aws/box'


@pytest.mark.skipif(sys.platform != 'linux', reason='Linux ru_maxrss byte conversion')
def test_complete_digest_row_and_dictionary_growth_has_bounded_memory(tmp_path, capsys):
    # These fixed-overhead tolerances are regression guards, not capacity claims.
    # Build pinned fixtures before tracing so only the complete writer is measured.
    code = r'''
import hashlib, json, pathlib, resource, sqlite3, sys, tracemalloc
sys.path.insert(0, sys.argv[1])
from frankie_box_digest_document import write_digest
n = int(sys.argv[2])
root = pathlib.Path(sys.argv[3]); root.mkdir()
layer = root/'layer.json'
with layer.open('w', encoding='utf-8') as output:
    output.write('{"status":"derived","producer":"fixture","member_rows":[')
    for i in range(n):
        if i: output.write(',')
        json.dump(dict(group_index=i, word='entry-%08d' % (i % (n//2)),
                       ts_recv_ns=1633298403300150001+i), output,
                  separators=(',', ':'), sort_keys=True)
    output.write(']}')
with layer.open('rb') as stream:
    layer_sha = hashlib.file_digest(stream, 'sha256').hexdigest()
pin = dict(path=str(layer), bytes=layer.stat().st_size, sha256=layer_sha)
receipt = dict(rows=dict(path='fixture', count=n, kinds={'INPUT':n}, head='a'*64,
                        head_is_request_source_hash=True),
               input_records=n, legacy_rows=0, f_last_groups=n, failure_count=0,
               pin_group='resource-fixture',
               layers={'calculation':dict(pin, status='derived', producer='fixture')})
tracemalloc.start()
proof = write_digest(root/'digest.md', receipt, {}, iter(()), iter(()), iter(()),
                     [], 0, [], [], bedrock_entries={'calculation':pin},
                     scratch_directory=root/'scratch')
_, peak = tracemalloc.get_traced_memory()
tracemalloc.stop()
assert proof['verified']
table_index = next(i for i,t in enumerate(proof['tables']) if t['name']=='bedrock.members')
assert proof['tables'][table_index]['rows'] == n
# Prove the fixture really exercised a growing repeated-string dictionary rather
# than shrinking into constants or previous-cell markers.
with sqlite3.connect(root/'scratch'/('table-%04d' % table_index)/'table.sqlite') as db:
    distinct = db.execute('SELECT count(*) FROM frequency WHERE number IS NOT NULL').fetchone()[0]
assert distinct == n//2, distinct
with (root/'digest.md').open('rb') as stream:
    assert hashlib.file_digest(stream, 'sha256').hexdigest() == proof['sha256']
assert (root/'digest.md').stat().st_size == proof['bytes']
assert (root/'scratch'/'publication-receipt.json').is_file()
print(json.dumps(dict(rows=n, distinct=distinct, python_peak_bytes=peak,
                     rss_peak_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
                     output_bytes=proof['bytes'])))
'''
    records = []
    for rows in (4000, 40000):
        result = subprocess.run([sys.executable, '-c', code, str(BOX), str(rows), str(tmp_path/str(rows))],
                                check=True, capture_output=True, text=True, timeout=300)
        records.append(json.loads(result.stdout))
    small, large = records
    with capsys.disabled():
        print('\nDIGEST_DOCUMENT_MEMORY_REGRESSION ' + json.dumps(records), flush=True)
    assert large['rows'] == 10 * small['rows']
    assert large['distinct'] == 10 * small['distinct']
    assert large['output_bytes'] > 5 * small['output_bytes']
    assert large['python_peak_bytes'] <= small['python_peak_bytes'] + 4 * 1024 * 1024
    assert large['rss_peak_bytes'] <= small['rss_peak_bytes'] + 24 * 1024 * 1024
