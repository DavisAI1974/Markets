"""M8: Two-way feedback. (A) price change -> later orders/liquidity/trading/price, from the native per-second paths (0487d83): every second
where the midpoint changed inside a path, split by kind (candidate = dipole-conditioned context; control1/control2 = matched arbitrary anchors =
general market sample). Same-second action totals are MECHANICAL/simultaneous (the fill that moved the quote lives in the same second);
seconds +1 and +2..+5 and +6..+20 are later responses. Oriented so that + is the side the price moved TOWARD (ask side for an up move).
(B) group-level: after a group whose midpoint moved, does the next group carry a print, and how soon (b-next-group-arrival, 87dc338).
(C) quote-episode endings: old/new touch effects at a retreat (c-quote-ending-mechanisms) = what removed the resistance."""
import pandas as pd, numpy as np, json, pyarrow.parquet as pq
from common import *
summ = []; resp_rows = []
for day in DAYS:
    p = pd.read_csv(NATIVE / f"{day}-paths.csv.gz")
    p = p.sort_values(["candidate_id", "kind", "relative_s"]).reset_index(drop=True)
    p["mid"] = (p.bid + p.ask) / 2
    g = p.groupby(["candidate_id", "kind"], sort=False)
    p["dmid"] = g.mid.diff()
    p["dmid_ticks"] = (p.dmid / 0.001).round(3)
    p["dir"] = np.sign(p.dmid_ticks).fillna(0).astype(int)
    key = p.candidate_id + "|" + p.kind
    base_all = {}
    for kind in ["candidate", "control1", "control2"]:
        q = p[p.kind == kind]
        base_all[kind] = dict(seconds=len(q), price_change_seconds=int((q.dir != 0).sum()), up=int((q.dir > 0).sum()), down=int((q.dir < 0).sum()))
    # per price-change second: oriented action totals at offsets 0, +1, +2..+5, +6..+20 and subsequent oriented mid change at +5, +20
    recs = []
    arr = {c: p[c].values for c in ["add_B", "add_A", "cancel_B", "cancel_A", "fill_B", "fill_A", "modify_B", "modify_A", "trade_B", "trade_A", "mid", "bid_size", "ask_size", "relative_s"]}
    keys = key.values; dirs = p.dir.values; n = len(p)
    idx = np.where(dirs != 0)[0]
    def win(i, lo, hi, col_t, col_a):
        # toward side = side price moved toward (ask for up: price rose into asks), away side = the other
        j0, j1 = i + lo, i + hi
        if j1 >= n or keys[j1] != keys[i]: return np.nan, np.nan
        return arr[col_t][j0:j1 + 1].sum(), arr[col_a][j0:j1 + 1].sum()
    for i in idx:
        d = dirs[i]; k = keys[i].split("|")
        tow = "A" if d > 0 else "B"; awy = "B" if d > 0 else "A"
        r = dict(day=day, candidate_id=k[0], kind=k[1], relative_s=arr["relative_s"][i], dir=int(d), dmid_ticks=float(p.dmid_ticks.values[i]),
                 pre_mid5=(arr["mid"][i - 1] - arr["mid"][i - 6]) / 0.001 * d if i - 6 >= 0 and keys[i - 6] == keys[i] else np.nan)
        for lo, hi, tag in [(0, 0, "s0"), (1, 1, "s1"), (2, 5, "s2_5"), (6, 20, "s6_20")]:
            for act in ["add", "cancel", "fill", "modify", "trade"]:
                t, a = win(i, lo, hi, f"{act}_{tow}", f"{act}_{awy}")
                r[f"{tag}_{act}_toward"] = t; r[f"{tag}_{act}_away"] = a
        for h in [5, 20]:
            j = i + h
            r[f"mid_next_{h}_oriented"] = (arr["mid"][j] - arr["mid"][i]) / 0.001 * d if j < n and keys[j] == keys[i] else np.nan
        recs.append(r)
    df = pd.DataFrame(recs); df.to_csv(OUT / f"m8_price_change_seconds_{day}.csv.gz", index=False)
    # baseline for quiet seconds: same windows after seconds with no mid change (sample up to 20000 per kind)
    rng = np.random.default_rng(1401)
    qidx = np.where(dirs == 0)[0]; qidx = qidx[(arr["relative_s"][qidx] > -59)]
    qidx = rng.choice(qidx, size=min(20000, len(qidx)), replace=False)
    qrec = []
    for i in qidx:
        k = keys[i].split("|")
        r = dict(kind=k[1])
        for lo, hi, tag in [(1, 1, "s1"), (2, 5, "s2_5"), (6, 20, "s6_20")]:
            for act in ["add", "cancel", "fill", "trade"]:
                j0, j1 = i + lo, i + hi
                if j1 < n and keys[j1] == keys[i]:
                    r[f"{tag}_{act}_both"] = arr[f"{act}_A"][j0:j1 + 1].sum() + arr[f"{act}_B"][j0:j1 + 1].sum()
        qrec.append(r)
    qdf = pd.DataFrame(qrec)
    s = dict(day=day, base=base_all)
    for kind in ["candidate", "control1", "control2"]:
        x = df[df.kind == kind]; qk = qdf[qdf.kind == kind]
        o = dict(n=len(x))
        for tag in ["s0", "s1", "s2_5", "s6_20"]:
            for act in ["add", "cancel", "fill", "trade", "modify"]:
                t = x[f"{tag}_{act}_toward"]; a = x[f"{tag}_{act}_away"]
                o[f"{tag}_{act}"] = dict(toward_mean=round(float(t.mean()), 3), away_mean=round(float(a.mean()), 3), toward_gt_away=int((t > a).sum()), away_gt_toward=int((a > t).sum()), equal=int((t == a).sum()), n=int(t.notna().sum()))
        for tag in ["s1", "s2_5", "s6_20"]:
            for act in ["add", "cancel", "fill", "trade"]:
                o[f"{tag}_{act}_both_after_change_mean"] = round(float((x[f"{tag}_{act}_toward"] + x[f"{tag}_{act}_away"]).mean()), 3)
                o[f"{tag}_{act}_both_quiet_mean"] = round(float(qk[f"{tag}_{act}_both"].mean()), 3) if f"{tag}_{act}_both" in qk else None
        for h in [5, 20]:
            o[f"mid_next_{h}"] = sign_counts(x[f"mid_next_{h}_oriented"])
        # conditional: continuation vs reversal at +20 by response in s1..s5 (adds on away side = replenishment behind the move? no: away side = side price moved away from = the side being refilled/withdrawn)
        rep = x[(x.s2_5_add_away.notna())]
        hi = rep[rep.s2_5_add_toward > rep.s2_5_add_away]; lo_ = rep[rep.s2_5_add_toward < rep.s2_5_add_away]
        o["mid_next_20_given_more_adds_toward_2_5"] = sign_counts(hi.mid_next_20_oriented); o["mid_next_20_given_more_adds_away_2_5"] = sign_counts(lo_.mid_next_20_oriented)
        ft = rep[rep.s2_5_fill_toward > 0]; nf = rep[rep.s2_5_fill_toward == 0]
        o["mid_next_20_given_fills_toward_2_5"] = sign_counts(ft.mid_next_20_oriented); o["mid_next_20_given_no_fills_toward_2_5"] = sign_counts(nf.mid_next_20_oriented)
        pre = x[x.pre_mid5.notna()]
        o["mid_next_20_given_prior5_same_dir"] = sign_counts(pre[pre.pre_mid5 > 0].mid_next_20_oriented); o["mid_next_20_given_prior5_opposite"] = sign_counts(pre[pre.pre_mid5 < 0].mid_next_20_oriented); o["mid_next_20_given_prior5_flat"] = sign_counts(pre[pre.pre_mid5 == 0].mid_next_20_oriented)
        s[kind] = o
    # (B) next group arrival after a midpoint-moving group
    ng = pq.read_table(EVENTS / f"events-{day}/b-next-group-arrival.parquet", columns=["midpoint_direction", "next_has_print", "current_has_print", "next_print_lead_ns", "elapsed_known_by_ns", "standalone_falling_touch", "spread_raw"]).to_pandas()
    def cell(m):
        return dict(n=int(len(m)), next_has_print=int(m.next_has_print.sum()), share=round(float(m.next_has_print.mean()), 4), elapsed_p50_ms=round(float(m.elapsed_known_by_ns.median()) / 1e6, 1),
                    next_print_lead_p50_ms=round(float(m.next_print_lead_ns[m.next_has_print].median()) / 1e6, 1) if m.next_has_print.any() else None)
    s["next_group"] = {"mid_moved": cell(ng[ng.midpoint_direction != 0]), "mid_flat": cell(ng[ng.midpoint_direction == 0]),
                       "mid_moved_no_print": cell(ng[(ng.midpoint_direction != 0) & (~ng.current_has_print)]), "mid_moved_with_print": cell(ng[(ng.midpoint_direction != 0) & (ng.current_has_print)]),
                       "mid_flat_no_print": cell(ng[(ng.midpoint_direction == 0) & (~ng.current_has_print)])}
    # (C) ending mechanisms of thin-touch episodes
    qm = pq.read_table(EVENTS / f"events-{day}/c-quote-ending-mechanisms.parquet").to_pandas()
    def eff(col):
        vals = [v if isinstance(v, dict) else {} for v in qm[col].tolist()]
        e = pd.DataFrame(vals).fillna(0); e["ending"] = qm.ending.values
        return {k: {c: int(v) for c, v in g.drop(columns="ending").sum().items()} for k, g in e.groupby("ending")}
    s["episode_end_old_touch_effect_totals"] = eff("ending_old_touch_effect"); s["episode_end_new_touch_effect_totals"] = eff("ending_new_touch_effect")
    s["episode_end_flags"] = {k: dict(n=len(g), fill_linked=int(g.ending_fill_linked.sum()), unlinked_reduction=int(g.ending_unlinked_reduction.sum())) for k, g in qm.groupby("ending")}
    summ.append(s); print(json.dumps({k: s[k] for k in ("day", "base", "next_group", "episode_end_flags")}))
json.dump(summ, open(OUT / "m8_summary.json", "w"), indent=1)
