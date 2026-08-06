"""
options_replay.py - E4: the settle-IV replay of the walked winter (OPTIONS_COACH_RESEARCH_S100.1).

THE OPTIONS COACH'S FIRST SCORECARD: takes the signal core's RECORDED BLIND day-book calls
(forecasts/grp7..grp11 - the calls as actually made, at that group's brain version; the
COACH_REPLAY_S97 honest pattern - the brain is NEVER re-run in-sample), translates each day
to the small typed options menu (research B5, v1 subset), prices the structure at settle
marks from the phase-ii IV surface, and scores per-event on the OPTIONS BOOK ledger
(never pooled with the futures day-book or the Kalshi echo book).

SCOPE (blind-run hygiene, binding): G7-G11 ONLY (Nov 5 - Jan 30). G12/G13 have NOT been
walked blind (S101 owns them from a fresh session); their windows join the replay only
after those blinds complete. THIS MODULE'S OUTPUT (and md_measures.json) CONTAINS
UNWALLED FEB-WINDOW DATA in its input stores and MUST NOT be given to the S101 blind
agent as input.

V1 TRANSLATION MENU (deliberately tiny; the scorecard tests the TRANSLATION of recorded
calls, it invents nothing):
  side long,  squeeze inactive -> call vertical: buy nearest-OTM ATM call, sell ~25d call
  side short, squeeze inactive -> put vertical: buy nearest-OTM ATM put, sell ~25d put
  side long,  squeeze ACTIVE   -> same call vertical, tagged squeeze cell (long-vol-compatible)
  side short, squeeze ACTIVE   -> DECLINED (never short the squeeze leg - doctrine)
  Sundays / non-option-sessions -> SKIPPED (no settle print exists; the gap content lands
  inside the next session's settle-to-settle move - named limitation)

CLOCK: entry at the last option session STRICTLY BEFORE the called day D (the marks a
D-open decision could actually know: the D-1 settles); exit at the first option session
>= D. One settle per day => the book is SETTLE-TO-SETTLE and says so; the futures
day-book's intraday session cell has no options analog yet (research E4 limitation).

LEAKAGE GATE (structural, asserted per event): entry_session < called_day <= exit_session,
and entry marks come only from the entry session's store rows (D-1-walled by construction
of the phase-ii store). The odcore tick-frame gate does not map 1:1 to a settle replay;
this invariant is its equivalent here and is checked on every event, hard-fail on violation.

ECONOMICS: 1-lot, multiplier 10,000 MMBtu; fee line $6.00 RT estimate (2 legs x 2 crossings
x ~$1.50 CME+clearing, VENDOR-CLAIM tier) - "settle-marked, execution unmeasured" labels
every row; spreads/fills are phase-EX territory, not claimed here. Attribution: delta P&L =
spread entry delta x dF x mult; residual = vol/theta/gamma, so right-vol-wrong-direction
days are visible per event.

STORE: data/options_ng/replay_g7_g11.json. Usage:
  python research/kalshi/options_replay.py --run
  python research/kalshi/options_replay.py --selftest
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from options_iv_surface import RATE, black76_delta, load_store  # noqa: E402

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FORECAST_DIR = os.path.join(_ROOT, "research", "kalshi", "forecasts")
STRUCT_PATH = os.path.join(_ROOT, "data", "contract_structure", "NG_structure.json")
VOL_PATH = os.path.join(_ROOT, "data", "vol_regime", "vol_regime.json")
OUT_PATH = os.path.join(_ROOT, "data", "options_ng", "replay_g7_g11.json")

GROUPS = [7, 8, 9, 10, 11, 12, 13]   # 12/13 joined 2026-07-21: their one-shot blinds are
                                     # COMPLETE on the trunk (grp12/grp13 committed by S101),
                                     # so the Feb window is no longer blind-restricted
MULT = 10000.0
FEE_RT_EST = 6.00
WING_DELTA = 0.25
ROLL_GUARD_DAYS = 2          # entry front rolls to next month when opex is this close


def _iso(d: str) -> str:
    return d if "-" in d else f"{d[:4]}-{d[4:6]}-{d[6:]}"


def _q(vals, q):
    if not vals:
        return None
    v = sorted(vals)
    return round(v[min(len(v) - 1, int(len(v) * q))], 2)


def _load_calls() -> list[dict]:
    calls = []
    for g in GROUPS:
        f = json.load(open(os.path.join(FORECAST_DIR, f"grp{g}.json")))
        for d in f["days"]:
            calls.append({"group": g, "brain": f.get("brain_version"),
                          "day": _iso(d["date"]), "dow": d.get("dow"),
                          "archetype": d.get("archetype"),
                          "guessed_net_usd": d.get("guessed_net_usd")})
    return calls


def _squeeze_active(struct: dict, day_iso: str) -> bool:
    st = struct.get(day_iso, {})
    exp = st.get("calendar_front_expiry")
    if not exp:
        return False
    dte = (datetime.date.fromisoformat(exp) - datetime.date.fromisoformat(day_iso)).days
    return dte <= 7 and (st.get("calendar_front_next_spread_chg_3d") or 0) > 0


def _pick_month(day_store: dict) -> str | None:
    """Entry front month with features; roll to next when opex is inside the guard."""
    for label in ("front", "next"):
        name = day_store.get(label)
        if name is None:
            continue
        m = day_store["months"][name]
        if m.get("atm_iv") is None:
            continue
        if label == "front" and m["days_to_opex"] < ROLL_GUARD_DAYS:
            continue
        return name
    return None


def _leg_rows(m: dict, side: str) -> tuple[list, list] | None:
    """(atm_leg, wing_leg) from LNE OTM rows on the chosen side. side C/P."""
    F, T = m["F"], m["days_to_opex"] / 365.0
    rows = [r for r in m.get("strikes_lne", []) if r[1] == side and r[3] is not None]
    if len(rows) < 2:
        return None
    if side == "C":
        atm_cands = [r for r in rows if r[0] >= F]
        atm = min(atm_cands, key=lambda r: r[0]) if atm_cands else None
    else:
        atm_cands = [r for r in rows if r[0] <= F]
        atm = max(atm_cands, key=lambda r: r[0]) if atm_cands else None
    if atm is None:
        return None
    best = None
    for r in rows:
        if r[0] == atm[0]:
            continue
        d = black76_delta(F, r[0], T, r[3], side)
        gap = abs(abs(d) - WING_DELTA)
        if best is None or gap < best[0]:
            best = (gap, r)
    if best is None or best[0] > 0.10:
        return None
    return atm, best[1]


def _mark(m_exit: dict, K: float, side: str) -> tuple[float, str] | None:
    """Exit mark for (K, side) from exit-session LNE rows; parity fallback (European)."""
    for r in m_exit.get("strikes_lne", []):
        if abs(r[0] - K) < 1e-6 and r[2] is not None:
            if r[1].upper() == side:
                return r[2], "direct"
            F, T = m_exit["F"], m_exit["days_to_opex"] / 365.0
            df = math.exp(-RATE * T)
            other = r[2]
            val = other + df * (F - K) if side == "C" else other - df * (F - K)
            return max(val, 0.0), "parity"
    return None


def run() -> dict:
    surface = load_store()
    if surface is None:
        sys.exit("[options_replay] iv store absent - options_iv_surface.py --build first")
    sessions = sorted(surface["sessions"])
    struct = json.load(open(STRUCT_PATH)) if os.path.exists(STRUCT_PATH) else {}
    vol = json.load(open(VOL_PATH)) if os.path.exists(VOL_PATH) else {}
    closes = {r["date"]: r["close"] for r in vol.get("sessions", {}).get("n0", []) if r.get("close")}

    events = []
    n_gate_checked = 0
    for call in _load_calls():
        D = call["day"]
        net = call["guessed_net_usd"]
        ev = dict(call)
        if net is None or net == 0:
            ev["outcome"] = "no_trade_flat_call"
            events.append(ev)
            continue
        side_dir = "long" if net > 0 else "short"
        entry_s = max((s for s in sessions if s < D), default=None)
        exit_s = min((s for s in sessions if s >= D), default=None)
        if entry_s is None or exit_s is None:
            ev["outcome"] = "skipped_out_of_coverage"
            events.append(ev)
            continue
        if D not in surface["sessions"]:
            ev["outcome"] = "skipped_no_session"      # Sundays/holidays; named limitation
            events.append(ev)
            continue
        assert entry_s < D <= exit_s, f"leakage invariant violated: {entry_s} {D} {exit_s}"
        n_gate_checked += 1
        squeeze = _squeeze_active(struct, D)
        if squeeze and side_dir == "short":
            ev.update({"outcome": "declined_squeeze_short", "squeeze": True})
            events.append(ev)
            continue
        e_day = surface["sessions"][entry_s]
        month = _pick_month(e_day)
        if month is None:
            ev["outcome"] = "skipped_no_month"
            events.append(ev)
            continue
        m_entry = e_day["months"][month]
        m_exit = surface["sessions"][exit_s]["months"].get(month)
        if m_exit is None or m_exit.get("F") is None:
            ev["outcome"] = "skipped_no_exit_month"
            events.append(ev)
            continue
        side = "C" if side_dir == "long" else "P"
        legs = _leg_rows(m_entry, side)
        if legs is None:
            ev["outcome"] = "skipped_no_legs"
            events.append(ev)
            continue
        atm, wing = legs
        entry_cost = atm[2] - wing[2]
        x_atm = _mark(m_exit, atm[0], side)
        x_wing = _mark(m_exit, wing[0], side)
        if x_atm is None or x_wing is None:
            ev["outcome"] = "skipped_no_exit_mark"
            events.append(ev)
            continue
        exit_val = x_atm[0] - x_wing[0]
        F0, F1 = m_entry["F"], m_exit["F"]
        T0 = m_entry["days_to_opex"] / 365.0
        d_atm = black76_delta(F0, atm[0], T0, atm[3], side) if atm[3] else 0.0
        d_wing = black76_delta(F0, wing[0], T0, wing[3], side) if wing[3] else 0.0
        spread_delta = d_atm - d_wing
        gross = (exit_val - entry_cost) * MULT
        delta_pnl = spread_delta * (F1 - F0) * MULT
        ev.update({
            "outcome": "traded", "structure": f"{'call' if side == 'C' else 'put'}_vertical",
            "squeeze": squeeze, "month": month,
            "entry_session": entry_s, "exit_session": exit_s,
            "legs": {"long": {"K": atm[0], "settle_in": atm[2], "iv_in": atm[3]},
                     "short": {"K": wing[0], "settle_in": wing[2], "iv_in": wing[3]}},
            "exit_marks": {"long": x_atm[0], "short": x_wing[0],
                           "method": f"{x_atm[1]}/{x_wing[1]}"},
            "F_entry": F0, "F_exit": F1, "spread_delta_entry": round(spread_delta, 4),
            "entry_cost_usd": round(entry_cost * MULT, 2),
            "pnl_gross_usd": round(gross, 2),
            "pnl_net_usd": round(gross - FEE_RT_EST, 2),
            "delta_pnl_usd": round(delta_pnl, 2),
            "residual_pnl_usd": round(gross - delta_pnl, 2),
            "actual_dF": round(F1 - F0, 4),
            "fut_close_move_usd": (round((closes[exit_s] - closes[entry_s]) * MULT, 2)
                                   if entry_s in closes and exit_s in closes else None),
            "label": "settle-marked, execution unmeasured",
        })
        events.append(ev)

    traded = [e for e in events if e["outcome"] == "traded"]
    cells: dict[str, list[float]] = {}
    for e in traded:
        key = f"g{e['group']}|{e['structure']}|{'squeeze' if e['squeeze'] else 'normal'}"
        cells.setdefault(key, []).append(e["pnl_net_usd"])
    out = {
        "meta": {"built_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                 "groups": GROUPS, "blind_files_only": True, "fee_rt_est_usd": FEE_RT_EST,
                 "n_calls": len(events), "n_traded": len(traded),
                 "n_leakage_checked": n_gate_checked,
                 "outcome_counts": {o: sum(1 for e in events if e["outcome"] == o)
                                    for o in sorted({e["outcome"] for e in events})},
                 "ledger": "OPTIONS BOOK (never pooled with the futures day-book or Kalshi echo book)",
                 "label": "settle-to-settle, 1-lot, settle-marked, execution unmeasured"},
        "events": events,
        "cells": {k: {"n": len(v), "sum": round(sum(v), 2), "med": _q(v, .5),
                      "p10": _q(v, .1), "p90": _q(v, .9),
                      "n_pos": sum(1 for x in v if x > 0)} for k, v in sorted(cells.items())},
    }
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=1)
    print(f"[options_replay] {len(events)} calls -> {len(traded)} traded; "
          f"leakage invariant checked on {n_gate_checked} events; -> {os.path.relpath(OUT_PATH, _ROOT)}")
    print("outcomes:", json.dumps(out["meta"]["outcome_counts"]))
    print("\nOPTIONS BOOK cells (net USD, per-event):")
    for k, v in out["cells"].items():
        print(f"  {k:34s} n={v['n']:2d} pos={v['n_pos']:2d} med={v['med']:>8} "
              f"p10={v['p10']:>8} p90={v['p90']:>8} sum={v['sum']:>9}")
    per_group = {}
    for e in traded:
        per_group.setdefault(e["group"], []).append(e["pnl_net_usd"])
    print("\nper-group footnotes (sums are descriptors, rows are the record):")
    for g in sorted(per_group):
        v = per_group[g]
        print(f"  G{g}: n={len(v)} pos={sum(1 for x in v if x > 0)} sum={round(sum(v), 2)}")
    return out


def _selftest() -> int:
    ok = True

    def chk(c, m):
        nonlocal ok
        print(("  PASS " if c else "  FAIL ") + m)
        ok = ok and bool(c)

    print("[options_replay selftest]")
    if not os.path.exists(OUT_PATH):
        print("  SKIP (run --run first)")
        return 0
    out = json.load(open(OUT_PATH))
    chk(out["meta"]["n_calls"] >= 60, f"calls loaded: {out['meta']['n_calls']} (G7-G11)")
    chk(out["meta"]["n_traded"] >= 30, f"traded events: {out['meta']['n_traded']}")
    chk(out["meta"]["n_leakage_checked"] == sum(
        v for k, v in out["meta"]["outcome_counts"].items()
        if k not in ("no_trade_flat_call", "skipped_out_of_coverage", "skipped_no_session")),
        "leakage invariant checked on every session-priced event")
    for e in out["events"]:
        if e["outcome"] == "traded":
            chk(e["entry_session"] < e["day"] <= e["exit_session"], "first traded event clock sane")
            break
    dec = out["meta"]["outcome_counts"].get("declined_squeeze_short", 0)
    print(f"  INFO declined_squeeze_short: {dec} (doctrine gate exercised)")
    print("[options_replay selftest]", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    sys.exit(_selftest() if a.selftest else (0 if run() else 1))
