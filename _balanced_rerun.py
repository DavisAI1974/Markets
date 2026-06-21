"""S34 Direction-2 balanced re-run — de-confound + stack on the MEATED pools.

Merges the existing 1240 same-period win coeffs (cs2000_clean) with the newly
discovered candidate coeffs (cand_sp), relabels the candidates by true-horizon,
pulls microstructure features from the audit, and re-runs per cell:
  - DIPOLE (centroid margin) OOF AUC + within-period 500-perm null z
  - DIPOLE vs MICRO vs STACK OOF AUC + lift
on the now-balanced win/lose pools. The point: does more lose-side meat make any
per-cell signal (dipole, micro, or the stack) survive + clear the bar.
"""
from __future__ import annotations

import bisect, csv, glob, json, math, re, sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, r"E:\refrag\adapters")
from markets_bar_loader import load_closes  # noqa: E402

DISC = Path(r"E:\refrag\discoveries\operator_discoveries")
EXIST_SHARDS = Path(r"E:\Markets\_cs2000_coeff_index")
EXIST_RELABEL = Path(r"E:\Markets\_relabel_true_horizon_results.json")
CAND_DIR = Path(r"E:\Markets\_sameperiod_cand")
AUDIT = Path(r"E:\Markets\research\strategy_evolution\live_mock_replay\live_hindsight_missed_winner_audit_rows.csv")
OUT = Path(r"E:\Markets\_balanced_rerun_results.json")
CAND_SUFFIX = "_win_cand_sp"
FEE_BPS = 10.0
MICRO = ["mean_dipole", "dipole_acl1", "volume_zscore", "trade_present_score",
         "trade_recent_2chunk_bps", "trade_from_onset_bps"]
PAIRS = ["btc_bybit_buy", "btc_bybit_sell", "btc_coinbase_buy", "btc_coinbase_sell",
         "btc_kraken_buy", "btc_kraken_sell", "eth_bybit_buy", "eth_bybit_sell",
         "eth_coinbase_buy", "eth_coinbase_sell", "eth_kraken_buy", "eth_kraken_sell"]
K, SEED, N_PERM = 5, 1974, 500
RE_COEF = re.compile(r'"operator_coefficients"\s*:\s*\[([^\]]*)\]')
RE_SID = re.compile(r'"supporting_documents"\s*:\s*\[\s*"([^"]+)"')


def pair_of(sid):
    p = sid.split("|")
    return f"{p[0].lower()}_{p[1].lower()}_{p[-1].lower()}" if len(p) >= 4 else None


def auc(scores, labels):
    pos = scores[labels == 1]; neg = scores[labels == 0]
    if len(pos) == 0 or len(neg) == 0:
        return 0.5
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty(len(scores)); ranks[order] = np.arange(1, len(scores) + 1)
    s = scores[order]; i = 0
    while i < len(s):
        j = i
        while j < len(s) and s[j] == s[i]:
            j += 1
        if j - i > 1:
            ranks[order[i:j]] = (i + 1 + j) / 2.0
        i = j
    U = ranks[labels == 1].sum() - len(pos) * (len(pos) + 1) / 2.0
    return float(U / (len(pos) * len(neg)))


def folds_of(y, k, rng):
    pos = np.where(y == 1)[0]; neg = np.where(y == 0)[0]
    rng.shuffle(pos); rng.shuffle(neg)
    return [np.sort(np.concatenate([pos[i::k], neg[i::k]])) for i in range(k)]


def oof_margin(C, y, folds):
    s = np.zeros(len(y))
    for fi in range(len(folds)):
        te = folds[fi]; tr = np.concatenate([folds[f] for f in range(len(folds)) if f != fi])
        tw = C[tr[y[tr] == 1]]; tl = C[tr[y[tr] == 0]]
        if len(tw) == 0 or len(tl) == 0:
            continue
        cw = tw.mean(0); cl = tl.mean(0)
        nw = np.linalg.norm(cw) or 1.0; nl = np.linalg.norm(cl) or 1.0
        s[te] = C[te] @ cw / nw - C[te] @ cl / nl
    return s


def load_coeffs():
    coefs = {}
    for sh in glob.glob(str(EXIST_SHARDS / "*_win_preentry_cs2000_clean.json")):
        for _u, rec in json.load(open(sh)).items():
            coefs[rec["source_id"]] = rec["coef"]
    n_exist = len(coefs)
    n_cand = 0
    for d in DISC.glob(f"markets_*{CAND_SUFFIX}"):
        for fp in d.glob("*.json"):
            txt = fp.read_text(encoding="utf-8", errors="ignore")
            mc = RE_COEF.search(txt); ms = RE_SID.search(txt)
            if not mc or not ms:
                continue
            try:
                coef = [float(x) for x in mc.group(1).split(",") if x.strip()]
            except ValueError:
                continue
            if len(coef) == 128 and ms.group(1) not in coefs:
                coefs[ms.group(1)] = coef; n_cand += 1
    print(f"coeffs: existing={n_exist}  new_cand={n_cand}  total={len(coefs)}")
    return coefs


def load_labels(cand_sids):
    lab = {}
    rel = json.load(open(EXIST_RELABEL))
    for t in rel["trades"]:
        if t.get("new_label") in ("win", "lose"):
            lab[t["source_id"]] = t["new_label"]
    # relabel candidates by true-horizon (only those with coeffs)
    cand = {}
    for p in PAIRS:
        fp = CAND_DIR / f"markets_{p}_cand.json"
        if not fp.exists():
            continue
        for e in json.load(open(fp)).get("entries", []):
            if e["source_id"] in cand_sids:
                cand[e["source_id"]] = e
    series = {}
    for av in sorted({(e["asset"], e["venue"]) for e in cand.values()}):
        ts = [e["entry_ts_utc"] for e in cand.values() if (e["asset"], e["venue"]) == av]
        hs = [e["horizon_minutes"] for e in cand.values() if (e["asset"], e["venue"]) == av]
        cl = load_closes(asset=av[0], venue=av[1], t_min=min(ts) - 120, t_max=max(ts) + max(hs) * 60 + 120)
        series[av] = ([c.ts for c in cl], [c.close for c in cl])
    n_rel = 0
    for sid, e in cand.items():
        av = (e["asset"], e["venue"]); ts = float(e["entry_ts_utc"]); H = float(e["horizon_minutes"])
        if av not in series:
            continue
        tsl, csl = series[av]
        i = bisect.bisect_left(tsl, ts)
        cands = [j for j in (i - 1, i) if 0 <= j < len(tsl)]
        if not cands:
            continue
        entry = csl[min(cands, key=lambda k: abs(tsl[k] - ts))]
        i0 = bisect.bisect_right(tsl, ts); i1 = bisect.bisect_right(tsl, ts + H * 60)
        seg = csl[i0:i1]
        if entry <= 0 or not seg:
            continue
        if e["side"].lower() == "buy":
            net = (max(seg) / entry - 1) * 1e4 - FEE_BPS
        else:
            net = (entry / min(seg) - 1) * 1e4 - FEE_BPS
        lab[sid] = "win" if net > 0 else "lose"; n_rel += 1
    print(f"labels: existing+cand; candidates relabeled={n_rel}")
    return lab


def load_micro():
    feats = {}
    with AUDIT.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            k = r.get("unique_key")
            if not k or k in feats:
                continue
            row = {}
            ok = True
            for m in MICRO:
                try:
                    row[m] = float(r.get(m))
                except (TypeError, ValueError):
                    ok = False; break
            if ok:
                feats[k] = row
    return feats


def main() -> int:
    coefs = load_coeffs()
    lab = load_labels(set(coefs))
    micro = load_micro()
    data = {p: {"C": [], "M": [], "y": []} for p in PAIRS}
    for sid, c in coefs.items():
        l = lab.get(sid); p = pair_of(sid); m = micro.get(sid)
        if l not in ("win", "lose") or p not in data or m is None:
            continue
        data[p]["C"].append(c); data[p]["M"].append([m[k] for k in MICRO])
        data[p]["y"].append(1 if l == "win" else 0)

    print(f"\n{'pair':18s} {'n_w':>4s} {'n_l':>4s} {'AUCdip':>6s} {'z_perm':>6s} {'AUCmic':>6s} {'AUCstk':>6s} {'lift':>6s}")
    print("-" * 70)
    res = {}
    for p in PAIRS:
        C = np.array(data[p]["C"], float); M = np.array(data[p]["M"], float); y = np.array(data[p]["y"], int)
        nw = int((y == 1).sum()); nl = int((y == 0).sum())
        if nw < 8 or nl < 8:
            print(f"{p:18s} {nw:>4d} {nl:>4d}   (too few)")
            res[p] = {"n_win": nw, "n_lose": nl, "note": "too_few"}; continue
        rng = np.random.default_rng(SEED)
        folds = folds_of(y, K, rng)
        sA = oof_margin(C, y, folds)
        aA = auc(sA, y)
        nulls = np.empty(N_PERM)
        for k in range(N_PERM):
            yp = rng.permutation(y)
            nulls[k] = auc(oof_margin(C, yp, folds_of(yp, K, rng)), yp)
        z = float((aA - nulls.mean()) / (nulls.std() + 1e-12))
        # stack
        sB = np.zeros(len(y)); sC = np.zeros(len(y))
        for fi in range(K):
            te = folds[fi]; tr = np.concatenate([folds[f] for f in range(K) if f != fi])
            ytr = y[tr]
            tw = C[tr[ytr == 1]]; tl = C[tr[ytr == 0]]
            if len(tw) == 0 or len(tl) == 0:
                continue
            cw = tw.mean(0); cl = tl.mean(0)
            nwn = np.linalg.norm(cw) or 1.0; nln = np.linalg.norm(cl) or 1.0
            mtr = C[tr] @ cw / nwn - C[tr] @ cl / nln
            mte = C[te] @ cw / nwn - C[te] @ cl / nln
            scl = StandardScaler().fit(M[tr])
            sB[te] = LogisticRegression(max_iter=1000).fit(scl.transform(M[tr]), ytr).predict_proba(scl.transform(M[te]))[:, 1]
            XtrC = np.column_stack([mtr, M[tr]]); XteC = np.column_stack([mte, M[te]])
            sclC = StandardScaler().fit(XtrC)
            sC[te] = LogisticRegression(max_iter=1000).fit(sclC.transform(XtrC), ytr).predict_proba(sclC.transform(XteC))[:, 1]
        aB = auc(sB, y); aC = auc(sC, y); lift = aC - max(aA, aB)
        print(f"{p:18s} {nw:>4d} {nl:>4d} {aA:>6.3f} {z:>+6.2f} {aB:>6.3f} {aC:>6.3f} {lift:>+6.3f}")
        res[p] = {"n_win": nw, "n_lose": nl, "auc_dipole": aA, "z_perm": z,
                  "auc_micro": aB, "auc_stack": aC, "lift": lift}
    nz = sum(1 for r in res.values() if r.get("z_perm", 0) > 3)
    nstk = sum(1 for r in res.values() if r.get("lift", -1) > 0.02)
    print("-" * 70)
    print(f"dipole z_perm>3: {nz}/12   stack lift>+0.02: {nstk}/12")
    OUT.write_text(json.dumps({"schema": "balanced_rerun_v1", "results": res}, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
