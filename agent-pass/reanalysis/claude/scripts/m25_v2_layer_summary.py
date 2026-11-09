"""M25 (rerun v2 summary): for the realistic-exit outcome (ride_exh_end) and the fixed 60 s hold (ride_60), list every layer (derived M17 + raw MBO M23)
whose high-vs-low tertile direction is the same on all four dates, with the per-date high and low cells (up/flat/down). Also the per-layer per-date table
for ALL layers (no selection) so that weak and inconsistent layers are recorded too (brief: include everything)."""
import pandas as pd, numpy as np, json
from common import *
c17 = pd.read_csv(OUT / "m17_layer_tertile_cells.csv"); c17["source"] = "derived (Ccode life paths / Native operands)"
c23 = pd.read_csv(OUT / "m23_raw_layer_tertile_cells.csv"); c23["source"] = "raw MBO queue layer (M22)"
C = pd.concat([c17, c23], ignore_index=True)
rows = []
for (o, L, src), g in C.groupby(["outcome", "layer", "source"]):
    rec = dict(outcome=o, layer=L, source=src); dirs = []
    for d in DAYS:
        h = g[(g.day == int(d)) & (g.tertile == "high")]; l = g[(g.day == int(d)) & (g.tertile == "low")]
        if len(h) and len(l) and h.iloc[0].n > 0 and l.iloc[0].n > 0:
            h = h.iloc[0]; l = l.iloc[0]
            rec[f"high_{d}"] = f"{int(h.up)}/{int(h.flat)}/{int(h.down)}"; rec[f"low_{d}"] = f"{int(l.up)}/{int(l.flat)}/{int(l.down)}"
            dh = (h.up - h.down) / max(h.n, 1); dl = (l.up - l.down) / max(l.n, 1); rec[f"diff_{d}"] = round(float(dh - dl), 3); dirs.append(int(np.sign(dh - dl)))
    rec["n_dates"] = len(dirs); rec["consistent_direction"] = dirs[0] if len(dirs) == 4 and len(set(dirs)) == 1 and dirs[0] != 0 else 0
    rec["min_abs_diff"] = round(float(min(abs(rec[f"diff_{d}"]) for d in DAYS if f"diff_{d}" in rec)), 3) if dirs else None
    rows.append(rec)
S = pd.DataFrame(rows); S.to_csv(OUT / "m25_v2_all_layers_by_outcome.csv", index=False)
for o in ["ride_exh_end", "ride_60", "ride_300", "ride_exh"]:
    k = S[(S.outcome == o) & (S.consistent_direction != 0)].sort_values("min_abs_diff", ascending=False)
    print(o, "consistent layers:", len(k), "of", int((S.outcome == o).sum()))
    for _, r in k.iterrows(): print(f"   {r.consistent_direction:+d} {r.layer:32s} {r.source[:8]} min|diff|={r.min_abs_diff}  " + " | ".join(f"{r[f'high_{d}']} vs {r[f'low_{d}']}" for d in DAYS))
