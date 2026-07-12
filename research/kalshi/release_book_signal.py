"""
release_book_signal.py — the S80 release-triggered BOOK signal (the MERGED architecture).

Greg's S79 result reorganized the whole plan: the news SURPRISE number cannot call direction
(proven null, release-hour hit 0.52 / sell-the-news). The BOOK can. So:

  * News release  = the CATALYST/gate (a move is coming; |surprise| = COARSE size only, a range,
                    NO precise surprise->move regression) + the PAUSE-through-the-spike trigger.
  * Book imbalance SIGN            = DIRECTION      (incl. sell-the-news, which the book shows and
                                                     the number can't).
  * Book imbalance MAGNITUDE + dipole EXHAUSTION = MAGNITUDE-class + will-it-HOLD-or-FADE.

This is the crypto FILTER+TIMING stack (`early_signal.book_imbalance` direction + `info_dipole`
exhaustion) FIRED BY a scheduled release instead of hunting turns blind.

DATA-SHAPE ADAPTATION (honest, load-bearing). The crypto `divergence()` consumes per-bar taker
BUY vs SELL volume. Kalshi public book snapshots carry NO signed trade tape — they carry the two
BOOK SIDES. The faithful mapping is: the information dipole's two coupled channels become the two
book sides (bid-side weighted depth vs ask-side weighted depth, from `early_signal.book_imbalance`).
Then:
  - imb_level (window depth imbalance)         -> DIRECTION
  - aligned_flow = imb_level * sign(prob drift)-> does the book CONFIRM or OPPOSE the prob move
  - exhausting (late-half |imb| < early-half)  -> the book-imbalance dipole COLLAPSING toward 0.5
                                                  = the leader weakening = the FADE / sell-the-news
                                                  catcher.
CAVEAT kept in view: resting depth is not taker aggression; support depth can mean "won't move"
rather than "buying". The S71 early-signal edge is nonetheless built on exactly this proximity-
weighted book imbalance predicting direction, and it is the placebo test below — not this
docstring — that adjudicates whether it calls direction on Kalshi contracts.

MANDATORY GATE: `--selftest` runs `odcore.leakage.assert_no_leakage` on the signal (the Architect's
S36b discipline — a signal does not touch a backtest until a value computed AT t is invariant to
all data AFTER t). The real per-contract EDGE test (`--test`) runs ONLY on accrued order-book bins
spanning a real release, is placebo-baselined, per-contract, and PROVISIONAL-until-live. There is
NO synthetic trading data here: the selftest fixtures are leakage tool-validation anchors only.

Usage:
    python research/kalshi/release_book_signal.py --selftest
    python research/kalshi/release_book_signal.py --series KXNATGASD --test \
        --data-dir data/kalshi --consensus data/kalshi/consensus.jsonl
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

import numpy as np

# --- repo wiring (script-style imports, matching book_swing_kraken.py) ---------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
sys.path.insert(0, os.path.join(_ROOT, "research", "shape_s71"))
sys.path.insert(0, _ROOT)

import early_signal as es                                 # noqa: E402  book_imbalance()
from odcore.info_dipole import divergence                 # noqa: E402  exhaustion/fade
from odcore.leakage import assert_no_leakage              # noqa: E402  mandatory gate


# ============================================================================================
# 1. DATA — load accrued bins, build per-contract book-feature arrays
# ============================================================================================
def load_series_rows(data_dir: str, series: str) -> list[dict]:
    """Read data/<series>_bins.jsonl(.gz) into a list of snapshot rows (one per market/cycle)."""
    base = os.path.join(data_dir, f"{series}_bins.jsonl")
    path = base if os.path.exists(base) else (base + ".gz" if os.path.exists(base + ".gz") else None)
    if path is None:
        return []
    opener = gzip.open if path.endswith(".gz") else open
    rows: list[dict] = []
    with opener(path, "rt") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


@dataclass
class ContractFrames:
    """Time-ordered book-feature arrays for ONE contract (ticker). All arrays are aligned."""
    ticker: str
    ts: np.ndarray          # epoch seconds
    prob: np.ndarray        # mid in cents == implied YES probability * 100  (the price series)
    bid_depth: np.ndarray   # proximity-weighted bid-side depth  (dipole channel A)
    ask_depth: np.ndarray   # proximity-weighted ask-side depth  (dipole channel B)
    imb: np.ndarray         # signed proximity-weighted book imbalance in [-1, +1]

    def __len__(self) -> int:
        return int(self.ts.size)


def build_contract_frames(rows: list[dict], ticker: str, k: int = es.DEFAULT_K) -> ContractFrames | None:
    """Filter rows to one ticker, keep two-sided books, compute book_imbalance per snapshot."""
    sel = [r for r in rows if r.get("ticker") == ticker and r.get("book_ok")
           and r.get("bids") and r.get("asks") and r.get("mid") is not None]
    sel.sort(key=lambda r: r.get("ts", 0.0))
    ts, prob, bd, ad, im = [], [], [], [], []
    last_ts = None
    for r in sel:
        t = float(r["ts"])
        if last_ts is not None and t == last_ts:      # collapse duplicate-ts snapshots
            continue
        last_ts = t
        bk = es.book_imbalance(r["bids"], r["asks"], k, r.get("mid"))
        if not bk["ok"]:
            continue
        ts.append(t); prob.append(float(r["mid"]))
        bd.append(bk["bid_depth"]); ad.append(bk["ask_depth"]); im.append(bk["imb"])
    if len(ts) < 8:
        return None
    return ContractFrames(ticker, np.asarray(ts), np.asarray(prob),
                          np.asarray(bd), np.asarray(ad), np.asarray(im))


def contract_tickers(rows: list[dict]) -> list[str]:
    seen: dict[str, int] = {}
    for r in rows:
        if r.get("book_ok") and r.get("ticker"):
            seen[r["ticker"]] = seen.get(r["ticker"], 0) + 1
    return [t for t, _ in sorted(seen.items(), key=lambda kv: -kv[1])]


# ============================================================================================
# 2. THE SIGNAL — read the book over a strictly pre-decision window
# ============================================================================================
@dataclass
class BookRead:
    ok: bool
    direction: int          # +1 YES-prob up / -1 down / 0 flat   <- book-imbalance SIGN
    conviction: float       # |imb_level| over the window (magnitude class)
    aligned_flow: float     # imb_level * sign(prob drift): >0 book confirms move, <0 opposes
    exhausting: bool        # book-imbalance dipole collapsing toward 0.5 -> FADE
    expect: str             # continue / weakening / flip_risk / reversal
    reversal_conviction: float
    scalar: float           # single signed scalar (for the leakage gate): direction * strength


def read_book(prob, bid_depth, ask_depth, lo: int, hi: int, direction_sign: int = +1) -> BookRead:
    """Read the book over indices [lo, hi] inclusive (hi = the DECISION snapshot; strictly no
    data after hi is used). direction from the depth-imbalance sign; fade from dipole exhaustion.

    The two dipole channels are the book sides; `divergence` computes the window depth-imbalance
    (imb_level) + whether it collapses early->late (exhausting). price_drift = prob[hi]-prob[lo]."""
    lo = max(0, lo)
    if hi - lo + 1 < 6:
        return BookRead(False, 0, 0.0, 0.0, False, "insufficient", 0.0, 0.0)
    bv = np.asarray(bid_depth[lo:hi + 1], float)
    sv = np.asarray(ask_depth[lo:hi + 1], float)
    drift = float(prob[hi] - prob[lo])
    d = divergence(bv, sv, price_drift=drift if drift != 0 else 1e-9)
    if d is None:
        return BookRead(False, 0, 0.0, 0.0, False, "insufficient", 0.0, 0.0)
    lvl = d["imb_level"]
    oriented = lvl * (1 if direction_sign >= 0 else -1)
    direction = +1 if oriented > 0 else (-1 if oriented < 0 else 0)
    conv = abs(lvl)
    # magnitude-class strength: lean magnitude, DISCOUNTED when the dipole is exhausting (fade)
    strength = conv * (0.5 if d["exhausting"] else 1.0)
    scalar = round(direction * strength * (1.0 + d["reversal_conviction"]), 9)
    return BookRead(True, direction, round(conv, 6), round(d["aligned_flow"], 6),
                    bool(d["exhausting"]), d["expect"], d["reversal_conviction"], scalar)


def signal_at(i: int, ts, p, bv, sv, window: int = 20, direction_sign: int = +1):
    """Signal 'as of index i' -> a signed scalar, using ONLY data in [i-window+1, i].

    This is the exact closure the leakage gate corrupts-after-i and requires unchanged. p=prob,
    bv=bid_depth, sv=ask_depth (the leakage harness's (p, bv, sv) triple)."""
    lo = i - window + 1
    r = read_book(p, bv, sv, lo, i, direction_sign)
    return r.scalar if r.ok else None


# ============================================================================================
# 3. CATALYST / GATE — the release calendar from the consensus store
# ============================================================================================
def _parse_ff_date(s: str) -> float | None:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except ValueError:
        return None


def release_times_for_series(consensus_path: str, series: str) -> list[dict]:
    """Release events (epoch ts + coarse |surprise| when actual+forecast both present) for a series."""
    if not os.path.exists(consensus_path):
        return []
    out: list[dict] = []
    for line in open(consensus_path):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if series not in (r.get("series") or []):
            continue
        rts = _parse_ff_date(r.get("date"))
        if rts is None:
            continue
        surprise = _coarse_surprise(r.get("actual"), r.get("forecast"))
        out.append({"ts": rts, "title": r.get("title"), "actual": r.get("actual"),
                    "forecast": r.get("forecast"), "surprise": surprise})
    out.sort(key=lambda x: x["ts"])
    return out


def _num_release(x) -> float | None:
    """ForexFactory values like '-1.9M', '60B', '3.1%' -> float (unit-scaled)."""
    if x is None:
        return None
    s = str(x).strip().replace(",", "").replace("%", "")
    mult = 1.0
    if s and s[-1] in "KMBT":
        mult = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}[s[-1]]
        s = s[:-1]
    try:
        return float(s) * mult
    except ValueError:
        return None


def _coarse_surprise(actual, forecast) -> dict | None:
    """COARSE size only — a bucketed magnitude/sign, NOT a precise regression input (per rule #2)."""
    a, f = _num_release(actual), _num_release(forecast)
    if a is None or f is None:
        return None
    diff = a - f
    scale = max(abs(f), 1e-9)
    ratio = abs(diff) / scale
    size = "big" if ratio >= 0.5 else ("moderate" if ratio >= 0.15 else "small")
    return {"sign": int(np.sign(diff)), "size": size, "abs_ratio": round(ratio, 3)}


# ============================================================================================
# 4. PER-CONTRACT PLACEBO TEST — runs on accrued release-spanning bins (provisional-until-live)
# ============================================================================================
def _decision_index(frames: ContractFrames, release_ts: float, spike_pause_s: float) -> int | None:
    """First snapshot at/after (release + spike-pause) — we PAUSE through the first-seconds spike
    and read the book on the decay."""
    target = release_ts + spike_pause_s
    idx = np.searchsorted(frames.ts, target, side="left")
    return int(idx) if idx < len(frames) else None


def _forward_move(prob: np.ndarray, ts: np.ndarray, i: int, horizon_s: float) -> float | None:
    """Realized prob change from decision i to the first snapshot >= horizon_s later."""
    j = np.searchsorted(ts, ts[i] + horizon_s, side="left")
    if j >= len(prob) or j <= i:
        return None
    return float(prob[j] - prob[i])


def evaluate_windows(frames: ContractFrames, decision_idxs: list[int], cfg: dict) -> list[dict]:
    """For each decision index: signal read (pre-decision window) vs realized forward move."""
    recs = []
    W, hs, ds = cfg["window"], cfg["horizon_s"], cfg["direction_sign"]
    for i in decision_idxs:
        r = read_book(frames.prob, frames.bid_depth, frames.ask_depth, i - W + 1, i, ds)
        if not r.ok:
            continue
        fwd = _forward_move(frames.prob, frames.ts, i, hs)
        if fwd is None:
            continue
        hit = int(np.sign(fwd) == r.direction and r.direction != 0)
        recs.append({"i": i, "direction": r.direction, "conviction": r.conviction,
                     "expect": r.expect, "exhausting": r.exhausting, "aligned": r.aligned_flow,
                     "fwd_move": round(fwd, 3), "hit": hit})
    return recs


def placebo_indices(frames: ContractFrames, armed_idxs: set[int], n: int, cfg: dict,
                    seed: int = 0) -> list[int]:
    """Random NON-release decision indices with enough room fore & aft (the placebo baseline)."""
    W, hs = cfg["window"], cfg["horizon_s"]
    rng = np.random.default_rng(seed)
    lo = W
    hi = len(frames) - 1
    pool = [i for i in range(lo, hi) if i not in armed_idxs
            and _forward_move(frames.prob, frames.ts, i, hs) is not None]
    if not pool:
        return []
    rng.shuffle(pool)
    return pool[:n]


def _hit_rate(recs: list[dict]) -> tuple[float, int]:
    if not recs:
        return float("nan"), 0
    return sum(r["hit"] for r in recs) / len(recs), len(recs)


def run_test(data_dir: str, series: str, consensus_path: str, cfg: dict,
             ticker: str | None = None) -> dict:
    rows = load_series_rows(data_dir, series)
    if not rows:
        return {"series": series, "status": "NO_BINS",
                "msg": f"no {series}_bins.jsonl(.gz) in {data_dir} yet (accrues via the 6h durable cron)"}
    releases = release_times_for_series(consensus_path, series)
    tickers = [ticker] if ticker else contract_tickers(rows)
    per_contract = []
    for tk in tickers:
        frames = build_contract_frames(rows, tk)
        if frames is None:
            continue
        span = (float(frames.ts[0]), float(frames.ts[-1]))
        armed = []
        for rel in releases:
            if span[0] <= rel["ts"] <= span[1] + cfg["horizon_s"]:
                di = _decision_index(frames, rel["ts"], cfg["spike_pause_s"])
                if di is not None:
                    armed.append((di, rel))
        armed_idxs = {di for di, _ in armed}
        event_recs = evaluate_windows(frames, [di for di, _ in armed], cfg)
        plac_idxs = placebo_indices(frames, armed_idxs, max(20, 5 * len(armed_idxs) or 20), cfg)
        plac_recs = evaluate_windows(frames, plac_idxs, cfg)
        ev_hr, ev_n = _hit_rate(event_recs)
        pl_hr, pl_n = _hit_rate(plac_recs)
        per_contract.append({
            "ticker": tk, "n_snaps": len(frames),
            "span_hours": round((span[1] - span[0]) / 3600.0, 2),
            "n_releases_in_span": len(armed),
            "event": {"hit_rate": None if math.isnan(ev_hr) else round(ev_hr, 3), "n": ev_n,
                      "recs": event_recs},
            "placebo": {"hit_rate": None if math.isnan(pl_hr) else round(pl_hr, 3), "n": pl_n},
            "edge_vs_placebo": (None if (math.isnan(ev_hr) or math.isnan(pl_hr))
                                else round(ev_hr - pl_hr, 3)),
        })
    n_armed_total = sum(c["n_releases_in_span"] for c in per_contract)
    return {"series": series, "status": "OK" if n_armed_total else "NO_RELEASE_IN_SPAN",
            "n_contracts": len(per_contract), "n_releases_in_span": n_armed_total,
            "note": ("PROVISIONAL — one window; never size off it. Awaiting release-spanning bins."
                     if n_armed_total == 0 else "PROVISIONAL — per-contract, placebo-baselined."),
            "contracts": per_contract}


# ============================================================================================
# 5. MANDATORY LEAKAGE GATE (--selftest) — tool-validation fixtures only (no synthetic trading data)
# ============================================================================================
def _leakage_fixture(n: int = 240, seed: int = 7):
    """A format-faithful (prob, bid_depth, ask_depth) triple for the leakage check ONLY. This is a
    tool-validation anchor (like the Brusselator) — it makes NO trading claim and is never scored."""
    rng = np.random.default_rng(seed)
    ts = np.arange(n, dtype=float) * 60.0
    prob = np.clip(50 + np.cumsum(rng.normal(0, 0.8, n)), 1, 99)
    bid = np.abs(rng.normal(300, 60, n)) + 40 * (prob > 50)
    ask = np.abs(rng.normal(300, 60, n)) + 40 * (prob <= 50)
    return ts, prob, bid, ask


def selftest() -> int:
    ts, p, bv, sv = _leakage_fixture()
    idxs = list(range(30, len(p) - 1, 7))
    passed, fails = assert_no_leakage(
        lambda i, ts_, p_, bv_, sv_: signal_at(i, ts_, p_, bv_, sv_, window=20),
        ts, p, bv, sv, idxs, reps=3, seed=0)
    print(f"[selftest] leakage gate: {'PASS' if passed else 'FAIL'} "
          f"({len(idxs)} indices, {len(fails)} leaks)")
    if not passed:
        for i, a, b in fails[:5]:
            print(f"    LEAK i={i}: clean={a} corrupt={b}")
        return 1
    # smoke: the signal produces a sane read on the fixture
    r = read_book(p, bv, sv, len(p) - 21, len(p) - 1)
    print(f"[selftest] sample read: dir={r.direction} conv={r.conviction} "
          f"expect={r.expect} exhausting={r.exhausting} scalar={r.scalar}")
    print("[selftest] OK — signal is leakage-free and ready to fire on release-spanning bins.")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="S80 release-triggered Kalshi book signal")
    ap.add_argument("--selftest", action="store_true", help="run the mandatory leakage gate + smoke")
    ap.add_argument("--test", action="store_true", help="per-contract placebo test on accrued bins")
    ap.add_argument("--data-dir", default="data/kalshi")
    ap.add_argument("--series", default="KXNATGASD")
    ap.add_argument("--ticker", default=None, help="single contract (default: all in the series)")
    ap.add_argument("--consensus", default="data/kalshi/consensus.jsonl")
    ap.add_argument("--window", type=int, default=20, help="pre-decision read window (snapshots)")
    ap.add_argument("--spike-pause-s", type=float, default=120.0, help="pause through the release spike")
    ap.add_argument("--horizon-s", type=float, default=1800.0, help="forward move horizon (s)")
    ap.add_argument("--direction-sign", type=int, default=1, help="+1 bid-heavy -> YES up (fit per cell)")
    ap.add_argument("--out", default=None, help="write the test JSON here")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(selftest())

    if args.test:
        cfg = {"window": args.window, "spike_pause_s": args.spike_pause_s,
               "horizon_s": args.horizon_s, "direction_sign": args.direction_sign}
        res = run_test(args.data_dir, args.series, args.consensus, cfg, args.ticker)
        txt = json.dumps(res, indent=2)
        if args.out:
            open(args.out, "w").write(txt)
            print(f"[test] wrote {args.out}")
        # compact console summary
        print(f"[test] {res['series']}: status={res['status']} "
              f"contracts={res.get('n_contracts', 0)} releases_in_span={res.get('n_releases_in_span', 0)}")
        for c in res.get("contracts", []):
            print(f"    {c['ticker']:<28} snaps={c['n_snaps']} span={c['span_hours']}h "
                  f"rel={c['n_releases_in_span']} event={c['event']['hit_rate']}(n={c['event']['n']}) "
                  f"placebo={c['placebo']['hit_rate']}(n={c['placebo']['n']}) edge={c['edge_vs_placebo']}")
        if res["status"] != "OK":
            print(f"    -> {res.get('msg') or res.get('note')}")
        return

    print("nothing to do — pass --selftest (leakage gate) or --test (per-contract placebo).")


if __name__ == "__main__":
    main()
