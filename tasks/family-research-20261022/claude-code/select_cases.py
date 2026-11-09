"""Select ten individual cases across the four sessions for the five coordinated views.

Every case is a frozen-detector event with an archived Native recognition (so recognition can be marked on
its own clock). Selection rules are stated per case and applied to the row files; the chosen ids and clocks
are written to cases-10.json. Nothing here is a finding; it is a sampling of individual lifecycles including
failed and flat moves, with two cases that are consecutive bursts on one level for comparison.
"""

import gzip
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DAY0 = {"oct02": 1696194000, "oct03": 1696280400, "oct17": 1697490000, "oct18": 1697576400}


def rows(name):
    return [json.loads(l) for l in gzip.open(HERE / name, "rt")]


def load(tag):
    ev = [r for r in rows(f"exhaustion-clock-{tag}-events.jsonl.gz") if r["mode"] == "day"]
    cls = {r["t0"]: r for r in rows(f"frozen-a-classifier-{tag}-events.jsonl.gz")}
    nb = {r["t0"]: r for r in rows(f"next-burst-forecast-{tag}-events.jsonl.gz")}
    by = {r["t0"]: r for r in rows(f"beyond-direction-prebirth-{tag}-events.jsonl.gz")}
    play = {r["t0"]: r for r in rows(f"chain-play-filter-{tag}-rows.jsonl.gz")}
    dp = {}
    for r in rows(f"dipole-post-recognition-{tag}-rows.jsonl.gz"):
        dp[r["birth_second"] - DAY0[tag]] = r
    out = []
    for i, r in enumerate(ev):
        if r.get("archived_recognition_s") is None:
            continue
        t0 = r["t0"]
        c = dict(tag=tag, t0=t0, t0_epoch_s=DAY0[tag] + t0, polarity=r["polarity"], seed=r["seed_state"], a_state=cls[t0]["a_state"], onset=r["onset"], confirm=r["confirm"],
                 runway_s=r["runway_s"], confirm_offset_s=r["confirm_offset_s"], recognition_s=r["archived_recognition_s"], recognition_offset_s=r["archived_recognition_offset_s"],
                 hour_utc=(DAY0[tag] + t0) % 86400 // 3600, m_confirm=r.get("move_t0_to_confirm"), m300=r.get("move_seed_known_plus300"), m60=r.get("move_seed_known_plus60"),
                 range600=by.get(t0, {}).get("plus60_600_range"), vol300=by.get(t0, {}).get("pre300_volume"),
                 next_t0=nb.get(t0, {}).get("next_t0"), next_pol=nb.get(t0, {}).get("next_pol"), state_hit=nb.get(t0, {}).get("state_hit"), next_window=nb.get(t0, {}).get("state_next_t0_to_next_confirm"),
                 is_play=play.get(t0, {}).get("is_play") and play.get(t0, {}).get("eligible"), play_return=play.get(t0, {}).get("return_ticks"),
                 candidate_id=dp.get(t0, {}).get("candidate_id"), recognition_receive_ns=dp.get(t0, {}).get("recognition_receive_ns"), recognition_cursor=dp.get(t0, {}).get("recognition_cursor"))
        c["m300_with"] = None if c["m300"] is None else c["m300"] * c["polarity"] if False else c["m300"]  # move_seed_known_plus300 is already oriented? keep raw, orient below
        out.append(c)
    return out


def pick(cands, key, pred=lambda c: True, reverse=True):
    pool = [c for c in cands if pred(c) and key(c) is not None]
    pool.sort(key=key, reverse=reverse)
    return pool[0] if pool else None


def main():
    C = {t: load(t) for t in DAY0}
    def oriented(c, f):
        v = c.get(f)
        return None if v is None else v  # the exhaustion summary stored moves already oriented to polarity (tri() counted with/against on them)
    cases = []
    def add(label, rule, c):
        if c is None:
            print("NO CASE for", label); return
        cases.append(dict(label=label, rule=rule, **c)); print(f"{len(cases):2d} {label:42s} {c['tag']} t0 {c['t0']} {c['candidate_id']} pol {c['polarity']} {c['a_state']} seed {c['seed']} runway {c['runway_s']} rec+{c['recognition_offset_s']} m_confirm {c['m_confirm']} m300 {c['m300']} range600 {c['range600']} hour {c['hour_utc']}")
    us = lambda c: 12 <= c["hour_utc"] <= 20
    add("Oct 18 continuation, US day", "largest oriented move by seed-known +300 s among US-day events", pick(C["oct18"], lambda c: oriented(c, "m300"), us))
    add("Oct 18 reversal, US day", "most negative oriented move by seed-known +300 s among US-day events", pick(C["oct18"], lambda c: oriented(c, "m300"), us, reverse=False))
    add("Oct 18 SSOS play instance", "an eligible S,S,O,S play entry, the one with the most negative gross return", pick(C["oct18"], lambda c: -(c["play_return"] or 0), lambda c: c["is_play"]))
    add("Oct 18 early recognition, long runway", "recognised before confirmation with the longest runway", pick(C["oct18"], lambda c: c["runway_s"], lambda c: c["recognition_offset_s"] < c["confirm_offset_s"]))
    add("Oct 17 inside the 13:00 UTC collapse", "largest oriented +300 s move in the 13:00 hour", pick(C["oct17"], lambda c: abs(oriented(c, "m300") or 0), lambda c: c["hour_utc"] == 13))
    add("Oct 17 absorbed pair (first burst)", "persistent state, next burst from the forecast side, price against that burst; largest against", pick(C["oct17"], lambda c: -(c["next_window"] or 0), lambda c: c["a_state"] == "A-persistent" and c["state_hit"] == 1 and (c["next_window"] or 0) < 0 and us(c)))
    add("Oct 3 continuation in the 15:00 hour", "largest oriented +300 s move in the 15:00 hour", pick(C["oct03"], lambda c: oriented(c, "m300"), lambda c: c["hour_utc"] == 15))
    add("Oct 3 flat overnight move", "persistent, overnight, zero move at +60 and +300, lowest pre-300 s volume", pick(C["oct03"], lambda c: -(c["vol300"] or 0), lambda c: c["a_state"] == "A-persistent" and c["hour_utc"] < 10 and c["m300"] == 0 and c["m60"] == 0))
    add("Oct 2 inside the 14:00 UTC hour", "largest |oriented +300 s move| in the 14:00 hour", pick(C["oct02"], lambda c: abs(oriented(c, "m300") or 0), lambda c: c["hour_utc"] == 14))
    add("Oct 2 failed move", "moved with polarity by confirmation by 2+ ticks, then 2+ ticks the other way by +300", pick(C["oct02"], lambda c: (c["m_confirm"] or 0) - (c["m300"] or 0), lambda c: (c["m_confirm"] or 0) >= 2 and (c["m300"] or 0) <= -2))
    (HERE / "cases-10.json").write_text(json.dumps(cases, indent=2) + "\n")


if __name__ == "__main__":
    main()
