"""Section 1 on four sessions, from the standalone exports: outcomes after the archived adapter's recognition.

Mirrors dipole_post_recognition_outcomes.py (October 18, 863 archived candidates) with the recognition rule
applied to every frozen-detector event of each session: recognition = the first completed group whose
receive clock is at or after t0 + 50 s (the archived adapter's available_second; section 11), the
reference midpoint = that group's midpoint, the later midpoint = the last completed group at or before
recognition + horizon. Nothing interpolated; exports read exactly as published (October 2 and 17 are
partial, so events born in the missing prefix hours have no groups and are counted out). Arms as in
section 1: baseline, flow state at recognition (300 s imbalance sign relative to polarity), recognition
touch-size relation (bid size minus ask size, relative to polarity). Also an export-versus-tape check:
the export's print count against the replay's, and the recognition-group midpoint against the replay's
per-second midpoint. No trade cost.
"""

import gzip
import json
import os
import sys
from bisect import bisect_right
from collections import Counter
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from export_paths import SESSIONS  # noqa: E402

NS = 1_000_000_000
TICK = 1_000_000
HORIZONS = (1, 5, 20, 60, 300, 600)
RECOGNITION_OFFSET = 50


def sign(x):
    return (x > 0) - (x < 0)


def load_groups(path):
    recv, mid2, bsz, asz, cur = [], [], [], [], []
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            g = json.loads(line)
            if not g["bid"] or not g["ask"] or g["bid"][0] is None or g["ask"][0] is None:
                continue
            recv.append(g["receive_ns"]); mid2.append(g["bid"][0] + g["ask"][0]); bsz.append(g["bid"][1]); asz.append(g["ask"][1]); cur.append(g["close_cursor"])
    return recv, mid2, bsz, asz, cur


def describe(events, label):
    out = dict(label=label, events=len(events), horizons={})
    for h in HORIZONS:
        vals = [e["moves"][str(h)] * e["polarity"] for e in events if e["moves"][str(h)] is not None]
        out["horizons"][str(h)] = dict(n=len(vals), with_birth=sum(1 for v in vals if v > 0), flat=sum(1 for v in vals if v == 0),
                                       against_birth=sum(1 for v in vals if v < 0), median_ticks=median(vals) if vals else None,
                                       with_share_nonflat=round(sum(1 for v in vals if v > 0) / max(1, sum(1 for v in vals if v != 0)), 3) if vals else None)
    return out


def main():
    tag = os.environ.get("NG_TAG", "oct18")
    S = SESSIONS[tag]
    os.environ["NG_DAY"] = S["day"]
    import exhaustion_clock_reanalysis_oct18 as X  # noqa: E402  (reads NG_DAY)
    stream = X.replay_cached()
    recv, mid2, bsz, asz, cur = load_groups(S["groups"])
    tape_end = recv[-1]
    ev = [json.loads(l) for l in gzip.open(HERE / f"exhaustion-clock-{tag}-events.jsonl.gz", "rt")]
    ev = sorted((r for r in ev if r["mode"] == "day"), key=lambda r: r["t0"])
    cls = {r["t0"]: r for r in (json.loads(l) for l in gzip.open(HERE / f"frozen-a-classifier-{tag}-events.jsonl.gz", "rt"))}
    rows, skipped, mid_check = [], Counter(), []
    for r in ev:
        t0, pol = r["t0"], r["polarity"]
        rec_ns = (S["day0"] + t0 + RECOGNITION_OFFSET) * NS
        idx = bisect_right(recv, rec_ns - 1)  # first group with receive >= rec_ns
        if idx >= len(recv):
            skipped["no_group_after_recognition"] += 1; continue
        if recv[0] > rec_ns:
            skipped["born_before_export_start"] += 1; continue
        ref2 = mid2[idx]
        rsec = recv[idx] // NS - S["day0"]
        if 0 <= rsec < 86400 and X.fin(stream["mid"][rsec]):
            mid_check.append(abs(ref2 / 2 - stream["mid"][rsec]) / TICK)
        imb, vol = X.window_imb(stream["cb"], stream["cs"], min(rsec, 86399), 300)
        flow_state = "undefined" if imb is None else {1: "same_direction", -1: "opposite_direction", 0: "balanced"}[sign(imb) * pol]
        touch = sign(bsz[idx] - asz[idx])
        moves = {}
        for h in HORIZONS:
            target = recv[idx] + h * NS
            if target > tape_end:
                moves[str(h)] = None; continue
            j = bisect_right(recv, target) - 1
            moves[str(h)] = (mid2[j] - ref2) / (2 * TICK)
        rows.append(dict(t0=t0, polarity=pol, seed=r["seed_state"], a_state=cls[t0]["a_state"], recognition_receive_ns=recv[idx], recognition_cursor=cur[idx],
                         recognition_delay_s=round((recv[idx] - (S["day0"] + t0) * NS) / NS, 3), flow_state=flow_state,
                         touch_relation={-1: "opposed", 0: "equal", 1: "aligned"}[touch * pol], moves=moves))
    arms = dict(baseline=describe(rows, "all recognitions, oriented to polarity"))
    for st in ("same_direction", "opposite_direction", "balanced", "undefined"):
        arms[f"flow/{st}"] = describe([e for e in rows if e["flow_state"] == st], f"300 s flow at recognition {st}")
    for rel in ("aligned", "opposed", "equal"):
        arms[f"touch/{rel}"] = describe([e for e in rows if e["touch_relation"] == rel], f"recognition touch size {rel} to polarity")
    for a in ("A-fast-collapse", "A-persistent"):
        arms[f"state/{a}"] = describe([e for e in rows if e["a_state"] == a], a)
    # the touch read as a direction call irrespective of polarity: touch sign vs later move sign
    touch_dir = {}
    for h in HORIZONS:
        w = ag = fl = 0
        for e in rows:
            m = e["moves"][str(h)]
            ts = {"aligned": e["polarity"], "opposed": -e["polarity"], "equal": 0}[e["touch_relation"]]
            if m is None or ts == 0:
                continue
            w += ts * m > 0; ag += ts * m < 0; fl += m == 0
        touch_dir[str(h)] = dict(with_touch=w, flat=fl, against_touch=ag, with_share_nonflat=round(w / max(1, w + ag), 3))
    out = dict(session=tag, export_scope=S["export_scope"], export_groups=len(recv), export_prints=None, replay_prints=stream["counts"]["prints"],
               events=len(ev), used=len(rows), skipped=dict(skipped), recognition_delay_s=dict(median=median([e["recognition_delay_s"] for e in rows]), max=max(e["recognition_delay_s"] for e in rows)) if rows else None,
               export_vs_replay_midpoint_abs_ticks=dict(n=len(mid_check), median=median(mid_check), max=max(mid_check), zero_share=round(sum(1 for v in mid_check if v == 0) / len(mid_check), 3)) if mid_check else None,
               arms=arms, touch_as_direction_call=touch_dir)
    (HERE / f"export-recognition-outcomes-{tag}-summary.json").write_text(json.dumps(out, indent=2, default=str) + "\n")
    with gzip.open(HERE / f"export-recognition-outcomes-{tag}-events.jsonl.gz", "wt") as f:
        for e in rows:
            f.write(json.dumps(e) + "\n")
    print(tag, S["export_scope"], "groups", len(recv), "events", len(ev), "used", len(rows), "skipped", dict(skipped), "replay prints", stream["counts"]["prints"])
    print(" midpoint check", out["export_vs_replay_midpoint_abs_ticks"], "| recognition delay", out["recognition_delay_s"])
    for k, a in arms.items():
        print(f"  {k:28s} n {a['events']:4d} " + " | ".join(f"{h}s {v['with_birth']}/{v['flat']}/{v['against_birth']} ({v['with_share_nonflat']})" for h, v in a["horizons"].items() if h in ("5", "60", "300", "600")))
    print("  touch as direction call:", {h: (v["with_touch"], v["flat"], v["against_touch"], v["with_share_nonflat"]) for h, v in touch_dir.items()})


if __name__ == "__main__":
    main()
