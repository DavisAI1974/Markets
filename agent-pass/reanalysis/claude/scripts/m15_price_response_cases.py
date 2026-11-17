"""M15: price-followed-by-response examples with exact clocks (brief: reinforcement, absorption/replenishment, withdrawal, reversal, no discernible
response). Population: midpoint-change seconds in native candidate paths (0487d83). Rules (declared): first chronological instance per date of
 - reinforcement: in +1..+5 s more adds on the side left behind (away) than toward, no fills on the toward side, and the midpoint continued (+20 s oriented > 0)
 - absorption/replenishment: adds on the toward (attacked) side exceed fills there in +1..+5 s and the midpoint returned (+20 s oriented < 0)
 - withdrawal: cancels on the away side exceed adds there in +1..+5 s and the midpoint continued
 - reversal: oriented +5 s move < 0 with fills on the away side in +1..+5 s
 - no discernible response: zero adds/cancels/fills/prints on both sides in +1..+5 s and the midpoint unchanged at +20 s."""
import pandas as pd, numpy as np, json
from common import *
rows = []
for day in DAYS:
    x = pd.read_csv(OUT / f"m8_price_change_seconds_{day}.csv.gz"); x = x[x.kind == "candidate"]
    p = pd.read_csv(NATIVE / f"{day}-paths.csv.gz", usecols=["candidate_id", "kind", "relative_s", "cut_ns", "bid", "ask", "cursor"], low_memory=False)
    p = p[p.kind == "candidate"]
    x = x.merge(p, on=["candidate_id", "kind", "relative_s"], how="left").sort_values("cut_ns")
    a = x.s1_add_toward + x.s2_5_add_toward; aa = x.s1_add_away + x.s2_5_add_away; ft = x.s1_fill_toward + x.s2_5_fill_toward; fa = x.s1_fill_away + x.s2_5_fill_away
    ct = x.s1_cancel_toward + x.s2_5_cancel_toward; ca = x.s1_cancel_away + x.s2_5_cancel_away; tr = x.s1_trade_toward + x.s1_trade_away + x.s2_5_trade_toward + x.s2_5_trade_away
    rules = {
        "reinforcement": (aa > a) & (ft == 0) & (x.mid_next_20_oriented > 0),
        "absorption_replenishment": (a > ft) & (a > 0) & (x.mid_next_20_oriented < 0),
        "withdrawal": (ca > aa) & (x.mid_next_20_oriented > 0),
        "reversal": (x.mid_next_5_oriented < 0) & (fa > 0),
        "no_discernible_response": (a + aa + ft + fa + ct + ca + tr == 0) & (x.mid_next_20_oriented == 0),
    }
    for name, m in rules.items():
        g = x[m & x.mid_next_20_oriented.notna()]
        n_all = int(m.sum())
        if len(g) == 0: continue
        r = g.iloc[0]
        rows.append(dict(case_id=f"{day}:{r.candidate_id}:candidate:rel{int(r.relative_s)}", rule=f"R7 price-followed-by-{name} (first chronological; {n_all} such seconds of {len(x)} candidate price-change seconds on this date)", day=day,
                         population=f"midpoint-change seconds inside native candidate paths ({len(x)} this date)", source="markets-data@0487d83 native-dipole/.../tables/<day>-paths.csv.gz; tables/m8_price_change_seconds_<day>.csv.gz",
                         parent_id=f"{day}:{r.candidate_id}:candidate", component_refs=f"path second relative_s={int(r.relative_s)}; cursor={r.cursor}", observation_clock_ns=int(r.cut_ns), known_by_clock_ns=int(r.cut_ns), recognition_clock_ns="", outcome_clock_ns=int(r.cut_ns + 20 * 10**9),
                         observed_sequence=f"dir={int(r.dir)} dmid_ticks={r.dmid_ticks}; bid/ask after={r.bid}/{r.ask}; same-second toward/away adds={r.s0_add_toward}/{r.s0_add_away} fills={r.s0_fill_toward}/{r.s0_fill_away}; +1..+5 adds toward/away={a[r.name]}/{aa[r.name]} fills={ft[r.name]}/{fa[r.name]} cancels={ct[r.name]}/{ca[r.name]} prints={tr[r.name]}; mid +5={r.mid_next_5_oriented} +20={r.mid_next_20_oriented} (oriented ticks)",
                         relation_to_interpretation=f"example of {name}; the population-level reading is in REPORT section 5 (no side asymmetry in the response; next move reverses more often)", contrary_or_complementary="", unexplained="whether the +1..+5 s events are reactions or the same activity cluster is not identifiable at 1 s"))
df = pd.DataFrame(rows); old = pd.read_csv(OUT.parent / "CASES.csv"); old = old[~old.rule.str.startswith("R7")]
pd.concat([old, df]).to_csv(OUT.parent / "CASES.csv", index=False); print(len(df), "cases added;", len(old) + len(df), "total")
