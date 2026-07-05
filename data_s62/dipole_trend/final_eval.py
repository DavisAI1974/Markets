"""final_eval.py — definitive per-cell dipole arm-point trend-read evaluation. S62."""
import sys, json
sys.path.insert(0, '/home/user/Markets/scripts'); sys.path.insert(0, '/home/user/Markets')
sys.path.insert(0, '/tmp/claude-0/-home-user-Markets/f99798a3-6da2-5ba6-be91-f750299844f3/scratchpad')
import numpy as np
from _s54_backfill_sweep import load_bins
from odcore.entry_coinbase import armed_midband_flips
from dipole_trend_gate import arm_trend_reads
from run_gate import auc

CELLS = [('SOLUSDT', 100), ('ETHUSDT', 80), ('BTCUSDT', 80), ('XRPUSDT', 80), ('DOGEUSDT', 100)]
CAP = 5000.0; FLIP_COST = 22.0; DEATH = -40.0; REC = -20.0
# candidate arm-point reads to score (dipole-family + price ER comparison)
FEATS = ['netmag_full', 'netmag_t120', 'lean_full', 'aligned_full', 'aligned_t120',
         'miflow_full', 'persist_full', 'revconv_full', 'er_full', 'er_t120']


def build(SYM, TH, Xarm):
    mid, buy, sell, cover, hrs = load_bins(f'/tmp/backfill/{SYM}_30d_bins.json')
    mid = np.asarray(mid, float); buy = np.asarray(buy, float); sell = np.asarray(sell, float)
    n = len(mid); flips = armed_midband_flips(mid, TH, 0.5)
    legs = []
    for k in range(len(flips) - 1):
        ci, xi, side = int(flips[k][0]), int(flips[k + 1][0]), int(flips[k][2])
        if xi <= ci or ci < 1802:
            continue
        seg = side * (np.log(mid[ci:xi + 1]) - np.log(mid[ci])) * 1e4
        below = np.where(seg <= -Xarm)[0]
        aj = ci + int(below[0]) if len(below) else None
        gross = float(side * (np.log(mid[xi]) - np.log(mid[ci])) * 1e4)
        L = dict(ci=ci, xi=xi, side=side, aj=aj, gross=gross)
        if aj is not None:
            L['arm_loss'] = float(side * (np.log(mid[aj]) - np.log(mid[ci])) * 1e4)
            L['rest'] = float(side * (np.log(mid[xi]) - np.log(mid[aj])) * 1e4)
            L['reads'] = arm_trend_reads(mid, buy, sell, ci, aj, side)
        legs.append(L)
    return dict(SYM=SYM, TH=TH, Xarm=Xarm, mid=mid, buy=buy, sell=sell, hrs=hrs, n=n, legs=legs)


def labels_of(legs):
    keep = []; lab = []
    for L in legs:
        if L['aj'] is None:
            continue
        if L['gross'] <= DEATH:
            keep.append(L); lab.append(1)
        elif L['gross'] > REC:
            keep.append(L); lab.append(0)
    return keep, np.array(lab)


def leg_pnl(L, action):
    if L['aj'] is None:
        return L['gross']
    if action == 'flip':
        return L['arm_loss'] - L['rest'] - FLIP_COST
    if action == 'flatten':
        return L['arm_loss']
    return L['gross']


def dph(legs, decide, hrs):
    return (sum(leg_pnl(L, decide(L)) for L in legs) / 1e4 * CAP) / hrs


def circ_null_auc(D, keep, lab, feature, nperm=150, seed=1):
    rng = np.random.default_rng(seed); N = len(D['buy']); mid = D['mid']
    out = []
    for _ in range(nperm):
        sh = int(rng.integers(N // 10, N - N // 10))
        b2 = np.roll(D['buy'], sh); s2 = np.roll(D['sell'], sh)
        sc = [arm_trend_reads(mid, b2, s2, L['ci'], L['aj'], L['side']).get(feature, 0.0) for L in keep]
        out.append(auc(np.array(sc), lab))
    return np.array(out)


def main():
    report = {}
    for SYM, TH in CELLS:
        cell = {}
        for Xarm in (10, 15):
            D = build(SYM, TH, Xarm)
            legs = D['legs']; hrs = D['hrs']
            keep, lab = labels_of(legs)
            armed = [L for L in legs if L['aj'] is not None]
            aucs = {f: auc(np.array([L['reads'][f] for L in keep]), lab) for f in FEATS}
            best = max(FEATS, key=lambda f: aucs[f])
            # null on best
            null = circ_null_auc(D, keep, lab, best, nperm=40)
            z = (aucs[best] - null.mean()) / (null.std() + 1e-9)
            # baseline / oracle
            base = dph(legs, lambda L: 'hold', hrs)
            orac = dph(legs, lambda L: ('flip' if L['gross'] <= DEATH else 'hold') if L['aj'] is not None else 'hold', hrs)
            # gated flip: flip armed legs with top-q netmag; hold rest. sweep q, in-sample best + report
            sc_best = {id(L): L['reads'][best] for L in armed}
            vals = np.array([sc_best[id(L)] for L in armed])
            qres = {}
            for q in (0.05, 0.1, 0.15, 0.2, 0.3):
                thr = np.quantile(vals, 1 - q)
                fset = set(id(L) for L in armed if sc_best[id(L)] >= thr)
                qres[q] = dph(legs, lambda L: ('flip' if id(L) in fset else 'hold'), hrs)
            bestq = max(qres, key=lambda q: qres[q])
            # per-week $/hr at bestq (fixed threshold from full sample -> mild leakage, but robustness view)
            thr = np.quantile(vals, 1 - bestq)
            fset = set(id(L) for L in armed if sc_best[id(L)] >= thr)
            wk = D['n'] // 4; wkdph = []
            for w in range(4):
                seg = [L for L in legs if w * wk <= L['ci'] < (w + 1) * wk]
                seghrs = (min((w + 1) * wk, D['n']) - w * wk) / 3600.0
                b = dph(seg, lambda L: 'hold', seghrs)
                g = dph(seg, lambda L: ('flip' if id(L) in fset else 'hold'), seghrs)
                wkdph.append((round(b, 2), round(g, 2)))
            # biggest-loser capture: of 10 worst legs, how many armed & flipped; recovery-winners spared
            worst10 = sorted(legs, key=lambda L: L['gross'])[:10]
            w10_flipped = sum(1 for L in worst10 if L['aj'] is not None and id(L) in fset)
            rec_winners = [L for L in armed if L['gross'] > 0]  # recovered to positive
            rec_spared = sum(1 for L in rec_winners if id(L) not in fset)
            cell[f'X{Xarm}'] = dict(
                narmed=len(armed), ndeath=int((lab == 1).sum()), nrec=int((lab == 0).sum()),
                aucs={f: round(float(v), 3) for f, v in aucs.items()},
                best=best, best_auc=round(float(aucs[best]), 3),
                null_mean=round(float(null.mean()), 3), null_z=round(float(z), 2),
                base=round(base, 2), oracle_flipdeath=round(orac, 2),
                gated_by_q={str(q): round(v, 2) for q, v in qres.items()},
                bestq=bestq, gated_bestq=round(qres[bestq], 2),
                perweek=wkdph, worst10_flipped=w10_flipped,
                rec_winners=len(rec_winners), rec_spared=rec_spared)
            print(f"{SYM} X{Xarm}: armed={len(armed)} D/R={int((lab==1).sum())}/{int((lab==0).sum())} "
                  f"best={best} AUC={aucs[best]:.3f} z={z:.1f} | base={base:+.2f} oracle={orac:+.2f} "
                  f"gated(q{bestq})={qres[bestq]:+.2f} | w10flip={w10_flipped}/10 recSpared={rec_spared}/{len(rec_winners)}", flush=True)
        report[SYM] = cell
    with open('/tmp/claude-0/-home-user-Markets/f99798a3-6da2-5ba6-be91-f750299844f3/scratchpad/final_eval.json', 'w') as f:
        json.dump(report, f, indent=1)
    print('\nsaved final_eval.json')


if __name__ == '__main__':
    main()
