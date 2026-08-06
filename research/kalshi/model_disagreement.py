"""model_disagreement.py -- FEED C (DATA_GATE_S98): MODEL DISAGREEMENT as a forecast-uncertainty proxy.

WHAT THIS IS
------------
An INPUT, not a thesis (gate doctrine, Greg S97): the market prices UNCERTAINTY, not just the central
case. G11's 0125/0126 whipsaw happened on a wobbling forecast -- the composite MOS run-delta for target
2026-01-30 cut -2.315 gw-HDD (as-of 01-25) then re-added +3.197 (as-of 01-26) at the same target within
two evening batches. This feed puts two state variables in front of the agent so a horizon like that is
visible as CONTESTED:

  1. DISAGREEMENT  -- GFS-MOS (MAV) vs NAM-MOS (MET), horizon-MATCHED only: per matched horizon the
     gas-weighted HDD from each model, the signed spread (MAV minus MET) and its absolute value,
     computed on the COMMON metro set only (a coverage difference can never masquerade as disagreement).
     MET is short-range, so the overlap set is limited (empirically D+0..D+2 under the D-1-evening
     as-of); horizons with no overlap are None and named -- never zero, never imputed.
  2. RUN STABILITY -- per MODEL (GFS, NAM, and MEX = GFS-extended), the run-to-run change at each
     horizon: this-evening's batch minus the prior evening's batch for the SAME target day, restricted
     to one model. The existing mos_asof_index run_delta covers the gas-weighted COMPOSITE (its model
     preference walk GFS -> NAM -> MEX); this feed adds the per-model split so the agent can see WHICH
     model moved. At D+3..D+7 the composite is structurally MEX-only, so the composite delta and this
     feed's MEX stability must agree exactly -- the selftest asserts that reproduction.

Never scored, never gated on whether it "predicts" anything. The agent decides what it means.

SOURCE / READ-ONLY DISCIPLINE
-----------------------------
This feed COMPUTES, it does not fetch. Input is the local raw IEM-MOS archive cache written by the S97
MOS build (`nws_temp_feed.py --mos-asof`): `weather/mos_asof/raw/{METRO}_{MODEL}_{sts}_{ets}.json`,
rows {runtime, ftime, tmp} verbatim (UTC). All existing stores are read-only here; this module writes
ONLY its own store `data/model_disagreement/model_disagreement.json`. If the raw archive is absent or
partial, the gap is NAMED in the output -- scope is never silently narrowed and nothing is re-fetched.

RUN-SELECTION LOGIC IS INHERITED, NOT RE-DERIVED
------------------------------------------------
The blind wall and run selection are imported directly from `nws_temp_feed` (same directory) so this
feed can never drift from the canonical MOS as-of feed:
  _mos_cutoff_utc  -- the wall: target day D sees only runs initialized <= D-1T23:59Z
                      (= 17:59 CT on D-1, the evening of D-1; the 00Z cycle of D itself is EXCLUDED)
  _runset_asof     -- the 24h evening batch ending at the wall (hard assert inside)
  _day_temp_from_run / degree_days / station_weights -- the gas-day (America/Chicago) max/min ->
                      tmean -> base-65 HDD/CDD convention, MOS_MIN_OBS per model
The prior batch (for stability) uses the same machinery at cutoff minus one day, exactly as the
canonical run_delta does. Per-metro run stamps are carried for every value so the audit (and the
agent) can see precisely which model cycle produced every number.

ARCHIVE CYCLE GEOMETRY (measured, not assumed -- see MODEL_DISAGREEMENT_NOTES_S98.md)
-------------------------------------------------------------------------------------
GFS (MAV): 4 cycles/day in the archive (00/06/12/18Z), reach ~+72h -> latest eligible = 18Z D-1.
NAM (MET): 2 cycles/day (00/12Z only -- MET bulletins are only issued from the 00Z/12Z NAM),
           reach ~+84h -> latest eligible = 12Z D-1.
MEX:       2 cycles/day (00/12Z), 12-hourly temps, reach ~+192h -> latest eligible = 12Z D-1.
The MAV-vs-MET pair therefore compares an 18Z-initialized MAV against a 12Z-initialized MET -- the
freshest of each model a D-1-evening decision actually had. The 6h initialization mismatch is inherent
to the decision-time information geometry and is exposed via the per-metro run stamps, not hidden.

MISSING IS EXPLICIT, NEVER ZERO: every uncovered (horizon, metro, model, batch) is None with the
missing metros / the reason NAMED. A zeroed spread would read as "models agree"; a zeroed delta as
"forecast stable" -- both catastrophic false signals.

Usage (run from the repo root; no network ever):
    python research/kalshi/model_disagreement.py --build              # precompute over the MOS index span
    python research/kalshi/model_disagreement.py --selftest           # audits + the 0125/0126 factual case
    python research/kalshi/model_disagreement.py --show 2026-01-26    # one day, compact
    python research/kalshi/model_disagreement.py --coverage           # per-date coverage table, gaps named
"""
from __future__ import annotations

import argparse
import datetime as _dt
import glob
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from functools import lru_cache

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(_HERE))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import nws_temp_feed as ntf  # noqa: E402  (read-only import of the canonical as-of logic)

MOS_RAW_DIR = os.path.join(ROOT, "weather", "mos_asof", "raw")
MOS_INDEX_PATH = os.path.join(ROOT, "weather", "mos_asof", "mos_asof_index.json")
STORE_DIR = os.path.join(ROOT, "data", "model_disagreement")
STORE_PATH = os.path.join(STORE_DIR, "model_disagreement.json")

DISAGREE_MAV = "GFS"           # GFS-MOS MAV short range -- the "mav" side of the pair
DISAGREE_MET = "NAM"           # NAM-MOS MET -- the "met" side of the pair
STABILITY_MODELS = ("GFS", "NAM", "MEX")   # per-model run-to-run split (MEX = GFS extended)
HORIZONS = ntf.MOS_HORIZONS    # D+0 .. D+7, same as the canonical feed

_pts = lru_cache(maxsize=None)(ntf._parse_ts)   # memoized timestamp parse (hot loop; logic unchanged)


# ------------------------------------------------------------------------------------------------------
# raw archive load (read-only; merges every cached window per metro+model; conflicts are LOUD)
# ------------------------------------------------------------------------------------------------------
def load_raw_runs(raw_dir: str = MOS_RAW_DIR, verbose: bool = False):
    """{metro: {model: {runtime: {ftime: tmp}}}} from every raw cache file present, plus a gap report.
    Never fetches. A metro/model with no file on disk is an entry in `gaps`, not an exception."""
    mos: dict[str, dict[str, dict]] = {}
    gaps: list[str] = []
    conflicts = 0
    for st in ntf.STATION_WEIGHTS_RAW:
        mos[st] = {}
        for model in STABILITY_MODELS:
            paths = sorted(glob.glob(os.path.join(raw_dir, f"{st}_{model}_*.json")))
            if not paths:
                gaps.append(f"{st}/{model}: no raw archive file on disk under {raw_dir}")
                continue
            runs: dict[str, dict[str, float]] = {}
            for p in paths:
                with open(p) as f:
                    rows = json.load(f)
                for r in rows:
                    prev = runs.setdefault(r["runtime"], {}).get(r["ftime"])
                    if prev is not None and prev != r["tmp"]:
                        conflicts += 1   # same (runtime, ftime), different value across cache files
                    runs[r["runtime"]][r["ftime"]] = r["tmp"]
            mos[st][model] = runs
            if verbose:
                print(f"[md] {st} {model}: {len(runs)} runs from {len(paths)} file(s)", flush=True)
    if conflicts:
        # zero expected (re-pull windows verified exact subsets); if it ever fires it is a data event
        gaps.append(f"RAW CONFLICTS: {conflicts} (runtime,ftime) rows disagree across cache files")
    return mos, gaps


# ------------------------------------------------------------------------------------------------------
# single-model station read (the canonical _station_forecast minus the model-preference walk)
# ------------------------------------------------------------------------------------------------------
def _model_station_read(runs: dict | None, target_day: str, cutoff: datetime, model: str) -> dict | None:
    """One metro, ONE model: latest eligible cycle in the 24h batch ending at `cutoff` that covers
    `target_day` with >= MOS_MIN_OBS[model] temps inside the gas day. None = explicit miss, never 0."""
    if not runs:
        return None
    sel = ntf._runset_asof(runs, cutoff)          # hard-asserts the blind wall
    for rt in sorted(sel, key=_pts, reverse=True):
        mm = ntf._day_temp_from_run(sel[rt], target_day, ntf.MOS_MIN_OBS[model])
        if mm is None:
            continue
        tmax, tmin = mm
        tmean = (tmax + tmin) / 2.0
        hdd, cdd = ntf.degree_days(tmean)
        return {"runtime": rt, "hdd": round(hdd, 2), "cdd": round(cdd, 2)}
    return None


def _gw_over(reads: dict[str, dict], metros: list[str]) -> tuple[float, float, float]:
    """(gw_hdd, gw_cdd, weight_coverage) over an explicit metro list, weights renormalized over it."""
    w = ntf.station_weights()
    wsum = sum(w[s] for s in metros)
    gw_hdd = sum(w[s] * reads[s]["hdd"] for s in metros) / wsum
    gw_cdd = sum(w[s] * reads[s]["cdd"] for s in metros) / wsum
    return round(gw_hdd, 3), round(gw_cdd, 3), round(wsum, 4)


# ------------------------------------------------------------------------------------------------------
# the per-day record
# ------------------------------------------------------------------------------------------------------
def disagreement_day(target_day: str, mos: dict[str, dict[str, dict]]) -> dict:
    """Everything this feed knows for target day D, as of the EVENING OF D-1 (the canonical wall)."""
    cutoff_cur = ntf._mos_cutoff_utc(target_day)          # D-1 T23:59Z
    cutoff_prv = cutoff_cur - timedelta(days=1)           # D-2 T23:59Z (prior evening batch)
    all_metros = list(ntf.STATION_WEIGHTS_RAW)

    disagreement = []
    stability: dict[str, list] = {m: [] for m in STABILITY_MODELS}

    for h in range(HORIZONS):
        tgt = ntf._shift(target_day, h)

        # ---- per-model current-batch reads (shared by disagreement + stability) ----
        cur: dict[str, dict[str, dict | None]] = {
            m: {s: _model_station_read(mos.get(s, {}).get(m), tgt, cutoff_cur, m) for s in all_metros}
            for m in STABILITY_MODELS}

        # ---- DISAGREEMENT: MAV vs MET on the common metro set only ----
        mav, met = cur[DISAGREE_MAV], cur[DISAGREE_MET]
        common = [s for s in all_metros if mav[s] and met[s]]
        mav_only = sorted(s for s in all_metros if mav[s] and not met[s])
        met_only = sorted(s for s in all_metros if met[s] and not mav[s])
        neither = sorted(s for s in all_metros if not mav[s] and not met[s])
        if not common:
            disagreement.append({
                "horizon": h, "target_date": tgt,
                "mav_gw_hdd": None, "met_gw_hdd": None, "mav_gw_cdd": None, "met_gw_cdd": None,
                "spread_gw_hdd": None, "abs_spread_gw_hdd": None, "spread_gw_cdd": None,
                "n_common_metros": 0, "coverage": 0.0,
                "metros_mav_only": mav_only, "metros_met_only": met_only, "metros_neither": neither,
                "mav_runs": {}, "met_runs": {},
                # S114: the reach reason is CORRECT but was read as absurd by three specialists
                # independently, each computing "h2 is only +48h, well inside a +72h model" and
                # concluding the note was boilerplate over a dead feed. The arithmetic they were
                # missing is the GAS DAY: coverage requires the WHOLE Chicago day, so target D+2
                # runs to ~D+3T05Z, which is ~+77h from the last eligible (D-1 18Z) MAV cycle and
                # ~+89h from the last eligible (D-1 12Z) MET cycle. Both fall short by a few hours,
                # which is why h>=2 is empty while h0/h1 are complete. State the binding constraint,
                # not just the model reach - an accurate note that misleads an expert reader is a
                # defect in the note.
                "note": ("no MAV/MET overlap at this horizon - spread is null, NOT zero"
                         + (" (the binding constraint is FULL-GAS-DAY coverage, not the horizon"
                            " label: target D+h ends ~D+h+1T05Z, so h2 needs ~+77h from the last"
                            " eligible MAV cycle (D-1 18Z, reach ~+72h) and ~+89h from the last"
                            " eligible MET cycle (D-1 12Z, reach ~+84h). Both fall short by hours,"
                            " so h>=2 is MEX-only territory - this is a reach limit, not an outage;"
                            " h0/h1 on this same date carry all 16 metros)"
                            if not mav_only and not met_only else
                            f" (one-sided coverage: MAV-only {mav_only or '[]'}, MET-only {met_only or '[]'})")),
            })
        else:
            mav_hdd, mav_cdd, cov = _gw_over(mav, common)
            met_hdd, met_cdd, _ = _gw_over(met, common)
            spread = round(mav_hdd - met_hdd, 3)
            partial = len(common) < len(all_metros)
            disagreement.append({
                "horizon": h, "target_date": tgt,
                "mav_gw_hdd": mav_hdd, "met_gw_hdd": met_hdd,
                "mav_gw_cdd": mav_cdd, "met_gw_cdd": met_cdd,
                "spread_gw_hdd": spread, "abs_spread_gw_hdd": round(abs(spread), 3),
                "spread_gw_cdd": round(mav_cdd - met_cdd, 3),
                "n_common_metros": len(common), "coverage": cov,
                "metros_mav_only": mav_only, "metros_met_only": met_only, "metros_neither": neither,
                "mav_runs": {s: mav[s]["runtime"] for s in common},
                "met_runs": {s: met[s]["runtime"] for s in common},
                "note": ("complete: all 16 metros in both models" if not partial else
                         f"PARTIAL: common set {len(common)}/16, weights renormalized "
                         f"(MAV-only {mav_only}, MET-only {met_only}, neither {neither})"),
            })

        # ---- RUN STABILITY per model: current evening batch minus prior evening batch, same target ----
        for m in STABILITY_MODELS:
            prv = {s: _model_station_read(mos.get(s, {}).get(m), tgt, cutoff_prv, m) for s in all_metros}
            both = [s for s in all_metros if cur[m][s] and prv[s]]
            miss = sorted(set(all_metros) - set(both))
            if not both:
                stability[m].append({
                    "horizon": h, "target_date": tgt, "d_gw_hdd": None, "d_gw_cdd": None,
                    "n_metros": 0, "coverage": 0.0, "metros_missing": miss,
                    "runs_cur": {}, "runs_prv": {},
                    "note": (f"no metro has a usable {m} read in BOTH evening batches - "
                             "delta is null, NOT zero"),
                })
            else:
                w = ntf.station_weights()
                wsum = sum(w[s] for s in both)
                d_hdd = sum(w[s] * (cur[m][s]["hdd"] - prv[s]["hdd"]) for s in both) / wsum
                d_cdd = sum(w[s] * (cur[m][s]["cdd"] - prv[s]["cdd"]) for s in both) / wsum
                stability[m].append({
                    "horizon": h, "target_date": tgt,
                    "d_gw_hdd": round(d_hdd, 3), "d_gw_cdd": round(d_cdd, 3),
                    "n_metros": len(both), "coverage": round(wsum, 4), "metros_missing": miss,
                    "runs_cur": {s: cur[m][s]["runtime"] for s in both},
                    "runs_prv": {s: prv[s]["runtime"] for s in both},
                    "note": ("complete: all 16 metros in both batches" if not miss else
                             f"PARTIAL delta: {len(miss)} metros lack one batch ({','.join(miss)}); "
                             "common-set weights renormalized"),
                })

    # ---- within-date summary (shape descriptor ONLY; per-horizon rows are canonical) ----
    overlap = [d for d in disagreement if d["spread_gw_hdd"] is not None]
    if overlap:
        mx = max(overlap, key=lambda d: d["abs_spread_gw_hdd"])
        summary = {
            "n_overlap_horizons": len(overlap),
            "overlap_horizons": [d["horizon"] for d in overlap],
            "max_abs_spread_gw_hdd": mx["abs_spread_gw_hdd"],
            "max_abs_spread_horizon": mx["horizon"],
            "mean_abs_spread_over_overlap": round(
                sum(d["abs_spread_gw_hdd"] for d in overlap) / len(overlap), 3),
        }
    else:
        summary = {"n_overlap_horizons": 0, "overlap_horizons": [],
                   "max_abs_spread_gw_hdd": None, "max_abs_spread_horizon": None,
                   "mean_abs_spread_over_overlap": None}
    summary["summary_note"] = ("within-THIS-date summary across its matched horizons - a shape "
                               "descriptor for the agent, NOT a pooled conclusion; the per-horizon "
                               "rows are canonical (no-pooling rule)")

    return {
        "date": target_day,
        "asof_utc": cutoff_cur.strftime("%Y-%m-%dT%H:%MZ"),
        "asof_note": ("same blind wall as mos_asof_index: all runs initialized <= D-1T23:59Z "
                      "(= 17:59 CT on D-1, the evening of D-1); the 00Z cycle of D itself is EXCLUDED; "
                      "the stability prior batch is <= D-2T23:59Z"),
        "disagreement": disagreement,
        "stability": stability,
        "summary": summary,
    }


# ------------------------------------------------------------------------------------------------------
# store build / load / asof
# ------------------------------------------------------------------------------------------------------
def _index_span() -> tuple[str, str]:
    """The canonical MOS store's span (first day, last day inclusive). This feed covers exactly that."""
    if not os.path.exists(MOS_INDEX_PATH):
        raise FileNotFoundError(f"canonical MOS index absent: {MOS_INDEX_PATH} - "
                                "restore weather/mos_asof/ (S3) first; this feed never fetches")
    with open(MOS_INDEX_PATH) as f:
        ks = sorted(json.load(f))
    return ks[0], ks[-1]


def build(start: str | None = None, end: str | None = None, verbose: bool = True) -> dict:
    """Precompute the store over [start, end] inclusive (default: the canonical MOS index span)."""
    if start is None or end is None:
        s, e = _index_span()
        start, end = start or s, end or e
    mos, gaps = load_raw_runs(verbose=verbose)
    days = {}
    day = start
    while day <= end:
        days[day] = disagreement_day(day, mos)
        if verbose:
            sm = days[day]["summary"]
            print(f"[md] {day}  overlap_h={sm['overlap_horizons']}  "
                  f"max|spread|={sm['max_abs_spread_gw_hdd']} @h{sm['max_abs_spread_horizon']}  "
                  f"mean|spread|={sm['mean_abs_spread_over_overlap']}", flush=True)
        day = ntf._shift(day, 1)
    store = {
        "_meta": {
            "feed": "model_disagreement (DATA_GATE_S98 feed C, family D)",
            "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "span": [start, end], "n_days": len(days),
            "source": ("local raw IEM-MOS archive cache weather/mos_asof/raw/ written by "
                       "nws_temp_feed.py --mos-asof (S97). This feed COMPUTES only - never fetches."),
            "raw_gaps": gaps,
            "models": {
                "mav": "GFS = GFS-MOS MAV short range; archive cycles 00/06/12/18Z; reach ~+72h",
                "met": "NAM = NAM-MOS MET; archive cycles 00/12Z only; reach ~+84h",
                "mex": ("MEX = GFS extended MOS; archive cycles 00/12Z; 12-hourly temps; reach ~+192h. "
                        "Stability only - NOT part of the disagreement pair."),
            },
            "conventions": {
                "spread": ("spread_gw_hdd = MAV minus MET (signed; positive = the GFS short-range MOS "
                           "carries more heating demand than the NAM MOS), on the COMMON metro set only "
                           "so a coverage difference can never masquerade as disagreement"),
                "stability": ("per model: latest eligible cycle of the D-1 evening batch minus latest "
                              "eligible cycle of the D-2 evening batch, same target day, common metro "
                              "set only - the per-model split of the canonical composite run_delta"),
                "blind_wall": "inherited from nws_temp_feed: runs initialized <= D-1T23:59Z (17:59 CT D-1)",
                "missing": "None = unknown, always named; never zero, never imputed",
                "gas_day": "America/Chicago day boundary; tmean=(tmax+tmin)/2; base-65 HDD/CDD",
            },
        },
        "days": days,
    }
    os.makedirs(STORE_DIR, exist_ok=True)
    with open(STORE_PATH, "w") as f:
        json.dump(store, f, sort_keys=True, indent=1)
    if verbose:
        mb = os.path.getsize(STORE_PATH) / 1e6
        print(f"[md] store written: {STORE_PATH} ({len(days)} days, {mb:.1f} MB)", flush=True)
    return store


_STORE_CACHE: dict | None = None
_RUNS_CACHE = None


def load_store(path: str = STORE_PATH) -> dict | None:
    global _STORE_CACHE
    if _STORE_CACHE is None and os.path.exists(path):
        with open(path) as f:
            _STORE_CACHE = json.load(f)
    return _STORE_CACHE


def _coerce_day(date) -> str:
    if isinstance(date, str):
        return datetime.strptime(date[:10], "%Y-%m-%d").strftime("%Y-%m-%d")
    if isinstance(date, (_dt.datetime, _dt.date)):
        return date.strftime("%Y-%m-%d")
    raise TypeError(f"date must be 'YYYY-MM-DD' or date/datetime, got {type(date)}")


def model_disagreement_asof(date) -> dict | None:
    """The model-disagreement + per-model run-stability state for target day `date`, as of the evening
    of date-1 (the canonical MOS blind wall). Store lookup first; falls back to computing directly from
    the local raw archive; None if the date is outside what the local archive can honestly cover."""
    day = _coerce_day(date)
    store = load_store()
    if store and day in store.get("days", {}):
        return store["days"][day]
    # fallback: compute on the fly from the local raw cache (still never fetches)
    global _RUNS_CACHE
    if _RUNS_CACHE is None:
        if not os.path.isdir(MOS_RAW_DIR) or not glob.glob(os.path.join(MOS_RAW_DIR, "*.json")):
            return None                       # raw archive absent locally - named gap, do not guess
        _RUNS_CACHE = load_raw_runs()
    mos, _ = _RUNS_CACHE
    rec = disagreement_day(day, mos)
    # a date wholly outside archive coverage yields no values anywhere -> honest None, not empty shell
    any_value = (any(d["spread_gw_hdd"] is not None for d in rec["disagreement"])
                 or any(r["d_gw_hdd"] is not None for rows in rec["stability"].values() for r in rows))
    return rec if any_value else None


# ------------------------------------------------------------------------------------------------------
# audits
# ------------------------------------------------------------------------------------------------------
def audit_blind_wall(store: dict) -> tuple[int, int]:
    """Walk EVERY run stamp in the built store and check it against the wall:
    current-batch stamps <= D-1T23:59Z, prior-batch stamps <= D-2T23:59Z (and both inside their 24h
    batch windows). Returns (n_stamps_checked, n_violations); violations are printed, named."""
    checked = viol = 0
    for day, rec in sorted(store["days"].items()):
        cut_cur = ntf._mos_cutoff_utc(day)
        cut_prv = cut_cur - timedelta(days=1)
        def _chk(stamps: dict, cutoff: datetime, what: str):
            nonlocal checked, viol
            lo = cutoff - timedelta(hours=24)
            for metro, rt in stamps.items():
                checked += 1
                t = _pts(rt)
                if not (lo < t <= cutoff):
                    viol += 1
                    print(f"  [VIOLATION] {day} {what} {metro}: run {rt} outside "
                          f"({lo:%Y-%m-%d %H:%M}, {cutoff:%Y-%m-%d %H:%M}]")
        for d in rec["disagreement"]:
            _chk(d["mav_runs"], cut_cur, f"h{d['horizon']} MAV")
            _chk(d["met_runs"], cut_cur, f"h{d['horizon']} MET")
        for m, rows in rec["stability"].items():
            for r in rows:
                _chk(r["runs_cur"], cut_cur, f"h{r['horizon']} {m} cur")
                _chk(r["runs_prv"], cut_prv, f"h{r['horizon']} {m} prv")
    return checked, viol


def audit_vs_canonical(store: dict) -> tuple[int, int, int, int]:
    """Cross-validate against the canonical mos_asof_index composite run_delta:
    (a) at h>=3 the composite is structurally MEX-only (MAV ~+72h / MET ~+84h cannot reach a gas day
        >= D+3 from the D-1 evening batch), so composite d_gw_hdd must EQUAL this feed's MEX stability;
    (b) at h<=2, wherever this feed's GFS stability covers all 16 metros in both batches AND the
        canonical current-batch source_by_metro is all-GFS, the composite must EQUAL GFS stability.
    Returns (n_mex_cmp, n_mex_mismatch, n_gfs_cmp, n_gfs_mismatch); mismatches printed, named."""
    with open(MOS_INDEX_PATH) as f:
        idx = json.load(f)
    n_mex = mm_mex = n_gfs = mm_gfs = 0
    for day, rec in sorted(store["days"].items()):
        can = idx.get(day)
        if not can:
            continue
        can_rd = {r["horizon"]: r for r in can["run_delta"]}
        can_hz = {h["horizon"]: h for h in can["horizons"]}
        for r in rec["stability"]["MEX"]:
            h = r["horizon"]
            if h < 3 or h not in can_rd:
                continue
            c = can_rd[h]
            if c["d_gw_hdd"] is None and r["d_gw_hdd"] is None:
                continue
            n_mex += 1
            if (c["d_gw_hdd"] is None) != (r["d_gw_hdd"] is None) or \
               (c["d_gw_hdd"] is not None and abs(c["d_gw_hdd"] - r["d_gw_hdd"]) > 5e-4):
                mm_mex += 1
                print(f"  [MISMATCH mex] {day} h{h}: canonical {c['d_gw_hdd']} vs MEX {r['d_gw_hdd']}")
        for r in rec["stability"]["GFS"]:
            h = r["horizon"]
            if h > 2 or h not in can_rd or r["n_metros"] != 16:
                continue
            src = can_hz.get(h, {}).get("source_by_metro", {})
            if len(src) != 16 or not all(v.startswith("GFS@") for v in src.values()):
                continue
            c = can_rd[h]
            if c["d_gw_hdd"] is None:
                continue
            n_gfs += 1
            if r["d_gw_hdd"] is None or abs(c["d_gw_hdd"] - r["d_gw_hdd"]) > 5e-4:
                mm_gfs += 1
                print(f"  [MISMATCH gfs] {day} h{h}: canonical {c['d_gw_hdd']} vs GFS {r['d_gw_hdd']}")
    return n_mex, mm_mex, n_gfs, mm_gfs


def audit_recompute(store: dict, sample_every: int = 1) -> tuple[int, int]:
    """Determinism audit: recompute day records from raw and require exact equality with the store."""
    mos, _ = load_raw_runs()
    days = sorted(store["days"])
    n = bad = 0
    for day in days[::sample_every]:
        n += 1
        if disagreement_day(day, mos) != store["days"][day]:
            bad += 1
            print(f"  [RECOMPUTE MISMATCH] {day}")
    return n, bad


# ------------------------------------------------------------------------------------------------------
# selftest
# ------------------------------------------------------------------------------------------------------
def selftest() -> int:
    ok = True

    def check(name, cond):
        nonlocal ok
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        ok = ok and cond

    print("[md selftest] unit fixtures (join-logic structure only; nothing persisted)")
    cut = ntf._mos_cutoff_utc("2026-01-20")
    check("wall is D-1T23:59Z / 17:59 CT D-1 evening",
          cut == datetime(2026, 1, 19, 23, 59, tzinfo=timezone.utc)
          and cut.astimezone(ntf.REF_TZ).strftime("%H:%M") == "17:59")
    runs = {"2026-01-19 12:00:00": {f"2026-01-20 {hh:02d}:00:00": 20.0 for hh in (6, 9, 12, 15, 18)},
            "2026-01-20 00:00:00": {f"2026-01-20 {hh:02d}:00:00": 99.0 for hh in (6, 9, 12, 15, 18)}}
    r = _model_station_read(runs, "2026-01-20", cut, "NAM")
    check("00Z-of-D cycle EXCLUDED; 12Z D-1 used", r is not None and r["runtime"] == "2026-01-19 12:00:00")
    check("uncovered model read is None, never 0",
          _model_station_read({"2026-01-19 12:00:00": {"2026-01-20 12:00:00": 30.0}},
                              "2026-01-20", cut, "GFS") is None)
    # spread sign convention on a two-metro fixture: MAV colder (more HDD) than MET -> positive spread
    fx_mav = {"ORD": {"runtime": "r", "hdd": 30.0, "cdd": 0.0}, "NYC": {"runtime": "r", "hdd": 20.0, "cdd": 0.0}}
    fx_met = {"ORD": {"runtime": "r", "hdd": 25.0, "cdd": 0.0}, "NYC": {"runtime": "r", "hdd": 18.0, "cdd": 0.0}}
    mh, _, _ = _gw_over(fx_mav, ["ORD", "NYC"])
    th, _, _ = _gw_over(fx_met, ["ORD", "NYC"])
    check("spread = MAV minus MET, signed positive when MAV carries more HDD", mh - th > 0)

    print("[md selftest] built store")
    store = load_store()
    check("store present (run --build first if FAIL)", store is not None)
    if store is None:
        return 1
    meta = store["_meta"]
    days = store["days"]
    print(f"  span {meta['span'][0]} .. {meta['span'][1]}  ({meta['n_days']} days)  "
          f"raw_gaps={meta['raw_gaps'] or 'none'}")
    check("raw archive had no gaps at build time", not meta["raw_gaps"])

    checked, viol = audit_blind_wall(store)
    print(f"  blind-wall audit: {checked} run stamps checked, {viol} violations")
    check("blind wall: 0 violations across every stored run stamp", viol == 0)

    zero_hdd = sum(1 for rec in days.values() for d in rec["disagreement"]
                   if d["spread_gw_hdd"] is None and (d["mav_gw_hdd"] == 0.0 or d["met_gw_hdd"] == 0.0))
    check("missing never zeroed (no 0.0 masquerading where spread is null)", zero_hdd == 0)

    n_mex, mm_mex, n_gfs, mm_gfs = audit_vs_canonical(store)
    print(f"  canonical cross-check: MEX-vs-composite {n_mex} comparisons / {mm_mex} mismatches; "
          f"GFS-vs-composite {n_gfs} comparisons / {mm_gfs} mismatches")
    check("h>=3 composite run_delta exactly reproduced by the MEX split", n_mex > 0 and mm_mex == 0)
    check("h<=2 all-GFS composite run_delta exactly reproduced by the GFS split", n_gfs > 0 and mm_gfs == 0)

    n_rc, bad_rc = audit_recompute(store)
    print(f"  determinism audit: {n_rc} days recomputed from raw, {bad_rc} mismatches")
    check("store is a pure function of the raw archive (full recompute equality)", bad_rc == 0)

    # ---- factual demonstration: a no-overlap horizon is None and named ----
    print("[md selftest] no-overlap horizon (factual)")
    sample = days.get("2026-01-15") or next(iter(days.values()))
    d3 = sample["disagreement"][3]
    print(f"  {sample['date']} h3 (target {d3['target_date']}): spread_gw_hdd={d3['spread_gw_hdd']}  "
          f"note: {d3['note']}")
    check("h3 has no MAV/MET overlap -> None, reason named",
          d3["spread_gw_hdd"] is None and "null" in d3["note"])

    # ---- factual demonstration: the 0125/0126 whipsaw, per-model split ----
    print("[md selftest] the 0125/0126 case (factual demonstration, target 2026-01-30)")
    have = all(d in days for d in ("2026-01-25", "2026-01-26", "2026-01-28", "2026-01-29", "2026-01-30"))
    # S114: A COVERAGE GAP IS NOT A TEST FAILURE. This case demonstrates a January whipsaw, and the
    # local raw MOS archive spans only 2026-07-14..2026-08-11 - so on any container without a
    # January pull the case CANNOT run, and reporting it as FAIL made `--selftest` permanently red.
    # A permanently-red check is one people learn to ignore, which is the S112 Station 0 lesson and
    # the same argument that fixed the scored_leg regression this session. DECLARE the gap loudly,
    # SKIP the demonstration, and do not let it mark the suite failed - the substantive checks
    # (blind wall, determinism, missing-never-zeroed, the composite cross-checks) all still run and
    # still gate.
    if not have:
        span = (min(days), max(days)) if days else ("none", "none")
        print("  SKIPPED - DECLARED COVERAGE GAP, not a failure. This factual case targets "
              "2026-01-30; the store spans %s..%s because the local raw MOS archive does. "
              "Re-run after a January MOS pull (nws_temp_feed.py --mos-asof) to exercise it. "
              "Every other section below ran." % span)
    if have:
        r25 = next(r for r in days["2026-01-25"]["stability"]["MEX"] if r["target_date"] == "2026-01-30")
        r26 = next(r for r in days["2026-01-26"]["stability"]["MEX"] if r["target_date"] == "2026-01-30")
        g25 = next(r for r in days["2026-01-25"]["stability"]["GFS"] if r["target_date"] == "2026-01-30")
        n25 = next(r for r in days["2026-01-25"]["stability"]["NAM"] if r["target_date"] == "2026-01-30")
        print(f"  asof 01-24 eve (h{r25['horizon']}): MEX d_gw_hdd {r25['d_gw_hdd']}   "
              f"GFS {g25['d_gw_hdd']}   NAM {n25['d_gw_hdd']}   <- the cut, and WHICH model made it")
        print(f"  asof 01-25 eve (h{r26['horizon']}): MEX d_gw_hdd {r26['d_gw_hdd']}   <- the re-add, "
              "same target, next evening batch")
        check("the cut is the MEX (extended) model, short-range models out of reach",
              r25["d_gw_hdd"] is not None and r25["d_gw_hdd"] < -2.0
              and g25["d_gw_hdd"] is None and n25["d_gw_hdd"] is None)
        check("the re-add is visible in the same per-model split",
              r26["d_gw_hdd"] is not None and r26["d_gw_hdd"] > 3.0)
        for d in ("2026-01-28", "2026-01-29", "2026-01-30"):
            row = next(x for x in days[d]["disagreement"] if x["target_date"] == "2026-01-30")
            mexs = next(x for x in days[d]["stability"]["MEX"] if x["target_date"] == "2026-01-30")
            print(f"  asof {d} eve-of-D-1 (h{row['horizon']}): MAV {row['mav_gw_hdd']} vs MET "
                  f"{row['met_gw_hdd']}  spread {row['spread_gw_hdd']}  |  MEX run-delta {mexs['d_gw_hdd']}")
        row = next(x for x in days["2026-01-30"]["disagreement"] if x["target_date"] == "2026-01-30")
        check("once 01-30 enters the short-range overlap, the MAV/MET pair is matched (n=16)",
              row["n_common_metros"] == 16 and row["spread_gw_hdd"] is not None)

    print(f"[md selftest] {'ALL PASS' if ok else 'FAILURES PRESENT'}")
    return 0 if ok else 1


# ------------------------------------------------------------------------------------------------------
# reporting helpers
# ------------------------------------------------------------------------------------------------------
def coverage_report() -> None:
    """Per-date coverage: matched horizons, spread summary, per-model stability reach, gaps named."""
    store = load_store()
    if store is None:
        print("no store - run --build first")
        return
    print("date        overlap_h  max|spr|@h   mean|spr|  GFSd_h  NAMd_h  MEXd_h  gaps")
    for day, rec in sorted(store["days"].items()):
        sm = rec["summary"]
        reach = {}
        for m in STABILITY_MODELS:
            hs = [r["horizon"] for r in rec["stability"][m] if r["d_gw_hdd"] is not None]
            reach[m] = f"{min(hs)}-{max(hs)}" if hs else "-"
        gaps = []
        for d in rec["disagreement"]:
            if d["spread_gw_hdd"] is not None and d["n_common_metros"] < 16:
                gaps.append(f"h{d['horizon']}:common{d['n_common_metros']}/16")
        for m in STABILITY_MODELS:
            for r in rec["stability"][m]:
                if r["d_gw_hdd"] is not None and r["n_metros"] < 16:
                    gaps.append(f"h{r['horizon']}{m}:n{r['n_metros']}/16")
        mx = (f"{sm['max_abs_spread_gw_hdd']}@h{sm['max_abs_spread_horizon']}"
              if sm["max_abs_spread_gw_hdd"] is not None else "-")
        print(f"{day}  {sm['overlap_horizons']}    {mx:>10}   {sm['mean_abs_spread_over_overlap']!s:>8}"
              f"  {reach['GFS']:>5}  {reach['NAM']:>5}  {reach['MEX']:>5}  {';'.join(gaps) or 'none'}")


def show_day(day: str) -> None:
    rec = model_disagreement_asof(day)
    if rec is None:
        print(f"{day}: None (outside local archive coverage)")
        return
    print(f"{rec['date']}  asof {rec['asof_utc']}")
    for d in rec["disagreement"]:
        if d["spread_gw_hdd"] is None:
            print(f"  h{d['horizon']} {d['target_date']}: no MAV/MET overlap (None)")
        else:
            print(f"  h{d['horizon']} {d['target_date']}: MAV {d['mav_gw_hdd']} vs MET {d['met_gw_hdd']}"
                  f"  spread {d['spread_gw_hdd']}  (n={d['n_common_metros']})")
    for m in STABILITY_MODELS:
        rows = [f"h{r['horizon']}:{r['d_gw_hdd']}" for r in rec["stability"][m] if r["d_gw_hdd"] is not None]
        print(f"  {m} run-delta: {'  '.join(rows) if rows else 'none'}")
    sm = rec["summary"]
    print(f"  summary: overlap {sm['overlap_horizons']}  max|spread| {sm['max_abs_spread_gw_hdd']} "
          f"@h{sm['max_abs_spread_horizon']}  mean|spread| {sm['mean_abs_spread_over_overlap']}")


def main() -> int:
    ap = argparse.ArgumentParser(description="FEED C: MAV-vs-MET disagreement + per-model run stability")
    ap.add_argument("--build", action="store_true", help="precompute the store over the MOS index span")
    ap.add_argument("--start", help="override span start YYYY-MM-DD (inclusive)")
    ap.add_argument("--end", help="override span end YYYY-MM-DD (inclusive)")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--show", metavar="DATE", help="print one day compactly")
    ap.add_argument("--coverage", action="store_true", help="per-date coverage table, gaps named")
    a = ap.parse_args()
    if a.build:
        build(a.start, a.end)
        return 0
    if a.selftest:
        return selftest()
    if a.show:
        show_day(a.show)
        return 0
    if a.coverage:
        coverage_report()
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
