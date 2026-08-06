"""restore_substrate.py - rebuild a fresh container's local data plane in ONE command (S107).

    env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY python research/kalshi/restore_substrate.py
    ... --group g21          also pull that group's MBO legs + prior tape (or just run stage_group)

WHY THIS EXISTS. git carries CODE and the committed state/forecast artifacts; S3 carries DATA; the
container's data/ is DISPOSABLE and does not survive the session. S107 opened with an empty data/
and burned real time rediscovering the prefix -> local-path mapping, and two of those mappings are
NOT the obvious one:

  * weather/nws_temp/  ->  data/nws_temp          NOT data/weather/nws_temp. forecast_harness reads
                                                  _load_json("nws_temp/gw_degree_days.json"), i.e.
                                                  data/nws_temp/. Pulling weather/ wholesale puts it
                                                  one level too deep and the `weather` block comes
                                                  back EMPTY on every day, silently. That is the
                                                  sixth silent-empty of S107.
  * consensus/         ->  data/storage_consensus  (prefix and local name differ)
  * eia/               ->  data/  as eia_surprise.json (a FILE, not a directory)

Everything here is a pull. Nothing is pushed, nothing is deleted.

AFTER this runs, vol_regime must be REBUILT from the restored tape (its store is derived, not
stored): python research/kalshi/vol_regime.py --build. This script does it for you.
"""
from __future__ import annotations
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
BUCKET = "bento-568968024170-us-east-2-an"
REGION = "us-east-2"

# (s3 prefix, local dest relative to repo). Order is cheapest-first so a failure surfaces early.
PREFIXES = [
    ("cot/",                      "data/cot"),
    ("cot_combined/",             "data/cot_combined"),
    ("storage_regional/",         "data/storage_regional"),
    ("storage_vintage/",          "data/storage_vintage"),
    ("steo_vintage/",             "data/steo_vintage"),
    ("consensus/",                "data/storage_consensus"),      # name differs from the prefix
    ("cash_basis/",               "data/cash_basis"),
    ("grid_stack/",               "data/grid_stack"),
    ("model_disagreement/",       "data/model_disagreement"),
    # S114 / G-5 / A-51: the FORWARD renewables forcing store (wind + solar as an ensemble
    # density). REQUIRED_EVERY_DAY in state_health, so a session without it cannot stage a group -
    # which is deliberate: its absence was invisible for the whole walk until four g24 specialists
    # found it by hand.
    ("nymex/gefs_forcing/",       "data/gefs_forcing"),
    ("nuclear_outages/",          "data/nuclear_outages"),
    ("solar_calendar/",           "data/solar_calendar"),
    ("flow_calendar/",            "data/flow_calendar"),
    ("ngwu/",                     "data/ngwu"),
    ("nymex/contract_structure/", "data/contract_structure"),
    ("nymex/nymex_curve/",        "data/nymex_curve"),
    ("weather/nws_temp/",         "data/nws_temp"),               # THE PATH TRAP - see the docstring
    ("weather/mos_cycle/",        "data/weather/mos_cycle"),
    ("weather/mos_freeze/",       "data/weather/mos_freeze"),
    ("nymex/nymex_cont_n0/",      "data/nymex_cont_n0"),          # the tape vol_regime is built from
]

# Single objects that are not a whole prefix.
SINGLES = [
    ("eia/eia_surprise.json",        "data/eia_surprise.json"),
    ("options_ng/surface.json.gz",   "data/options_ng/surface.json.gz"),
    ("options_ng/iv_surface.json.gz", "data/options_ng/iv_surface.json.gz"),
]

# Deliberately NOT restored: options_ng/raw (GB-scale, only needed to REBUILD the surface),
# options_cl, options_ng_bridge, kalshi/, kalshi_echo/, deploy/, nymex raw MBO year-pull. Per-group
# MBO legs and prior tape come from stage_group, which pulls exactly the days a group needs.


def log(m):
    print(f"[restore] {m}", flush=True)


def main(groups):
    # S115: creds.aws_client, never bare boto3 - it resolves the pair from MARKETS_ env vars,
    # ~/.config/markets/env or legacy, and is immune to the container's placeholder injection.
    # A bare client here worked only when ~/.aws/credentials happened to exist.
    import creds
    s3 = creds.aws_client("s3", REGION)
    try:
        s3.list_objects_v2(Bucket=BUCKET, MaxKeys=1)
    except Exception as e:
        raise SystemExit(f"[restore] S3 unreachable - check creds ({type(e).__name__}: {e}). "
                         f"Run with `env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY` - the "
                         f"container injects PLACEHOLDER creds that override ~/.aws/credentials.")

    n_files = 0
    for prefix, dest in PREFIXES:
        full = os.path.join(REPO, dest)
        os.makedirs(full, exist_ok=True)
        got = kept = 0
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=prefix):
            for o in page.get("Contents", []):
                rel = o["Key"][len(prefix):]
                if not rel or rel.endswith("/"):
                    continue
                local = os.path.join(full, rel.replace("/", os.sep))
                os.makedirs(os.path.dirname(local), exist_ok=True)
                if os.path.exists(local) and os.path.getsize(local) == o["Size"]:
                    continue
                # S113 GUARD - DO NOT DESTROY A NEWER LOCAL BUILD. Greg: "Fix that problem asap."
                # MEASURED INSTANCE: grid_stack was rebuilt in-session with a live EIA key (2,774 days
                # through 2026-08-05, interchange added) and this loop silently replaced it with the
                # older S3 copy (last 2026-07-20, no interchange) on the next restore. The rebuild
                # printed success, the file reverted, and nothing said so - present, well-formed,
                # wrong vintage, which is this desk's signature defect applied to a whole store.
                # D34 says data/ is disposable and rebuilt from S3; the corollary nobody wrote down is
                # that a LOCAL rebuild is therefore TRANSIENT until it is pushed back. Until it is,
                # refuse to overwrite it and say so loudly rather than reverting work in silence.
                if os.path.exists(local):
                    import datetime as _dt
                    lm = o["LastModified"]
                    if lm.timestamp() < os.path.getmtime(local):
                        log(f"  KEPT LOCAL (newer than S3): {os.path.relpath(local, REPO)} "
                            f"- local {_dt.datetime.utcfromtimestamp(os.path.getmtime(local)):%Y-%m-%d %H:%M}Z "
                            f"vs S3 {lm:%Y-%m-%d %H:%M}Z. NOT overwritten. Push it to S3 or it dies "
                            f"with this container (platform_sync.py).")
                        kept += 1
                        continue
                s3.download_file(BUCKET, o["Key"], local)
                got += 1
        n_files += got
        log(f"{prefix:28} -> {dest:26} {got} new" + (f", {kept} KEPT LOCAL (newer)" if kept else ""))

    for key, dest in SINGLES:
        full = os.path.join(REPO, dest)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        if os.path.exists(full) and os.path.getsize(full) > 0:
            log(f"{key:28} -> {dest:26} already local")
            continue
        s3.download_file(BUCKET, key, full)
        n_files += 1
        log(f"{key:28} -> {dest:26} pulled")

    log(f"{n_files} file(s) fetched")

    # vol_regime is DERIVED from the tape, not stored. Its as-of span now follows the tape (S107),
    # so it must be rebuilt after the tape lands or every group past the old horizon reads None.
    log("rebuilding vol_regime from the restored tape ...")
    subprocess.run([sys.executable, os.path.join(HERE, "vol_regime.py"), "--build"], check=True)

    for gid in groups:
        log(f"staging {gid} ...")
        subprocess.run([sys.executable, os.path.join(HERE, "stage_group.py"), gid], check=True)

    log("DONE. Verify with: python research/kalshi/state_health.py")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    gs = []
    if "--group" in sys.argv:
        gs = args
    main(gs)
