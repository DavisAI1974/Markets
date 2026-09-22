# The FRIDAY ANCHOR (Greg, 2026-09-22: "get the proper value to anchor the last trade on fri so frankie knows where to
# start"): the last trade before the 17:00 ET (21:00Z) halt on Friday 2021-10-01, from the 5-year native archive's own
# Friday file, decoded on the box with the same databento-dbn the ingest uses. Read-only on S3 (a presigned GET through
# MAP_URL; the box's role reads nothing), no model call, nothing deleted; the file stays under data/anchor/ and the
# result is receipted under receipts/. Inputs: MAP_URL (frankie_box_run.yml presign=<bucket>/<key>), INSTRUMENT
# (the roster instrument id; cycle 0's entity is (1, 111313)).
set -u
[ -n "${MAP_URL:-}" ] || { echo "MAP_URL not set (dispatch frankie_box_run.yml with presign=bento-568968024170-us-east-2-an/nymex/ng_mbo_5y_v0/native/20211001_20211101/glbx-mdp3-20211001.mbo.dbn.zst)"; exit 2; }
ROOT=/opt/frankie-box; INSTRUMENT="${INSTRUMENT:-111313}"
mkdir -p "$ROOT/data/anchor" "$ROOT/receipts" "$ROOT/tmp"
cd "$ROOT/tmp" || exit 2
curl -fsS -m 60 --retry 3 -o anchor-map.json "$MAP_URL" || { echo "map download failed"; exit 2; }
[ -x "$ROOT/venv/bin/python" ] || { echo "venv not staged (databento-dbn lives in the box venv)"; exit 2; }
export ROOT INSTRUMENT
"$ROOT/venv/bin/python" - <<'PY'
import hashlib, json, os, subprocess, sys, time
from datetime import datetime, timezone
root = os.environ['ROOT']; instrument = int(os.environ['INSTRUMENT'])
# the Friday object, pinned in git (NG_EXHAUSTION_OCTOBER_FRANKIE_BLIND_CANARY_LAUNCH_20260824.json target_object)
KEY_SUFFIX = 'native/20211001_20211101/glbx-mdp3-20211001.mbo.dbn.zst'
WANT_BYTES, WANT_SHA = 25628861, 'e6b4ec01bd9b34d57cb22c770b5d49c756e7f41a658f081823d923004a0121b2'
HALT = datetime(2021, 10, 1, 21, 0, tzinfo=timezone.utc)           # Friday 17:00 ET under EDT = the CME halt
HALT_NS = int(HALT.timestamp()) * 1_000_000_000
def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 22), b''): h.update(block)
    return h.hexdigest()
m = json.load(open('anchor-map.json'))
key = next((k for k in m if k.endswith(KEY_SUFFIX)), None)
if key is None: raise SystemExit('the map carries no Friday object (' + KEY_SUFFIX + '); refused')
entry = m[key]
if entry.get('bytes') != WANT_BYTES: raise SystemExit(f'bytes differ from the pin: have {entry.get("bytes")} want {WANT_BYTES}; refused')
dest = os.path.join(root, 'data', 'anchor', 'glbx-mdp3-20211001.mbo.dbn.zst')
if os.path.exists(dest):
    have = sha(dest)
    if have != WANT_SHA: raise SystemExit('a different file is already at ' + dest + '; not overwritten (move it aside with a receipt first)')
    print('present', dest)
else:
    part = dest + '.part'; t0 = time.time()
    r = subprocess.run(['curl', '-fsS', '-L', '--retry', '5', '--retry-delay', '5', '-C', '-', '-o', part, entry['url']])
    if r.returncode != 0: raise SystemExit(f'download failed ({r.returncode})')
    got = sha(part)
    if os.path.getsize(part) != WANT_BYTES or got != WANT_SHA:
        os.replace(part, part + f'.rejected-{int(time.time())}'); raise SystemExit(f'digest differs from the pin: {got}; refused')
    os.replace(part, dest); print(f'restored {dest} {WANT_BYTES} bytes in {time.time()-t0:.0f}s')
import databento_dbn as dbn, zstandard
from importlib.metadata import version
versions = dict(databento_dbn=version('databento-dbn'), zstandard=version('zstandard'))
decoder = dbn.DBNDecoder()          # metadata first, then records, from the decompressed stream
last_before_halt, last_any, counts_last_hour, trades_total, records_total = {}, {}, {}, 0, 0
kinds = {}
with open(dest, 'rb') as f:
    reader = zstandard.ZstdDecompressor().stream_reader(f)
    while True:
        chunk = reader.read(1 << 20)
        if not chunk: break
        decoder.write(chunk)
        for rec in decoder.decode():
            records_total += 1
            if type(rec) is not dbn.MBOMsg:
                kinds[type(rec).__name__] = kinds.get(type(rec).__name__, 0) + 1; continue
            if str(rec.action) != 'T': continue
            trades_total += 1
            row = dict(instrument_id=rec.instrument_id, ts_event=rec.ts_event, ts_recv=rec.ts_recv, price_raw=rec.price,
                       price=rec.price / 1e9, size=rec.size, side=str(rec.side), sequence=rec.sequence, order_id=rec.order_id)
            last_any[rec.instrument_id] = row
            if rec.ts_recv < HALT_NS:
                last_before_halt[rec.instrument_id] = row
                if rec.ts_recv >= HALT_NS - 3600 * 1_000_000_000:
                    counts_last_hour[rec.instrument_id] = counts_last_hour.get(rec.instrument_id, 0) + 1
def iso(ns): return datetime.fromtimestamp(ns / 1e9, tz=timezone.utc).isoformat()
def show(row): return dict(row, ts_event_iso=iso(row['ts_event']), ts_recv_iso=iso(row['ts_recv']))
anchor = last_before_halt.get(instrument)
top = sorted(counts_last_hour.items(), key=lambda kv: -kv[1])[:8]
result = dict(schema='FRANKIE_FRIDAY_ANCHOR_V1', at=time.time(), file=dict(key=key, bytes=WANT_BYTES, sha256=WANT_SHA), versions=versions,
              halt_utc=HALT.isoformat(), halt_ns=HALT_NS, instrument=instrument, records_total=records_total, trades_total=trades_total,
              non_mbo_records=kinds, anchor=show(anchor) if anchor else None,
              last_trade_any_time=show(last_any[instrument]) if instrument in last_any else None,
              last_hour_by_instrument=[dict(instrument_id=i, trades_last_hour=n, last_before_halt=show(last_before_halt[i])) for i, n in top],
              rule='the anchor is the last MBO trade (action T) with ts_recv before the 21:00Z Friday halt for the roster instrument; nothing averaged, nothing derived')
name = os.path.join(root, 'receipts', f'friday-anchor-{int(time.time())}.json')
with open(name, 'w') as f: json.dump(result, f, indent=1, sort_keys=True)
print('RECEIPT', name)
print('### FRIDAY ANCHOR', 'instrument', instrument, 'halt', HALT.isoformat())
print(json.dumps(result['anchor'], sort_keys=True))
print('### last trade of the file for the instrument (any time)'); print(json.dumps(result['last_trade_any_time'], sort_keys=True))
print('### last hour before the halt, by instrument (trade counts; the front is the busiest)')
for row in result['last_hour_by_instrument']: print(json.dumps(row, sort_keys=True))
print('records', records_total, 'trades', trades_total, 'other record kinds', kinds, 'versions', versions)
PY
code=$?
rm -f "$ROOT/tmp/anchor-map.json"
exit $code
