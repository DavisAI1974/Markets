"""The futures curve for the experiment's 30 days: every NG futures month, native DBN, to S3 (Greg, 2026-09-29: "do the
30 days immediately and get any other data that we have a gap on that we don't have a source for"; point 13 of
FRANKIE_DATA_WISHLIST_20260929 and HISTORICAL_DATA_PLAN_20260929.md).

The 5-year MBO pull is NG.v.0 (one instrument, the volume-leading month). This pulls the NG futures PARENT (NG.FUT,
stype parent: every listed month and the calendar spreads) for exactly the UTC partitions the 30 trading days need
(blocks/DAY_SELECTION_CANDIDATES_20260929.json proposed_partitions, 46 days), in three schemas:
  definition  the contract list per day (instrument id -> month, expiry);
  statistics  settlements, open interest, session high/low and the rest, each stamped with its own time;
  mbo         the full order book of every month, the same raw form as Frankie's front-month ingest.
Native compressed DBN is kept byte for byte (the 5-year pull's invariant); each object is uploaded with its sha256 and a
manifest. Before anything is bought the whole request is quoted per schema and refused above CEILING_USD. Each job id is
written to S3 before polling, so a rerun reuses it and never buys the same span twice. Nothing is converted, sampled or
dropped. Environment: DATABENTO_API_KEY, BUCKET, PREFIX, SCHEMAS (comma list), CEILING_USD, and either CANDIDATES
(the 30 days) or RANGES (comma list of UTC START:END ranges, END exclusive), Greg 2026-09-29: "do the 30 days first then do Oct for the 5
years and then do the other months for the 5 years that we don't already have"). A day whose native file for a schema is
already under PREFIX is skipped for that schema (never bought twice); spans never cross a month. QUOTE_ONLY=1 prints the
quotes and buys nothing.
"""
import datetime as dt
import glob
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path

import boto3
import databento as db

DATASET, SYMBOL, STYPE = 'GLBX.MDP3', 'NG.FUT', 'parent'


def env(name):
    value = os.environ.get(name)
    if not value:
        raise SystemExit('required environment variable unavailable: %s' % name)
    return value


def ranges(days):
    """Contiguous [start, end) date spans covering exactly the given UTC partition days, never crossing a month."""
    days = sorted(dt.date(int(d[:4]), int(d[4:6]), int(d[6:])) for d in days)
    if not days:
        return []
    spans, start, prev = [], days[0], days[0]
    for d in days[1:]:
        if d != prev + dt.timedelta(days=1) or d.month != prev.month:
            spans.append((start, prev + dt.timedelta(days=1)))
            start = d
        prev = d
    spans.append((start, prev + dt.timedelta(days=1)))
    return spans


def main():
    key, bucket, prefix = env('DATABENTO_API_KEY'), env('BUCKET'), env('PREFIX').strip('/')
    schemas = [s.strip() for s in env('SCHEMAS').split(',') if s.strip()]
    ceiling = float(env('CEILING_USD'))
    quote_only = os.environ.get('QUOTE_ONLY') == '1'
    if os.environ.get('CANDIDATES'):
        candidates = json.loads(Path(os.environ['CANDIDATES']).read_bytes())
        wanted = sorted({p['partition'] for p in candidates['proposed_partitions']})
    else:
        wanted = set()
        for part in env('RANGES').split(','):
            a, b = (dt.date.fromisoformat(x) for x in part.split(':'))
            wanted.update((a + dt.timedelta(days=i)).strftime('%Y%m%d') for i in range((b - a).days))
        wanted = sorted(wanted)
    s3 = boto3.client('s3', region_name=os.environ.get('AWS_DEFAULT_REGION'))
    client = db.Historical(key)
    held = {}
    for schema in schemas:
        names = set()
        for page in s3.get_paginator('list_objects_v2').paginate(Bucket=bucket, Prefix='%s/%s/native/' % (prefix, schema)):
            names.update(o['Key'].rsplit('/', 1)[-1] for o in page.get('Contents', []))
        held[schema] = {d for d in wanted if 'glbx-mdp3-%s.%s.dbn.zst' % (d, schema) in names}
    plan = {schema: ranges([d for d in wanted if d not in held[schema]]) for schema in schemas}
    for schema in schemas:
        print('[plan] %s: %d days wanted, %d already held (skipped), %d spans to buy' % (
            schema, len(wanted), len(held[schema]), len(plan[schema])), flush=True)

    def exists(name):
        try:
            s3.head_object(Bucket=bucket, Key=name)
            return True
        except Exception as exc:
            r = getattr(exc, 'response', {})
            if str(r.get('Error', {}).get('Code')) in {'404', 'NoSuchKey', 'NotFound'} or \
                    r.get('ResponseMetadata', {}).get('HTTPStatusCode') == 404:
                return False
            raise

    def put_json(name, obj):
        s3.put_object(Bucket=bucket, Key=name, Body=(json.dumps(obj, indent=2, sort_keys=True) + '\n').encode(),
                      ContentType='application/json')

    quotes = {}
    for schema in schemas:
        quotes[schema] = [float(client.metadata.get_cost(dataset=DATASET, symbols=[SYMBOL], stype_in=STYPE, schema=schema,
                                                          start=a.isoformat(), end=b.isoformat())) for a, b in plan[schema]]
        print('[quote] %s $%.4f' % (schema, sum(quotes[schema])), flush=True)
    total = sum(sum(q) for q in quotes.values())
    print('[quote] total $%.4f ceiling $%.2f' % (total, ceiling), flush=True)
    Path('/tmp/curve-days-receipt.json').write_text(json.dumps(dict(quote_only=quote_only, quotes_usd=quotes,
                                                                     total_quote_usd=total, ceiling_usd=ceiling), indent=1))
    if quote_only:
        print('[quote-only] nothing bought', flush=True)
        return
    if total > ceiling:
        raise SystemExit('total quote $%.4f exceeds the ceiling $%.2f; nothing bought' % (total, ceiling))

    receipt = dict(schema='FRANKIE_CURVE_DAYS_PULL_V1', dataset=DATASET, symbol=SYMBOL, stype_in=STYPE, schemas=schemas,
                   partitions_wanted=wanted, already_held={k: sorted(v) for k, v in held.items()},
                   spans={k: [[a.isoformat(), b.isoformat()] for a, b in v] for k, v in plan.items()}, quotes_usd=quotes,
                   total_quote_usd=total, ceiling_usd=ceiling, native_dbn_preserved=True, results=[])
    for schema in schemas:
        for (a, b), quote in zip(plan[schema], quotes[schema]):
            seg = '%s_%s' % (a.strftime('%Y%m%d'), b.strftime('%Y%m%d'))
            base = '%s/%s' % (prefix, schema)
            done, job_key, manifest_key = ('%s/_done/%s.done' % (base, seg), '%s/_jobs/%s.json' % (base, seg),
                                           '%s/manifests/%s.json' % (base, seg))
            if exists(done) and exists(manifest_key):
                print('[resume] %s %s already complete' % (schema, seg), flush=True)
                receipt['results'].append(dict(schema=schema, segment=seg, status='already_complete'))
                continue
            if exists(job_key):
                jid = json.loads(s3.get_object(Bucket=bucket, Key=job_key)['Body'].read())['job_id']
                print('[resume] %s %s reuse job %s' % (schema, seg, jid), flush=True)
            else:
                job = client.batch.submit_job(dataset=DATASET, symbols=[SYMBOL], stype_in=STYPE, schema=schema,
                                              start=a.isoformat(), end=b.isoformat(), encoding='dbn', compression='zstd',
                                              split_duration='day')
                jid = job.get('id')
                if not jid:
                    raise RuntimeError('no job id for %s %s: %s' % (schema, seg, job))
                put_json(job_key, dict(job_id=jid, schema=schema, segment=seg, start=a.isoformat(), end=b.isoformat(),
                                       quote_usd=quote, symbol=SYMBOL, stype_in=STYPE, dataset=DATASET,
                                       submitted_at_utc=dt.datetime.now(dt.timezone.utc).isoformat()))
                print('[submit] %s %s job=%s quote=$%.4f' % (schema, seg, jid, quote), flush=True)
            deadline = time.time() + 4.5 * 3600
            while True:
                state = client.batch.get_job_details(jid).get('state')
                print('[poll] %s %s job=%s state=%s' % (schema, seg, jid, state), flush=True)
                if state == 'done':
                    break
                if state in {'failed', 'expired'}:
                    raise RuntimeError('%s %s job %s state=%s' % (schema, seg, jid, state))
                if time.time() > deadline:
                    raise RuntimeError('%s %s job %s polling deadline; a rerun reuses the saved job id' % (schema, seg, jid))
                time.sleep(20)
            with tempfile.TemporaryDirectory(prefix='ngfut_') as tmp:
                client.batch.download(jid, output_dir=tmp)
                files = sorted(glob.glob(os.path.join(tmp, '**', '*.dbn.zst'), recursive=True))
                if not files:
                    raise RuntimeError('%s %s job %s: no .dbn.zst downloaded' % (schema, seg, jid))
                entries = []
                for f in files:
                    path = Path(f)
                    h, size = hashlib.sha256(), 0
                    with path.open('rb') as fh:
                        for chunk in iter(lambda: fh.read(8 * 1024 * 1024), b''):
                            h.update(chunk)
                            size += len(chunk)
                    obj = '%s/native/%s' % (base, path.name)
                    s3.upload_file(str(path), bucket, obj, ExtraArgs=dict(Metadata=dict(sha256=h.hexdigest(), job_id=jid)))
                    entries.append(dict(key=obj, bytes=size, sha256=h.hexdigest()))
                    print('[upload] %s %d bytes %s' % (obj, size, h.hexdigest()), flush=True)
            put_json(manifest_key, dict(schema=schema, segment=seg, job_id=jid, quote_usd=quote, objects=entries))
            s3.put_object(Bucket=bucket, Key=done, Body=b'done\n')
            receipt['results'].append(dict(schema=schema, segment=seg, job_id=jid, objects=len(entries),
                                           bytes=sum(e['bytes'] for e in entries)))
    put_json('%s/receipts/%s.json' % (prefix, dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')), receipt)
    Path('/tmp/curve-days-receipt.json').write_text(json.dumps(receipt, indent=1, sort_keys=True))
    print('[done] %d segment results' % len(receipt['results']), flush=True)


if __name__ == '__main__':
    main()
