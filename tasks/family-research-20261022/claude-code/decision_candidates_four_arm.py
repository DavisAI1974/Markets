"""Four arms on the frozen touch-print candidate population, four sessions, from the exports.

The sealed standalone decisions apply the same frozen rules on every session (falling-touch.v1,
falling-touch+print.v1, prior-touch-print.v1) and mark CANDIDATE groups with a side. That gives a
population defined identically across the four days, unlike the October 18 first-family ledger. For each
falling-touch+print CANDIDATE (about 9,000 per day) the decision boundary is the decision's known_by
clock; the reference midpoint is the last completed group at or before it, the later midpoint the last
group at or before boundary + horizon (60 / 300 / 600 s), exactly as the first-family four arms read
outcomes. The baseline direction is the rule's side read as the pressure direction (a falling bid touch =
selling pressure, oriented so positive = continuation of that pressure). Arms:
  baseline   the rule side
  + flow     the 60 s aggressor imbalance (per-second replay, window ending at the boundary second)
             opposes the rule side
  + book     the 10-level displayed depth skew at the boundary second opposes the rule side
  + both     both oppose
Also the inverse cells (flow agrees, book agrees) and an activity split by the 300 s volume tercile.
Per-second replay operands are one-second approximations of the ns-exact ROOT quantities the first-family
ledger carried; stated. No trade cost.
"""

import gzip
import json
import os
import sys
from bisect import bisect_right
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from export_paths import SESSIONS  # noqa: E402
from export_recognition_outcomes import load_groups  # noqa: E402

NS = 1_000_000_000
TICK = 1_000_000
HORIZONS = (60, 300, 600)
RULE = "falling-touch+print.v1"


def sgn(x):
    return (x > 0) - (x < 0)


def tri(vals):
    v = [x for x in vals if x is not None]
    w = sum(1 for x in v if x > 0); ag = sum(1 for x in v if x < 0); fl = len(v) - w - ag
    return dict(n=len(v), continue_=w, flat=fl, reverse=ag, continue_share_nonflat=round(w / max(1, w + ag), 3) if v else None, median_ticks=median(v) if v else None)


def main():
    tag = os.environ.get("NG_TAG", "oct18")
    S = SESSIONS[tag]
    os.environ["NG_DAY"] = S["day"]
    import exhaustion_clock_reanalysis_oct18 as X  # noqa: E402
    stream = X.replay_cached()
    recv, mid2, bsz, asz, cur = load_groups(S["groups"])
    tape_end = recv[-1]
    bdep, adep, cb, cs = stream["bid_depth"], stream["ask_depth"], stream["cb"], stream["cs"]
    rows = []
    rule_counts = Counter()
    with gzip.open(S["decisions"], "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            rule_counts[(d["rule"], d["disposition"])] += 1
            if d["rule"] != RULE or d["disposition"] != "CANDIDATE":
                continue
            kb = d["known_by_ns"]
            idx = bisect_right(recv, kb) - 1
            if idx < 0:
                continue
            sec = kb // NS - S["day0"]
            if not (0 <= sec < 86400):
                continue
            pressure = -1 if d["side"] == "bid" else 1   # falling bid touch = selling pressure, falling ask touch = buying pressure
            imb60, vol60 = X.window_imb(cb, cs, sec, 60)
            imb300, vol300 = X.window_imb(cb, cs, sec, 300)
            bd, ad = bdep[sec], adep[sec]
            skew = None if not (X.fin(bd) and X.fin(ad)) or bd + ad == 0 else (bd - ad) / (bd + ad)
            ref2 = mid2[idx]
            moves = {}
            for h in HORIZONS:
                target = kb + h * NS
                if target > tape_end:
                    moves[str(h)] = None; continue
                j = bisect_right(recv, target) - 1
                moves[str(h)] = pressure * (mid2[j] - ref2) / (2 * TICK)
            rows.append(dict(group=d["group"], known_by_ns=kb, side=d["side"], pressure=pressure, sec=sec,
                             flow60=None if imb60 is None else sgn(imb60) * pressure, book=None if skew is None else sgn(skew) * pressure,
                             vol300=vol300, moves=moves))
    vols = sorted(r["vol300"] for r in rows)
    cuts = (vols[len(vols) // 3], vols[2 * len(vols) // 3]) if vols else (0, 0)
    for r in rows:
        r["tercile"] = "low" if r["vol300"] <= cuts[0] else "mid" if r["vol300"] <= cuts[1] else "high"
    def arm_table(sub):
        arms = {"baseline": sub, "+flow opposes": [r for r in sub if r["flow60"] == -1], "+book opposes": [r for r in sub if r["book"] == -1],
                "+both oppose": [r for r in sub if r["flow60"] == -1 and r["book"] == -1],
                "inverse: flow agrees": [r for r in sub if r["flow60"] == 1], "inverse: book agrees": [r for r in sub if r["book"] == 1],
                "inverse: both agree": [r for r in sub if r["flow60"] == 1 and r["book"] == 1]}
        return {k: {h: tri([r["moves"][str(h)] for r in v]) for h in HORIZONS} | {"n": len(v)} for k, v in arms.items()}
    out = dict(session=tag, export_scope=S["export_scope"], rule=RULE, decision_rule_counts={f"{a}|{b}": n for (a, b), n in rule_counts.items()},
               candidates=len(rows), by_side=dict(Counter(r["side"] for r in rows)), vol_cuts=cuts,
               all=arm_table(rows), by_side_arms={s: arm_table([r for r in rows if r["side"] == s]) for s in ("bid", "ask")},
               by_tercile={t: arm_table([r for r in rows if r["tercile"] == t]) for t in ("low", "mid", "high")},
               book_skew_sign_share=dict(Counter({1: "bid_heavy", -1: "ask_heavy", 0: "even", None: "none"}[r["book"] * r["pressure"] if r["book"] is not None else None] for r in rows)))
    (HERE / f"decision-candidates-four-arm-{tag}-summary.json").write_text(json.dumps(out, indent=2, default=str) + "\n")
    with gzip.open(HERE / f"decision-candidates-four-arm-{tag}-events.jsonl.gz", "wt") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(tag, S["export_scope"], "candidates", len(rows), out["by_side"], "book skew (absolute):", out["book_skew_sign_share"])
    for k, v in out["all"].items():
        print(f"  {k:22s} n {v['n']:5d} " + " | ".join(f"{h}s {v[h]['continue_']}/{v[h]['flat']}/{v[h]['reverse']} ({v[h]['continue_share_nonflat']}) med {v[h]['median_ticks']}" for h in HORIZONS))
    for s in ("bid", "ask"):
        v = out["by_side_arms"][s]
        print(f"  side {s}: baseline", {h: v["baseline"][h]["continue_share_nonflat"] for h in HORIZONS}, "+both", {h: v["+both oppose"][h]["continue_share_nonflat"] for h in HORIZONS}, "n", v["+both oppose"]["n"])
    for t in ("low", "mid", "high"):
        v = out["by_tercile"][t]
        print(f"  tercile {t}: baseline", {h: v["baseline"][h]["continue_share_nonflat"] for h in HORIZONS}, "+both", {h: v["+both oppose"][h]["continue_share_nonflat"] for h in HORIZONS}, "n", v["+both oppose"]["n"])


if __name__ == "__main__":
    main()
