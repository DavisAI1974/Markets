"""The frozen SSOS play and the absorption filter on four sessions.

The frozen research play NG_CHAIN_D4_SSOS_CONTINUATION_V1 (Phase-2 findings, 2026-08-18): the four
preceding exhaustion episodes' +60 seed states must be S,S,O,S (oldest to newest), each knowable before the
current t0; wait for the current endpoint to be causally confirmed; stand down if a successor starts before
confirmation; enter WITH the current polarity at onset+5 if confirmation is known by then; exit at onset+30.
P,O,X was killed on its held week and is not a play. This script reproduces the play's universe, frequency
and gross return per session from the frozen-detector events of sections 11 to 15, then tests the
absorption regularity of section 14.5 as a filter at the play's own horizon: split every eligible entry by
whether the current burst came from the side the previous event's state forecast (same side after a
persistent state or P seed, opposite after fast-collapse or O seed) or from the other side. Returns are
exit displacement minus entry displacement in ticks, oriented to the current polarity, last-trade price
forward-filled per second (the chain work used the same per-second price). No trade cost.
"""

import gzip
import json
import os
import sys
from collections import Counter
from pathlib import Path
from statistics import mean, median

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

ENTRY, EXIT = 5, 30
PLAY = "SSOS"  # prev4_states is the oldest-to-newest string of the four predecessors' seed states


def main():
    tag = os.environ.get("NG_TAG", "oct18")
    day = {"oct18": "20231018", "oct17": "20231017", "oct03": "20231003", "oct02": "20231002"}[tag]
    os.environ["NG_DAY"] = day
    import exhaustion_clock_reanalysis_oct18 as X  # noqa: E402
    stream = X.replay_cached()
    price = stream["price"]
    last = min(stream["last_trade"], 86399)
    ev = [json.loads(l) for l in gzip.open(HERE / f"exhaustion-clock-{tag}-events.jsonl.gz", "rt")]
    ev = sorted((r for r in ev if r["mode"] == "day"), key=lambda r: r["t0"])
    cls = {r["t0"]: r["a_state"] for r in (json.loads(l) for l in gzip.open(HERE / f"frozen-a-classifier-{tag}-events.jsonl.gz", "rt"))}
    rows = []
    for i, r in enumerate(ev):
        t0, pol, onset, confirm = r["t0"], r["polarity"], r["onset"], r["confirm"]
        if onset is None or confirm is None:
            continue
        reasons = []
        if confirm > onset + ENTRY:
            reasons.append("not_confirmed_by_entry")
        if i + 1 < len(ev) and ev[i + 1]["t0"] <= confirm:
            reasons.append("successor_before_confirmation")
        if i < 4 or any(ev[i - k]["t0"] + 60 > t0 for k in range(1, 5)):
            reasons.append("predecessors_not_knowable")
        if onset + EXIT > last:
            reasons.append("censored")
        pe, px = price[onset + ENTRY] if onset + ENTRY <= last else None, price[onset + EXIT] if onset + EXIT <= last else None
        ret = None if not (X.fin(pe) and X.fin(px)) else pol * (px - pe) / X.TICK
        prev = ev[i - 1] if i else None
        if prev is None:
            expected = None
        else:
            ps, pa = prev["seed_state"], cls.get(prev["t0"])
            fc = prev["polarity"] if (pa == "A-persistent" or ps == "P") else -prev["polarity"]
            expected = int(fc == pol)
        rows.append(dict(t0=t0, polarity=pol, onset=onset, confirm=confirm, eligible=not reasons, reasons=reasons, prev4=r["prev4_states"],
                         is_play=(r["prev4_states"] == PLAY), return_ticks=ret, expected_side=expected, prev_seed=None if prev is None else prev["seed_state"],
                         prev_a_state=None if prev is None else cls.get(prev["t0"]), same_as_prev=None if prev is None else int(prev["polarity"] == pol)))
    def desc(sub):
        v = [r["return_ticks"] for r in sub if r["return_ticks"] is not None]
        return dict(n=len(v), mean=round(mean(v), 3) if v else None, median=median(v) if v else None,
                    with_=sum(1 for x in v if x > 0), flat=sum(1 for x in v if x == 0), against=sum(1 for x in v if x < 0),
                    with_share_nonflat=round(sum(1 for x in v if x > 0) / max(1, sum(1 for x in v if x != 0)), 3) if v else None)
    uni = [r for r in rows if r["eligible"]]
    play = [r for r in uni if r["is_play"]]
    out = dict(session=tag, events=len(ev), eligible_universe=len(uni), ineligible_reasons=dict(Counter(x for r in rows for x in r["reasons"])),
               universe=desc(uni), play=dict(frequency=round(len(play) / len(uni), 4) if uni else None, **desc(play)),
               play_rows=[dict(t0=r["t0"], polarity=r["polarity"], return_ticks=r["return_ticks"], expected_side=r["expected_side"], same_as_prev=r["same_as_prev"]) for r in play],
               universe_by_expected_side={k: desc([r for r in uni if r["expected_side"] == k]) for k in (1, 0)},
               universe_by_same_as_prev={k: desc([r for r in uni if r["same_as_prev"] == k]) for k in (1, 0)},
               universe_by_prev_seed={k: desc([r for r in uni if r["prev_seed"] == k]) for k in "PSOX"},
               universe_by_prev_seed_x_same={f"{k}|same={s}": desc([r for r in uni if r["prev_seed"] == k and r["same_as_prev"] == s]) for k in "PSOX" for s in (1, 0)},
               play_by_expected_side={k: desc([r for r in play if r["expected_side"] == k]) for k in (1, 0)},
               play_by_same_as_prev={k: desc([r for r in play if r["same_as_prev"] == k]) for k in (1, 0)},
               prev4_top=dict(Counter(r["prev4"] for r in uni if r["prev4"]).most_common(8)))
    (HERE / f"chain-play-filter-{tag}-summary.json").write_text(json.dumps(out, indent=2, default=str) + "\n")
    with gzip.open(HERE / f"chain-play-filter-{tag}-rows.jsonl.gz", "wt") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(tag, "events", len(ev), "eligible", len(uni), out["ineligible_reasons"])
    print("  universe", out["universe"], "| play", {k: out["play"][k] for k in ("n", "frequency", "mean", "median", "with_", "flat", "against")})
    print("  universe by expected side:", out["universe_by_expected_side"])
    print("  universe by same-as-prev:", out["universe_by_same_as_prev"])
    print("  universe by prev seed:", {k: (v["n"], v["mean"], v["with_share_nonflat"]) for k, v in out["universe_by_prev_seed"].items()})
    print("  prev seed x same:", {k: (v["n"], v["mean"], v["with_share_nonflat"]) for k, v in out["universe_by_prev_seed_x_same"].items()})
    print("  play by expected side:", out["play_by_expected_side"], "| by same:", out["play_by_same_as_prev"])


if __name__ == "__main__":
    main()
