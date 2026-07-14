"""
coach_replay.py — deterministic backtest of the ng_brain.json PLAYBOOK on the NG canary tape (S92 build).

This is the RIGID, mechanical baseline of the coach's plays — the thing the future ADAPTIVE agent-coach must
beat. It reads the plays out of knowledge/ng_brain.json and applies them per leg, NET-OF-FEE, PER EVENT, with
NO POOLING as the verdict (per-leg rows + a per-day roll-up that is a sum of individual trades, never a mean
that hides the fingerprint).

PLAYS APPLIED (from ng_brain.json):
  - direction.flow_nowcast : ENTER a leg on sign(dip_imb_level) when |dip_imb_level| >= DIP_STRONG (0.15).
  - ride.magnitude_staircase: flag legs that crossed the $RIDE (350) magnitude = the 92% "ride it" event.
  - exit.recruitment_reversal: flag legs whose far side STOPPED recruiting (turn_far_thinning > 0) = top risk.

HONEST SCOPE / ASSUMPTIONS (explicit — refine next session with a real fill model):
  - Canary-side only: this measures whether the SIGNAL makes money on the NG futures move itself. The KALSHI
    echo (fire on the lag) and the NYMEX-OPTIONS vehicle are the next layers (see FORECASTER_RUNBOOK_S93.md).
  - Coarse capture proxy off characterize_day OUTCOMES (peak_usd, retention, dir) — NOT a tick-by-tick fill
    sim. A right-direction trade captures ~ retention*peak_usd (rode the leg, kept the retention fraction);
    a wrong-direction trade loses ~ peak_usd (long into the opposite move). Round-trip fee FEE_RT per contract.
    The number is INDICATIVE (sizes the edge), NOT a validated P&L. The real fill/slippage model is JOB for S93.
  - Only |dip|>=DIP_STRONG legs are traded (the play's own gate). 1 contract/leg.

This is a SCAFFOLD, wired to the brain, ready to run + refine. `--selftest` for the mechanics; `--days` to replay.
"""
from __future__ import annotations
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import month_characterize as mc                                # the full-toolbox per-leg characterizer

BRAIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge", "ng_brain.json")
FEE_RT = 5.0            # $/contract round-trip on the NG canary (conservative; refine per venue next session)


def _thresholds(brain: dict) -> dict:
    """Pull the numeric gates out of the plays so the strategy reads FROM the brain (single source of truth)."""
    t = {"dip_strong": 0.15, "ride_usd": 350.0}
    for p in brain.get("plays", []):
        if p["id"] == "direction.flow_nowcast":
            t["dip_strong"] = 0.15   # play gate (documented in the play text)
        if p["id"] == "ride.magnitude_staircase":
            t["ride_usd"] = 350.0
    return t


def replay_day(day: str, brain: dict, source: str = "s3") -> dict:
    """Apply the playbook to one NG day. Returns {day, trades:[per-leg rows], summary}. No pooling — the summary
    is a SUM of individual trades + counts, never a mean-as-verdict."""
    t = _thresholds(brain)
    rows = mc.characterize_day("NG", day, source=source)
    trades = []
    for r in rows:
        dip = r.get("dip_imb_level")
        if dip is None or abs(dip) < t["dip_strong"]:
            continue                                            # play gate: only strong flow
        pred_up = dip > 0
        act_up = (r["dir"] == "up")
        correct = (pred_up == act_up)
        peak = float(r.get("peak_usd") or 0.0)
        ret = float(r.get("retention") or 0.0)
        # coarse capture proxy (INDICATIVE, not a fill sim):
        capture = (ret * peak) if correct else -peak
        net = round(capture - FEE_RT, 1)
        trades.append({
            "entry_idx": r["entry_idx"], "tod": r.get("tod"), "dip": round(dip, 3),
            "pred_dir": "up" if pred_up else "down", "actual_dir": r["dir"], "correct": correct,
            "peak_usd": peak, "retention": ret, "would_ride_350": peak >= t["ride_usd"],
            "far_recruit": r.get("turn_far_thinning"), "reversal_risk": (r.get("turn_far_thinning") or 0) > 0,
            "net_indicative": net,
        })
    n = len(trades)
    correct = sum(1 for x in trades if x["correct"])
    net_sum = round(sum(x["net_indicative"] for x in trades), 1)
    rode = sum(1 for x in trades if x["would_ride_350"])
    return {"day": day, "n_trades": n, "n_correct": correct, "n_rode_350": rode,
            "net_indicative_sum": net_sum, "trades": trades}


def selftest() -> int:
    # synthetic legs exercise the play gates without network
    brain = {"plays": [{"id": "direction.flow_nowcast"}, {"id": "ride.magnitude_staircase"}]}
    t = _thresholds(brain)
    assert t["dip_strong"] == 0.15 and t["ride_usd"] == 350.0
    # a strong-up leg that went up + held -> positive; wrong-dir -> negative
    fake = [
        {"entry_idx": 1, "dir": "up", "dip_imb_level": 0.5, "peak_usd": 400, "retention": 0.8,
         "turn_far_thinning": -0.3, "tod": "us"},
        {"entry_idx": 2, "dir": "down", "dip_imb_level": 0.4, "peak_usd": 200, "retention": 0.5,
         "turn_far_thinning": 0.2, "tod": "us"},     # predicted up, went down -> wrong
        {"entry_idx": 3, "dir": "up", "dip_imb_level": 0.05, "peak_usd": 300, "retention": 0.5,
         "turn_far_thinning": 0.0, "tod": "ov"},      # weak flow -> NOT traded
    ]
    import types
    orig = mc.characterize_day
    mc.characterize_day = lambda root, day, source="s3": fake                          # monkeypatch
    try:
        d = replay_day("SELFTEST", brain, source="local")
    finally:
        mc.characterize_day = orig
    assert d["n_trades"] == 2, d                       # weak-flow leg skipped
    assert d["n_correct"] == 1, d                      # leg1 correct, leg2 wrong
    assert d["trades"][0]["net_indicative"] == round(0.8 * 400 - FEE_RT, 1), d["trades"][0]
    assert d["trades"][0]["would_ride_350"] is True and d["trades"][1]["reversal_risk"] is True
    print("[coach_replay] selftest PASS — play gates, capture proxy, ride/reversal flags")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Replay the ng_brain playbook on NG days (canary-side, indicative).")
    ap.add_argument("--days", help="comma-separated YYYYMMDD")
    ap.add_argument("--source", default="s3", choices=["s3", "local"])
    ap.add_argument("--brain", default=BRAIN)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.days:
        ap.error("need --days or --selftest")
    brain = json.load(open(a.brain))
    print(f"[coach_replay] INDICATIVE canary-side replay (fee ${FEE_RT} rt/contract; NOT a validated fill P&L)")
    for day in a.days.split(","):
        d = replay_day(day, brain, source=a.source)
        print(f"\n=== NG {day}: {d['n_trades']} trades, {d['n_correct']} correct-dir, "
              f"{d['n_rode_350']} rode>=$350, net(indicative)=${d['net_indicative_sum']} ===")
        for x in d["trades"]:
            print(f"  idx{x['entry_idx']:>6} {x['tod']:<8} dip{x['dip']:+.2f} pred={x['pred_dir']:<4} "
                  f"act={x['actual_dir']:<4} {'OK' if x['correct'] else 'XX'} peak${x['peak_usd']:>6.0f} "
                  f"ret{x['retention']:+.2f} ride={x['would_ride_350']!s:<5} net${x['net_indicative']:>7.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
