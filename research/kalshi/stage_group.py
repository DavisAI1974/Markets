"""stage_group.py - ONE-COMMAND staging so a group is completely ready (S105):
    env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY <creds...> python research/kalshi/stage_group.py g18

Does everything: resolve the chained anchor, pull the per-contract legs + prior-session tape from S3,
build the masked decision-state, the two-leg actual, and the MBO causal evidence. Idempotent (skips
files already local). Leaves the group turnkey for a blind/refine run. Reads group_config; a new group
is a config entry, not new code.
"""
import os, sys, subprocess, json
import boto3
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import group_config as gc
import verify_gold
verify_gold.assert_gold_intact()   # the concrete wall - no staging on a violated refine gold vault

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
LEG_DIR = os.path.join(REPO, "data", "ng_mbo_g17")
RENDER_DIR = os.path.join(HERE, "renders", "ng_refine_s95")
BUCKET = "bento-568968024170-us-east-2-an"
# S115 (audit D1-07): creds.aws_client, never a bare boto3.client - the bare client picks up the
# container's placeholder injection and every download then reports as a per-file "miss".
import creds
s3 = creds.aws_client("s3", "us-east-2")

# Exception names that mean THE CREDENTIALS ARE BROKEN, not "this one file is absent". Reporting
# an auth failure as a per-file miss is how a whole stage silently degrades into empty blocks.
_AUTH_ERR_CODES = ("InvalidClientTokenId", "InvalidAccessKeyId", "SignatureDoesNotMatch",
                   "AccessDenied", "ExpiredToken", "AuthFailure")


def log(m): print(f"[stage {m}]", flush=True)


def _dl(key, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return "skip"
    try:
        s3.download_file(BUCKET, key, dest); return "ok"
    except Exception as e:
        # S115 (audit D1-07): an auth/credential failure fails the whole stage LOUDLY - it is not
        # a property of one key, and 400 quiet "miss" lines would stage a group on an empty plane.
        name = type(e).__name__
        blob = f"{name}: {e}"
        if name == "NoCredentialsError" or any(c in blob for c in _AUTH_ERR_CODES):
            raise SystemExit(
                f"[stage] S3 AUTH FAILURE on {key}: {blob}\n"
                f"[stage] This is a credential problem, not a missing file - fix keys "
                f"(creds.py status) before staging. Refusing to continue and record misses.")
        return f"miss ({e})"


def resolve_anchor(gid):
    g = gc.GROUPS[gid]
    if g["anchor"] is not None:
        return g["anchor"]
    prev = f"g{int(gid[1:]) - 1}"
    apath = os.path.join(RENDER_DIR, f"{prev}_actual.json")
    if not os.path.exists(apath):
        raise SystemExit(f"{gid}: anchor is None and {prev}_actual.json not built - stage {prev} first.")
    close = json.load(open(apath))["days"][-1]["close"]
    gc.set_anchor(gid, close)
    log(f"{gid} anchor resolved from {prev} close = {close}")
    return close


def stage(gid, suffix=""):
    """suffix: REHEARSAL redirect (NC-4). Writes grp<N>_state<suffix>.json and <gid>_actual<suffix>.json
    instead of the canonical names, so a re-stage can be DIFFED against the committed artifacts rather
    than replacing them. group_config lookup still uses the real gid. Downstream steps that write their
    own canonical files (mbo evidence, exit states) are SKIPPED when a suffix is given, and that is
    stated in the log rather than silently done - a partial rehearsal that pretends to be a full one is
    the failure this whole exercise exists to prevent."""
    g = gc.GROUPS[gid]; days = g["days"]
    anchor = resolve_anchor(gid)
    os.makedirs(LEG_DIR, exist_ok=True)
    # 1. per-contract legs (+ the anchor day, on the anchor's leg = the first day's pre-seam leg)
    anchor_day = g["anchor_date"]
    leg_days = [(gc.leg_for(gid, d), d) for d in days]
    # anchor day sits on the first day's leg (or pre leg)
    first_leg = leg_days[0][0]
    leg_days = [(first_leg, anchor_day)] + leg_days
    okc = 0
    for store, d in leg_days:
        r = _dl(f"nymex/{store}/NG_{d}.dbn.zst", os.path.join(LEG_DIR, f"{store}_{d}.dbn.zst"))
        okc += (r in ("ok", "skip"))
        if r.startswith("miss"):
            log(f"  LEG MISS {store} {d}: {r}")
    log(f"{gid} legs: {okc}/{len(leg_days)} local")
    # 2. prior-session tape (n0/n1) for state's tape_conditions - the mask day + block days minus last
    import datetime
    tape_days = [anchor_day] + days[:-1]
    for storet in ("nymex_cont_n0", "nymex_cont_n1", "ng_l1"):   # ng_l1 = the L1 book flow (data doctrine)
        dd = os.path.join(REPO, "data", storet); os.makedirs(dd, exist_ok=True)
        for d in tape_days:
            _dl(f"nymex/{storet}/NG_{d}.jsonl.gz", os.path.join(dd, f"NG_{d}.jsonl.gz"))
    log(f"{gid} prior tape + L1 book pulled")
    # 3. masked decision-state
    out_state = os.path.join(RENDER_DIR, f"grp{gid[1:]}_state{suffix}.json")
    subprocess.run([sys.executable, os.path.join(HERE, "forecast_harness.py"), "decision-state",
                    "--days", ",".join(days), "--mask-after", g["mask_after"], "--out", out_state,
                    "--group", gid],
                   check=True, stdout=subprocess.DEVNULL)
    log(f"{gid} state -> {os.path.relpath(out_state, HERE)}")
    # S107: COMPLETENESS ASSERTION. Six times in one session a block was silently empty and read
    # downstream exactly like a deliberate mask. Refuse to hand a specialist a state with a hole in it.
    import state_health
    _st = json.load(open(out_state))
    state_health.assert_healthy(_st, gid)
    # S108 HOLE #8: presence is not enough and internal consistency is not enough. tape_conditions
    # selects its source by "whichever continuous store has more trades", so after a roll it silently
    # switches to the DEFERRED contract while the group still forecasts the front leg. On G21 that
    # served 18-60% of the real tape with signed flow SIGN-FLIPPED on the blind's only open-time flow
    # channel - a channel declared never_masked, on days the doctrine says are masked on price ALONE.
    # state_health cannot catch it (nothing is empty) and consistency checks cannot either (D verified
    # the artifact as a real liquidity migration by checking exactly that). Only RECONCILIATION against
    # an independent count of the same session on the SAME instrument settles it.
    import tape_reconcile
    tape_reconcile.assert_reconciled(gid, _st)
    # 4. actual + 5. MBO evidence (config anchor now set in-process)
    import importlib
    import group_actual, group_mbo_engine
    importlib.reload(group_actual); importlib.reload(group_mbo_engine)
    act = group_actual.build(gid)
    json.dump(act, open(os.path.join(RENDER_DIR, f"{gid}_actual{suffix}.json"), "w"))
    if suffix:
        log(f"{gid} SUFFIXED RUN ({suffix}): skipping mbo_evidence and exit_states - they write "
            f"canonical names with no redirect. State + actual only.")
        log(f"{gid} STAGED{suffix} - anchor {anchor}, {len(days)} days")
        return
    ev = group_mbo_engine.build(gid)
    log(f"{gid} actual (ends {act['days'][-1]['cum_from_anchor_usd']:+d}) + mbo evidence ({len(ev)} days) built")
    # 6. S108: precompute the round-2 HE24->HE1 exit states while the legs are local. This was the LAST
    # thing in a staged group's run cycle that reached into data/ - everything else (round-1
    # specialists, both coordinators, the round-2 re-run) reads committed artifacts only. Staging is
    # the one step that legitimately needs the data plane and the credentials, so the read belongs
    # here, not mid-run in a later session that would otherwise have to restore 463MB to get 146MB of
    # legs for one function.
    import group_he24_he1_handoff as hh
    importlib.reload(hh)
    hh.precompute_exit_states(gid)
    log(f"{gid} STAGED - anchor {anchor}, {len(days)} days, seam {g.get('seam')}")


if __name__ == "__main__":
    _a = sys.argv[1:]
    _sfx = ""
    if "--suffix" in _a:
        _i = _a.index("--suffix"); _sfx = _a[_i + 1]; _a = _a[:_i] + _a[_i + 2:]
    for gid in _a:
        stage(gid, _sfx)
