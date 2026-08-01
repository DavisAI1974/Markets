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
    "2026-06-19": ("Juneteenth", "closed"),          "2026-07-03": ("Independence_Day_obs", "closed"),
    # S98 correction (feed F, verified vs the CME calendar + contract_structure's holiday set):
    # 2026-07-03 is a FULL CME holiday/non-business-day, not an early close. Note also that
    # "closed" days like Memorial/Juneteenth can carry a partial no-settlement Globex session
    # (the S96 Thanksgiving correction generalizes) - business-day COUNTING authority is the
    # flow_calendar feed, not this day-type tag dict.
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
        # S109 THE HDD-ONLY LADDER. nws_temp_feed computes forecast_gw_cdd at EVERY horizon (see its
        # header: "forecast_gw_hdd / forecast_gw_cdd - gas-weighted, for target D and each horizon out to
        # D+7") and this assembly dropped it, exactly as S107 defect 3 dropped big_print_b_share. The
        # cost is not a missing nicety: in a JULY block CDD is the entire demand signal, and with only
        # HDD served the whole HDD-keyed play family degrades ONE WAY. Measured on G22, where realized
        # CDD ran 9.0 -> 18.7 while forecast_gw_hdd sat at 0.03-0.30:
        #   selector.divergence_resolution's catalyst override needs HDD >= 16.4 - unreachable in
        #     summer, so it never fires and the selector silently defaults to the bearish angle;
        #   magnitude.shoulder_weather_band_void needs HDD <= ~13.5 - trivially satisfied, so it VOIDS
        #     the weather band on every summer day;
        #   and both weekend-add delta channels read ~0 against a +4.7 CDD add.
        # Four independent artifacts, every one leaning the same way, none of them a signal. Specialist
        # B named this mechanism in its 0629 posterior BEFORE the block was scored; the blind then came
        # in with four days called down that printed up and a drift of -1815. Served additively so
        # empirically-fitted HDD bars keep reading exactly what they read before.
        "horizons": [{k: h[k] for k in ("horizon", "target_date", "forecast_gw_hdd", "forecast_vs_normal",
                                        "partial", "coverage")}
                     | ({"forecast_gw_cdd": h["forecast_gw_cdd"]} if "forecast_gw_cdd" in h else {})
                     for h in r.get("horizons", [])],
        "run_delta": [{k: h[k] for k in ("horizon", "target_date", "d_gw_hdd", "partial", "coverage")}
                      | ({"d_gw_cdd": h["d_gw_cdd"]} if "d_gw_cdd" in h else {})
                      for h in r.get("run_delta", [])],
        "fwd7_gw_cdd_span": r.get("fwd7_gw_cdd_span"),
        "ladder_basis_note": (
            "S109: forecast_gw_cdd / d_gw_cdd are served ALONGSIDE the HDD ladder, never replacing it. "
            "In a summer block CDD is the demand signal and HDD is inert - a play stating an ABSOLUTE "
            "HDD bar (divergence_resolution 16.4, shoulder_weather_band_void 13.5) is UNEVALUABLE in "
            "summer, not satisfied and not refuted. Treat an unreachable HDD bar as UNKNOWN; do not let "
            "it default the selector to a direction."),
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
    # (S98 feed H) the futures-AND-OPTIONS-COMBINED variant + the derived OPTIONS-IMPLIED delta
    # (combined minus futures-only, per field) - additive, suffixed, same publication wall. The two
    # books can sit at OPPOSITE extremes: at the G11 open futures-only MM net was at the 2.83rd 1-yr
    # percentile while the options-implied read was at the 97.17th.
    import cot_combined_feed
    comb = cot_combined_feed.cot_combined_asof(iso)
    if comb:
        c = c | comb
    # (S100, Greg: "as long as the ice data is free do it") the FOUR ICE Futures Energy Div HH
    # books from the SAME CFTC files - free, additive, each book carried SEPARATELY (never pooled;
    # LD1/PEN echo the NYMEX crowd on twin contracts; BASIS/INDEX are the physical legs - the
    # squeeze-regime context read). Weekly cadence: positioning context, never intraday.
    ice = {}
    for key, code in (("ld1", "023391"), ("pen", "023392"),
                      ("hh_basis", "0233AG"), ("hh_index", "0233AH")):
        r = cot_feed.cot_asof(iso, contract_code=code)
        ice[key] = (None if not r else {
            "report_date": r["report_date"], "publication_ts": r["publication_ts"],
            "open_interest": r["open_interest"], "managed_money_net": r["managed_money_net"],
            "managed_money_net_chg_wow": r["managed_money_net_chg_wow"],
            "managed_money_net_pctile_1y": r["managed_money_net_pctile_1y"],
            "managed_money_net_pctile_3y": r["managed_money_net_pctile_3y"]})
    return c | {"ice": ice,
                "note": "positioning as-of PUBLICATION time; futures-only + _combined + the derived "
                        "_options_implied delta + the four ICE HH books under `ice` (separate reads, "
                        "never pooled; basis/index = the physical legs, squeeze-regime context); "
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


def _squeeze_watch(cs: dict | None, iso: str | None = None) -> dict | None:
    """(S98 Tier 0, DATA_GATE_S98 0b family DEL) Derived convenience read - transparently from the wired
    structure fields, components exposed alongside so the agent reads both. None = components unknown
    (never False-when-unknown): a cross-roll day zeroes nothing, it says 'unknown'.
    S101.5 ADDITIVE (brain s101.3 item 9, from G12's 0201): PROMPT-EXPIRY fields + the dead-sponsor
    UNWIND arm. squeeze_watch keyed only on the LIVE calendar front and was structurally blind to a
    just-expired prompt's premium unwinding (Feb expired Jan 28 at 7.460; the -7080 0201 gap was the
    unwind). last_prompt_* names the most recent expiry; unwind_watch flags <=3 sessions since it -
    a READ, not a gate; magnitude.block_gap_ownership owns what it means."""
    if not cs:
        return None
    d2e = cs.get("days_to_calendar_front_expiry")
    chg3 = cs.get("calendar_front_next_spread_chg_3d")
    active = None if (d2e is None or chg3 is None) else bool(d2e <= 7 and chg3 > 0)
    out = {"active": active,
           "days_to_calendar_front_expiry": d2e,
           "calendar_front_next_spread": cs.get("calendar_front_next_spread"),
           "calendar_front_next_spread_chg_3d": chg3,
           "calendar_front_symbol": cs.get("calendar_front_symbol"),
           "note": "derived: days_to_calendar_front_expiry<=7 AND calendar_front_next_spread_chg_3d>0. "
                   "Inside this window delivery mechanics own the tape (DATA_GATE_S98 0b: demand-regime "
                   "bands are out of scope); G11's 0122-0130 is the n=1, G13 the forward test"}
    if iso:
        try:
            import datetime as _dt
            import flow_calendar as _fcal
            day = _dt.date.fromisoformat(iso)
            prev_sym = prev_exp = None
            y, m = day.year, day.month + 2           # delivery month M expires in M-1: start ahead, walk back
            if m > 12:
                m, y = m - 12, y + 1
            for _ in range(5):                       # walk back until the most recent expiry strictly before iso
                exp = _fcal.ng_expiry(y, m)
                if exp < day:
                    prev_sym, prev_exp = _fcal.ng_symbol(y, m), exp
                    break
                m -= 1
                if m == 0:
                    m, y = 12, y - 1
            # S108 THE CONFIDENT FALSE NEGATIVE. `active` is derived from contract_structure, which is
            # PRICE-DERIVED and therefore FROZEN at the anchor vintage in blind mode - so the whole block
            # reports the anchor day's days-to-expiry and `active: false` on every day. On G21 that read
            # dte=14 / active=false while the live calendar said dte=7 on 0616, 6 on 0617, 5 on 0618 and
            # 5 on 0619: the block sat INSIDE the play's own <=7 window and the flag denied it, on four
            # separate days. C and A found it independently and both used the live calendar instead.
            #
            # But only ONE of the two limbs is genuinely price-derived. `days_to_calendar_front_expiry`
            # is DETERMINISTIC CALENDAR and needs no mask; only `calendar_front_next_spread_chg_3d` does.
            # So derive the calendar limb LIVE here and say so. Additive: `active` keeps its name, type
            # and value so nothing downstream is silently re-pointed - what is added is the truth
            # alongside it, and an explicit false-negative flag when the two disagree. This is the same
            # stale-block family as frozen_structure_stale, and state_health cannot catch it because the
            # block is populated and internally consistent.
            fy, fm = day.year, day.month
            live_d2e = live_sym = None
            for _ in range(6):                       # walk FORWARD to the nearest expiry on/after iso
                exp_f = _fcal.ng_expiry(fy, fm)
                if exp_f >= day:
                    live_d2e, live_sym = _fcal.bd_between(day, exp_f), _fcal.ng_symbol(fy, fm)
                    break
                fm += 1
                if fm == 13:
                    fm, fy = 1, fy + 1
            if live_d2e is not None:
                cal_live = bool(live_d2e <= 7)
                out |= {"days_to_calendar_front_expiry_live": live_d2e,
                        "calendar_front_symbol_live": live_sym,
                        "calendar_limb_satisfied_live": cal_live,
                        "calendar_limb_basis": ("days_to_calendar_front_expiry_live is DETERMINISTIC "
                                                "CALENDAR from flow_calendar and is never masked; the "
                                                "spread limb is the only genuinely price-derived half. "
                                                "Prefer the live value over the frozen one.")}
                if cal_live and out.get("active") is False:
                    out["active_false_negative"] = (
                        f"active=false is NOT decision-legit here: the frozen vintage reports "
                        f"days_to_calendar_front_expiry={d2e} while the LIVE calendar says {live_d2e} "
                        f"- inside the play's own <=7 window. Only the spread limb is unknown, so treat "
                        f"active as UNKNOWN, not absent. Take the note's SCOPE consequence (delivery "
                        f"mechanics own the tape) and its TAIL consequence, and do not read a squeeze "
                        f"into the p50 on a limb you cannot see.")
            if prev_exp is not None:
                sessions_since = _fcal.bd_between(prev_exp, day)
                out |= {"last_prompt_symbol": prev_sym,
                        "last_prompt_expiry": prev_exp.isoformat(),
                        "sessions_since_prompt_expiry": sessions_since,
                        "unwind_watch": bool(sessions_since <= 3),
                        "unwind_note": "dead-sponsor arm (s101.3 item 9): a prompt expiry within ~3 sessions "
                                       "with premium stranded in the front is the block_gap_ownership "
                                       "structural condition; the flag is a read, the agent decides"}
        except Exception:
            out |= {"last_prompt_symbol": None, "last_prompt_expiry": None,
                    "sessions_since_prompt_expiry": None, "unwind_watch": None,
                    "unwind_note": "prompt-expiry lookup failed - unknown, never False"}
    return out


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


def _model_disagreement_block(iso: str) -> dict | None:
    """(S98 feed C) MODEL DISAGREEMENT as the forecast-uncertainty proxy - GFS-MAV vs NAM-MET
    gas-weighted HDD spread per MATCHED horizon (the overlap is short-range, h0-h1), plus the
    per-model run-to-run stability split (WHICH model moved). The market prices uncertainty, not
    just the central case: G11's 0125/0126 whipsaw ran on a wobbling forecast. Same D-1-evening
    as-of discipline as the MOS block; module self-audits."""
    import model_disagreement as md
    m = md.model_disagreement_asof(iso)
    if not m:
        return None
    return m | {"note": "uncertainty conditioner; per-horizon rows canonical, the summary is a "
                        "shape descriptor never a pooled conclusion; no-overlap horizons are None"}


def _ngwu_block(iso: str) -> dict | None:
    """(S98 feed N) The EIA weekly S/D balance (NGWU -> WNGSR-Supplement eras). HONEST STRUCTURAL
    LIMIT (measured): EIA removed the S&P supply/demand section 2025-10-02, so the walked winter has
    NO free weekly balance LEVELS - the block carries the last live levels (week ending 2025-09-24)
    with honest age, era-2 LSEG narrative w/w deltas where published, and the one line continuous
    through BOTH eras: LNG vessel departures/capacity (the squeeze week ending Jan 28 is the winter
    low, 31 vessels / 118 Bcf). Missing levels are None + attribution named; module self-audits 0
    violations on knowable_from = release+1."""
    import ngwu_feed
    n = ngwu_feed.ngwu_asof(iso)
    if not n:
        return None
    return n | {"note": "free weekly balance; LEVELS dead after 2025-09-24 (named gap - strengthens "
                        "the feed J paid-arm question); vessel line continuous; deltas as stated, "
                        "never derived"}


def _steo_vintage_block(iso: str) -> dict | None:
    """(S99 feed T) STEO monthly VINTAGES - the complete NG balance as-of each monthly release
    (frozen archive workbooks; the live API is current-vintage-only). Dry production, consumption
    by sector, LNG/pipeline trade, net withdrawals, working gas - at honest 1-34d staleness, joined
    on MEASURED release dates (knowable_from = release+1; workbook Last-Modified leads release by
    3-6d and is NEVER used). Vintage-to-vintage revision deltas ride with the read - the
    Jan-13 -> Feb-10 pair brackets the freeze re-mark (+5.95 Bcf/d Jan consumption, -137 Bcf
    end-Jan inventory), landing mid-G12 as a readable revision."""
    import steo_vintage as stv
    s = stv.steo_vintage_asof(iso)
    if not s:
        return None
    return s | {"note": "monthly as-of balance consensus (STIFS estimates, as-printed, frozen per "
                        "issue - zero vintage risk by construction); revisions_vs_prev_vintage is "
                        "the first-appearance-vs-revision signal; scope sep25..mar26 vintages, "
                        "apr26+ joins only after its release dates are measured"}


def _storage_vintage_block(iso: str) -> dict | None:
    """(S98 feed K) The AS-PRINTED storage vintage overlay - what the market actually saw at each print
    vs the current revised series the stores carry. The walk's whole vintage look-ahead resolved to ONE
    EIA revision event (published 2026-04-23, AFTER the walked winter): a Mountain base-gas
    reclassification of ~10 Bcf/week across 33 weeks. as_printed is what was knowable; current is what
    the modern series says; deltas named. Recovered from in-window Wayback captures of EIA's own report
    page; module self-audits 0 violations."""
    import storage_vintage as sv
    v = sv.storage_vintage_asof(iso)
    if not v:
        return None
    return v | {"note": "as_printed = decision-time truth; the current-vintage `storage`/`storage_regional` "
                        "blocks run 9-12 Bcf BELOW market-known LEVELS across the walked winter (Mountain "
                        "reclass); net CHANGES match within +-1 except the named Sep 4 print (+55 printed "
                        "vs +45 current)"}


def _solar_block(iso: str) -> dict | None:
    """(S98 feed P, Greg: "do we have sun up/sun down") Sunrise/sunset/day-length per demand metro +
    gas-weighted day length and its 7d change. Pure astronomy, forward-known, no blind wall. Channels
    (recorded, agent decides): the sunset power-burn ramp (solar collapses at sunset, gas peakers pick
    up - the duck-curve neck, strongest ERCOT/CAISO) and day length as the seasonal demand-shape
    descriptor."""
    import solar_calendar
    p = solar_calendar.solar_asof(iso)
    if not p:
        return None
    return p | {"note": "deterministic solar state; sunset_et positions the evening gas-burn ramp on "
                        "the session clock; gw_day_length_chg_7d is the seasonal march"}


def _nuclear_outages_block(iso: str) -> dict | None:
    """(S99 feed R arm 1) U.S. nuclear capacity offline, daily (EIA nuclear-outages API,
    2007->present). Nuclear GW offline adds gas burn roughly GW-for-GW at the margin; shoulder
    seasons are refueling seasons; and the walked winter's freeze window carried a measured
    1.8 -> 3.2 GW outage jump across Jan 17-18 - extra implied gas demand arriving DURING the
    squeeze build-up, invisible to the agent until now. Wall: knowable_from = period+1,
    strictly-prior join; changes across real series gaps are None, never bridged."""
    import nuclear_outages as no
    n = no.nuclear_outages_asof(iso)
    if not n:
        return None
    return n


def _options_surface_block(iso: str) -> dict | None:
    """(S99 feed I phase i - REQUIRED FOR G13) NG options OI pin map: the two nearest live option
    months (ON+LNE combined per strike, per-asset splits kept), top-5 OI walls with concentrations,
    P/C totals, OI-weighted strike, and the opex clock. Options expire the business day BEFORE
    futures expiry - the pin/unpin boundary G13 carries (opex Feb 24 / expiry Feb 25). Distance
    from settle is the agent's read against contract_structure's calendar-front settle. Wall: CME
    next-morning publication, session strictly prior."""
    import options_surface as osf
    o = osf.options_surface_asof(iso)
    if not o:
        return None
    return o


def _grid_stack_block(iso: str) -> dict | None:
    """(S99 feed Q) EIA-930 daily grid stack per BA - demand (loads), the BA's own DAY-AHEAD demand
    forecast (leading, free), and generation by fuel: gas share, solar displacement measured. The
    freeze's power-burn ramp (est 28.3 -> 41.1 Bcf/d across G11's build-up) was visible daily at
    this wall while every other demand read was weekly-or-slower. US48 carries the labeled
    power-burn ESTIMATE (stated method); per-BA always, never pooled. Wall: knowable_from =
    period + 2 (measured worst case)."""
    import grid_stack as gs
    g = gs.grid_stack_asof(iso)
    if not g:
        return None
    return g


def _flow_calendar_block(iso: str) -> dict | None:
    """(S98 feed F) The FLOW CALENDAR - deterministic scheduled-flow state: futures/options expiry
    clocks, bidweek, GSCI/BCOM index-roll windows, the EIA release datetime for the week (holiday
    shifts encoded from the PUBLISHED schedule - Veterans week slips to FRIDAY, Christmas week slips
    LATE to Mon Dec 29), CME holiday classes. Fully forward-known; no blind wall needed. Counting
    authority for business days is this feed (see FLOW_CALENDAR_NOTES_S98.md disagreement log)."""
    import flow_calendar as fcal
    f = fcal.flow_calendar_asof(iso)
    if not f:
        return None
    return f | {"note": "mechanical scheduled flows - desks trade around these; G13 carries the full "
                        "gauntlet (GSCI roll Feb 6-12, BCOM Feb 9-13, bidweek Feb 23-27, opex Feb 24, "
                        "expiry Feb 25)"}


def _cash_basis_block(iso: str) -> dict | None:
    """(S98 feed G) Henry Hub CASH vs front-settle basis - the free sliver of the physical market, the
    ground truth paper converges to in delivery stress. LOAD-BEARING PUBLICATION FACT (measured): the
    'daily' spot publishes in WEEKLY batches (NGWU era -> WNGSR-Supplement era from Jan 2026) with
    holiday blackouts up to 22 days - joins key on knowable_from = release+1, so this is a WEEKLY-REFRESH
    regime-state variable at 2-9d staleness (age_days ships with every read). A naive T+1 join would have
    leaked the Jan 2026 cash blowout a week early. Module self-audits 0 violations."""
    import cash_basis as cb
    c = cb.cash_basis_asof(iso)
    if not c:
        return None
    return c | {"note": "physical delivery-stress gauge at weekly staleness; basis changes are None "
                        "across gaps and rolls, never bridged; on 2026-01-30 the knowable basis was "
                        "+10.77 with chg_3d +7.29 - the squeeze visible decision-time-legit"}


def _vol_regime_block(iso: str) -> dict | None:
    """(S98 feed B) The VOL / RANGE REGIME conditioner - trailing realized vol of session nets, range
    means/percentile, activity trend, computed strictly from prior sessions on BOTH tape bases (n0_/v0_
    fields, never mixed; a basis with no tape is None per field with win_n exposing partial windows).
    CONDITIONS magnitude expectations (the walk's dominant residual - bands calibrated in one vol regime
    applied in another); never calls direction. Module self-audits 0 blind-wall violations."""
    import vol_regime as vr
    v = vr.vol_regime_asof(iso)
    if not v:
        return None
    return v | {"note": "magnitude conditioner only; n0/v0 bases never mixed (same-window v0 sigma can "
                        "read 3x n0 across the G11 expiry week - the basis IS the difference); "
                        "None = insufficient prior sessions on that basis, never calm"}


def _mos_cycle_block(iso: str) -> dict | None:
    """(S100 feed A phase 1) hour-resolution CYCLE-LEVEL MOS as-of, additive beside weather_forecast.
    weekday_open = what was available at 08:00 ET on D, with per-horizon deltas vs the D-1-evening
    state (the overnight cycles' add). sunday_reopen (Mondays only) = what was available BEFORE the
    Sun 18:00 ET reopen, deltas vs Saturday evening = the weekend cycles' add - the information the
    0118 +2100 / 0125 +2480 gaps priced (measured: the Jan-24 +8.511 add was reopen-available).
    Availability wall: cycle usable from runtime + 4.5h (conservative; posting stamps unrecoverable
    from the IEM archive - named limitation). None = store absent for the day, never zeros."""
    try:
        import mos_cycle_feed
    except Exception:
        return None
    rec = mos_cycle_feed.mos_cycle_asof(iso)
    if rec is None:
        return None

    def _compact(view):
        if not view:
            return None
        hs = view["horizons"]
        d0 = hs[0]
        stamps = [rt.split("@")[-1] for h in hs for rt in (h.get("cycle_by_metro") or {}).values()]
        return {"asof_utc": view["asof_utc"], "asof_et": view["asof_et"],
                "gw_hdd_d0": d0["gw_hdd"], "vs_normal_d0": d0["forecast_vs_normal"],
                "regime_d0": d0.get("regime"),
                "max_cycle_runtime_utc": (max(stamps) if stamps else None),
                # S109, found by specialist B on 0629. This is the SECOND, INDEPENDENT weekend-add
                # channel that was HDD-only - and it is the one built for precisely this job, labelled
                # decision-time-legit for Mondays. On 20260629 sunday_reopen reported d_gw_hdd +0.096
                # against a realized weekend CDD add of +4.7. Both purpose-built weekend-delta channels
                # therefore read ~zero while the LEVEL channels read the block's largest add of the
                # week. Serve the CDD delta and the D0 level beside the HDD ones.
                "gw_cdd_d0": d0.get("gw_cdd"),
                "delta_vs_prior_by_horizon": [
                    {"target": h["target_date"],
                     "d_gw_hdd": (h.get("delta_vs_prior") or {}).get("d_gw_hdd"),
                     "d_gw_cdd": (h.get("delta_vs_prior") or {}).get("d_gw_cdd")} for h in hs],
                # S109, the general finding from the clean 0629 bridge: a RUN delta baselines against
                # the previous model RUN, not the previous SESSION. Across a weekend spanning 4-8
                # cycles the accumulation is spread thin and appears in no single delta - measured
                # -0.219 on 0629 against a +4.7 LEVEL move, with the whole block's run-delta series
                # inside a +1.05/-0.50 noise band while the level ran 10.08 -> 14.82. The delta channel
                # is STRUCTURALLY BLIND ACROSS A SEAM and gets the sign wrong. Across any weekend or
                # holiday boundary, difference the LEVELS; the deltas are for intra-week use only.
                "seam_delta_warning": ("run deltas baseline run-over-run, NOT session-over-session. "
                                       "Across a weekend/holiday seam use the LEVEL difference "
                                       "(gw_cdd_d0 here vs the prior session's), never these deltas."),
                "availability_rule": view["availability_rule"]}

    out = {"weekday_open": _compact(rec.get("weekday_open")),
           "note": ("cycle-level as-of (feed A ph1): weekday_open deltas = the overnight cycles vs the "
                    "D-1-evening state; sunday_reopen (Mondays) = the weekend cycles' add available "
                    "BEFORE the Sun 18:00 ET reopen, decision-time-legit")}
    if rec.get("sunday_reopen"):
        out["sunday_reopen"] = _compact(rec["sunday_reopen"])
    return out


def _freeze_risk_block(iso: str) -> dict | None:
    """(S100 feed E) producing-basin forecast MIN temps, cycle as-of (feed A discipline). Deep cold
    CUTS SUPPLY while raising demand - the convexity mechanism the demand-only weather blocks miss.
    Temps only; thresholds are data (20/15/10F), never tuned; no synthesized Bcf impact."""
    try:
        import freeze_risk_feed
    except Exception:
        return None
    rec = freeze_risk_feed.freeze_risk_asof(iso)
    if rec is None:
        return None

    def _compact(v):
        if not v:
            return None
        out = {"asof_utc": v["asof_utc"], "asof_et": v["asof_et"], "basins": {}}
        for st, b in v["basins"].items():
            out["basins"][st] = {"basin": b["basin"],
                                 "tmin_d0_f": b["horizons"][0]["tmin_f"],
                                 "tmin_by_horizon": [h["tmin_f"] for h in b["horizons"]],
                                 "thresholds_f": b["thresholds_f"],
                                 "max_cycle_runtime_utc": b["max_cycle_runtime_utc"]}
        return out

    out = {"weekday_open": _compact(rec.get("weekday_open")),
           "note": ("feed E: basin freeze-off MIN temps as-of the same cycle wall as "
                    "weather_forecast_cycle; the agent decides what sub-threshold runs mean")}
    if rec.get("sunday_reopen"):
        out["sunday_reopen"] = _compact(rec["sunday_reopen"])
    return out


_PRICE_DERIVED_BLOCKS = ("contract_structure", "squeeze_watch", "vol_regime", "cash_basis", "options_surface")

# ---- tape_conditions (S102, Greg's OPEN-CONDITIONS directive): NON-PRICE market conditions of the
# PRIOR session, served LIVE even under the one-shot mask. The blind forecasts price from market
# conditions - it sees everything the market generated except the price curve itself (settles, nets,
# levels, spreads stay behind _PRICE_DERIVED_BLOCKS). Contents: activity (trades/volume/rate),
# participation (zigzag leg count, $150 trigger - the month_characterize TRIG), aggressor balance
# (session B-share; big prints >= 25 lots), all UNSIGNED-or-flow quantities, never a price or return.
# Source file = the more-active of the n0/n1 continuation stores for that day (front proxy, basis-
# robust). Missing file -> None with the absence named (missing==None doctrine).
_TAPE_DIRS = (os.path.join(HERE, "..", "..", "data", "nymex_cont_n0"),
              os.path.join(HERE, "..", "..", "data", "nymex_cont_n1"))
_tape_cond_cache: dict = {}


_ACTIVE_LEGS = None      # S108: set by decision_state(group=) so the tape read knows the SCORED contract


def _leg_store_for(ymd: str):
    """The per-contract leg this session should be measured on, if a group context was supplied."""
    if not _ACTIVE_LEGS:
        return None
    try:
        import group_config as gc
        return gc.leg_for(_ACTIVE_LEGS, ymd)
    except Exception:
        return None


def _tape_day_stats(ymd: str) -> dict | None:
    _leg = _leg_store_for(ymd)
    _ck = (ymd, _leg)
    if _ck in _tape_cond_cache:
        return _tape_cond_cache[_ck]
    import gzip as _gz
    best = None
    # S108 HOLE #8 CORRECTION. The loop below selects whichever CONTINUOUS store has more trades, which
    # after a roll is the DEFERRED contract - so the flow read silently switched instrument while the
    # group went on forecasting the front leg (G21: 18-60% of the real tape, signed flow sign-flipped).
    # Selecting better between the continuous stores cannot fix it, because on the affected sessions
    # NEITHER contains the tape (n0 6,262 and n1 5,554 against a leg of 34,221). So when a group context
    # is known, read the SCORED LEG itself and skip the guessing entirely. Falls back to the old path
    # when no group is supplied, so every existing caller behaves exactly as before.
    if _leg:
        try:
            import tape_reconcile as _tr
            _lt = _tr.load_leg_trades(_leg, ymd)
        except Exception:
            _lt = None
        if _lt:
            _ts, _px, _sz, _sd = _lt
            best = (len(_ts), f"leg:{_leg}", _ts, _px, _sz, _sd)
    for dpath in ([] if best is not None else _TAPE_DIRS):   # leg is authoritative; never overridden
        p = os.path.join(dpath, f"NG_{ymd}.jsonl.gz")
        if not os.path.exists(p):
            continue
        ts, px, sz, sd = [], [], [], []
        with _gz.open(p, "rt") as fh:
            for line in fh:
                if '"action": "T"' not in line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if r.get("action") != "T" or r.get("price") is None:
                    continue
                ts.append(float(r["ts"])); px.append(float(r["price"]))
                sz.append(float(r.get("size") or 0)); sd.append(r.get("side"))
        if not ts:
            continue
        if best is None or len(ts) > best[0]:
            best = (len(ts), dpath, ts, px, sz, sd)
    if best is None:
        _tape_cond_cache[_ck] = None
        return None
    n, dpath, ts, px, sz, sd = best
    order = sorted(range(n), key=lambda i: ts[i])
    ts = [ts[i] for i in order]; px = [px[i] for i in order]
    sz = [sz[i] for i in order]; sd = [sd[i] for i in order]
    # S109 SIDE-ENCODING COLLISION. The two readers that can fill `best` disagree about how a side is
    # spelled: the continuous reader appends the RAW TAPE STRING ("B"/"A"/"N"), while the S108 leg
    # reader (tape_reconcile.load_leg_trades) appends flow_read's SIGNED INT (1/-1/0) - and claimed in
    # its docstring to map "exactly as the continuous reader maps it". Every test below is `s == "B"`,
    # so on the leg path NOTHING matched: buys summed to 0 and session_b_share served a hard 0.0 on
    # every scored-leg session of G22 and G23 (8 days each, plus both prior_full_session limbs).
    # It survived because the OTHER b_share fields are overwritten from flow_read in _tape_enrich and
    # session_b_share was the one field missing from that copy list - so only the broken one showed.
    # Normalize to the string convention here so BOTH paths compute the same quantity from the same math.
    sd = [("B" if s == 1 else "A" if s == -1 else "N") if isinstance(s, int) else s for s in sd]
    if ts and ts[0] > 1e15:
        ts = [t / 1e9 for t in ts]
    span_min = max((ts[-1] - ts[0]) / 60.0, 1.0)
    buys = sum(z for z, s in zip(sz, sd) if s == "B")
    tot = sum(sz) or 1.0
    bigs = [(z, s) for z, s in zip(sz, sd) if z >= 25]
    big_b = sum(1 for z, s in bigs if s == "B")
    # zigzag legs, $0.015 trigger (prices used internally; only the COUNT is served)
    legs, ext, ext_dir = 0, px[0], 1   # seed dir arbitrary; first flip corrects it (count +-1 at start)
    for p_ in px[1:]:
        if ext_dir >= 0 and p_ > ext:
            ext = p_
        elif ext_dir <= 0 and p_ < ext:
            ext = p_
        if ext_dir >= 0 and ext - p_ >= 0.015:
            legs += 1; ext_dir = -1; ext = p_
        elif ext_dir <= 0 and p_ - ext >= 0.015:
            legs += 1; ext_dir = 1; ext = p_
    out = {"session": ymd, "source_store": os.path.basename(dpath),
           "n_trades": n, "volume_lots": int(tot), "trades_per_min": round(n / span_min, 1),
           "session_b_share": round(buys / tot, 3),
           "big_prints_n": len(bigs), "big_print_b_share": round(big_b / len(bigs), 3) if bigs else None,
           "leg_count_150": legs,
           "note": "NON-PRICE tape conditions of this session; open-conditions protocol (S102) - "
                   "served live under the one-shot mask; no price/return content"}
    _tape_cond_cache[_ck] = out
    return out


def _tape_conditions_block(iso: str) -> dict | None:
    """Prior TRADE session's non-price flow read, decision-time legit at iso's open. S105 data doctrine:
    the FULL kitchen-sink flow read (signed-flow imbalance + UNBALANCED SIDES by phase, big-print imbalance,
    L1 book quote imbalance + spread) - all NON-PRICE. The blind gets every market FORCE, masked only on
    price. Enriched from flow_read.py; the reduced fields (b_share, big_prints, leg_count) are kept."""
    d = datetime.date(int(iso[:4]), int(iso[5:7]), int(iso[8:10]))
    for back in range(1, 6):
        prev = d - datetime.timedelta(days=back)
        ymd = prev.strftime("%Y%m%d")
        st = _tape_day_stats(ymd)
        if st is not None:
            out = _tape_enrich(prev, ymd, st)
            # S108: THE MONDAY STUB. This loop returns the FIRST day with a tape file, so on a Monday it
            # stops at the ~2h SUNDAY reopen and the FRIDAY - the last full session - is never consulted.
            # Measured across every staged group, a Monday's prior session carried 78-1,245 trades with
            # 0-2 big prints and no L1 book, against 30,000-58,000 trades and 49-288 big prints on every
            # other day: 0.2%-3% of a normal tape. Doctrine puts DIRECTION on the D-1 trade tilt, so on the
            # one day class the walk declares its focus, the blind had almost no tilt to read - which is
            # why B has no independent read of E's Friday exit, and why Mondays run a -465 mean signed
            # error across G17-G20 (second worst after Thursday's -692).
            #
            # The Sunday stub is NOT discarded: it is the gap-forming session (A, G20 - the 05-24 stub's
            # uniform sell lean across all three sub-phases is what signed the -240 gap), and the Sunday
            # fold already assigns it to Monday. So carry BOTH, each labelled, and let the specialist
            # choose - the kitchen-sink doctrine, not a substitution.
            #
            # A stub is identified by the CME trade-date convention (the reopen falls on a Sunday), not by
            # a trade-count threshold: every stub measured across G20/G21/G22 is a Sunday, and a calendar
            # test cannot drift the way a magic number can.
            if prev.weekday() == 6:
                out["prior_session_is_reopen_stub"] = True
                for back2 in range(back + 1, 9):
                    prev2 = d - datetime.timedelta(days=back2)
                    if prev2.weekday() == 6:
                        continue
                    ymd2 = prev2.strftime("%Y%m%d")
                    st2 = _tape_day_stats(ymd2)
                    if st2 is not None:
                        out["prior_full_session"] = _tape_enrich(prev2, ymd2, st2)
                        break
                if "prior_full_session" not in out:
                    out["prior_full_session"] = None
                    out["prior_full_session_absent"] = ("no full session found within 8 days before "
                                                        f"{iso} - this is a data gap, not a mask")
                out["note_stub"] = (
                    "prior session is the Sunday REOPEN STUB (CME trade-date convention: it belongs to "
                    "this Monday). It is the GAP-FORMING session. `prior_full_session` carries the last "
                    "FULL session (normally the Friday) - the D-1 trade tilt doctrine puts direction on. "
                    "Both are open-time and non-price; use whichever the read calls for, and do not treat "
                    "the stub's thin sample as a tilt (big_print_b_share on 0-2 prints is degenerate - "
                    "see flow.big_print_bshare_thin_tape_guard).")
            return out
    return None


def _tape_enrich(prev, ymd: str, st: dict) -> dict:
    """The per-session non-price flow read. Factored out of _tape_conditions_block (S108) so a Monday can
    carry BOTH the Sunday reopen stub and the prior full session through the identical code path - the two
    blocks are the same measurement on different sessions, and must not be allowed to drift apart."""
    out = {"asof_prior_session": prev.isoformat(), "never_masked": True} | st
    ff = None
    try:
        import flow_read
        ff = flow_read.session_flow(ymd)
        if ff:
            # S107 defect 3: big_print_b_share MUST be copied through from flow_read, whose value
            # is SIZE-WEIGHTED (big_b / big_tot lots). Omitting it left _tape_day_stats' COUNT-based
            # value (big_b / len(bigs)) shadowing it under the same name. That was a G19 root cause:
            # the >=0.55 conviction gate saw a block max of 0.537 (count) while the size-weighted
            # series reaches 0.550 - the gate was fed the wrong series, not mis-specified.
            # S108: the two-sided b_share series MUST be copied through here. S107 defect 3 was exactly
            # this list omitting a computed field (big_print_b_share), leaving a different series
            # shadowing it under the same name for four groups. Adding a series to flow_read and not to
            # this list produces the same silent failure - the field simply never reaches a specialist.
            # S109: session_b_share JOINS this list. It was the ONE b_share field absent from it, so
            # when the S108 leg path broke _tape_day_stats' own computation (side-encoding collision,
            # see above) there was nothing to overwrite the 0.0 - while phase_b_share, big_print_b_share
            # and every *_two_sided field were silently rescued by being copied through. The omission
            # was invisible for as long as the harness's own value happened to be right.
            for k in ("session_signed_flow", "phase_signed_flow", "phase_b_share",
                      "big_print_b_share", "l1_book", "session_b_share",
                      "session_b_share_two_sided", "phase_b_share_two_sided",
                      "big_print_b_share_two_sided", "unsided_volume_frac", "b_share_basis_note",
                      "phase_volume_lots", "phase_n_trades", "phase_volume_note"):
                if k in ff:
                    out[k] = ff[k]
            if "big_print_b_share" in ff:
                out["big_print_b_share_basis"] = "size_weighted"
    except Exception as e:
        out["flow_read_error"] = str(e)
    # S107 defect 1: the flow read is the blind's PRIMARY channel (price is masked), so its absence
    # has to be STATED, never inferred from a missing key. A silently absent store previously read
    # as "no data" - that is how G20/G21 were staged with zero signed flow and nothing flagged it.
    out["firehose_present"] = {"mbo_flow": bool(ff) and "session_signed_flow" in ff,
                               "l1_book": bool(ff) and "l1_book" in ff}
    if not out["firehose_present"]["l1_book"]:
        print(f"[tape_conditions] {ymd}: ng_l1 book read MISSING (data/ng_l1/NG_{ymd}.jsonl.gz) - "
              f"quote imbalance and spread unavailable for this session", file=sys.stderr)
    if not out["firehose_present"]["mbo_flow"]:
        print(f"[tape_conditions] {ymd}: MBO trade-flow read MISSING (data/nymex_cont_n0|n1) - "
              f"signed flow and unbalanced sides unavailable for this session", file=sys.stderr)
    return out


def decision_state(days: list[str], mask_after: str | None = None, group: str | None = None) -> dict:
    """Blind-safe decision-time state per day: weekday + EIA storage surprise + curve regime + the RUNNING
    STORAGE capacity story (level / vs-5yr / phase) + gas-weighted degree-day regime (S94 chronological walk)
    + (S98 Tier 0) COT positioning + regional/salt storage + contract structure incl. the calendar-front
    squeeze view + (S98 feed D) the storage survey CONSENSUS + (S98 feed B) the vol/range regime + (S99 feed T) the STEO vintage balance + (S99 feed R) nuclear outages + (S99 feed Q) the EIA-930 grid stack + (S99 feed I) the options OI pin map. NO tape
    from the forecast day or later, NO legs, NO outcome — exactly what a forecaster knows at the open.
    Output carries a leading '_information_clock' meta key (static doctrine, not a day).

    mask_after (S101.5, brain s101.3 item 10 - the ONE-SHOT MASKING FIX, from the G12 disclosure): in
    one-shot blind mode the in-block days' price-derived blocks (contract_structure settles, vol_regime
    prior-session nets, cash_basis, options settle/OI, squeeze_watch's spread arms) carry the block's own
    path - a leak. With mask_after=YYYYMMDD (the block anchor), every day AFTER that date gets those
    blocks FROZEN at the anchor vintage, wrapped with masked_one_shot + vintage flags; curve_regime
    freezes with them. Exogenous feeds (weather/storage/COT/calendar/nuclear/grid/solar/STEO) stay live -
    published information a forecaster legitimately learns mid-block. Deterministic calendar clocks stay
    live in flow_calendar. Default None = unchanged behavior (refine/audit use)."""
    # S108: publish the group so _tape_day_stats can target the SCORED leg rather than guessing
    # by max trade count - which after a roll picks the DEFERRED contract (hole #8).
    global _ACTIVE_LEGS
    _ACTIVE_LEGS = group
    _tape_cond_cache.clear()

    import forward_curve as fc
    surp = _load_json("eia_surprise.json").get("KXNATGASD", {})
    stor = _storage_series()
    wx = _load_json("nws_temp/gw_degree_days.json")
    mos = json.load(open(MOS_ASOF)) if os.path.exists(MOS_ASOF) else {}   # additive; absent -> None, never 0
    cv = fc.load("NG")
    out = {"_information_clock": INFORMATION_CLOCK}
    frozen = None
    if mask_after:
        # anchor-CLOSE vintage: the state as-of the day AFTER the anchor (asof_session = the anchor itself),
        # because the anchor day's own settle is legitimately knowable at the block's first reopen
        m_next = datetime.date(int(mask_after[:4]), int(mask_after[4:6]), int(mask_after[6:])) + datetime.timedelta(days=1)
        m_iso = m_next.isoformat()
        m_cs = _contract_structure_block(m_iso)
        m_cr = fc.curve_asof(cv, m_iso)
        m_regime = m_cr[1]["regime"] if m_cr else "unknown"
        if m_regime == "unknown" and m_cs and m_cs.get("curve_regime"):
            m_regime = m_cs["curve_regime"]
        frozen = {"contract_structure": m_cs,
                  "squeeze_watch": _squeeze_watch(m_cs, m_iso),
                  "vol_regime": _vol_regime_block(m_iso),
                  "cash_basis": _cash_basis_block(m_iso),
                  "options_surface": _options_surface_block(m_iso),
                  "curve_regime": m_regime}
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
                  "storage_vintage": _storage_vintage_block(iso),
                  "ngwu_balance": _ngwu_block(iso),
                  "steo_vintage": _steo_vintage_block(iso),
                  "cot": _cot_asof_block(iso),
                  "contract_structure": cs,
                  "squeeze_watch": _squeeze_watch(cs, iso),
                  "vol_regime": _vol_regime_block(iso),
                  "cash_basis": _cash_basis_block(iso),
                  "flow_calendar": _flow_calendar_block(iso),
                  "solar": _solar_block(iso),
                  "nuclear_outages": _nuclear_outages_block(iso),
                  "grid_stack": _grid_stack_block(iso),
                  "options_surface": _options_surface_block(iso),
                  "weather": _weather_asof(iso, wx),
                  "weather_forecast": _forecast_weather_asof(iso, mos),
                  "weather_forecast_cycle": _mos_cycle_block(iso),
                  "freeze_risk": _freeze_risk_block(iso),
                  "model_disagreement": _model_disagreement_block(iso),
                  "tape_conditions": _tape_conditions_block(iso),
                  "holiday": _holiday_asof(iso)}
        # S107 defect 2: hoist the flow-read health to the DAY's top level. Buried inside tape_conditions
        # a degraded firehose is invisible without digging; at the top level the reader cannot miss it.
        _tc = out[d].get("tape_conditions") or {}
        out[d]["firehose_present"] = _tc.get("firehose_present")
        if _tc.get("flow_read_error"):
            out[d]["flow_read_error"] = _tc["flow_read_error"]
        if frozen is not None and d > mask_after:
            for blk in _PRICE_DERIVED_BLOCKS:
                fv = frozen[blk]
                out[d][blk] = ({"masked_one_shot": True, "vintage_asof": mask_after} | fv) if fv else \
                              {"masked_one_shot": True, "vintage_asof": mask_after, "value": None}
            out[d]["curve_regime"] = frozen["curve_regime"]
            out[d]["_mask_note"] = ("price-derived blocks FROZEN at the block-anchor vintage (one-shot "
                                    "masking fix, brain s101.3 item 10) - the deterministic expiry/print "
                                    "clock stays live in flow_calendar; exogenous feeds stay live")
            # S107: the one-shot freeze can OUTLIVE the contract it describes. When a front expires
            # inside the block, the frozen contract_structure keeps naming the dead contract and
            # squeeze_watch keeps reading active off an expiry that has already happened - a stale
            # FALSE POSITIVE, not merely stale data (G20: on 20260603 the frozen block still said
            # calendar_front NGM26, expiry 2026-05-27, days_to_expiry 2). The live front is always
            # available in flow_calendar, which is never masked, so the discrepancy is detectable
            # without un-masking anything. Flag it rather than let a reader infer a live squeeze.
            _cs = out[d].get("contract_structure") or {}
            _fe = _cs.get("calendar_front_expiry")
            if _fe and _fe < iso:
                for _blk in ("contract_structure", "squeeze_watch"):
                    if isinstance(out[d].get(_blk), dict):
                        out[d][_blk]["frozen_front_expired"] = True
                out[d]["frozen_structure_stale"] = {
                    "frozen_calendar_front_symbol": _cs.get("calendar_front_symbol"),
                    "frozen_calendar_front_expiry": _fe,
                    "live_front_symbol_calendar": (out[d].get("flow_calendar") or {}).get("front_symbol_calendar"),
                    "note": "the anchor-vintage freeze describes a front that has already expired as of "
                            "this day; contract_structure and squeeze_watch fields keyed to the calendar "
                            "front are NOT decision-legit here. flow_calendar carries the live front and "
                            "expiry clock and is never masked - use it.",
                }
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
            "structure_oi_session": 0, "storage_national": 0, "mos_asof": 0, "consensus_join": 0,
            "cash_knowable": 0, "steo_release": 0, "nuclear_wall": 0, "grid_wall": 0,
            "options_session": 0, "mos_cycle_wall": 0, "freeze_wall": 0}
    absent = {"cot": [], "storage_regional": [], "contract_structure": [], "weather_forecast": [],
              "storage_consensus": [], "vol_regime": [], "cash_basis": [], "steo_vintage": [],
              "nuclear_outages": [], "grid_stack": [], "options_surface": [],
              "weather_forecast_cycle": [], "freeze_risk": []}
    ds = decision_state([x.replace("-", "") for x in days])
    for iso in days:
        k = iso.replace("-", "")
        st = ds[k]
        c = st.get("cot")
        if c is None:
            absent["cot"].append(iso)
        else:
            if not (c["publication_ts"][:10] < iso and c["report_date"] < iso):
                viol["cot_publication"] += 1; print(f"  VIOLATION cot {iso}: pub {c['publication_ts']}")
            for bk, r in (c.get("ice") or {}).items():
                if r is not None and not (r["publication_ts"][:10] < iso and r["report_date"] < iso):
                    viol["cot_publication"] += 1; print(f"  VIOLATION cot-ice {iso} {bk}: pub {r['publication_ts']}")
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
        if st.get("vol_regime") is None:
            absent["vol_regime"].append(iso)
        cbx = st.get("cash_basis")
        if cbx is None:
            absent["cash_basis"].append(iso)
        elif cbx.get("hh_spot_gas_day") and not cbx["hh_spot_gas_day"] < iso:
            viol["cash_knowable"] += 1; print(f"  VIOLATION cash {iso}: gas_day {cbx['hh_spot_gas_day']}")
        stv = st.get("steo_vintage")
        if stv is None:
            absent["steo_vintage"].append(iso)
        elif not (stv["release_date"] < iso and stv["knowable_from"] <= iso):
            viol["steo_release"] += 1; print(f"  VIOLATION steo {iso}: release {stv['release_date']}")
        nu = st.get("nuclear_outages")
        if nu is None:
            absent["nuclear_outages"].append(iso)
        elif not nu["period"] < iso:
            viol["nuclear_wall"] += 1; print(f"  VIOLATION nuclear {iso}: period {nu['period']}")
        gsb = st.get("grid_stack")
        if gsb is None:
            absent["grid_stack"].append(iso)
        elif not gsb["period"] <= (datetime.date.fromisoformat(iso) - datetime.timedelta(days=2)).isoformat():
            viol["grid_wall"] += 1; print(f"  VIOLATION grid {iso}: period {gsb['period']}")
        osb = st.get("options_surface")
        if osb is None:
            absent["options_surface"].append(iso)
        elif not osb["asof_session"] < iso:
            viol["options_session"] += 1; print(f"  VIOLATION options {iso}: session {osb['asof_session']}")
        wfc = st.get("weather_forecast_cycle")
        if wfc is None:
            absent["weather_forecast_cycle"].append(iso)
        else:
            # the cycle wall: in EVERY view, the newest contributing cycle + 4.5h dissemination lag
            # must not pass the view's own asof moment (runtimes/asof both UTC, lexical-comparable)
            for vname in ("weekday_open", "sunday_reopen"):
                v = wfc.get(vname)
                if not v or not v.get("max_cycle_runtime_utc"):
                    continue
                rt = datetime.datetime.strptime(v["max_cycle_runtime_utc"], "%Y-%m-%d %H:%M:%S")
                asof = datetime.datetime.strptime(v["asof_utc"], "%Y-%m-%dT%H:%M:%SZ")
                if rt + datetime.timedelta(hours=4.5) > asof:
                    viol["mos_cycle_wall"] += 1
                    print(f"  VIOLATION mos-cycle {iso} {vname}: cycle {v['max_cycle_runtime_utc']} vs asof {v['asof_utc']}")
        fz = st.get("freeze_risk")
        if fz is None:
            absent["freeze_risk"].append(iso)
        else:
            for vname in ("weekday_open", "sunday_reopen"):
                v = fz.get(vname)
                if not v:
                    continue
                asof = datetime.datetime.strptime(v["asof_utc"], "%Y-%m-%dT%H:%M:%SZ")
                for st4, b in v["basins"].items():
                    if not b.get("max_cycle_runtime_utc"):
                        continue
                    rt = datetime.datetime.strptime(b["max_cycle_runtime_utc"], "%Y-%m-%d %H:%M:%S")
                    if rt + datetime.timedelta(hours=4.5) > asof:
                        viol["freeze_wall"] += 1
                        print(f"  VIOLATION freeze {iso} {vname} {st4}: cycle {b['max_cycle_runtime_utc']} vs asof {v['asof_utc']}")
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
    # (S101.5, brain s101.3 item 9) squeeze_watch PROMPT-EXPIRY fields - measured 2026-07-21 then pinned:
    # 0202 sits 3 sessions after the NGG26 Jan-28 expiry (the G12 dead-sponsor case), unwind_watch True.
    sw = decision_state(["20260202"])["20260202"]["squeeze_watch"]
    assert sw["last_prompt_symbol"] == "NGG26" and sw["last_prompt_expiry"] == "2026-01-28", sw
    assert sw["sessions_since_prompt_expiry"] == 3 and sw["unwind_watch"] is True, sw
    # (S101.5, brain s101.3 item 10) ONE-SHOT MASKING: in-block price-derived blocks freeze at the
    # anchor-CLOSE vintage (asof_session = the anchor itself); exogenous feeds stay live.
    md = decision_state(["20260205"], mask_after="20260130")["20260205"]
    assert md["contract_structure"]["masked_one_shot"] is True, md["contract_structure"]
    assert md["contract_structure"]["asof_session"] == "2026-01-30", md["contract_structure"]
    assert (md["vol_regime"] or {}).get("masked_one_shot") is True, md["vol_regime"]
    assert md.get("storage_consensus") is not None, "masking must not touch exogenous feeds"
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
    # (S98 feed H) combined + options-implied: additive, consistent (combined = futures + implied),
    # and the G11-open two-books divergence on record (futures 2.83rd pctile vs implied 97.17th).
    assert c.get("managed_money_net_combined") == c["managed_money_net"] + c["managed_money_net_options_implied"], c
    assert c["managed_money_net_options_implied"] == 1085 and c["managed_money_net_options_implied_pctile_1y"] == 97.17, c
    # (S100, ICE extension - free per Greg) the four ICE HH books ride under `ice`, separate reads.
    # Pins measured 2026-07-20: on 2026-01-22 the ICE LD1 book echoes the NYMEX futures extreme
    # (4.72nd 1y pctile vs NYMEX 2.83rd) - independent corroboration of the crowded short.
    ice = c.get("ice")
    assert ice is not None and set(ice) == {"ld1", "pen", "hh_basis", "hh_index"}, ice
    assert ice["ld1"]["managed_money_net"] == 798940 and ice["ld1"]["managed_money_net_pctile_1y"] == 4.72, ice["ld1"]
    assert all(r["publication_ts"][:10] < "2026-01-22" for r in ice.values() if r), ice
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
    # (S98 feed B) vol regime: the G11-open minimum reads through, bases never mixed, None never zero.
    d16 = decision_state(["20260116"])["20260116"]
    vb = d16["vol_regime"]
    assert vb is not None and vb["n0_net_sigma_20"] == 798, ("G11-open vol minimum", vb.get("n0_net_sigma_20"))
    assert vb.get("v0_net_sigma_20") is None, "v0 stub must be None, never a fabricated calm"
    # (S98 feed G) cash basis: weekly-batch publication respected - on 0123 the blowout is NOT knowable
    # (basis still -0.12 from the Jan 21 gas day); on 0130 it IS (+10.765, chg_3d +7.287).
    d23 = decision_state(["20260123"])["20260123"]
    cbb = d23["cash_basis"]
    assert cbb is not None and abs(cbb["hh_cash_minus_front_settle"] - (-0.12)) < 1e-9, \
        ("0123 must NOT see the cash blowout early", cbb)
    d30 = decision_state(["20260130"])["20260130"]
    cb30 = d30["cash_basis"]
    assert cb30 is not None and abs(cb30["hh_cash_minus_front_settle"] - 10.765) < 1e-9, cb30
    assert cb30["basis_chg_3d"] is not None and cb30["age_days"] >= 2, cb30
    # (S98 feed F) flow calendar: the G13 gauntlet anchors + the Thanksgiving EIA shift.
    d25 = decision_state(["20260225"])["20260225"]
    fc25 = d25["flow_calendar"]
    assert fc25 is not None and fc25["is_expiry_day"] is True, fc25
    fc24 = decision_state(["20260224"])["20260224"]["flow_calendar"]
    assert fc24["is_opex_day"] is True, fc24
    fc26 = decision_state(["20251126"])["20251126"]["flow_calendar"]
    assert fc26["is_eia_print_day"] is True and "12:00" in fc26["eia_storage_release_datetime_et"], \
        ("Thanksgiving-week EIA shift (Wed 12:00) must be encoded", fc26)
    # (S98 feed P) solar: deterministic, present, sane on the G11 window.
    sol = decision_state(["20260120"])["20260120"]["solar"]
    assert sol is not None and sol["metros"]["NYC"]["sunset_et"] == "16:57", sol["metros"]["NYC"]
    assert sol["gw_day_length_chg_7d"] is not None and sol["gw_day_length_chg_7d"] > 0, sol
    # (S98 feed K) the as-printed vintage overlay: mid-winter the market-known level ran ~10-11 Bcf
    # ABOVE the current revised series (the Mountain reclass), and both vintages are exposed.
    sv20 = decision_state(["20260120"])["20260120"]["storage_vintage"]
    assert sv20 is not None and sv20["national_level_as_printed"] == 3185 and sv20["national_level_current"] == 3174.0, sv20
    assert sv20["as_of"] < "2026-01-20", ("vintage blind wall", sv20)
    # (S98 feed N) the balance block: winter levels honestly DEAD (last live week 2025-09-24, large
    # age exposed) - never a fabricated fresh number; the vessel line carries through.
    nb = decision_state(["20260130"])["20260130"]["ngwu_balance"]
    assert nb is not None and nb["latest_sd_levels"]["week_ending"] == "2025-09-24", nb.get("latest_sd_levels")
    assert nb["latest_sd_levels"]["age_days"] > 100, "staleness must be exposed, not hidden"
    assert nb.get("dry_production_bcfd") is None, "winter issues must NOT carry fabricated levels"
    assert nb.get("lng_vessel_capacity_bcf") == 118.0, ("the squeeze-week vessel low", nb.get("lng_vessel_capacity_bcf"))
    # (S98 feed C) model disagreement: present through February, D-1 as-of, the 0125 whipsaw-eve
    # spread on record (max_abs 1.733 gw-HDD at h1 over the 2-horizon MET overlap).
    mdb = decision_state(["20260125"])["20260125"]["model_disagreement"]
    assert mdb is not None and mdb["summary"]["n_overlap_horizons"] == 2, mdb.get("summary")
    assert abs(mdb["summary"]["max_abs_spread_gw_hdd"] - 1.733) < 1e-9, mdb["summary"]
    assert mdb["asof_utc"][:10] < "2026-01-25", ("model-disagreement blind wall", mdb["asof_utc"])
    assert decision_state(["20260225"])["20260225"]["model_disagreement"] is not None, "Feb coverage"
    # (S99 feed T) STEO vintage balance: G12 opens on the pre-freeze jan26 consensus at age 19d; the
    # Feb-10 vintage lands MID-BLOCK as a readable revision (the freeze re-mark); a release day never
    # sees its own vintage.
    st1 = decision_state(["20260201"])["20260201"]["steo_vintage"]
    assert st1 is not None and st1["vintage_id"] == "jan26" and st1["age_days"] == 19, st1
    assert abs(st1["fields"]["total_consumption_bcfd"]["prev"] - 115.95) < 0.01, \
        ("G12 open must see the PRE-freeze Jan consumption", st1["fields"]["total_consumption_bcfd"])
    st2 = decision_state(["20260211"])["20260211"]["steo_vintage"]
    assert st2 is not None and st2["vintage_id"] == "feb26", st2
    assert abs(st2["revisions_vs_prev_vintage"]["total_consumption_bcfd"]["prev"] - 5.95) < 0.02, \
        ("the freeze re-mark must ride as a revision delta", st2.get("revisions_vs_prev_vintage"))
    st3 = decision_state(["20260113"])["20260113"]["steo_vintage"]
    assert st3 is not None and st3["vintage_id"] == "dec25", ("jan26 release day must NOT be knowable", st3)
    # (S99 feed R arm 1) nuclear outages: the freeze-window 1.8 -> 3.2 GW jump readable at honest
    # D+1 staleness; a day never sees its own morning row.
    n21 = decision_state(["20260121"])["20260121"]["nuclear_outages"]
    assert n21 is not None and n21["period"] == "2026-01-20" and n21["age_days"] == 1, n21
    assert abs(n21["capacity_out_gw"] - 3.184) < 0.01, ("freeze-window outage peak", n21["capacity_out_gw"])
    n16 = decision_state(["20260116"])["20260116"]["nuclear_outages"]
    assert n16 is not None and n16["period"] == "2026-01-15" and abs(n16["capacity_out_gw"] - 1.839) < 0.01, n16
    n20 = decision_state(["20260120"])["20260120"]["nuclear_outages"]
    assert n20 is not None and n20["period"] == "2026-01-19", ("own-day row must be walled", n20)
    # (S99 feed Q) EIA-930 grid stack: loads + the BA's own day-ahead forecast + fuel mix, per BA;
    # the freeze power-burn ramp (est 28.3 -> 41.1 Bcf/d) visible decision-time at the +2 wall.
    g22 = decision_state(["20260122"])["20260122"]["grid_stack"]
    assert g22 is not None and g22["period"] == "2026-01-20" and g22["age_days"] == 2, g22 and g22.get("period")
    assert abs(g22["bas"]["US48"]["est_gas_burn_bcfd"] - 41.1) < 0.7, g22["bas"]["US48"]
    assert g22["bas"]["ERCO"]["demand_forecast_mwh"] is not None, "ERCO day-ahead forecast missing"
    g12a = decision_state(["20260112"])["20260112"]["grid_stack"]
    assert g12a["period"] == "2026-01-10" and abs(g12a["bas"]["US48"]["est_gas_burn_bcfd"] - 28.3) < 0.7, \
        g12a["bas"]["US48"]
    # (S99 feed I phase i - G13 blocker) the options pin map: squeeze-eve Jan 27 shows the NGG26
    # walls at days_to_opex 0 off the Jan 26 session; G13's opex day (Feb 24) shows NGH26 at 0.
    o27 = decision_state(["20260127"])["20260127"]["options_surface"]
    assert o27 is not None and o27["asof_session"] == "2026-01-26", o27 and o27.get("asof_session")
    assert o27["months"][0]["month"] == "NGG26" and o27["months"][0]["days_to_opex"] == 0, o27["months"][0]
    assert len(o27["months"][0]["top5_oi_strikes"]) == 5 and o27["months"][0]["total_call_oi"] > 0, \
        "pin map must be populated on squeeze eve"
    o24 = decision_state(["20260224"])["20260224"]["options_surface"]
    assert o24 is not None and o24["months"][0]["month"] == "NGH26" and o24["months"][0]["days_to_opex"] == 0, \
        ("G13 opex-day view", o24 and o24["months"][0])
    # missing-is-explicit: a pre-coverage date carries None blocks, never zeros.
    d_old = decision_state(["20250902"])["20250902"]
    assert d_old["contract_structure"] is None or d_old["contract_structure"].get("front_next_spread") != 0, d_old
    assert d_old["steo_vintage"] is None, "pre-coverage steo_vintage must be None, never zeros"
    # the information clock rides ONCE as a leading meta key, and day keys still index cleanly.
    full = decision_state(["20260122"])
    assert "_information_clock" in full and "20260122" in full, list(full)
    print(f"[forecast_harness] S98 wired: 20260122 cot MM net={c['managed_money_net']} "
          f"pctile1y={c['managed_money_net_pctile_1y']} | salt={r['regions']['south_central_salt']['level']} "
          f"| cal_spread={cs['calendar_front_next_spread']} (oi-front {cs['front_next_spread']}) "
          f"| squeeze_watch={sw['active']} | curve_regime={d22['curve_regime']}")
    # (S100 feed A phase 1) cycle-level MOS as-of: additive block present; the 0119-Monday pin -
    # the sunday_reopen view carries the Jan-24 +8.511 gw-HDD add (measured 2026-07-20, equals the
    # run-delta s100_2 recorded arriving an hour AFTER the reopen in the D-1-evening frame).
    d19 = decision_state(["20260119"])["20260119"]
    wfc = d19.get("weather_forecast_cycle")
    if wfc is not None:
        assert wfc.get("weekday_open") is not None, wfc
        sr = wfc.get("sunday_reopen")
        assert sr is not None, "0119 is a Monday - the sunday_reopen view must ride"
        j24 = [x for x in sr["delta_vs_prior_by_horizon"] if x["target"] == "2026-01-24"]
        assert j24 and abs(j24[0]["d_gw_hdd"] - 8.511) < 1e-9, ("the 0118 reopen pin", j24)
        assert sr["max_cycle_runtime_utc"] is not None and sr["max_cycle_runtime_utc"] <= "2026-01-18 18:00:00", sr
        print(f"[forecast_harness] mos_cycle wired: 0119 sunday_reopen Jan-24 add "
              f"{j24[0]['d_gw_hdd']:+.3f} gw-HDD, newest cycle {sr['max_cycle_runtime_utc']}Z "
              f"(reopen-available)")
    # (S100 feed E) freeze risk: additive block; the measured 0119/0122 pins (Appalachia 10F with
    # 7 sub-20F days from Jan-19; Permian AND Haynesville sub-20F from Jan-24 visible on 0122 -
    # the supply-convexity signal into the squeeze week).
    fz19 = d19.get("freeze_risk")
    if fz19 is not None:
        b = fz19["weekday_open"]["basins"]
        assert b["PIT"]["tmin_d0_f"] == 10.0 and b["PIT"]["thresholds_f"]["20.0"]["days_below"] == 7, b["PIT"]
        fz22 = decision_state(["20260122"])["20260122"]["freeze_risk"]["weekday_open"]["basins"]
        assert fz22["MAF"]["thresholds_f"]["20.0"]["first_below"] == "2026-01-24", fz22["MAF"]
        assert fz22["SHV"]["thresholds_f"]["20.0"]["first_below"] == "2026-01-24", fz22["SHV"]
        print(f"[forecast_harness] freeze_risk wired: 0119 PIT {b['PIT']['tmin_d0_f']}F/7d sub-20; "
              f"0122 MAF+SHV sub-20F from 2026-01-24")
    brain_show()
    print("[forecast_harness] selftest PASS")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    a1 = sub.add_parser("decision-state"); a1.add_argument("--days", required=True); a1.add_argument("--out")
    a1.add_argument("--group", help="gid (g21...) - S108: lets the tape read target the SCORED leg")
    a1.add_argument("--mask-after", default=None,
                    help="YYYYMMDD block anchor: freeze price-derived blocks at this vintage for later days (one-shot masking fix)")
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
        ds = decision_state(a.days.split(","), mask_after=a.mask_after, group=a.group)
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
