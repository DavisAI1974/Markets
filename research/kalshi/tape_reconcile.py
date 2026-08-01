"""tape_reconcile.py - assert tape_conditions is measuring THE CONTRACT WE ARE FORECASTING (S108).

HOLE #8, and the hardest one yet. Found by C during the G21 refine, proved independently by E, verified
against the leg files by the session lead.

THE DEFECT. `_tape_day_stats` (and `flow_read._load_trades`) select their source by "whichever
continuous store has MORE trades". Before a roll that is the front contract and is correct. AFTER a
roll, volume migrates to the deferred contract - so the selector silently switches instrument, while
the group is still forecasting the front leg. G21:

    session   NGN26 leg (scored)   tape_conditions served   ratio
    20260610              43572                    43572     1.00
    20260611              47040                    47040     1.00
    20260615              34221                     6262     0.18
    20260616              37477                     6923     0.18
    20260617              44127                    18317     0.42
    20260618              37378                    22490     0.60

Served `session_signed_flow` was SIGN-FLIPPED on 0615 and 0617 and destroyed on 0618 (-1 against a real
-3,670). `source_store` said `nymex_cont_n1` outright on 0618/0619 - the deferred leg - while
`flow_calendar` and the scored leg were NGN26 throughout.

WHY IT IS THE HARDEST OF THE EIGHT. The six S107 holes were EMPTY blocks. #7 (the nws_temp fetch tail)
was a WRONG VALUE. This one is OFF-INSTRUMENT: the block is fully populated, internally consistent, and
recomputes coherently off a different contract. `state_health` asserts PRESENCE and cannot see it. It
even manufactured a false mechanism - C's blind-run "week-2 delivery-window thinning", complete with
three corroborating markers (spread doubling, unsided fraction tripling, leg_count preserved), every one
of which is also what an off-instrument read looks like. D independently "verified" the same artifact as
a real liquidity migration by checking internal consistency. Consistency was never the test.

THE COST. tape_conditions is the blind's ONLY open-time flow channel and is declared `never_masked`. The
doctrine says the blind's one deliberate mask is the PRICE CURVE. On four of G21's ten days it was also
handed a wrong-instrument, sign-flipped flow read - an undeclared handicap on its primary input.

THE TEST. Presence is not enough and consistency is not enough; only RECONCILIATION against an
independent measurement of the same session on the SAME instrument settles it. That is what this does.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
LEG_DIR = os.path.join(REPO, "data", "ng_mbo_g17")

TOL_LO, TOL_HI = 0.95, 1.05


def leg_path(store: str, ymd: str):
    p = os.path.join(LEG_DIR, f"{store}_{ymd}.dbn.zst")
    return p if os.path.exists(p) else None


def load_leg_trades(store: str, ymd: str):
    """(ts_seconds, price, size, side) for the SCORED contract, from its per-contract leg.

    S108 hole #8 correction. The continuous stores select by max trade count and therefore follow the
    volume to the DEFERRED contract after a roll; worse, on the affected G21/G23 sessions they simply do
    not contain the tape at all (n0 6,262 and n1 5,554 against a leg of 34,221). Selecting better between
    two short stores cannot work - the read has to come from the leg. Side is mapped exactly as the
    continuous reader maps it, so the two paths produce the same quantity.
    """
    p = leg_path(store, ymd)
    if p is None:
        return None
    try:
        import databento as db
    except Exception:
        return None
    ts, px, sz, sd = [], [], [], []
    for r in db.DBNStore.from_file(p):
        if type(r).__name__ != "MBOMsg" or str(getattr(r.action, "value", r.action)) != "T":
            continue
        pr = r.price
        if pr in (None, 9223372036854775807, -9223372036854775808):
            continue
        s = str(getattr(r.side, "value", r.side))
        ts.append(int(r.ts_event) / 1e9)
        px.append(pr / 1e9)
        sz.append(float(getattr(r, "size", 0) or 0))
        sd.append(1 if s in ("B", "Bid") else (-1 if s in ("A", "Ask") else 0))
    if not ts:
        return None
    o = sorted(range(len(ts)), key=lambda i: ts[i])
    return [ts[i] for i in o], [px[i] for i in o], [sz[i] for i in o], [sd[i] for i in o]


def leg_trade_count(store: str, ymd: str):
    """Trades in the per-contract leg - the instrument actually being forecast and scored."""
    p = os.path.join(LEG_DIR, f"{store}_{ymd}.dbn.zst")
    if not os.path.exists(p):
        return None
    try:
        import databento as db
    except Exception:
        return None
    n = 0
    for r in db.DBNStore.from_file(p):
        if type(r).__name__ == "MBOMsg" and str(getattr(r.action, "value", r.action)) == "T":
            n += 1
    return n


def reconcile(gid: str, state: dict, verbose: bool = True) -> list[str]:
    """Compare each day's served tape_conditions trade count against the leg it claims to describe.

    Returns a list of failures. A session legitimately absent from the leg store (a Sunday reopen stub,
    a day outside the pulled range) is SKIPPED rather than failed - the check must not manufacture a
    hole of its own, which is the failure mode this whole family keeps producing.
    """
    import group_config as gc
    fails = []
    days = [d for d in gc.GROUPS[gid]["days"] if d in state]
    for d in days:
        tc = state[d].get("tape_conditions") or {}
        served, sess = tc.get("n_trades"), tc.get("session")
        if not served or not sess:
            continue
        legn = leg_trade_count(gc.leg_for(gid, sess if sess in gc.GROUPS[gid]["days"] else d), sess)
        if legn is None or legn == 0:
            continue                      # not pullable on this leg - not a failure, just unverifiable
        ratio = served / legn
        if not (TOL_LO <= ratio <= TOL_HI):
            fails.append(
                f"{d}: tape_conditions describes session {sess} with {served:,} trades but the SCORED "
                f"LEG has {legn:,} (ratio {ratio:.2f}) - source_store={tc.get('source_store')}. The flow "
                f"read is OFF-INSTRUMENT or partial; signed flow may be sign-flipped. This is the blind's "
                f"only open-time flow channel and it is declared never_masked.")
        elif verbose:
            print(f"[reconcile] {d}: session {sess} {served:,} vs leg {legn:,} (ratio {ratio:.2f}) OK")
    return fails


def assert_reconciled(gid: str, state: dict) -> None:
    fails = reconcile(gid, state, verbose=False)
    if fails:
        raise SystemExit(
            f"TAPE RECONCILIATION FAILED for {gid} - {len(fails)} session(s) off-instrument:\n  "
            + "\n  ".join(fails)
            + "\n\nDo NOT route around this. tape_conditions must measure the contract being forecast."
              "\nFix the store selection or pull the correct leg, then restage.")
    print(f"[reconcile] {gid}: tape_conditions reconciles to the scored leg on every verifiable day")


if __name__ == "__main__":
    import json
    sys.path.insert(0, HERE)
    RD = os.path.join(HERE, "renders", "ng_refine_s95")
    for gid in (sys.argv[1:] or ["g20", "g21", "g22", "g23"]):
        p = os.path.join(RD, f"grp{gid[1:]}_state.json")
        if not os.path.exists(p):
            continue
        print(f"\n=== {gid} ===")
        for f in reconcile(gid, json.load(open(p))):
            print("  FAIL ", f)
