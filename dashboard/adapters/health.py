"""Data-plane health: what is REAL right now, honestly. This is the source for every
LIVE DATA / AWAITING DATA / SIMULATED badge in the UI - no invented certainty (rule 4).

Execution-side truths carried as constants (from LIVE_TELEMETRY_S100 / the handoff):
the live gateway is unreachable from cloud containers; live processes run on AWS boxes.
The dashboard never claims a live feed it does not have."""
from __future__ import annotations

import os

from . import brain, lagmap, market, paths

STORES = [
    # (label, local path relative to repo, s3 prefix, what it feeds)
    ("eia_surprise", "data/eia_surprise.json", "eia/", "storage surprise + running storage story"),
    ("nws degree-days", "data/nws_temp/gw_degree_days.json", "weather/", "realized weather regime"),
    ("MOS as-of", "data/mos_asof", "weather/", "forecast weather (D-1 evening as-of)"),
    ("MOS cycle", "data/mos_cycles", "weather/", "cycle-level MOS (feed A ph1)"),
    ("freeze risk", "data/freeze_risk", "weather/", "basin freeze-off minima (feed E)"),
    ("forward curve", "data/nymex_curve/NG_curve.json", "nymex/", "curve regime"),
    ("COT", "data/cot", "cot/", "positioning (futures + combined + ICE HH)"),
    ("storage regional", "data/storage_regional", "eia/", "5-region + salt split"),
    ("storage consensus", "data/storage_consensus", "consensus/", "survey consensus"),
    ("storage vintage", "data/storage_vintage", "eia/", "as-printed vintages"),
    ("STEO vintages", "data/steo_vintage", "eia/", "monthly as-of balance"),
    ("NGWU balance", "data/ngwu", "eia/", "free weekly balance (levels dead 2025-09-24)"),
    ("contract structure", "data/contract_structure", "nymex/contract_structure/", "expiries + calendar-front squeeze view"),
    ("vol regime", "data/vol_regime", "nymex/", "magnitude conditioner"),
    ("cash basis", "data/cash_basis", "cash/", "physical delivery stress"),
    ("flow calendar", "data/flow_calendar", "calendar/", "scheduled flows"),
    ("nuclear outages", "data/nuclear_outages", "grid/", "feed R arm 1"),
    ("grid stack", "data/grid_stack", "grid/", "EIA-930 loads + fuel mix (feed Q)"),
    ("options surface", "data/options_surface", "options/", "OI pin map (feed I ph i)"),
    ("model disagreement", "data/model_disagreement", "weather/", "uncertainty conditioner"),
    ("lag map (feed M)", "data/kalshi_echo/lag_map.jsonl", "kalshi_echo/", "per-cell execution windows"),
    ("kalshi raw", "data/kalshi", "kalshi/", "trades + 1m candles + definitions"),
    ("nymex cont tape", "data/nymex_cont", "nymex/nymex_cont/", "leader tape (pull deliberately - large)"),
]

LIVE_FEED_NOTE = ("live GLBX feed runs on AWS boxes only (raw-TCP blocked in cloud containers); "
                  "measured transit us-east-2 median 7.7ms (LIVE_TELEMETRY_S100). "
                  "This dashboard is a replay/as-of console until a live box streams to it.")


def _store_status(rel: str) -> dict:
    p = os.path.join(paths.REPO, rel)
    if os.path.isfile(p):
        return {"present": True, "bytes": os.path.getsize(p)}
    if os.path.isdir(p):
        n = sum(len(fs) for _, _, fs in os.walk(p))
        return {"present": n > 0, "files": n}
    return {"present": False}


def snapshot() -> dict:
    creds = paths.resolve_aws_creds()
    stores = []
    n_present = 0
    for label, rel, prefix, feeds in STORES:
        st = _store_status(rel)
        n_present += 1 if st["present"] else 0
        stores.append({"label": label, "local": rel, "s3_prefix": prefix,
                       "feeds": feeds, **st})
    return {
        "aws_credentials": {
            "resolved": creds is not None,
            "note": (None if creds else
                     "no real key pair on this container (placeholder proxy vars ignored); "
                     "drop the pair into scratchpad/aws.env or ~/.aws/credentials"),
        },
        "stores": stores,
        "stores_present": n_present,
        "stores_total": len(STORES),
        "brain": {"present": os.path.exists(paths.BRAIN_PATH),
                  "version": brain.summary().get("version")},
        "lag_map_present": lagmap.available(),
        "kalshi_raw_present": market.kalshi_available(),
        "nymex_days_local": len(market.nymex_available_days()),
        "live_feed": {"reachable_from_here": False, "note": LIVE_FEED_NOTE},
        "execution": {"exists": False,
                      "note": "no executor is wired anywhere yet; every order/fill/P&L panel "
                              "is SIMULATED by design until the executor lane is built (last)"},
    }
