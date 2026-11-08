"""Four-arm flow/book comparison on the 749 October 18 first-observed family events.

Population: the 749 first-observed structural-family starts in the saved screening
ledger (instance-market-review-20261023/candidate-flow-transition-audit.csv). Each
event has a strict pre-event decision boundary (cutoff_ns, cursor_cap) and the
saved pre-event ROOT measurements (rolling aggressor quantities over 1/5/20/60/300 s,
full displayed depth by side, spread). Outcomes are read from the pinned standalone
group export: the last completed group whose receive clock is at or before the
decision boundary supplies the reference midpoint; the last completed group at or
before boundary + horizon supplies the later midpoint. Nothing is interpolated.

Arms share one eligible population: events whose 1-second and 5-second aggressor
windows both have a nonzero, agreeing net direction ("recent flow"). Outcomes are
oriented so that positive means the midpoint continued in the recent-flow direction.

  baseline        recent flow direction only
  + flow          60-second window opposes the recent direction (the 375/391 transition)
  + book          full displayed depth skew opposes the recent direction
  + both          the original 375/391 stack when recent flow is selling; its mirror
                  (inverse stack) when recent flow is buying

The script also reproduces the saved 50-case screen, builds the inverse stack and
activity-matched controls, and counts overlapping 600-second windows.
"""

import csv
import gzip
import json
from bisect import bisect_right
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[3]
GROUPS = ROOT / ("research/kalshi/adaptive_wavepacket_20261108/markets_bridge/tasks/"
                 "root-bounded-replay/retained/october18-standalone-inputs/groups.jsonl.gz")
AUDIT = ROOT / ("artifacts/sqlite-triage/20261022/families/instance-market-review-20261023/"
                "candidate-flow-transition-audit.csv")
OUT = Path(__file__).resolve().parent
NS = 1_000_000_000
TICK = 1_000_000
HORIZONS = (1, 5, 20, 60, 120, 300, 600)
TAPE_END_NS = None


def load_groups():
    recv, cursor, mid, bidp, askp, bids, asks = [], [], [], [], [], [], []
    with gzip.open(GROUPS, "rt", encoding="utf-8") as stream:
        for line in stream:
            g = json.loads(line)
            recv.append(g["receive_ns"])
            cursor.append(g["close_cursor"])
            mid.append(g["bid"][0] + g["ask"][0])  # twice the midpoint, integer raw
            bidp.append(g["bid"][0]); askp.append(g["ask"][0])
            bids.append(g["bid"][1]); asks.append(g["ask"][1])
    return recv, cursor, mid, bidp, askp, bids, asks


def fnum(value):
    return None if value in ("", None) else float(value)


def sign(x):
    return (x > 0) - (x < 0)


def main():
    recv, cursor, mid2, bidp, askp, bids, asks = load_groups()
    tape_end = recv[-1]
    rows = list(csv.DictReader(AUDIT.open()))
    per_event = []
    for r in rows:
        cutoff = int(r["cutoff_ns"])
        start = int(r["start_recv_ns"])
        pre_index = bisect_right(recv, cutoff) - 1
        # the saved pre-event cursor must agree with the as-of group we pick
        pre_cursor_saved = int(r["pre_input_cursor"])
        agree = cursor[pre_index] == pre_cursor_saved
        pre_mid2 = mid2[pre_index]
        b60, s60 = fnum(r["root.activity.60.trade_buy_aggressor_qty"]), fnum(r["root.activity.60.trade_sell_aggressor_qty"])
        b5, s5 = fnum(r["root.activity.5.trade_buy_aggressor_qty"]), fnum(r["root.activity.5.trade_sell_aggressor_qty"])
        b1, s1 = fnum(r["root.activity.1.trade_buy_aggressor_qty"]), fnum(r["root.activity.1.trade_sell_aggressor_qty"])
        b20, s20 = fnum(r["root.activity.20.trade_buy_aggressor_qty"]), fnum(r["root.activity.20.trade_sell_aggressor_qty"])
        bidd, askd = fnum(r["root.bid_depth_full"]), fnum(r["root.ask_depth_full"])
        d1 = sign(b1 - s1); d5 = sign(b5 - s5); d60 = sign(b60 - s60); d20 = sign(b20 - s20)
        recent = d1 if d1 and d1 == d5 else 0
        depth_sign = sign(bidd - askd)
        outcomes = {}
        for h in HORIZONS:
            target = start + h * NS
            if target > tape_end:
                outcomes[h] = None  # censored at the retained tape end
                continue
            idx = bisect_right(recv, target) - 1
            outcomes[h] = (mid2[idx] - pre_mid2) / (2 * TICK)  # ticks of 0.001
        # pre-event 1 s and 5 s midpoint change (pre-start displacement), for context
        back = {}
        for h in (1, 5, 60):
            idx = bisect_right(recv, cutoff - h * NS) - 1
            back[h] = (pre_mid2 - mid2[idx]) / (2 * TICK) if idx >= 0 else None
        per_event.append(dict(
            instance=int(r["instance"]), family_id=r["family_id"], start_recv_ns=start, cutoff_ns=cutoff,
            pre_close_cursor=cursor[pre_index], pre_receive_ns=recv[pre_index], pre_cursor_agrees=agree,
            pre_book_age_s=(cutoff - recv[pre_index]) / NS,
            pre_bid_raw=bidp[pre_index], pre_ask_raw=askp[pre_index], pre_bid_size=bids[pre_index], pre_ask_size=asks[pre_index],
            spread_ticks=(askp[pre_index] - bidp[pre_index]) / TICK,
            buy1=b1, sell1=s1, buy5=b5, sell5=s5, buy20=b20, sell20=s20, buy60=b60, sell60=s60,
            bid_depth_full=bidd, ask_depth_full=askd, depth_sign=depth_sign,
            near_depth_imbalance=fnum(r["root.depth_imbalance_n"]), near_sign=sign(fnum(r["root.depth_imbalance_n"]) or 0),
            touch_sign=sign(bids[pre_index] - asks[pre_index]),
            d1=d1, d5=d5, d20=d20, d60=d60, recent=recent,
            saved_match=r["candidate_status"] == "matched",
            chronological_quarter=int(r["chronological_quarter"]),
            hour_utc=(start // NS) // 3600 % 24,
            prior_move_ticks=back,
            move_ticks=outcomes,
        ))

    # reproduce the saved screen
    screen = [e for e in per_event if e["buy60"] is not None and e["buy60"] > e["sell60"] and e["sell5"] > e["buy5"]
              and e["sell1"] > e["buy1"] and e["bid_depth_full"] > e["ask_depth_full"]]
    inverse = [e for e in per_event if e["buy60"] is not None and e["sell60"] > e["buy60"] and e["buy5"] > e["sell5"]
               and e["buy1"] > e["sell1"] and e["ask_depth_full"] > e["bid_depth_full"]]
    saved = {e["instance"] for e in per_event if e["saved_match"]}
    reproduced = {e["instance"] for e in screen}

    eligible = [e for e in per_event if e["recent"]]

    def arm_cells(events):
        cells = defaultdict(list)
        for e in events:
            flow = "60s_opposes" if e["d60"] == -e["recent"] else "60s_agrees" if e["d60"] == e["recent"] else "60s_balanced"
            book = ("depth_opposes" if e["depth_sign"] == -e["recent"] else
                    "depth_agrees" if e["depth_sign"] == e["recent"] else "depth_equal")
            cells[(flow, book)].append(e)
        return cells

    def clusters(events):
        """Count chains of events whose 600-second outcome windows overlap."""
        starts = sorted(e["start_recv_ns"] for e in events)
        n = 0; last_end = -1
        for s in starts:
            if s > last_end:
                n += 1
            last_end = max(last_end, s + 600 * NS)
        return n

    def describe(events, label):
        out = dict(label=label, events=len(events), overlap_clusters_600s=clusters(events),
                   recent_sell=sum(1 for e in events if e["recent"] < 0),
                   recent_buy=sum(1 for e in events if e["recent"] > 0), horizons={})
        for h in HORIZONS:
            vals = [(e["move_ticks"][h] * e["recent"]) for e in events if e["move_ticks"][h] is not None]
            censored = sum(1 for e in events if e["move_ticks"][h] is None)
            if not vals:
                out["horizons"][h] = dict(censored=censored); continue
            srt = sorted(vals)
            q = lambda p: srt[min(len(srt) - 1, int(p * (len(srt) - 1)))]
            out["horizons"][h] = dict(
                n=len(vals), censored=censored,
                continued=sum(1 for v in vals if v > 0), flat=sum(1 for v in vals if v == 0),
                reversed=sum(1 for v in vals if v < 0),
                median_ticks=median(vals), q25=q(0.25), q75=q(0.75), min=srt[0], max=srt[-1],
            )
        return out

    cells = arm_cells(eligible)
    arms = dict(
        baseline=describe(eligible, "recent 1 s and 5 s flow agree (all)"),
        baseline_plus_flow=describe([e for k, v in cells.items() if k[0] == "60s_opposes" for e in v],
                                    "recent flow with 60 s window opposing"),
        baseline_flow_agrees=describe([e for k, v in cells.items() if k[0] == "60s_agrees" for e in v],
                                      "recent flow with 60 s window agreeing (contrast)"),
        baseline_plus_book=describe([e for k, v in cells.items() if k[1] == "depth_opposes" for e in v],
                                    "recent flow with full depth skew opposing"),
        baseline_book_agrees=describe([e for k, v in cells.items() if k[1] == "depth_agrees" for e in v],
                                      "recent flow with full depth skew agreeing (contrast)"),
        baseline_plus_both=describe(cells[("60s_opposes", "depth_opposes")],
                                    "60 s opposes and depth opposes (375/391 stack and its mirror)"),
        both_agree=describe(cells[("60s_agrees", "depth_agrees")], "60 s agrees and depth agrees (contrast)"),
        flow_opposes_depth_agrees=describe(cells[("60s_opposes", "depth_agrees")], "60 s opposes, depth agrees"),
        flow_agrees_depth_opposes=describe(cells[("60s_agrees", "depth_opposes")], "60 s agrees, depth opposes"),
        original_stack_sell_side=describe(screen, "saved 50-case screen: selling recent, 60 s buy-heavy, bid depth larger"),
        inverse_stack_buy_side=describe(inverse, "inverse: buying recent, 60 s sell-heavy, ask depth larger"),
    )
    # per-side split of the both cell
    arms["both_recent_sell"] = describe([e for e in cells[("60s_opposes", "depth_opposes")] if e["recent"] < 0], "both, recent selling")
    arms["both_recent_buy"] = describe([e for e in cells[("60s_opposes", "depth_opposes")] if e["recent"] > 0], "both, recent buying")

    # alternative book layers that vary on this day: first-ten near-depth imbalance and touch size
    def rel(e, key):
        v = e[key] * e["recent"]
        return "opposes" if v < 0 else "agrees" if v > 0 else "equal"
    alt_book = {}
    for key in ("near_sign", "touch_sign"):
        for relation in ("opposes", "agrees", "equal"):
            sub = [e for e in eligible if rel(e, key) == relation]
            alt_book[f"{key}/{relation}"] = describe(sub, f"{key} {relation} recent flow")
            alt_book[f"{key}/{relation}/recent_sell"] = describe([e for e in sub if e["recent"] < 0], "recent selling")
            alt_book[f"{key}/{relation}/recent_buy"] = describe([e for e in sub if e["recent"] > 0], "recent buying")
            both = [e for e in sub if e["d60"] == -e["recent"]]
            alt_book[f"{key}/{relation}/60s_opposes"] = describe(both, f"{key} {relation} recent flow and 60 s opposes")
    # raw, unoriented day reference (the deflationary reading: a day drift)
    def raw(events, label):
        out = dict(label=label, events=len(events), horizons={})
        for h in HORIZONS:
            vals = [e["move_ticks"][h] for e in events if e["move_ticks"][h] is not None]
            out["horizons"][h] = dict(n=len(vals), up=sum(1 for v in vals if v > 0), flat=sum(1 for v in vals if v == 0),
                                      down=sum(1 for v in vals if v < 0), median_ticks=median(vals) if vals else None)
        return out
    day_reference = dict(
        all_749=raw(per_event, "all first-family events, unoriented"),
        recent_sell=raw([e for e in per_event if e["recent"] < 0], "recent selling, unoriented"),
        recent_buy=raw([e for e in per_event if e["recent"] > 0], "recent buying, unoriented"),
        no_recent_direction=raw([e for e in per_event if e["recent"] == 0], "no agreeing 1 s/5 s direction"),
        by_quarter={q: raw([e for e in per_event if e["chronological_quarter"] == q], f"quarter {q}") for q in (1, 2, 3, 4)},
        stack50_by_quarter={q: describe([e for e in screen if e["chronological_quarter"] == q], f"stack quarter {q}") for q in (1, 2, 3, 4)},
    )
    # activity-matched controls: same 60 s total aggressor quantity tercile and same recent direction, not in the stack
    def activity(e):
        return (e["buy60"] or 0) + (e["sell60"] or 0)
    acts = sorted(activity(e) for e in eligible)
    t1, t2 = acts[len(acts) // 3], acts[2 * len(acts) // 3]
    def tercile(e):
        a = activity(e); return "low" if a < t1 else "mid" if a < t2 else "high"
    both_set = {e["instance"] for e in cells[("60s_opposes", "depth_opposes")]}
    controls = {}
    for terc in ("low", "mid", "high"):
        stack = [e for e in cells[("60s_opposes", "depth_opposes")] if tercile(e) == terc]
        ctrl = [e for e in eligible if tercile(e) == terc and e["instance"] not in both_set]
        controls[terc] = dict(activity_bounds=[t1, t2], stack=describe(stack, f"stack, 60 s activity {terc}"),
                              control=describe(ctrl, f"same-activity eligible events outside the stack, {terc}"))
    # same-hour controls for the saved 50
    hour_controls = {}
    for e in screen:
        hour_controls.setdefault(e["hour_utc"], dict(stack=[], control=[]))["stack"].append(e)
    for e in eligible:
        if e["hour_utc"] in hour_controls and e["instance"] not in reproduced and e["recent"] < 0:
            hour_controls[e["hour_utc"]]["control"].append(e)
    hour_summary = {h: dict(stack=describe(v["stack"], "stack"), control=describe(v["control"], "same hour, recent selling, outside stack"))
                    for h, v in sorted(hour_controls.items())}

    # pre-start displacement: how much of the move was already visible
    disp = {}
    for label, events in (("stack50", screen), ("inverse", inverse), ("eligible", eligible)):
        vals = [e["prior_move_ticks"][1] * (e["recent"] or -1) for e in events if e["prior_move_ticks"][1] is not None]
        disp[label] = dict(n=len(vals), median_prior_1s_ticks_in_recent_direction=median(vals) if vals else None,
                           already_moved_with_recent_flow=sum(1 for v in vals if v > 0),
                           flat=sum(1 for v in vals if v == 0), against=sum(1 for v in vals if v < 0))

    summary = dict(
        population=len(per_event), eligible_recent_flow_defined=len(eligible),
        pre_cursor_agreement=sum(1 for e in per_event if e["pre_cursor_agrees"]),
        saved_screen=len(saved), reproduced_screen=len(reproduced), saved_equals_reproduced=saved == reproduced,
        inverse_stack=len(inverse), tape_end_receive_ns=tape_end,
        recent_direction_counts=Counter(e["recent"] for e in per_event),
        cell_counts={f"{k[0]}|{k[1]}": len(v) for k, v in sorted(cells.items())},
        full_depth_sign_counts=Counter(e["depth_sign"] for e in per_event),
        full_depth_ratio=dict(min=min(e["bid_depth_full"] / e["ask_depth_full"] for e in per_event),
                              median=median(e["bid_depth_full"] / e["ask_depth_full"] for e in per_event),
                              max=max(e["bid_depth_full"] / e["ask_depth_full"] for e in per_event)),
        near_vs_touch_sign=Counter(f"{e['near_sign']}|{e['touch_sign']}" for e in per_event),
        arms=arms, alternative_book_layers=alt_book, day_reference=day_reference, activity_matched_controls=controls, same_hour_controls_for_saved_screen=hour_summary,
        pre_start_displacement=disp,
        note="Ticks are 0.001 price units; positive = midpoint continued in the recent 1 s/5 s flow direction. "
             "Outcomes end at boundary + horizon using the last completed group; censored when beyond the retained tape.",
    )
    (OUT / "first-family-four-arm-summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")
    with gzip.open(OUT / "first-family-four-arm-events.jsonl.gz", "wt", encoding="utf-8") as stream:
        for e in per_event:
            stream.write(json.dumps(e, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k not in ("arms", "alternative_book_layers", "day_reference", "activity_matched_controls", "same_hour_controls_for_saved_screen")}, indent=1, default=str))
    for name, arm in arms.items():
        print(f"\n== {name}: {arm['label']} n={arm['events']} clusters={arm['overlap_clusters_600s']} sell={arm['recent_sell']} buy={arm['recent_buy']}")
        for h, s in arm["horizons"].items():
            if "n" in s:
                print(f"  {h:>4}s n={s['n']:>3} cont={s['continued']:>3} flat={s['flat']:>3} rev={s['reversed']:>3} med={s['median_ticks']:+.1f} q25={s['q25']:+.1f} q75={s['q75']:+.1f} cens={s['censored']}")


if __name__ == "__main__":
    main()
