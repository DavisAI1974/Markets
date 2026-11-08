"""Decode one pinned GLBX.MDP3 MBO tape (.dbn.zst) into a flat parquet and print a coverage receipt.
Usage: python3 -I c00_dbn_to_parquet.py <tape.dbn.zst> <expected_sha256> <out.parquet> <receipt.json>
The tape is untrusted input: the sha256 must equal the MANIFEST value before it is decoded.
Index = ts_recv (capture clock).  Columns kept as served: ts_event, action, side, price, size, order_id, flags,
instrument_id, channel_id, sequence.  Nothing is dropped, filtered or re-ordered.  No cost assumption.
Coverage receipt: record count, snapshot records (flag 32) and their ts_recv, first/last ts_recv, instruments, per-UTC-hour record counts.
Calendar hours appear in the receipt as provenance only; no analysis step reads them as a feature."""
import hashlib, json, sys
import numpy as np, pandas as pd, databento as db
src, want, out, receipt = sys.argv[1:5]
h = hashlib.sha256(open(src, 'rb').read()).hexdigest()
assert h == want, f'sha256 mismatch {h} != {want}'
df = db.DBNStore.from_file(src).to_df(price_type='fixed', pretty_ts=False, map_symbols=False)
df.index = pd.to_datetime(df.index.astype('int64'), unit='ns', utc=True) if not np.issubdtype(df.index.dtype, np.datetime64) else df.index
df.index.name = 'ts_recv'
keep = ['ts_event', 'action', 'side', 'price', 'size', 'order_id', 'flags', 'instrument_id', 'channel_id', 'sequence']
df = df[keep]
df.to_parquet(out)
fl = df['flags'].astype('int64').to_numpy(); ts = df.index.asi8
snap = (fl & 32) > 0; last = (fl & 128) > 0
hours = pd.Series(1, index=df.index).groupby(df.index.floor('h')).sum()
rc = dict(sha256=h, records=int(len(df)), first_ts_recv=str(df.index[0]), last_ts_recv=str(df.index[-1]),
          snapshot_records=int(snap.sum()), snapshot_ts_recv_min=str(df.index[snap].min()) if snap.any() else None,
          snapshot_ts_recv_max=str(df.index[snap].max()) if snap.any() else None,
          f_last_records=int(last.sum()), instruments={int(k): int(v) for k, v in df['instrument_id'].value_counts().items()},
          actions={str(k): int(v) for k, v in df['action'].value_counts().items()},
          sides={str(k): int(v) for k, v in df['side'].value_counts().items()},
          ts_recv_monotone=bool((np.diff(ts) >= 0).all()), ts_recv_decreases=int((np.diff(ts) < 0).sum()),
          records_per_utc_hour={str(k): int(v) for k, v in hours.items()})
json.dump(rc, open(receipt, 'w'), indent=1)
print(json.dumps({k: v for k, v in rc.items() if k != 'records_per_utc_hour'}, indent=1))
print('hours with records:', len(rc['records_per_utc_hour']))
