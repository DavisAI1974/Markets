"""group_he24_he1_handoff.py - GENERIC HE24->HE1 day-boundary handoff chain (S105). Config-driven:
    python research/kalshi/group_he24_he1_handoff.py g17

The boundary handoff carries STATE, never the day-net. Built from the ACTUAL prior-day MBO tape (objective
exit state) + the prior owner's round-1 exit READ (verbatim). Precomputed once, injected into the round-2
specialist re-run so the block is ONE continuous coordinated path (HE24 exit -> HE1 open), not siloed days.
Writes <gid>_he24_he1_handoffs.json under forecasts/. The original he24_he1_handoff.py stays the G15 record.
"""
import os, sys, json
import numpy as np, pandas as pd, databento as db
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import group_config as gc

HERE = os.path.dirname(os.path.abspath(__file__))
LEG_DIR = os.path.join(HERE, "..", "..", "data", "ng_mbo_g17")
FC = os.path.join(HERE, "forecasts")
RENDER_DIR = os.path.join(HERE, "renders", "ng_refine_s95")
ET = "America/New_York"; MULT = 10000.0
_DOW = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def load_trades(gid, day):
    store = db.DBNStore.from_file(os.path.join(LEG_DIR, f"{gc.leg_for(gid, day)}_{day}.dbn.zst"))
    ts, px, sd = [], [], []
    for r in store:
        if type(r).__name__ != "MBOMsg" or str(getattr(r.action, "value", r.action)) != "T":
            continue
        p = r.price
        if p in (None, 9223372036854775807, -9223372036854775808):
            continue
        s = getattr(r.side, "value", r.side)
        ts.append(int(r.ts_event) / 1e9); px.append(p / 1e9)
        sd.append(1 if str(s) in ("B", "Bid") else (-1 if str(s) in ("A", "Ask") else 0))
    o = np.argsort(ts)
    return np.asarray(ts)[o], np.asarray(px)[o], np.asarray(sd)[o]


def prior_owner_verdict(gid, prior_date, owner, source="actual"):
    """The prior owner's round-1 read, carried verbatim. grp<N>_mbo_specialist_<X>.json is a REFINE
    artifact (written by a price-bearing run), so a blind run must never consult it - S107 guard: in
    blind mode this returns a stated null rather than falling through to the refine's read. Whether the
    blind should instead carry its OWN prior-owner read (and under what filename) is a design decision,
    deliberately left open rather than guessed at here."""
    n = gid[1:]
    if source == "blind":
        return {"withheld": "refine posterior not readable from a blind run (price-bearing artifact); "
                            "no blind-side prior-owner read is wired yet"}
    f = os.path.join(FC, f"grp{n}_mbo_specialist_{owner}.json")
    if not os.path.exists(f):
        return None
    d = json.load(open(f)); entries = d.get("days") or (d if isinstance(d, list) else list(d.values()))
    for e in entries:
        if isinstance(e, dict) and str(e.get("date", "")).replace("-", "") == prior_date:
            return {"owner": owner, "continuation_vs_reversal": e.get("continuation_vs_reversal"),
                    "turn_time_et": e.get("turn_time_et"), "trend_vs_chop": e.get("trend_vs_chop"),
                    "mbo_verdict": (e.get("mbo_verdict") or "")[:300], "confidence": e.get("confidence")}
    return None


def exit_states_path(gid):
    return os.path.join(RENDER_DIR, f"{gid}_exit_states.json")


_PRECOMPUTED = {}


def _precomputed(gid):
    """The stage-time exit-state artifact, or None if this group predates it / was never staged with it.

    S108: exit_state() is the ONLY thing in a staged group's whole run cycle that still reached into
    data/ (the raw MBO legs, ~146MB of a 463MB plane) - round-1 specialists, both coordinators and the
    round-2 re-run all read committed artifacts only. data/ is gitignored and dies with the container,
    so that single call forced a full S3 restore (and live credentials) on any session that only wanted
    to run an already-staged group. Computing it at STAGE time - when the legs are local and the keys
    are in hand by definition - and committing the result makes a staged group self-contained.
    """
    if gid not in _PRECOMPUTED:
        p = exit_states_path(gid)
        _PRECOMPUTED[gid] = json.load(open(p)).get("days") if os.path.exists(p) else None
    return _PRECOMPUTED[gid]


def exit_state(gid, day):
    """ACTUAL-tape exit state. Prefers the stage-time artifact; falls back to reading the legs.

    ONLY ever reached on source='actual' - the blind path calls exit_state_blind(), which is built
    from the assembled forecast and never touches the tape. That separation is what S107's price-leak
    fix established and it is load-bearing here: this artifact is realized-price-derived, so a blind
    run must never consult it. main() asserts the separation rather than trusting the call graph.
    """
    pre = _precomputed(gid)
    if pre is not None and day in pre:
        return pre[day]          # authoritative: a stored null means the day genuinely had no trades
    return exit_state_from_legs(gid, day)


def exit_state_from_legs(gid, day):
    """Read the raw MBO leg off disk. The original exit_state() body, unchanged - this is what the
    stage-time precompute calls, and what exit_state() falls back to when no artifact exists."""
    ts, px, sd = load_trades(gid, day)
    if px.size == 0:
        return None
    et = pd.to_datetime(ts, unit="s", utc=True).tz_convert(ET)
    o, c = float(px[0]), float(px[-1])
    lo_i, hi_i = int(np.argmin(px)), int(np.argmax(px))
    mask = ts >= (ts[-1] - 3600); lh_px = px[mask]; lh_sd = sd[mask]
    lhd = int(np.sign(lh_px[-1] - lh_px[0])) if lh_px.size > 1 else 0
    lhf = int(np.sign(lh_sd.sum())) if lh_sd.size else 0
    rng = float(px.max() - px.min()); off_low = round((c - float(px.min())) / rng, 2) if rng > 1e-9 else 0.0
    return {"close_px": round(c, 3), "open_px": round(o, 3), "day_move_usd": round((c - o) * MULT),
            "last_hour_dir": lhd, "last_hour_signed_flow": lhf,
            "low_et": et[lo_i].strftime("%H:%M"), "high_et": et[hi_i].strftime("%H:%M"),
            "close_off_low_frac": off_low,
            "low_late": bool(et[lo_i] >= et[-1] - pd.Timedelta(hours=3)),
            "high_late": bool(et[hi_i] >= et[-1] - pd.Timedelta(hours=3))}


def precompute_exit_states(gid):
    """Compute every day's ACTUAL exit state from the legs and commit it. Called by stage_group, when
    the legs are local and the credentials are in hand by definition.

    Writes renders/ng_refine_s95/<gid>_exit_states.json. Stores an entry for EVERY configured day,
    including an explicit null for a day whose leg holds no trades, so the reader can tell 'known to
    have no trades' from 'not precomputed' - a silently missing key is the recurring failure mode this
    whole artifact is meant to avoid, not one to introduce.
    """
    days = gc.GROUPS[gid]["days"]
    out, missing = {}, []
    for d in days:
        try:
            out[d] = exit_state_from_legs(gid, d)
        except FileNotFoundError:
            missing.append(d)
    if missing:
        raise SystemExit(f"{gid}: cannot precompute exit states - legs absent for {missing}. "
                         f"Stage with the data plane restored; do NOT commit a partial artifact.")
    p = exit_states_path(gid)
    json.dump({"spec": "stage-time ACTUAL exit states for the HE24->HE1 chain (S108)",
               "group": gid,
               "provenance": "derived from the realized MBO legs - REFINE-ONLY. A blind run must never "
                             "read this file; the blind chain is built by exit_state_blind() from the "
                             "assembled forecast.",
               "n_days": len(out),
               "n_null": sum(1 for v in out.values() if v is None),
               "days": out}, open(p, "w"), indent=1)
    print(f"[exit_states] {gid}: {len(out)} days "
          f"({sum(1 for v in out.values() if v is None)} null) -> {os.path.relpath(p, HERE)}")
    return out


def _date(d):
    return pd.Timestamp(f"{d[:4]}-{d[4:6]}-{d[6:]}")


def exit_state_blind(gid, day, blind_days, prev_close):
    """Forecast exit state from the assembled blind grp<n>.json (walled - no actual tape). Uses the
    day's forecast day-move + its p50 path for last-hour dir + close_off_low. Signed flow is UNKNOWN
    in the blind (null) - the blind handoff carries forecast STATE, direction still from the D-1 tilt."""
    e = blind_days.get(day)
    if e is None:
        return None
    dm = e.get("guess_day_move_usd", 0)
    seam = gc.GROUPS[gid].get("seam")
    gap = 0 if day == seam else (e.get("overnight_gap_usd", 0) or 0)
    net = dm - (0 if day == seam else gap)
    open_px = round(prev_close + gap / MULT, 3)
    close_px = round(open_px + net / MULT, 3)
    path = [(h, v) for h, v in (e.get("path_p50") or []) if h is not None and v is not None]
    if len(path) >= 2:
        lhd = int(np.sign(path[-1][1] - path[-2][1])) or int(np.sign(net))
        vals = [v for _, v in path]
        rng = max(vals) - min(vals)
        off_low = round((path[-1][1] - min(vals)) / rng, 2) if rng > 1e-9 else 0.5
    else:
        lhd = int(np.sign(net)); off_low = 1.0 if net > 0 else 0.0
    return {"close_px": close_px, "open_px": open_px, "day_move_usd": dm,
            "last_hour_dir": lhd, "last_hour_signed_flow": None,   # unknown in the blind
            "low_et": None, "high_et": None, "close_off_low_frac": off_low,
            "low_late": None, "high_late": None, "source": "forecast"}


def main(gid, source="actual"):
    g = gc.GROUPS[gid]; DAYS = g["days"]; SEAM = g.get("seam"); ANCHOR = g["anchor"]; OWNER = gc.owner_map(gid)
    blind_days = {}
    if source == "blind":
        n = gid[1:]
        bpath = os.path.join(FC, f"grp{n}.json")
        blind_days = {str(r["date"]).replace("-", ""): r for r in json.load(open(bpath)).get("days", [])}

    def _exit(day, prev_close):
        # S108: the precomputed artifact is realized-price-derived, so it is reachable ONLY through
        # exit_state() and ONLY on source='actual'. Asserted here rather than left to the call graph -
        # S107's leak was exactly this shape (a tape read that did not check the source), and moving
        # the computation to stage time must not quietly re-open it.
        if source == "blind":
            return exit_state_blind(gid, day, blind_days, prev_close)
        return exit_state(gid, day)

    moves, cum_by, exits, prev_close, cum = {}, {}, {}, ANCHOR, 0.0
    for d in DAYS:
        st = _exit(d, prev_close)
        if st is None:
            continue
        exits[d] = st
        gap = 0 if d == SEAM else round((st["open_px"] - prev_close) * MULT)
        moves[d] = gap + round((st["close_px"] - st["open_px"]) * MULT)
        cum += moves[d]; cum_by[d] = round(cum); prev_close = st["close_px"]
    ordered = [d for d in DAYS if d in moves]

    def chain_state(upto):
        seq = [moves[ordered[j]] for j in range(upto + 1)]
        pol = int(np.sign(sum(seq[-3:]))) or int(np.sign(seq[-1])); age = 0
        for m in reversed(seq):
            if int(np.sign(m)) == pol or m == 0:
                age += 1
            else:
                break
        # S108 THE CHAIN_AGE DEFINITION COLLISION. On G20's 0601 boundary one quantity carried THREE
        # incompatible values: this builder said 0, the brain's own doctrine wording ("sessions since
        # the turn") implies 3, and E read 5 (sessions from the anchor). The gap is not cosmetic - under
        # the brain's definition B's day FAILS the age>=5 arm of covering_extension_distribution_flip
        # whose exemplar G19 0520 PASSES it at age 5, and E separately measured the same arm costing
        # 1,350 on 0605, where a single -70 close on 0602 reset this counter while realized cum ran
        # +2,550 -> +3,200 WITHOUT EVER TURNING.
        #
        # What this counter measures is CONSECUTIVE SAME-SIGNED DAY-MOVES. That is a real quantity and
        # nothing downstream is silently re-pointed - it keeps its name and its value. What was missing
        # is REGIME age, which the incumbent boundary.chain_label_must_track_realized_cum already says
        # the label must track: sessions since the realized CUM last set its running extreme on the far
        # side of the current polarity. A one-day counter-move does not reset that; a genuine turn does.
        # Both are emitted, both are labelled, and the specialist chooses - the same additive pattern as
        # the Monday prior_full_session and the two-sided b_share.
        cum_seq = [cum_by[ordered[j]] for j in range(upto + 1)]
        if pol >= 0:
            ext_i = min(range(len(cum_seq)), key=lambda i: cum_seq[i])      # UP chain -> age from the low
        else:
            ext_i = max(range(len(cum_seq)), key=lambda i: cum_seq[i])      # DOWN chain -> age from the high
        return pol, age, upto - ext_i

    handoffs = {}
    for i, d in enumerate(ordered):
        if i == 0:
            handoffs[d] = {"note": f"block open - no prior in-block session; anchor to {ANCHOR} down/flat."}
            continue
        # S107: use the SOURCE-AWARE exit state computed above, never a fresh read of the actual tape.
        # This line previously called exit_state(gid, pd_) unconditionally, so a --source blind run
        # still received the REALIZED close/open/day-move/signed-flow - a direct price leak into the
        # blind's handoff. In --source actual mode exits[pd_] IS exit_state(gid, pd_), so the refine
        # path is unchanged (verified byte-identical against the committed g19 chain).
        pd_ = ordered[i - 1]; pol, age, regime_age = chain_state(i - 1); st = exits[pd_]
        weekend = (_date(d) - _date(pd_)).days > 1
        handoffs[d] = {"prior_date": pd_, "prior_dow": _DOW[_date(pd_).weekday()],
                       "prior_owner": OWNER.get(pd_), "receiving_owner": OWNER.get(d),
                       "boundary_kind": ("weekend_reopen" if weekend else ("post_seam" if pd_ == SEAM else "overnight")),
                       "prior_exit_state": st, "chain_polarity": pol, "chain_age_sessions": age,
                       "chain_age_basis": ("consecutive same-signed DAY-MOVES ending at the prior "
                                           "session; a single counter-signed close resets it"),
                       "chain_regime_age_sessions": regime_age,
                       "chain_regime_age_basis": ("sessions since realized CUM last set its running "
                                                  "extreme opposite the current polarity - the 'sessions "
                                                  "since the turn' the brain's own doctrine means, and "
                                                  "what boundary.chain_label_must_track_realized_cum "
                                                  "requires. A one-day counter-move does NOT reset it. "
                                                  "Use this for age-gated plays "
                                                  "(covering_extension_distribution_flip)."),
                       "cum_from_anchor_usd": cum_by[pd_], "prior_owner_read": prior_owner_verdict(gid, pd_, OWNER.get(pd_), source),
                       "carry_rules": [
                           "Start from your blind + prior posterior; use this STATE to size/time, not to override direction.",
                           "Direction stays with the D-1 trade tilt; a turn realizing in the overnight seam is sized by the PRIOR-day exhaustion read, not front-run.",
                           ("Weekend: Monday inherits the Friday CLOSE + chain state, not the Friday day-move; reopen gap SIGN is noise." if weekend else
                            "Seam: leg change never-traded; anchor to the new leg's close, offset scoring-only." if pd_ == SEAM else
                            "Read your open RELATIVE to the prior close's exit condition (close_off_low, low_late, last_hour_dir/flow).")]}
    out = os.path.join(FC, f"{gid}_he24_he1_handoffs.json")
    json.dump({"spec": "he24->he1 boundary handoff (STATE not day-net); brain s102.6", "group": gid, "days": handoffs},
              open(out, "w"), indent=1)
    print("wrote", os.path.relpath(out, HERE))
    for d in ordered:
        h = handoffs[d]
        if "prior_date" not in h:
            print(f"{d} {OWNER[d]}  [block open]"); continue
        st = h["prior_exit_state"]
        # S107: blind-source exit states legitimately carry None for the fields the price mask withholds
        # (signed flow, low/high timing) - render them as n/a instead of crashing the summary.
        _sd = lambda v: f"{v:+d}" if isinstance(v, int) else "n/a"
        print(f"{d} {OWNER[d]} <- {h['prior_date']}({h['prior_owner']}) {h['boundary_kind']:14} "
              f"pol{h['chain_polarity']:+d} age{h['chain_age_sessions']} cum{h['cum_from_anchor_usd']:+5d} | "
              f"prior close {st['close_px']} off_low {st['close_off_low_frac']} lh_dir{_sd(st['last_hour_dir'])} "
              f"lh_flow{_sd(st['last_hour_signed_flow'])} low@{st['low_et'] or 'n/a'}{' LATE' if st['low_late'] else ''}")


if __name__ == "__main__":
    # S107: --source was accepted by main() but never wired to the CLI, so the BLIND round-2 chain
    # (--source blind) was unreachable. Defaults to actual, so existing refine invocations are unchanged.
    _a = sys.argv[1:]
    _src = "actual"
    if "--source" in _a:
        _i = _a.index("--source"); _src = _a[_i + 1]; del _a[_i:_i + 2]
    if _src not in ("actual", "blind"):
        raise SystemExit(f"--source must be 'actual' or 'blind', got {_src!r}")
    if not _a:
        raise SystemExit("usage: group_he24_he1_handoff.py [--source actual|blind] [--precompute] <gid>")
    # S108: --precompute builds the stage-time ACTUAL exit-state artifact from the legs (stage_group
    # calls this). It is refine-side data by construction, so it is rejected under --source blind.
    if "--precompute" in _a:
        _a.remove("--precompute")
        if _src == "blind":
            raise SystemExit("--precompute builds ACTUAL exit states; it is meaningless under --source blind")
        precompute_exit_states(_a[0])
    else:
        main(_a[0], _src)
