"""Build the group-close arrays from the reconstructed tape (replaces the retained groups.jsonl.gz as the source, so any date works).
Usage: python3 -I c01b_groups_from_recon.py <date>
A group closes at a record with F_LAST (flags & 128); it is known at that record's ts_recv; its touch is the book after the record applies.
Only two-sided groups (best bid and best ask both present) are kept, and the touch must not be locked/crossed for the spread regimes;
locked/crossed groups are KEPT in the arrays (flag `lockcross`) and counted in the printed receipt, so nothing is dropped silently.
Prices are in raw 1e-9 units (index * 1e6).  Fields mirror c01_load_groups.py (ord, recv_ns, bid_px, bid_sz, bid_n, ask_px, ask_sz, ask_n);
rec_idx (position of the closing record in the recon table) is a provenance coordinate, never used in the math."""
import sys; sys.path.insert(0, '.')   # cwd is this code directory, not a data directory
import numpy as np, pandas as pd
from odcfg import *
d = date_arg(); R = pd.read_parquet(recon(d))
NPX = 10001
last = (R['flags'].to_numpy().astype('int64') & 128) > 0
i = np.where(last)[0]
bb = R.bb_a.to_numpy()[i]; ba = R.ba_a.to_numpy()[i]
two = (bb >= 0) & (ba < NPX)
i, bb, ba = i[two], bb[two], ba[two]
ts = R.ts_recv.astype('int64').to_numpy()[i]
out = dict(ord=np.arange(len(i)), rec_idx=i, recv_ns=ts,
           bid_px=bb.astype(np.int64) * 1_000_000, ask_px=ba.astype(np.int64) * 1_000_000,
           bid_sz=R.bsz_a.to_numpy()[i], ask_sz=R.asz_a.to_numpy()[i], bid_n=R.bn_a.to_numpy()[i], ask_n=R.an_a.to_numpy()[i],
           lockcross=(ba <= bb))
np.savez_compressed(groups(d), **out)
print(d, 'F_LAST records', int(last.sum()), '| two-sided groups kept', len(i), '| one-sided/empty dropped', int(last.sum() - len(i)),
      '| locked or crossed kept (flagged)', int((ba <= bb).sum()), '| recv monotone', bool((np.diff(ts) >= 0).all()))
