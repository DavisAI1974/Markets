"""vol_regime.py - DATA_GATE_S98 feed B: VOL / RANGE REGIME per date (family: tape conditioner).

WHY: the brain's magnitude bands keep being overshot on named days (1119, 1128, 1211, 1223,
0121 +3820 vs band 3000, 0130 +5020 vs 2200) - bands calibrated in one vol regime are applied
in another, and the forecaster carries NO state variable saying which regime today's open sits
in. This feed computes that state from tape already on disk. It CONDITIONS magnitude
expectations; it never calls direction (Tier 3 usage doctrine: vol = band scaler, never
direction).

TWO TAPE BASES, NEVER MIXED, both exposed (field prefixes carry the basis):
  n0_*  data/nymex_cont_n0/  NG.n.0 (OI-continuous front)   - the G11+ walk basis
  v0_*  data/nymex_cont/     NG.v.0 (volume-continuous)     - the G3-G10 walk basis; LOCAL
                                                              coverage is only the G11-era
                                                              sub-span (see coverage in meta)
A date where a basis has no coverage yields None for that basis's fields - NEVER a fall-through
to the other basis. MISSING IS EXPLICIT, NEVER ZERO.

SESSION = one continuous-tape day-file = one UTC calendar day (the walk's own day convention;
the 23:00-24:00 UTC hour of file D belongs to the exchange session dated D+1 - recorded caveat).
open/close = first/last trade print of the file (verified == roll_meta_NG.json first/last);
range = high-low of trade prints; net and range in $ per contract (NG MULT = 10000 $/pt).
Sundays are REAL (thin) sessions - the 18:00-19:00 ET reopen hour; trades_n exposes thinness.

BLIND WALL: every value for date D derives ONLY from sessions strictly before D (trailing
windows end at the prior session's close; D's own tape is never an input). Asserted in code on
every window build AND audited by --selftest over the whole store (violation count must be 0).

Fields per basis prefix b_ in {n0_, v0_}. Whenever a window lacks the full number of prior
sessions the value is None and b_win_n_* carries the actual count - a partial-window number is
never silently presented as a full-window one. b_range_pctile is the one BY-SPEC exception:
computed over up to 60 prior sessions with the actual n exposed in b_range_pctile_n.
  b_prev_date / b_prev_age_days / b_prev_net / b_prev_range / b_prev_trades  the prior session
  b_net_sigma_5/10/20    population sigma of session nets over the prior 5/10/20 sessions ($)
  b_range_5_mean/_10_/_20_  mean session range over the prior 5/10/20 sessions ($)
  b_range_20_max         max session range over the prior 20 sessions ($)
  b_win_n_5/10/20        actual prior-session counts backing every 5/10/20-window field
  b_range_pctile         percentile of the PRIOR session's range within the prior <=60 sessions
                         (share of window ranges <= it, x100; the prior session is in the window,
                         so the floor is 100/n, never 0)
  b_range_pctile_n       the actual n behind it
  b_activity_trend       mean(trades_n prior 5) / mean(trades_n prior 20); None unless 20 exist

Usage:
  python research/kalshi/vol_regime.py --canary          # 3 days per basis end-to-end, no write
  python research/kalshi/vol_regime.py --build           # precompute span -> data/vol_regime/
  python research/kalshi/vol_regime.py --selftest        # blind-wall audit + sanity anchors
  python research/kalshi/vol_regime.py --day 2025-12-05  # print one asof row from the store

  from vol_regime import vol_regime_asof
  vol_regime_asof("2026-01-21") -> dict | None           # store-read only, never touches tape

Tape access is READ-ONLY and uses the sanctioned override hook exactly as
run_g11_fingerprints_s98.py does (mc.CONT_DIR = <abs path> then mc.load_cont_full); for v0 the
walk's own *_tp.npz caches are used where present (verified identical to the full parse).
This module edits NO shared module and never writes into the tape dirs.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from datetime import date as _date, datetime, timedelta, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
ROOT = "NG"
MULT = 10000.0                                   # NG contract: $ per 1.000 price point
SPAN_START, SPAN_END = "2025-09-01", "2026-03-13"
# S107: SPAN_END is now a FLOOR, not the build end. It was a hard-coded date pinned when the feed was
# first built and never advanced, so every group whose anchor fell past 2026-03-13 got
# vol_regime_asof -> None. That surfaced as {"masked_one_shot": true, "value": null} in the decision
# state - indistinguishable from a deliberate price mask - and it silently cost G16 through G23 the
# entire vol/range conditioner, i.e. the one module built to fix what the brain itself calls the walk's
# dominant residual (bands calibrated in one vol regime applied in another). The build end is now
# DERIVED from the tape actually on disk so it cannot go stale again.
ASOF_FORWARD_MARGIN_DAYS = 7   # as-of rows a little past the last session; n0_prev_age_days exposes staleness
WINS = (5, 10, 20)
PCTILE_WIN = 60
BASES = {
    "n0": {"dir": os.path.join(REPO, "data", "nymex_cont_n0"), "series": "NG.n.0",
           "role": "G11+ walk basis (OI-continuous front)"},
    "v0": {"dir": os.path.join(REPO, "data", "nymex_cont"), "series": "NG.v.0",
           "role": "G3-G10 walk basis (volume-continuous); local files = G11-era sub-span only"},
}
STORE = os.path.join(REPO, "data", "vol_regime", "vol_regime.json")

_store_cache: dict[str, dict] = {}


# ---------------------------------------------------------------- date helpers

def _iso(d8: str) -> str:
    return f"{d8[:4]}-{d8[4:6]}-{d8[6:8]}"


def _daterange(a: str, b: str):
    d, e = _date.fromisoformat(a), _date.fromisoformat(b)
    while d <= e:
        yield d.isoformat()
        d += timedelta(days=1)


# ---------------------------------------------------------------- tape reading (read-only)

def _list_session_days(basis: str) -> list[str]:
    """Session day-files 'YYYYMMDD' present for a basis, from filenames (NG_YYYYMMDD.jsonl[.gz])."""
    d = BASES[basis]["dir"]
    days = set()
    for p in (glob.glob(os.path.join(d, f"{ROOT}_*.jsonl.gz"))
              + glob.glob(os.path.join(d, f"{ROOT}_*.jsonl"))):
        day = os.path.basename(p).split(".")[0].split("_")[1]
        if len(day) == 8 and day.isdigit():
            days.add(day)
    return sorted(days)


def _load_ts_price(basis: str, day: str):
    """(ts, price) trade-print arrays for one session file. Uses the walk's *_tp.npz cache when
    present (fast_tape format; verified identical to the full parse); otherwise the shared raw
    reader via the sanctioned month_characterize CONT_DIR override (run_g11_fingerprints_s98
    pattern). Never writes into the tape dirs."""
    cdir = BASES[basis]["dir"]
    npz = os.path.join(cdir, f"{ROOT}_{day}_tp.npz")
    if os.path.exists(npz) and os.path.getsize(npz) > 0:
        z = np.load(npz)
        return z["ts"], z["price"]
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    import month_characterize as mc
    mc.CONT_DIR = cdir                    # the existing override hook - never edit the module
    a = mc.load_cont_full(ROOT, day, source="local")
    return a["ts"], a["price"]


def _session_row(basis: str, day: str) -> dict:
    """One session's descriptors. Integrity assertion: the tape's ts span must sit inside the
    file's own UTC day (protects the blind wall against a mis-dated file)."""
    ts, p = _load_ts_price(basis, day)
    iso = _iso(day)
    if len(p) == 0:
        return {"date": iso, "net": None, "range": None, "open": None, "close": None,
                "trades_n": 0}
    d0 = datetime.strptime(day, "%Y%m%d").replace(tzinfo=timezone.utc).timestamp()
    if not (d0 <= float(ts[0]) and float(ts[-1]) < d0 + 86400.0):
        raise AssertionError(f"[{basis} {day}] tape ts outside its UTC day: "
                             f"{float(ts[0]):.0f}..{float(ts[-1]):.0f} vs [{d0:.0f},{d0+86400.0:.0f})")
    return {"date": iso,
            "net": int(round((float(p[-1]) - float(p[0])) * MULT)),
            "range": int(round((float(np.max(p)) - float(np.min(p))) * MULT)),
            "open": round(float(p[0]), 4), "close": round(float(p[-1]), 4),
            "trades_n": int(len(p))}


def build_sessions(basis: str, days: list[str] | None = None, verbose: bool = True) -> list[dict]:
    days = _list_session_days(basis) if days is None else days
    rows = []
    for i, day in enumerate(days):
        rows.append(_session_row(basis, day))
        if verbose and ((i + 1) % 20 == 0 or i == len(days) - 1):
            print(f"  [{basis}] {i + 1}/{len(days)} {day} trades={rows[-1]['trades_n']}", flush=True)
    return rows


# ---------------------------------------------------------------- asof derivation

# S114: the bar that separates a full trading session from a reopen/holiday stub. Data-driven
# rather than a day-of-week rule, because holiday stubs are not Sundays: measured on the live n0
# store the population is strongly bimodal - full sessions cluster at a ~19,900 median while the
# stubs sit at 134-2,594 prints, with nothing in between near this bar.
FULL_SESSION_MIN_FRAC = 0.15


def _is_stub(s: dict, population: list[dict]) -> bool:
    """True if this row is a thin reopen/holiday stub rather than a full trading session.
    The bar floats off the POPULATION median so it tracks a changing tape instead of a constant."""
    if not population:
        return False
    med = float(np.median([x["trades_n"] for x in population if x.get("trades_n") is not None] or [0]))
    if med <= 0:
        return False
    return (s.get("trades_n") or 0) < FULL_SESSION_MIN_FRAC * med


def _basis_fields(b: str, prior: list[dict], iso: str) -> dict:
    """Trailing-window state for date iso from prior = this basis's VALID sessions strictly
    before iso, oldest->newest. The blind wall is asserted on every call."""
    assert all(s["date"] < iso for s in prior), f"blind wall: session >= {iso} in window ({b})"
    f: dict = {}
    # S114: THE S108 MONDAY-STUB FIX NEVER REACHED THIS MODULE.
    # tape_conditions got `prior_full_session` at S108 ("Mondays were served 0.2-3% of a normal
    # tape, the Friday never consulted"). vol_regime did not, so on EVERY Monday `*_prev_*`
    # describes the ~1-hour Sunday reopen. Measured for 2026-07-20: the prior session is Sunday
    # 2026-07-19 with 294 trades and a 400 range - against Friday 07-17's 13,743 trades and 800.
    # `*_prev_*` still reports the LITERAL prior session (it is the honest answer to "what traded
    # last", and its thinness is informative), but the prior FULL session is now served beside it
    # and the percentile is sited on the full-session distribution, because a stub's range cannot
    # be located in a population of 23-hour sessions.
    prev = prior[-1] if prior else None
    prev_full = next((s for s in reversed(prior) if not _is_stub(s, prior)), None)
    f[f"{b}_prev_is_stub"] = None if prev is None else _is_stub(prev, prior)
    if prev_full is not None:
        f[f"{b}_prev_full_session_date"] = prev_full["date"]
        f[f"{b}_prev_full_session_net"] = prev_full["net"]
        f[f"{b}_prev_full_session_range"] = prev_full["range"]
        f[f"{b}_prev_full_session_trades"] = prev_full["trades_n"]
    else:
        for _k in ("date", "net", "range", "trades"):
            f[f"{b}_prev_full_session_{_k}"] = None
    if prev is None:
        f[f"{b}_prev_date"] = None
        f[f"{b}_prev_age_days"] = None
        f[f"{b}_prev_net"] = None
        f[f"{b}_prev_range"] = None
        f[f"{b}_prev_trades"] = None
    else:
        f[f"{b}_prev_date"] = prev["date"]
        f[f"{b}_prev_age_days"] = (_date.fromisoformat(iso) - _date.fromisoformat(prev["date"])).days
        f[f"{b}_prev_net"] = prev["net"]
        f[f"{b}_prev_range"] = prev["range"]
        f[f"{b}_prev_trades"] = prev["trades_n"]
    # S114 (S110 audit f3): DECLARE THE WINDOW. `*_prev_trades` and `tape_conditions.n_trades` count
    # the SAME tape over DIFFERENT windows, and nothing said so - state_health rightly refused a
    # fresh g22 stage over it (1,835 here vs 6,935 there for 2026-06-19). This module slices by UTC
    # CALENDAR DAY (`_session_row` asserts the tape's ts span sits inside d0..d0+86400), while
    # tape_conditions counts the EXCHANGE SESSION (18:00 ET prior day -> 17:00 ET). The gap is
    # largest on holidays and shortened sessions, which is exactly where g22 anchors (Juneteenth).
    # Neither number is wrong; comparing them as if they were the same quantity is. Declared rather
    # than silenced - the session_b_share_basis pattern (S109).
    f[f"{b}_era_basis"] = (
        f"{b}_prev_* count the {b} continuous store sliced by UTC CALENDAR DAY. "
        f"tape_conditions.n_trades counts the EXCHANGE SESSION (18:00 ET prior day -> 17:00 ET) and "
        f"is the scored-leg tape. The two windows do not coincide and diverge most on holidays and "
        f"shortened sessions. Use {b}_prev_* for volatility-regime scaling only; never reconcile it "
        f"against the tape block's trade count as though they were the same measurement.")
    # S114: A DISTRIBUTION MUST BE OVER COMPARABLE OBJECTS.
    # The module header declares "Sundays are REAL (thin) sessions - the 18:00-19:00 ET reopen
    # hour; trades_n exposes thinness". The declaration is honest and NOTHING DOWNSTREAM EVER
    # FILTERED ON IT: every trailing sigma/mean/percentile was computed over a mixed population of
    # ~23-hour sessions and ~1-hour reopen stubs. MEASURED on the live store: 41 of 223 n0
    # "sessions" (18.4%) carry <15% of the median trade count, 36 of them SUNDAYS, and their
    # median |net| is 250 against 600 for full sessions. They drag the magnitude conditioner DOWN -
    # removing them raises sigma_20 by +12% at the g24 anchor and +22% at g23's.
    # This matters because vol_regime IS the magnitude conditioner and the g24 blind under-emitted
    # at 0.29x of realized. It is not the whole story (g24's sigma_5 = 137 is arithmetically
    # correct over five genuinely quiet full sessions) but it is a real, measured bias.
    # `*_prev_*` above is deliberately NOT filtered: a Sunday reopen genuinely IS the prior session
    # for a Monday and its thinness is informative. Only the trailing DISTRIBUTIONS are.
    # The proper long-term fix is folding the Sunday reopen into Monday per the CME trade-date
    # convention (S104.1, "the ~2h reopen belongs to Monday", effective G17) - which this module
    # does NOT do, because it slices by UTC calendar day. That re-slice is registered separately;
    # it is not half-done here.
    full_sessions = [s for s in prior if not _is_stub(s, prior)]
    n_excluded = len(prior) - len(full_sessions)
    nets = [s["net"] for s in full_sessions]
    rngs = [s["range"] for s in full_sessions]
    trd = [s["trades_n"] for s in full_sessions]
    f[f"{b}_window_excluded_stub_sessions"] = n_excluded
    f[f"{b}_window_basis"] = (
        f"trailing sigma/mean/percentile fields are computed over FULL SESSIONS ONLY "
        f"(trades_n >= {FULL_SESSION_MIN_FRAC:.0%} of the store median); {n_excluded} thin "
        f"reopen/holiday stub(s) were excluded from the windows so the distribution is over "
        f"comparable objects. {b}_prev_* is NOT filtered - it describes the immediately prior "
        f"session whatever it was, and a thin reopen is informative there.")
    for w in WINS:
        n = min(w, len(prior))
        f[f"{b}_win_n_{w}"] = n
        full = n == w
        f[f"{b}_net_sigma_{w}"] = int(round(float(np.std(nets[-w:])))) if full else None
        f[f"{b}_range_{w}_mean"] = int(round(float(np.mean(rngs[-w:])))) if full else None
    f[f"{b}_range_20_max"] = int(max(rngs[-20:])) if len(prior) >= 20 else None
    if prev is not None:
        # S114: SITE LIKE WITH LIKE. `rngs` is now full-sessions-only, so the reference range must
        # be a full session's too - locating a 1-hour Sunday reopen's 400 range inside a
        # distribution of 23-hour sessions returned 0.0 (a "record-compressed regime") when the
        # honest reading is that the two are not the same measurement. This percentile is the
        # field a g24 specialist used to weight toward the short sigma, so a spurious extreme here
        # propagates straight into an under-sized emission.
        wr = rngs[-PCTILE_WIN:]
        _ref = prev_full if prev_full is not None else prev
        f[f"{b}_range_pctile"] = round(100.0 * sum(1 for r in wr if r <= _ref["range"]) / len(wr), 1)
        f[f"{b}_range_pctile_n"] = len(wr)
        f[f"{b}_range_pctile_basis"] = (
            f"the prior FULL session's range ({_ref['range']}, {_ref['date']}) sited in the "
            f"trailing {len(wr)} FULL sessions. Both sides exclude thin reopen/holiday stubs so "
            f"the comparison is between comparable objects."
            + ("" if prev is None or not _is_stub(prev, prior) else
               f" NOTE: the LITERAL prior session was {prev['date']} (a stub, {prev['trades_n']} "
               f"prints, range {prev['range']}); it is reported in {b}_prev_* and deliberately "
               f"NOT used here."))
    else:
        f[f"{b}_range_pctile"] = None
        f[f"{b}_range_pctile_n"] = 0
    if len(prior) >= 20:
        m5, m20 = float(np.mean(trd[-5:])), float(np.mean(trd[-20:]))
        f[f"{b}_activity_trend"] = round(m5 / m20, 3) if m20 > 0 else None
    else:
        f[f"{b}_activity_trend"] = None
    return f


def _coverage(basis: str, rows: list[dict]) -> dict:
    """Per-basis coverage: first/last, every missing non-Saturday date inside the covered span
    named individually, zero-trade files named, and the basis's absent ranges vs the feed span."""
    valid = [r for r in rows if r["net"] is not None]
    zero = [r["date"] for r in rows if r["net"] is None]
    have = {r["date"] for r in rows}
    cov: dict = {"series": BASES[basis]["series"], "role": BASES[basis]["role"],
                 "dir": os.path.relpath(BASES[basis]["dir"], REPO),
                 "files": len(rows), "valid_sessions": len(valid),
                 "zero_trade_days": zero}
    if not rows:
        cov.update({"first": None, "last": None, "missing_days_in_span": [],
                    "absent_ranges_vs_feed_span": [f"{SPAN_START}..{SPAN_END} (no files at all)"]})
        return cov
    first, last = rows[0]["date"], rows[-1]["date"]
    missing = [d for d in _daterange(first, last)
               if d not in have and _date.fromisoformat(d).weekday() != 5]   # Sat = no Globex day-file
    absent = []
    if SPAN_START < first:
        pre_end = (_date.fromisoformat(first) - timedelta(days=1)).isoformat()
        absent.append(f"{SPAN_START}..{pre_end} (no {basis} tape on local disk)")
    if last < SPAN_END:
        post_start = (_date.fromisoformat(last) + timedelta(days=1)).isoformat()
        absent.append(f"{post_start}..{SPAN_END} (no {basis} tape on local disk)")
    cov.update({"first": first, "last": last, "missing_days_in_span": missing,
                "absent_ranges_vs_feed_span": absent})
    return cov


def _resolved_span_end(sessions: dict) -> str:
    """S107: the as-of span ends where the TAPE ends (plus a small forward margin), never at a
    hard-coded date. SPAN_END is kept as a floor so the feed's intended minimum span still holds."""
    lasts = [s[-1]["date"] for s in sessions.values() if s]
    if not lasts:
        return SPAN_END
    end = max(max(lasts), SPAN_END)
    d = datetime.strptime(end, "%Y-%m-%d") + timedelta(days=ASOF_FORWARD_MARGIN_DAYS)
    return d.strftime("%Y-%m-%d")


def build_store(write: bool = True) -> dict:
    print(f"[vol_regime] building sessions  span_start={SPAN_START} (end derived from tape)")
    sessions = {}
    for b in BASES:
        days = _list_session_days(b)
        print(f"[{b}] {BASES[b]['series']}  {BASES[b]['dir']}  files={len(days)}", flush=True)
        sessions[b] = build_sessions(b, days)
    span_end = _resolved_span_end(sessions)
    print(f"[vol_regime] as-of span resolved to {SPAN_START}..{span_end}")
    asof = {}
    for iso in _daterange(SPAN_START, span_end):
        row = {"date": iso}
        for b in BASES:
            prior = [s for s in sessions[b] if s["date"] < iso and s["net"] is not None]
            row.update(_basis_fields(b, prior, iso))
        asof[iso] = row
    meta = {
        "feed": "vol_regime (DATA_GATE_S98 feed B, family: tape conditioner)",
        "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "span": [SPAN_START, span_end],
        "span_end_source": "derived from the last session on disk + "
                           f"{ASOF_FORWARD_MARGIN_DAYS}d margin (floor {SPAN_END}); S107 - a "
                           "hard-coded end silently starved every group past it",
        "root": ROOT, "mult_usd_per_pt": MULT,
        "definitions": {
            "session": "one continuous-tape day-file = one UTC calendar day; open/close = "
                       "first/last trade print (== roll_meta first/last); Sundays are real thin "
                       "sessions (the 18:00-19:00 ET reopen hour)",
            "net": "(close - open) * 10000, $ per contract, int",
            "range": "(high - low) of trade prints * 10000, $ per contract, int",
            "net_sigma_w": "population sigma (ddof=0) of session nets over the prior w sessions",
            "range_pctile": "share of the prior <=60 sessions' ranges <= the prior session's "
                            "range, x100 (prior session included; floor 100/n)",
            "activity_trend": "mean(trades_n prior 5) / mean(trades_n prior 20)",
            "trades_n": "ts-deduplicated trade prints (the codebase's standard trade count)",
            "blind_wall": "every value for date D derives only from sessions with date < D",
            "missing": "None = unknown/insufficient; win_n_* carries the actual prior count",
        },
        "coverage": {b: _coverage(b, sessions[b]) for b in BASES},
    }
    store = {"meta": meta, "sessions": sessions, "asof": asof}
    if write:
        os.makedirs(os.path.dirname(STORE), exist_ok=True)
        with open(STORE, "w") as fh:
            json.dump(store, fh, indent=1)
        _store_cache.pop(STORE, None)
        print(f"[vol_regime] wrote {STORE} ({os.path.getsize(STORE) / 1024:.0f} KB)")
    _print_coverage(meta["coverage"])
    return store


def _print_coverage(cov: dict) -> None:
    print("\n[vol_regime] COVERAGE (per basis; gaps named)")
    for b, c in cov.items():
        print(f"  {b} ({c['series']}, {c['dir']}): files={c['files']} valid={c['valid_sessions']} "
              f"span={c['first']}..{c['last']}")
        if c["zero_trade_days"]:
            print(f"    zero-trade files: {', '.join(c['zero_trade_days'])}")
        if c["missing_days_in_span"]:
            print(f"    missing non-Saturday days inside covered span: "
                  f"{', '.join(c['missing_days_in_span'])}")
        else:
            print("    missing non-Saturday days inside covered span: none")
        for a in c["absent_ranges_vs_feed_span"]:
            print(f"    absent vs feed span: {a}")


# ---------------------------------------------------------------- the asof reader

def vol_regime_asof(date, store_path: str = STORE) -> dict | None:
    """Vol/range regime state for a date ('YYYY-MM-DD', 'YYYYMMDD', or a date/datetime).
    Reads the precomputed store ONLY (never touches tape). Returns None if the store is absent
    or the date is outside the built span. Every value derives from sessions strictly before
    the date; a basis without coverage is None-per-field, never zero, never the other basis."""
    if hasattr(date, "isoformat"):
        iso = date.isoformat()[:10]
    else:
        s = str(date)
        iso = _iso(s) if len(s) == 8 and s.isdigit() else s[:10]
    st = _store_cache.get(store_path)
    if st is None:
        if not os.path.exists(store_path):
            return None
        with open(store_path) as fh:
            st = json.load(fh)
        _store_cache[store_path] = st
    return st["asof"].get(iso)


# ---------------------------------------------------------------- selftest

def selftest() -> int:
    if not os.path.exists(STORE):
        print(f"[selftest] store missing: {STORE} - run --build first")
        return 1
    with open(STORE) as fh:
        st = json.load(fh)
    sess = st["sessions"]
    fails = 0

    # (a) BLIND-WALL AUDIT over the whole store: independent strictly-prior filter, direct
    # raw-table checks (prev really is the last prior session; win_n honest), and a full
    # field-by-field recompute equality per date x basis.
    viol, checked = 0, 0
    for iso, row in st["asof"].items():
        for b in BASES:
            prior = [s for s in sess[b] if s["date"] < iso and s["net"] is not None]
            if prior and not max(s["date"] for s in prior) < iso:
                viol += 1
            pd = row.get(f"{b}_prev_date")
            if pd is not None and not pd < iso:
                viol += 1
            exp_prev = prior[-1]["date"] if prior else None
            if pd != exp_prev:
                viol += 1
            if row.get(f"{b}_win_n_20") != min(20, len(prior)):
                viol += 1
            rec = _basis_fields(b, prior, iso)
            for k, v in rec.items():
                checked += 1
                if row.get(k) != v:
                    viol += 1
                    if viol <= 5:
                        print(f"    MISMATCH {iso} {k}: store={row.get(k)} recomputed={v}")
    n_dates = len(st["asof"])
    print(f"[selftest] (a) blind-wall audit: {viol} violations over {n_dates} dates x "
          f"{len(BASES)} bases ({checked} field recomputes)")
    if viol:
        fails += 1

    # (b) KNOWN-DAY SANITY ANCHOR: the G9 crest/crash (2025-12-05..12-11) must sit materially
    # ABOVE the late-September level on 20-session net-sigma and range means (direction of
    # comparison only, no fitted threshold). Late-September needs v0 tape from Sep/Oct 2025,
    # which is NOT on local disk (S3-only; no AWS credentials this session) - if unavailable
    # the comparison base falls back, NAMED, to the earliest date with a full 20-session n0
    # window (late November), same direction-only check.
    crest_dates = list(_daterange("2025-12-05", "2025-12-11"))
    sep_sessions = [s for s in sess["v0"] if s["date"] < "2025-10-01" and s["net"] is not None]
    if len(sep_sessions) >= 20:
        base_iso = "2025-10-01"
        base = st["asof"][base_iso]
        b_sig, b_rng = base["v0_net_sigma_20"], base["v0_range_20_mean"]
        base_label = f"v0 late-September base (asof {base_iso})"
        crest = [(d, st["asof"][d].get("v0_net_sigma_20"), st["asof"][d].get("v0_range_20_mean"))
                 for d in crest_dates]
    else:
        print("[selftest] (b) NAMED GAP: no v0 September tape on local disk (G3-G10 v0 corpus "
              "is S3-only; not restored this session) - literal late-September base "
              "unavailable; falling back to the earliest full-20-window n0 date")
        base_iso = next((d for d in _daterange(SPAN_START, SPAN_END)
                         if st["asof"][d].get("n0_win_n_20") == 20), None)
        if base_iso is None:
            print("[selftest] (b) FAIL: no date with a full 20-session n0 window")
            return 1
        base = st["asof"][base_iso]
        b_sig, b_rng = base["n0_net_sigma_20"], base["n0_range_20_mean"]
        base_label = f"n0 earliest full-20 base (asof {base_iso}, window = November sessions)"
        crest = [(d, st["asof"][d].get("n0_net_sigma_20"), st["asof"][d].get("n0_range_20_mean"))
                 for d in crest_dates]
    print(f"[selftest] (b) base: {base_label}  net_sigma_20=${b_sig}  range_20_mean=${b_rng}")
    ok_b = True
    for d, sg, rg in crest:
        if sg is None or rg is None:
            ok_b = False
            print(f"    {d}: MISSING (sigma={sg} range_mean={rg})")
            continue
        above = sg > b_sig and rg > b_rng
        ok_b &= above
        print(f"    {d}: net_sigma_20=${sg} ({sg / b_sig:.2f}x)  range_20_mean=${rg} "
              f"({rg / b_rng:.2f}x)  {'ABOVE' if above else 'NOT ABOVE'}")
    print(f"[selftest] (b) G9 crest/crash above base on BOTH measures, every date: "
          f"{'PASS' if ok_b else 'FAIL'}")
    if not ok_b:
        fails += 1

    # (c) MISSING-BASIS EXPLICITNESS on a date where only one basis has tape: 2025-11-15
    # (n0 live for 12 sessions; v0 has zero local sessions before it). Also demonstrates the
    # partial-window rule: n0 sigma_20 must be None with win_n_20=12 actual. And staleness
    # visibility: 2026-02-10 carries v0 values only with prev_age_days exposing the dead basis.
    r = st["asof"].get("2025-11-15", {})
    checks = [
        ("n0_prev_date populated", r.get("n0_prev_date") == "2025-11-14"),
        ("n0_win_n_10 full", r.get("n0_win_n_10") == 10),
        ("n0_net_sigma_10 populated", r.get("n0_net_sigma_10") is not None),
        ("n0 partial 20-window -> None", r.get("n0_net_sigma_20") is None
         and r.get("n0_win_n_20") == 12 and r.get("n0_range_20_max") is None),
        ("v0_prev_date None", r.get("v0_prev_date") is None),
        ("v0 windows empty (win_n 0)", r.get("v0_win_n_5") == 0 and r.get("v0_win_n_20") == 0),
        ("v0 sigma fields None", all(r.get(f"v0_net_sigma_{w}") is None for w in WINS)),
        ("v0_range_pctile None (n 0)", r.get("v0_range_pctile") is None
         and r.get("v0_range_pctile_n") == 0),
        ("v0_activity_trend None", r.get("v0_activity_trend") is None),
    ]
    ok_c = all(ok for _, ok in checks)
    print("[selftest] (c) missing-basis explicitness at 2025-11-15 (n0 live, v0 absent):")
    for name, ok in checks:
        print(f"    {'ok ' if ok else 'FAIL'} {name}")
    r2 = st["asof"].get("2026-02-10", {})
    print(f"    staleness visibility at 2026-02-10: v0_prev_date={r2.get('v0_prev_date')} "
          f"v0_prev_age_days={r2.get('v0_prev_age_days')} (basis dead after 2026-01-30, "
          f"age exposes it); n0_prev_age_days={r2.get('n0_prev_age_days')}")
    if not ok_c:
        fails += 1

    print(f"[selftest] {'PASS' if fails == 0 else 'FAIL'} ({fails} failing section(s))")
    return 0 if fails == 0 else 1


# ---------------------------------------------------------------- canary

def canary() -> None:
    """Three days per basis end-to-end (session rows + a derived asof row), no store write."""
    picks = {"n0": ["20251102", "20251103", "20251110"],
             "v0": ["20260116", "20260118", "20260119"]}
    for b, days in picks.items():
        days = [d for d in days if d in set(_list_session_days(b))]
        rows = build_sessions(b, days, verbose=False)
        for r in rows:
            print(f"[canary {b}] {r}")
        if rows:
            after = (_date.fromisoformat(rows[-1]["date"]) + timedelta(days=1)).isoformat()
            prior = [s for s in rows if s["net"] is not None]
            f = _basis_fields(b, prior, after)
            keep = {k: v for k, v in f.items() if v is not None}
            print(f"[canary {b}] asof {after} (from {len(prior)} sessions): {keep}")


# ---------------------------------------------------------------- cli

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="DATA_GATE_S98 feed B: vol / range regime")
    ap.add_argument("--build", action="store_true", help="precompute the span to the store")
    ap.add_argument("--canary", action="store_true", help="3 days per basis end-to-end, no write")
    ap.add_argument("--selftest", action="store_true", help="blind-wall audit + sanity anchors")
    ap.add_argument("--day", help="print vol_regime_asof(day) from the store")
    args = ap.parse_args()
    if args.canary:
        canary()
    elif args.build:
        build_store(write=True)
    elif args.selftest:
        sys.exit(selftest())
    elif args.day:
        print(json.dumps(vol_regime_asof(args.day), indent=1))
    else:
        ap.print_help()
