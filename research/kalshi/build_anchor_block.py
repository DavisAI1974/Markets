#!/usr/bin/env python3
"""S109: build the per-group ANCHOR BLOCK that gets handed to the specialists at spawn.

WHY THIS EXISTS. The README names the group data as three things - "the decision-state file + ANCHOR +
basis" - but the anchor is NOT in the staged state (grp<N>_state.json carries zero anchor-keyed leaves),
and the specialist rule files are static and deliberately carry no group data. So the anchor has been a
per-run, hand-carried number. Only g15 ever had an anchor FILE. A hand-carried input is precisely what
S108 lost when the blind coordinator's hand-built alias died with the scratchpad, and a specialist
spawned without an anchor has no reference level for the cum-from-anchor path it is asked to emit.

WHAT IS VERIFIED, NOT ASSERTED. Each group's anchor must equal the PRIOR group's last-day close - an
independent measurement of the same quantity, from a different file, built by a different step. That
chain holds exactly across G17->G23. anchor_lasthr_dir is re-derived from the prior group's actual price
path and must agree with the declared value. Either mismatch is a hard failure: an anchor is the level
the entire forward curve hangs off, and a wrong one moves every day in the block by the same amount
while every per-day error still looks locally reasonable.

PROVENANCE IS DECLARED, NOT IMPLIED. The final-hour shape is derived from the actual file's `continuous`
render series, which is a DOWNSAMPLED path (~4000 points per block), not the raw tape. Price levels off
it are sound; trade counts and signed flow are NOT recoverable from it and are therefore emitted as null
with the reason stated, rather than computed from a series that cannot support them. g15_anchor.json
carried true tape counts because it was built with a data plane; this builder runs without one.

THE HOLIDAY CAVEAT (G22, G23). Both anchor on a holiday half-session - the first two groups of the walk
to do so. The anchor PRICE is chain-verified and sound. The anchor's last-hour DIRECTION comes off a
tape roughly a fifth as active as a normal session, so it is a weaker signal than the same field in
G17-G21, and it feeds the E->A->B weekend seam. That is declared to the specialists in the block itself
rather than left for them to discover.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RENDER_DIR = os.path.join(HERE, "renders", "ng_refine_s95")
sys.path.insert(0, HERE)
import group_config as gc  # noqa: E402

SEQ = ["g17", "g18", "g19", "g20", "g21", "g22", "g23"]
MULT = 10000.0          # NG: $0.001 = $10 per contract, so a $1 move = 10,000 ticks of $/MMBtu


def _actual(gid):
    p = os.path.join(RENDER_DIR, f"{gid}_actual.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def build(gid: str) -> dict:
    g = gc.GROUPS[gid]
    anchor, adate, lhd = g.get("anchor"), g.get("anchor_date"), g.get("anchor_lasthr_dir")
    if anchor is None or not adate or lhd is None:
        raise SystemExit(f"{gid}: INCOMPLETE anchor triple (anchor={anchor} date={adate} lasthr={lhd}) "
                         f"- a specialist cannot emit a cum-from-anchor path without it")

    d = datetime.date(int(adate[:4]), int(adate[4:6]), int(adate[6:]))
    out = {
        "group": gid,
        "date": adate,
        "dow": d.strftime("%a"),
        "anchor_close": anchor,
        "anchor_lasthr_dir": lhd,
        "leg": gc.leg_for(gid, g["days"][0]),
        "basis": g.get("basis"),
        "is_holiday_session": adate in gc.HOLIDAYS,
        "verification": {},
        "last_hour": {},
        "session_activity": {},
    }

    # --- VERIFY against the prior group's actual last-day close (independent source) ---
    i = SEQ.index(gid) if gid in SEQ else -1
    prev = SEQ[i - 1] if i > 0 else None
    pa = _actual(prev) if prev else None
    if pa:
        last = pa["days"][-1]
        if last["date"] != adate:
            raise SystemExit(f"{gid}: anchor_date {adate} is NOT {prev}'s last day ({last['date']}) - "
                             f"the block chain is broken; do not spawn")
        if abs(last["close"] - anchor) > 1e-9:
            raise SystemExit(f"{gid}: anchor {anchor} CONTRADICTS {prev}'s actual close on {adate} "
                             f"({last['close']}) - the forward curve would hang off a wrong level")
        out["verification"] = {"source": f"{prev}_actual.json last day {adate}",
                               "prior_group_close": last["close"], "status": "MATCH"}

        # --- final-hour shape off the actual render path (declared downsampled) ---
        cont = pa.get("continuous") or []
        if cont:
            t_end = cont[-1][0]
            hr = [(t, p) for t, p in cont if t >= t_end - 3600]
            if hr:
                px = [p for _, p in hr]
                derived = 1 if px[-1] > px[0] else (-1 if px[-1] < px[0] else 0)
                if derived != lhd:
                    raise SystemExit(f"{gid}: anchor_lasthr_dir declared {lhd} but the actual final hour "
                                     f"ran {px[0]}->{px[-1]} ({derived}) - do not spawn on a wrong seam dir")
                net = int(round((px[-1] - px[0]) * MULT))
                rng = max(px) - min(px)
                rng_usd = int(round(rng * MULT))
                # S109 f14(b), raised by the state auditor against this very file. A last-hour NET can
                # sit at the price resolution floor and still be published as a confident direction.
                # On the G22 anchor the net is 2 ticks (3.200 -> 3.198) = 18% of an $110 last-hour
                # range: that is noise, not a direction, and anchor_lasthr_dir feeds the E->A->B
                # weekend seam. The close's LOCATION IN RANGE is the sturdier reading off the same
                # data and is now served beside it. Declared, so the reader weights them itself.
                close_in_range = round((px[-1] - min(px)) / rng, 3) if rng > 0 else None
                ticks = abs(net) // 10
                out["last_hour"] = {
                    "first_price": px[0], "last_price": px[-1],
                    "high_price": max(px), "low_price": min(px),
                    "net_usd": net,
                    "direction": "up" if derived > 0 else ("down" if derived < 0 else "flat"),
                    "derived_dir": derived, "n_points": len(hr),
                    "range_usd": rng_usd,
                    "net_ticks": ticks,
                    "net_share_of_range": round(abs(net) / rng_usd, 3) if rng_usd else None,
                    "close_in_range": close_in_range,
                    "direction_is_resolution_floor": ticks <= 3,
                    "direction_caveat": (
                        f"the last-hour NET is {ticks} tick(s), {round(abs(net)/rng_usd*100) if rng_usd else 0}% "
                        f"of the ${rng_usd} last-hour range - at or near the price resolution floor, so "
                        f"anchor_lasthr_dir is a WEAK signal and should not be leaned on as a seam "
                        f"direction. close_in_range ({close_in_range}) is derived from the same data and "
                        f"is the sturdier read." if ticks <= 3 else
                        f"last-hour net {ticks} ticks on a ${rng_usd} range - direction is supported."),
                    "trade_count": None, "signed_flow": None,
                    "provenance": ("price levels derived from the actual file's DOWNSAMPLED `continuous` "
                                   "render path, not the raw tape. Trade count and signed flow are NOT "
                                   "recoverable from a downsampled series and are null by design - a "
                                   "number computed off this series would be wrong-but-well-formed."),
                }
    else:
        out["verification"] = {"source": None, "status": "UNVERIFIED - no prior group actual on disk"}

    # --- true session activity, from the tape read already served in the staged state ---
    st_path = os.path.join(RENDER_DIR, f"{gid.replace('g', 'grp')}_state.json")
    if os.path.exists(st_path):
        st = json.load(open(st_path, encoding="utf-8"))
        d0 = gc.GROUPS[gid]["days"][0]
        pfs = ((st.get(d0) or {}).get("tape_conditions") or {}).get("prior_full_session") or {}
        if pfs.get("session") == adate:
            out["session_activity"] = {
                "n_trades": pfs.get("n_trades"), "volume_lots": pfs.get("volume_lots"),
                "trades_per_min": pfs.get("trades_per_min"),
                "session_signed_flow": pfs.get("session_signed_flow"),
                "session_b_share": pfs.get("session_b_share"),
                "session_b_share_two_sided": pfs.get("session_b_share_two_sided"),
                "source": "tape_conditions.prior_full_session (scored leg)",
            }
            # S109 f14(a), raised by the state auditor against this file. A REPUTATION problem: the
            # source label said "the true tape" while session_b_share may be an S109 reconstruction
            # (recovered by algebraic identity because the leg reader's side encoding zeroed the direct
            # computation). Copying a declared value and dropping its declaration re-launders a
            # reconstruction as a measurement - the exact failure the basis field exists to prevent.
            # Carry the basis through whenever the source limb has one.
            if pfs.get("session_b_share_basis"):
                out["session_activity"]["session_b_share_basis"] = pfs["session_b_share_basis"]
                out["session_activity"]["source"] = (
                    "tape_conditions.prior_full_session (scored leg); NOTE session_b_share is a "
                    "declared RECONSTRUCTION, not a direct measurement - see session_b_share_basis")

    if out["is_holiday_session"]:
        act = out["session_activity"].get("n_trades")
        out["holiday_caveat"] = (
            f"{adate} is a HOLIDAY half-session"
            + (f" ({act} trades against a ~37,000 normal-session median)" if act else "")
            + ". The anchor CLOSE is chain-verified and sound. The anchor's LAST-HOUR DIRECTION is "
              "derived from this thin tape, so it is a weaker seam signal than the same field in "
              "G17-G21 - size the weekend/reopen read accordingly and do not treat it as a "
              "full-session exit. Declared, not hidden."
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("gids", nargs="+")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    for gid in args.gids:
        blk = build(gid)
        print(json.dumps(blk, indent=1))
        if args.write:
            p = os.path.join(RENDER_DIR, f"{gid}_anchor.json")
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(blk, fh, indent=1)
                fh.write("\n")
            print(f"[build_anchor_block] {gid}: WROTE {p}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
