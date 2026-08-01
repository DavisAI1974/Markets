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
