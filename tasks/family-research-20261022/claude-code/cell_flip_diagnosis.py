"""Why do the per-cell direction sources of October 18 not survive October 17?

Reads the saved stack tables for both days (stack-direction-sources-{oct18,oct17}-events.jsonl.gz) and the
cached replays, and tests four explanations for the cell flips, with the dipole discipline's own warning
in mind (apparent directional lifts have been trend and base-rate artifacts before):
  1. Day drift. The two sessions' price paths, by hour; whether a source's calls are mostly one sign in a
     cell (a near-constant call plus a drifting price is a hit rate that measures the drift, not the source);
     hit rates split by call sign; hit rates after removing the cell's median move.
  2. Activity level. Each day's own tercile cuts versus the other's; the key cells recut at the other day's
     absolute cuts, so 'mid' means the same tape on both days.
  3. Chance. Across every source x cell x target combination, the number of cells beyond a hit-rate band,
     against the binomial expectation under no information; and the cross-day sign agreement of (hit - 0.5).
  4. Composition. Hour-of-day and state composition of each cell on each day.
No trade cost. Nothing refit.
"""

import gzip
import json
import math
import os
import pickle
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

from scipy.stats import binom, spearmanr

HERE = Path(__file__).resolve().parent
CACHE_DIR = Path(os.environ.get("NG_REPLAY_CACHE_DIR", "/tmp/claude-0/-home-user-Markets/e6cffa19-4561-5119-b5f4-3474c12f9fe5/scratchpad"))
DAYS = {"oct02": dict(day0=1696194000), "oct03": dict(day0=1696280400), "oct17": dict(day0=1697490000), "oct18": dict(day0=1697576400)}
TICK = 1_000_000
SOURCES = ["pol", "next_state", "next_seed", "dip300", "dip300_strong", "book10", "touch", "recruit", "mom300"]
TARGETS = ["net300", "net600", "first3"]
KEY_CELLS = [("book10", "a_state", "A-persistent"), ("book10", "state_x_tercile", "A-fast-collapse|high"), ("dip300_strong", "vol_tercile", "mid"),
             ("dip300_strong", "state_x_tercile", "A-fast-collapse|mid"), ("mom300", "vol_tercile", "high"), ("mom300", "vol_tercile", "low"),
             ("pol", "a_state", "A-persistent"), ("book10", "state_x_tercile", "A-persistent|low")]


def load(tag):
    rows = [json.loads(l) for l in gzip.open(HERE / f"stack-direction-sources-{tag}-events.jsonl.gz", "rt")]
    for r in rows:
        r["state_x_tercile"] = f"{r['a_state']}|{r['vol_tercile']}"
    stream = pickle.load(open(CACHE_DIR / f"{tag}-replay-cache-v2.pkl", "rb"))
    return rows, stream


def hit(calls, moves):
    w = ag = f = 0
    for c, m in zip(calls, moves):
        if c is None or m is None or c == 0:
            continue
        cm = c * m
        w += cm > 0; ag += cm < 0; f += cm == 0
    return dict(n=w + ag + f, with_=w, flat=f, against=ag, hit=round(w / (w + ag), 3) if w + ag else None)


def fin(x):
    return x is not None and isinstance(x, float) and math.isfinite(x) or isinstance(x, int)


def day_facts(tag, stream):
    price = stream["price"]
    n = len(price)
    ff = [p for p in price if fin(p)]
    first = next(i for i in range(n) if fin(price[i]))
    last = min(stream["last_trade"], 86399)
    hourly = {}
    for h in range(24):
        lo, hi = h * 3600, min((h + 1) * 3600 - 1, last)
        if hi <= lo or not fin(price[lo]) or not fin(price[hi]):
            continue
        seg = [p for p in price[lo:hi + 1] if fin(p)]
        vol = (stream["cb"][hi + 1] - stream["cb"][lo]) + (stream["cs"][hi + 1] - stream["cs"][lo])
        hourly[f"{(h + 21) % 24:02d}Z"] = dict(net_ticks=round((price[hi] - price[lo]) / TICK), range_ticks=round((max(seg) - min(seg)) / TICK), lots=round(vol))
    return dict(open_price=price[first] / TICK, close_price=price[last] / TICK, net_ticks=round((price[last] - price[first]) / TICK),
                range_ticks=round((max(ff) - min(ff)) / TICK), total_lots=round(stream["cb"][last + 1] + stream["cs"][last + 1]), hourly=hourly)


def main():
    data = {tag: load(tag) for tag in DAYS}
    out = {"day_facts": {tag: day_facts(tag, s) for tag, (_, s) in data.items()}}
    # 1 + 4: key cells, call-sign split, demeaned hit, composition
    key = {}
    for src, dim, cell in KEY_CELLS:
        key[f"{src}|{cell}"] = {}
        for tag, (rows, _) in data.items():
            sub = [r for r in rows if r[dim] == cell]
            calls = [r["sources"].get(src) for r in sub]
            plus_share = round(sum(1 for c in calls if c == 1) / max(1, sum(1 for c in calls if c in (1, -1))), 3)
            d = dict(n=len(sub), call_plus_share=plus_share, hours=dict(Counter(r["hour_class"] for r in sub)), states=dict(Counter(r["a_state"] for r in sub)))
            for t in TARGETS:
                moves = [r["targets"][t] for r in sub]
                d[t] = hit(calls, moves)
                d[f"{t}_plus_calls"] = hit([c if c == 1 else None for c in calls], moves)
                d[f"{t}_minus_calls"] = hit([c if c == -1 else None for c in calls], moves)
                if t != "first3":
                    cm = median([m for m in moves if m is not None]) if any(m is not None for m in moves) else 0
                    d[f"{t}_cell_median_move"] = cm
                    d[f"{t}_demeaned"] = hit(calls, [None if m is None else m - cm for m in moves])
            key[f"{src}|{cell}"][tag] = d
    out["key_cells"] = key
    # 2: activity recut
    cuts = {}
    for tag, (rows, _) in data.items():
        vols = sorted(r["pre300_volume"] for r in rows)
        cuts[tag] = (vols[len(vols) // 3], vols[2 * len(vols) // 3])
    out["tercile_cuts_by_day"] = cuts
    recut = {}
    ref = cuts["oct18"]
    for tag, (rows, _) in data.items():
        for r in rows:
            r["recut"] = "low" if r["pre300_volume"] <= ref[0] else "mid" if r["pre300_volume"] <= ref[1] else "high"
        recut[f"{tag}_at_oct18_cuts"] = {}
        for tc in ("low", "mid", "high"):
            for st in (None, "A-fast-collapse", "A-persistent"):
                sub = [r for r in rows if r["recut"] == tc and (st is None or r["a_state"] == st)]
                lab = f"{st or 'all'}|{tc}"
                recut[f"{tag}_at_oct18_cuts"][lab] = {src: hit([r["sources"].get(src) for r in sub], [r["targets"]["net300"] for r in sub]) for src in ("book10", "dip300_strong", "mom300", "dip300")}
                recut[f"{tag}_at_oct18_cuts"][lab]["n"] = len(sub)
    out["recut"] = recut
    # 3: chance across all cells, and cross-day agreement
    cells = {}
    for tag, (rows, _) in data.items():
        tab = {}
        groups = [("all", lambda r: True)]
        for dim in ("a_state", "vol_tercile", "state_x_tercile", "hour_class"):
            for g in sorted({r[dim] for r in rows}):
                groups.append((f"{dim}={g}", (lambda d, v: (lambda r: r[d] == v))(dim, g)))
        for gname, pred in groups:
            sub = [r for r in rows if pred(r)]
            for src in SOURCES:
                for t in TARGETS:
                    h = hit([r["sources"].get(src) for r in sub], [r["targets"][t] for r in sub])
                    if h["hit"] is not None and (h["with_"] + h["against"]) >= 30:
                        tab[f"{gname}|{src}|{t}"] = h
        cells[tag] = tab
    chance = {}
    for tag, tab in cells.items():
        n_cells = len(tab)
        beyond = sum(1 for h in tab.values() if abs(h["hit"] - 0.5) >= 0.08)
        expected = sum(binom.cdf(math.floor((0.42) * (h["with_"] + h["against"])), h["with_"] + h["against"], 0.5) + binom.sf(math.ceil(0.58 * (h["with_"] + h["against"])) - 1, h["with_"] + h["against"], 0.5) for h in tab.values())
        extreme = sorted(tab.items(), key=lambda kv: -abs(kv[1]["hit"] - 0.5))[:12]
        chance[tag] = dict(cells_n30=n_cells, beyond_008=beyond, expected_beyond_008_if_no_information=round(expected, 1), most_extreme=[(k, v["hit"], v["with_"] + v["against"]) for k, v in extreme])
    tags = sorted(cells)
    common = sorted(set.intersection(*(set(cells[t]) for t in tags)))
    import itertools
    pair_agree = {}
    for a_, b_ in itertools.combinations(tags, 2):
        ag = sum(1 for k in common if (cells[a_][k]["hit"] - 0.5) * (cells[b_][k]["hit"] - 0.5) > 0)
        rho = spearmanr([cells[a_][k]["hit"] for k in common], [cells[b_][k]["hit"] for k in common])
        pair_agree[f"{a_}~{b_}"] = dict(same_sign_share=round(ag / len(common), 3), spearman_rho=round(float(rho[0]), 3))
    all_same = [k for k in common if len({(cells[t][k]["hit"] - 0.5) > 0 for t in tags}) == 1 and all(cells[t][k]["hit"] != 0.5 for t in tags)]
    beyond_all = [(k, [cells[t][k]["hit"] for t in tags]) for k in all_same if all(abs(cells[t][k]["hit"] - 0.5) >= 0.04 for t in tags)]
    # expected count of all-same-sign cells under independence = common / 2^(n-1)
    chance["cross_day"] = dict(days=tags, common_cells=len(common), pairwise=pair_agree, same_sign_all_days=len(all_same),
                               expected_same_sign_all_days_if_independent=round(len(common) / 2 ** (len(tags) - 1), 1),
                               cells_same_sign_all_days_and_beyond_004=beyond_all)
    out["chance"] = chance
    (HERE / "cell-flip-diagnosis-4day.json").write_text(json.dumps(out, indent=2, default=str) + "\n")
    print(json.dumps(out["day_facts"], indent=1))
    print("\n== key cells")
    for k, v in key.items():
        print(k)
        for tag, d in v.items():
            print(f"  {tag}: n {d['n']} call+ {d['call_plus_share']} hours {d['hours']} states {d['states']}")
            for t in TARGETS:
                extra = f" demeaned {d[t + '_demeaned']['hit']} (cell med {d[t + '_cell_median_move']})" if t != "first3" else ""
                print(f"     {t}: hit {d[t]['hit']} ({d[t]['with_']}/{d[t]['flat']}/{d[t]['against']}) | +calls {d[t + '_plus_calls']['hit']} n{d[t + '_plus_calls']['n']} | -calls {d[t + '_minus_calls']['hit']} n{d[t + '_minus_calls']['n']}{extra}")
    print("\n== tercile cuts", cuts)
    for k, v in recut.items():
        print(k)
        for lab, d in v.items():
            print(f"   {lab:26s} n {d['n']:4d} book10 {d['book10']['hit']} dip300_strong {d['dip300_strong']['hit']} (n {d['dip300_strong']['n']}) mom300 {d['mom300']['hit']} dip300 {d['dip300']['hit']}")
    print("\n== chance")
    print(json.dumps(chance, indent=1, default=str))


if __name__ == "__main__":
    main()
