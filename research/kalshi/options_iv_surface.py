"""
options_iv_surface.py - FEED I phase ii: the NG settle-IV surface (OPTIONS_COACH_RESEARCH_S100.1 E2 items 1-3).

WHY THIS EXISTS
---------------
The options coach's underlying state. Black-76 prices each option month off ITS OWN futures
contract (the curve IS the underlying - Greg's frame), so this module joins every strike's
settle to that month's futures settle (NEVER a continuous series; the S97 calendar-front
lesson generalized) and inverts Black-76 per strike. LNE (European) is the IV BACKBONE
(Black-76 exact); ON (American) IVs are recorded as iv_amer_naive; the matched-strike
ON-LNE settle-IV gap is exposed as a data product (the early-exercise premium measured,
not modeled - research C3).

MEASURED SCALE TRAP (this build's first find, 2026-07-20): LNE strike_price decodes at 1/10
of dollars - LNE K=0.4750 prices IDENTICALLY to ON K=4.75 (2026-01-22 NGH26: call 0.1792 vs
0.179, put 1.3473 vs 1.348 - matched to the tick across the ladder). LNE strikes are
therefore multiplied by LNE_STRIKE_SCALE=10 here, and the build VERIFIES the scale each run
by matched-pair pricing (selftest asserts the winner). CONSEQUENCE FOR PHASE I (reported,
not fixed here - the signal core owns options_surface.py): its COMBINED ON+LNE per-strike
pin view merges mismatched ladders; per-asset views are unaffected.

INPUTS (all on disk, $0): data/options_ng/surface.json.gz (phase i: per session/root/month/
strike [call_oi, put_oi, call_settle, put_settle] + opex dates) and
data/contract_structure/NG_statistics_raw.json.gz (per-contract futures settles, stat_type 3,
session in ts_ref). Cross-check: LNE put-call-parity-implied F vs the futures settle, recorded
per month-session.

MODEL (research C1): r fixed at 0.045 ACT/365 (disclosed, never tuned; <1% price effect at
our horizons); T = calendar days session->opex / 365; OTM side preferred per strike (puts
below F, calls above) to minimize intrinsic contamination; NO smoothing/global fit - raw
per-strike IVs + per-(month, session) FEATURES: atm_iv (linear-in-K interpolation across F),
rr25 (25d call IV - 25d put IV), fly25, front/next atm ratio, days_to_opex, ON-LNE ATM-band
gap, OI context. Missing = None, never interpolated across months. Settle marks on untraded
strikes are the settlement algorithm's opinion - every row carries OI so claims can degrade
honestly (ATM +-2 strikes trustworthy; 10-delta wings descriptive).

BLIND WALL (unchanged from phase i, binding): CME publishes settlements next morning;
surface_asof(iso) serves the latest session STRICTLY BEFORE iso.

STORE: data/options_ng/iv_surface.json.gz. No commits by this module; S3 push is the
orchestrator's step (suggested prefix options_iv/ to avoid rewriting the options_ng/
manifest owned by the phase-i pull).

USAGE
-----
  python research/kalshi/options_iv_surface.py --build
  python research/kalshi/options_iv_surface.py --selftest
  python research/kalshi/options_iv_surface.py --show 2026-01-22
  python research/kalshi/options_iv_surface.py --asof 2026-01-23
  python research/kalshi/options_iv_surface.py --inventory
"""

from __future__ import annotations

import argparse
import datetime
import gzip
import json
import math
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PHASE1_STORE = os.path.join(_ROOT, "data", "options_ng", "surface.json.gz")
FUT_STATS = os.path.join(_ROOT, "data", "contract_structure", "NG_statistics_raw.json.gz")
STORE_PATH = os.path.join(_ROOT, "data", "options_ng", "iv_surface.json.gz")

# LIVE-ERA BRIDGE (E2 item 5, pulled 2026-07-20, measured cost $0.00 in-subscription):
# raw dbn.zst under data/options_ng/raw/, Mar 1 - Jul 19 2026 sessions, decoded here with
# the SAME measured record rules as phase i (stat 3/9, ts_ref session, 1e9 fixed point,
# null sentinels, dedupe by instrument_id) and merged IN MEMORY - the phase-i store file
# is never touched (it stays the signal core's artifact, 81 winter sessions).
RAW_DIR = os.path.join(_ROOT, "data", "options_ng", "raw")
BRIDGE_OPT_DEFS = os.path.join(RAW_DIR, "glbx_ng_opt_definition_20260301_20260720.dbn.zst")
BRIDGE_OPT_STATS = os.path.join(RAW_DIR, "glbx_ng_opt_statistics_20260301_20260720.dbn.zst")
BRIDGE_FUT_STATS = os.path.join(RAW_DIR, "glbx_ng_fut_statistics_20260301_20260720.dbn.zst")
I64_NULL = 9223372036854775807
U64_NULL = 18446744073709551615
STAT_OPEN_INTEREST = 9

RATE = 0.045                 # fixed, disclosed, never tuned (research C1.2)
LNE_STRIKE_SCALE = 10.0      # measured (docstring); verified per build by matched-pair pricing
IV_LO, IV_HI = 0.01, 4.0     # inversion bracket, annualized
MIN_IVS_FOR_FEATURES = 5     # months with fewer OTM IVs carry strikes but no feature row
ATM_BAND_DOLLARS = 0.25      # ON-LNE gap band around F
STAT_SETTLEMENT = 3


# ------------------------------------------------------------------------------------------
# Black-76
# ------------------------------------------------------------------------------------------
def _ncdf(x: float) -> float:
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def black76(F: float, K: float, T: float, sigma: float, cp: str, r: float = RATE) -> float:
    if T <= 0 or sigma <= 0:
        intrinsic = max(0.0, F - K) if cp == "C" else max(0.0, K - F)
        return math.exp(-r * T) * intrinsic
    sT = sigma * math.sqrt(T)
    d1 = (math.log(F / K) + 0.5 * sigma * sigma * T) / sT
    d2 = d1 - sT
    df = math.exp(-r * T)
    if cp == "C":
        return df * (F * _ncdf(d1) - K * _ncdf(d2))
    return df * (K * _ncdf(-d2) - F * _ncdf(-d1))


def black76_delta(F: float, K: float, T: float, sigma: float, cp: str, r: float = RATE) -> float:
    sT = sigma * math.sqrt(T)
    d1 = (math.log(F / K) + 0.5 * sigma * sigma * T) / sT
    df = math.exp(-r * T)
    return df * _ncdf(d1) if cp == "C" else -df * _ncdf(-d1)


def implied_vol(price: float, F: float, K: float, T: float, cp: str) -> float | None:
    """Bisection inversion (monotone in sigma). None when the settle sits outside the
    no-arbitrage band for the bracket - recorded, never repaired (research C1)."""
    if price <= 0 or F <= 0 or K <= 0 or T <= 0:
        return None
    lo, hi = IV_LO, IV_HI
    p_lo, p_hi = black76(F, K, T, lo, cp), black76(F, K, T, hi, cp)
    if not (p_lo <= price <= p_hi):
        return None
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if black76(F, K, T, mid, cp) < price:
            lo = mid
        else:
            hi = mid
    return round(0.5 * (lo + hi), 5)


# ------------------------------------------------------------------------------------------
# inputs
# ------------------------------------------------------------------------------------------
def _load_phase1() -> dict:
    if not os.path.exists(PHASE1_STORE):
        sys.exit("[options_iv] phase i store absent - platform_sync pull options_ng/ first")
    with gzip.open(PHASE1_STORE, "rt", encoding="utf-8") as f:
        return json.load(f)


def _futures_settles() -> dict[str, dict[str, float]]:
    """{session_iso: {futures_symbol: settle}} from the contract-structure raw statistics
    (stat_type 3 = settlement; session date in ts_ref ms). Last write per key wins."""
    if not os.path.exists(FUT_STATS):
        sys.exit("[options_iv] futures statistics absent - platform_sync pull nymex/contract_structure/ first")
    out: dict[str, dict[str, float]] = {}
    with gzip.open(FUT_STATS, "rt", encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("stat_type") != STAT_SETTLEMENT or not r.get("symbol"):
                continue
            ts_ref = r.get("ts_ref")
            price = r.get("price")
            if ts_ref is None or price is None:
                continue
            iso = datetime.datetime.fromtimestamp(ts_ref / 1e3, tz=datetime.timezone.utc).date().isoformat()
            sym = r["symbol"].strip()
            if "-" in sym:                       # spreads carry a dash; single months only
                continue
            out.setdefault(iso, {})[sym] = float(price)
    return out


def _strike_real(root: str, k_store: str) -> float:
    k = float(k_store)
    return k * LNE_STRIKE_SCALE if root == "LNE" else k


def _ns_to_date(ns: int) -> str:
    return datetime.datetime.fromtimestamp(ns / 1e9, tz=datetime.timezone.utc).date().isoformat()


def _decode_bridge() -> tuple[dict, dict]:
    """Bridge raws -> (sessions phase-1-shaped, opex updates). Empty when raws absent."""
    if not (os.path.exists(BRIDGE_OPT_DEFS) and os.path.exists(BRIDGE_OPT_STATS)):
        return {}, {}
    import databento as db
    defs: dict[int, dict] = {}
    for rec in db.DBNStore.from_file(BRIDGE_OPT_DEFS):
        cls = str(getattr(rec, "instrument_class", ""))
        if cls not in ("InstrumentClass.CALL", "InstrumentClass.PUT", "C", "P"):
            continue
        defs[rec.instrument_id] = {
            "underlying": (rec.underlying or "").strip(),
            "asset": (rec.asset or "").strip(),
            "strike": rec.strike_price / 1e9,
            "cp": "C" if cls.endswith("CALL") or cls == "C" else "P",
            "opex": _ns_to_date(rec.expiration),
        }
    sessions: dict = {}
    for rec in db.DBNStore.from_file(BRIDGE_OPT_STATS):
        st = int(rec.stat_type)
        if st not in (STAT_SETTLEMENT, STAT_OPEN_INTEREST):
            continue
        d = defs.get(rec.instrument_id)
        if d is None or rec.ts_ref == U64_NULL:
            continue
        sess = _ns_to_date(rec.ts_ref)
        cell = (sessions.setdefault(sess, {}).setdefault(d["asset"], {})
                .setdefault(d["underlying"], {}).setdefault(f"{d['strike']:.4f}",
                                                            [None, None, None, None]))
        idx = 0 if d["cp"] == "C" else 1
        if st == STAT_OPEN_INTEREST and rec.quantity != I64_NULL and rec.quantity >= 0:
            cell[idx] = int(rec.quantity)
        elif st == STAT_SETTLEMENT and rec.price != I64_NULL:
            cell[2 + idx] = rec.price / 1e9
    opex: dict = {}
    for d in defs.values():
        opex.setdefault(d["asset"], {}).setdefault(d["underlying"], d["opex"])
    print(f"[options_iv] bridge decoded: {len(sessions)} sessions, {len(defs)} option defs")
    return sessions, opex


def _fut_settles_dbn() -> dict[str, dict[str, float]]:
    """Bridge futures settles (single months only) from the Mar-Jul statistics dbn.
    to_df(map_symbols=True) carries the symbol map from DBN metadata; prices pre-scaled."""
    if not os.path.exists(BRIDGE_FUT_STATS):
        return {}
    import databento as db
    df = db.DBNStore.from_file(BRIDGE_FUT_STATS).to_df(map_symbols=True)
    df = df[(df["stat_type"] == STAT_SETTLEMENT) & df["symbol"].notna()]
    df = df[~df["symbol"].str.contains("-")]
    out: dict[str, dict[str, float]] = {}
    for ts_ref, sym, price in zip(df["ts_ref"], df["symbol"], df["price"]):
        if price is None or price != price:
            continue
        out.setdefault(str(ts_ref.date()), {})[sym.strip()] = float(price)
    return out


# ------------------------------------------------------------------------------------------
# scale verification (runs at build; the selftest pins the winner)
# ------------------------------------------------------------------------------------------
def measure_lne_scale(p1: dict, n_sessions: int = 10) -> dict:
    """For candidate scales, price-match LNE strikes onto ON strikes (same session+month)
    and report median |settle diff| where the real strikes coincide. Smaller = truer."""
    scores = {1.0: [], 10.0: []}
    sessions = sorted(p1["sessions"])[:: max(1, len(p1["sessions"]) // n_sessions)]
    for iso in sessions:
        roots = p1["sessions"][iso]
        for month, on_ladder in roots.get("ON", {}).items():
            lne_ladder = roots.get("LNE", {}).get(month)
            if not lne_ladder:
                continue
            on_c = {round(float(k), 4): v[2] for k, v in on_ladder.items() if v[2] is not None}
            for scale in scores:
                for k, v in lne_ladder.items():
                    if v[2] is None:
                        continue
                    kk = round(float(k) * scale, 4)
                    if kk in on_c:
                        scores[scale].append(abs(v[2] - on_c[kk]))
    out = {}
    for scale, diffs in scores.items():
        diffs.sort()
        out[str(scale)] = {"n_matched": len(diffs),
                           "median_abs_settle_diff": round(diffs[len(diffs) // 2], 4) if diffs else None}
    return out


# ------------------------------------------------------------------------------------------
# build
# ------------------------------------------------------------------------------------------
def _month_ivs(root: str, ladder: dict, F: float, T: float) -> list[list]:
    """Per-strike rows [K_real, side_used, settle, iv, call_oi, put_oi]; OTM side preferred."""
    rows = []
    for k_store, (c_oi, p_oi, c_set, p_set) in sorted(ladder.items(), key=lambda kv: float(kv[0])):
        K = _strike_real(root, k_store)
        side, settle = ("C", c_set) if K >= F else ("P", p_set)
        if settle is None:                       # OTM side missing -> ITM side, flagged lowercase
            side, settle = ("p", p_set) if K >= F else ("c", c_set)
            settle = p_set if K >= F else c_set
        if settle is None:
            continue
        iv = implied_vol(settle, F, K, T, side.upper())
        rows.append([round(K, 4), side, settle, iv, c_oi, p_oi])
    return rows


def _interp_atm(rows: list[list], F: float) -> float | None:
    pts = [(r[0], r[3]) for r in rows if r[3] is not None and r[1] in ("C", "P")]
    if len(pts) < 2:
        return None
    below = [p for p in pts if p[0] <= F]
    above = [p for p in pts if p[0] > F]
    if not below or not above:
        return None
    k0, v0 = max(below)
    k1, v1 = min(above)
    if k1 == k0:
        return round(v0, 5)
    return round(v0 + (v1 - v0) * (F - k0) / (k1 - k0), 5)


def _delta_wing_iv(rows: list[list], F: float, T: float, target: float, cp: str) -> float | None:
    """IV at the OTM strike whose Black-76 delta is nearest target (0.25 call / -0.25 put)."""
    best = None
    for K, side, _settle, iv, _c, _p in rows:
        if iv is None or side != cp:
            continue
        d = black76_delta(F, K, T, iv, cp)
        gap = abs(d - (target if cp == "C" else -target))
        if best is None or gap < best[0]:
            best = (gap, iv)
    return None if best is None or best[0] > 0.10 else round(best[1], 5)


def _parity_F(lne_ladder: dict, T: float) -> tuple[float | None, int]:
    """LNE put-call parity F = K + (C-P)*e^{rT}; median over strikes with both settles."""
    ests = []
    for k_store, (_c_oi, _p_oi, c_set, p_set) in lne_ladder.items():
        if c_set is None or p_set is None:
            continue
        K = float(k_store) * LNE_STRIKE_SCALE
        ests.append(K + (c_set - p_set) * math.exp(RATE * T))
    if not ests:
        return None, 0
    ests.sort()
    return round(ests[len(ests) // 2], 4), len(ests)


def build() -> dict:
    p1 = _load_phase1()
    fut = _futures_settles()
    # live-era bridge: merged IN MEMORY; phase-i store file and winter sessions untouched
    bridge_sessions, bridge_opex = _decode_bridge()
    n_bridge = 0
    for sess, day in bridge_sessions.items():
        if sess in p1["sessions"]:
            continue                              # phase-i wins on any overlap (none expected)
        p1["sessions"][sess] = day
        n_bridge += 1
    for asset, months in bridge_opex.items():
        for month, ox in months.items():
            p1["opex"].setdefault(asset, {}).setdefault(month, ox)
    for iso, settles in _fut_settles_dbn().items():
        fut.setdefault(iso, {}).update(settles)
    scale_check = measure_lne_scale(p1)
    opex = p1["opex"]
    sessions_out: dict = {}
    n_iv = n_no_f = 0
    for iso in sorted(p1["sessions"]):
        day = datetime.date.fromisoformat(iso)
        fset = fut.get(iso, {})
        months_out: dict = {}
        for root in ("LNE", "ON"):
            for month, ladder in p1["sessions"][iso].get(root, {}).items():
                ox = opex.get(root, {}).get(month)
                if ox is None:
                    continue
                T_days = (datetime.date.fromisoformat(ox) - day).days
                if T_days <= 0:
                    continue
                T = T_days / 365.0
                m = months_out.setdefault(month, {"opex": ox, "days_to_opex": T_days})
                F = fset.get(month)
                if root == "LNE":
                    pF, n_pairs = _parity_F(ladder, T)
                    m["F_parity_lne"] = pF
                    m["n_parity_pairs"] = n_pairs
                    if F is None and pF is not None:
                        F = pF
                        m["F_source"] = "lne_parity"
                if F is None:
                    n_no_f += 1
                    continue
                m.setdefault("F", round(F, 4))
                m.setdefault("F_source", "futures_settle")
                rows = _month_ivs(root, ladder, F, T)
                n_iv += sum(1 for r in rows if r[3] is not None)
                key = "strikes_lne" if root == "LNE" else "strikes_on"
                m[key] = rows
        # features per month (LNE backbone), then front/next
        for month, m in months_out.items():
            rows = m.get("strikes_lne") or []
            live = [r for r in rows if r[3] is not None and r[1] in ("C", "P")]
            F = m.get("F")
            if F is None or len(live) < MIN_IVS_FOR_FEATURES:
                continue
            T = m["days_to_opex"] / 365.0
            atm = _interp_atm(rows, F)
            c25 = _delta_wing_iv(live, F, T, 0.25, "C")
            p25 = _delta_wing_iv(live, F, T, 0.25, "P")
            m["atm_iv"] = atm
            m["rr25"] = round(c25 - p25, 5) if c25 is not None and p25 is not None else None
            m["fly25"] = (round(0.5 * (c25 + p25) - atm, 5)
                          if None not in (c25, p25, atm) else None)
            m["n_iv_lne"] = len(live)
            m["oi_call_lne"] = sum(r[4] or 0 for r in rows)
            m["oi_put_lne"] = sum(r[5] or 0 for r in rows)
            if m.get("F_parity_lne") is not None and m.get("F_source") == "futures_settle":
                m["parity_minus_settle_F"] = round(m["F_parity_lne"] - F, 4)
            # ON-LNE matched gap in the ATM band (early-exercise premium, measured)
            on_rows = {(r[0], r[1]): r[3] for r in m.get("strikes_on", [])
                       if r[3] is not None and r[1] in ("C", "P")}
            gaps = [on_rows[(r[0], r[1])] - r[3] for r in live
                    if abs(r[0] - F) <= ATM_BAND_DOLLARS and (r[0], r[1]) in on_rows]
            gaps.sort()
            m["on_minus_lne_iv_atm_band"] = (round(gaps[len(gaps) // 2], 5) if gaps else None)
            m["n_on_lne_matched_atm"] = len(gaps)
        # front/next by opex among months WITH features
        feat = sorted((m["opex"], name) for name, m in months_out.items() if m.get("atm_iv") is not None)
        front = feat[0][1] if feat else None
        nxt = feat[1][1] if len(feat) > 1 else None
        ratio = None
        if front and nxt:
            ratio = round(months_out[front]["atm_iv"] / months_out[nxt]["atm_iv"], 4)
        sessions_out[iso] = {"months": months_out, "front": front, "next": nxt,
                             "front_next_atm_ratio": ratio}
    store = {
        "meta": {
            "built_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "phase1_range": p1["meta"]["range"], "n_bridge_sessions": n_bridge,
            "bridge_range": "2026-03-01..2026-07-19 (cost $0.00 in-sub)" if n_bridge else None,
            "n_sessions": len(sessions_out),
            "n_iv_points": n_iv, "n_month_sessions_no_F": n_no_f,
            "rate": RATE, "lne_strike_scale": LNE_STRIKE_SCALE,
            "lne_scale_check": scale_check,
            "wall": "CME next-morning publication; surface_asof serves latest session STRICTLY before iso",
            "caveat": ("settle marks exist for untraded strikes (settlement-algorithm opinion); "
                       "trust degrades away from ATM - OI columns carry the context. "
                       "iv on ON rows = iv_amer_naive (Black-76 applied to American settles)"),
        },
        "sessions": sessions_out,
    }
    os.makedirs(os.path.dirname(STORE_PATH), exist_ok=True)
    with gzip.open(STORE_PATH, "wt", encoding="utf-8") as f:
        json.dump(store, f)
    print(f"[options_iv] {len(sessions_out)} sessions, {n_iv} IVs, no-F month-sessions {n_no_f} "
          f"-> {os.path.relpath(STORE_PATH, _ROOT)}")
    print(f"[options_iv] LNE scale check: {json.dumps(scale_check)}")
    return store


_CACHE: dict | None = None


def load_store() -> dict | None:
    global _CACHE
    if _CACHE is None and os.path.exists(STORE_PATH):
        with gzip.open(STORE_PATH, "rt", encoding="utf-8") as f:
            _CACHE = json.load(f)
    return _CACHE


def surface_asof(iso: str) -> dict | None:
    """Latest session STRICTLY before iso; front/next feature view (blind-wall-safe).
    Strike ladders stay in the store; this is the decision-time read."""
    s = load_store()
    if not s:
        return None
    prior = [d for d in s["sessions"] if d < iso]
    if not prior:
        return None
    sess = max(prior)
    day = s["sessions"][sess]
    out = {"asof_session": sess, "front": day["front"], "next": day["next"],
           "front_next_atm_ratio": day["front_next_atm_ratio"]}
    for label in ("front", "next"):
        name = day[label]
        if name is None:
            continue
        m = day["months"][name]
        out[label + "_month"] = {k: m.get(k) for k in
                                 ("F", "F_source", "atm_iv", "rr25", "fly25", "days_to_opex",
                                  "n_iv_lne", "on_minus_lne_iv_atm_band", "oi_call_lne",
                                  "oi_put_lne", "parity_minus_settle_F")}
    out["note"] = ("feed I phase ii settle-IV features, LNE backbone (European, Black-76 exact); "
                   "rr25>0 = call wing over put wing; settle-marked, execution unmeasured")
    return out


def inventory() -> dict:
    """Roots present + coverage. HONEST LIMITATION: the phase-i raw pull was parent-scoped to
    ON/LNE - weekly-option roots (Mon-Fri expiries) were NOT captured; their in-window
    existence/OI stays OPEN until a defs-only pull (research D3/E5 item 6 gate)."""
    p1 = _load_phase1()
    roots: dict[str, dict] = {}
    for iso, day in p1["sessions"].items():
        for root, months in day.items():
            r = roots.setdefault(root, {"sessions": 0, "months": set(), "strike_rows": 0})
            r["sessions"] += 1
            r["months"] |= set(months)
            r["strike_rows"] += sum(len(l) for l in months.values())
    out = {root: {"sessions": v["sessions"], "n_months": len(v["months"]),
                  "strike_rows": v["strike_rows"]} for root, v in roots.items()}
    out["weeklies"] = "NOT CAPTURED by the phase-i parent pull (ON/LNE only) - open item, defs-only pull required"
    return out


# ------------------------------------------------------------------------------------------
def _selftest() -> int:
    ok = True

    def chk(c, m):
        nonlocal ok
        print(("  PASS " if c else "  FAIL ") + m)
        ok = ok and bool(c)

    print("[options_iv selftest]")
    # Black-76 round trip
    px = black76(3.50, 3.75, 30 / 365, 0.85, "C")
    iv = implied_vol(px, 3.50, 3.75, 30 / 365, "C")
    chk(iv is not None and abs(iv - 0.85) < 1e-4, f"Black-76 invert round-trip (sigma 0.85 -> {iv})")
    p_px = black76(3.50, 3.25, 30 / 365, 0.85, "P")
    p_iv = implied_vol(p_px, 3.50, 3.25, 30 / 365, "P")
    chk(p_iv is not None and abs(p_iv - 0.85) < 1e-4, "put side round-trip")
    chk(implied_vol(0.0001, 3.50, 3.75, 30 / 365, "C") is not None, "tiny OTM price inverts")
    chk(implied_vol(5.0, 3.50, 3.75, 30 / 365, "C") is None, "impossible price -> None (recorded, not repaired)")
    s = load_store()
    if s is None:
        print("  SKIP store checks (run --build first)")
        return 0 if ok else 1
    sc = s["meta"]["lne_scale_check"]
    d10, d1 = sc.get("10.0", {}), sc.get("1.0", {})
    chk(d10.get("n_matched", 0) > 1000 and (d1.get("median_abs_settle_diff") is None
        or d10["median_abs_settle_diff"] < (d1.get("median_abs_settle_diff") or 9e9)),
        f"LNE strike scale winner = 10 (matched {d10.get('n_matched')}, "
        f"med diff {d10.get('median_abs_settle_diff')})")
    a = surface_asof("2026-01-22")
    chk(a is not None and a["asof_session"] == "2026-01-21", "wall: asof 01-22 serves 01-21")
    day = s["sessions"].get("2026-01-22", {})
    h26 = day.get("months", {}).get("NGH26", {})
    chk(h26.get("F") is not None and 3.3 < h26["F"] < 3.9,
        f"NGH26 0122 F from futures settle = {h26.get('F')} (parity cross-check "
        f"{h26.get('parity_minus_settle_F')})")
    chk(h26.get("atm_iv") is not None and 0.3 < h26["atm_iv"] < 3.0,
        f"NGH26 0122 atm_iv = {h26.get('atm_iv')} (squeeze-week winter vol, sane band)")
    pd = h26.get("parity_minus_settle_F")
    chk(pd is not None and abs(pd) < 0.05, f"LNE parity F within 5c of futures settle ({pd})")
    n_feat = sum(1 for d in s["sessions"].values() for m in d["months"].values() if m.get("atm_iv"))
    chk(n_feat > 200, f"feature month-sessions: {n_feat}")
    print("[options_iv selftest]", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--show")
    ap.add_argument("--asof")
    ap.add_argument("--inventory", action="store_true")
    a = ap.parse_args()
    if a.build:
        build()
        return 0
    if a.selftest:
        return _selftest()
    if a.inventory:
        print(json.dumps(inventory(), indent=1, default=sorted))
        return 0
    if a.show:
        s = load_store()
        day = (s or {}).get("sessions", {}).get(a.show)
        if not day:
            print(f"no session {a.show}")
            return 1
        slim = {"front": day["front"], "next": day["next"],
                "front_next_atm_ratio": day["front_next_atm_ratio"],
                "months": {k: {kk: vv for kk, vv in v.items() if not kk.startswith("strikes")}
                           for k, v in day["months"].items()}}
        print(json.dumps(slim, indent=1))
        return 0
    if a.asof:
        print(json.dumps(surface_asof(a.asof), indent=1))
        return 0
    main.__doc__ = __doc__
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
