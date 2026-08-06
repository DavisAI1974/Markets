"""Is session_b_share structurally sub-0.50 because of how it is NORMALIZED?

_tape_day_stats does:  buys = sum(size where side == "B");  tot = sum(size);  b_share = buys/tot
If a material share of volume carries a side that is neither "B" nor "A", it lands in the DENOMINATOR
but can never land in the numerator - and b_share is biased LOW by construction on every session.

Any play gated on b_share >= 0.50 would then be unable to admit the up angle, on any group, ever.
That is a candidate mechanical source of a persistent DOWN lean.
"""
import os as _os
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_REPO = _os.path.dirname(_os.path.dirname(_HERE))

import gzip, json, os, glob, collections

D = _os.path.join(_REPO, "data", "nymex_cont_n0")
files = sorted(glob.glob(os.path.join(D, "NG_*.jsonl.gz")))
print(f"sessions on disk: {len(files)}")

side_vol = collections.Counter()
side_cnt = collections.Counter()
per_session = []

for p in files:
    b = a = o = 0.0
    n = 0
    with gzip.open(p, "rt") as fh:
        for line in fh:
            if '"action": "T"' not in line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("action") != "T" or r.get("price") is None:
                continue
            z = float(r.get("size") or 0)
            s = r.get("side")
            n += 1
            side_cnt[str(s)] += 1
            if s == "B":
                b += z
            elif s == "A":
                a += z
            else:
                o += z
            side_vol[str(s)] += z
    tot = b + a + o
    if tot <= 0:
        continue
    per_session.append({
        "date": os.path.basename(p)[3:11],
        "n": n,
        "b_share_AS_COMPUTED": b / tot,                       # what the harness serves
        "b_share_TWO_SIDED": b / (b + a) if (b + a) > 0 else None,   # buy vs sell only
        "unsided_frac": o / tot,
    })

print(f"\n=== side field: volume share across {len(per_session)} sessions ===")
tv = sum(side_vol.values())
for s, v in side_vol.most_common():
    print(f"  side={s!r:8} volume {v:14,.0f}  {100*v/tv:6.2f}%   trades {side_cnt[s]:10,}")

asc = [x["b_share_AS_COMPUTED"] for x in per_session]
two = [x["b_share_TWO_SIDED"] for x in per_session if x["b_share_TWO_SIDED"] is not None]
uns = [x["unsided_frac"] for x in per_session]

def stats(v, label):
    v = sorted(v)
    n = len(v)
    print(f"  {label:26} mean {sum(v)/n:.4f}  median {v[n//2]:.4f}  "
          f"min {v[0]:.4f}  max {v[-1]:.4f}  frac>=0.50 {sum(1 for x in v if x >= 0.50)/n:.3f}")

print(f"\n=== session_b_share, {len(per_session)} sessions ===")
stats(asc, "AS COMPUTED (b/total)")
stats(two, "TWO-SIDED (b/(b+a))")
stats(uns, "unsided volume frac")

print(f"\n=== the gate that matters: selector.divergence_resolution arm (b) needs b_share >= 0.50 ===")
print(f"  sessions clearing 0.50 as computed : {sum(1 for x in asc if x>=0.50)}/{len(asc)}")
print(f"  sessions clearing 0.50 two-sided   : {sum(1 for x in two if x>=0.50)}/{len(two)}")
