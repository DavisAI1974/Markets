"""state_health.py - the stage-time COMPLETENESS ASSERTION (S107).

WHY THIS EXISTS. Six separate times in one session, a decision_state block was silently EMPTY and
nothing said so:

  1. storage / stor_surprise    a missing data/eia_surprise.json - dead across G18-G21
  2. tape_conditions signed flow  the L1 + MBO flow read absent - dead on G20/G21 as staged
  3. options_surface            the OI pin map absent - dead on G16, G20, G21
  4. vol_regime                 a hard-coded SPAN_END - dead on EVERY group from G16 on
  5. squeeze_watch              frozen on an EXPIRED front, reading active TRUE - a false positive
  6. weather                    the degree-day store one directory off the path the harness reads

Every one presented identically to a reader: a null, or {"masked_one_shot": true, "value": null} -
indistinguishable from a deliberate price mask or from "the market genuinely had no data". That
ambiguity is the bug. forecast_harness._load_json returns {} for a missing file, feeds return None
for "no coverage", and the one-shot mask emits {"value": null} when it has nothing to freeze; the
three are then impossible to tell apart downstream.

THE RULE THIS ENFORCES: a block is allowed to be empty only if something DECLARED it may be. Anything
else is a hard failure at stage time, before a specialist ever reads it - not a discovery in the
post-mortem, where a data hole gets written into the brain as a reasoning lesson.

Not a mask check. A masked block is EXPECTED to hide its value; what it must not do is arrive with
nothing frozen behind the mask, which is exactly how vol_regime went missing for five groups.
"""
from __future__ import annotations

# Blocks that must carry real content on EVERY day of a group.
REQUIRED_EVERY_DAY = (
    "dow", "curve_regime", "storage", "stor_surprise", "stor_surprise_sign",
    "storage_regional", "storage_consensus", "storage_vintage", "ngwu_balance",
    "steo_vintage", "cot", "flow_calendar", "solar", "nuclear_outages", "grid_stack",
    "weather", "weather_forecast", "weather_forecast_cycle", "freeze_risk",
    "model_disagreement", "tape_conditions",
)

# Price-derived blocks. Under a mask they are EXPECTED to be frozen at the anchor vintage - but the
# freeze must have captured something. `masked_one_shot` with a null value means the block was
# already empty when it was frozen, which is a data failure wearing a mask's clothes.
MASKED_MUST_HAVE_FROZEN_VALUE = (
    "contract_structure", "squeeze_watch", "vol_regime", "cash_basis", "options_surface",
)

# Legitimately absent most days - never a failure.
EXPECTED_SPARSE = ("holiday",)

# tape_conditions sub-reads that the DATA DOCTRINE calls the blind's primary channel.
TAPE_REQUIRED = ("session_signed_flow", "phase_signed_flow", "phase_b_share", "big_print_b_share")


def _empty(v) -> bool:
    if v is None or v == {} or v == []:
        return False if v == 0 else True
    if isinstance(v, dict):
        # a mask envelope carrying nothing
        if v.get("masked_one_shot") and v.get("value", "__absent__") is None:
            return True
        if set(v.keys()) <= {"masked_one_shot", "vintage_asof", "value"} and v.get("value") is None:
            return True
    return False


def audit(state: dict) -> dict:
    """Return {'hard': [...], 'soft': [...], 'days': n}. `hard` blocks a run; `soft` is announced."""
    days = [k for k in state if k.isdigit()]
    hard, soft = [], []
    if not days:
        return {"hard": ["state has no day keys at all"], "soft": [], "days": 0}

    for blk in REQUIRED_EVERY_DAY:
        bad = [d for d in days if _empty(state[d].get(blk))]
        if bad:
            hard.append(f"{blk}: EMPTY on {len(bad)}/{len(days)} days ({bad[0]}..{bad[-1]}) - "
                        f"required every day")

    for blk in MASKED_MUST_HAVE_FROZEN_VALUE:
        bad = [d for d in days if _empty(state[d].get(blk))]
        if bad:
            hard.append(f"{blk}: frozen with NO VALUE on {len(bad)}/{len(days)} days - the mask "
                        f"had nothing to freeze; this is a missing store, not a mask")

    for d in days:
        tc = state[d].get("tape_conditions") or {}
        missing = [f for f in TAPE_REQUIRED if f not in tc]
        if missing:
            hard.append(f"tape_conditions {d}: missing {missing} - the non-price flow read is the "
                        f"blind's PRIMARY channel under the data doctrine")
            break
        fh = state[d].get("firehose_present")
        if fh is None:
            soft.append(f"{d}: no firehose_present flag (state built before the S107 fix?)")
            break

    # degraded-but-declared conditions: announce, never block
    for d in days:
        fh = state[d].get("firehose_present") or {}
        if fh and not fh.get("l1_book"):
            soft.append(f"{d}: L1 book absent for the prior session (declared) - thin reopen?")
        if state[d].get("frozen_structure_stale"):
            s = state[d]["frozen_structure_stale"]
            soft.append(f"{d}: frozen front {s.get('frozen_calendar_front_symbol')} EXPIRED "
                        f"{s.get('frozen_calendar_front_expiry')}; live front "
                        f"{s.get('live_front_symbol_calendar')} (declared)")
        if state[d].get("flow_read_error"):
            hard.append(f"{d}: flow_read_error {state[d]['flow_read_error']!r}")
        # S108 THE PARTIAL-TAIL DEFECT (hole #7). The last day of any nws_temp fetch range is computed
        # on incomplete hours and is WRONG while still reporting coverage 1.0 and n_stations 16 - so it
        # is a WRONG-VALUE defect, not an empty-block one, and the completeness assertion above cannot
        # see it. Measured: 2026-07-13 read gw_cdd 8.034/mod_cool as a pull tail and 13.548/hard_cool
        # once a later day was fetched, against neighbours of 14.2 and 15.5. G23's window ended exactly
        # on such a day. HARD, because a wrong weather value is worse than a missing one: it reads as
        # decision-legit.
        w = state[d].get("weather") or {}
        if isinstance(w, dict) and w.get("provisional_tail"):
            hard.append(f"{d}: weather is a PROVISIONAL FETCH TAIL (computed on incomplete hours; "
                        f"coverage/n_stations do not detect it) - re-fetch nws_temp with at least one "
                        f"day of margin past {d} and restage")

        # S109 THE B_SHARE RECONCILIATION. Every check above this line asks "is the field THERE?" - and
        # the recurring enemy has now worn four faces, three of which answer that question with a
        # confident yes: EMPTY (S107's six), WRONG VALUE (the weather tail), OFF-INSTRUMENT (the tape
        # after a roll), and now WRONG ENCODING (the leg reader spelling side as an int against math
        # that tested for a string). session_b_share served a hard 0.0 on all 8 scored-leg days of both
        # G22 and G23 - present, numeric, in range, right owner, internally consistent.
        #
        # The only thing that catches a wrong-but-well-formed value is a comparison against an
        # INDEPENDENT measurement of the same quantity, and here the state already carries one. The
        # three fields are algebraically locked: b_share = buys/tot and b_share_two_sided = buys/sides
        # with sides = tot*(1-unsided_frac), so
        #                 session_b_share == session_b_share_two_sided * (1 - unsided_volume_frac)
        # is an IDENTITY, not a correlation. It reproduces every continuous-store day in G22/G23 to the
        # third decimal and fails every leg day by 0.39-0.52. Tolerance 0.002 covers the compounding of
        # two independently 3-dp-rounded inputs. HARD: a b_share pinned at zero silently satisfies every
        # "sub-0.50 sell tape" bar in the brain, on every day at once, and those include SIGN plays.
        for blk in ("tape_conditions",):
            for scope in (state[d].get(blk) or {}, ((state[d].get(blk) or {}).get("prior_full_session") or {})):
                if not isinstance(scope, dict):
                    continue
                b, b2 = scope.get("session_b_share"), scope.get("session_b_share_two_sided")
                u = scope.get("unsided_volume_frac")
                if not all(isinstance(x, (int, float)) for x in (b, b2, u)):
                    continue
                pred = b2 * (1.0 - u)
                if abs(pred - b) > 0.002:
                    hard.append(
                        f"{d}: {blk}{'/prior_full_session' if scope is not state[d].get(blk) else ''} "
                        f"session_b_share {b} CONTRADICTS its own two-sided pair "
                        f"({b2} two-sided x {round(1.0 - u, 3)} sided-volume = {pred:.3f}) on session "
                        f"{scope.get('session')} [{scope.get('source_store')}] - the b_share family does "
                        f"not reconcile, so at least one member is computed off a different tape or a "
                        f"different side encoding. Do not reason over it.")

        # S109 f1 THE FROZEN-BUT-LIVE RECONCILIATION. A fifth kind of silently wrong input: a
        # DETERMINISTIC quantity frozen alongside the designed price mask, then republished under a
        # "_live" name and used to compute a boolean served as current. squeeze_watch's calendar limb
        # read a constant dte 5 / NGN26 on all ten days of G22 and G23 while flow_carrying the real
        # walk 4,3,2,1,0 then 21,20,19,18 - and asserted calendar_limb_satisfied_live TRUE on five
        # sessions whose live dte was 18-21 against a play window of <=7. S108 fixed a false NEGATIVE
        # here and shipped its mirror image. A presence check cannot see it: the field is there,
        # integer, in range, and self-consistent with the rest of its own frozen block.
        #
        # The reconciliation is exact and free: flow_calendar carries the same two quantities LIVE and
        # is never masked, so a "_live" field that disagrees with it is definitionally wrong.
        sw, fc = state[d].get("squeeze_watch") or {}, state[d].get("flow_calendar") or {}
        if isinstance(sw, dict) and isinstance(fc, dict):
            lv, fv = sw.get("days_to_calendar_front_expiry_live"), fc.get("days_to_futures_expiry")
            if isinstance(lv, int) and isinstance(fv, int) and lv != fv:
                hard.append(f"{d}: squeeze_watch days_to_calendar_front_expiry_live={lv} CONTRADICTS "
                            f"flow_calendar days_to_futures_expiry={fv} - the same deterministic "
                            f"calendar quantity, one of them frozen. A '_live' field that disagrees "
                            f"with the live block is not live.")
            ls, fs = sw.get("calendar_front_symbol_live"), fc.get("front_symbol_calendar")
            if ls and fs and ls != fs:
                hard.append(f"{d}: squeeze_watch calendar_front_symbol_live={ls!r} CONTRADICTS "
                            f"flow_calendar front_symbol_calendar={fs!r}")
            if sw.get("frozen_front_expired") and ls and ls == sw.get("calendar_front_symbol"):
                hard.append(f"{d}: squeeze_watch declares frozen_front_expired but its '_live' symbol "
                            f"is still {ls!r}, the expired contract - self-contradictory in one block")

        # S110 audit f1 THE TWO-TAPE SPLIT. A sixth face of the enemy: HALF a block computed on a
        # different tape than the other half, sitting side by side under one source_store label. On
        # g23 20260717 the session counts (n_trades 39,965 / volume 100,272) came from the LEG while
        # the entire flow/phase/b-family came from a degraded cont store carrying ~44% of the tape -
        # and the S109 b_share identity PASSED, because the family is internally consistent within
        # its own (wrong) tape. Root cause is audit f2: flow_read's leg context was never set, so its
        # leg path was dead code and the cont max-count fallback served everything; it matched the
        # leg on other days only because the leg tape happened to also be the biggest cont store.
        # The reconciliation is free and exact: phases are thirds of ONE tape, so their sums ARE the
        # session totals. Measured across all 17 committed group states: 46 scopes sum exactly, the
        # 2 defective scopes (n 0.493, vol 0.438) are the only failures. HARD - the family feeds
        # SIGN plays and the big-print pair straddled 0.50 across the two tapes.
        for blk in ("tape_conditions",):
            tc0 = state[d].get(blk) or {}
            for scope, tag in ((tc0, blk), (tc0.get("prior_full_session") or {}, blk + "/prior_full_session")):
                if not isinstance(scope, dict):
                    continue
                for plist, tot, nm in (("phase_n_trades", "n_trades", "trades"),
                                       ("phase_volume_lots", "volume_lots", "lots")):
                    pv, tv = scope.get(plist), scope.get(tot)
                    if (isinstance(pv, list) and pv and all(isinstance(x, (int, float)) for x in pv)
                            and isinstance(tv, (int, float))):
                        if sum(pv) != tv:
                            hard.append(
                                f"{d}: {tag} sum({plist})={sum(pv):,} != {tot}={tv:,} "
                                f"(ratio {sum(pv)/tv:.3f}) on session {scope.get('session')} - the "
                                f"flow family and the session counts describe TWO DIFFERENT TAPES; "
                                f"every b_share/phase/signed-flow field here is off-tape. Do not "
                                f"reason over the flow family (S110 audit f1/f2).")

        # S110 audit f4 CONSENSUS FRESHNESS. The survey store died after the 07-09 print and the
        # state kept serving that print as last_print for eight days - while the SAME day's storage
        # block correctly carried the 07-16 print. Two blocks, one fact, two answers: the one
        # post-print day of the second week evaluates the WRONG print's age and surprise. The
        # reconciliation: once storage knows a print, the consensus block may not claim an older one
        # as "last". Measured: fires on exactly 1 of 99 day-blocks with both fields present (g23
        # 20260717); a repaired block nulls last_print with a *_basis and is skipped here.
        st0, sc0 = state[d].get("storage") or {}, state[d].get("storage_consensus") or {}
        lp = sc0.get("last_print") if isinstance(sc0, dict) else None
        if isinstance(st0, dict) and isinstance(lp, dict):
            a, pdt = st0.get("as_of"), lp.get("print_date")
            if isinstance(a, str) and isinstance(pdt, str) and a > pdt:
                hard.append(
                    f"{d}: storage.as_of {a} POSTDATES storage_consensus.last_print.print_date {pdt} "
                    f"- storage knows a print the consensus block still calls future. last_print "
                    f"affirmatively misdescribes which print is last; age/surprise reads off it are "
                    f"about the wrong print (S110 audit f4).")

        # S110 audit f5 STRIKE SCALE. options_surface serves strikes in units exactly 10x below the
        # $/MMBtu convention of every other price field (0.35 on a 3.2 settle), undeclared, in every
        # group that carries the block (g12-g23) - a standing feed convention defect. The in-block
        # note directs distance-from-settle reads against contract_structure, which is $/MMBtu, so a
        # reader must silently infer a rescale (the G19 lesson forbids relying on that). Repaired
        # states carry strike_units; this fires only where the units are UNDECLARED and the scale is
        # out of family with the settle - median top-OI strike inside [0.4x, 2.5x] settle passes any
        # sane regime including the G11 squeeze.
        op = state[d].get("options_surface") or {}
        cs0 = state[d].get("contract_structure") or {}
        months = op.get("months") if isinstance(op, dict) else None
        settle = cs0.get("calendar_front_settle") if isinstance(cs0, dict) else None
        if (isinstance(months, list) and months and isinstance(settle, (int, float)) and settle
                and not op.get("strike_units")):
            stks = [t.get("strike") for m in months for t in (m.get("top5_oi_strikes") or [])
                    if isinstance(t.get("strike"), (int, float))]
            if stks:
                med = sorted(stks)[len(stks) // 2]
                if not (0.4 * settle <= med <= 2.5 * settle):
                    hard.append(
                        f"{d}: options_surface median top-OI strike {med} vs calendar_front_settle "
                        f"{settle} (ratio {med/settle:.3f}) with NO strike_units declared - the "
                        f"strikes are off the $/MMBtu convention by ~10x; any distance-from-settle "
                        f"read is nonsense (S110 audit f5).")

        # S110 audit f3 THE n0 ERA BREAK. vol_regime's n0 'prior session' store carries ~a fifth to
        # a quarter of the scored tape in the leg era (n0_prev_trades 2,594 vs the same session's
        # leg-reconciled 11,501 in g23; 1,835 vs 6,935 in g22) while the pre-June era reconciles
        # (g21: 0.978). The magnitude-band scalers read these levels. The values cannot be rebuilt
        # without the stores, so the disposition is DECLARE, not destroy: a state whose n0 family
        # breaks the ratio must say so in an n0_era_basis; declared = legitimate and skipped here.
        vr0, tc1 = state[d].get("vol_regime") or {}, state[d].get("tape_conditions") or {}
        if isinstance(vr0, dict) and isinstance(tc1, dict) and not vr0.get("n0_era_basis"):
            nd, nt0 = str(vr0.get("n0_prev_date", "")).replace("-", ""), vr0.get("n0_prev_trades")
            for scope in (tc1, tc1.get("prior_full_session") or {}):
                if not isinstance(scope, dict):
                    continue
                ses, nt1 = str(scope.get("session", "")).replace("-", ""), scope.get("n_trades")
                if (nd and nd == ses and isinstance(nt0, (int, float))
                        and isinstance(nt1, (int, float)) and nt1):
                    r0 = nt0 / nt1
                    if not (0.8 <= r0 <= 1.25):
                        hard.append(
                            f"{d}: vol_regime n0_prev_trades {nt0:,} vs the same session's tape "
                            f"n_trades {nt1:,} (ratio {r0:.3f}) with no n0_era_basis declared - the "
                            f"n0 volatility basis is off the scored tape and the magnitude-band "
                            f"scalers reading it do not know (S110 audit f3).")

    return {"hard": hard, "soft": soft, "days": len(days)}


def report(state: dict, label: str = "") -> dict:
    r = audit(state)
    tag = f" {label}" if label else ""
    print(f"[state_health{tag}] {r['days']} days | {len(r['hard'])} hard, {len(r['soft'])} soft")
    for m in r["hard"]:
        print(f"  HARD  {m}")
    for m in sorted(set(r["soft"]))[:12]:
        print(f"  soft  {m}")
    if not r["hard"]:
        print("  PASS - every required block carries content on every day")
    return r


GUARD_ROSTER = (
    "block-emptiness (declared-only exemptions)", "tape_conditions required fields",
    "flow_read_error surfacing", "weather provisional-fetch-tail",
    "b_share identity b == b2*(1-u) [S109 #9]", "squeeze_watch _live vs flow_calendar [S109 #10]",
    "phase-sum == session totals [S110 f1]", "storage-vs-consensus freshness [S110 f4]",
    "strike scale vs calendar_front_settle when units undeclared [S110 f5]",
    "vol_regime n0 era vs same-session tape when undeclared [S110 f3]",
)


def write_manifest(state: dict, gid: str) -> str:
    """S110 (turnaround memo 1.2): the INCOMING-INSPECTION CERTIFICATE. A per-group record of what
    was checked, by which guard roster, with what verdict - stapled into the batch record so
    'it passed inspection' has a dated, versioned artifact instead of a memory."""
    import json
    import os
    import time
    r = audit(state)
    out = {"group": gid, "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "guards": list(GUARD_ROSTER), "days": r["days"],
           "hard": r["hard"], "soft": sorted(set(r["soft"])),
           "verdict": "PASS" if not r["hard"] else "FAIL"}
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "forecasts",
                     f"g{gid.lstrip('g')}_inspection.json")
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    return p


if __name__ == "__main__":
    import json
    import os
    import sys as _sys
    _here = os.path.dirname(os.path.abspath(__file__))
    for _gid in _sys.argv[1:] or ():
        _n = _gid.lstrip("g")
        _sp = os.path.join(_here, "renders", "ng_refine_s95", f"grp{_n}_state.json")
        _st = json.load(open(_sp, encoding="utf-8"))
        report(_st, f"g{_n}")
        print("  manifest ->", os.path.relpath(write_manifest(_st, f"g{_n}"), _here))
    if not _sys.argv[1:]:
        print("usage: python state_health.py g22 [g23 ...] - report + write inspection manifest")


def assert_healthy(state: dict, label: str = "") -> None:
    r = report(state, label)
    if r["hard"]:
        raise SystemExit(
            f"[state_health] REFUSING to stage{' ' + label if label else ''}: "
            f"{len(r['hard'])} block(s) empty. A silently empty block reads exactly like a masked "
            f"one and gets reasoned over as if the market had no data. Fix the store, or declare "
            f"the block optional in state_health.py - do not run past this."
        )


if __name__ == "__main__":
    import json, os, sys
    HERE = os.path.dirname(os.path.abspath(__file__))
    RD = os.path.join(HERE, "renders", "ng_refine_s95")
    for gid in (sys.argv[1:] or ["g19", "g20", "g21", "g22", "g23"]):
        p = os.path.join(RD, f"grp{gid[1:]}_state.json")
        if not os.path.exists(p):
            print(f"[state_health {gid}] no state file"); continue
        report(json.load(open(p)), gid)
        print()
