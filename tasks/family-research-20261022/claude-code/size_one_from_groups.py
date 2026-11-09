"""Derive the size-one onset episodes of a session from the standalone group export, and validate on October 18.

A size-one onset is a group close at which one side's touch shows exactly one lot where the previous group
close did not: NEW_BEST when the touch price changed, STANDING_BEST_SHRANK when the price is unchanged and
the previous size was larger. The first end is the first later group close at which that side's touch is
no longer (that price, one lot): RETREATED if the price is worse for that side, SIZE_RECOVERED_AT_SAME_PRICE
if the price is unchanged and the size larger, IMPROVED if the price is better. Entry is the first group
close at or after onset receive + 1 ms (the assumed paper entry of the October 18 ledger); the end is
BY_ENTRY when its group is at or before the entry group, AFTER_ENTRY otherwise. Prior touch = the previous
group's touch on that side (price, size, order count). The October 18 ledger (october18-size-one-mechanisms,
1,012 episodes) covers the 13:00 UTC hour only; this script derives the whole session on every day and
validates the 13:00 hour of October 18 against the ledger by (onset group, side). Tape-side mechanics
(next displayed level, fill-linked reductions) come from size_one_tape_pass.py.
"""

import gzip
import json
import os
import sys
from bisect import bisect_left
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from export_paths import SESSIONS  # noqa: E402

NS = 1_000_000_000
ENTRY_NS = 1_000_000


def main():
    tag = os.environ.get("NG_TAG", "oct18")
    S = SESSIONS[tag]
    groups = []
    with gzip.open(S["groups"], "rt", encoding="utf-8") as f:
        for line in f:
            g = json.loads(line)
            if g["bid"] and g["ask"] and g["bid"][0] is not None and g["ask"][0] is not None:
                groups.append((g["group_ordinal"], g["first_cursor"], g["close_cursor"], g["receive_ns"], tuple(g["bid"]), tuple(g["ask"])))
    recv = [g[3] for g in groups]
    eps = []
    for i in range(1, len(groups)):
        prev, cur = groups[i - 1], groups[i]
        for side, k in (("B", 4), ("A", 5)):
            pt, ct = prev[k], cur[k]
            if ct[1] != 1:
                continue
            if ct[0] != pt[0]:
                onset = "NEW_BEST"
                better = (ct[0] > pt[0]) if side == "B" else (ct[0] < pt[0])
            elif pt[1] > 1:
                onset = "STANDING_BEST_SHRANK"; better = None
            else:
                continue  # still one lot at the same price: no onset
            # first end
            end_i = None
            for j in range(i + 1, len(groups)):
                t = groups[j][k]
                if t[0] != ct[0] or t[1] != 1:
                    end_i = j; break
            if end_i is None:
                outcome, end = "CENSORED", None
            else:
                t = groups[end_i][k]
                if t[0] == ct[0]:
                    outcome = "SIZE_RECOVERED_AT_SAME_PRICE"
                elif (t[0] < ct[0]) if side == "B" else (t[0] > ct[0]):
                    outcome = "RETREATED"
                else:
                    outcome = "IMPROVED"
                end = groups[end_i]
            entry_i = bisect_left(recv, cur[3] + ENTRY_NS)
            eps.append(dict(side=side, onset=onset, new_best_is_better=better, onset_group=cur[0], onset_first_cursor=cur[1], onset_cursor=cur[2], onset_ns=cur[3],
                            original_price_raw=ct[0], prior_touch=list(pt), other_touch=list(cur[5] if side == "B" else cur[4]),
                            end_group=None if end is None else end[0], end_cursor=None if end is None else end[2], end_ns=None if end is None else end[3],
                            ending_touch=None if end is None else list(end[k]), outcome=outcome,
                            entry_group=groups[entry_i][0] if entry_i < len(groups) else None,
                            end_vs_entry=None if end is None else ("BY_ENTRY" if entry_i < len(groups) and end[0] <= groups[entry_i][0] else "AFTER_ENTRY"),
                            hour_utc=(cur[3] // NS) % 86400 // 3600, t_session=cur[3] // NS - S["day0"]))
    out = dict(session=tag, export_scope=S["export_scope"], groups=len(groups), episodes=len(eps),
               by_side_onset=dict(Counter(f"{e['side']}|{e['onset']}" for e in eps)), outcomes=dict(Counter(e["outcome"] for e in eps)),
               end_vs_entry=dict(Counter(str(e["end_vs_entry"]) for e in eps)), by_hour=dict(sorted(Counter(e["hour_utc"] for e in eps).items())))
    if tag == "oct18":
        led = [json.loads(l) for l in gzip.open(HERE.parent / "october18-size-one-mechanisms.jsonl.gz", "rt")]
        lkey = {(r["onset_group"], r["side"]): r for r in led}
        mine13 = [e for e in eps if e["hour_utc"] == 13]
        mkey = {(e["onset_group"], e["side"]): e for e in mine13}
        both = set(lkey) & set(mkey)
        onset_agree = sum(1 for k in both if lkey[k]["onset"] == mkey[k]["onset"])
        outcome_agree = sum(1 for k in both if lkey[k]["outcome"] == mkey[k]["outcome"])
        end_agree = sum(1 for k in both if lkey[k]["end_group"] == mkey[k]["end_group"])
        eve_agree = sum(1 for k in both if lkey[k]["end_vs_entry"] == mkey[k]["end_vs_entry"])
        only_mine = [mkey[k] for k in set(mkey) - set(lkey)]
        only_led = [lkey[k] for k in set(lkey) - set(mkey)]
        out["validation_oct18_13h"] = dict(ledger=len(led), derived_13h=len(mine13), matched=len(both), onset_type_agree=onset_agree, outcome_agree=outcome_agree,
                                           end_group_agree=end_agree, end_vs_entry_agree=eve_agree,
                                           only_derived=dict(n=len(only_mine), by=dict(Counter(f"{e['side']}|{e['onset']}|better={e['new_best_is_better']}" for e in only_mine))),
                                           only_ledger=dict(n=len(only_led), by=dict(Counter(f"{e['side']}|{e['onset']}" for e in only_led)), sample=[(e["onset_group"], e["side"], e["onset"], e["prior_touch"]) for e in only_led[:5]]),
                                           outcome_disagreements=dict(Counter(f"{lkey[k]['outcome']}->{mkey[k]['outcome']}" for k in both if lkey[k]["outcome"] != mkey[k]["outcome"])))
    (HERE / f"size-one-episodes-{tag}.jsonl.gz").open("wb").close()
    with gzip.open(HERE / f"size-one-episodes-{tag}.jsonl.gz", "wt") as f:
        for e in eps:
            f.write(json.dumps(e) + "\n")
    (HERE / f"size-one-episodes-{tag}-summary.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
