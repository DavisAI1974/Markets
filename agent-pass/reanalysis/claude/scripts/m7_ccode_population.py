"""M7: Ccode's independent full-session detector population (839/857/830/890) from the per-event files at Markets 24da878/f1c7277:
exhaustion-clock (runway, confirm, info horizon), runway-duration (time to k ticks with/either direction, censored), a-state direction knowable,
next-burst forecast, chain-play filter. These are a DIFFERENT population from the archived Native 741/833/741/863 (not joined here)."""
import pandas as pd, numpy as np, json
from common import *
summ = []; cells = []
for day in DAYS:
    tag = TAG[day]
    ex = pd.DataFrame(list(jsonl(CCODE / f"exhaustion-clock-{tag}-events.jsonl.gz")))
    modes = ex["mode"].value_counts().to_dict() if "mode" in ex else {}
    exd = ex[ex["mode"] == "day"].copy() if "mode" in ex else ex.copy()
    def cls(a, h):
        return a.get(str(h), {}).get("cls") if isinstance(a, dict) else None
    aft = {h: exd["aftermath"].apply(lambda a: cls(a, h)) for h in [30, 60, 120, 300]}
    rd = pd.DataFrame(list(jsonl(CCODE / f"runway-duration-{tag}-events.jsonl.gz")))
    ak = pd.DataFrame(list(jsonl(CCODE / f"a-state-direction-knowable-{tag}-events.jsonl.gz")))
    nb = pd.DataFrame(list(jsonl(CCODE / f"next-burst-forecast-{tag}-events.jsonl.gz")))
    cp = pd.DataFrame(list(jsonl(CCODE / f"chain-play-filter-{tag}-rows.jsonl.gz")))
    b = lambda s: s.fillna(False).astype(bool)
    s = dict(day=day, exhaustion_rows=len(ex), modes=modes, day_mode_rows=len(exd),
             seed_state=exd.seed_state.value_counts().to_dict(), runway_s=qdesc(exd.runway_s), confirm_offset_s=qdesc(exd.confirm_offset_s),
             censored=int(b(exd.censored).sum()), confirmed_before_info50=int(b(exd.confirmed_before_info50).sum()),
             remaining_runway_at_info50_s=qdesc(exd.remaining_runway_at_info50_s),
             archived_recognition_present=int(exd.archived_recognition_s.notna().sum()), archived_recognition_offset_s=qdesc(exd.archived_recognition_offset_s),
             move_t0_to_info50=sign_counts(exd.move_t0_to_info50), move_info50_plus30=sign_counts(exd.move_info50_plus30), move_info50_plus60=sign_counts(exd.move_info50_plus60),
             move_t0_to_confirm=sign_counts(exd.move_t0_to_confirm),
             aftermath_cls_60=aft[60].value_counts().to_dict(), aftermath_cls_300=aft[300].value_counts().to_dict(),
             a_state=ak.a_state.value_counts().to_dict(), plus60_d60=sign_counts(ak.plus60_d60_oriented), plus60_d300=sign_counts(ak.plus60_d300_oriented), plus60_d600=sign_counts(ak.plus60_d600_oriented),
             known_d60=sign_counts(ak.known_d60_oriented) if "known_d60_oriented" in ak else None,
             next_burst_state_hit=[int(nb.state_hit.sum()), int(nb.state_hit.notna().sum())],
             chain_eligible=int(b(cp.eligible).sum()), chain_is_play=int(b(cp.is_play).sum()), chain_return_ticks_plays=sign_counts(cp[b(cp.is_play)].return_ticks),
             chain_reasons=pd.Series([r for rs in cp.reasons.dropna() for r in rs]).value_counts().to_dict(),
             runway_with3t_s=qdesc(rd.price_with_3t[~b(rd.price_with_3t_censored)]), runway_with3t_censored=int(b(rd.price_with_3t_censored).sum()),
             runway_either3t_s=qdesc(rd.price_either_3t[~b(rd.price_either_3t_censored)]), with3t_not_after_either3t=int((rd.price_with_3t <= rd.price_either_3t).sum()), n_runway=len(rd))
    summ.append(s); print(json.dumps({k: v for k, v in s.items() if k in ("day", "day_mode_rows", "seed_state", "confirmed_before_info50", "archived_recognition_present", "move_info50_plus60", "aftermath_cls_300", "a_state", "plus60_d300", "next_burst_state_hit", "chain_is_play", "chain_return_ticks_plays")}))
    for k, g in exd.groupby("seed_state", dropna=False):
        cells.append(dict(day=day, cell_var="seed_state", cell=str(k), n=len(g), confirmed_before_info50=int(b(g.confirmed_before_info50).sum()),
                          runway_p50=float(g.runway_s.median()), remaining_at_info50_p50=float(g.remaining_runway_at_info50_s.median()),
                          **{f"info50_plus30_{kk}": v for kk, v in sign_counts(g.move_info50_plus30).items()}, **{f"info50_plus60_{kk}": v for kk, v in sign_counts(g.move_info50_plus60).items()},
                          aftermath300=json.dumps(aft[300][g.index].value_counts().to_dict())))
    for k, g in ak.groupby("a_state", dropna=False):
        cells.append(dict(day=day, cell_var="a_state", cell=str(k), n=len(g), **{f"d60_{kk}": v for kk, v in sign_counts(g.plus60_d60_oriented).items()},
                          **{f"d300_{kk}": v for kk, v in sign_counts(g.plus60_d300_oriented).items()}, **{f"d600_{kk}": v for kk, v in sign_counts(g.plus60_d600_oriented).items()},
                          first3t_with=int(g.plus60_first3t_with.sum()), first5t_with=int(g.plus60_first5t_with.sum())))
    for k, g in rd.groupby("seed", dropna=False):
        ok = g[~b(g.price_with_3t_censored)]
        cells.append(dict(day=day, cell_var="runway_seed", cell=str(k), n=len(g), with3t_p50_s=float(ok.price_with_3t.median()) if len(ok) else np.nan,
                          with3t_censored=int(b(g.price_with_3t_censored).sum()), with3t_not_after_either=int((g.price_with_3t <= g.price_either_3t).sum())))
pd.DataFrame(cells).to_csv(OUT / "m7_ccode_cells.csv", index=False)
json.dump(summ, open(OUT / "m7_summary.json", "w"), indent=1)
