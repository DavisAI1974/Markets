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
