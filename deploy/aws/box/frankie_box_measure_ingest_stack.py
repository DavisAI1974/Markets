"""Measure the DIGEST_V5 table transforms stacked ON TOP OF the current ingest block codec (Greg, 2026-09-23).

Read-only against the sealed Monday container (SQLite opened immutable: no lock, no sidecar). For each sampled
block: decode it with the pinned codec (every entry's digest verified), keep that codec's own exact order
dictionary, render the records and the dictionary as DIGEST_V5 tables, gzip at the codec's level, then parse the
tables back and rebuild every entry byte-exact (canonical body and sha256 digest). A block that does not rebuild
exactly is counted and reported, never scored. Per-block numbers are written, never only an average.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys
import time

REPOSITORY = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPOSITORY))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from frankie_box_digest_render import SCHEMA as DIGEST_SCHEMA, parse_table, render_table  # noqa: E402
from research.kalshi.frankie_boss.c15_journal import pack, unpack  # noqa: E402
from research.kalshi.frankie_boss.compact_journal import FORMAT, _orders, decode_block  # noqa: E402
from research.kalshi.frankie_boss.verified_journal_reader import DIGEST_PREFIX, canonical_tagged_bytes  # noqa: E402

CONTAINER = '/opt/frankie-box/work/ingest-20211004-ingest-1790057801/journal.compact.sqlite'
OUTPUT_PARENT = Path('/opt/frankie-box/work/ingest-stack-measure')
BYTES, TUPLE = '$b', '$t'


def encode(value):
    """Table-safe exact form: bytes -> {'$b': hex}; every tuple -> {'$t': [...]}; the rest unchanged."""
    if type(value) is bytes:
        return {BYTES: value.hex()}
    if type(value) is dict:
        if BYTES in value or TUPLE in value:
            raise ValueError('reserved marker key present in data')
        return {k: encode(v) for k, v in value.items()}
    if type(value) is tuple:
        return {TUPLE: [encode(v) for v in value]}
    if type(value) is list:
        return [encode(v) for v in value]
    return value


def decode(value):
    if type(value) is dict:
        if set(value) == {BYTES}:
            return bytes.fromhex(value[BYTES])
        if set(value) == {TUPLE}:
            return tuple(decode(v) for v in value[TUPLE])
        return {k: decode(v) for k, v in value.items()}
    if type(value) is list:
        return [decode(v) for v in value]
    if type(value) is tuple:
        return tuple(decode(v) for v in value)
    return value


def reorder(value, template):
    """Restore the stored key order (it is part of the canonical bytes) from the flattened column order."""
    if type(value) is dict and type(template) is dict:
        return {k: reorder(value[k], template[k]) for k in template}
    if type(value) in (list, tuple) and type(template) is type(value) and len(value) == len(template):
        return type(value)(reorder(v, t) for v, t in zip(value, template))
    return value


def stacked(rows):
    """The codec's own split (order dictionary + records with orders removed), then DIGEST_V5 tables, then gzip."""
    dictionary, lookup, records, trees = [], {}, [], []
    for ordinal, kind, body, digest in rows:
        tree = json.loads(body)
        orders, indices = _orders(tree), None
        if orders is not None:
            indices = []
            for order in orders[1]:
                key = repr(order)
                if key not in lookup:
                    lookup[key] = len(dictionary)
                    dictionary.append(order)
                indices.append(lookup[key])
            orders[1] = []
        payload = unpack(tree)
        records.append(dict(ordinal=ordinal, kind=kind, digest=digest, size=len(body),
                            order_refs=indices if indices else ([] if indices is not None else None),
                            entry=encode(payload)))
        trees.append(payload)
    tables = {'records': records, 'orders': [dict(order=encode(unpack(o))) for o in dictionary]}
    text = ''.join(render_table(name, value) for name, value in tables.items() if value)
    return text, dictionary, trees


def rebuild(text, rows, templates):
    """Parse the tables back and rebuild every entry; True only if every body and digest is byte-exact."""
    blocks = re.split(r'(?m)^(?=### table )', text)
    parsed = {}
    for block in blocks:
        if block:
            name, value = parse_table(block)
            parsed[name] = value
    orders = [pack(decode(o['order'])) for o in parsed.get('orders', [])]
    for (ordinal, kind, body, digest), record, template in zip(rows, parsed['records'], templates):
        payload = reorder(decode(record['entry']), template)
        tree = pack(payload)
        refs = record.get('order_refs')
        if refs is not None:
            target = _orders(tree)
            if target is None:
                return False
            target[1] = [orders[i] for i in refs]
        raw = canonical_tagged_bytes(tree)
        if (record['ordinal'], record['kind'], record['digest'], record['size']) != (ordinal, kind, digest, len(body)):
            return False
        if raw != body or hashlib.sha256(DIGEST_PREFIX + raw).hexdigest() != digest:
            return False
    return len(parsed['records']) == len(rows)


def measure(output, samples):
    output = Path(output)
    if output.parent != OUTPUT_PARENT or not re.fullmatch('[A-Za-z0-9_-]{1,96}', output.name) or output.exists():
        raise ValueError('fresh named output under ' + str(OUTPUT_PARENT))
    OUTPUT_PARENT.mkdir(parents=True, exist_ok=True)
    output.mkdir(mode=0o700)
    db = sqlite3.connect('file:%s?mode=ro&immutable=1' % CONTAINER, uri=True)
    starts = [r[0] for r in db.execute('SELECT start FROM blocks ORDER BY start')]
    total_blob = db.execute('SELECT SUM(LENGTH(body)), SUM(count) FROM blocks').fetchone()
    stride = max(1, len(starts) // samples)
    chosen = starts[::stride]
    per_block, started = [], time.time()
    with (output/'per-block.jsonl').open('x') as sink:
        for start in chosen:
            count, blob = db.execute('SELECT count, body FROM blocks WHERE start=?', (start,)).fetchone()
            rows = decode_block(blob)
            plain = sum(len(r[2]) for r in rows)
            try:
                text, dictionary, templates = stacked(rows)
                exact = rebuild(text, rows, templates)
                error = None
            except Exception as err:  # reported per block, never scored
                text, dictionary, exact, error = '', [], False, '%s: %s' % (type(err).__name__, str(err)[:200])
            stacked_gz = len(gzip.compress(text.encode(), 6, mtime=0)) if text else None
            item = dict(start=start, entries=count, plain_bytes=plain, current_block_bytes=len(blob),
                        order_dictionary=len(dictionary), table_bytes=len(text.encode()) if text else None,
                        stacked_gzip_bytes=stacked_gz, exact=exact, error=error,
                        gain_over_current=(round(len(blob) / stacked_gz, 4) if exact and stacked_gz else None))
            sink.write(json.dumps(item, sort_keys=True) + '\n')
            per_block.append(item)
    exact = [b for b in per_block if b['exact']]
    gains = sorted(b['gain_over_current'] for b in exact)
    q = lambda p: gains[min(len(gains) - 1, int(p * len(gains)))] if gains else None
    summary = dict(schema='FRANKIE_INGEST_STACK_MEASURE_V1', digest_schema=DIGEST_SCHEMA, codec=FORMAT,
        container=CONTAINER, container_blocks=len(starts), container_entries=total_blob[1],
        container_block_bytes=total_blob[0], sampled_blocks=len(per_block), stride=stride,
        exact_blocks=len(exact), inexact_blocks=len(per_block) - len(exact),
        sampled_current_bytes=sum(b['current_block_bytes'] for b in exact),
        sampled_stacked_bytes=sum(b['stacked_gzip_bytes'] for b in exact),
        sampled_plain_bytes=sum(b['plain_bytes'] for b in exact),
        gain_distribution=dict(min=q(0), p10=q(0.1), p50=q(0.5), p90=q(0.9), max=q(0.999999)),
        first_errors=[b['error'] for b in per_block if b['error']][:5],
        seconds=round(time.time() - started, 1), source_writes=0, model_calls=0)
    (output/'summary.json').open('x').write(json.dumps(summary, sort_keys=True))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', required=True)
    parser.add_argument('--samples', type=int, default=300)
    args = parser.parse_args()
    print(json.dumps(measure(args.output_root, args.samples), sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
