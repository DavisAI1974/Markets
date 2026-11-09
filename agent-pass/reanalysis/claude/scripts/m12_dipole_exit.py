"""M12: the dipole as an EXIT cue. (A) For the S2 large-move fade: does a Native dipole recognized in the jump direction inside the 600 s window
(before any full return) mark the moves that fail to return? Join c-large-quote-events (87dc338) with a-dipole-clocks (same run). (B) For a position
held in the birth direction, compare the oriented move after recognition by flow state (exit at 'opposite' vs hold) using the M1 tables, with MAE-like
adverse counts at 60/300 s. (C) Ccode population: aftermath after confirm vs after info50 by seed."""
import pandas as pd, numpy as np, json, pyarrow.parquet as pq
from common import *
out = {}
for day in DAYS:
    lm = pd.read_csv(OUT / f"m2_large_moves_{day}.csv")
    dc = pq.read_table(EVENTS / f"events-{day}/a-dipole-clocks.parquet").to_pandas()
    dc = dc[dc.live_recognition == True]
    rec = dc.recognition_ns.values.astype("int64"); pol = dc.polarity.values; birth = dc.birth_label_ns.values.astype("int64")
    rows = []
    for _, r in lm.iterrows():
        t0 = int(r.move_known_by_ns); tend = t0 + 600 * 10**9
        tret = t0 + int(r.full_recovery_s * 1e9) if pd.notna(r.full_recovery_s) else tend
        m = (rec > t0) & (rec <= min(tret, tend))
        with_dir = int(((pol == r.direction) & m).sum()); against = int(((pol == -r.direction) & m).sum())
        # also dipoles already alive at the move (born in the 60 s before) in the move direction
        pre = ((birth >= t0 - 60 * 10**9) & (birth <= t0) & (pol == r.direction)).sum()
        rows.append(dict(event_id=r.event_id, returned=pd.notna(r.full_recovery_s), full_recovery_s=r.full_recovery_s, dip_with_before_return=with_dir, dip_against_before_return=against, dip_with_born_60s_before=int(pre)))
    d = pd.DataFrame(rows)
    def cell(mask):
        g = d[mask]; return dict(n=int(len(g)), returned=int(g.returned.sum()), not_returned=int((~g.returned).sum()), return_time_p50=float(g.full_recovery_s.median()) if g.returned.any() else None)
    out[day] = {"A_large_moves": dict(all=cell(d.index == d.index), dipole_with_move_recognized_before_return=cell(d.dip_with_before_return > 0), no_dipole_with_move=cell(d.dip_with_before_return == 0),
                                       dipole_against_move_recognized=cell(d.dip_against_before_return > 0), no_dipole_against=cell(d.dip_against_before_return == 0),
                                       dipole_with_move_born_in_prior_60s=cell(d.dip_with_born_60s_before > 0))}
    d.to_csv(OUT / f"m12_large_move_dipole_join_{day}.csv", index=False)
    # (B) hold vs exit at recognition by flow state: adverse = oriented move < 0 (against the birth-direction position)
    c = pd.read_csv(OUT / f"m1_candidates_{day}.csv", low_memory=False); c = c[c.live_recognition == True]
    B = {}
    for fs, g in c.groupby("flow_state"):
        B[fs] = dict(n=len(g), adverse_60=int((g.cc_move_60 < 0).sum()), favourable_60=int((g.cc_move_60 > 0).sum()), adverse_300=int((g.cc_move_300 < 0).sum()), favourable_300=int((g.cc_move_300 > 0).sum()),
                     adverse_300_ge2ticks=int((g.cc_move_300 <= -2).sum()), favourable_300_ge2ticks=int((g.cc_move_300 >= 2).sum()), ended_before=int(g.ended_before_recognition.sum()))
    out[day]["B_hold_after_recognition_by_flow_state"] = B
    # (C) Ccode: aftermath class at 60/300 after confirm, by seed (already confirmed) vs P (not confirmed at info50)
    ex = pd.DataFrame(list(jsonl(CCODE / f"exhaustion-clock-{TAG[day]}-events.jsonl.gz"))); ex = ex[ex["mode"] == "day"] if "mode" in ex else ex
    C = {}
    for s_, g in ex.groupby("seed_state"):
        a300 = g.aftermath.apply(lambda a: a.get("300", {}).get("cls") if isinstance(a, dict) else None).value_counts().to_dict()
        C[s_] = dict(n=len(g), confirmed_before_info50=int(g.confirmed_before_info50.fillna(False).astype(bool).sum()), move_info50_plus60_up=int((g.move_info50_plus60 > 0).sum()), move_info50_plus60_down=int((g.move_info50_plus60 < 0).sum()), aftermath300=a300)
    out[day]["C_ccode_by_seed"] = C
    print(day); print("  A:", json.dumps(out[day]["A_large_moves"])); print("  B:", json.dumps(B)); print("  C:", json.dumps(C))
json.dump(out, open(OUT / "m12_dipole_exit.json", "w"), indent=1)
