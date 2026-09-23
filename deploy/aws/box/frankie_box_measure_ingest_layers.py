"""Measure every ingest reduction stacked, layer by layer, on the sealed Monday container (Greg, 2026-09-23).

Layers, each ON TOP OF the one before (nothing replaced):
  L0  the stored blocks as ingested (pinned codec C15_EXACT_ORDER_BLOCK_GZIP_V1)
  L1  the same pinned codec, blocks of 256 entries (the format's own bound) instead of the ingest's chunking
  L2  + one order dictionary carried across blocks (each block ships only orders not seen before)
  L3  + digests derived, not stored (every digest recomputed from the rebuilt body and checked)
  L4  + DIGEST_V5 tables for the records and the new orders
Each layer is gzip at the codec's level 6. Read-only (SQLite immutable); contiguous segments spread over the
whole trading day; per-segment numbers written. L4 is rebuilt entry by entry and must match every original
body and digest byte-exact, or the segment is counted inexact and not scored.
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
from frankie_box_measure_ingest_stack import CONTAINER, decode, encode, reorder  # noqa: E402
from research.kalshi.frankie_boss.c15_journal import pack, unpack  # noqa: E402
from research.kalshi.frankie_boss.compact_journal import MAX_ROWS, _orders, decode_block, encode_block  # noqa: E402
from research.kalshi.frankie_boss.verified_journal_reader import DIGEST_PREFIX, canonical_tagged_bytes  # noqa: E402

OUTPUT_PARENT = Path('/opt/frankie-box/work/ingest-stack-measure')


def gz(raw):
    return len(gzip.compress(raw, 6, mtime=0))


def chunks(rows):
    return [rows[i:i + MAX_ROWS] for i in range(0, len(rows), MAX_ROWS)]


def split(rows, lookup, dictionary):
    """Records with orders replaced by references into a dictionary carried across blocks; returns the new orders."""
    start, records, templates = len(dictionary), [], []
    for ordinal, kind, body, digest in rows:
        tree = json.loads(body)
        orders, refs = _orders(tree), None
        if orders is not None:
            refs = []
            for order in orders[1]:
                key = repr(order)
                if key not in lookup:
                    lookup[key] = len(dictionary)
                    dictionary.append(order)
                refs.append(lookup[key])
            orders[1] = []
        records.append((ordinal, kind, tree, refs, digest, len(body)))
        templates.append(unpack(tree))
    return records, dictionary[start:], templates


def layers(rows):
    out = dict(L0=None, L1=sum(len(encode_block(c)) for c in chunks(rows)))
    lookup, dictionary, l2, l3, l4, texts, all_templates = {}, [], 0, 0, 0, [], []
    for chunk in chunks(rows):
        records, new, templates = split(chunk, lookup, dictionary)
        l2 += gz(canonical_tagged_bytes([new, [list(r) for r in records]]))
        l3 += gz(canonical_tagged_bytes([new, [[o, k, t, refs, size] for o, k, t, refs, _, size in records]]))
        text = ''
        if new:
            text += render_table('orders', [dict(order=encode(unpack(o))) for o in new])
        text += render_table('records', [dict(ordinal=o, kind=k, size=size, refs=refs, entry=encode(unpack(t)))
                                          for o, k, t, refs, _, size in records])
        l4 += gz(text.encode())
        texts.append(text)
        all_templates.append(templates)
    out.update(L2=l2, L3=l3, L4=l4)
    return out, texts, all_templates, len(dictionary)


def rebuild(texts, templates, rows):
    """Decode L4 in order (the carried dictionary grows block by block); every body and digest must match."""
    dictionary, index = [], 0
    for text, block_templates in zip(texts, templates):
        parsed = {}
        for block in re.split(r'(?m)^(?=### table )', text):
            if block:
                name, value = parse_table(block)
                parsed[name] = value
        dictionary.extend(pack(decode(o['order'])) for o in parsed.get('orders', []))
        for record, template in zip(parsed['records'], block_templates):
            ordinal, kind, body, digest = rows[index]
            tree = pack(reorder(decode(record['entry']), template))
            if record['refs'] is not None:
                target = _orders(tree)
                if target is None:
                    return False
                target[1] = [dictionary[i] for i in record['refs']]
            raw = canonical_tagged_bytes(tree)
            if ((record['ordinal'], record['kind'], record['size']) != (ordinal, kind, len(body)) or raw != body
                    or hashlib.sha256(DIGEST_PREFIX + raw).hexdigest() != digest):
                return False
            index += 1
    return index == len(rows)


def measure(output, segments, entries):
    output = Path(output)
    if output.parent != OUTPUT_PARENT or not re.fullmatch('[A-Za-z0-9_-]{1,96}', output.name) or output.exists():
        raise ValueError('fresh named output under ' + str(OUTPUT_PARENT))
    OUTPUT_PARENT.mkdir(parents=True, exist_ok=True)
    output.mkdir(mode=0o700)
    db = sqlite3.connect('file:%s?mode=ro&immutable=1' % CONTAINER, uri=True)
    blocks = db.execute('SELECT start, count FROM blocks ORDER BY start').fetchall()
    total_bytes, total_entries = db.execute('SELECT SUM(LENGTH(body)), SUM(count) FROM blocks').fetchone()
    step = max(1, len(blocks) // segments)
    results, started = [], time.time()
    with (output/'per-segment.jsonl').open('x') as sink:
        for first in range(0, len(blocks), step)[:segments]:
            rows, stored, i = [], 0, first
            while i < len(blocks) and len(rows) < entries:
                blob = db.execute('SELECT body FROM blocks WHERE start=?', (blocks[i][0],)).fetchone()[0]
                rows.extend(decode_block(blob))
                stored += len(blob)
                i += 1
            try:
                sizes, texts, templates, orders = layers(rows)
                sizes['L0'] = stored
                exact, error = rebuild(texts, templates, rows), None
            except Exception as err:  # reported per segment, never scored
                sizes, orders, exact, error = dict(L0=stored), None, False, '%s: %s' % (type(err).__name__, str(err)[:200])
            item = dict(first_block=first, first_entry=blocks[first][0], stored_blocks=i - first, entries=len(rows),
                        plain_bytes=sum(len(r[2]) for r in rows), distinct_orders=orders, exact=exact, error=error,
                        **sizes)
            sink.write(json.dumps(item, sort_keys=True) + '\n')
            results.append(item)
    good = [r for r in results if r['exact']]
    totals = {k: sum(r[k] for r in good) for k in ('plain_bytes', 'L0', 'L1', 'L2', 'L3', 'L4')}
    def dist(key):
        values = sorted(r['L0'] / r[key] for r in good)
        return dict(min=round(values[0], 3), p50=round(values[len(values)//2], 3), max=round(values[-1], 3)) if values else None
    summary = dict(schema='FRANKIE_INGEST_LAYERS_MEASURE_V1', digest_schema=DIGEST_SCHEMA, container=CONTAINER,
        container_blocks=len(blocks), container_entries=total_entries, container_block_bytes=total_bytes,
        mean_entries_per_stored_block=round(total_entries / len(blocks), 2),
        segments=len(results), exact_segments=len(good), entries_measured=sum(r['entries'] for r in good),
        sampled_totals=totals, gain_over_L0_per_segment={k: dist(k) for k in ('L1', 'L2', 'L3', 'L4')},
        first_errors=[r['error'] for r in results if r['error']][:5],
        seconds=round(time.time() - started, 1), source_writes=0, model_calls=0)
    (output/'summary.json').open('x').write(json.dumps(summary, sort_keys=True))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', required=True)
    parser.add_argument('--segments', type=int, default=24)
    parser.add_argument('--entries', type=int, default=20480)
    args = parser.parse_args()
    print(json.dumps(measure(args.output_root, args.segments, args.entries), sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
