"""Read-only probe: the field names the teacher's pictures carry (for the per-state split of the second set).

Decodes pictures exactly as the teacher's shared walk does (frankie_box_market_timeline.SharedMarketTimeline over the
ROOT, iter_applied, the same equation filter: present APPLIED payloads with adapter cursors contiguous from zero) and
prints, for the picture at --cursor (default: the first APPLIED row):
  - the instant's key and clocks (picture.at) and the 99 registry entries its plane rows carry
  - every plane row of the picture (updates, last_observed_state, active_instrument_state, published_state): its
    source, source_ordinal, entries and the full list of its field paths with one example value each (strings and
    other scalars truncated to 60 characters; a list shows its length and its first element's fields)
then keeps reading (up to --max-pictures) until every stream source has shown a row, printing the first row of each
(source, emitting_section) not printed yet, so the native lifecycle sections (lineage, episode, candidate,
detector_coverage, replenishment, absorption, ladder, queue, flow_substrate, recurrence) appear with their fields.
Finally it lists where derived_roll20_and_dipole_state could live outside the picture: ROOT files whose names hold
'roll20' or 'dipole', and every derive.json / calculations-receipt.json key path holding either word.

Nothing is written; no model is called. Stdlib plus the project's own reader. Run on the box:
  python3 deploy/aws/box/frankie_box_probe_picture_fields.py [--root OUTPUT_ROOT] [--cursor N] [--workers 2]
"""
import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for path in (str(HERE), str(HERE.parents[2])):
    if path not in sys.path:
        sys.path.insert(0, path)

DEFAULT_ROOT = '/opt/frankie-box/work/experiment-roots/e2e-20231018-a2-20231018-a1'
WIDTH = 60
SOURCES = ('root.frames', 'root.prices', 'root.structures', 'native.member', 'native.lifecycle')


def short(value):
    text = repr(value) if not isinstance(value, str) else value
    return text if len(text) <= WIDTH else text[:WIDTH] + '...(%d chars)' % len(text)


def fields(value, prefix='', out=None):
    """{field path: one example} of a decoded row; a list shows its length and its first element's fields."""
    out = {} if out is None else out
    if isinstance(value, dict):
        if not value:
            out.setdefault(prefix or '.', '{} (empty mapping)')
        for key, item in value.items():
            fields(item, '%s.%s' % (prefix, key) if prefix else str(key), out)
    elif isinstance(value, (list, tuple)):
        out.setdefault(prefix + '[]', '%s of length %d' % (type(value).__name__, len(value)))
        if value:
            fields(value[0], prefix + '[0]', out)
    else:
        out.setdefault(prefix or '.', short(value))
    return out


def show_row(where, row):
    value = row.get('value') if isinstance(row, dict) else None
    print('  --- %s: source=%s source_ordinal=%s input_cursor=%s known_at_ns=%s availability_basis=%s'
          % (where, row.get('source'), row.get('source_ordinal'), row.get('input_cursor'), row.get('known_at_ns'),
             row.get('availability_basis')))
    print('      entries: %s' % (row.get('entries'),))
    if isinstance(value, dict):
        section = value.get('emitting_section')
        if section is not None:
            print('      emitting_section: %s' % short(section))
        for path, example in fields(value).items():
            print('      %s = %s' % (path, example))
    else:
        print('      value: %s' % short(value))


def show_picture(item):
    picture = item['picture']
    evidence = item['evidence']
    print('=== picture at adapter cursor %s' % (evidence.get('cursor') if evidence else None))
    print('at:')
    for key, value in (picture.get('at') or {}).items():
        print('  %s = %s' % (key, short(value)))
    entries = sorted({e for u in picture.get('updates') or () for e in (u.get('entries') or ())})
    print('99 entries carried by this picture\'s plane rows (%d): %s' % (len(entries), entries))
    print('picture keys: %s' % sorted(picture))
    print('coverage: %s' % {k: short(v) for k, v in (picture.get('coverage') or {}).items()})
    print('opening_state keys: %s' % sorted((picture.get('opening_state') or {})))
    for name in ('updates', 'last_observed_state', 'active_instrument_state', 'published_state'):
        rows = picture.get(name) or ()
        print('%s: %d row(s)' % (name, len(rows)))
        for row in rows:
            show_row(name, row)
    if evidence is not None:
        print('teacher row (APPLIED payload) keys: %s' % sorted(evidence))


def dipole_locations(root):
    print('=== where derived_roll20_and_dipole_state could live outside the picture')
    found = 0
    for directory, subdirectories, files in os.walk(root):
        for name in subdirectories + files:
            low = name.lower()
            if 'roll20' in low or 'dipole' in low:
                print('  path: %s' % os.path.join(directory, name))
                found += 1
    print('  (%d path(s) named roll20/dipole under %s)' % (found, root))
    for document in ('derive.json', 'calculations-receipt.json', 'source-binding.json'):
        candidates = [Path(root) / document] + list(Path(root).glob('work/%s' % document))
        for path in candidates:
            if not path.is_file():
                continue
            try:
                body = json.loads(path.read_bytes())
            except Exception as error:  # noqa: BLE001 - a probe lists what it could not read
                print('  %s: not read (%s)' % (path, error))
                continue

            def walk(value, prefix):
                if isinstance(value, dict):
                    for key, item in value.items():
                        here = '%s.%s' % (prefix, key) if prefix else str(key)
                        if 'roll20' in str(key).lower() or 'dipole' in str(key).lower():
                            print('  %s: %s = %s' % (path.name, here, short(item)))
                        walk(item, here)
                elif isinstance(value, list):
                    for index, item in enumerate(value):
                        walk(item, '%s[%d]' % (prefix, index))
                elif isinstance(value, str) and ('roll20' in value.lower() or 'dipole' in value.lower()):
                    print('  %s: %s = %s' % (path.name, prefix, short(value)))
            walk(body, '')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', default=os.environ.get('OUTPUT_ROOT', DEFAULT_ROOT))
    parser.add_argument('--cursor', type=int, default=None, help='adapter cursor of the picture (default: the first)')
    parser.add_argument('--workers', type=int, default=2, help='decode workers of the reader (default 2)')
    parser.add_argument('--max-pictures', type=int, default=200000,
                        help='after the cursor, read at most this many more pictures looking for unseen sources')
    args = parser.parse_args()
    from frankie_box_market_timeline import SharedMarketTimeline
    import frankie_box_all99_coverage as ALL99
    root = Path(args.root)
    binding = json.loads((root / 'source-binding.json').read_bytes())
    day = str(binding['source']['trading_day'])
    print('ROOT %s, trading day %s' % (root, day))
    market = SharedMarketTimeline(str(root), day=day, workers=args.workers)
    print('streams: %s' % {s.name: dict(kind=s.kind, path=s.pin.get('path'), bytes=s.pin.get('bytes'))
                           for s in market.streams})
    print('absent layers: %s' % (market.absent_layers,))
    print('carriers: %s' % {k: dict(status=v['status'], reason=v['reason']) for k, v in market.layer_entries().items()})
    print('entries not carried by the picture: %s' % {k: v for k, v in ALL99.NOT_MARKET_CARRIED.items()})
    pictures = market.iter_applied()
    expected, shown, seen, after = 0, False, set(), 0
    try:
        for item in pictures:
            if item['arithmetic']['status'] != 'present':
                continue
            evidence = item['evidence']
            if evidence.get('cursor') != expected:
                print('the equation prefix ends at adapter cursor %s (expected %d)' % (evidence.get('cursor'), expected))
                break
            expected += 1
            if not shown:
                if args.cursor is not None and evidence['cursor'] != args.cursor:
                    continue
                show_picture(item)
                shown = True
                for row in item['picture'].get('updates') or ():
                    seen.add((row.get('source'), (row.get('value') or {}).get('emitting_section')
                              if isinstance(row.get('value'), dict) else None))
                print('=== reading on for sources / lifecycle sections not shown yet (up to %d pictures)'
                      % args.max_pictures)
                continue
            after += 1
            for row in item['picture'].get('updates') or ():
                section = (row.get('value') or {}).get('emitting_section') if isinstance(row.get('value'), dict) else None
                key = (row.get('source'), section)
                if key not in seen:
                    seen.add(key)
                    print('=== first row of %s (section %s) at adapter cursor %s' % (key[0], key[1], evidence['cursor']))
                    show_row('updates', row)
            if after >= args.max_pictures:
                break
    finally:
        pictures.close()
    print('=== sources / sections seen: %s' % sorted(seen, key=str))
    print('=== sources never seen in %d pictures: %s' % (after, [s for s in SOURCES if s not in {k[0] for k in seen}]))
    dipole_locations(root)


if __name__ == '__main__':
    main()
