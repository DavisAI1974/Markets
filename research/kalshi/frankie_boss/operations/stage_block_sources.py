"""Bring a multi-day block's raw MBO sources in: pinned copies on S3 and a hash-bound block manifest.

For each day file in the block: server-side copy from the archive prefix into the block's own S3
prefix, stream the bytes once to compute sha256 and size, decode the DBN in memory to count MBO
records and split them at the daily halt (17:00 ET = 21:00Z in October), and write a manifest in
the shape of the Sunday single-source manifest (member_index, member_key, sha256, size_bytes,
mbo_records) plus the per-file session split. manifest_hash is raw_mbo_source_manifest.manifest_hash
over the same canonical payload. Nothing is ingested, scheduled or run.

    python operations/stage_block_sources.py --block 20211004_20211006 --days 20211003 20211004 20211005 20211006
        --archive nymex/ng_mbo_5y_v0/native/2021-10 --out blocks/BLOCK_20211004_20211006_SOURCE_MANIFEST.json
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
ROOT = HERE.parents[2]
for entry in (str(ROOT), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from raw_mbo_source_manifest import manifest_hash  # noqa: E402

BUCKET = 'bento-568968024170-us-east-2-an'
SCHEMA = 'BOSS_BLOCK_SOURCE_MANIFEST_V1'
HALT_UTC_HOUR = 21   # CME Globex daily halt 17:00-18:00 ET; October is EDT, so 21:00Z


def load_env_file(path):
    for line in open(path, encoding='utf-8', errors='replace'):
        m = re.match(r'\s*(?:export\s+)?([A-Z_]+)\s*=\s*"?([^"\n]+)"?', line)
        if m and m.group(1).startswith('AWS_'):
            os.environ[m.group(1)] = m.group(2).strip()


def count_records(raw, day):
    import databento as db
    frame = db.DBNStore.from_bytes(raw).to_df(pretty_ts=False, map_symbols=False)
    ts = frame.index.astype('int64')
    halt = int(dt.datetime(int(day[:4]), int(day[4:6]), int(day[6:]), HALT_UTC_HOUR, tzinfo=dt.timezone.utc).timestamp() * 1e9)
    before = int((ts < halt).sum())
    flags = frame['flags'].astype(int).values
    # Seam checks (ingestion review 9.2/9.3): the builder refuses a member transition or a session
    # change inside an open group, and F_LAST (flag 0x80) closes a group. So the LAST record of every
    # day file must be F_LAST, and if the halt is a session boundary the last pre-halt record must be too.
    last_is_f_last = bool(flags[-1] & 0x80)
    halt_boundary_f_last = bool(flags[before - 1] & 0x80) if 0 < before < len(frame) else None
    f_last_groups = int((flags & 0x80).astype(bool).sum())
    return dict(mbo_records=int(len(frame)), before_halt=before, after_halt=int(len(frame)) - before,
                first_ts_recv_ns=int(ts.min()), last_ts_recv_ns=int(ts.max()),
                instruments=int(frame['instrument_id'].nunique()), f_last_groups=f_last_groups,
                last_record_f_last=last_is_f_last, halt_boundary_f_last=halt_boundary_f_last)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--block', required=True, help='block id, e.g. 20211004_20211006')
    parser.add_argument('--days', nargs='+', required=True, help='UTC day files in replay order')
    parser.add_argument('--archive', required=True, help='S3 prefix holding glbx-mdp3-<day>.mbo.dbn.zst')
    parser.add_argument('--bucket', default=BUCKET)
    parser.add_argument('--env-file', default=str(ROOT / 'scratchpad' / 'aws.env'))
    parser.add_argument('--out', required=True, help='manifest path, committed to git')
    args = parser.parse_args()
    if Path(args.env_file).is_file():
        load_env_file(args.env_file)
    import boto3
    s3 = boto3.client('s3', region_name='us-east-2')
    target_prefix = f'frankie/block_{args.block}/sources'
    sources, sessions = [], []
    for index, day in enumerate(args.days):
        name = f'glbx-mdp3-{day}.mbo.dbn.zst'
        source_key, target_key = f'{args.archive}/{name}', f'{target_prefix}/{name}'
        raw = s3.get_object(Bucket=args.bucket, Key=source_key)['Body'].read()
        sha = hashlib.sha256(raw).hexdigest()
        head = None
        try:
            head = s3.head_object(Bucket=args.bucket, Key=target_key)
        except s3.exceptions.ClientError:
            pass
        if head is None or head['ContentLength'] != len(raw):
            s3.copy_object(Bucket=args.bucket, Key=target_key, CopySource=dict(Bucket=args.bucket, Key=source_key),
                           MetadataDirective='REPLACE', Metadata={'sha256': sha, 'archive_key': source_key})
        copied = s3.get_object(Bucket=args.bucket, Key=target_key)['Body'].read()
        if hashlib.sha256(copied).hexdigest() != sha:
            raise SystemExit('block copy differs from archive bytes: ' + name)
        counts = count_records(raw, day)
        sources.append(dict(member_index=index, member_key=name, sha256=sha, size_bytes=len(raw),
                            mbo_records=counts['mbo_records']))
        sessions.append(dict(member_key=name, day_utc=day, **counts))
        print(json.dumps(dict(member=index, key=target_key, bytes=len(raw), sha256=sha[:16], **counts)), flush=True)
    seams_clean = all(x['last_record_f_last'] for x in sessions[:-1])
    halts_clean = all(x['halt_boundary_f_last'] in (True, None) for x in sessions)
    body = dict(schema=SCHEMA, source_kind='NATIVE_DBN_MBO', role='HELD_OUT_BLIND_BLOCK',
                member_seams_close_groups=seams_clean, halt_boundaries_close_groups=halts_clean,
                causal_clock='ts_recv_ns', sampled=False, canonical_source_rewritten=False,
                block=args.block, bucket=args.bucket, prefix=target_prefix, archive_prefix=args.archive,
                halt_utc_hour=HALT_UTC_HOUR, sources=sources, sessions=sessions,
                total_mbo_records=sum(s['mbo_records'] for s in sources),
                staged_unix=int(dt.datetime.now(dt.timezone.utc).timestamp()),
                ingested=False, scheduled=False, prefixes_built=False, model_calls=0)
    body['manifest_hash'] = manifest_hash(body)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(body, indent=1, sort_keys=True), encoding='utf-8')
    print(json.dumps(dict(status='block_sources_staged', manifest=str(out), manifest_hash=body['manifest_hash'],
                          total_mbo_records=body['total_mbo_records'])), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
