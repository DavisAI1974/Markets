"""M26 (rerun v2 headline cells): the strongest layer at the realistic exit is the touch ratio at k=+5 (own-side touch size / target-side touch size,
own = the side the birth direction rests on). Report, per date, its tertiles against the realistic exit rule (exhaustion-end or 60 s), the fixed 60 s and
300 s holds, with up/flat/down counts and quantiles in ticks; a two-way cell with the raw-MBO own-side touch order count (independent source, same read);
and the same cells for the earliest-knowable cluster population (M24) using the raw book at the decision second."""
import pandas as pd, numpy as np, json
from common import *
A = pd.read_csv(OUT / "m23_features_with_raw.csv.gz", low_memory=False)
lc = pd.read_csv(OUT / "m16_lookahead_lifecycle_candidates.csv")
A = A.merge(lc[["day", "row", "m_exh_end"]], on=["day", "row"], how="left", suffixes=("", "_lc2"))
A["exit_real"] = np.where(A.k_exhaustion <= 5, 0.0, np.where(A.k_exhaustion.notna() & (A.k_exhaustion <= 60), A.m_exh_end, A.m60) - A.m5)
def q(x): x = x[np.isfinite(x)]; return dict(n=int(x.size), up=int((x > 0).sum()), flat=int((x == 0).sum()), down=int((x < 0).sum()), p25=float(np.percentile(x, 25)) if x.size else None, p50=float(np.median(x)) if x.size else None, p75=float(np.percentile(x, 75)) if x.size else None, mean=float(x.mean()) if x.size else None)
def tert(s): return pd.cut(s.rank(pct=True, method="average"), [0, 1/3, 2/3, 1.0001], labels=["low", "mid", "high"], include_lowest=True)
out = {}
for day in DAYS:
    d = A[A.day == int(day)].copy(); d["t_ratio"] = tert(d.touch_ratio_k5); d["t_rawown"] = tert(d.raw_own_touch_orders_k5)
    r = {"touch_ratio_k5_tertiles": {}, "two_way_touch_ratio_x_raw_own_touch_orders": {}}
    for t in ["low", "mid", "high"]:
        g = d[d.t_ratio == t]; r["touch_ratio_k5_tertiles"][t] = {o: q(g[o].values) for o in ["exit_real", "ride_exh_end", "ride_60", "ride_300"]}
    for t1 in ["low", "high"]:
        for t2 in ["low", "high"]:
            g = d[(d.t_ratio == t1) & (d.t_rawown == t2)]; r["two_way_touch_ratio_x_raw_own_touch_orders"][f"ratio_{t1}__rawown_{t2}"] = {o: q(g[o].values) for o in ["exit_real", "ride_60"]}
    # exhaustion timing by touch ratio (does the thick own side delay the first opposed lot?)
    r["k_exhaustion_p50_by_touch_ratio"] = {t: float(d[d.t_ratio == t].k_exhaustion.median()) for t in ["low", "mid", "high"]}
    r["share_exhausted_within_20s_by_touch_ratio"] = {t: float((d[d.t_ratio == t].k_exhaustion <= 20).mean()) for t in ["low", "mid", "high"]}
    out[day] = r
    print(day, "exit_real by touch ratio:", {t: (v["exit_real"]["up"], v["exit_real"]["flat"], v["exit_real"]["down"], v["exit_real"]["p75"]) for t, v in r["touch_ratio_k5_tertiles"].items()}, "| ride_60:", {t: (v["ride_60"]["up"], v["ride_60"]["flat"], v["ride_60"]["down"]) for t, v in r["touch_ratio_k5_tertiles"].items()})
    print("    two-way exit_real:", {k: (v["exit_real"]["up"], v["exit_real"]["flat"], v["exit_real"]["down"]) for k, v in r["two_way_touch_ratio_x_raw_own_touch_orders"].items()}, "| k_exh p50", r["k_exhaustion_p50_by_touch_ratio"])
# earliest-knowable clusters with raw book at the decision second
PREV = {"20231002": "20231001", "20231003": "20231002", "20231017": "20231016", "20231018": "20231017"}
for day in DAYS:
    B = pd.read_csv(OUT / f"m24_clusters_{day}.csv")
    s = pd.concat([pd.read_parquet(OUT / f"m22_mbo_second_layers_{PREV[day]}.parquet"), pd.read_parquet(OUT / f"m22_mbo_second_layers_{day}.parquet")]).drop_duplicates("second", keep="last").set_index("second")
    own_n = []; tgt_n = []; own_sz = []; tgt_sz = []
    for _, r in B.iterrows():
        sec = int(r.decision); tgt, own = ("A", "B") if r.pol > 0 else ("B", "A")
        if sec in s.index: x = s.loc[sec]; own_n.append(x[f"{own}_touch_orders"]); tgt_n.append(x[f"{tgt}_touch_orders"]); own_sz.append(x[f"{own}_touch_size"] if f"{own}_touch_size" in x else np.nan); tgt_sz.append(x[f"{tgt}_touch_size"] if f"{tgt}_touch_size" in x else np.nan)
        else: own_n.append(np.nan); tgt_n.append(np.nan); own_sz.append(np.nan); tgt_sz.append(np.nan)
    B["own_n"] = own_n; B["tgt_n"] = tgt_n; B["own_sz"] = own_sz; B["tgt_sz"] = tgt_sz; B["ratio"] = (B.own_sz + 1) / (B.tgt_sz + 1) if B.own_sz.notna().any() else (B.own_n + 1) / (B.tgt_n + 1)
    B["t"] = tert(B.ratio); r = {}
    for t in ["low", "mid", "high"]:
        g = B[B.t == t]; r[t] = {o: q(g[o].values) for o in ["r_exh", "r60", "r300"]}
    out[day]["earliest_knowable_clusters_by_touch_ratio_raw_book"] = dict(ratio_basis=("touch size" if B.own_sz.notna().any() else "touch order count"), cells=r, non_recorded_high=q(B[(B.t == "high") & (B.recorded == 0)].r60.values), non_recorded_low=q(B[(B.t == "low") & (B.recorded == 0)].r60.values))
    print(day, "clusters r_exh by raw touch ratio:", {t: (v["r_exh"]["up"], v["r_exh"]["flat"], v["r_exh"]["down"]) for t, v in r.items()}, "| r60:", {t: (v["r60"]["up"], v["r60"]["flat"], v["r60"]["down"]) for t, v in r.items()})
json.dump(out, open(OUT / "m26_v2_headline_cells.json", "w"), indent=1)
