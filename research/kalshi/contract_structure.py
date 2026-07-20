"""
contract_structure.py - the CONTRACT STRUCTURE feed for the NG intraday forecaster (S98).

WHY THIS EXISTS
---------------
In the G11 block (2026-01-18..01-30) the EXPIRING February contract went parabolic into delivery
(3.0 -> 5.4) while MARCH - the contract the forecaster was actually reading - traded 2.7 -> 4.4.
The Feb/Mar spread widened from -0.41 (Jan 16) to -1.54 (Jan 22). A delivery squeeze was underway
and the forecast agent had NO state variable that could show it. The unblinded refine independently
named this as the mechanism behind the block's largest day (Jan 30) and listed the missing variable.

This module supplies those state variables as an INPUT. It does not gate, score, rank or recommend
anything - the agent decides how to use it.

FIELDS (per trading day, all strictly-prior / decision-time safe)
-----------------------------------------------------------------
  days_to_front_expiry      calendar + business days from the session to the FRONT contract's
                            expiration. Sourced from Databento's `definition` schema (authoritative
                            CME expiration); the computed CME rule (3 business days before the first
                            calendar day of the delivery month, holiday-aware) is a FALLBACK only.
                            `expiry_source` records which was used, per day.
  front_next_spread         front minus next settlement, plus its 1/3/5-session CHANGE. The RATE of
                            widening is the squeeze tell more than the level.
  open_interest             front + next open interest and day-over-day change (Databento
                            `statistics` schema, stat_type OPEN_INTEREST).
  oi_volume_divergence      whether the OI-selected front month (NG.n.0) and the volume-selected
                            front month (NG.v.0) point at DIFFERENT instruments. They disagreed
                            repeatedly through the G11 expiry week (see PASS2_CONTINUOUS_SERIES_NOTES).
  curve_regime              backwardation / contango / flat from the multi-month forward curve,
                            including the MARCH/APRIL spread (NGH-NGJ), NG's most-watched structural
                            spread (end of withdrawal season).

MISSING IS EXPLICIT, NEVER ZERO
-------------------------------
Every field is None when unknown. A zeroed spread reads as "front and next are at parity" - exactly
wrong during a squeeze, which is the one moment this feed exists for. Nothing is filled, interpolated
or defaulted. Zero synthetic data.

LEAKAGE
-------
`contract_structure_asof(date)` derives EVERY market-observed quantity from sessions STRICTLY BEFORE
`date`. A session's own settlement, open interest and instrument selection are end-of-session facts
and can never enter that session's open-time state. The only same-day quantities are pure CALENDAR
facts (the date, and the distance to a contract expiration that was published months earlier), which
are known before the open by construction.

DATA INPUTS (already on disk; this module does not pull tape)
-------------------------------------------------------------
  data/nymex_cont_n0/NG_YYYYMMDD.jsonl.gz   OI-continuous FRONT month trades
  data/nymex_cont_n1/NG_YYYYMMDD.jsonl.gz   OI-continuous NEXT month trades
  data/nymex_cont/NG_YYYYMMDD.jsonl.gz      VOLUME-continuous front (partial; rest -> divergence None)
  data/contract_structure/NG_instrument_map.json.gz   definitions: iid->symbol per day + expirations
  data/contract_structure/NG_statistics_raw.json.gz   statistics: settlements + open interest
  data/nymex_curve/NG_curve.json            forward curve (forward_curve.py --pull)

PUBLIC API
----------
  contract_structure_asof(date: str, root: str = "NG") -> dict | None
      date: "YYYY-MM-DD" (also accepts "YYYYMMDD"). Returns the decision-time contract-structure
      state for that session, or None if the feed has no session strictly before `date`. All values
      may individually be None. Never raises on missing data.

CLI
---
  python research/kalshi/contract_structure.py --selftest
  python research/kalshi/contract_structure.py --build          # scan tape -> sessions cache
  python research/kalshi/contract_structure.py --emit           # write NG_structure.json
  python research/kalshi/contract_structure.py --show 2026-01-22
  python research/kalshi/contract_structure.py --table 2026-01-12 2026-01-30
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
from datetime import date as _date, datetime, timedelta, timezone

# S98 Tier 0 fix: anchor to the repo root (module-relative), not the CWD - the S97 paths only worked
# when invoked from the repo root, so `contract_structure_asof` silently returned None from any other
# CWD (observed wiring decision_state). Matches cot_feed.py's _REPO pattern.
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(_REPO, "data", "contract_structure")
N0_DIR = os.path.join(_REPO, "data", "nymex_cont_n0")     # OI-continuous FRONT
N1_DIR = os.path.join(_REPO, "data", "nymex_cont_n1")     # OI-continuous NEXT
V0_DIR = os.path.join(_REPO, "data", "nymex_cont")        # VOLUME-continuous front (partial coverage)
CURVE_DIR = os.path.join(_REPO, "data", "nymex_curve")

SESSIONS_PATH = os.path.join(DATA_DIR, "NG_sessions.json")
STRUCTURE_PATH = os.path.join(DATA_DIR, "NG_structure.json")
INSTMAP_PATH = os.path.join(DATA_DIR, "NG_instrument_map.json.gz")
STATS_PATH = os.path.join(DATA_DIR, "NG_statistics_raw.json.gz")

# NYMEX/CME month codes -> delivery month number.
MONTH_CODE = {"F": 1, "G": 2, "H": 3, "J": 4, "K": 5, "M": 6,
              "N": 7, "Q": 8, "U": 9, "V": 10, "X": 11, "Z": 12}

# CME holidays (full closures) relevant to the covered window. Used ONLY by the computed-rule
# FALLBACK for expiry; the authoritative path reads Databento definitions and ignores this.
CME_HOLIDAYS = {
    "2025-01-01", "2025-01-09", "2025-01-20", "2025-02-17", "2025-04-18", "2025-05-26",
    "2025-06-19", "2025-07-04", "2025-09-01", "2025-11-27", "2025-12-25",
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25",
    "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
    "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31",
    "2027-06-18", "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24",
}


# =====================================================================================
# small helpers
# =====================================================================================
def _norm_date(d: str) -> str:
    """'20260122' or '2026-01-22' -> '2026-01-22'."""
    s = str(d).strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return s


def _compact(d: str) -> str:
    return _norm_date(d).replace("-", "")


def _is_business_day(d: _date) -> bool:
    return d.weekday() < 5 and d.isoformat() not in CME_HOLIDAYS


def business_days_between(a: str, b: str) -> int | None:
    """Business days from a (exclusive) to b (inclusive), CME-holiday aware. Negative if b < a."""
    try:
        da = _date.fromisoformat(_norm_date(a))
        dbb = _date.fromisoformat(_norm_date(b))
    except Exception:
        return None
    sign = 1 if dbb >= da else -1
    lo, hi = (da, dbb) if sign > 0 else (dbb, da)
    n, cur = 0, lo
    while cur < hi:
        cur += timedelta(days=1)
        if _is_business_day(cur):
            n += 1
    return n * sign


def computed_expiry(symbol: str) -> str | None:
    """
    FALLBACK CME rule: NG futures terminate 3 business days BEFORE the first calendar day of the
    delivery month, accounting for CME holidays. symbol e.g. 'NGG26' -> Feb-2026 delivery.
    Returns 'YYYY-MM-DD' or None if the symbol cannot be parsed.
    """
    s = str(symbol).upper()
    if not s.startswith("NG") or len(s) < 5:
        return None
    code, yy = s[2], s[3:]
    if code not in MONTH_CODE or not yy.isdigit():
        return None
    mon = MONTH_CODE[code]
    yr = 2000 + int(yy) if len(yy) == 2 else int(yy)
    first = _date(yr, mon, 1)
    cur, back = first, 0
    while back < 3:
        cur -= timedelta(days=1)
        if _is_business_day(cur):
            back += 1
    return cur.isoformat()


def contract_sort_key(symbol: str) -> tuple:
    """Chronological delivery order for 'NGG26' style symbols."""
    s = str(symbol).upper()
    if len(s) >= 5 and s[2] in MONTH_CODE and s[3:].isdigit():
        yy = s[3:]
        return (2000 + int(yy) if len(yy) == 2 else int(yy), MONTH_CODE[s[2]])
    return (9999, 99)


# =====================================================================================
# tape scan -> per-session observations
# =====================================================================================
def _scan_day(path: str) -> dict | None:
    """One continuous-series day file -> dominant instrument, trade count, last price."""
    if not os.path.exists(path):
        return None
    counts: dict[int, int] = {}
    last_ts, last_px = None, None
    n = 0
    try:
        with gzip.open(path, "rt") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                iid = r.get("instrument_id")
                if iid is not None:
                    counts[int(iid)] = counts.get(int(iid), 0) + 1
                ts, px = r.get("ts"), r.get("price")
                if ts is not None and px is not None and (last_ts is None or ts >= last_ts):
                    last_ts, last_px = ts, float(px)
                n += 1
    except Exception:
        return None
    if not n:
        return None
    dom = max(counts, key=counts.get) if counts else None
    return {"n_trades": n, "instrument_id": dom, "instrument_counts": counts,
            "last_price": last_px, "last_ts": last_ts}


def build_sessions(root: str = "NG") -> dict:
    """
    Scan the on-disk continuous tapes into a per-session observation table. This is the raw,
    end-of-session record; the strictly-prior logic lives in contract_structure_asof.
    """
    instmap = _load_instmap()
    per_day = instmap.get("per_day", {})
    sessions: dict[str, dict] = {}
    for label, d in (("n0", N0_DIR), ("n1", N1_DIR), ("v0", V0_DIR)):
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not (fn.startswith(f"{root}_") and fn.endswith(".jsonl.gz")):
                continue
            day = fn[len(root) + 1:len(root) + 9]
            if not day.isdigit():
                continue
            got = _scan_day(os.path.join(d, fn))
            if not got:
                continue
            iso = _norm_date(day)
            rec = sessions.setdefault(iso, {"date": iso})
            sym = per_day.get(day, {}).get(str(got["instrument_id"])) if got["instrument_id"] else None
            rec[label] = {"instrument_id": got["instrument_id"], "symbol": sym,
                          "n_trades": got["n_trades"], "last_price": got["last_price"]}
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SESSIONS_PATH, "w") as f:
        json.dump(sessions, f, sort_keys=True, indent=0)
    print(f"[cs] sessions: {len(sessions)} -> {SESSIONS_PATH}")
    return sessions


# =====================================================================================
# loaders
# =====================================================================================
def _load_json(path):
    if not os.path.exists(path):
        return {}
    try:
        opener = gzip.open if path.endswith(".gz") else open
        with opener(path, "rt") as f:
            return json.load(f)
    except Exception:
        return {}


def _load_instmap() -> dict:
    return _load_json(INSTMAP_PATH) or {"per_day": {}, "expiration": {}}


_STATS_CACHE = None


UNDEF_QTY = 2147483647          # DBN int32 UNDEF sentinel - a settlement row's `quantity` is NOT an OI


def _load_stats() -> dict:
    """
    statistics schema -> {session_date: {symbol: {key: {"value": v, "pub": 'YYYY-MM-DD'}}}}
    for key in {"settlement", "open_interest"}.

    Databento StatType: 3 = SETTLEMENT_PRICE, 9 = OPEN_INTEREST.

    `session_date` comes from ts_ref (the trade date the statistic DESCRIBES). `pub` is the EARLIEST
    ts_event carrying that value - i.e. when the number first became knowable. CME publishes a
    session's open interest the FOLLOWING morning, so the two dates differ and the read must respect
    it; `pub` is what makes the strictly-prior guarantee real rather than nominal.

    Values that are absent stay absent - never zero-filled. Prices arrive already float-scaled from
    to_df; the settlement row's `quantity` is the int32 UNDEF sentinel and is discarded.
    """
    global _STATS_CACHE
    if _STATS_CACHE is not None:
        return _STATS_CACHE
    out: dict[str, dict] = {}
    if not os.path.exists(STATS_PATH):
        _STATS_CACHE = out
        return out
    try:
        with gzip.open(STATS_PATH, "rt") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                st = r.get("stat_type")
                if st not in (3, 9):
                    continue
                sess = _stat_day(r.get("ts_ref"))
                pub = _stat_day(r.get("ts_event")) or sess
                sym = r.get("symbol")
                if not sess or not sym:
                    continue
                if st == 3:
                    px = r.get("price")
                    if px is None:
                        continue
                    px = float(px)
                    if not (0 < px < 1000):
                        continue
                    key, val = "settlement", px
                else:
                    q = r.get("quantity")
                    if q is None or int(q) < 0 or int(q) == UNDEF_QTY:
                        continue
                    key, val = "open_interest", int(q)
                slot = out.setdefault(_norm_date(sess), {}).setdefault(str(sym), {})
                cur = slot.get(key)
                # keep the value, and the EARLIEST publication day observed for it
                if cur is None:
                    slot[key] = {"value": val, "pub": _norm_date(pub)}
                elif cur["value"] == val:
                    cur["pub"] = min(cur["pub"], _norm_date(pub))
                elif _norm_date(pub) > cur["pub"]:
                    slot[key] = {"value": val, "pub": _norm_date(pub)}   # a later revision
    except Exception:
        pass
    _STATS_CACHE = out
    return out


def _stat_asof(stats: dict, symbol: str | None, key: str, before: str,
               sessions_desc: list[str]) -> tuple:
    """
    Latest (value, session_date) for `symbol`.`key` from a session STRICTLY BEFORE `before` whose
    value was also PUBLISHED strictly before `before`. (None, None) when unknown - never 0.
    """
    if not symbol:
        return None, None
    for s in sessions_desc:
        if s >= before:
            continue
        e = (stats.get(s, {}).get(symbol, {}) or {}).get(key)
        if e and e.get("pub", "9999") < before:
            return e["value"], s
    return None, None


def _stat_day(ts) -> str | None:
    """statistics ts (epoch seconds/ms/ns, or ISO) -> 'YYYYMMDD'."""
    if ts is None:
        return None
    try:
        if isinstance(ts, str):
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%Y%m%d")
        v = float(ts)
        for div in (1e9, 1e6, 1e3, 1.0):
            cand = v / div
            if 1.5e9 < cand < 2.5e9:
                return datetime.fromtimestamp(cand, timezone.utc).strftime("%Y%m%d")
    except Exception:
        return None
    return None


def _load_curve(root: str = "NG") -> dict:
    return _load_json(os.path.join(CURVE_DIR, f"{root}_curve.json"))


_SESSIONS_CACHE = None


def load_sessions() -> dict:
    global _SESSIONS_CACHE
    if _SESSIONS_CACHE is None:
        _SESSIONS_CACHE = _load_json(SESSIONS_PATH)
    return _SESSIONS_CACHE


# =====================================================================================
# expiry
# =====================================================================================
def front_expiry(symbol: str, instmap: dict | None = None) -> tuple[str | None, str]:
    """
    (expiry 'YYYY-MM-DD', source) for a contract symbol. Prefers the AUTHORITATIVE Databento
    definition expiration; falls back to the computed CME rule. source in
    {"definition", "computed_rule", "none"}.
    """
    if not symbol:
        return None, "none"
    im = instmap if instmap is not None else _load_instmap()
    raw = (im.get("expiration") or {}).get(str(symbol).upper())
    if raw:
        try:
            return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date().isoformat(), "definition"
        except Exception:
            pass
    c = computed_expiry(symbol)
    return (c, "computed_rule") if c else (None, "none")


# =====================================================================================
# the feed
# =====================================================================================
def _settle(stats: dict, day: str, sym: str | None, key: str):
    """Raw end-of-session value for one session (NOT leakage-filtered; for --table reporting)."""
    if not sym:
        return None
    e = (stats.get(_norm_date(day), {}).get(sym, {}) or {}).get(key)
    return e["value"] if e else None


def _front_next_spread_on(session_date: str, sessions: dict, stats: dict):
    """
    front minus next for ONE session, using settlement where available and the session's last trade
    price as the fallback. Returns (spread, basis, front_sym, next_sym); spread is None if either
    leg is unknown. NEVER zero-filled. Both legs always come from the SAME session, so the number is
    a real calendar spread and never a cross-session artifact.
    """
    rec = sessions.get(session_date) or {}
    n0, n1 = rec.get("n0") or {}, rec.get("n1") or {}
    fs, ns = n0.get("symbol"), n1.get("symbol")
    f_set = _settle(stats, session_date, fs, "settlement")
    n_set = _settle(stats, session_date, ns, "settlement")
    if f_set is not None and n_set is not None:
        return round(f_set - n_set, 4), "settlement", fs, ns
    f_px, n_px = n0.get("last_price"), n1.get("last_price")
    if f_px is not None and n_px is not None:
        return round(float(f_px) - float(n_px), 4), "last_trade", fs, ns
    return None, "none", fs, ns


def contract_structure_asof(date: str, root: str = "NG") -> dict | None:
    """
    Decision-time CONTRACT STRUCTURE state for `date`.

    Args:
        date: "YYYY-MM-DD" or "YYYYMMDD" - the session whose OPEN-time state is wanted.
        root: futures root (only "NG" is built today).

    Returns:
        dict of state variables, or None if no session exists strictly before `date`.
        Every value may independently be None; missing is ALWAYS None, never 0.

    Leakage: all market observations come from sessions strictly BEFORE `date`. Only calendar
    facts (the expiry distance) reference `date` itself.
    """
    d = _norm_date(date)
    # Reject an unparseable date rather than letting it through: every lookup here is a STRING
    # comparison, and an arbitrary string compares greater than every ISO date, so a malformed input
    # would silently return the last session's state as if it were valid.
    try:
        _date.fromisoformat(d)
    except Exception:
        return None
    sessions = load_sessions()
    if not sessions:
        return None
    prior = sorted(x for x in sessions if x < d)
    if not prior:
        return None
    stats = _load_stats()
    instmap = _load_instmap()

    p0 = prior[-1]                                   # last session strictly before `date`
    rec = sessions.get(p0, {})
    n0, n1 = rec.get("n0") or {}, rec.get("n1") or {}
    front_sym, next_sym = n0.get("symbol"), n1.get("symbol")

    # ---- 1. days_to_front_expiry (calendar fact about `date`; expiry published months earlier)
    exp, exp_src = front_expiry(front_sym, instmap)
    dte_bus = business_days_between(d, exp) if exp else None
    dte_cal = None
    if exp:
        try:
            dte_cal = (_date.fromisoformat(exp) - _date.fromisoformat(d)).days
        except Exception:
            dte_cal = None

    # ---- 2. front_next_spread + its rate of change over 1/3/5 prior sessions
    # A spread CHANGE is only meaningful when both observations are on the SAME contract pair. Across
    # a roll it compares e.g. Feb-Mar to Mar-Apr, which is a contract-change artifact, not a market
    # move (the same class of artifact PASS2_CONTINUOUS_SERIES_NOTES documents for weekend gaps).
    # When the pair changed the change is None - undefined, not zero - and the flag says why.
    spread, basis, _, _ = _front_next_spread_on(p0, sessions, stats)
    cur_pair = (front_sym, next_sym)
    chg: dict[str, object] = {}
    for lag in (1, 3, 5):
        prev = prior[-1 - lag] if len(prior) > lag else None
        prec = (sessions.get(prev) or {}) if prev else {}
        prev_pair = ((prec.get("n0") or {}).get("symbol"), (prec.get("n1") or {}).get("symbol"))
        s_prev = _front_next_spread_on(prev, sessions, stats)[0] if prev else None
        rolled = bool(prev) and prev_pair != cur_pair
        chg[f"front_next_spread_chg_{lag}d"] = (
            None if (rolled or spread is None or s_prev is None) else round(spread - s_prev, 4))
        chg[f"front_next_pair_changed_{lag}d"] = rolled if prev else None

    # ---- 3. open interest, front + next, and day-over-day change.
    # CME publishes a session's OI the FOLLOWING morning, so the newest OI knowable at D's open is
    # often session D-2's, not D-1's. _stat_asof enforces that with the publication day; the session
    # each figure actually came from is reported alongside it so the staleness is visible, not hidden.
    desc = sorted(sessions, reverse=True)
    oi_f, oi_f_sess = _stat_asof(stats, front_sym, "open_interest", d, desc)
    oi_n, oi_n_sess = _stat_asof(stats, next_sym, "open_interest", d, desc)
    oi_f_p = oi_n_p = None
    if oi_f_sess:
        oi_f_p, _ = _stat_asof(stats, front_sym, "open_interest", oi_f_sess, desc)
    if oi_n_sess:
        oi_n_p, _ = _stat_asof(stats, next_sym, "open_interest", oi_n_sess, desc)

    # ---- 4. OI-vs-VOLUME front-month divergence (prior session; own-session is EOS information)
    v0 = rec.get("v0") or {}
    v_sym, v_iid = v0.get("symbol"), v0.get("instrument_id")
    n_iid = n0.get("instrument_id")
    if v_iid is None or n_iid is None:
        divergence, v_note = None, "v0_absent"          # NOT False - genuinely unknown
    else:
        divergence, v_note = (v_iid != n_iid), "compared"

    # ---- 5. curve regime (strictly-prior by construction inside forward_curve.curve_asof)
    curve = _load_curve(root)
    cf = None
    if curve:
        prior_c = [x for x in curve if x < d]
        if prior_c:
            cf = curve[max(prior_c)]

    # ---- 6. the CALENDAR front (nearest-expiry), which is NOT always the OI-continuous front.
    # This is the field that makes a delivery squeeze visible. Once open interest has migrated out of
    # an expiring contract, NG.n.0 rolls forward and the dying contract vanishes from the n0/n1 view
    # entirely - which is exactly what happened in G11: on 2026-01-22 n0/n1 read Mar/Apr while the
    # contract actually going parabolic was Feb. The curve's rank 0/1 keep the nearest-expiry pair,
    # so the expiring leg stays observable right up to its last trade date.
    cal_syms = (cf or {}).get("symbols") or {}
    cal_front = cal_syms.get("0")
    cal_next = cal_syms.get("1")
    cal_exp, cal_exp_src = front_expiry(cal_front, instmap) if cal_front else (None, "none")
    cal_spread = round(-(cf["slope_1"]), 4) if cf and cf.get("slope_1") is not None else None
    # Same roll discipline as the n0/n1 spread: a change across a contract roll is undefined, not a
    # move. In G11 the Jan-30 roll from Feb/Mar to Mar/Apr would otherwise print a -3.2 "collapse".
    cal_chg: dict[str, object] = {}
    cdates = sorted(x for x in curve if x < d) if curve else []
    cur_c = curve[cdates[-1]] if cdates else None
    cur_cpair = ((cur_c.get("symbols") or {}).get("0"), (cur_c.get("symbols") or {}).get("1")) if cur_c else (None, None)
    for lag in (1, 3, 5):
        prv = curve[cdates[-1 - lag]] if len(cdates) > lag else None
        prv_pair = ((prv.get("symbols") or {}).get("0"), (prv.get("symbols") or {}).get("1")) if prv else (None, None)
        rolled = bool(prv) and prv_pair != cur_cpair
        ok = (cur_c and prv and not rolled
              and cur_c.get("slope_1") is not None and prv.get("slope_1") is not None)
        cal_chg[f"calendar_front_next_spread_chg_{lag}d"] = (
            round(-(cur_c["slope_1"]) + prv["slope_1"], 4) if ok else None)
        cal_chg[f"calendar_front_pair_changed_{lag}d"] = rolled if prv else None

    return {
        "date": d,
        "asof_session": p0,
        "root": root,

        "calendar_front_symbol": cal_front,
        "calendar_next_symbol": cal_next,
        "calendar_front_expiry": cal_exp,
        "calendar_front_expiry_source": cal_exp_src,
        "days_to_calendar_front_expiry": business_days_between(d, cal_exp) if cal_exp else None,
        "calendar_front_settle": (cf or {}).get("front"),
        "calendar_next_settle": (cf or {}).get("c1"),
        "calendar_front_next_spread": cal_spread,
        **cal_chg,
        "front_is_calendar_front": ((cal_front == front_sym) if (cal_front and front_sym) else None),

        "front_symbol": front_sym,
        "next_symbol": next_sym,
        "front_expiry": exp,
        "expiry_source": exp_src,
        "days_to_front_expiry": dte_bus,
        "days_to_front_expiry_calendar": dte_cal,

        "front_next_spread": spread,
        "front_next_spread_basis": basis,
        **chg,

        "open_interest_front": oi_f,
        "open_interest_next": oi_n,
        "open_interest_front_session": oi_f_sess,
        "open_interest_next_session": oi_n_sess,
        "open_interest_front_chg_1d": (oi_f - oi_f_p) if (oi_f is not None and oi_f_p is not None) else None,
        "open_interest_next_chg_1d": (oi_n - oi_n_p) if (oi_n is not None and oi_n_p is not None) else None,

        "oi_volume_divergence": divergence,
        "oi_volume_divergence_note": v_note,
        "oi_front_symbol": front_sym,
        "volume_front_symbol": v_sym,

        "curve_regime": (cf or {}).get("regime"),
        "curve_asof": max([x for x in curve if x < d]) if curve and [x for x in curve if x < d] else None,
        "curve_slope_1": (cf or {}).get("slope_1"),
        "curve_slope_back": (cf or {}).get("slope_back"),
        "curve_curvature": (cf or {}).get("curvature"),
        "mar_apr_spread": (cf or {}).get("mar_apr_spread"),
        "mar_apr_pair": (cf or {}).get("mar_apr_pair"),
    }


def emit(root: str = "NG") -> dict:
    """Materialize contract_structure_asof for every covered session -> NG_structure.json."""
    sessions = load_sessions()
    out = {}
    for d in sorted(sessions):
        got = contract_structure_asof(d, root)
        if got:
            out[d] = got
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(STRUCTURE_PATH, "w") as f:
        json.dump(out, f, sort_keys=True, indent=0)
    print(f"[cs] structure: {len(out)} dated states -> {STRUCTURE_PATH}")
    return out


# =====================================================================================
# selftest
# =====================================================================================
def selftest() -> int:
    ok = True

    def check(name, cond):
        nonlocal ok
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        ok = ok and cond

    # --- date normalization
    check("norm compact", _norm_date("20260122") == "2026-01-22")
    check("norm iso passthrough", _norm_date("2026-01-22") == "2026-01-22")

    # --- computed CME expiry rule: NG Feb-2026 = 3 business days before 2026-02-01.
    # Feb 1 2026 is a Sunday; back up: Fri Jan 30 (1), Thu Jan 29 (2), Wed Jan 28 (3).
    check("computed expiry NGG26 = 2026-01-28", computed_expiry("NGG26") == "2026-01-28")
    # NG Jan-2026: Jan 1 2026 is a CME holiday (Thu). Back from Jan 1: Wed Dec 31 (1),
    # Tue Dec 30 (2), Mon Dec 29 (3).
    check("computed expiry NGF26 = 2025-12-29", computed_expiry("NGF26") == "2025-12-29")
    check("computed expiry bad symbol -> None", computed_expiry("XX") is None)

    # --- holidays are honoured by the business-day walk
    # 2026-01-19 is MLK (CME closed): Jan 16 (Fri) -> Jan 20 (Tue) is 1 business day, not 2.
    check("business days skip MLK 2026", business_days_between("2026-01-16", "2026-01-20") == 1)
    check("business days skip weekend", business_days_between("2026-01-16", "2026-01-19") == 0)
    check("business days negative when b<a", business_days_between("2026-01-20", "2026-01-16") == -1)

    # --- chronological contract ordering
    check("contract order G26 < H26", contract_sort_key("NGG26") < contract_sort_key("NGH26"))
    check("contract order Z26 < F27", contract_sort_key("NGZ26") < contract_sort_key("NGF27"))

    # --- MISSING IS EXPLICIT, NEVER ZERO (the central invariant)
    sp = _front_next_spread_on("1999-01-01", {}, {})
    check("absent session -> spread None (not 0.0)", sp[0] is None and sp[1] == "none")
    empty = _front_next_spread_on("2026-01-22", {"2026-01-22": {"n0": {"symbol": "NGG26"}}}, {})
    check("one leg missing -> spread None (not 0.0)", empty[0] is None)

    # --- expiry falls back cleanly and reports its source
    e, src = front_expiry("NGG26", {"expiration": {}})
    check("expiry falls back to computed rule", e == "2026-01-28" and src == "computed_rule")
    e2, src2 = front_expiry("NGG26", {"expiration": {"NGG26": "2026-01-28T19:30:00+0000"}})
    check("expiry prefers definition", e2 == "2026-01-28" and src2 == "definition")
    check("expiry unknown symbol -> none", front_expiry(None, {})[1] == "none")

    # --- LEAKAGE: asof must never read the session's own or any later data
    fake = {"2026-01-20": {"date": "2026-01-20", "n0": {"symbol": "NGG26", "instrument_id": 1,
                                                        "last_price": 5.0},
                            "n1": {"symbol": "NGH26", "instrument_id": 2, "last_price": 4.0}},
            "2026-01-21": {"date": "2026-01-21", "n0": {"symbol": "NGG26", "instrument_id": 1,
                                                        "last_price": 9.9},
                            "n1": {"symbol": "NGH26", "instrument_id": 2, "last_price": 1.1}}}
    global _SESSIONS_CACHE, _STATS_CACHE
    _SESSIONS_CACHE, _STATS_CACHE = fake, {}
    got = contract_structure_asof("2026-01-21")
    check("asof uses strictly-prior session", got is not None and got["asof_session"] == "2026-01-20")
    check("asof spread is prior session's (no same-day leak)", got["front_next_spread"] == 1.0)
    check("asof before earliest -> None", contract_structure_asof("2026-01-20") is None)
    check("divergence unknown -> None, not False", got["oi_volume_divergence"] is None)
    check("absent OI -> None, not 0", got["open_interest_front"] is None)

    # --- PUBLICATION LAG: a value describing a prior session but published ON `date` is NOT knowable
    desc = ["2026-01-21", "2026-01-20"]
    st = {"2026-01-20": {"NGG26": {"open_interest": {"value": 100, "pub": "2026-01-21"}}},
          "2026-01-19": {"NGG26": {"open_interest": {"value": 90, "pub": "2026-01-20"}}}}
    v, s = _stat_asof(st, "NGG26", "open_interest", "2026-01-21", ["2026-01-20", "2026-01-19"])
    check("OI published same day is excluded", v == 90 and s == "2026-01-19")
    v2, _ = _stat_asof(st, "NGG26", "open_interest", "2026-01-22", ["2026-01-20", "2026-01-19"])
    check("OI published day before is included", v2 == 100)
    check("OI unknown symbol -> None", _stat_asof(st, None, "open_interest", "2026-01-22", desc)[0] is None)

    # --- settlement rows carry the int32 UNDEF sentinel in `quantity`; it must never become an OI
    check("UNDEF sentinel recognised", UNDEF_QTY == 2147483647)

    # --- ROLL ARTIFACT: a spread change across a contract change is UNDEFINED, never a "move"
    rolled = {"2026-01-28": {"date": "2026-01-28",
                             "n0": {"symbol": "NGG26", "instrument_id": 1, "last_price": 6.4},
                             "n1": {"symbol": "NGH26", "instrument_id": 2, "last_price": 3.8}},
              "2026-01-29": {"date": "2026-01-29",
                             "n0": {"symbol": "NGH26", "instrument_id": 2, "last_price": 3.9},
                             "n1": {"symbol": "NGJ26", "instrument_id": 3, "last_price": 3.7}}}
    _SESSIONS_CACHE, _STATS_CACHE = rolled, {}
    g2 = contract_structure_asof("2026-01-30")
    check("spread itself still reported across a roll", g2["front_next_spread"] == 0.2)
    check("spread change across roll -> None, not a fake move",
          g2["front_next_spread_chg_1d"] is None)
    check("roll is flagged, not silent", g2["front_next_pair_changed_1d"] is True)
    _SESSIONS_CACHE, _STATS_CACHE = None, None
    nroll = {"2026-01-28": {"date": "2026-01-28",
                            "n0": {"symbol": "NGH26", "instrument_id": 2, "last_price": 3.5},
                            "n1": {"symbol": "NGJ26", "instrument_id": 3, "last_price": 3.4}},
             "2026-01-29": {"date": "2026-01-29",
                            "n0": {"symbol": "NGH26", "instrument_id": 2, "last_price": 3.9},
                            "n1": {"symbol": "NGJ26", "instrument_id": 3, "last_price": 3.7}}}
    _SESSIONS_CACHE, _STATS_CACHE = nroll, {}
    g3 = contract_structure_asof("2026-01-30")
    check("same-pair change is reported", g3["front_next_spread_chg_1d"] == 0.1)
    check("no-roll flag is False", g3["front_next_pair_changed_1d"] is False)
    # a malformed date must NOT silently resolve to the latest session (string compare would)
    check("malformed date -> None", contract_structure_asof("not-a-date") is None)
    check("empty date -> None", contract_structure_asof("") is None)
    _SESSIONS_CACHE, _STATS_CACHE = None, None
    _SESSIONS_CACHE, _STATS_CACHE = None, None

    print("SELFTEST:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


# =====================================================================================
# CLI
# =====================================================================================
def _table(start: str, end: str, root: str = "NG"):
    s, e = _norm_date(start), _norm_date(end)
    sessions = load_sessions()
    stats = _load_stats()
    print(f"{'date':<12}{'front':<8}{'next':<8}{'settle_f':>10}{'settle_n':>10}"
          f"{'spread':>9}{'chg1d':>8}{'dte':>5}  {'basis':<11}{'src':<13}")
    for d in sorted(x for x in sessions if s <= x <= e):
        st = contract_structure_asof(d, root) or {}
        rec = sessions.get(d, {})
        fs = (rec.get("n0") or {}).get("symbol")
        ns = (rec.get("n1") or {}).get("symbol")
        sf = _settle(stats, d, fs, "settlement")
        sn = _settle(stats, d, ns, "settlement")
        sp, basis, _, _ = _front_next_spread_on(d, sessions, stats)

        def f(v, w=10, p=3):
            return f"{v:>{w}.{p}f}" if isinstance(v, (int, float)) else f"{'-':>{w}}"
        print(f"{d:<12}{str(fs or '-'):<8}{str(ns or '-'):<8}{f(sf)}{f(sn)}{f(sp,9)}"
              f"{f(st.get('front_next_spread_chg_1d'),8)}"
              f"{str(st.get('days_to_front_expiry') if st.get('days_to_front_expiry') is not None else '-'):>5}"
              f"  {basis:<11}{str(st.get('expiry_source','-')):<13}")


def main() -> int:
    ap = argparse.ArgumentParser(description="NG contract-structure feed (delivery-squeeze state)")
    ap.add_argument("--build", action="store_true", help="scan tape -> sessions cache")
    ap.add_argument("--emit", action="store_true", help="write NG_structure.json")
    ap.add_argument("--show", help="print the asof state for a date")
    ap.add_argument("--table", nargs=2, metavar=("START", "END"), help="factual per-day table")
    ap.add_argument("--root", default="NG")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if args.build:
        build_sessions(args.root)
        return 0
    if args.emit:
        emit(args.root)
        return 0
    if args.show:
        got = contract_structure_asof(args.show, args.root)
        print(json.dumps(got, indent=2, sort_keys=True) if got else "None")
        return 0
    if args.table:
        _table(args.table[0], args.table[1], args.root)
        return 0
    ap.error("need --build / --emit / --show / --table / --selftest")


if __name__ == "__main__":
    sys.exit(main())
