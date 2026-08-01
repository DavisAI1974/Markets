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
s3 = boto3.client("s3", "us-east-2")


def log(m): print(f"[stage {m}]", flush=True)


def _dl(key, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return "skip"
    try:
        s3.download_file(BUCKET, key, dest); return "ok"
    except Exception as e:
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


def stage(gid):
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
    out_state = os.path.join(RENDER_DIR, f"grp{gid[1:]}_state.json")
    subprocess.run([sys.executable, os.path.join(HERE, "forecast_harness.py"), "decision-state",
                    "--days", ",".join(days), "--mask-after", g["mask_after"], "--out", out_state],
                   check=True, stdout=subprocess.DEVNULL)
    log(f"{gid} state -> {os.path.relpath(out_state, HERE)}")
    # S107: COMPLETENESS ASSERTION. Six times in one session a block was silently empty and read
    # downstream exactly like a deliberate mask. Refuse to hand a specialist a state with a hole in it.
    import state_health
    state_health.assert_healthy(json.load(open(out_state)), gid)
    # 4. actual + 5. MBO evidence (config anchor now set in-process)
    import importlib
    import group_actual, group_mbo_engine
    importlib.reload(group_actual); importlib.reload(group_mbo_engine)
    act = group_actual.build(gid)
    json.dump(act, open(os.path.join(RENDER_DIR, f"{gid}_actual.json"), "w"))
    ev = group_mbo_engine.build(gid)
    log(f"{gid} actual (ends {act['days'][-1]['cum_from_anchor_usd']:+d}) + mbo evidence ({len(ev)} days) built")
    log(f"{gid} STAGED - anchor {anchor}, {len(days)} days, seam {g.get('seam')}")


if __name__ == "__main__":
    for gid in sys.argv[1:]:
        stage(gid)
