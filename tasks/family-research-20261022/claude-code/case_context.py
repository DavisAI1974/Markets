"""Per-case context without the tape: per-second series from the replay cache and every dated event in the window.

For each case of cases-10.json on NG_TAG: the replay's per-second last price, midpoint, roll-20, buy and
sell lots (so fresh flow entering the 20 s window at t and expiring flow leaving it at t-20 can be drawn),
10-level depth by side, touch sizes and spread over [t0-300, t0+600]; the detector's own clocks (t0, onset,
confirmation, seed known, the two information horizons, the archived recognition); every other
frozen-detector event, size-one onset, first-observed family start and sealed touch-print decision whose
clock falls in the window, each with its id and absolute clock. Writes case-context-<tag>.json.
"""

import csv
import gzip
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from export_paths import SESSIONS  # noqa: E402
import data_locator  # noqa: E402

NS = 1_000_000_000
PRE, POST = 300, 600


def rows(name):
    return [json.loads(l) for l in gzip.open(HERE / name, "rt")]


def main():
    tag = os.environ.get("NG_TAG", "oct18")
    cases = [c for c in json.load(open(HERE / "cases-10.json")) if c["tag"] == tag]
    if not cases:
        return
    S = SESSIONS[tag]; day0 = S["day0"]; day = S["day"]
    os.environ["NG_DAY"] = day
    import exhaustion_clock_reanalysis_oct18 as X  # noqa: E402
    st = X.replay_cached()
    ev = [r for r in rows(f"exhaustion-clock-{tag}-events.jsonl.gz") if r["mode"] == "day"]
    cls = {r["t0"]: r["a_state"] for r in rows(f"frozen-a-classifier-{tag}-events.jsonl.gz")}
    eps = rows(f"size-one-episodes-{tag}.jsonl.gz")
    fam = list(csv.DictReader(data_locator.local_path(f"tasks/family-research-20261022/family-replication/run-42566535537-1/family-{day}/chronological-instance-index.csv").open()))
    decs = []
    with gzip.open(S["decisions"], "rt") as f:
        for line in f:
            d = json.loads(line)
            if d.get("disposition") == "CANDIDATE":
                decs.append(d)
    out = {}
    for c in cases:
        t0 = c["t0"]; lo, hi = t0 - PRE, t0 + POST
        lo_ns, hi_ns = (day0 + lo) * NS, (day0 + hi + 1) * NS
        series = []
        for s in range(max(0, lo), min(86399, hi) + 1):
            series.append(dict(sec=s, epoch_s=day0 + s, price=st["price"][s] if X.fin(st["price"][s]) else None, mid=st["mid"][s] if X.fin(st["mid"][s]) else None,
                               roll20=st["roll"][s] if X.fin(st["roll"][s]) else None, buy=st["buy"][s], sell=st["sell"][s],
                               buy_expiring=st["buy"][s - 20] if s >= 20 else 0, sell_expiring=st["sell"][s - 20] if s >= 20 else 0,
                               bid_depth=st["bid_depth"][s] if X.fin(st["bid_depth"][s]) else None, ask_depth=st["ask_depth"][s] if X.fin(st["ask_depth"][s]) else None,
                               bid_touch=st["bid_touch"][s] if X.fin(st["bid_touch"][s]) else None, ask_touch=st["ask_touch"][s] if X.fin(st["ask_touch"][s]) else None,
                               spread=st["spread"][s] if X.fin(st["spread"][s]) else None))
        me = next(r for r in ev if r["t0"] == t0)
        clocks = dict(t0=t0, onset=me["onset"], confirm=me["confirm"], seed_known_s=me["seed_known_s"], info_local=me["info_horizon_local_s"], info_refractory=me["info_horizon_refractory_s"],
                      recognition_s=me["archived_recognition_s"], recognition_receive_ns=c.get("recognition_receive_ns"), recognition_cursor=c.get("recognition_cursor"), candidate_id=c.get("candidate_id"))
        others = [dict(t0=r["t0"], epoch_s=day0 + r["t0"], polarity=r["polarity"], seed=r["seed_state"], a_state=cls.get(r["t0"]), onset=r["onset"], confirm=r["confirm"], recognition_s=r.get("archived_recognition_s"))
                  for r in ev if lo <= r["t0"] <= hi and r["t0"] != t0]
        onsets = [dict(onset_group=e["onset_group"], side=e["side"], onset=e["onset"], onset_ns=e["onset_ns"], sec=e["onset_ns"] // NS - day0, price_raw=e["original_price_raw"], outcome=e["outcome"], end_ns=e["end_ns"])
                  for e in eps if lo_ns <= e["onset_ns"] < hi_ns]
        fams = [dict(family_id=f["family_id"], start_recv_ns=int(f["start_recv_ns"]), sec=int(f["start_recv_ns"]) // NS - day0, input_cursor=f.get("input_cursor"), occurrence_count=f.get("occurrence_count"))
                for f in fam if f.get("start_recv_ns") and lo_ns <= int(f["start_recv_ns"]) < hi_ns]
        dd = [dict(group=d["group"], cursor=d["cursor"], known_by_ns=d["known_by_ns"], sec=d["known_by_ns"] // NS - day0, rule=d["rule"], side=d["side"], price_raw=d.get("price_raw"))
              for d in decs if lo_ns <= d["known_by_ns"] < hi_ns]
        out[str(t0)] = dict(case=c, day0=day0, window=[lo, hi], clocks=clocks, series=series, other_detector_events=others, size_one_onsets=onsets, family_starts=fams, touch_print_decisions=dd)
        print(tag, t0, "series", len(series), "other events", len(others), "onsets", len(onsets), "families", len(fams), "decisions", len(dd))
    (HERE / f"case-context-{tag}.json").write_text(json.dumps(out) + "\n")


if __name__ == "__main__":
    main()
