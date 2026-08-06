"""group_coordinate_blind.py - GENERIC blind coordinator (S105), config-driven:
    python research/kalshi/group_coordinate_blind.py g18

SELECT the owner per day under the GUARD (+ Friday sign-off), assemble grp<n>.json from the specialist
blind files' guessed_net_usd (verbatim, never averaged), score vs the two-leg actual, render actual +
own p50 path only. Reads group_config for days/owner/seam/anchor. Original g17_coordinate.py kept as the
G17 record.
"""
import os, sys, json
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import group_config as gc
import render_util as ru
import verify_gold
import due_gate
import path_contract
verify_gold.assert_gold_intact()   # the concrete wall - no blind coordinate on a violated gold vault

HERE = os.path.dirname(os.path.abspath(__file__))
FC = os.path.join(HERE, "forecasts")
RENDER_DIR = os.path.join(HERE, "renders", "ng_refine_s95")
MULT = gc.MULT
_DOW = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _find_report(fname):
    """Autonomous-safe: find a specialist report wherever the agent wrote it (canonical FC, or a
    repo-root forecasts/ that a differently-cwd'd agent may have used). Report routing is the
    coordinator's job - we do not babysit paths."""
    for d in (FC, os.path.join(HERE, "..", "..", "forecasts")):
        p = os.path.join(d, fname)
        if os.path.exists(p):
            return p
    return None


def load_specialist(gid, tag):
    # S108: accept the ENGINE filename too. Blind and refine run the IDENTICAL rule files, so the blind
    # writes grp<N>_mbo_specialist_<X>.json like the refine does - but this coordinator only ever looked
    # for grp<N>_blind_<X>.json, which forced a hand-built alias file every single blind run. That alias
    # lived in the scratchpad, which does not survive a session, so it was re-authored from memory each
    # time - a per-run manual step sitting directly upstream of the guard. Legacy name is still tried
    # FIRST so every committed pre-S108 blind coordinates byte-identically.
    n = gid[1:]
    for fname in (f"grp{n}_blind_{tag}.json", f"grp{n}_mbo_specialist_{tag}.json"):
        p = _find_report(fname)
        if p is not None:
            return {str(x["date"]).replace("-", ""): x for x in json.load(open(p)).get("days", [])}
    return None


def num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def day_move(day):
    """The scored day-move. The engine emits expected_magnitude_usd; the older blind alias files emit
    guessed_net_usd. Same number, two names - accept both rather than making a human retype it."""
    for k in ("guessed_net_usd", "expected_magnitude_usd"):
        if num(day.get(k)):
            return day[k]
    return day.get("guessed_net_usd", day.get("expected_magnitude_usd"))   # non-numeric -> guard reports it


def day_path(day):
    """Intraday p50 path as [(et_hr, cum_usd), ...]. The engine emits path_p50_curve (pairs); the alias
    files emit path_distribution (records). S107 lost the blind curve to exactly this kind of key
    mismatch - the render asked for one name, the file carried the other, and the curve silently
    vanished from the chart whose entire point was blind-vs-refine-vs-price."""
    pts = day.get("path_distribution")
    if pts:
        return [(r.get("et_hr"), r.get("p50")) for r in pts]
    return [(h, v) for h, v in (day.get("path_p50_curve") or [])]


break_gaps = ru.break_gaps   # S107: one implementation, in render_util


def guard_assemble(gid):
    g = gc.GROUPS[gid]; days = g["days"]; owner = gc.owner_map(gid); seam = g.get("seam")
    weekend_feeding = {d for d in days if _DOW[pd.Timestamp(f"{d[:4]}-{d[4:6]}-{d[6:]}").weekday()] == "Fri"}
    # S107: A is a full owner. agents/README.md has always said "A owns holiday/extended-weekend
    # reopens ONLY"; the coordinator carried a TODO instead ("handle when it occurs") and hard-failed
    # the whole block on any A-owned day. It occurred on G20 (Memorial Day 20260525, a real if thin
    # session). A is now loaded and selected like any other owner - EVERY other guard is unchanged
    # (owner match, numeric day-move, Friday sign-off). A must emit a `days` array on a day it owns,
    # not only its bridge block.
    specs = {t: load_specialist(gid, t) for t in ("A", "B", "C", "D", "E")}
    errs, block = [], []
    for d in days:
        o = owner[d]
        sp = specs.get(o)
        if sp is None:
            errs.append(f"{d}: owner {o} file missing"); continue
        day = sp.get(d)
        if day is None:
            errs.append(f"{d}: owner {o} did not forecast this day"); continue
        dm = day_move(day)
        if not num(dm):
            errs.append(f"{d}: owner {o} day-move non-numeric ({dm!r}) - needs guessed_net_usd or "
                        f"expected_magnitude_usd"); continue
        if d in weekend_feeding and "handoff_out" not in day:
            errs.append(f"{d}: FRIDAY SIGN-OFF FAIL - weekend-feeding, owner {o} no handoff_out")
        block.append({"date": d, "dow": _DOW[pd.Timestamp(f'{d[:4]}-{d[4:6]}-{d[6:]}').weekday()],
                      "owner": o, "guess_day_move_usd": int(dm),
                      "overnight_gap_usd": day.get("overnight_gap_usd", 0) or 0,
                      "path_p50": day_path(day)})
    if errs:
        raise SystemExit("BLIND COORDINATOR GUARD FAILED:\n  " + "\n  ".join(errs))
    return block, seam


def score(block, actual):
    amap = {r["date"]: r for r in actual["days"]}
    rows, sabs, dh = [], 0, 0
    for b in block:
        a = amap[b["date"]]; am = a["day_move_usd"]; gm = b["guess_day_move_usd"]
        err = gm - am; hit = (gm > 0) == (am > 0) or (gm == 0 and am == 0)
        sabs += abs(err); dh += int(hit)
        rows.append({**b, "actual_day_move_usd": am, "err_usd": err, "dir_hit": hit})
    return rows, sabs, dh


def render(gid, rows, actual, seam):
    fig, ax = plt.subplots(figsize=(15, 7))
    ct, cp = break_gaps([t for t, _ in actual["continuous"]], [p for _, p in actual["continuous"]])
    adt = pd.to_datetime(ct, unit="s", utc=True).tz_convert("America/New_York")
    ax.plot(adt, cp, color="#1f6feb", lw=0.8, label="actual (MBO trades)", zorder=3)
    anchor = actual["anchor"]; run = 0.0
    fx, fy = [], []                     # S107: accumulate the WHOLE block, then draw ONE polyline
    for b in rows:
        d = b["date"]; gap = 0 if d == seam else b["overnight_gap_usd"]
        open_cum = run + gap; net = b["guess_day_move_usd"] - (0 if d == seam else gap)
        day0 = pd.Timestamp(f"{d[:4]}-{d[4:6]}-{d[6:]}", tz="America/New_York")
        path = [(h, v) for h, v in b["path_p50"] if h is not None and v is not None]
        # S110 (Greg spotted it in the render; measured after): the running level advances by NET
        # while the LINE is drawn to the last path point. If a specialist emits its path as
        # cum-from-PRIOR-CLOSE (gap included) instead of cum-from-OPEN, the pen lands one whole gap
        # above where the next day starts - THAT is why the lines did not connect. Measured: g22
        # 0/10 mismatched, g23 8/10, both Mondays off by exactly their +400 gap. Announced, not
        # hard-failed: no SCORE is affected (scoring reads guess_day_move_usd, never the path), and
        # hard-failing would invalidate committed artifacts - see DECISIONS D27, Greg's call.
        if path and abs(path[-1][1] - net) > 1:
            print(f"  [render-continuity] {d}: path ends {path[-1][1]:+.0f} but the running level "
                  f"advances by net {net:+.0f} (delta {path[-1][1]-net:+.0f}, gap {gap:+.0f}) - the "
                  f"drawn line will not meet the next day. Path convention is cum-from-OPEN.")
        if path:
            sx = ru.path_times(day0, path)
            sy = [anchor + (open_cum + v) / MULT for _, v in path]
        else:
            sx = [day0 + pd.Timedelta(hours=8), day0 + pd.Timedelta(hours=16)]
            sy = [anchor + open_cum / MULT, anchor + (open_cum + net) / MULT]
        fx.extend(sx); fy.extend(sy)
        run = open_cum + net
    ru.plot_forecast(ax, fx, fy, color="#d1242f", label="blind p50 path", lw=1.2, z=4)
    ax.axhline(anchor, color="#999", lw=0.7, ls="--")
    if seam:
        sd = pd.Timestamp(f"{seam[:4]}-{seam[4:6]}-{seam[6:]}", tz="America/New_York")
        ax.axvline(sd, color="#999", lw=0.8, ls=":")
    ax.set_title(f"NG {gid.upper()} BLIND (5-specialist sequenced panel, brain {ru.brain_version()}) vs actual", fontsize=10, fontweight="bold")
    ax.set_ylabel("price ($/MMBtu)"); ax.legend(fontsize=8); ax.grid(True, color="#eee"); ax.set_axisbelow(True)
    out = os.path.join(RENDER_DIR, f"{gid}_blind_vs_actual.png")
    fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(out, dpi=130); plt.close(fig); return out


def assert_not_the_refine(gid, block):
    """THE MIRROR OF assert_not_the_blind, AND IT DID NOT EXIST UNTIL S114 (NC-4).

    D9 guards one direction: a refine posterior byte-identical to its blind archive is rejected.
    NOTHING guarded the other direction. After a group's refine, `archive_blind.py` has MOVED the
    blind posteriors into g<N>_blind_round1/ and the canonical names `grp<N>_mbo_specialist_<X>.json`
    now hold the REFINE posteriors - so re-running this blind coordinator on a refined group
    silently assembles REFINE numbers and overwrites the immutable blind record.

    INSTANCE (NC-4, mine, S114): running `group_coordinate_blind.py g22` to D11-verify a newly wired
    due-gate rewrote forecasts/grp22.json from the true blind (4/10 dir, sum|err| 5,965) to the
    refine's numbers (10/10, 500) - a 12x improvement in the record, from a command that only meant
    to prove an import executed. Caught by `git diff` and restored; it would have been invisible in
    a dirty tree. This is the S108 filename-collision family, fourth occurrence.

    THE FIRST VERSION OF THIS GUARD USED THE ARCHIVE'S EXISTENCE AS THE SIGNAL, AND IT WAS
    INSUFFICIENT - recorded rather than tidied away, because it is the same lesson twice. Only
    g19-g22 have archives; g15, g17, g18 and g23 are refined with NO archive (they predate or
    skipped archive_blind), so a presence check passed on four of the eight exposed groups and the
    D11 negative test walked straight into overwriting grp18.json.

    The working guard is a RECONCILIATION against an independent source, which is exactly the S108
    hole-#8 lesson: a field-level or presence check cannot catch a wrong-but-well-formed input -
    only comparison against something independent can. Here the independent source is the committed
    blind record itself: if grp<N>.json already exists as phase "blind" and the numbers we just
    assembled DISAGREE with it, then whatever is sitting in the canonical specialist names is not
    what produced that record, and writing would destroy it."""
    n = gid[1:]
    rec = os.path.join(FC, f"grp{n}.json")
    if not os.path.exists(rec):
        return                                   # first blind for this group - nothing to protect
    try:
        old = json.load(open(rec, encoding="utf-8"))
    except Exception:
        return
    if old.get("phase") != "blind":
        return
    oldmap = {d["date"]: d.get("guess_day_move_usd") for d in old.get("days", [])}
    newmap = {d["date"]: num(d.get("guess_day_move_usd")) for d in block}
    diffs = [(k, oldmap.get(k), newmap.get(k)) for k in sorted(set(oldmap) | set(newmap))
             if oldmap.get(k) != newmap.get(k)]
    if diffs:
        lines = "\n".join(f"      {k}: committed {a}  vs  assembled {b}" for k, a, b in diffs[:6])
        arch = os.path.join(FC, f"g{n}_blind_round1")
        hint = (f"  The blind posteriors were archived to {os.path.relpath(arch, HERE)} - read them from there."
                if os.path.isdir(arch) else
                "  No blind archive exists for this group, so the original blind posteriors are NOT recoverable\n"
                "  from disk - the committed record is the only copy. Do not overwrite it.")
        raise SystemExit(
            f"[blind-coordinator] HARD FAIL: assembling {gid} would OVERWRITE the committed blind record\n"
            f"  with different numbers - so the canonical specialist files are not the blind ones.\n"
            f"  {len(diffs)} day(s) disagree:\n{lines}\n{hint}\n"
            f"  NC-4 (S114): this exact command rewrote grp22.json from the true blind (4/10, sum|err|\n"
            f"  5,965) to the refine's numbers (10/10, 500). To rehearse, write to a rehearsal namespace.")


if __name__ == "__main__":
    gid = sys.argv[1]
    actual = json.load(open(os.path.join(RENDER_DIR, f"{gid}_actual.json")))
    block, seam = guard_assemble(gid)
    assert_not_the_refine(gid, block)
    rows, sabs, dh = score(block, actual)
    json.dump({"group": gid, "phase": "blind", "brain_version": ru.brain_version(), "anchor": actual["anchor"],
               "sum_abs_err_usd": sabs, "mean_abs_err_usd": round(sabs / len(rows)), "dir_hits": dh,
               "n": len(rows), "days": rows}, open(os.path.join(FC, f"grp{gid[1:]}.json"), "w"), indent=1)
    print(f"{'date':10} {'dow':4} {'own':4} {'guess':>8} {'actual':>8} {'err':>7} {'dir':>4}")
    for r in rows:
        print(f"{r['date']:10} {r['dow']:4} {r['owner']:4} {r['guess_day_move_usd']:8d} "
              f"{r['actual_day_move_usd']:8d} {r['err_usd']:7d} {'OK' if r['dir_hit'] else 'X':>4}")
    print(f"\n{gid.upper()} BLIND: {dh}/{len(rows)} dir, mean abs err {round(sabs/len(rows))}, sum abs {sabs}")
    # REGISTERED FORWARD TESTS (merge_gate/due_gate): a play merged PROVISIONAL names this group as
    # its test. Measured S114: the coordinators referenced the DUE list NOWHERE, so the mechanism
    # merge_gate calls "the one thing that makes unattended merging survivable" was prose only.
    # Announce-not-hard-fail HERE by design: the blind is scored before any human sees it and a
    # SystemExit would discard a completed run's numbers. The refine coordinator hard-fails.
    _reports = [_find_report(f"grp{gid[1:]}_mbo_specialist_{t}.json") for t in "ABCDE"]
    due_gate.assert_reported(gid, [p for p in _reports if p], hard=False)
    # THE PATH CONTRACT (S114). BLD-1/RFN-1 require the 2-hourly clock FROM THE 20:00
    # REOPEN through the close, first point 0, last == (day-move minus gap). Nothing
    # checked it, and the committed g22 blind violates it on 10 of 10 days - every one
    # starting at hour 08, so every curve was missing its overnight leg. g21 got it right
    # on 8 of 10, which makes g22 a REGRESSION, and the cause is recorded: the clock spec
    # lived only in RFN-1 until S110.
    # Announce, not hard-fail, for the same reason as due_gate above: the blind is scored before any
    # human sees it and a SystemExit here would discard a completed run's numbers. A path can
    # only be repaired by re-running the specialist.
    path_contract.assert_rows(rows, hard=False)
    try:
        print("render ->", render(gid, rows, actual, seam))
    except Exception as e:
        print(f"[render skipped: {e}]")
