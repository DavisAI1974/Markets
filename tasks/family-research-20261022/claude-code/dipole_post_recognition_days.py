"""Forward midpoint outcomes after the actual recognition close of the 863 October 18 dipole candidates.

The existing reconstruction (october18-candidate-inputs.jsonl.gz) measures the midpoint
from the last group before the birth second through the recognition close. Most of that
interval precedes the moment the candidate became observable. This script keeps that
retrospective measure and adds what happened AFTER the recognition close, read from the
pinned standalone group export at fixed horizons. The reference is the recognition
close's own quote. Nothing later than the recognition close enters any predictor.

Arms on the same 863 recognitions, oriented to the birth polarity (positive = the
midpoint moved in the birth-flow direction after recognition):
  baseline        birth polarity only
  + flow          rolling 20-second flow at the last closed second before recognition
                  (same as birth / opposite / balanced / undefined)
  + book          displayed touch size at the recognition close (bid minus ask) relative
                  to the birth polarity (aligned / opposed / equal)
  + both          the cross of the two
plus the SAME/FLIP orientation to the predecessor, the number of classified lots in
the birth window, and the midpoint displacement already realised by recognition.
"""

import gzip
import os
import sys
import json
from bisect import bisect_right
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
TAG = os.environ.get("NG_TAG", "oct18")
sys.path.insert(0, str(HERE))
from export_paths import SESSIONS  # noqa: E402
import data_locator  # noqa: E402
DAY = SESSIONS[TAG]["day"]
GROUPS = SESSIONS[TAG]["groups"]
CANDIDATES = (HERE.parent / "october18-candidate-inputs.jsonl.gz") if TAG == "oct18" else data_locator.local_path(f"tasks/family-research-20261022/replay-comparison/{DAY}/candidate-inputs.jsonl.gz")
DAY_MIDNIGHT_UTC = {"20231002": 1696204800, "20231003": 1696291200, "20231017": 1697500800, "20231018": 1697587200}[DAY]
NS = 1_000_000_000
TICK = 1_000_000
HORIZONS = (1, 5, 20, 60, 300)


def sign(x):
    return (x > 0) - (x < 0)


def main():
    recv, cursor, mid2, bids, asks = [], [], [], [], []
    with gzip.open(GROUPS, "rt", encoding="utf-8") as stream:
        for line in stream:
            g = json.loads(line)
            recv.append(g["receive_ns"]); cursor.append(g["close_cursor"])
            mid2.append(g["bid"][0] + g["ask"][0]); bids.append(g["bid"][1]); asks.append(g["ask"][1])
    tape_end = recv[-1]
    rows = [json.loads(line) for line in gzip.open(CANDIDATES, "rt", encoding="utf-8")]
    out_rows = []
    finalization_only = [c["candidate_id"] for c in rows if c.get("recognition_group") is None or c.get("recognition_receive_ns") is None]
    rows = [c for c in rows if c.get("recognition_group") is not None and c.get("recognition_receive_ns") is not None]
    by_cursor = {cu: i for i, cu in enumerate(cursor)}
    join = Counter()
    for c in rows:
        t0 = c["recognition_receive_ns"]
        idx = bisect_right(recv, t0) - 1
        if cursor[idx] != c["recognition_cursor"]:
            # the archived recognition names its group by close cursor; the receive clock can tie across groups
            # (known_by ties are ordered by close_cursor), so join on the cursor and report the clock relation
            j = by_cursor.get(c["recognition_cursor"])
            if j is None:
                join["unmatched_recognition_cursor"] += 1; continue
            join["matched_by_cursor_clock_tie" if recv[j] == t0 else "matched_by_cursor_clock_differs"] += 1
            idx = j
        else:
            join["matched_by_clock_and_cursor"] += 1
        ref2 = mid2[idx]
        c.setdefault("recognition_bid", [None, bids[idx]]); c.setdefault("recognition_ask", [None, asks[idx]])
        c.setdefault("recognition_orientation", "undefined"); c.setdefault("prebirth_displayed_depth_relative_to_birth_flow", "undefined")
        c.setdefault("quote_move_relative_to_birth_polarity", "undefined"); c.setdefault("prebirth_quote", None)
        polarity = c.get("recorded_operands", {}).get("polarity") or sign(c["birth_window"]["roll20"] or 0)
        moves = {}
        for h in HORIZONS:
            target = t0 + h * NS
            if target > tape_end:
                moves[h] = None; continue
            j = bisect_right(recv, target) - 1
            moves[h] = (mid2[j] - ref2) / (2 * TICK)
        touch = sign(c["recognition_bid"][1] - c["recognition_ask"][1])
        realised = 0
        pq = c["prebirth_quote"]
        if pq:
            realised = (ref2 - (pq["bid"][0] + pq["ask"][0])) / (2 * TICK)
        out_rows.append(dict(
            candidate_id=c["candidate_id"], birth_second=c["birth_second"], recognition_cursor=c["recognition_cursor"],
            recognition_receive_ns=t0, polarity=polarity, orientation=c["recognition_orientation"],
            flow_state=c["birth_to_emission_flow_state"], prebirth_depth_state=c["prebirth_displayed_depth_relative_to_birth_flow"],
            recognition_touch_relation={-1: "opposed", 0: "equal", 1: "aligned"}[touch * polarity] if polarity else "undefined",
            birth_classified_lots=c["birth_window"]["classified_lots"],
            last_window_classified_lots=c["last_closed_window"]["classified_lots"],
            realised_by_recognition_ticks_in_birth_direction=realised * polarity,
            quote_move_by_recognition=c["quote_move_relative_to_birth_polarity"],
            move_ticks_after_recognition=moves,
        ))

    def describe(events, label):
        out = dict(label=label, events=len(events), horizons={})
        for h in HORIZONS:
            vals = [e["move_ticks_after_recognition"][h] * e["polarity"] for e in events
                    if e["move_ticks_after_recognition"][h] is not None]
            if not vals:
                out["horizons"][h] = dict(n=0); continue
            out["horizons"][h] = dict(
                n=len(vals), with_birth=sum(1 for v in vals if v > 0), flat=sum(1 for v in vals if v == 0),
                against_birth=sum(1 for v in vals if v < 0), median_ticks=median(vals),
                censored=sum(1 for e in events if e["move_ticks_after_recognition"][h] is None))
        return out

    def raw(events, label):
        out = dict(label=label, events=len(events), horizons={})
        for h in HORIZONS:
            vals = [e["move_ticks_after_recognition"][h] for e in events if e["move_ticks_after_recognition"][h] is not None]
            out["horizons"][h] = dict(n=len(vals), up=sum(1 for v in vals if v > 0), flat=sum(1 for v in vals if v == 0),
                                      down=sum(1 for v in vals if v < 0), median_ticks=median(vals) if vals else None)
        return out

    arms = dict(baseline=describe(out_rows, "all recognitions, oriented to birth polarity"))
    for state in ("same_direction_at_emission", "opposite_direction_at_emission", "balanced_at_emission", "undefined_at_emission"):
        arms[f"flow/{state}"] = describe([e for e in out_rows if e["flow_state"] == state], f"flow at recognition {state}")
    for relation in ("aligned", "opposed", "equal"):
        arms[f"book/{relation}"] = describe([e for e in out_rows if e["recognition_touch_relation"] == relation],
                                            f"recognition touch size {relation} to birth polarity")
    for state in ("same_direction_at_emission", "opposite_direction_at_emission", "undefined_at_emission"):
        for relation in ("aligned", "opposed"):
            arms[f"both/{state}/{relation}"] = describe(
                [e for e in out_rows if e["flow_state"] == state and e["recognition_touch_relation"] == relation],
                f"flow {state} and touch {relation}")
    for relation in ("aligned", "opposed", "balanced"):
        arms[f"prebirth_depth/{relation}"] = describe([e for e in out_rows if e["prebirth_depth_state"] == relation],
                                                      f"prebirth displayed depth {relation} (the existing retrospective stack)")
    for orientation in ("SAME", "FLIP"):
        arms[f"orientation/{orientation}"] = describe([e for e in out_rows if e["orientation"] == orientation], f"orientation {orientation}")
    for move in ("same", "opposite", "flat"):
        arms[f"realised_by_recognition/{move}"] = describe([e for e in out_rows if e["quote_move_by_recognition"] == move],
                                                            f"midpoint already moved {move} relative to birth by recognition")
    for lots in ("one_lot", "multiple_lots"):
        arms[f"birth_lots/{lots}"] = describe(
            [e for e in out_rows if (e["birth_classified_lots"] == 1) == (lots == "one_lot")], f"birth window {lots}")
    for pol, name in ((1, "buy_birth"), (-1, "sell_birth")):
        arms[f"polarity/{name}"] = describe([e for e in out_rows if e["polarity"] == pol], name)
    # control: the same touch-size relation at every active-session second's last completed close (no dipole involved)
    OPEN, CLOSE = (DAY_MIDNIGHT_UTC + 9 * 3600) * NS, (DAY_MIDNIGHT_UTC + 20 * 3600 + 55 * 60) * NS  # 09:00 to 20:55 UTC, the span the October 18 reconstruction used (its constants 1697619600 / 1697662500)
    last_close_per_second = {}
    for i, t in enumerate(recv):
        if OPEN <= t < CLOSE:
            last_close_per_second[t // NS] = i
    control = defaultdict(lambda: {h: Counter() for h in HORIZONS})
    for sec, i in last_close_per_second.items():
        ts = sign(bids[i] - asks[i])
        if not ts:
            key = "touch_equal"
        else:
            key = "touch_imbalance"
        for h in HORIZONS:
            target = recv[i] + h * NS
            if target > tape_end:
                continue
            j = bisect_right(recv, target) - 1
            mv = sign(mid2[j] - mid2[i])
            if ts:
                control[key][h]["with_heavier_side" if mv == ts else "flat" if mv == 0 else "against_heavier_side"] += 1
            else:
                control[key][h]["up" if mv > 0 else "flat" if mv == 0 else "down"] += 1
    control_out = {k: {h: dict(v) for h, v in hs.items()} for k, hs in control.items()}
    control_out["seconds"] = len(last_close_per_second)
    day_reference = dict(all=raw(out_rows, "all recognitions, unoriented"),
                         touch_imbalance_control_all_active_seconds=control_out,
                         buy_birth=raw([e for e in out_rows if e["polarity"] > 0], "buy births, unoriented"),
                         sell_birth=raw([e for e in out_rows if e["polarity"] < 0], "sell births, unoriented"))
    summary = dict(session=TAG, candidates_in_file=len(out_rows) + len(finalization_only) + join["unmatched_recognition_cursor"], finalization_only=finalization_only, join=dict(join), recognitions=len(out_rows), polarity_counts=Counter(e["polarity"] for e in out_rows),
                   flow_state_counts=Counter(e["flow_state"] for e in out_rows),
                   recognition_touch_counts=Counter(e["recognition_touch_relation"] for e in out_rows),
                   arms=arms, day_reference=day_reference,
                   note="Ticks of 0.001. Reference = the recognition close quote itself; later quotes from the group export at "
                        "recognition receive clock + horizon, last completed group. Positive = moved with the birth polarity.")
    (HERE / f"dipole-post-recognition-{TAG}-summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")
    with gzip.open(HERE / f"dipole-post-recognition-{TAG}-rows.jsonl.gz", "wt", encoding="utf-8") as stream:
        for e in out_rows:
            stream.write(json.dumps(e, sort_keys=True) + "\n")
    for name, arm in arms.items():
        print(f"\n== {name}: n={arm['events']}")
        for h, s in arm["horizons"].items():
            if s.get("n"):
                print(f"  {h:>4}s n={s['n']:>3} with={s['with_birth']:>3} flat={s['flat']:>3} against={s['against_birth']:>3} med={s['median_ticks']:+.1f}")
    print("\n== control: touch-size imbalance at every active second's last close", json.dumps(control_out, default=str))
    for name, arm in day_reference.items():
        if "horizons" not in arm:
            continue
        print(f"\n== raw {name}")
        for h, s in arm["horizons"].items():
            print(f"  {h:>4}s n={s['n']} up={s['up']} flat={s['flat']} down={s['down']} med={s['median_ticks']}")


if __name__ == "__main__":
    main()
