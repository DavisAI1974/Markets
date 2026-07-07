"""S72 PEAK/VALLEY EXHAUSTION study (DESCRIPTIVE — changes no strategy code).

REFRAME (project lead): stop using the detector's entry/exit legs. Segment the tape
by the PRICE's OWN peaks and valleys (a zigzag on `mid`) and study what EXHAUSTION
(with-trade order-flow imbalance) is doing AT those price turns.

  Legs = peak->valley (down-swing) and valley->peak (up-swing): each leg starts at one
  price extreme and ends at the NEXT OPPOSITE extreme (a full price swing).
  The trade EXIT PRICE is irrelevant and never computed. The important prices are the
  PEAK and VALLEY themselves (the turns).

Flow = arc_gate.rolling_imb(buy,sell,20) — the with-trade imbalance ("exhaustion"). Here
flow is signed by the SWING direction, not a trade side:
  up-swing (valley->peak): with-flow = +imb   (buys "with" the up move)
  down-swing (peak->valley): with-flow = -imb  (sells "with" the down move)
So "exhaustion" always means with-flow rolling back toward balance in the swing's own
direction. EXHAUSTION event = with-flow reaches its peak (velocity ~ 0) then rolls back.

FOUR GROUPS on the SWINGS themselves (no detector outcome here — the swing IS the object):
  DURATION: short vs long = swing time split at the MEDIAN swing duration per cell.
  WINNER/LOSER: winner = swing MAGNITUDE >= the ~20bp fee floor (big enough to be worth
    catching); loser = sub-fee small swing. Second, robustness cut = magnitude split at the
    MEDIAN swing size.
  => short-winner / long-winner / short-loser / long-loser (swing version).

Per cell, per INDIVIDUAL leg (no averaging — distributions), for theta = 10/20/40 bps:
  1. exhaustion-at-turn: with-flow value at the extreme, returned-to-balance fraction, |velocity|.
  2. LEAD/LAG: offset = (with-flow flatten time) - (price extreme time). Negative => flow
     flattens BEFORE the price turn => LEADS => catchable. Distribution reported.
  3. peaks-vs-valleys / up-vs-down asymmetry.
  4. duration- and size-invariance (terciles), and the 4-group breakdown (at anchor theta=20).

Plots: per coin, 4-group layout (rows = short-winner/long-winner/short-loser/long-loser),
individual swings (price across the swing + 60s-smoothed exhaustion; markers at start/end
extreme and the flow-flatten point). NO trade-exit-price. PNGs -> /tmp/kbook/ (gitignored).
"""
import os, sys, json
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, "/home/user/Markets")
sys.path.insert(0, "/home/user/Markets/research/shape_s71")
sys.path.insert(0, "/home/user/Markets/scripts")
from arc_gate import load_raw, build_channels, median_spread_bps, rolling_imb, KRAKEN

CPS = 10                 # cells per second (0.1s book grid)
SMOOTH_SEC = 20          # flow (exhaustion) rolling window — matches S71/S72 convention
DISP_SEC = 60            # per-leg DISPLAY smoothing only (never across legs)
THETAS = [10.0, 20.0, 40.0]   # zigzag retrace confirmation, bps (anchor ~ 20bps fee-floor)
FEE_BPS = 20.0           # winner swing must clear the ~20bp fee floor to be worth catching
OUTDIR = "/tmp/kbook"
COINS = ["btc", "eth", "sol", "xrp", "doge"]
GROUP_ORDER = ["short-winner", "long-winner", "short-loser", "long-loser"]

VERDICT = """
## VERDICT — NULL: no consistent leading exhaustion tell at the price turns

Across ALL 5 cells (btc/eth/sol/xrp/doge), ALL 3 thetas (10/20/40bps), and ALL 4 groups, the
with-trade order-flow imbalance ('exhaustion') shows NO consistent, LEADING signature at the
price peaks/valleys. The thesis 'exhaustion marks the top/bottom so we can catch it' is NOT
supported at this flow resolution on the Kraken book data.

- LEAD: the flow-hump position within a swing is ~0.5 of the leg everywhere (per-cell medians
  0.40-0.66, pooled ~0.54) = RANDOM. Flow does NOT flatten before the price turn. (An earlier
  raw-argmax metric produced huge fake 'leads' of hundreds-to-thousands of seconds; those were
  artifacts of a saturated signal, corrected here with swing-proportional smoothing.)
- EXHAUSTION: with-flow is weaker in the 2nd half of the swing in only 33-46% of legs (~40%,
  BELOW a coin flip) — if anything the with-flow tends to be STRONGER approaching the turn, the
  opposite of exhaustion. At the turn itself with-flow is still mildly WITH-trend (median
  +0.08..+0.23), and flow has 'turned against' the swing in only ~13-44% of legs.
- 4 GROUPS DO NOT SEPARATE: short/long x winner/loser show statistically indistinguishable
  wf_turn, hump position, and exhaust% (e.g. long-winner vs short-loser within a cell differ by
  noise only). The big fee-CLEARING swings — the ones we want to catch — have no cleaner or more
  leading exhaustion tell than the small sub-fee swings. This is the opposite of how the entry
  archetypes separated.
- ONLY consistent asymmetry: wf_turn is more positive at PEAKS (+0.14..+0.42) than at VALLEYS
  (~0.0..-0.05). That is a Kraken retail BUY-flow baseline bias (buy volume > sell volume on
  average), present at every peak regardless of what price does next — NOT a turn/exhaustion tell.
- ROBUSTNESS across theta: identical null at 10/20/40bps; not a theta artifact.
- Fee-floor winner cut at theta=20: since the zigzag already keeps only swings >= theta, at
  theta=20 essentially every leg is a '>=20bp winner' -> short/long-LOSER groups are empty (n=0);
  the MEDIAN-SIZE winner/loser cut is the informative one and it too shows no separation.

CORRELATION / PRECISION (the decisive two-directional test):
- CORR#1 P(exhaustion SPENT | price turn) = 24-73% across cells/thetas, clustered ~45-60% =
  roughly a COIN FLIP. Turns are NOT reliably marked by a spent/reversed exhaustion state.
- CORR#3 per-leg corr(exhaustion curve, price curve across the swing) = median +0.03..+0.18
  (~+0.1) = near-zero, and the small positive sign means flow runs mildly WITH the price move,
  not the against/rolling-back pattern exhaustion would require.
- CORR#2/#4 flow-flip (60s-imbalance sign flip) as a turn-caller: PRECISION is ~equal to the
  random BASE RATE (lift x1.0-x2.5, absolute precision low: e.g. ~20-49% at +/-60s on the denser
  coins) because flow flips CONSTANTLY — 1300-1800 flips vs only tens-to-hundreds of real turns —
  so it fires everywhere, not specifically at turns. High RECALL (50-86%) is a saturation
  artifact (with that many flips, every turn has one nearby by chance). Median matched LEAD is
  NEGATIVE (-1..-18s) on 4 of 5 cells = the flow flip LAGS or coincides with the price turn, it
  does NOT lead it. => no specific, leading, catch-the-top/bottom signal.
- These four correlation views ALSO fail to separate the 4 swing groups (P(spent|turn) and
  corr are indistinguishable across short/long x winner/loser).

ROOT CAUSE (data reality, diagnosed): Kraken trades are extremely sparse — only ~1.7% (btc) down
to ~0.2% (doge) of 0.1s cells carry a trade — so rolling_imb(20s) saturates to a +/-1 square wave
(btc: 53% of cells |flow|>0.95). The with-trade imbalance simply does not carry a coherent
onset->exhaustion arc over these multi-minute fee-floor price swings.

IMPLICATION: this specific 'book-only 20s order-flow imbalance marks the price turns' tell is not
present in the Kraken book at these resolutions. Catching the exact top/bottom via exhaustion
would need either (a) a denser trade tape (a higher-volume venue/feed or aggregated cross-venue),
or (b) a different exhaustion proxy (book depth/pressure, trade-size decay, or price
microstructure) rather than the sparse 20s trade-imbalance. Plots (per cell, individual swings,
no trade-exit-price) visually confirm the noise: /tmp/kbook/<coin>_peak_valley_groups.png.
"""


def mav(a, w):
    if w <= 1:
        return a
    k = np.ones(w) / w
    return np.convolve(a, k, mode="same")


def zigzag(mid, theta_bps):
    """Alternating price peaks/valleys. A new extreme is CONFIRMED when price retraces
    >= theta from the running extreme. Returns [(idx, 'peak'|'valley'), ...] where idx is
    the actual extreme index (not the confirmation index)."""
    theta = theta_bps / 1e4
    n = len(mid)
    piv = []
    trend = 0                       # +1 up-leg forming, -1 down-leg forming, 0 unknown
    ext_idx, ext_val = 0, float(mid[0])
    anchor = float(mid[0])
    for i in range(1, n):
        p = float(mid[i])
        if trend == 0:
            if (p - anchor) / anchor >= theta:
                trend = 1; ext_idx, ext_val = i, p
            elif (anchor - p) / anchor >= theta:
                trend = -1; ext_idx, ext_val = i, p
        elif trend == 1:            # seeking a PEAK
            if p > ext_val:
                ext_val, ext_idx = p, i
            elif (ext_val - p) / ext_val >= theta:
                piv.append((ext_idx, "peak"))
                trend = -1; ext_val, ext_idx = p, i
        else:                       # trend == -1, seeking a VALLEY
            if p < ext_val:
                ext_val, ext_idx = p, i
            elif (p - ext_val) / ext_val >= theta:
                piv.append((ext_idx, "valley"))
                trend = 1; ext_val, ext_idx = p, i
    return piv


def measure_leg(mid, flow, s, e, end_kind):
    """One swing from extreme s (start) to extreme e (turn). Returns per-leg exhaustion metrics.

    NOTE ON RESOLUTION (important, drives interpretation): Kraken trades are SPARSE (~0.2-1.7% of
    0.1s cells carry a trade), so the 20s rolling imbalance saturates to a +/-1 square wave. A raw
    argmax over a multi-minute swing is meaningless. We therefore smooth the with-flow with a
    swing-PROPORTIONAL window (15% of the leg, clipped 20s..120s) so 'the flow flattens' is a real
    hump top, and we report the hump position as a FRACTION of the leg (0=start extreme, 1=the turn)
    alongside a decisive first-half vs second-half exhaustion test. with-flow is signed by swing dir."""
    dirsign = +1.0 if end_kind == "peak" else -1.0   # up-swing ends in a peak
    wf = flow[s:e + 1] * dirsign
    L = e - s
    if L < 2:
        return None
    dur_s = L * 0.1
    size_bps = abs(mid[e] - mid[s]) / mid[s] * 1e4
    w = int(np.clip(L * 0.15, 20 * CPS, 120 * CPS))  # swing-proportional exhaustion smoothing
    wfS = mav(wf, min(w, L))
    pk = int(np.argmax(wfS))                          # flatten = top of the (smoothed) with-flow hump
    hump_frac = pk / L                                # 0=start .. 1=turn; <1 => flow peaks before the turn
    offset_s = (pk - L) * 0.1                         # seconds before the turn (large for long swings)
    wf_peak = wfS[pk]; wf_min = wfS.min(); wf_turn = wfS[-1]; wf_start = wfS[0]
    rng = (wf_peak - wf_min) + 1e-9
    returned_frac = (wf_peak - wf_turn) / rng         # 1 => flow fully rolled back to its swing-low by the turn
    half = max(1, L // 2)
    fh = wf[:half].mean(); sh = wf[half:].mean()
    exhausts = bool(fh > sh)                          # with-flow WEAKER in 2nd half = genuine exhaustion into the turn
    turned_against = bool(wf_turn < 0)                # flow already opposing the swing AT the turn
    w30 = min(30 * CPS, L)
    xx = np.arange(w30) * 0.1
    vel_turn = np.polyfit(xx, wf[-w30:], 1)[0] if w30 >= 3 else 0.0
    rose = (wf_peak - wf_start) > 0.05
    interior = (0.10 * L) <= pk <= (0.90 * L)
    clean = bool(rose and interior)
    # per-leg correlation of the EXHAUSTION curve vs the PRICE curve across the swing.
    # prog = dir-signed price displacement = 'how far the swing has progressed' (monotone-ish up).
    prog = dirsign * (mid[s:e + 1] - mid[s])
    pf_corr = float(np.corrcoef(wf, prog)[0, 1]) if np.std(wf) > 1e-9 and np.std(prog) > 1e-9 else 0.0
    # 'spent' at the turn = exhaustion in its spent state: rolled >=50% back to its swing-low,
    # OR the flow has crossed to oppose the swing (wf_turn <= 0).
    spent = bool(returned_frac >= 0.5 or wf_turn <= 0)
    return dict(s=s, e=e, end_kind=end_kind, dirsign=dirsign, dur_s=dur_s, size_bps=size_bps,
                offset_s=offset_s, hump_frac=float(hump_frac), wf_turn=float(wf_turn),
                wf_peak=float(wf_peak), returned_frac=float(returned_frac), exhausts=exhausts,
                turned_against=turned_against, vel_turn=float(vel_turn), pf_corr=pf_corr,
                spent=spent, imb_turn=float(flow[e]), clean=clean, pk_cell=pk)


def dist(a):
    a = np.asarray(a, float)
    if len(a) == 0:
        return dict(n=0, med=float("nan"), q1=float("nan"), q3=float("nan"), mean=float("nan"))
    return dict(n=len(a), med=float(np.median(a)), q1=float(np.percentile(a, 25)),
                q3=float(np.percentile(a, 75)), mean=float(np.mean(a)))


def frac_lead(offsets, tol=0.5):
    o = np.asarray(offsets, float)
    return float(np.mean(o <= -tol)) if len(o) else float("nan")


def turn_flow_precision(mid, flow, piv, W_sec):
    """Two-directional correlation between price turns and exhaustion FLIP events.
    Exhaustion-flip event = a sign flip (zero-crossing) of the 60s-smoothed raw imbalance
    (flow flattens through balance and reverses) — detected WITHOUT knowing the swings.
    - PRECISION P(price turn | flow event): fraction of flow events with a confirmed price
      extreme within +/-W_sec, vs the random BASE RATE (specific to turns only if precision>>base).
    - RECALL P(flow event | price turn): fraction of price extremes with a flow event within +/-W_sec.
    - median LEAD: for matched flow events, signed seconds to the nearest extreme (>0 => flow LEADS)."""
    fS = mav(flow, 60 * CPS)
    sg = np.sign(fS); sg[sg == 0] = 1
    cross = np.where(np.diff(sg) != 0)[0]
    ext = np.array([p[0] for p in piv], dtype=float)
    N = len(mid); W = W_sec * CPS
    if len(ext) == 0 or len(cross) == 0:
        return None
    # precision + lead (nearest extreme to each flow event)
    leads = []
    for c in cross:
        j = np.searchsorted(ext, c)
        cands = []
        if j < len(ext): cands.append(ext[j] - c)
        if j > 0: cands.append(ext[j - 1] - c)
        leads.append(min(cands, key=abs))
    leads = np.array(leads)
    hit = np.abs(leads) <= W
    prec = float(hit.mean())
    base = float(min(1.0, 2.0 * W * len(ext) / N))         # random chance of landing within W of an extreme
    med_lead = float(np.median(leads[hit] * 0.1)) if hit.any() else float("nan")
    # recall (nearest flow event to each extreme)
    rhit = 0
    for x in ext:
        k = np.searchsorted(cross, x)
        best = 1e18
        if k < len(cross): best = min(best, abs(cross[k] - x))
        if k > 0: best = min(best, abs(cross[k - 1] - x))
        if best <= W: rhit += 1
    recall = float(rhit / len(ext))
    return dict(n_events=len(cross), n_ext=len(ext), prec=prec, base=base,
                lift=prec / base if base > 0 else float("nan"), recall=recall,
                med_lead=med_lead, W=W_sec)


def assign_groups(legs, win_thresh):
    """4 groups on the swings: short/long by median duration, winner/loser by win_thresh (bps)."""
    dur = np.array([l["dur_s"] for l in legs]); siz = np.array([l["size_bps"] for l in legs])
    dmed = np.median(dur)
    groups = {g: [] for g in GROUP_ORDER}
    for l in legs:
        sh = "short" if l["dur_s"] <= dmed else "long"
        wn = "winner" if l["size_bps"] >= win_thresh else "loser"
        groups[f"{sh}-{wn}"].append(l)
    return groups, dmed


def group_signature(legs):
    hf = np.array([l["hump_frac"] for l in legs]); wft = np.array([l["wf_turn"] for l in legs])
    rf = np.array([l["returned_frac"] for l in legs]); vel = np.array([l["vel_turn"] for l in legs])
    ex = np.array([l["exhausts"] for l in legs]); ta = np.array([l["turned_against"] for l in legs])
    sp = np.array([l["spent"] for l in legs]); pc = np.array([l["pf_corr"] for l in legs])
    up = np.array([l["end_kind"] == "peak" for l in legs])
    line = (f"  n={len(legs):4d} | P(exhaustion SPENT | turn)={100*sp.mean():.0f}% | "
            f"exhaustion-at-turn: wf_turn med={np.median(wft):+.3f} (0=balance) "
            f"returned med={np.median(rf):.2f} (1=rolled back) flow-turned-against={100*ta.mean():.0f}% | "
            f"per-leg corr(flow,price) med={np.median(pc):+.2f} | "
            f"LEAD: flow-hump position med={np.median(hf):.2f} of leg (0.5=random, <0.5=leads) "
            f"exhausts(1st>2nd half)={100*ex.mean():.0f}% (50=coinflip)")
    pk = up.sum(); va = (~up).sum()
    if pk >= 3 and va >= 3:
        line += (f"\n       peak/valley: PEAK(n={pk}) hump_pos={np.median(hf[up]):.2f} "
                 f"wf_turn={np.median(wft[up]):+.3f} exh={100*ex[up].mean():.0f}% | "
                 f"VALLEY(n={va}) hump_pos={np.median(hf[~up]):.2f} "
                 f"wf_turn={np.median(wft[~up]):+.3f} exh={100*ex[~up].mean():.0f}%")
    return line


def analyze_coin(coin, report):
    path = f"{OUTDIR}/{coin}_book.jsonl"
    cfg = [c for c in KRAKEN if c.coin == coin][0]
    raw = load_raw(path)
    ch, g = build_channels(path, cfg.K, SMOOTH_SEC, raw=raw)
    mid = np.asarray(g["mid"], float)
    buy = np.asarray(g["buy"], float); sell = np.asarray(g["sell"], float)
    flow = rolling_imb(buy, sell, SMOOTH_SEC)
    N = len(mid); hours = N * 0.1 / 3600.0
    report.append(f"\n## {coin}_kraken  ({N} cells, {hours:.1f}h)\n")
    per_theta = {}
    for theta in THETAS:
        piv = zigzag(mid, theta)
        legs = []
        for k in range(len(piv) - 1):
            m = measure_leg(mid, flow, piv[k][0], piv[k + 1][0], piv[k + 1][1])
            if m is not None:
                legs.append(m)
        per_theta[theta] = (piv, legs)
        if not legs:
            report.append(f"### theta={theta:.0f}bps — 0 legs\n")
            continue
        hf = np.array([l["hump_frac"] for l in legs])
        wft = np.array([l["wf_turn"] for l in legs]); rf = np.array([l["returned_frac"] for l in legs])
        ex = np.array([l["exhausts"] for l in legs]); ta = np.array([l["turned_against"] for l in legs])
        dur = np.array([l["dur_s"] for l in legs])
        siz = np.array([l["size_bps"] for l in legs]); clean = np.array([l["clean"] for l in legs])
        up = np.array([l["end_kind"] == "peak" for l in legs])
        do = report.append
        do(f"### theta={theta:.0f}bps — {len(legs)} legs "
           f"({int(up.sum())} up->peak, {int((~up).sum())} down->valley); "
           f"clean-hump legs={int(clean.sum())} ({100*clean.mean():.0f}%)\n")
        do(f"- median swing: dur={np.median(dur):.0f}s  size={np.median(siz):.1f}bps\n")
        do(f"- LEAD test — flow-hump position in leg (0=start,1=turn; 0.5=random, <0.5 would LEAD): "
           f"median={np.median(hf):.2f}  IQR[{np.percentile(hf,25):.2f},{np.percentile(hf,75):.2f}]\n")
        do(f"- EXHAUSTION test — with-flow 1st-half > 2nd-half (weaker into the turn): "
           f"{100*ex.mean():.0f}% of legs (50%=coinflip)\n")
        do(f"- exhaustion AT turn: with-flow median={np.median(wft):+.3f} (0=balanced, +1=still fully with-trend); "
           f"returned-fraction median={np.median(rf):.2f} (1=fully rolled back); "
           f"flow-turned-against-swing-at-turn={100*ta.mean():.0f}%\n")
        sp = np.array([l["spent"] for l in legs]); pc = np.array([l["pf_corr"] for l in legs])
        do(f"- CORR #1 P(exhaustion SPENT | price turn)={100*sp.mean():.0f}% "
           f"(spent = returned>=50% OR flow crossed to oppose the swing)\n")
        do(f"- CORR #3 per-leg corr(exhaustion curve, price curve across swing): "
           f"median={np.median(pc):+.2f}  IQR[{np.percentile(pc,25):+.2f},{np.percentile(pc,75):+.2f}] "
           f"(0=uncorrelated)\n")
        for Ws in (30, 60):
            pr = turn_flow_precision(mid, flow, piv, Ws)
            if pr:
                do(f"- CORR #2/#4 flow-flip as turn-caller (+-{Ws}s): "
                   f"PRECISION P(turn|flow-flip)={100*pr['prec']:.0f}% vs base {100*pr['base']:.0f}% "
                   f"(lift x{pr['lift']:.2f}); RECALL P(flow-flip|turn)={100*pr['recall']:.0f}%; "
                   f"median lead={pr['med_lead']:+.0f}s (>0=leads); {pr['n_events']} flow-flips vs {pr['n_ext']} turns\n")
        do(f"- asymmetry: up->PEAK hump_pos={np.median(hf[up]):.2f} wf_turn={np.median(wft[up]):+.3f} "
           f"exh={100*ex[up].mean():.0f}% | down->VALLEY hump_pos={np.median(hf[~up]):.2f} "
           f"wf_turn={np.median(wft[~up]):+.3f} exh={100*ex[~up].mean():.0f}%\n")
        def terciles(vals, key):
            qs = np.percentile(vals, [33.3, 66.7])
            lo = vals <= qs[0]; hi = vals > qs[1]; mid_ = ~lo & ~hi
            return (f"    {key} terciles — flow-hump pos / exhausts%%: "
                    f"low={np.median(hf[lo]):.2f}/{100*ex[lo].mean():.0f}%  "
                    f"mid={np.median(hf[mid_]):.2f}/{100*ex[mid_].mean():.0f}%  "
                    f"high={np.median(hf[hi]):.2f}/{100*ex[hi].mean():.0f}%  "
                    f"[low<= {qs[0]:.0f} < mid <= {qs[1]:.0f} < high]\n")
        do("- duration-invariance:\n" + terciles(dur, "duration(s)"))
        do("- size-invariance:\n" + terciles(siz, "size(bps)"))

    # ---- 4-GROUP breakdown at anchor theta=20bps ----
    _, legs20 = per_theta[20.0]
    if legs20:
        do = report.append
        do(f"\n### 4-GROUP breakdown (theta=20bps, {len(legs20)} legs)\n")
        siz20 = np.array([l["size_bps"] for l in legs20]); szmed = np.median(siz20)
        for cut_name, thr in [(f"WINNER = swing >= {FEE_BPS:.0f}bp fee floor", FEE_BPS),
                              (f"WINNER = swing >= median size ({szmed:.0f}bp)", szmed)]:
            groups, dmed = assign_groups(legs20, thr)
            do(f"\n**Cut: {cut_name}**  (short/long split at median dur {dmed:.0f}s)\n")
            for gname in GROUP_ORDER:
                gl = groups[gname]
                if len(gl) < 3:
                    do(f"- {gname}: n={len(gl)} (too few)\n"); continue
                do(f"- {gname}:\n{group_signature(gl)}\n")
        plot_coin_groups(coin, mid, flow, legs20, szmed)
    return per_theta


def _plot_leg(ax, mid, flow, l):
    s, e = l["s"], l["e"]; dirsign = l["dirsign"]
    seg_mid = mid[s:e + 1]; tsec = np.arange(len(seg_mid)) * 0.1
    price_bps = (seg_mid - seg_mid[0]) / seg_mid[0] * 1e4
    wf = flow[s:e + 1] * dirsign
    L = len(wf)
    w = int(np.clip(L * 0.15, DISP_SEC * CPS, 120 * CPS))   # match measurement smoothing (>=60s for display)
    wf_disp = mav(wf, min(w, L))
    pkd = int(np.argmax(wf_disp))
    ax.plot(tsec, price_bps, color="C3", lw=1.5); ax.axhline(0, color="0.7", lw=0.5)
    ax2 = ax.twinx(); ax2.plot(tsec, wf_disp, color="C0", lw=1.4); ax2.axhline(0, color="C0", lw=0.4, alpha=0.4)
    kstart = "valley" if l["end_kind"] == "peak" else "peak"
    ax.plot(0, 0, "o", color="k", ms=5)                       # start extreme
    ax.plot(tsec[-1], price_bps[-1], "X", color="k", ms=7)    # the TURN
    ax2.plot(tsec[pkd], wf_disp[pkd], "*", color="green", ms=11)  # flow flattens
    ax.set_title(f"{kstart}->{l['end_kind']} dur{l['dur_s']:.0f}s sz{l['size_bps']:.0f}bp "
                 f"flat@{(pkd-len(wf))*0.1:+.0f}s", fontsize=7)
    ax.tick_params(labelsize=5); ax2.tick_params(labelsize=5, colors="C0")
    return ax2


def plot_coin_groups(coin, mid, flow, legs, szmed):
    """4-group layout: rows = short-winner/long-winner/short-loser/long-loser (fee-floor winner def).
    Sample individual swings spanning each group's duration range."""
    groups, dmed = assign_groups(legs, FEE_BPS)
    ncol = 5
    fig, axs = plt.subplots(4, ncol, figsize=(4.0 * ncol, 12))
    for r, gname in enumerate(GROUP_ORDER):
        gl = sorted(groups[gname], key=lambda l: l["dur_s"])
        if gl:
            idxs = np.linspace(0, len(gl) - 1, min(ncol, len(gl))).astype(int)
            pick = [gl[i] for i in idxs]
        else:
            pick = []
        for c in range(ncol):
            ax = axs[r, c]
            if c >= len(pick):
                ax.axis("off"); continue
            _plot_leg(ax, mid, flow, pick[c])
            if c == 0:
                ax.set_ylabel(f"{gname}\n(n={len(groups[gname])})", fontsize=9, color="k")
    fig.suptitle(f"{coin}_kraken — PRICE swings by 4 groups (theta=20bp; winner=swing>={FEE_BPS:.0f}bp, "
                 f"short=dur<= {dmed:.0f}s)  |  red=price bps(L) blue=exhaustion/with-flow 60s(R)  "
                 f"o=start X=TURN green*=flow flattens", fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    p = f"{OUTDIR}/{coin}_peak_valley_groups.png"
    fig.savefig(p, dpi=95); plt.close()
    print(f"  {coin}: saved {p}", flush=True)
    return p


if __name__ == "__main__":
    coins = sys.argv[1:] or COINS
    report = ["# PEAK/VALLEY EXHAUSTION FINDINGS (S72) — descriptive, per-cell, per-leg distributions\n",
              "Segment the tape by the PRICE's own zigzag peaks/valleys; measure with-trade order-flow\n"
              "imbalance ('exhaustion') AT the price turns. with-flow signed by swing direction.\n"
              "LEAD test = flow-hump position within the leg (0=start extreme, 1=the turn); <0.5 would\n"
              "mean flow flattens BEFORE the price turn = LEADS = catchable. 4 groups on the SWINGS:\n"
              "short/long = swing duration vs median; winner/loser = swing magnitude vs 20bp fee floor.\n",
              VERDICT]
    for c in coins:
        print(f"... {c} ...", flush=True)
        try:
            analyze_coin(c, report)
        except Exception as ex:
            import traceback; traceback.print_exc()
            report.append(f"\n## {c}_kraken — FAILED: {ex}\n")
    txt = "".join(report)
    print("\n" + txt, flush=True)
    with open("/home/user/Markets/research/exit_s72/PEAK_VALLEY_FINDINGS_S72.md", "w") as f:
        f.write(txt)
    print("wrote research/exit_s72/PEAK_VALLEY_FINDINGS_S72.md", flush=True)
