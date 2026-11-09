"""Re-analyse October 18 under the frozen NG exhaustion contract, with three clocks kept separate.

Frozen contract (canonical-sources/research/ng_exhaustion_chain_canonical_table_20260817.py and the
study contract of 2026-08-17): per-second classified aggressor lots (trade price versus the concurrent
top-of-book midpoint), roll20 = (buy - sell) / (buy + sell) over the trailing 20 s, event t0 = a local
maximum of |roll20| within +/-5 s (LOCAL_RADIUS) at or above the 85th percentile of |roll20| for the UTC
source day (PEAK_Q), prominence = |roll20(t0)| - median |roll20| over t0-30..t0-10, 45 s refractory
(REFRACTORY) resolved by prominence, polarity = sign roll20(t0). Dynamic endpoint = three consecutive
forward-filled oriented roll20 <= 0 (PERSIST): structural onset = first of the three, causal confirmation
= the third. Aftermath = last-trade price at confirmation + 5/10/20/30/60/120/300 s, oriented to polarity,
classed continuation / reversal / chop at +/-2 ticks (MATERIAL_TICKS). Seed state P/O/S/X from the first
zero of the oriented curve within +60 and the late flow pressure over t0+41..t0+61.

Clocks kept separate:
  information horizon   t0+5 (a spike is a local max only once t0+5 is seen) and t0+50 (the 45 s refractory
                        means a candidate is final only when no larger-prominence peak arrives within 45 s;
                        this is the archived Native adapter's available_second = t0+46..50)
  state-confirmation    the causal confirmation second of the endpoint (onset+2)
  exhaustion runway     structural onset - t0 (how long the oriented flow stayed positive)

Two thresholds are run: the frozen day-native 85th percentile (retrospective, uses the whole UTC day) and
a causal trailing 85th percentile (what the archived Native adapter did). Both event sets are compared with
the 863 archived recognitions. The dipole direction nowcast (300 s flow imbalance) and the resting-book
contrarian read are evaluated at t0 and at the information horizon against the price path over the
runway and after confirmation. Everything is October 18 only.
"""

import gzip
import json
import sys
from bisect import bisect_right, insort
from collections import Counter, defaultdict
from math import ceil, floor, isfinite
from pathlib import Path
from statistics import median

import databento as db

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from audit_october18_touch_mechanisms import Book, F_LAST, INSTRUMENT, OCTOBER18_UTC_OFFSET, TAPE, TAPE_FILE, git_blob  # noqa: E402
import data_locator  # noqa: E402

NS = 1_000_000_000
TICK = 1_000_000
import os

# Trading day = 21:00 UTC the prior calendar day to 21:00 UTC. DAY0 is the session index origin. Members are
# the Databento UTC-day files at the tape commit, with the cursor offset that aligns each member's record
# index to the standalone export's cursor (only known for October 18; 0 elsewhere). The tape commit holds
# only the October 2, 3, 17 and 18 UTC members, so the 22:00-24:00 UTC prefix of the prior calendar day is
# available for October 18 (from the 17 member) and October 3 (from the 2 member); for October 2 and 17 it comes
# from the 2023-10-01 and 2023-10-16 members pulled on 2026-11-08 (PREFIX_TAPE commit). Member tuple = (UTC day,
# cursor offset, commit or None for the original tape commit).
PREFIX_TAPE = "603c4defcb28fbf66cb6afc8d7728b1d7b1ed268"  # data commit carrying the 2023-10-01 and 2023-10-16 members pulled 2026-11-08
DAYS = {
    "20231018": dict(day0=1697576400, members=(("20231017", -841601, None), ("20231018", 17375, None)), archived="october18-candidate-inputs.jsonl.gz", tag="oct18"),
    "20231017": dict(archived_locator=f"tasks/family-research-20261022/replay-comparison/20231017/candidate-inputs.jsonl.gz", day0=1697490000, members=(("20231016", 0, PREFIX_TAPE), ("20231017", 0, None)), archived=None, tag="oct17"),
    "20231003": dict(archived_locator=f"tasks/family-research-20261022/replay-comparison/20231003/candidate-inputs.jsonl.gz", day0=1696280400, members=(("20231002", 0, None), ("20231003", 0, None)), archived=None, tag="oct03"),
    "20231002": dict(archived_locator=f"tasks/family-research-20261022/replay-comparison/20231002/candidate-inputs.jsonl.gz", day0=1696194000, members=(("20231001", 0, PREFIX_TAPE), ("20231002", 0, None)), archived=None, tag="oct02"),
}
NG_DAY = os.environ.get("NG_DAY", "20231018")
CFG = DAYS[NG_DAY]
DAY0 = CFG["day0"]
TAG = CFG["tag"]
ROLL, PEAK_Q, LOCAL_RADIUS, REFRACTORY, PERSIST, MATERIAL_TICKS = 20, 0.85, 5, 45, 3, 2.0
PRE = POST = 60
HORIZONS = (5, 10, 20, 30, 60, 120, 300)
NAN = float("nan")


def fin(x):
    return x is not None and isfinite(x)


def quantile(vals, q):
    a = sorted(v for v in vals if fin(v))
    if not a:
        return NAN
    z = q * (len(a) - 1)
    i, j = floor(z), min(floor(z) + 1, len(a) - 1)
    return a[i] * (1 - (z - i)) + a[j] * (z - i)


def replay():
    """Per-second buy/sell lots, last trade price, mean and last 10-level book imbalance, last midpoint."""
    n = 86400
    buy, sell = [0.0] * n, [0.0] * n
    last_px = [NAN] * n
    bsum, bn, blast = [0.0] * n, [0] * n, [NAN] * n
    mid_last = [NAN] * n
    spread_last, bdepth_last, adepth_last, btouch_last, atouch_last = [NAN] * n, [NAN] * n, [NAN] * n, [NAN] * n, [NAN] * n
    book = Book()
    pending = Counter()
    counts = Counter()
    members = tuple((TAPE_FILE.replace("20231018", d), off, commit or TAPE) for d, off, commit in CFG["members"])
    def records():
        for path, offset, commit in members:
            for index, record in enumerate(db.DBNStore.from_bytes(data_locator.read_bytes(path))):  # sha256-verified, pinned in data-manifest.json
                yield index + offset, record
    for cursor, record in records():
        if record.instrument_id != INSTRUMENT:
            raise ValueError(cursor)
        sec = record.ts_recv // NS - DAY0
        action = str(record.action)
        if action == "T" and 0 <= sec < n:
            bids = [p for (s, p), o in book.levels.items() if s == "B" and o]
            asks = [p for (s, p), o in book.levels.items() if s == "A" and o]
            counts["prints"] += 1
            if bids and asks and record.size > 0 and record.price > 0:
                mid = 0.5 * (max(bids) + min(asks))
                if record.price > mid:
                    buy[sec] += record.size; counts["buy"] += 1
                elif record.price < mid:
                    sell[sec] += record.size; counts["sell"] += 1
                else:
                    counts["at_mid"] += 1
                last_px[sec] = record.price
            else:
                counts["unclassifiable"] += 1
        book.apply(record, cursor, pending, None)
        if int(record.flags) & F_LAST:
            pending.clear()
            if 0 <= sec < n:
                bids = sorted((p for (s, p), o in book.levels.items() if s == "B" and o), reverse=True)[:10]
                asks = sorted(p for (s, p), o in book.levels.items() if s == "A" and o)[:10]
                bs = sum(sum(book.levels[("B", p)].values()) for p in bids)
                as_ = sum(sum(book.levels[("A", p)].values()) for p in asks)
                if bs + as_ > 0:
                    imb = (bs - as_) / (bs + as_)
                    bsum[sec] += imb; bn[sec] += 1; blast[sec] = imb
                if bids and asks:
                    mid_last[sec] = 0.5 * (bids[0] + asks[0])
                    spread_last[sec] = (asks[0] - bids[0]) / TICK
                    bdepth_last[sec], adepth_last[sec] = bs, as_
                    btouch_last[sec] = sum(book.levels[("B", bids[0])].values())
                    atouch_last[sec] = sum(book.levels[("A", asks[0])].values())
    # forward fills
    price, bookimb, mid = [NAN] * n, [NAN] * n, [NAN] * n
    lp = li = lm = NAN
    first_trade = last_trade = None
    for i in range(n):
        if fin(last_px[i]):
            lp = last_px[i]
            first_trade = i if first_trade is None else first_trade
            last_trade = i
        price[i] = lp
        if fin(blast[i]):
            li = blast[i]
        bookimb[i] = (bsum[i] / bn[i]) if bn[i] else li
        if fin(mid_last[i]):
            lm = mid_last[i]
        mid[i] = lm
    extra = {}
    for name, raw in (("spread", spread_last), ("bid_depth", bdepth_last), ("ask_depth", adepth_last), ("bid_touch", btouch_last), ("ask_touch", atouch_last)):
        ff, lv = [NAN] * n, NAN
        for i in range(n):
            if fin(raw[i]):
                lv = raw[i]
            ff[i] = lv
        extra[name] = ff
    cb, cs = [0.0] * (n + 1), [0.0] * (n + 1)
    for i in range(n):
        cb[i + 1] = cb[i] + buy[i]; cs[i + 1] = cs[i] + sell[i]
    roll = [NAN] * n
    for i in range(n):
        lo = max(0, i - ROLL + 1)
        b, s = cb[i + 1] - cb[lo], cs[i + 1] - cs[lo]
        if b + s > 0:
            roll[i] = (b - s) / (b + s)
    return dict(buy=buy, sell=sell, price=price, book=bookimb, mid=mid, roll=roll, cb=cb, cs=cs,
                first_trade=first_trade, last_trade=last_trade, counts=counts, **extra)


CACHE_DIR = Path(os.environ.get("NG_REPLAY_CACHE_DIR", "/tmp/claude-0/-home-user-Markets/e6cffa19-4561-5119-b5f4-3474c12f9fe5/scratchpad"))


def replay_cached():
    """replay() with a per-day pickle cache in the scratchpad (never committed); v2 carries spread and depth."""
    import pickle
    cache = CACHE_DIR / f"{TAG}-replay-cache-v2.pkl"
    if cache.exists():
        return pickle.load(open(cache, "rb"))
    s = replay()
    cache.parent.mkdir(parents=True, exist_ok=True)
    pickle.dump(s, open(cache, "wb"))
    return s


def detect(stream, mode):
    """Frozen detector. mode='day' = day-native 85th pct (retrospective); mode='trailing' = causal trailing 85th pct
    judged when t+5 is observed (the archived Native adapter)."""
    flow = stream["roll"]
    lo = max(stream["first_trade"] + PRE, LOCAL_RADIUS, 30)
    hi = min(stream["last_trade"] - POST, len(flow) - LOCAL_RADIUS - 1)
    cand = []
    if mode == "day":
        thr_day = quantile([abs(v) for v in flow if fin(v)], PEAK_Q)
    ordered = []
    for t in range(0, hi + 1):
        if mode == "trailing":
            # bar as of observing t + LOCAL_RADIUS: all finite |roll| up to t+5 are in the trailing set
            pass
        if t < lo:
            continue
    # build trailing bars once: ordered insert of |roll| as seconds complete
    bars = {}
    if mode == "trailing":
        ordered = []
        for s in range(0, hi + LOCAL_RADIUS + 1):
            v = flow[s]
            if fin(v):
                insort(ordered, abs(v))
            t = s - LOCAL_RADIUS
            if t >= lo and ordered:
                z = PEAK_Q * (len(ordered) - 1)
                i, j = floor(z), ceil(z)
                bars[t] = ordered[i] if i == j else ordered[i] * (j - z) + ordered[j] * (z - i)
    for t in range(lo, hi + 1):
        v = flow[t]
        if not fin(v):
            continue
        thr = thr_day if mode == "day" else bars.get(t, NAN)
        if not fin(thr) or abs(v) < thr:
            continue
        local = [abs(flow[j]) for j in range(t - LOCAL_RADIUS, t + LOCAL_RADIUS + 1) if fin(flow[j])]
        if not local or abs(v) < max(local) - 1e-12:
            continue
        base = median([abs(flow[j]) for j in range(t - 30, t - 9) if fin(flow[j])] or [0.0])
        cand.append((t, abs(v), abs(v) - base))
    cand.sort(key=lambda z: (z[2], z[1]), reverse=True)
    picked = []
    for row in cand:
        if any(abs(row[0] - p[0]) < REFRACTORY for p in picked):
            continue
        picked.append(row)
    picked.sort()
    return picked, len(cand), (thr_day if mode == "day" else None)


def fill_curve(arc):
    out, last = [], NAN
    for v in arc:
        if fin(v):
            last = v
        out.append(last)
    return None if not fin(out[0]) else out


def first_zero(post):
    for i, v in enumerate(post):
        if v <= 0:
            return i
    return None


def first_persist_below(post, peak, frac):
    lim = frac * peak
    for i in range(len(post) - PERSIST + 1):
        if all(post[i + k] < lim for k in range(PERSIST)):
            return i
    return None


def endpoint(flow, t0, pol, last_trade):
    last, run = None, 0
    for i in range(t0 + 1, last_trade + 1):
        if fin(flow[i]):
            last = flow[i]
        if last is None:
            continue
        run = run + 1 if pol * last <= 0 else 0
        if run >= PERSIST:
            return i - (PERSIST - 1), i
    return None, None


def window_imb(cb, cs, t, width):
    lo = max(0, t - width + 1)
    b, s = cb[t + 1] - cb[lo], cs[t + 1] - cs[lo]
    return (b - s) / (b + s) if b + s > 0 else None, b + s


def sgn(x):
    return (x > 0) - (x < 0)


def aftermath(price, end, pol, last_trade):
    if end is None or not fin(price[end]):
        return None
    p0 = price[end]
    out = {}
    for h in HORIZONS:
        if end + h > last_trade:
            out[h] = dict(censored=True); continue
        path = [pol * (price[i] - p0) / TICK for i in range(end, end + h + 1) if fin(price[i])]
        signed = pol * (price[end + h] - p0) / TICK
        out[h] = dict(censored=False, signed_ticks=signed, mfe=max(path), mae=min(path),
                      cls="continuation" if signed >= MATERIAL_TICKS else "reversal" if signed <= -MATERIAL_TICKS else "chop")
    return out


def main():
    stream = replay_cached()
    flow, price, mid, bookimb, cb, cs = stream["roll"], stream["price"], stream["mid"], stream["book"], stream["cb"], stream["cs"]
    SESSION_CLOSE = 86400  # 21:00 UTC on the trading day; prints after this belong to the next trading day
    stream["last_trade"] = min(stream["last_trade"], SESSION_CLOSE - 1)
    last_trade = stream["last_trade"]
    archived_path = (HERE.parent / CFG["archived"]) if CFG.get("archived") else (data_locator.local_path(CFG["archived_locator"]) if CFG.get("archived_locator") else None)
    archived = [json.loads(l) for l in gzip.open(archived_path, "rt")] if archived_path else []
    archived = [c for c in archived if c.get("recognition_receive_ns") is not None]  # finalization-only rows carry no live recognition
    arch_by_birth = {c["birth_second"] - DAY0: c for c in archived}
    results = {}
    for mode in ("day", "trailing"):
        picked, n_cand, thr_day = detect(stream, mode)
        rows = []
        for t0, mag, prom in picked:
            pol = sgn(flow[t0])
            if not pol:
                continue
            raw_arc = [pol * flow[t0 + d] if fin(flow[t0 + d]) else NAN for d in range(-PRE, POST + 1)]
            arc = fill_curve(raw_arc)
            pre_arc_defined = arc is not None
            if arc is None:
                arc = fill_curve([0.0] + raw_arc[1:])
            pre, post = arc[:PRE + 1], arc[PRE:]
            peak = pre[-1]
            if peak <= 0:
                continue
            zero_s = first_zero(post)
            late_imb, late_vol = window_imb(cb, cs, t0 + 60, 20)  # t0+41..t0+60
            late_pressure = None if late_imb is None else pol * late_imb
            if zero_s is None:
                seed = "P"
            elif late_pressure is None or abs(late_pressure) < 1e-12:
                seed = "X"
            else:
                seed = "S" if late_pressure > 0 else "O"
            onset, confirm = endpoint(flow, t0, pol, last_trade)
            info5, info50 = t0 + LOCAL_RADIUS, t0 + LOCAL_RADIUS + REFRACTORY
            dip_t0, vol_t0 = window_imb(cb, cs, t0, 300)
            dip_i50, vol_i50 = window_imb(cb, cs, info50, 300)
            t0_book = [bookimb[i] for i in range(t0 - 19, t0 + 1) if fin(bookimb[i])]
            book_t0 = (sum(t0_book) / len(t0_book)) if t0_book else None
            def move(a, b, series=price):
                return None if (a is None or b is None or b > last_trade or not fin(series[a]) or not fin(series[b])) else pol * (series[b] - series[a]) / TICK
            arch = arch_by_birth.get(t0)
            arch_rec = None
            if arch:
                arch_rec = arch["recognition_receive_ns"] // NS - DAY0
            seed_known = t0 + 61
            def smove(h):
                return move(seed_known, seed_known + h if seed_known + h <= last_trade else None)
            row = dict(
                pre_arc_defined=pre_arc_defined, seed_known_s=seed_known,
                move_seed_known_plus30=smove(30), move_seed_known_plus60=smove(60), move_seed_known_plus300=smove(300),
                confirmed_before_seed_known=None if confirm is None else confirm <= seed_known,
                t0=t0, t0_utc=f"{((t0 + 75600) % 86400) // 3600:02d}:{(t0 + 75600) % 3600 // 60:02d}:{(t0 + 75600) % 60:02d}", polarity=pol,
                peak_abs=mag, prominence=prom, seed_state=seed, zero_within_60=zero_s,
                t50=first_persist_below(post, peak, .5), t25=first_persist_below(post, peak, .25), t10=first_persist_below(post, peak, .1),
                late_pressure_41_60=late_pressure, late_volume=late_vol,
                onset=onset, confirm=confirm, runway_s=None if onset is None else onset - t0,
                confirm_offset_s=None if confirm is None else confirm - t0, censored=confirm is None,
                info_horizon_local_s=LOCAL_RADIUS, info_horizon_refractory_s=LOCAL_RADIUS + REFRACTORY,
                confirmed_before_info50=None if confirm is None else confirm <= info50,
                remaining_runway_at_info50_s=None if confirm is None else confirm - info50,
                archived_recognition_s=arch_rec, archived_recognition_offset_s=None if arch_rec is None else arch_rec - t0,
                archived_flow_state=arch["birth_to_emission_flow_state"] if arch else None,
                dip300_t0=dip_t0, dip300_vol_t0=vol_t0, dip300_info50=dip_i50, dip300_vol_info50=vol_i50,
                book_t0_aligned=None if book_t0 is None else pol * book_t0,
                move_t0_to_confirm=move(t0, confirm), move_t0_to_info50=move(t0, info50 if info50 <= last_trade else None),
                move_info50_plus30=move(info50, info50 + 30 if info50 + 30 <= last_trade else None),
                move_info50_plus60=move(info50, info50 + 60 if info50 + 60 <= last_trade else None),
                move_confirm5_to_30=move(None if confirm is None else confirm + 5, None if confirm is None else confirm + 30),
                mid_move_t0_to_confirm=move(t0, confirm, mid), mid_move_info50_plus30=move(info50, info50 + 30 if info50 + 30 <= last_trade else None, mid),
                aftermath=aftermath(price, confirm, pol, last_trade),
            )
            rows.append(row)
        # sequence annotations
        rows.sort(key=lambda r: r["t0"])
        for i, r in enumerate(rows):
            r["prev_gap_s"] = None if i == 0 else r["t0"] - rows[i - 1]["t0"]
            r["same_as_prev"] = None if i == 0 else r["polarity"] == rows[i - 1]["polarity"]
            r["next_starts_before_confirm"] = None if i + 1 == len(rows) or r["confirm"] is None else rows[i + 1]["t0"] < r["confirm"]
            r["prev4_states"] = "".join(x["seed_state"] for x in rows[max(0, i - 4):i]) if i >= 4 else None
            r["prev3_states"] = "".join(x["seed_state"] for x in rows[max(0, i - 3):i]) if i >= 3 else None
        results[mode] = dict(rows=rows, candidates=n_cand, day_threshold=thr_day)

    def summarise(rows, label):
        n = len(rows)
        s = dict(label=label, events=n, polarity=Counter(r["polarity"] for r in rows), seed_states=Counter(r["seed_state"] for r in rows),
                 censored=sum(1 for r in rows if r["censored"]))
        rw = [r["runway_s"] for r in rows if r["runway_s"] is not None]
        co = [r["confirm_offset_s"] for r in rows if r["confirm_offset_s"] is not None]
        s["runway_s"] = dict(n=len(rw), min=min(rw), q25=quantile(rw, .25), median=median(rw), q75=quantile(rw, .75), max=max(rw)) if rw else None
        s["confirm_offset_s"] = dict(n=len(co), min=min(co), q25=quantile(co, .25), median=median(co), q75=quantile(co, .75), max=max(co)) if co else None
        s["confirmed_before_info50"] = sum(1 for r in rows if r["confirmed_before_info50"])
        s["confirmed_before_info5"] = sum(1 for r in rows if r["confirm_offset_s"] is not None and r["confirm_offset_s"] <= LOCAL_RADIUS)
        rem = [r["remaining_runway_at_info50_s"] for r in rows if r["remaining_runway_at_info50_s"] is not None]
        s["remaining_runway_at_info50_s"] = dict(negative=sum(1 for v in rem if v < 0), zero_to_20=sum(1 for v in rem if 0 <= v <= 20), over_20=sum(1 for v in rem if v > 20), median=median(rem)) if rem else None
        ar = [r["archived_recognition_offset_s"] for r in rows if r["archived_recognition_offset_s"] is not None]
        s["archived_recognition_offset_s"] = dict(n=len(ar), min=min(ar), median=median(ar), max=max(ar)) if ar else None
        s["archived_recognition_after_confirm"] = sum(1 for r in rows if r["archived_recognition_offset_s"] is not None and r["confirm_offset_s"] is not None and r["archived_recognition_offset_s"] > r["confirm_offset_s"])
        s["matched_archived_births"] = sum(1 for r in rows if r["archived_recognition_s"] is not None)
        # price over the runway and after confirmation
        def tri(vals):
            v = [x for x in vals if x is not None]
            return dict(n=len(v), with_pol=sum(1 for x in v if x > 0), flat=sum(1 for x in v if x == 0), against=sum(1 for x in v if x < 0), median=median(v) if v else None)
        s["price_t0_to_confirm"] = tri([r["move_t0_to_confirm"] for r in rows])
        s["mid_t0_to_confirm"] = tri([r["mid_move_t0_to_confirm"] for r in rows])
        s["price_t0_to_info50"] = tri([r["move_t0_to_info50"] for r in rows])
        s["price_info50_plus30"] = tri([r["move_info50_plus30"] for r in rows])
        s["mid_info50_plus30"] = tri([r["mid_move_info50_plus30"] for r in rows])
        s["price_info50_plus60"] = tri([r["move_info50_plus60"] for r in rows])
        s["price_confirm5_to_30"] = tri([r["move_confirm5_to_30"] for r in rows])
        s["aftermath"] = {}
        for h in HORIZONS:
            c = Counter()
            for r in rows:
                a = r["aftermath"]
                if a is None:
                    c["no_price"] += 1; continue
                c["censored" if a[h]["censored"] else a[h].get("cls") or "no_price"] += 1
            s["aftermath"][h] = dict(c)
        s["pre_arc_defined"] = sum(1 for r in rows if r["pre_arc_defined"])
        s["confirmed_before_seed_known"] = sum(1 for r in rows if r["confirmed_before_seed_known"])
        s["runway_by_seed"] = {st: (lambda v: dict(n=len(v), median=median(v) if v else None, q75=quantile(v, .75) if v else None))([r["runway_s"] for r in rows if r["seed_state"] == st and r["runway_s"] is not None]) for st in "POSX"}
        s["price_from_seed_known_by_seed"] = {st: {h: tri([r[f"move_seed_known_plus{h}"] for r in rows if r["seed_state"] == st]) for h in (30, 60, 300)} for st in "POSX"}
        s["price_from_seed_known_by_seed_and_prearc"] = {f"{st}/{'defined' if d else 'undefined'}": {h: tri([r[f"move_seed_known_plus{h}"] for r in rows if r["seed_state"] == st and r["pre_arc_defined"] == d]) for h in (60, 300)} for st in "POSX" for d in (True, False)}
        s["aftermath_by_seed_30s"] = {st: Counter(r["aftermath"][30]["cls"] for r in rows if r["seed_state"] == st and r["aftermath"] and r["aftermath"][30].get("cls")) for st in "POSX"}
        s["aftermath_by_seed_60s"] = {st: Counter(r["aftermath"][60]["cls"] for r in rows if r["seed_state"] == st and r["aftermath"] and r["aftermath"][60].get("cls")) for st in "POSX"}
        # dipole direction nowcast: does sign(dip300) at t0 / at info50 agree with the price path
        def agree(key, movekey, strong=None):
            c = Counter()
            for r in rows:
                d, m = r[key], r[movekey]
                if d is None or m is None:
                    c["undefined"] += 1; continue
                if strong is not None and abs(d) < strong:
                    c["weak"] += 1; continue
                c["agree" if sgn(d) == sgn(m) and m != 0 else "flat" if m == 0 else "disagree"] += 1
            return dict(c)
        s["dip300_t0_vs_t0_to_confirm"] = agree("dip300_t0", "move_t0_to_confirm")
        s["dip300_t0_strong_vs_t0_to_confirm"] = agree("dip300_t0", "move_t0_to_confirm", 0.15)
        s["dip300_info50_vs_info50_plus30"] = agree("dip300_info50", "move_info50_plus30")
        s["dip300_info50_strong_vs_info50_plus30"] = agree("dip300_info50", "move_info50_plus30", 0.15)
        s["dip300_info50_strong_vs_info50_plus60"] = agree("dip300_info50", "move_info50_plus60", 0.15)
        s["dip300_t0_sign_vs_polarity"] = Counter("same" if r["dip300_t0"] is not None and sgn(r["dip300_t0"]) == r["polarity"] else "opposite" if r["dip300_t0"] is not None and sgn(r["dip300_t0"]) == -r["polarity"] else "zero_or_undefined" for r in rows)
        # book contrarian: heavy resting side at t0 (aligned with polarity = bid-heavy for a buy burst)
        def by_book(movekey):
            out = {}
            for lab, test in (("book_aligned", lambda b: b > 0.05), ("book_opposed", lambda b: b < -0.05), ("book_flat", lambda b: -0.05 <= b <= 0.05)):
                out[lab] = tri([r[movekey] for r in rows if r["book_t0_aligned"] is not None and test(r["book_t0_aligned"])])
            return out
        s["book_at_t0_vs_t0_to_confirm"] = by_book("move_t0_to_confirm")
        s["book_at_t0_vs_info50_plus30"] = by_book("move_info50_plus30")
        # sequence motifs
        s["prev_gap_s"] = dict(median=median([r["prev_gap_s"] for r in rows if r["prev_gap_s"] is not None]), under_60=sum(1 for r in rows if r["prev_gap_s"] is not None and r["prev_gap_s"] < 60))
        s["next_starts_before_confirm"] = sum(1 for r in rows if r["next_starts_before_confirm"])
        s["same_as_prev"] = Counter(r["same_as_prev"] for r in rows)
        s["ssos_motif"] = tri([r["move_confirm5_to_30"] for r in rows if r["prev4_states"] == "SSOS"])
        s["pox_motif"] = tri([r["move_confirm5_to_30"] for r in rows if r["prev3_states"] == "POX"])
        s["pox_opposite_current"] = tri([r["move_confirm5_to_30"] for r in rows if r["prev3_states"] == "POX" and r["same_as_prev"] is False])
        s["seed_transitions"] = Counter(f"{rows[i-1]['seed_state']}->{rows[i]['seed_state']}" for i in range(1, len(rows)))
        return s

    summary = dict(
        tape_counts=dict(stream["counts"]), first_trade_s=stream["first_trade"], last_trade_s=last_trade,
        day_threshold_85pct=results["day"]["day_threshold"], archived_recognitions=len(archived),
        archived_birth_seconds_matching_day_events=sum(1 for r in results["day"]["rows"] if r["archived_recognition_s"] is not None),
        archived_birth_seconds_matching_trailing_events=sum(1 for r in results["trailing"]["rows"] if r["archived_recognition_s"] is not None),
        constants=dict(ROLL=ROLL, PEAK_Q=PEAK_Q, LOCAL_RADIUS=LOCAL_RADIUS, REFRACTORY=REFRACTORY, PERSIST=PERSIST, MATERIAL_TICKS=MATERIAL_TICKS),
        day_native=summarise(results["day"]["rows"], "frozen day-native 85th percentile (retrospective)"),
        trailing=summarise(results["trailing"]["rows"], "causal trailing 85th percentile (archived adapter)"),
    )
    (HERE / f"exhaustion-clock-{TAG}-summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")
    with gzip.open(HERE / f"exhaustion-clock-{TAG}-events.jsonl.gz", "wt") as f:
        for mode in ("day", "trailing"):
            for r in results[mode]["rows"]:
                f.write(json.dumps(dict(mode=mode, **r), default=str) + "\n")
    print(json.dumps(summary, indent=1, default=str))


if __name__ == "__main__":
    main()
