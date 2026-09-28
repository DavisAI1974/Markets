"""CLM sidecar, step 2 (runs on the GPU Pod): learn from this Monday run's dataset and write outputs.

Standalone (Greg, 2026-09-28): a quick learner beside the run, not wired into Frankie/BOSS. Three methods per
question, all scored on the same held-out (later-in-the-day) rows:
  zero_shot   CLM-8B System One typed answer (clm-serve), probabilities over the question's choices
  zero_cal    the same probabilities with one temperature per question fitted on the train rows (calibration learned)
  head        a small softmax head trained on the train rows over frozen Qwen3-8B embeddings (the CLM recipe: frozen
              encoder, small learned projection)
  prior       the train-split majority choice (the named benchmark; a method that cannot beat it has learned nothing)
Outputs (per cell, counts not averages): predictions.jsonl.gz, report.md, summary.json.

    python learn.py --dataset dataset.jsonl.gz --out out/ [--emb-url http://127.0.0.1:8090/v1/embeddings]
"""
import argparse
import gzip
import json
import math
import time
import urllib.request
from pathlib import Path

import numpy as np

FILL_CLASSES = {
    'NO_FILL_IDS': 'no fill action carries an order id',
    'CANCEL': 'every filled id was also cancelled in the group',
    'MODIFY': 'every filled id was also modified in the group',
    'SPLIT_CANCEL_MODIFY': 'filled ids split between cancelled and modified',
    'SAME_ID_CANCEL_AND_MODIFY': 'some filled id was both cancelled and modified',
    'UNRESOLVED': 'filled ids neither cancelled nor modified',
}
MOVE = {'RISE': 'the mid price is higher', 'FALL': 'the mid price is lower', 'FLAT': 'the mid price is unchanged'}


def questions_for(name):
    """(instructions, {choice: description}) for one question; forecast questions are next_move_<h>s."""
    if name.startswith('next_move_'):
        h = name[len('next_move_'):]
        return ('NYMEX natural gas order book after this F_LAST group: %s later, compared with this group\'s mid, '
                'is the mid higher, lower or unchanged?' % h, MOVE)
    if name == 'mid_vs_previous':
        return ('Compare this group\'s book mid with the previous group\'s mid shown in the state.', MOVE)
    if name == 'deeper_side':
        return ('Which side of the full book has more resting depth in this state?',
                {'BID': 'bid depth is larger', 'ASK': 'ask depth is larger', 'EVEN': 'both sides are equal'})
    if name == 'fill_class':
        choices = dict(FILL_CLASSES)
        for k in list(FILL_CLASSES):
            if k not in ('NO_FILL_IDS', 'UNRESOLVED'):
                choices[k + '_WITH_UNRESOLVED'] = FILL_CLASSES[k] + ', and some filled ids were neither'
        return ('Classify this group\'s fill disposition from its filled, cancelled and modified order ids.', choices)
    raise KeyError(name)


def load(path):
    with gzip.open(path, 'rt', encoding='utf-8') as handle:
        return [json.loads(line) for line in handle]


# ---- CLM zero-shot ---------------------------------------------------------------------------------------------------

def _plain(obj):
    """A result object as plain JSON types, whatever the client returns (pydantic, dataclass, dict)."""
    for attr in ('model_dump', 'dict', 'to_dict'):
        if hasattr(obj, attr):
            try:
                return _plain(getattr(obj, attr)())
            except Exception:  # noqa: BLE001
                pass
    if isinstance(obj, dict):
        return {str(k): _plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_plain(v) for v in obj]
    if hasattr(obj, '__dict__'):
        return {k: _plain(v) for k, v in vars(obj).items() if not k.startswith('_')}
    return obj


def _choice_probs(node, choices):
    """Find the {choice: probability} mapping for this question anywhere in the node."""
    if isinstance(node, dict):
        if set(node) >= set(choices) and all(isinstance(node[c], (int, float)) for c in choices):
            return {c: float(node[c]) for c in choices}
        for v in node.values():
            found = _choice_probs(v, choices)
            if found:
                return found
    if isinstance(node, list):
        pairs = {}
        for item in node:
            if isinstance(item, dict):
                label = item.get('label') or item.get('choice') or item.get('value') or item.get('name')
                prob = item.get('probability', item.get('prob', item.get('score')))
                if label in choices and isinstance(prob, (int, float)):
                    pairs[label] = float(prob)
        if len(pairs) == len(choices):
            return pairs
        for item in node:
            found = _choice_probs(item, choices)
            if found:
                return found
    return None


def zero_shot(rows, names, raw_log):
    try:
        from clm import CLMClient, Choice
    except Exception as error:  # noqa: BLE001
        print('zero-shot unavailable: %s' % error, flush=True)
        return None
    client = CLMClient()
    out = []
    for n, row in enumerate(rows):
        qs = {}
        for q in names:
            if q in row['labels']:
                instructions, choices = questions_for(q)
                qs[q] = Choice(instructions=instructions, criteria=choices)
        if not qs:
            out.append({})
            continue
        try:
            result = _plain(client.system_one(state=row['state'], questions=qs))
        except Exception as error:  # noqa: BLE001
            if n < 3:
                print('zero-shot call failed: %s' % error, flush=True)
            out.append({})
            continue
        if n < 5:
            raw_log.append(result)
        probs = {}
        for q in qs:
            node = result.get(q, result) if isinstance(result, dict) else result
            found = _choice_probs(node, questions_for(q)[1])
            if found:
                total = sum(found.values()) or 1.0
                probs[q] = {c: v / total for c, v in found.items()}
        out.append(probs)
        if n % 250 == 0:
            print('zero-shot %d/%d' % (n, len(rows)), flush=True)
    return out


# ---- frozen-encoder embeddings and the learned head -----------------------------------------------------------------

def embed(texts, url, model, batch=32):
    vectors = []
    for start in range(0, len(texts), batch):
        body = json.dumps(dict(model=model, input=texts[start:start + batch])).encode()
        request = urllib.request.Request(url, body, {'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=600) as response:
            data = json.loads(response.read())['data']
        vectors.extend(item['embedding'] for item in sorted(data, key=lambda d: d['index']))
        if start % (batch * 20) == 0:
            print('embedded %d/%d' % (start + len(data), len(texts)), flush=True)
    return np.asarray(vectors, dtype=np.float32)


def fit_head(x, y, classes, steps=400, lr=0.05, l2=1e-3):
    """Softmax regression by full-batch Adam; x standardized by the caller."""
    k, d = len(classes), x.shape[1]
    w, b = np.zeros((d, k), np.float32), np.zeros(k, np.float32)
    onehot = np.eye(k, dtype=np.float32)[y]
    m = [np.zeros_like(w), np.zeros_like(b)]
    v = [np.zeros_like(w), np.zeros_like(b)]
    for t in range(1, steps + 1):
        z = x @ w + b
        z -= z.max(1, keepdims=True)
        p = np.exp(z)
        p /= p.sum(1, keepdims=True)
        g = (p - onehot) / len(x)
        grads = [x.T @ g + l2 * w, g.sum(0)]
        for i, (param, grad) in enumerate(zip((w, b), grads)):
            m[i] = 0.9 * m[i] + 0.1 * grad
            v[i] = 0.999 * v[i] + 0.001 * grad * grad
            param -= lr * (m[i] / (1 - 0.9 ** t)) / (np.sqrt(v[i] / (1 - 0.999 ** t)) + 1e-8)
    return w, b


def predict_head(x, w, b):
    z = x @ w + b
    z -= z.max(1, keepdims=True)
    p = np.exp(z)
    return p / p.sum(1, keepdims=True)


def fit_temperature(prob_rows, truths):
    """One temperature for the zero-shot probabilities, by grid search on the train rows' log loss."""
    best, best_t = None, 1.0
    for t in [0.25, 0.4, 0.55, 0.7, 0.85, 1.0, 1.25, 1.5, 2.0, 3.0, 5.0]:
        loss = 0.0
        for probs, truth in zip(prob_rows, truths):
            scaled = _temper(probs, t)
            loss -= math.log(max(scaled.get(truth, 0.0), 1e-9))
        if best is None or loss < best:
            best, best_t = loss, t
    return best_t


def _temper(probs, t):
    logits = {c: math.log(max(p, 1e-12)) / t for c, p in probs.items()}
    top = max(logits.values())
    ex = {c: math.exp(v - top) for c, v in logits.items()}
    s = sum(ex.values())
    return {c: v / s for c, v in ex.items()}


# ---- report (per cell, counts) ---------------------------------------------------------------------------------------

BINS = [(0.0, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01)]
THRESHOLDS = [0.5, 0.6, 0.7, 0.8, 0.9]


def report(preds, methods, meta):
    lines = ['# CLM sidecar report: %s' % meta['stamp'], '',
             'Standalone learner on this Monday run (not wired into Frankie/BOSS). Train = first 70%% of the day '
             '(purged of rows whose forecast window reaches the test part), test = the rest. Every number below is a '
             'count of held-out rows; no pooled score is the verdict. `prior` = the train majority choice (benchmark).',
             '', 'Encoder: %s. Zero-shot: %s.' % (meta['encoder'], meta['zero_shot']), '']
    summary = {}
    for q in sorted({p['question'] for p in preds}):
        rows = [p for p in preds if p['question'] == q]
        lines += ['## %s' % q, '', '| cell (session_phase) | n | ' + ' | '.join('%s hits' % m for m in methods) + ' |',
                  '|---|---|' + '---|' * len(methods)]
        cells = sorted({p['session_phase'] for p in rows}, key=str) + ['ALL']
        summary[q] = {}
        for cell in cells:
            sub = rows if cell == 'ALL' else [p for p in rows if p['session_phase'] == cell]
            hits = {m: sum(1 for p in sub if p.get(m) and max(p[m], key=p[m].get) == p['truth']) for m in methods}
            have = {m: sum(1 for p in sub if p.get(m)) for m in methods}
            lines.append('| %s | %d | %s |' % (cell, len(sub), ' | '.join('%d of %d' % (hits[m], have[m]) for m in methods)))
            summary[q][str(cell)] = dict(n=len(sub), hits=hits, scored=have)
        truth_counts = {}
        for p in rows:
            truth_counts[p['truth']] = truth_counts.get(p['truth'], 0) + 1
        lines += ['', 'Actual choices in the test rows: ' + ', '.join('%s %d' % kv for kv in sorted(truth_counts.items())), '']
        for m in methods:
            if m == 'prior' or not any(p.get(m) for p in rows):
                continue
            lines += ['Reliability, `%s` (confidence of the top choice; rows, of which right):' % m, '',
                      '| confidence | rows | right |', '|---|---|---|']
            for lo, hi in BINS:
                sub = [p for p in rows if p.get(m) and lo <= max(p[m].values()) < hi]
                right = sum(1 for p in sub if max(p[m], key=p[m].get) == p['truth'])
                lines.append('| %.1f-%.1f | %d | %d |' % (lo, min(hi, 1.0), len(sub), right))
            lines += ['', 'Accept when confident, escalate the rest (`%s`):' % m, '',
                      '| threshold | accepted | right among accepted | escalated |', '|---|---|---|---|']
            for t in THRESHOLDS:
                acc = [p for p in rows if p.get(m) and max(p[m].values()) >= t]
                right = sum(1 for p in acc if max(p[m], key=p[m].get) == p['truth'])
                lines.append('| %.1f | %d | %d | %d |' % (t, len(acc), right, len([p for p in rows if p.get(m)]) - len(acc)))
            lines.append('')
    return '\n'.join(lines) + '\n', summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--emb-url', default='http://127.0.0.1:8090/v1/embeddings')
    parser.add_argument('--emb-model', default='qwen3-8b')
    parser.add_argument('--stamp', default='')
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    data = load(args.dataset)
    train = [r for r in data if r['split'] == 'train']
    test = [r for r in data if r['split'] == 'test']
    names = sorted({q for r in data for q in r['labels']})
    print('dataset: %d train, %d test, questions %s' % (len(train), len(test), names), flush=True)

    raw = []
    zs_train, zs_test = zero_shot(train, names, raw), zero_shot(test, names, raw)
    (out / 'zero_shot_raw_examples.json').write_text(json.dumps(raw, indent=1, default=str))

    x_train = embed([r['state'] for r in train], args.emb_url, args.emb_model)
    x_test = embed([r['state'] for r in test], args.emb_url, args.emb_model)
    mu, sd = x_train.mean(0), x_train.std(0) + 1e-6
    x_train, x_test = (x_train - mu) / sd, (x_test - mu) / sd

    methods = ['prior', 'head'] + (['zero_shot', 'zero_cal'] if zs_test is not None else [])
    preds, temps = [], {}
    for q in names:
        tr = [(i, r) for i, r in enumerate(train) if q in r['labels']]
        te = [(i, r) for i, r in enumerate(test) if q in r['labels']]
        if not tr or not te:
            continue
        classes = sorted({r['labels'][q] for _, r in tr})
        counts = {c: sum(1 for _, r in tr if r['labels'][q] == c) for c in classes}
        majority = max(counts, key=counts.get)
        y = np.array([classes.index(r['labels'][q]) for _, r in tr])
        w, b = fit_head(x_train[[i for i, _ in tr]], y, classes)
        ph = predict_head(x_test[[i for i, _ in te]], w, b)
        if zs_test is not None:
            pairs = [(zs_train[i][q], r['labels'][q]) for i, r in tr if q in zs_train[i]]
            temps[q] = fit_temperature([p for p, _ in pairs], [t for _, t in pairs]) if pairs else 1.0
        for k, (i, r) in enumerate(te):
            p = dict(i=r['i'], ts_recv_ns=r['ts_recv_ns'], session_phase=r['session_phase'], question=q,
                     truth=r['labels'][q], prior={majority: 1.0},
                     head={c: float(ph[k, j]) for j, c in enumerate(classes)})
            if zs_test is not None and q in zs_test[i]:
                p['zero_shot'] = zs_test[i][q]
                p['zero_cal'] = _temper(zs_test[i][q], temps[q])
            preds.append(p)
    meta = dict(stamp=args.stamp, encoder='Qwen/Qwen3-8B (frozen, vLLM pooling)',
                zero_shot='CLM-8B via clm-serve' if zs_test is not None else 'unavailable (see pod log)')
    text, summary = report(preds, methods, meta)
    (out / 'report.md').write_text(text)
    (out / 'summary.json').write_text(json.dumps(dict(meta, temperatures=temps, seconds=round(time.time() - t0),
                                                      questions=summary), indent=1, sort_keys=True))
    with gzip.open(out / 'predictions.jsonl.gz', 'wt', encoding='utf-8') as handle:
        for p in preds:
            handle.write(json.dumps(p, sort_keys=True) + '\n')
    print('done in %.0f s' % (time.time() - t0), flush=True)


if __name__ == '__main__':
    main()
