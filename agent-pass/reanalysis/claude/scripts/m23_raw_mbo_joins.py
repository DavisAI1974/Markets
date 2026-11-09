"""M23: join the raw-MBO per-second queue layers (M22) to (A) the Native dipole candidates at the look-ahead clock (k=+5 after the birth second,
oriented: target side = the side the birth direction trades against) and to (B) the large moves (state in the second before the move and the sums
over the 20 s after). Outcomes as in M16/M2. Adds the raw layers to the M17 tertile/leave-one-date-out test so the picture is 'all layers together'."""
import pandas as pd, numpy as np, json
from common import *
LIFE = EV / "final_markets" / FR / "claude-pass-3day/tables/dipole"
def load_secs(day):
    prev = {"20231002": "20231001", "20231003": "20231002", "20231017": "20231016", "20231018": "20231017"}[day]
    s = pd.concat([pd.read_parquet(OUT / f"m22_mbo_second_layers_{prev}.parquet"), pd.read_parquet(OUT / f"m22_mbo_second_layers_{day}.parquet")]).drop_duplicates("second", keep="last").set_index("second").sort_index()
    return s
def orient(s, pol, sec, suffix=""):
    """features at second `sec` oriented: tgt = side hit by the birth direction (A for +1), own = other."""
    tgt, own = ("A", "B") if pol > 0 else ("B", "A")
    r = s.loc[sec] if sec in s.index else None
    if r is None: return {}
    return {f"raw_tgt_conc{suffix}": r[f"{tgt}_conc"], f"raw_own_conc{suffix}": r[f"{own}_conc"], f"raw_tgt_front_age{suffix}": r[f"{tgt}_front_age_s"], f"raw_own_front_age{suffix}": r[f"{own}_front_age_s"],
            f"raw_tgt_touch_orders{suffix}": r[f"{tgt}_touch_orders"], f"raw_own_touch_orders{suffix}": r[f"{own}_touch_orders"], f"raw_tgt_top5{suffix}": r[f"{tgt}_top5_size"], f"raw_own_top5{suffix}": r[f"{own}_top5_size"], f"raw_spread_ticks{suffix}": (r["A_best"] - r["B_best"]) / 0.001 if pd.notna(r["A_best"]) and pd.notna(r["B_best"]) else np.nan}
def sums(s, pol, a, b, prefix):
    tgt, own = ("A", "B") if pol > 0 else ("B", "A")
    w = s.loc[(s.index >= a) & (s.index <= b)]
    if len(w) == 0: return {}
    return {f"{prefix}_tgt_churn": float(w[f"{tgt}_churn"].mean()), f"{prefix}_own_churn": float(w[f"{own}_churn"].mean()), f"{prefix}_tgt_mod": int(w[f"{tgt}_mod"].sum()), f"{prefix}_own_mod": int(w[f"{own}_mod"].sum()), f"{prefix}_tgt_mod_lose": int(w[f"{tgt}_mod_lose"].sum()), f"{prefix}_own_mod_lose": int(w[f"{own}_mod_lose"].sum()),
            f"{prefix}_tgt_add_deep": int(w[f"{tgt}_add_deep"].sum()), f"{prefix}_own_add_deep": int(w[f"{own}_add_deep"].sum()), f"{prefix}_tgt_cx_deep": int(w[f"{tgt}_cx_deep"].sum()), f"{prefix}_own_cx_deep": int(w[f"{own}_cx_deep"].sum()), f"{prefix}_tgt_cx_touch": int(w[f"{tgt}_cx_touch"].sum()), f"{prefix}_own_cx_touch": int(w[f"{own}_cx_touch"].sum()),
            f"{prefix}_tgt_add_touch": int(w[f"{tgt}_add_touch"].sum()), f"{prefix}_own_add_touch": int(w[f"{own}_add_touch"].sum()), f"{prefix}_msgs": int(w["msgs"].sum()), f"{prefix}_clears": int(w["clears"].sum())}
feats = []
for day in DAYS:
    s = load_secs(day)
    F = pd.read_csv(OUT / "m17_features.csv.gz"); F = F[F.day == int(day)].copy()
    lc = pd.read_csv(OUT / "m16_lookahead_lifecycle_candidates.csv"); lc = lc[lc.day == int(day)].set_index("row")
    F = F.merge(lc[["k_exhaustion"]], left_on="row", right_index=True, how="left", suffixes=("", "_lc"))
    F["birth_sec"] = (F.anchor_label_ns // 10**9).astype("Int64")
    recs = []
    for _, r in F.iterrows():
        if pd.isna(r.birth_sec): recs.append({}); continue
        b = int(r.birth_sec); d = {}
        d.update(orient(s, r.pol, b + 5, "_k5")); d.update(orient(s, r.pol, b - 1, "_pre")); d.update(sums(s, r.pol, b - 20, b + 5, "raw_m20_5")); d.update(sums(s, r.pol, b + 1, b + 5, "raw_0_5"))
        recs.append(d)
    R = pd.DataFrame(recs, index=F.index); F = pd.concat([F, R], axis=1); feats.append(F)
A = pd.concat(feats, ignore_index=True); A.to_csv(OUT / "m23_features_with_raw.csv.gz", index=False)
RAW = [c for c in A.columns if c.startswith("raw_")]
def tert(s): return pd.cut(s.rank(pct=True, method="average"), [0, 1/3, 2/3, 1.0001], labels=["low", "mid", "high"], include_lowest=True)
cells = []; sign_table = {}
for out_name in ["ride_exh", "ride_60", "ride_300"]:
    for L in RAW:
        per = {}
        for day in DAYS:
            d = A[(A.day == int(day)) & A[L].notna() & A[out_name].notna()].copy()
            if d[L].nunique() < 3: continue
            d["t"] = tert(d[L])
            for t in ["low", "mid", "high"]:
                g = d[d.t == t]; cells.append(dict(outcome=out_name, layer=L, tertile=t, day=day, n=len(g), up=int((g[out_name] > 0).sum()), flat=int((g[out_name] == 0).sum()), down=int((g[out_name] < 0).sum())))
            hi = d[d.t == "high"][out_name]; lo = d[d.t == "low"][out_name]; per[day] = int(np.sign(((hi > 0).mean() - (hi < 0).mean()) - ((lo > 0).mean() - (lo < 0).mean())))
        sign_table[(out_name, L)] = per
pd.DataFrame(cells).to_csv(OUT / "m23_raw_layer_tertile_cells.csv", index=False)
cons = [dict(outcome=o, layer=L, direction=list(p.values())[0]) for (o, L), p in sign_table.items() if len(p) == 4 and len(set(p.values())) == 1 and 0 not in p.values()]
print("raw layers consistent on all four dates:", json.dumps(cons))
# LODO score with M17 layers + raw layers together
m17 = json.load(open(OUT / "m17_combined_layers.json")); ALL = m17["layers"] + RAW
cells17 = pd.read_csv(OUT / "m17_layer_tertile_cells.csv")
def sign_for(out_name, L, day):
    if L in RAW: return sign_table[(out_name, L)].get(day)
    g = cells17[(cells17.outcome == out_name) & (cells17.layer == L) & (cells17.day == int(day))]
    hi = g[g.tertile == "high"]; lo = g[g.tertile == "low"]
    if not len(hi) or not len(lo): return None
    h = hi.iloc[0]; l = lo.iloc[0]; return int(np.sign(((h.up - h.down) / max(h.n, 1)) - ((l.up - l.down) / max(l.n, 1))))
score_res = {}
for out_name in ["ride_exh", "ride_60"]:
    res = {}
    for held in DAYS:
        train = [d for d in DAYS if d != held]
        use = []
        for L in ALL:
            sg = [sign_for(out_name, L, d) for d in train]
            if all(x is not None for x in sg) and len(set(sg)) == 1 and sg[0] != 0: use.append((L, sg[0]))
        d = A[(A.day == int(held)) & A[out_name].notna()].copy(); sc_ = np.zeros(len(d)); sc_raw = np.zeros(len(d))
        for L, sg in use:
            if L not in d or d[L].notna().sum() < 10: continue
            t = tert(d[L].fillna(d[L].median())); v = sg * ((t == "high").astype(int) - (t == "low").astype(int)).values; sc_ += v
            if L in RAW: sc_raw += v
        d["score"] = sc_; d["score_raw"] = sc_raw
        def tb(col, k): return dict(top=dict(n=int((d[col] >= k).sum()), up=int(((d[col] >= k) & (d[out_name] > 0)).sum()), down=int(((d[col] >= k) & (d[out_name] < 0)).sum())), bottom=dict(n=int((d[col] <= -k).sum()), up=int(((d[col] <= -k) & (d[out_name] > 0)).sum()), down=int(((d[col] <= -k) & (d[out_name] < 0)).sum())))
        res[held] = dict(layers_used=len(use), raw_layers_used=sum(1 for L, _ in use if L in RAW), all_layers_score_ge4=tb("score", 4), raw_only_score_ge2=tb("score_raw", 2))
    score_res[out_name] = res; print(out_name, json.dumps(res))
json.dump(dict(raw_layers=RAW, consistent_raw_layers=cons, leave_one_date_out=score_res), open(OUT / "m23_raw_mbo_joins.json", "w"), indent=1)
# (B) large moves: raw state before and after
rows = []
for day in DAYS:
    s = load_secs(day); lm = pd.read_csv(OUT / f"m2_large_moves_{day}.csv")
    for _, r in lm.iterrows():
        ms = int(r.move_known_by_ns // 10**9); d = int(r.direction); rec = dict(day=day, event_id=r.event_id, returned=pd.notna(r.full_recovery_s), full_recovery_s=r.full_recovery_s)
        rec.update(orient(s, d, ms - 1, "_pre")); rec.update(orient(s, d, ms + 20, "_post20")); rec.update(sums(s, d, ms + 1, ms + 20, "raw_post20")); rec.update(sums(s, d, ms - 20, ms - 1, "raw_pre20")); rows.append(rec)
M = pd.DataFrame(rows); M.to_csv(OUT / "m23_large_move_raw_env.csv", index=False)
summ = {}
for day, g in M.groupby("day"):
    def cell(m): x = g[m]; return dict(n=int(len(x)), returned=int(x.returned.sum()), not_returned=int((~x.returned).sum()))
    summ[day] = {}
    for col in ["raw_tgt_conc_pre", "raw_own_conc_pre", "raw_tgt_front_age_pre", "raw_tgt_touch_orders_pre", "raw_post20_tgt_churn", "raw_post20_own_churn", "raw_post20_tgt_mod_lose", "raw_post20_own_mod_lose", "raw_post20_tgt_add_deep", "raw_post20_own_add_deep", "raw_post20_tgt_cx_deep", "raw_post20_own_cx_deep", "raw_post20_msgs", "raw_tgt_conc_post20", "raw_own_conc_post20"]:
        if col in g and g[col].notna().sum() >= 10:
            med = g[col].median(); summ[day][col] = dict(median=float(med), above=cell(g[col] > med), at_or_below=cell(g[col] <= med))
    print(day, {k: (v["above"]["not_returned"], v["above"]["n"], v["at_or_below"]["not_returned"], v["at_or_below"]["n"]) for k, v in summ[day].items()})
json.dump(summ, open(OUT / "m23_large_move_raw_env.json", "w"), indent=1)
