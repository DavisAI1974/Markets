"""Load the retained October 18 group-close export into flat arrays.
Usage: python3 -I c01_load_groups.py <groups.jsonl.gz> <out.npz>
Prices stay in raw 1e-9 units until used. No fee or execution assumption."""
import gzip, json, sys
import numpy as np
src, out = sys.argv[1], sys.argv[2]
cols = {k: [] for k in ['ord','first_cur','close_cur','event_ns','recv_ns','snap','reset','badclk',
                        'bid_px','bid_sz','bid_n','ask_px','ask_sz','ask_n','nprint']}
prints = []  # (group_ordinal, print dict)
with gzip.open(src, 'rt') as f:
    for line in f:
        r = json.loads(line)
        cols['ord'].append(r['group_ordinal']); cols['first_cur'].append(r['first_cursor'])
        cols['close_cur'].append(r['close_cursor']); cols['event_ns'].append(r['event_ns'])
        cols['recv_ns'].append(r['receive_ns']); cols['snap'].append(r['snapshot_member'])
        cols['reset'].append(r['reset_member']); cols['badclk'].append(r['bad_receive_clock_member'])
        b, a = r['bid'], r['ask']
        cols['bid_px'].append(b[0]); cols['bid_sz'].append(b[1]); cols['bid_n'].append(b[2])
        cols['ask_px'].append(a[0]); cols['ask_sz'].append(a[1]); cols['ask_n'].append(a[2])
        cols['nprint'].append(r['print_count'])
        for p in r['prints']:
            prints.append((r['group_ordinal'], p))
arr = {k: np.array(v) for k, v in cols.items()}
np.savez_compressed(out, **arr)
print('groups', len(arr['ord']), 'prints', len(prints))
if prints:
    print('print keys', sorted(prints[0][1].keys()))
    print(json.dumps(prints[0][1]))
    import pickle
    pickle.dump(prints, open(out.replace('.npz', '_prints.pkl'), 'wb'))
