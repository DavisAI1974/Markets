"""M22: raw MBO tape (markets-data c01caaf data/nymex_mbo/ng_v0_oct2023/*.dbn.zst, sha256-verified) decoded with databento and replayed
message by message with an order-ID book, to populate the registry layers the derived tables do not carry: queue concentration (largest order's
share of the touch), orders and volume ahead (touch size and count), front-of-queue age, churn and turnover (added+cancelled at the touch per
resting lot), replaces (M) and clears (R), and actions by side and by level distance. One row per UTC second (state at the second's end plus the
second's action sums). Nothing is smoothed; undefined when a side is empty."""
import pandas as pd, numpy as np, json, sys, time, collections
from common import *
TAPE = pathlib.Path("/tmp/claude-0/-home-user-Markets/9d08bbd8-e004-5d31-9253-a2d3c0d0bcc4/scratchpad/tape")
import pathlib
def run(day):
    df = pd.read_parquet(TAPE / f"mbo_{day}.parquet", columns=["ts_recv", "action", "side", "price", "size", "order_id"])
    ts = df.ts_recv.values.astype("datetime64[ns]").astype("int64"); act = df.action.values; side = df.side.values; price = df.price.values; size = df.size.values.astype("int64"); oid = df.order_id.values
    orders = {}            # oid -> [side, price_int, size, enter_ns]
    levels = {"B": collections.defaultdict(lambda: [0, 0, collections.deque()]), "A": collections.defaultdict(lambda: [0, 0, collections.deque()])}  # price_int -> [size, count, deque(oids)]
    def best(s):
        ks = [p for p, v in levels[s].items() if v[0] > 0]
        if not ks: return None
        return max(ks) if s == "B" else min(ks)
    per_sec = collections.defaultdict(lambda: collections.Counter())
    def lvl_dist(s, p, b):
        if b is None: return 9
        d = (b - p) if s == "B" else (p - b); d = int(round(d / 1_000_000))
        return 0 if d <= 0 else (1 if d <= 2 else (2 if d <= 5 else 3))
    rows = []; cur_sec = None
    def snapshot(sec):
        r = dict(second=sec)
        for s in ("B", "A"):
            b = best(s)
            if b is None: r.update({f"{s}_best": np.nan, f"{s}_touch_size": np.nan, f"{s}_touch_orders": np.nan, f"{s}_conc": np.nan, f"{s}_front_age_s": np.nan, f"{s}_top5_size": np.nan}); continue
            L = levels[s][b]; q = [orders[o] for o in L[2] if o in orders and orders[o][1] == b and orders[o][2] > 0]
            sizes = [o[2] for o in q]; tot = sum(sizes)
            ks = sorted([p for p, v in levels[s].items() if v[0] > 0], reverse=(s == "B"))[:5]
            r.update({f"{s}_best": b / 1e9, f"{s}_touch_size": tot, f"{s}_touch_orders": len(q), f"{s}_conc": (max(sizes) / tot) if tot else np.nan, f"{s}_front_age_s": ((sec + 1) * 1e9 - q[0][3]) / 1e9 if q else np.nan, f"{s}_top5_size": sum(levels[s][p][0] for p in ks)})
        c = per_sec[sec]
        for k in ["B_add_touch", "A_add_touch", "B_cx_touch", "A_cx_touch", "B_add_near", "A_add_near", "B_cx_near", "A_cx_near", "B_add_deep", "A_add_deep", "B_cx_deep", "A_cx_deep", "B_mod", "A_mod", "B_mod_lose", "A_mod_lose", "B_fill", "A_fill", "T_B", "T_A", "clears", "msgs"]: r[k] = c.get(k, 0)
        for s in ("B", "A"):
            ts_ = r[f"{s}_touch_size"]; r[f"{s}_churn"] = (c.get(f"{s}_add_touch", 0) + c.get(f"{s}_cx_touch", 0)) / ts_ if ts_ and ts_ > 0 else np.nan
        rows.append(r)
    n = len(df); t0 = time.time()
    for i in range(n):
        sec = ts[i] // 10**9
        if cur_sec is None: cur_sec = sec
        while sec > cur_sec:
            snapshot(cur_sec); cur_sec += 1
        a = act[i]; s = side[i]; c = per_sec[sec]; c["msgs"] += 1
        if a == "R":
            orders.clear(); levels["B"].clear(); levels["A"].clear(); c["clears"] += 1; continue
        if s not in ("B", "A"):
            if a == "T": c["T_N"] += 1
            continue
        if a == "T": c[f"T_{s}"] += int(size[i]); continue
        p = int(round(price[i] * 1e9)) if np.isfinite(price[i]) else None
        if a == "A":
            if p is None: continue
            orders[oid[i]] = [s, p, int(size[i]), ts[i]]; L = levels[s][p]; L[0] += int(size[i]); L[1] += 1; L[2].append(oid[i])
            b = best(s); d = lvl_dist(s, p, b); c[f"{s}_add_" + ("touch" if d == 0 else "near" if d <= 2 else "deep")] += int(size[i])
        elif a in ("C", "F"):
            o = orders.get(oid[i])
            if o is None: continue
            q = min(int(size[i]), o[2]); L = levels[o[0]][o[1]]; L[0] -= q; o[2] -= q
            if o[2] <= 0:
                L[1] -= 1
                try: L[2].remove(oid[i])
                except ValueError: pass
                del orders[oid[i]]
            b = best(o[0]); d = lvl_dist(o[0], o[1], b)
            c[f"{o[0]}_" + ("cx_" if a == "C" else "fill") + ("" if a == "F" else ("touch" if d == 0 else "near" if d <= 2 else "deep"))] += q
        elif a == "M":
            o = orders.get(oid[i])
            if o is None or p is None: continue
            c[f"{s}_mod"] += 1
            L = levels[o[0]][o[1]]
            if p != o[1] or int(size[i]) > o[2]:  # loses priority
                L[0] -= o[2]; L[1] -= 1
                try: L[2].remove(oid[i])
                except ValueError: pass
                o[1] = p; o[2] = int(size[i]); o[3] = ts[i]; L2 = levels[s][p]; L2[0] += o[2]; L2[1] += 1; L2[2].append(oid[i]); c[f"{s}_mod_lose"] += 1
            else:
                L[0] -= (o[2] - int(size[i])); o[2] = int(size[i])
    snapshot(cur_sec)
    out = pd.DataFrame(rows); out.to_parquet(OUT / f"m22_mbo_second_layers_{day}.parquet", index=False)
    print(day, "messages", n, "seconds", len(out), "elapsed", round(time.time() - t0, 1), "s", "| nonempty touch share B/A", round(out.B_touch_size.notna().mean(), 3), round(out.A_touch_size.notna().mean(), 3), "| conc p50 B/A", round(out.B_conc.median(), 3), round(out.A_conc.median(), 3), "| front age p50 s", round(out.B_front_age_s.median(), 1), round(out.A_front_age_s.median(), 1), "| mods/day", int(out.B_mod.sum() + out.A_mod.sum()), "lose-priority", int(out.B_mod_lose.sum() + out.A_mod_lose.sum()), "clears", int(out.clears.sum()))
if __name__ == "__main__":
    for day in (sys.argv[1:] or ["20231001", "20231002", "20231003", "20231016", "20231017", "20231018"]): run(day)
