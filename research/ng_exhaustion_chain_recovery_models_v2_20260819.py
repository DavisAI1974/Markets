#!/usr/bin/env python3
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

import numpy as np
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.neighbors import KNeighborsClassifier

from ng_exhaustion_chain_recovery_features_v2_20260819 import *


def scale(Xtr, Xte):
    if Xtr.shape[1] == 0:
        return Xtr, Xte
    xm = Xtr.mean(0)
    xs = Xtr.std(0)
    xs[xs < 1e-9] = 1.0
    return (Xtr - xm) / xs, (Xte - xm) / xs


def fit_model(name, param, X, y):
    if len(np.unique(y)) < 2 or X.shape[1] == 0:
        return None
    if name == "logistic":
        m = LogisticRegression(C=float(param), max_iter=1200, random_state=SEED)
    elif name == "extra_trees":
        m = ExtraTreesClassifier(n_estimators=120, min_samples_leaf=int(param), max_features=1.0, random_state=SEED, n_jobs=-1)
    else:
        m = KNeighborsClassifier(n_neighbors=min(int(param), len(X)), weights="distance", n_jobs=-1)
    m.fit(X, y)
    return m


def predict_probs(name, param, Xtr, ytr, Xte):
    A, C = scale(Xtr, Xte)
    m = fit_model(name, param, A, ytr)
    if m is None:
        return None, []
    return np.asarray(m.predict_proba(C), float), [str(x) for x in m.classes_]


def align_probs(probs: np.ndarray, model_classes: list[str], labels: list[str]):
    out = np.full((len(probs), len(labels)), 1e-9, float)
    pos = {lab: i for i, lab in enumerate(labels)}
    for j, lab in enumerate(model_classes):
        if lab in pos:
            out[:, pos[lab]] = probs[:, j]
    out /= out.sum(axis=1, keepdims=True)
    return out


def null_probs(ytr: np.ndarray, labels: list[str], n: int):
    c = Counter(str(x) for x in ytr)
    v = np.asarray([c.get(l, 0) + 1e-9 for l in labels], float)
    v /= v.sum()
    return np.repeat(v.reshape(1, -1), n, axis=0)


def multiclass_brier(y: np.ndarray, p: np.ndarray, labels: list[str]):
    pos = {lab: i for i, lab in enumerate(labels)}
    Y = np.zeros_like(p)
    for i, yy in enumerate(y):
        Y[i, pos[str(yy)]] = 1.0
    return float(np.mean(np.sum((Y - p) ** 2, axis=1)))


def metrics(y, p, nullp, labels, weeks):
    if not len(y):
        return {"n": 0}
    ll = float(log_loss(y, p, labels=labels))
    nll = float(log_loss(y, nullp, labels=labels))
    br = multiclass_brier(y, p, labels)
    nbr = multiclass_brier(y, nullp, labels)
    pred = np.asarray([labels[i] for i in np.argmax(p, axis=1)], dtype=object)
    out = {
        "n": int(len(y)),
        "class_counts": dict(sorted(Counter(str(x) for x in y).items())),
        "classes": labels,
        "log_loss": ll,
        "null_log_loss": nll,
        "log_loss_gain_vs_null": nll - ll,
        "brier": br,
        "null_brier": nbr,
        "brier_gain_vs_null": nbr - br,
        "accuracy": float(np.mean(pred == y)),
    }
    if len(labels) == 2 and len(set(y)) == 2:
        poslab = "1" if "1" in labels else labels[-1]
        j = labels.index(poslab)
        yy = np.asarray([1 if str(x) == poslab else 0 for x in y], int)
        out["roc_auc"] = float(roc_auc_score(yy, p[:, j]))
    else:
        out["roc_auc"] = None
    by = defaultdict(list)
    for i, w in enumerate(weeks):
        by[w].append(i)
    gains = {}
    for w, idx in by.items():
        yy = y[idx]
        pp = p[idx]
        nn = nullp[idx]
        gains[w] = multiclass_brier(yy, nn, labels) - multiclass_brier(yy, pp, labels)
    out["positive_week_fraction_brier"] = float(np.mean([g > 0 for g in gains.values()])) if gains else None
    out["per_week_brier_gain"] = dict(sorted((w, float(g)) for w, g in gains.items()))
    return out


def tune_param(model, fitset, tuneset, stage, phase, sec, cache, view, target):
    Xf, yf, _, _, _ = dataset(fitset, stage, phase, sec, cache, view, target)
    Xt, yt, _, _, _ = dataset(tuneset, stage, phase, sec, cache, view, target)
    if len(np.unique(yf)) < 2 or len(yt) == 0:
        return None
    best = None
    labels = sorted(set(map(str, yf)) | set(map(str, yt)))
    for param in GRIDS[model]:
        raw, cls = predict_probs(model, param, Xf, yf, Xt)
        if raw is None:
            continue
        p = align_probs(raw, cls, labels)
        loss = float(log_loss(yt, p, labels=labels))
        z = (loss, float(param), param)
        if best is None or z[:2] < best[:2]:
            best = z
    return None if best is None else best[2]


def score_block(model, param, trainset, testset, stage, phase, sec, cache, view, target):
    Xtr, ytr, _, _, _ = dataset(trainset, stage, phase, sec, cache, view, target)
    Xte, yte, weeks, leads, ids = dataset(testset, stage, phase, sec, cache, view, target)
    if len(np.unique(ytr)) < 2 or len(yte) == 0:
        return {"n": 0}
    raw, cls = predict_probs(model, param, Xtr, ytr, Xte)
    if raw is None:
        return {"n": 0}
    labels = sorted(set(map(str, ytr)) | set(map(str, yte)))
    p = align_probs(raw, cls, labels)
    np0 = null_probs(ytr, labels, len(yte))
    rec = metrics(yte, p, np0, labels, weeks)
    rec["ids"] = ids
    rec["lead_seconds"] = {
        "min": int(min(leads)) if leads else None,
        "median": float(np.median(leads)) if leads else None,
        "p90": float(np.quantile(leads, 0.90)) if leads else None,
        "max": int(max(leads)) if leads else None,
    }
    return rec


def support_ok(target: str, stage: int, block: str, q: dict[str, Any]):
    if q.get("n", 0) <= 0 or len(q.get("class_counts", {})) < 2:
        return False
    if target == "CONTINUATION":
        req = frozen.MIN_COUNTS[stage]
        cc = q["class_counts"]
        return int(cc.get("1", 0)) >= req[f"{block}_pos"] and int(cc.get("0", 0)) >= req[f"{block}_neg"]
    floor = {
        1: {"validation": 200, "confirmation": 100},
        2: {"validation": 30, "confirmation": 15},
        3: {"validation": 10, "confirmation": 5},
    }[stage][block]
    return int(q.get("n", 0)) >= floor


def independent_pass(target: str, stage: int, blocks: dict[str, dict[str, Any]]):
    for b in ("validation", "confirmation"):
        q = blocks.get(b, {})
        if not support_ok(target, stage, b, q):
            return False
        if not (q.get("log_loss_gain_vs_null", -1) > 0 and q.get("brier_gain_vs_null", -1) > 0):
            return False
        if q.get("positive_week_fraction_brier") is not None and q["positive_week_fraction_brier"] < 0.5:
            return False
        if target == "CONTINUATION" and (q.get("roc_auc") is None or q.get("roc_auc", 0) <= 0.5):
            return False
    held = blocks.get("held", {})
    if held.get("n", 0) >= 20 and held.get("brier_gain_vs_null", 0) < 0:
        return False
    return True


def evaluate(model, cases, stage, phase, sec, cache, view, target):
    fitset = split_cases(cases, ("discovery_fit",))
    tuneset = split_cases(cases, ("discovery_tune",))
    trainset = fitset + tuneset
    param = tune_param(model, fitset, tuneset, stage, phase, sec, cache, view, target)
    out = {"phase": phase, "seconds": int(sec), "view": view, "target": target, "param": param, "blocks": {}}
    if param is None:
        out["independently_validated"] = False
        return out
    for b in ("validation", "confirmation", "held"):
        out["blocks"][b] = score_block(model, param, trainset, split_cases(cases, (b,)), stage, phase, sec, cache, view, target)
    out["independently_validated"] = independent_pass(target, stage, out["blocks"])
    return out


def price_increment(full: dict[str, Any], noprice: dict[str, Any]):
    out = {}
    for b in ("validation", "confirmation", "held"):
        a = full.get("blocks", {}).get(b, {})
        n = noprice.get("blocks", {}).get(b, {})
        if not a.get("n") or not n.get("n") or a.get("ids") != n.get("ids"):
            out[b] = {"n": 0}
            continue
        out[b] = {
            "n": int(a["n"]),
            "full_minus_no_price_log_loss_improvement": float(n["log_loss"] - a["log_loss"]),
            "full_minus_no_price_brier_improvement": float(n["brier"] - a["brier"]),
        }
    return out
