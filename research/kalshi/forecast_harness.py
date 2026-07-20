"""
forecast_harness.py — turn-key helpers for the self-growing forecaster LOOP (S92 build).

Makes the loop one-command per step so S93 just runs it. NO agent reasoning here — this is the deterministic
scaffolding the agent uses: compute the decision-time state for a group, render guess-vs-actual overlays, and
load/merge the brain. The BLIND FORECAST itself (applying judgment from the brain) is the agent's job; this
harness holds the state it forecasts from and the render it's scored by.

Commands:
  decision-state --days D1,D2,...            -> print + write the decision-time state JSON for a group (blind-safe:
                                                weekday + storage surprise + curve regime ONLY; no tape/leg data)
  overlay --forecasts F.json --out P.png     -> render guess (dashed) vs actual (solid) per day, 1 panel/day, ET
  brain-show                                 -> summarize the current ng_brain.json (plays + status)
  --selftest
"""
from __future__ import annotations
import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
BRAIN = os.path.join(HERE, "knowledge", "ng_brain.json")
DOW = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
MULT = 10000.0   # $/MMBtu move = cum_move_usd / MULT (NG contract 10,000 MMBtu)
_DATA = os.path.join(HERE, "..", "..", "data")


def _load_json(rel: str):
    p = os.path.join(_DATA, rel)
    return json.load(open(p)) if os.path.exists(p) else (json.load(open(f"data/{rel}")) if os.path.exists(f"data/{rel}") else {})


def _storage_series():
    """RUNNING working-gas storage story from EIA prints (S94, Greg: chronological walk needs a running
    capacity story). Per report_date: {level Bcf (=prev_level+weekly change), chg, vs5yr (level - 5-yr avg
    for that ISO week), phase}. Built once, cached. All from historical EIA -> blind-safe."""
    d = _load_json("eia_surprise.json").get("KXNATGASD", {})
    rows = []
    for rep, r in sorted(d.items()):
        prev, act = r.get("prev_level"), r.get("actual")
        if prev is None or act is None:
            continue
        rows.append((rep, prev + act, act))
    from collections import defaultdict
    byweek = defaultdict(list)
    for rep, lvl, act in rows:
        wk = datetime.date.fromisoformat(rep).isocalendar()[1]
        byweek[wk].append((rep, lvl))
    out = {}
    for rep, lvl, act in rows:
        y = datetime.date.fromisoformat(rep).year
        wk = datetime.date.fromisoformat(rep).isocalendar()[1]
        hist = [v for rr, v in byweek[wk] if y - 5 <= datetime.date.fromisoformat(rr).year < y]
        vs5 = round(lvl - sum(hist) / len(hist)) if hist else None
        out[rep] = {"level": round(lvl), "weekly_chg": round(act), "vs_5yr": vs5,
                    "phase": "withdraw" if act < 0 else "inject"}
    return out


def _storage_asof(iso: str, series: dict) -> dict | None:
    """Most recent storage print with report_date STRICTLY BEFORE iso (S96 blind fix: <= let a storage
    Thursday's own 10:30 ET print into its open-time state; decision-time = prints from before the day)."""
    past = sorted(r for r in series if r < iso)
    return series[past[-1]] | {"as_of": past[-1]} if past else None


# US market / CME-energy weekday HOLIDAYS + half-days for the walk window (Greg S94: a weekday holiday
# absolutely changes that day's trade curve — closed / early-close / thin — so FLAG it). Effect tags:
# closed = no/near-no session; early_close = half-day; thin = trades but light (bond/bank holiday). Extend as
# the walk advances. Dates are the OBSERVED market date.
_HOLIDAYS = {
    "2025-10-13": ("Columbus_Day", "thin"),          "2025-11-11": ("Veterans_Day", "thin"),
    "2025-11-27": ("Thanksgiving", "thin"),          "2025-11-28": ("day_after_Thanksgiving", "early_close"),
    # S96 correction: CME Globex energy TRADES a thin shortened Thanksgiving session (2025-11-27 printed
    # ~13.6k trades, ~25% of normal) - it is NOT closed; only the equity-style full closure days are.
    "2025-12-24": ("Christmas_Eve", "early_close"),  "2025-12-25": ("Christmas", "closed"),
    "2025-12-31": ("New_Years_Eve", "thin"),         "2026-01-01": ("New_Years_Day", "closed"),
    "2026-01-19": ("MLK_Day", "thin"),               "2026-02-16": ("Presidents_Day", "thin"),
    "2026-04-03": ("Good_Friday", "closed"),         "2026-05-25": ("Memorial_Day", "closed"),
    "2026-06-19": ("Juneteenth", "closed"),          "2026-07-03": ("Independence_Day_obs", "early_close"),
}


def _holiday_asof(iso: str) -> dict | None:
    h = _HOLIDAYS.get(iso)
    return {"name": h[0], "effect": h[1]} if h else None


def _weather_asof(iso: str, wx: dict) -> dict | None:
    """Gas-weighted degree-day REGIME for the day (S88 nws feed). Blind rule (directive sec 6): the coarse
    HDD/CDD regime is highly forecastable a day ahead, so we carry it as the decision-time proxy (regime +
    values), NOT a precise same-day realized read. Flagged realized_as_proxy."""
    r = wx.get(iso)
    if not r:
        return None
    return {"regime": r.get("regime"), "gw_hdd": round(r.get("gw_hdd", 0), 1),
            "gw_cdd": round(r.get("gw_cdd", 0), 1), "gw_precip": round(r.get("gw_precip", 0), 2),
            "note": "realized_as_proxy_for_forecastable_regime"}


MOS_ASOF = os.path.join(HERE, "..", "..", "weather", "mos_asof", "mos_asof_index.json")


def _forecast_weather_asof(iso: str, mos: dict) -> dict | None:
    """(S97 JOB 2.2, Greg S96) What the NWS MOS FORECAST SAID as of the EVENING OF D-1 - the thing the gas
    market actually reprices on, as opposed to the realized temperature it turned out to be.

    ADDITIVE: this sits ALONGSIDE _weather_asof (the realized-as-proxy read), it does NOT replace it. Both
    are carried so the refine can compare forecast-conditioned rules against realized-proxy-conditioned
    ones and settle which the market is really trading.

    The key field is `run_delta` - the run-to-run CHANGE in the forecast (D-1 evening batch minus D-2
    evening batch, same target days). A forecast that is cold but UNCHANGED is already in the price; a
    forecast that just got colder is the repricing event.

    Blind wall: every underlying model run is initialized at or before D-1 T23:59Z (17:59 CT on D-1);
    built and asserted in nws_temp_feed._runset_asof. Missing coverage is None, NEVER 0."""
    r = mos.get(iso)
    if not r:
        return None
    return {
        "forecast_gw_hdd": r.get("forecast_gw_hdd"),
        "forecast_gw_cdd": r.get("forecast_gw_cdd"),
        "forecast_regime": r.get("forecast_regime"),
        "forecast_vs_normal": r.get("forecast_vs_normal"),
        "forecast_run_delta": r.get("forecast_run_delta"),
        "forecast_run_delta_cdd": r.get("forecast_run_delta_cdd"),
        "fwd7_gw_hdd_span": r.get("fwd7_gw_hdd_span"),
        "horizons": [{k: h[k] for k in ("horizon", "target_date", "forecast_gw_hdd", "forecast_vs_normal",
                                        "partial", "coverage")} for h in r.get("horizons", [])],
        "run_delta": [{k: h[k] for k in ("horizon", "target_date", "d_gw_hdd", "partial", "coverage")}
                      for h in r.get("run_delta", [])],
        "complete": r.get("complete"),
        "asof_utc": r.get("asof_utc"),
        "coverage_note": r.get("coverage_note"),
        "note": "mos_asof_D-1_evening_forecast (NOT realized); additive to `weather`, does not replace it",
    }


# S98 Tier 0 (DATA_GATE_S98.md): the INFORMATION CLOCK - a STATIC doctrine constant, not per-day data.
# The ET hours at which information arrives, so the agent can reason about WHICH session (or gap) a
# catalyst prices into ("a run posting 19:00 ET prices the overnight gap, not that day's close" - the
# generalization of the S97.2 finding that 0119's catalyst was consumed by the 0118 gap).
INFORMATION_CLOCK = {
    "note": "static ET reference of scheduled information arrival; all times approximate post/settle "
            "conventions, not data. A catalyst prices into the NEXT tradeable window after its arrival.",
    "model_cycles_et": {"00z_gfs_mos": "~03:30-04:30", "06z_gfs_mos": "~09:30-10:30",
                         "12z_gfs_mos": "~15:30-16:30", "18z_gfs_mos": "~21:30-22:30",
                         "cycles_run_weekends_too": True,
                         "weekend_note": "Sat/Sun 00z/12z cycles price the SUNDAY 18:00 ET reopen gap - "
                                          "the D-1-evening feed is one cycle behind it (s100_2_weekend_gap_note)"},
    "eia_storage_print_et": "Thu 10:30 (holiday weeks may shift - see the flow calendar feed when wired)",
    "cot_publication_et": "Fri 15:30 for Tuesday positions",
    "settle_window_et": "14:00-14:30 daily settle flows (excluded from every backtest cell)",
    "globex_reopen_et": "Sun 18:00 (the weekend gap prints here)",
    "session_close_et": "17:00, next session opens 18:00 (the daily maintenance hour)",
}


def _cot_asof_block(iso: str) -> dict | None:
    """(S98 Tier 0) CFTC COT positioning as-of - publication-keyed inside cot_feed (Friday 15:30 ET for
    Tuesday positions; a Friday's OWN publication never reaches its own open - verified 2026-01-16).
    Full passthrough: every field the feed exposes, nothing filtered. Missing -> None, never 0."""
    import cot_feed
    c = cot_feed.cot_asof(iso)
    if not c:
        return None
    return c | {"note": "positioning as-of PUBLICATION time; futures-only, NYMEX 023651 only (no ICE HH); "
                        "percentiles vs trailing 1y/3y of weekly nets"}


def _storage_regional_block(iso: str) -> dict | None:
    """(S98 Tier 0) EIA regional + SALT/NON-SALT storage as-of - strictly-prior Thursday print (a print
    Thursday's own 10:30 ET report never reaches its own open - verified 2026-01-15). Full passthrough."""
    import storage_regional
    s = storage_regional.storage_regional_asof(iso)
    if not s:
        return None
    return s | {"note": "five regions + salt split; salt = the fast-cycling swing capacity. ADDITIVE to the "
                        "national `storage` block, which is untouched"}


def _contract_structure_block(iso: str) -> dict | None:
    """(S98 Tier 0) Contract structure + forward curve as-of (49 fields, all passed through). THE CALENDAR-
    FRONT BLOCK IS THE POINT: the OI-continuous front rolls out of the dying contract early, so on
    2026-01-22 front_next_spread reads 0.093 while calendar_front_next_spread reads 1.539 - the squeeze
    lives ONLY in the calendar-front fields. Cross-roll spread changes arrive as None with
    *_pair_changed_*d flags set (artifact class, not moves)."""
    import contract_structure
    return contract_structure.contract_structure_asof(iso)


def _squeeze_watch(cs: dict | None) -> dict | None:
    """(S98 Tier 0, DATA_GATE_S98 0b family DEL) Derived convenience read - transparently from the wired
    structure fields, components exposed alongside so the agent reads both. None = components unknown
    (never False-when-unknown): a cross-roll day zeroes nothing, it says 'unknown'."""
    if not cs:
        return None
    d2e = cs.get("days_to_calendar_front_expiry")
    chg3 = cs.get("calendar_front_next_spread_chg_3d")
    active = None if (d2e is None or chg3 is None) else bool(d2e <= 7 and chg3 > 0)
    return {"active": active,
            "days_to_calendar_front_expiry": d2e,
            "calendar_front_next_spread": cs.get("calendar_front_next_spread"),
            "calendar_front_next_spread_chg_3d": chg3,
            "calendar_front_symbol": cs.get("calendar_front_symbol"),
            "note": "derived: days_to_calendar_front_expiry<=7 AND calendar_front_next_spread_chg_3d>0. "
                    "Inside this window delivery mechanics own the tape (DATA_GATE_S98 0b: demand-regime "
                    "bands are out of scope); G11's 0122-0130 is the n=1, G13 the forward test"}


def _storage_consensus_block(iso: str) -> dict | None:
    """(S98 feed D) The ANALYST SURVEY CONSENSUS for the EIA weekly storage print - the number the market
    is actually positioned against, vs the seasonal proxy in `stor_surprise`. `next_print` = the upcoming
    print's consensus (public pre-print - a print-day morning legitimately sees its OWN print's consensus,
    never its actual); `last_print` = the most recent completed print joined with its realized actual and
    `surprise_vs_consensus_bcf`. Per-house rows carried; disagreement exposed, never averaged. Holiday
    join trap handled inside the module (nominal vs actual release date - four shifted weeks incl. the
    double-print Christmas week). Module self-audits 0 blind-wall violations."""
    import storage_consensus as sc
    d = sc.storage_consensus_asof(iso)
    if not d:
        return None
    return d | {"note": "survey consensus ADDITIVE to stor_surprise (seasonal proxy) - both carried; "
                        "store spans Sep 2025 - Mar 5 2026, None outside (named forward hole Mar-Jul 2026)"}


def decision_state(days: list[str]) -> dict:
    """Blind-safe decision-time state per day: weekday + EIA storage surprise + curve regime + the RUNNING
    STORAGE capacity story (level / vs-5yr / phase) + gas-weighted degree-day regime (S94 chronological walk)
    + (S98 Tier 0) COT positioning + regional/salt storage + contract structure incl. the calendar-front
    squeeze view + (S98 feed D) the storage survey CONSENSUS. NO tape, NO legs, NO outcome — exactly what a
    forecaster knows at the open. Output carries a leading '_information_clock' meta key (static doctrine,
    not a day)."""
    import forward_curve as fc
    surp = _load_json("eia_surprise.json").get("KXNATGASD", {})
    stor = _storage_series()
    wx = _load_json("nws_temp/gw_degree_days.json")
    mos = json.load(open(MOS_ASOF)) if os.path.exists(MOS_ASOF) else {}   # additive; absent -> None, never 0
    cv = fc.load("NG")
    out = {"_information_clock": INFORMATION_CLOCK}
    for d in days:
        iso = f"{d[:4]}-{d[4:6]}-{d[6:]}"
        dow = DOW[datetime.date(int(d[:4]), int(d[4:6]), int(d[6:])).weekday()]
        past = sorted(ri for ri in surp if ri < iso)  # S96: strictly before the day (same-day print leaked)
        sv = surp[past[-1]]["surprise"] if past else None
        cr = fc.curve_asof(cv, iso)
        cs = _contract_structure_block(iso)
        # curve_regime: the legacy fc path first; where it reads 'unknown' the structure feed's regime
        # (settle-curve derived, strictly-prior) POPULATES it (S97 gate item 12: "confirm curve_regime
        # stops reading 'unknown'"). Populating an unknown is not replacing a field.
        regime = cr[1]["regime"] if cr else "unknown"
        if regime == "unknown" and cs and cs.get("curve_regime"):
            regime = cs["curve_regime"]
        out[d] = {"dow": dow, "stor_surprise": round(sv, 1) if sv is not None else None,
                  "stor_surprise_sign": ("above" if sv > 0 else "below") if sv is not None else None,
                  "curve_regime": regime,
                  "storage": _storage_asof(iso, stor),
                  "storage_regional": _storage_regional_block(iso),
                  "storage_consensus": _storage_consensus_block(iso),
                  "cot": _cot_asof_block(iso),
                  "contract_structure": cs,
                  "squeeze_watch": _squeeze_watch(cs),
                  "weather": _weather_asof(iso, wx),
                  "weather_forecast": _forecast_weather_asof(iso, mos),
                  "holiday": _holiday_asof(iso)}
    return out


def render_overlay(forecasts: dict, out_png: str, source: str = "s3") -> str:
    """Guess (dashed) vs actual (solid), one panel per day, price y / time x (ET). Anchors each guessed
    cumulative-move curve at the day's real OPEN. forecasts = {day: {dow, archetype, curve:[[et_hr, cum_usd],..]}}."""
    import numpy as np, pandas as pd
    import event_move_baseline as emb
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt, matplotlib.dates as mdates
    days = list(forecasts.keys())
    ncol = 3; nrow = (len(days) + ncol - 1) // ncol
    fig, axes = plt.subplots(nrow, ncol, figsize=(17, 4 * nrow)); axes = np.array(axes).reshape(-1)
    for i, day in enumerate(days):
        ax = axes[i]
        try:
            d = emb.load_cont_day("NG", day, source=source, trades_only=True)
            ts = np.asarray(d["ts"], float); px = np.asarray(d["price"], float)
            idx = pd.to_datetime(ts, unit="s", utc=True).tz_convert("America/New_York")
            ax.plot(idx, px, color="#1f6feb", lw=0.7, label="actual")
            o = float(px[0]); t0 = idx[0]; cur = forecasts[day]["curve"]
            gx = [t0 + pd.Timedelta(hours=2 * k) for k in range(len(cur))]
            gy = [o + float(c) / MULT for _, c in cur]
            ax.plot(gx, gy, color="#e8710a", lw=2.0, ls="--", label="guess")
            ax.set_title(f"{forecasts[day].get('dow','')} {day[4:6]}-{day[6:]}  {o:.3f}->{px[-1]:.3f}  "
                         f"[{forecasts[day].get('archetype','')}]", fontsize=9)
            ax.yaxis.tick_right(); ax.tick_params(labelsize=7)
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%H", tz=idx.tz)); ax.xaxis.set_major_locator(mdates.HourLocator(interval=4))
            ax.grid(True, color="#eee", lw=0.6); ax.set_axisbelow(True)
            for sp in ("top", "left"): ax.spines[sp].set_visible(False)
            if i == 0: ax.legend(fontsize=7)
        except Exception as e:
            ax.text(0.5, 0.5, f"{day}\n{str(e)[:60]}", ha="center", va="center", transform=ax.transAxes, fontsize=8)
    for j in range(len(days), len(axes)): axes[j].axis("off")
    fig.suptitle("NG BLIND forecast (dashed) vs ACTUAL (solid) — each day independent, no pooling",
                 fontsize=12, fontweight="bold", y=0.998)
    plt.tight_layout(rect=[0, 0, 1, 0.985]); plt.savefig(out_png, dpi=115, bbox_inches="tight")
    return out_png


def day_reveal(day: str, prior_day: str | None, anchor_day: str, fingerprints_path: str | None,
               closes_so_far: dict | None = None) -> dict:
    """The DAY-SEQUENTIAL rolling-anchor reveal (S96, Greg): after day D's blind forecast is LOCKED, this
    packages day D's ACTUALS for the NEXT day's forecast agent - exactly what a live coach knows the next
    morning. Decision-time-legit (all data is from a completed past session); the blind wall stays intact
    per-day. Mechanical extraction only - counts and values in the brain's fingerprint vocabulary
    (continuation-asymmetry / turn_exhaustion / peaked_fast), no interpretation baked in.
    closes_so_far = {date: close} of the block's already-revealed days (for the block-extreme flag)."""
    import numpy as np, pandas as pd
    import fast_tape
    ts, px = fast_tape.fast_load_day("NG", day)
    if len(px) == 0:
        return {"date": day, "error": "empty day"}
    et = pd.to_datetime(ts, unit="s", utc=True).tz_convert("America/New_York")
    o, c = float(px[0]), float(px[-1])
    a_ts, a_px = fast_tape.fast_load_day("NG", anchor_day)
    anchor_close = float(a_px[-1])
    last = px[et >= et[-1] - pd.Timedelta(hours=1)]
    rev = {"date": day, "dow": DOW[datetime.date(int(day[:4]), int(day[4:6]), int(day[6:])).weekday()],
           "open": round(o, 3), "close": round(c, 3), "net_usd": round((c - o) * MULT),
           "day_hi_usd": round((float(px.max()) - o) * MULT), "day_lo_usd": round((float(px.min()) - o) * MULT),
           "last_hour": {"dir": "up" if len(last) > 1 and last[-1] > last[0] else "down",
                          "net_usd": round((float(last[-1]) - float(last[0])) * MULT) if len(last) > 1 else 0},
           "cum_from_anchor_usd": round((c - anchor_close) * MULT)}
    if prior_day:
        p_ts, p_px = fast_tape.fast_load_day("NG", prior_day)
        if len(p_px):
            rev["overnight_gap_usd"] = round((o - float(p_px[-1])) * MULT)
    if closes_so_far:
        hi_d = max(closes_so_far, key=lambda k: closes_so_far[k]); lo_d = min(closes_so_far, key=lambda k: closes_so_far[k])
        rev["block_closes_so_far"] = {k: closes_so_far[k] for k in sorted(closes_so_far)}
        rev["at_block_extreme"] = ("high" if c >= closes_so_far[hi_d] else
                                    "low" if c <= closes_so_far[lo_d] else None)
    # per-leg turn fingerprint (brain vocabulary) from the day's characterize_day rows, if computed
    if fingerprints_path and os.path.exists(fingerprints_path):
        rows = json.load(open(fingerprints_path)).get(day)
        if isinstance(rows, list) and rows:
            legs = {}
            for dr in ("up", "down"):
                sub = [r for r in rows if r.get("dir") == dr]
                big = [r for r in sub if (r.get("peak_usd") or 0) >= 250]
                legs[dr] = {"n": len(sub), "continued": sum(1 for r in sub if r.get("continuation")),
                            "big_n": len(big), "big_continued": sum(1 for r in big if r.get("continuation")),
                            "peaked_fast": sum(1 for r in sub if r.get("peaked_fast")),
                            "turn_exhaustion_worst": round(min((r.get("turn_exhaustion") or 0) for r in sub), 3) if sub else None}
            rev["legs"] = legs
            rev["legs_note"] = ("per-direction leg counts for the day (brain vocabulary: continuation-"
                                "asymmetry / old-swing continuation-collapse / peaked_fast fades). "
                                "Read with ng_brain fingerprints; counts are THIS day only, never pooled.")
    return rev


def brain_show(path: str = BRAIN) -> None:
    b = json.load(open(path))
    print(f"ng_brain {b['meta']['version']} — {len(b['plays'])} plays:")
    for p in b["plays"]:
        print(f"  [{p['status']:<20}] {p['id']:<28} target={p['target']:<9} conf={p.get('confidence')}")
    print("open_frontier:")
    for o in b["open_frontier"]:
        print("  -", o)


def audit_joins(start_iso: str = "2025-11-03", end_iso: str = "2026-02-27") -> int:
    """(S98 Tier 0, DATA_GATE_S98) BLIND-WALL RE-AUDIT ACROSS ALL decision_state JOINS. Each feed has its
    own publication mechanics; this audits the JOINED view a forecast agent actually receives, per date
    over the walked window. Prints violation counts (must be 0) and per-feed None-coverage with every
    absent date NAMED (gaps individually, never a percentage). Returns the total violation count."""
    d0, d1 = datetime.date.fromisoformat(start_iso), datetime.date.fromisoformat(end_iso)
    days = []
    d = d0
    while d <= d1:
        if d.weekday() < 5 or d.weekday() == 6:   # trade days: Mon-Fri + Sunday sessions
            days.append(d.isoformat())
        d += datetime.timedelta(days=1)
    viol = {"cot_publication": 0, "storage_regional_asof": 0, "structure_session": 0,
            "structure_oi_session": 0, "storage_national": 0, "mos_asof": 0, "consensus_join": 0}
    absent = {"cot": [], "storage_regional": [], "contract_structure": [], "weather_forecast": [],
              "storage_consensus": []}
    ds = decision_state([x.replace("-", "") for x in days])
    for iso in days:
        k = iso.replace("-", "")
        st = ds[k]
        c = st.get("cot")
        if c is None:
            absent["cot"].append(iso)
        elif not (c["publication_ts"][:10] < iso and c["report_date"] < iso):
            viol["cot_publication"] += 1; print(f"  VIOLATION cot {iso}: pub {c['publication_ts']}")
        r = st.get("storage_regional")
        if r is None:
            absent["storage_regional"].append(iso)
        elif not (r["as_of"] < iso):
            viol["storage_regional_asof"] += 1; print(f"  VIOLATION regional {iso}: as_of {r['as_of']}")
        cs = st.get("contract_structure")
        if cs is None:
            absent["contract_structure"].append(iso)
        else:
            if not (cs.get("asof_session") and cs["asof_session"] < iso):
                viol["structure_session"] += 1; print(f"  VIOLATION structure {iso}: asof {cs.get('asof_session')}")
            for oik in ("open_interest_front_session", "open_interest_next_session"):
                if cs.get(oik) is not None and not cs[oik] < iso:
                    viol["structure_oi_session"] += 1; print(f"  VIOLATION structure-OI {iso}: {oik}={cs[oik]}")
        s = st.get("storage")
        if s is not None and not s["as_of"] < iso:
            viol["storage_national"] += 1; print(f"  VIOLATION storage {iso}: as_of {s['as_of']}")
        f = st.get("weather_forecast")
        if f is None:
            absent["weather_forecast"].append(iso)
        elif f.get("asof_utc") and not f["asof_utc"][:10] < iso:
            viol["mos_asof"] += 1; print(f"  VIOLATION mos {iso}: asof {f['asof_utc']}")
        sc = st.get("storage_consensus")
        if sc is None:
            absent["storage_consensus"].append(iso)
        else:
            lp, np_ = sc.get("last_print"), sc.get("next_print")
            # last_print's ACTUAL is knowable only after its print moment - its print_date must be < iso
            # (a print-day 10:30 print never reaches its own open); next_print must be >= iso and carry
            # NO actual (consensus only - the module strips page actuals from post-print captures).
            if lp is not None and not lp["print_date"] < iso:
                viol["consensus_join"] += 1; print(f"  VIOLATION consensus {iso}: last_print {lp['print_date']}")
            if np_ is not None:
                if np_["print_date"] < iso:
                    viol["consensus_join"] += 1; print(f"  VIOLATION consensus {iso}: next_print {np_['print_date']} in past")
                if np_.get("actual_bcf") is not None or np_.get("actual_as_printed_bcf") is not None:
                    viol["consensus_join"] += 1; print(f"  VIOLATION consensus {iso}: next_print carries an actual")
    total = sum(viol.values())
    print(f"[audit-joins] {start_iso}..{end_iso} ({len(days)} trade days) violations: {viol} TOTAL={total}")
    for feed, lst in absent.items():
        if lst:
            print(f"[audit-joins] {feed} absent on {len(lst)} dates (missing==None, named): {','.join(lst)}")
        else:
            print(f"[audit-joins] {feed} present on all {len(days)} dates")
    return total


def _selftest() -> int:
    ds = decision_state(["20250902"])
    assert ds["20250902"]["dow"] == "Tue" and ds["20250902"]["stor_surprise"] is not None, ds
    # (S97 JOB 2.2) the MOS as-of forecast block is ADDITIVE: the realized-proxy `weather` key must survive
    # untouched, and `weather_forecast` must be present-or-None but NEVER a silently-zeroed HDD.
    assert "weather" in ds["20250902"], "regression: realized-proxy weather key was removed"
    wf = decision_state(["20260120"])["20260120"]
    assert "weather" in wf and "weather_forecast" in wf, wf
    f = wf["weather_forecast"]
    if f is not None:
        assert f["forecast_gw_hdd"] is None or f["forecast_gw_hdd"] > 0, "zeroed winter HDD - false signal"
        assert f["forecast_run_delta"] is not None, f
        assert f["asof_utc"].startswith("2026-01-19"), ("blind wall: asof must be D-1", f["asof_utc"])
        print(f"[forecast_harness] mos_asof wired: 20260120 fHDD={f['forecast_gw_hdd']} "
              f"vsNorm={f['forecast_vs_normal']} runDelta={f['forecast_run_delta']} asof={f['asof_utc']}")
    # (S98 Tier 0) the three S97 feeds + squeeze_watch, on the canonical 2026-01-22 divergence day.
    d22 = decision_state(["20260122"])["20260122"]
    for key in ("cot", "storage_regional", "contract_structure", "squeeze_watch"):
        assert key in d22, f"S98 regression: {key} missing from decision_state"
    c = d22["cot"]
    assert c is not None and c["publication_ts"][:10] < "2026-01-22", ("COT blind wall", c)
    assert c["managed_money_net"] is not None and c["managed_money_net_pctile_1y"] is not None, c
    r = d22["storage_regional"]
    assert r is not None and r["as_of"] < "2026-01-22", ("regional blind wall", r)
    assert r["regions"]["south_central_salt"]["level"] is not None, ("salt missing", r)
    cs = d22["contract_structure"]
    assert cs is not None and cs["asof_session"] == "2026-01-21", cs
    # THE REASON THE FEED EXISTS: the OI front hides the squeeze the calendar front shows (S97 finding).
    assert abs(cs["front_next_spread"] - 0.093) < 1e-9, cs["front_next_spread"]
    assert abs(cs["calendar_front_next_spread"] - 1.539) < 1e-9, cs["calendar_front_next_spread"]
    sw = d22["squeeze_watch"]
    assert sw["active"] is True and sw["days_to_calendar_front_expiry"] == 4, sw
    assert d22["curve_regime"] != "unknown", "S97 gate item 12: curve_regime still 'unknown'"
    # (S98 feed D) the survey consensus on the 0129 motivating case: the print-day morning sees its OWN
    # print's consensus (public pre-print), never an actual; the prior print arrives realized.
    d29 = decision_state(["20260129"])["20260129"]
    scb = d29["storage_consensus"]
    assert scb is not None and scb["next_print"]["print_date"] == "2026-01-29", scb
    assert scb["next_print"]["consensus_chg_bcf"] is not None, scb
    assert scb["next_print"].get("actual_bcf") is None and scb["next_print"].get("actual_as_printed_bcf") is None, \
        "consensus block leaked an actual into its own print morning"
    assert scb["last_print"]["print_date"] == "2026-01-22" and scb["last_print"].get("surprise_vs_consensus_bcf") is not None, scb
    # missing-is-explicit: a pre-coverage date carries None blocks, never zeros.
    d_old = decision_state(["20250902"])["20250902"]
    assert d_old["contract_structure"] is None or d_old["contract_structure"].get("front_next_spread") != 0, d_old
    # the information clock rides ONCE as a leading meta key, and day keys still index cleanly.
    full = decision_state(["20260122"])
    assert "_information_clock" in full and "20260122" in full, list(full)
    print(f"[forecast_harness] S98 wired: 20260122 cot MM net={c['managed_money_net']} "
          f"pctile1y={c['managed_money_net_pctile_1y']} | salt={r['regions']['south_central_salt']['level']} "
          f"| cal_spread={cs['calendar_front_next_spread']} (oi-front {cs['front_next_spread']}) "
          f"| squeeze_watch={sw['active']} | curve_regime={d22['curve_regime']}")
    brain_show()
    print("[forecast_harness] selftest PASS")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    a1 = sub.add_parser("decision-state"); a1.add_argument("--days", required=True); a1.add_argument("--out")
    a2 = sub.add_parser("overlay"); a2.add_argument("--forecasts", required=True); a2.add_argument("--out", required=True); a2.add_argument("--source", default="s3")
    sub.add_parser("brain-show")
    a3 = sub.add_parser("reveal"); a3.add_argument("--day", required=True); a3.add_argument("--prior")
    a3.add_argument("--anchor", required=True); a3.add_argument("--fingerprints")
    a3.add_argument("--closes")   # json string {date: close} of the block's revealed days so far
    a3.add_argument("--out")      # merge into this json {date: reveal}
    a4 = sub.add_parser("audit-joins")   # S98 Tier 0: blind-wall re-audit across ALL joins
    a4.add_argument("--start", default="2025-11-03"); a4.add_argument("--end", default="2026-02-27")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return _selftest()
    if a.cmd == "audit-joins":
        return 1 if audit_joins(a.start, a.end) else 0
    if a.cmd == "decision-state":
        ds = decision_state(a.days.split(","))
        print(json.dumps(ds, indent=1))
        if a.out: json.dump(ds, open(a.out, "w"))
        return 0
    if a.cmd == "overlay":
        p = render_overlay(json.load(open(a.forecasts)), a.out, source=a.source)
        print("wrote", p); return 0
    if a.cmd == "brain-show":
        brain_show(); return 0
    if a.cmd == "reveal":
        rev = day_reveal(a.day, a.prior, a.anchor, a.fingerprints,
                         json.loads(a.closes) if a.closes else None)
        print(json.dumps(rev, indent=1))
        if a.out:
            allrev = json.load(open(a.out)) if os.path.exists(a.out) else {}
            allrev[a.day] = rev
            json.dump(allrev, open(a.out, "w"), indent=1)
        return 0
    ap.print_help(); return 1


if __name__ == "__main__":
    sys.exit(main())
