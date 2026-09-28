# CLM sidecar, step 1 of 2 (read-only on the run): build the sidecar's dataset from this Monday run's finished
# sources.sqlite (the bedrock member rows, one per F_LAST group) and upload it for the GPU Pod. Standalone: stdlib +
# boto3 only, imports nothing from the Frankie/BOSS runtime, writes only under /opt/frankie-box/work/clm-sidecar/.
# Greg 2026-09-28: a quick stand-alone learner, not wired into anything. See research/kalshi/frankie_boss/clm_sidecar/.
# Inputs (all optional): SOURCES (sources.sqlite path), HORIZONS (seconds, comma list, default 60,300),
# TRAIN (default 3000), TEST (default 1500), STAMP (run name, default UTC time).
set -eu
export SOURCES="${SOURCES:-/opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48/work/derived/.digest-109f959829b14b169fd6b98d69fc3125/calculation-layers/sources.sqlite}"
export HORIZONS="${HORIZONS:-60,300}" TRAIN="${TRAIN:-3000}" TEST="${TEST:-1500}" STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
exec nice -n 10 /usr/bin/python3 -B - <<'PY'
import bisect, gzip, hashlib, json, os, random, sqlite3, sys, time, zlib
from pathlib import Path

SOURCES, STAMP = os.environ['SOURCES'], os.environ['STAMP']
HORIZONS = [int(h) for h in os.environ['HORIZONS'].split(',') if h.strip()]
N_TRAIN, N_TEST = int(os.environ['TRAIN']), int(os.environ['TEST'])
OUT = Path('/opt/frankie-box/work/clm-sidecar') / STAMP
OUT.mkdir(parents=True, exist_ok=False)
BUCKET, REGION = 'frankie-granite42-568968024170-us-east-1', 'us-east-1'
# the box role writes nothing in S3 (measured 2026-09-28: both prefixes refused); these attempts are kept, and
# frankie_box_clm_sidecar_upload.sh uploads through a presigned PUT the runner signs
KEYS = ['host-deliveries/%s/principal-response/cycle-00/progress/clm-sidecar/%s/dataset.jsonl.gz' % (day, STAMP)
        for day in ('20211004', '20211003')]
# The columns the state is rendered from (the whole ask ladder and the FIFO queues are never read).
KEEP = ('ts_recv_ns', 'session_phase', 'structure.action_string', 'structure.side_string',
        'structure.distinct_order_id_count', 'structure.price_raw_span', 'structure.fill_disposition',
        'structure.fill_disposition.class', 'structure.fill_disposition.filled_order_ids',
        'book_full.best_bid', 'book_full.best_ask', 'book_full.mid', 'book_full.spread',
        'book_full.depth_imbalance_full', 'book_full.bid_depth_full', 'book_full.ask_depth_full',
        'book_full.bid_order_count_full', 'book_full.ask_order_count_full',
        'book_full.bid_price_level_count_full', 'book_full.ask_price_level_count_full',
        'activity_since.*.event_count', 'activity_since.*.trade_buy_aggressor_qty',
        'activity_since.*.trade_sell_aggressor_qty', 'activity_since.*.trade_aggressor_imbalance',
        'activity_since.*.add_cancel_churn')
t0 = time.time()
db = sqlite3.connect(Path(SOURCES).resolve().as_uri() + '?mode=ro', uri=True)
db.execute('PRAGMA cache_size=-1048576')
# group order: the digest's group_order collation (the JSON group value, None last), rebuilt here without the runtime
order = sorted(((json.loads(v), k) for k, v in db.execute('SELECT key, value FROM groups')),
               key=lambda x: (x[0] is None, x[0]))
index = {k: i for i, (_, k) in enumerate(order)}
rows = [dict() for _ in order]
marks = ','.join('?' * len(KEEP))
for key, column, payload in db.execute('SELECT group_key, column_name, payload FROM members WHERE column_name IN (%s)'
                                       % marks, KEEP):
    i = index.get(key)
    if i is not None:
        rows[i][column] = json.loads(zlib.decompress(payload) if isinstance(payload, bytes) else payload)
db.close()
n = len(rows)
print('read %d groups in %.0f s' % (n, time.time() - t0), flush=True)

def num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None

ts = [num(r.get('ts_recv_ns')) for r in rows]
mid = [num(r.get('book_full.mid')) for r in rows]

def fmt(v):
    if isinstance(v, float):
        return ('%.6g' % v)
    if isinstance(v, (list, tuple)):
        return '[' + ', '.join(fmt(x) for x in v[:12]) + (', ...%d more' % (len(v) - 12) if len(v) > 12 else '') + ']'
    if isinstance(v, dict):
        return '{' + ', '.join('%s: %s' % (k, fmt(x)) for k, x in v.items()) + '}'
    return str(v)

def state_at(i, rows):
    """The sidecar's state for group i: group i's row and the previous group's mid only (never a later row)."""
    r = rows[i]
    prev = rows[i - 1] if i else {}
    lines = ['session_phase: %s' % r.get('session_phase'),
             'actions: %s  sides: %s  distinct_orders: %s  price_raw_span: %s' % (
                 str(r.get('structure.action_string'))[:80], str(r.get('structure.side_string'))[:80],
                 r.get('structure.distinct_order_id_count'), r.get('structure.price_raw_span')),
             'book: best_bid %s best_ask %s mid %s spread %s' % tuple(fmt(r.get('book_full.' + c)) for c in ('best_bid', 'best_ask', 'mid', 'spread')),
             'previous group mid: %s' % fmt(prev.get('book_full.mid')),
             'depth: bid %s ask %s imbalance %s; orders bid %s ask %s; levels bid %s ask %s' % tuple(fmt(r.get('book_full.' + c)) for c in (
                 'bid_depth_full', 'ask_depth_full', 'depth_imbalance_full', 'bid_order_count_full', 'ask_order_count_full',
                 'bid_price_level_count_full', 'ask_price_level_count_full'))]
    fd = r.get('structure.fill_disposition')
    if isinstance(fd, dict):   # the class itself is the classroom answer: shown without it
        lines.append('fill disposition: %s' % fmt({k: v for k, v in fd.items() if k != 'class'}))
    for c in ('event_count', 'trade_buy_aggressor_qty', 'trade_sell_aggressor_qty', 'trade_aggressor_imbalance', 'add_cancel_churn'):
        v = r.get('activity_since.*.' + c)
        if v is not None:
            lines.append('activity since anchors, %s: %s' % (c, fmt(v)))
    return '\n'.join(lines)

def direction(a, b):
    if a is None or b is None:
        return None
    return 'RISE' if b > a else 'FALL' if b < a else 'FLAT'

def labels_at(i):
    r = rows[i]
    out = {}
    for h in HORIZONS:        # forecast: the mid of the first group at or after ts + h, against this group's mid
        if ts[i] is not None:
            j = bisect.bisect_left(ts, ts[i] + h * 10**9, lo=i + 1) if all_sorted else None
            if j is not None and j < n:
                out['next_move_%ds' % h] = direction(mid[i], mid[j])
    fd = r.get('structure.fill_disposition')
    cls = r.get('structure.fill_disposition.class') or (fd.get('class') if isinstance(fd, dict) else None)
    if cls is not None:
        out['fill_class'] = cls
    b, a = num(r.get('book_full.bid_depth_full')), num(r.get('book_full.ask_depth_full'))
    if b is not None and a is not None:
        out['deeper_side'] = 'BID' if b > a else 'ASK' if a > b else 'EVEN'
    out['mid_vs_previous'] = direction(num(rows[i - 1].get('book_full.mid')) if i else None, mid[i])
    return {k: v for k, v in out.items() if v is not None}

all_sorted = all(ts[k] is not None for k in range(n)) and all(ts[k] <= ts[k + 1] for k in range(n - 1))
print('receive clock monotone: %s' % all_sorted, flush=True)
# time-ordered split: learn on the first 70% of the day, score on the last 30%; the purge drops the train rows whose
# forecast window reaches into the scored part (no label overlap across the boundary)
cut = int(n * 0.7)
purge = max(HORIZONS) * 10**9
train_idx = [i for i in range(1, cut) if ts[i] is not None and ts[cut] is not None and ts[i] + purge < ts[cut]]
test_idx = list(range(cut, n))
rng = random.Random(20211004)
train = sorted(rng.sample(train_idx, min(N_TRAIN, len(train_idx))))
test = sorted(rng.sample(test_idx, min(N_TEST, len(test_idx))))

# leakage check (odcore/leakage.py's rule, applied to the state): the state at i must not change when every row
# after i is scrambled
leaks = 0
for i in rng.sample(train + test, min(200, len(train) + len(test))):
    s0 = state_at(i, rows)
    tail = rows[i + 1:]
    scrambled = rows[:i + 1] + rng.sample(tail, len(tail))
    if state_at(i, scrambled) != s0:
        leaks += 1
if leaks:
    raise SystemExit('leakage check FAILED: %d states changed when later rows were scrambled' % leaks)
print('leakage check passed (200 states invariant to scrambling every later row)', flush=True)

path = OUT / 'dataset.jsonl.gz'
counts = {}
with gzip.open(path, 'wt', encoding='utf-8') as handle:
    for split, idxs in (('train', train), ('test', test)):
        for i in idxs:
            lab = labels_at(i)
            for q, v in lab.items():
                counts.setdefault(split, {}).setdefault(q, {}).setdefault(v, 0)
                counts[split][q][v] += 1
            handle.write(json.dumps(dict(split=split, i=i, ts_recv_ns=ts[i], session_phase=rows[i].get('session_phase'),
                                         state=state_at(i, rows), labels=lab), sort_keys=True) + '\n')
digest = hashlib.sha256(path.read_bytes()).hexdigest()
manifest = dict(schema='CLM_SIDECAR_DATASET_V1', stamp=STAMP, sources=SOURCES, groups=n, horizons_s=HORIZONS,
                split_row=cut, purge_ns=purge, train=len(train), test=len(test), label_counts=counts,
                leakage_check='passed', bytes=path.stat().st_size, sha256=digest, s3=dict(bucket=BUCKET, key=None))
(OUT / 'manifest.json').write_text(json.dumps(manifest, indent=1, sort_keys=True))
manifest['uploaded'], errors = False, []
try:
    import boto3
    s3 = boto3.client('s3', region_name=REGION)
    for key in KEYS:
        try:
            s3.upload_file(str(path), BUCKET, key, ExtraArgs={'Metadata': {'sha256': digest}})
            manifest['uploaded'], manifest['s3']['key'] = True, key
            break
        except Exception as error:   # noqa: BLE001 - try the next granted prefix
            errors.append('%s: %s' % (key, str(error)[:200]))
except Exception as error:   # noqa: BLE001 - the dataset stays on the box either way
    errors.append('%s: %s' % (type(error).__name__, str(error)[:200]))
if errors:
    manifest['upload_errors'] = errors
(OUT / 'manifest.json').write_text(json.dumps(manifest, indent=1, sort_keys=True))
print(json.dumps(manifest, sort_keys=True))
PY
