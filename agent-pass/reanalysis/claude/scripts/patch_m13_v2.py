"""Patch m13_all_claims.py to add M23 (raw MBO layers) and M24 (flip/successor, earliest-knowable population) generated claim rows."""
import pathlib
p = pathlib.Path(__file__).with_name("m13_all_claims.py"); s = p.read_text()
extra = '''
# M23 raw MBO layers at the look-ahead clock and around large moves; M24 flip/successor and earliest-knowable population
try:
    m23 = json.load(open(OUT / "m23_raw_mbo_joins.json")); c23 = pd.read_csv(OUT / "m23_raw_layer_tertile_cells.csv")
    cons23 = {(c["outcome"], c["layer"]): c["direction"] for c in m23["consistent_raw_layers"]}
    for (o, L), g in c23.groupby(["outcome", "layer"]):
        parts = {}
        for d in DAYS:
            h = g[(g.tertile == "high") & (g.day == int(d))]; l = g[(g.tertile == "low") & (g.day == int(d))]
            if len(h) and len(l): parts[d] = f"high up/flat/down {int(h.up.iloc[0])}/{int(h.flat.iloc[0])}/{int(h.down.iloc[0])} n{int(h.n.iloc[0])} | low {int(l.up.iloc[0])}/{int(l.flat.iloc[0])}/{int(l.down.iloc[0])} n{int(l.n.iloc[0])}"
        add(f"M23-{o}-{L}", "raw MBO queue layer at look-ahead clock (k=+5)", f"{L} tertiles vs {o}", (f"same high-vs-low direction on all four dates ({cons23[(o, L)]:+d})" if (o, L) in cons23 else "not consistent across dates (retained)"), fmt(parts), "covered candidates", "", "", "tables/m23_raw_layer_tertile_cells.csv; markets-data@c01caaf raw MBO tapes", clock="k=+5 s (second-end book state) / -20..+5 sums", end=o)
    for o, res in m23["leave_one_date_out"].items():
        add(f"M23-score-{o}", "all layers together (derived + raw MBO), leave-one-date-out", f"Additive sign score over all consistent layers vs {o}, held-out date", "retained", fmt({d: json.dumps(res[d]) for d in DAYS}), src="tables/m23_raw_mbo_joins.json", clock="k=+5 s", end=o)
    e23 = json.load(open(OUT / "m23_large_move_raw_env.json"))
    for col in sorted({k for d in DAYS for k in e23.get(d, {})}):
        add(f"M23-fade-{col}", "raw MBO environment around large moves", f"Large-move full return by {col} (above vs at/below the date median)", "retained", fmt({d: json.dumps(e23[d][col]) for d in DAYS if col in e23.get(d, {})}), src="tables/m23_large_move_raw_env.csv", clock="second before the move / +1..+20 s", end="full return 600 s")
except FileNotFoundError:
    pass
try:
    m24 = json.load(open(OUT / "m24_flip_successor_and_peaks.json"))
    for k, v in m24.get("per_date", {}).get(DAYS[0], {}).items():
        add(f"M24-{k}", "look-ahead lifecycle (flip/successor; earliest-knowable population)", k.replace("_", " "), "retained", fmt({d: json.dumps(m24["per_date"][d].get(k)) for d in DAYS}), src="tables/m24_flip_successor_and_peaks.json", clock="completed second", end="see key")
except FileNotFoundError:
    pass
try:
    m16b = json.load(open(OUT / "m16b_exhaustion_convention_check.json"))
    NOTE16 = {"ride_to_exhaustion_before_opposed_print": "midpoint at the START of the exhaustion second (before the opposed print is known): up-leaning on all four dates; NOT a realistic exit",
              "ride_to_exhaustion_after_opposed_print": "midpoint at the END of the exhaustion second (realistic exit): symmetric on all four dates",
              "midpoint_change_inside_exhaustion_second": "the exhaustion second itself moves AGAINST the birth direction on all four dates (the opposed print takes the tick)",
              "after_exhaustion_60s_from_end_of_second": "symmetric on all four dates", "after_exhaustion_60s_from_start_of_second": "down-leaning on all four dates, but this includes the exhaustion second's own tick",
              "after_flip_60s_from_end_of_second": "symmetric on all four dates", "after_flip_60s_from_start_of_second": "down-leaning on all four dates, but this includes the flip second's own tick",
              "exit_rule_realistic": "exhaustion-end or 60 s: symmetric on all four dates", "k5_to_60_hold": "symmetric on all four dates"}
    for k in m16b[DAYS[0]]:
        add(f"M16B-{k}", "exhaustion CONVENTION check (look-ahead ride)", k.replace("_", " "), NOTE16.get(k, "retained"), fmt({d: json.dumps(m16b[d][k]) for d in DAYS}), src="tables/m16b_exhaustion_convention_check.json", clock="k=+5 s entry; mark second start vs end", end="see key", lim="oriented midpoint ticks from Ccode x13 life paths; four dates")
except FileNotFoundError:
    pass
'''
marker = 'with open(OUT.parent / "CLAIMS.csv") as fh: existing'
assert marker in s and "M23-" not in s
s = s.replace(marker, extra + "\n" + marker, 1).replace('PFX = ("LA-",', 'PFX = ("LA-", "M16B-", "M23-", "M24-",')
p.write_text(s); print("patched v2")
