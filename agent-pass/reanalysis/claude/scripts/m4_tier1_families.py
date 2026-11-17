"""M4: Tier 1 first-observed structural family starts (795/848/823/749) from Ccode's t1_family_master tables (Markets 3d0b06a; rows pinned in the
corrected Tier 1 ledgers at markets-data c6e99f4). Decision clock = cutoff_ns = start_recv_ns - 1 ns. Outcomes chg_<h>s from the last group known by start+h.
Per-date distributions and cells; no pooling."""
import pandas as pd, numpy as np, json
from common import *
summ = []; cells = []
for day in DAYS:
    fm = pd.read_csv(SUITE / f"tables/{day}/t1_family_master.csv", low_memory=False)
    H = [1, 5, 20, 60, 300, 600]
    for h in H: fm[f"tk_{h}"] = fm[f"chg_{h}s"] / 0.001
    fm["flow60"] = np.sign(fm["root.activity.60.trade_buy_aggressor_qty"] - fm["root.activity.60.trade_sell_aggressor_qty"])
    fm["flow5"] = np.sign(fm["root.activity.5.trade_buy_aggressor_qty"] - fm["root.activity.5.trade_sell_aggressor_qty"])
    fm["flow1"] = np.sign(fm["root.activity.1.trade_buy_aggressor_qty"] - fm["root.activity.1.trade_sell_aggressor_qty"])
    fm["depth_full_sign"] = np.sign(fm["root.depth_imbalance_full"]); fm["depth_near_sign"] = np.sign(fm["root.depth_imbalance_n"])
    fm["touch_imb_sign"] = np.sign(fm["touch_imb"]) if "touch_imb" in fm else np.nan
    fm["pre120_sign"] = np.sign(fm["pre120_change"]) if "pre120_change" in fm else pd.Series(np.nan, index=fm.index)
    s = dict(day=day, families=len(fm), in_member=int(fm.in_member.sum()) if "in_member" in fm else None,
             full_depth_bid_heavy=int((fm.depth_full_sign > 0).sum()), full_depth_ask_heavy=int((fm.depth_full_sign < 0).sum()),
             near_bid_heavy=int((fm.depth_near_sign > 0).sum()), near_ask_heavy=int((fm.depth_near_sign < 0).sum()),
             spread_ticks=fm.spread_ticks.value_counts().head(6).to_dict() if "spread_ticks" in fm else None,
             outcomes={h: sign_counts(fm[f"tk_{h}"]) for h in H}, abs_ticks={h: qdesc(fm[f"tk_{h}"].abs()) for h in [5, 60, 300, 600]},
             censored={h: int((fm[f"grp_{h}s"] == -1).sum()) for h in H},
             pre120_sign=sign_counts(fm.pre120_change) if "pre120_change" in fm else None)
    summ.append(s); print(json.dumps({k: s[k] for k in ("day", "families", "full_depth_bid_heavy", "outcomes", "censored")}))
    # oriented to prior 120 s price direction: continuation share (price -> price)
    for h in (H if "pre120_change" in fm else []):
        o = fm[(fm.pre120_sign != 0) & fm.pre120_sign.notna()]; cont = np.sign(o[f"tk_{h}"]) * o.pre120_sign
        cells.append(dict(day=day, cell_var="oriented_to_pre120_direction", cell="all_with_prior_move", horizon_s=h, n=int(cont.notna().sum()), continue_=int((cont > 0).sum()), flat=int((cont == 0).sum()), reverse=int((cont < 0).sum())))
    # oriented to 5 s flow (behavior -> price)
    for h in H:
        o = fm[fm.flow5 != 0]; cont = np.sign(o[f"tk_{h}"]) * o.flow5
        cells.append(dict(day=day, cell_var="oriented_to_flow5", cell="signed_5s_flow", horizon_s=h, n=int(cont.notna().sum()), continue_=int((cont > 0).sum()), flat=int((cont == 0).sum()), reverse=int((cont < 0).sum())))
        o = fm[fm.flow60 != 0]; cont = np.sign(o[f"tk_{h}"]) * o.flow60
        cells.append(dict(day=day, cell_var="oriented_to_flow60", cell="signed_60s_flow", horizon_s=h, n=int(cont.notna().sum()), continue_=int((cont > 0).sum()), flat=int((cont == 0).sum()), reverse=int((cont < 0).sum())))
        if "touch_imb" in fm:
            o = fm[fm.touch_imb_sign != 0]; cont = np.sign(o[f"tk_{h}"]) * o.touch_imb_sign
            cells.append(dict(day=day, cell_var="oriented_to_touch_imbalance", cell="signed_touch_imb", horizon_s=h, n=int(cont.notna().sum()), continue_=int((cont > 0).sum()), flat=int((cont == 0).sum()), reverse=int((cont < 0).sum())))
        # price -> flow feedback inside families: prior 120 s direction vs 5 s / 60 s flow sign at start (simultaneous/preceding, NOT later response)
    for fcol in (["flow5", "flow60", "flow1"] if "pre120_change" in fm else []):
        o = fm[(fm.pre120_sign != 0) & fm.pre120_sign.notna() & (fm[fcol] != 0)]
        cells.append(dict(day=day, cell_var=f"pre120_vs_{fcol}", cell="agree_flow_with_prior_price_direction", horizon_s=0, n=len(o), continue_=int((o[fcol] * o.pre120_sign > 0).sum()), flat=0, reverse=int((o[fcol] * o.pre120_sign < 0).sum())))
    # flow pattern x depth cells (reuse the Ccode cell definition) with own per-trade quantiles
    for keys, g in fm.groupby(["flow60", "flow5", "flow1", "depth_full_sign"], dropna=False):
        if len(g) < 15: continue
        rec = dict(day=day, cell_var="flow60_5_1_x_fulldepth", cell=f"{int(keys[0]) if pd.notna(keys[0]) else 'NA'}/{int(keys[1]) if pd.notna(keys[1]) else 'NA'}/{int(keys[2]) if pd.notna(keys[2]) else 'NA'}|depth{int(keys[3])}", horizon_s=None, n=len(g))
        for h in [5, 60, 300]:
            sc = sign_counts(g[f"tk_{h}"]); rec[f"up_{h}"] = sc["up"]; rec[f"flat_{h}"] = sc["flat"]; rec[f"down_{h}"] = sc["down"]; rec[f"p50_{h}"] = float(g[f"tk_{h}"].median())
        cells.append(rec)
pd.DataFrame(cells).to_csv(OUT / "m4_tier1_cells.csv", index=False)
json.dump(summ, open(OUT / "m4_summary.json", "w"), indent=1)
