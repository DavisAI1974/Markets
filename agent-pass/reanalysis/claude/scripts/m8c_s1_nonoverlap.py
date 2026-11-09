"""M8c: non-overlapping check for the +1 s response: condition on book events in second +1 after a midpoint change, measure the midpoint from +1 to +20
(so the event that produced the +1 s quote state is excluded from the outcome). Reads the native paths again (0487d83)."""
import pandas as pd, numpy as np, json
from common import *
out = {}
for day in DAYS:
    p = pd.read_csv(NATIVE / f"{day}-paths.csv.gz", low_memory=False).sort_values(["candidate_id", "kind", "relative_s"]).reset_index(drop=True)
    p["mid"] = (p.bid + p.ask) / 2; key = (p.candidate_id + "|" + p.kind).values
    dm = p.groupby(["candidate_id", "kind"], sort=False).mid.diff().values; d = np.sign(np.nan_to_num(dm)).astype(int)
    mid = p.mid.values; n = len(p); idx = np.where(d != 0)[0]
    A = {c: p[c].values for c in ["add_B", "add_A", "cancel_B", "cancel_A", "fill_B", "fill_A"]}
    recs = []
    for i in idx:
        if i + 20 >= n or key[i + 20] != key[i]: continue
        dd = d[i]; tow = "A" if dd > 0 else "B"; awy = "B" if dd > 0 else "A"
        recs.append(dict(kind=key[i].split("|")[1], m1_20=(mid[i + 20] - mid[i + 1]) / 0.001 * dd, m0_1=(mid[i + 1] - mid[i]) / 0.001 * dd,
                         a_t=A[f"add_{tow}"][i + 1], a_a=A[f"add_{awy}"][i + 1], c_t=A[f"cancel_{tow}"][i + 1], c_a=A[f"cancel_{awy}"][i + 1], f_t=A[f"fill_{tow}"][i + 1], f_a=A[f"fill_{awy}"][i + 1]))
    x = pd.DataFrame(recs); res = {}
    def sc(s): return dict(n=int(len(s)), up=int((s > 0).sum()), flat=int((s == 0).sum()), down=int((s < 0).sum()))
    for kind in ["candidate", "control1", "control2"]:
        k = x[x.kind == kind]
        res[kind] = dict(all_1_20=sc(k.m1_20), moved_in_s1_reversal=sc(k[k.m0_1 < 0].m1_20), moved_in_s1_continuation=sc(k[k.m0_1 > 0].m1_20), flat_in_s1=sc(k[k.m0_1 == 0].m1_20),
                         s1_adds_toward_gt=sc(k[k.a_t > k.a_a].m1_20), s1_adds_away_gt=sc(k[k.a_t < k.a_a].m1_20), s1_cancel_toward_gt=sc(k[k.c_t > k.c_a].m1_20), s1_cancel_away_gt=sc(k[k.c_t < k.c_a].m1_20),
                         s1_fill_toward_any=sc(k[k.f_t > 0].m1_20), s1_fill_away_any=sc(k[k.f_a > 0].m1_20),
                         # within flat-in-s1 only (no mechanical quote move yet): does the s1 book response lead the 1->20 price?
                         flat_s1_adds_toward_gt=sc(k[(k.m0_1 == 0) & (k.a_t > k.a_a)].m1_20), flat_s1_adds_away_gt=sc(k[(k.m0_1 == 0) & (k.a_t < k.a_a)].m1_20),
                         flat_s1_cancel_toward_gt=sc(k[(k.m0_1 == 0) & (k.c_t > k.c_a)].m1_20), flat_s1_cancel_away_gt=sc(k[(k.m0_1 == 0) & (k.c_t < k.c_a)].m1_20),
                         flat_s1_fill_toward_any=sc(k[(k.m0_1 == 0) & (k.f_t > 0)].m1_20), flat_s1_fill_away_any=sc(k[(k.m0_1 == 0) & (k.f_a > 0)].m1_20), flat_s1_quiet=sc(k[(k.m0_1 == 0) & (k.a_t + k.a_a + k.c_t + k.c_a + k.f_t + k.f_a == 0)].m1_20))
    out[day] = res
    print(day, {kind: {kk: (v["up"], v["down"]) for kk, v in res[kind].items()} for kind in ["candidate", "control1"]})
json.dump(out, open(OUT / "m8_feedback_s1_nonoverlap.json", "w"), indent=1)
