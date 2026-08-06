"""decision_state adapter - one call into the signal core's forecast_harness (read-only import;
the module is never edited). Returns the 23-block daily state plus availability accounting so
the UI can honestly badge which blocks are fed and which await a store pull."""
from __future__ import annotations

import os
import sys
import traceback

from . import paths

_BLOCK_KEYS = [
    "storage", "storage_regional", "storage_consensus", "storage_vintage", "ngwu_balance",
    "steo_vintage", "cot", "contract_structure", "squeeze_watch", "vol_regime", "cash_basis",
    "flow_calendar", "solar", "nuclear_outages", "grid_stack", "options_surface", "weather",
    "weather_forecast", "weather_forecast_cycle", "freeze_risk", "model_disagreement", "holiday",
]


def _harness():
    if paths.KALSHI_RESEARCH not in sys.path:
        sys.path.insert(0, paths.KALSHI_RESEARCH)
    import forecast_harness
    return forecast_harness


def _blockwise_state(fh, day8: str) -> tuple[dict, dict]:
    """Per-block fallback mirroring decision_state's assembly, each block individually
    guarded so a missing store degrades to None (awaiting data) instead of failing the
    whole day. Uses the harness's OWN block functions read-only - no logic is re-derived
    here; when the canonical decision_state call succeeds it is preferred verbatim."""
    import datetime as _dt
    iso = f"{day8[:4]}-{day8[4:6]}-{day8[6:]}"
    errors: dict[str, str] = {}

    def safe(name, fn, *a):
        try:
            return fn(*a)
        except Exception as e:
            errors[name] = f"{type(e).__name__}: {e}"
            return None

    state: dict = {}
    state["dow"] = fh.DOW[_dt.date(int(day8[:4]), int(day8[4:6]), int(day8[6:])).weekday()]
    surp = safe("stor_surprise_load",
                lambda i: fh._load_json("eia_surprise.json").get("KXNATGASD", {}), iso)
    sv = None
    if surp:
        past = sorted(ri for ri in surp if ri < iso)
        sv = surp[past[-1]]["surprise"] if past else None
    state["stor_surprise"] = round(sv, 1) if sv is not None else None
    state["stor_surprise_sign"] = ("above" if sv > 0 else "below") if sv is not None else None
    cs = safe("contract_structure", fh._contract_structure_block, iso)

    def _regime():
        import forward_curve as fc
        cv = fc.load("NG")
        cr = fc.curve_asof(cv, iso)
        return cr[1]["regime"] if cr else "unknown"
    regime = safe("curve_regime", lambda i: _regime(), iso) or "unknown"
    if regime == "unknown" and cs and cs.get("curve_regime"):
        regime = cs["curve_regime"]
    state["curve_regime"] = regime
    stor = safe("storage_series", lambda i: fh._storage_series(), iso)
    state["storage"] = safe("storage", fh._storage_asof, iso, stor) if stor else None
    wx = safe("weather_load", lambda i: fh._load_json("nws_temp/gw_degree_days.json"), iso)
    state["weather"] = safe("weather", fh._weather_asof, iso, wx) if wx else None
    mos = None
    if os.path.exists(getattr(fh, "MOS_ASOF", "")):
        import json as _json
        mos = safe("mos_load", lambda i: _json.load(open(fh.MOS_ASOF)), iso)
    state["weather_forecast"] = safe("weather_forecast", fh._forecast_weather_asof, iso, mos) if mos else None
    for key, fn in [
        ("storage_regional", fh._storage_regional_block),
        ("storage_consensus", fh._storage_consensus_block),
        ("storage_vintage", fh._storage_vintage_block),
        ("ngwu_balance", fh._ngwu_block),
        ("steo_vintage", fh._steo_vintage_block),
        ("cot", fh._cot_asof_block),
        ("vol_regime", fh._vol_regime_block),
        ("cash_basis", fh._cash_basis_block),
        ("flow_calendar", fh._flow_calendar_block),
        ("solar", fh._solar_block),
        ("nuclear_outages", fh._nuclear_outages_block),
        ("grid_stack", fh._grid_stack_block),
        ("options_surface", fh._options_surface_block),
        ("weather_forecast_cycle", fh._mos_cycle_block),
        ("freeze_risk", fh._freeze_risk_block),
        ("model_disagreement", fh._model_disagreement_block),
        ("holiday", fh._holiday_asof),
    ]:
        state[key] = safe(key, fn, iso)
    state["contract_structure"] = cs
    state["squeeze_watch"] = safe("squeeze_watch", fh._squeeze_watch, cs)
    return state, errors


def state_for_day(day8: str) -> dict:
    """day8 = YYYYMMDD. Runs with CWD at repo root (the harness reads data/ relative paths).
    Canonical decision_state first; blockwise guarded fallback when stores are missing."""
    cwd = os.getcwd()
    mode = "decision_state"
    block_errors: dict = {}
    try:
        os.chdir(paths.REPO)
        fh = _harness()
        try:
            out = fh.decision_state([day8])
            day_state = out.get(day8, {})
            clock = out.get("_information_clock")
        except Exception:
            mode = "blockwise_fallback"
            day_state, block_errors = _blockwise_state(fh, day8)
            clock = getattr(fh, "INFORMATION_CLOCK", None)
    except Exception:
        return {"available": False, "day": day8, "error": traceback.format_exc(limit=3)}
    finally:
        os.chdir(cwd)
    fed = [k for k in _BLOCK_KEYS if day_state.get(k) is not None]
    empty = [k for k in _BLOCK_KEYS if day_state.get(k) is None]
    scalar_fed = [k for k in ("dow", "stor_surprise", "curve_regime")
                  if day_state.get(k) not in (None, "unknown")]
    return {
        "available": True,
        "day": day8,
        "mode": mode,
        "block_errors": block_errors or None,
        "information_clock": clock,
        "state": day_state,
        "blocks_fed": fed,
        "blocks_awaiting_data": empty,
        "n_blocks_fed": len(fed),
        "n_blocks_total": len(_BLOCK_KEYS),
        "scalars_fed": scalar_fed,
        "note": ("blocks_awaiting_data = the harness returned None: the underlying store is not "
                 "in the local data/ cache (platform_sync pull) OR genuinely has no coverage for "
                 "this day (missing==None doctrine - absence is shown, never interpolated)"),
    }
