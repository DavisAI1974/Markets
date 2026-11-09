"""M24 (look-ahead, two open items). (A) Flip vs successor: does the second the ridden window turns majority-opposite coincide with the birth of
the next archived candidate of opposite polarity (FLIP successor)? (B) The earliest-knowable population: every saturated-second cluster in Ccode's
detector ledger (cluster_first_second, knowable at decision_second = +5 s), including clusters that did NOT win the recorded birth, priced with the
raw-tape per-second midpoints (M22) and the native per-second flow (whole/native-flow-source-clocks): oriented move from the decision second to +20/+60/+300 s
and to the first fresh opposed lot; compared with the recorded-winner subset."""
import pandas as pd, numpy as np, json, pyarrow.parquet as pq
from common import *
DET = EV / "final_markets" / FR / "claude-pass-3day/crossday/detector"
PREV = {"20231002": "20231001", "20231003": "20231002", "20231017": "20231016", "20231018": "20231017"}
out = {"per_date": {}}
def sc(a):
    a = np.asarray(a, dtype=float); a = a[np.isfinite(a)]; return dict(n=int(a.size), up=int((a > 0).sum()), flat=int((a == 0).sum()), down=int((a < 0).sum()), p50=float(np.median(a)) if a.size else None)
for day in DAYS:
    # (A) flip vs successor
    lc = pd.read_csv(OUT / "m16_lookahead_lifecycle_candidates.csv"); lc = lc[lc.day == int(day)].copy()
    c1 = pd.read_csv(OUT / f"m1_candidates_{day}.csv", low_memory=False)[["candidate_id", "anchor_label_ns", "polarity"]].sort_values("anchor_label_ns")
    F = pd.read_csv(OUT / "m17_features.csv.gz"); F = F[F.day == int(day)][["row", "candidate_id"]]
    lc = lc.merge(F, on="row", how="left").merge(c1, on="candidate_id", how="left")
    births = c1.anchor_label_ns.values // 10**9; pols = c1.polarity.values
    rows = []
    for _, r in lc.iterrows():
        if pd.isna(r.anchor_label_ns): continue
        b = int(r.anchor_label_ns // 10**9); nxt = np.where(births > b)[0]
        if len(nxt) == 0: rows.append(dict(gap_next=np.nan)); continue
        j = nxt[0]; gap = births[j] - b; same = pols[j] == r.polarity
        rows.append(dict(gap_next=gap, next_is_flip=(not same), k_flip=r.k_flip_majority, flip_minus_next=(r.k_flip_majority - gap) if pd.notna(r.k_flip_majority) else np.nan))
    A = pd.DataFrame(rows); fl = A[A.next_is_flip == True]
    resA = dict(candidates=len(A), next_birth_is_FLIP=int((A.next_is_flip == True).sum()), next_birth_is_SAME=int((A.next_is_flip == False).sum()),
                flip_second_minus_next_FLIP_birth_s=dict(p10=float(fl.flip_minus_next.quantile(.1)), p25=float(fl.flip_minus_next.quantile(.25)), p50=float(fl.flip_minus_next.median()), p75=float(fl.flip_minus_next.quantile(.75)), p90=float(fl.flip_minus_next.quantile(.9))) if fl.flip_minus_next.notna().any() else None,
                flip_within_5s_of_FLIP_birth=int((fl.flip_minus_next.abs() <= 5).sum()), flip_before_FLIP_birth=int((fl.flip_minus_next < -5).sum()), flip_after_FLIP_birth=int((fl.flip_minus_next > 5).sum()))
    # (B) earliest-knowable population from the detector ledger
    led = pd.read_csv(DET / f"ledger_saturated_seconds_{day}.csv")
    cl = led.groupby("cluster_id").agg(first=("cluster_first_second", "first"), pol=("polarity", "first"), recorded=("in_recorded", "max"), emitted=("disposition", lambda s: int((s == "emitted").any())), size=("second", "count")).reset_index()
    secs = pd.concat([pd.read_parquet(OUT / f"m22_mbo_second_layers_{PREV[day]}.parquet"), pd.read_parquet(OUT / f"m22_mbo_second_layers_{day}.parquet")]).drop_duplicates("second", keep="last").set_index("second").sort_index()
    mid = ((secs.A_best + secs.B_best) / 2)
    nf = pq.read_table(WHOLE / f"audit-{day}/native-flow-source-clocks.parquet", columns=["second", "native_buy", "native_sell"]).to_pandas().set_index("second")
    def m(sec): return mid.get(sec, np.nan)
    def first_opposed(sec0, pol, horizon=300):
        w = nf.loc[(nf.index > sec0) & (nf.index <= sec0 + horizon)]
        opp = w.native_sell if pol > 0 else w.native_buy
        k = opp[opp > 0]
        return int(k.index[0] - sec0) if len(k) else np.nan
    rec = []
    for _, r in cl.iterrows():
        d0 = int(r["first"]) + 5; pol = int(r.pol); m0 = m(d0)
        ko = first_opposed(int(r["first"]), pol)
        rec.append(dict(cluster=r.cluster_id, first=int(r["first"]), decision=d0, pol=pol, recorded=int(r.recorded), size=int(r["size"]), k_opposed=ko,
                        r20=(m(d0 + 20) - m0) / 0.001 * pol, r60=(m(d0 + 60) - m0) / 0.001 * pol, r300=(m(d0 + 300) - m0) / 0.001 * pol,
                        r_exh=((m(int(r["first"]) + ko) - m0) / 0.001 * pol) if pd.notna(ko) and ko > 5 else (0.0 if pd.notna(ko) else np.nan)))
    B = pd.DataFrame(rec); B.to_csv(OUT / f"m24_clusters_{day}.csv", index=False)
    resB = dict(clusters=len(B), recorded_winners=int(B.recorded.sum()), non_recorded=int((B.recorded == 0).sum()),
                all_clusters=dict(ride_to_exhaustion=sc(B.r_exh), r20=sc(B.r20), r60=sc(B.r60), r300=sc(B.r300), k_opposed_p50=float(B.k_opposed.median())),
                recorded_only=dict(ride_to_exhaustion=sc(B[B.recorded == 1].r_exh), r20=sc(B[B.recorded == 1].r20), r60=sc(B[B.recorded == 1].r60), r300=sc(B[B.recorded == 1].r300)),
                non_recorded_only=dict(ride_to_exhaustion=sc(B[B.recorded == 0].r_exh), r20=sc(B[B.recorded == 0].r20), r60=sc(B[B.recorded == 0].r60), r300=sc(B[B.recorded == 0].r300)))
    out["per_date"][day] = dict(A_flip_vs_successor=resA, B_earliest_knowable_population=resB)
    print(day, "A:", json.dumps(resA)); print("   B:", json.dumps({k: (v if not isinstance(v, dict) else {kk: (vv if not isinstance(vv, dict) else (vv["up"], vv["flat"], vv["down"])) for kk, vv in v.items()}) for k, v in resB.items()}))
json.dump(out, open(OUT / "m24_flip_successor_and_peaks.json", "w"), indent=1)
