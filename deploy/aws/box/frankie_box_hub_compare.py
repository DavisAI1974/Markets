"""THE COMPARISON before any piece is switched to the hub (Greg, 2026-10-09): "we won't disconnect any info the other
pieces get natively until we compare what is sent to them also includes everything they are getting fed to them
currently". Binding standard (Greg): SAME NUMBERS, FULLER ALLOWED, NEVER LESS. For every native input a piece gets
today, the hub's send must carry the exact same content (the same planes with the same numbers); the hub may send more
(more planes, fields, rows), never less and never a different value.

For one run/day on the box, for each piece (frankie_box_hub_spokes.PIECES):
  (a) every native input of the piece (frankie_box_hub_spokes.NATIVE_INPUTS, traced from the code) is resolved to the
      file(s) or field(s) present under the day's directories;
  (b) the hub's send to the piece is built from the same day (frankie_box_hub_spokes.send_set);
  (c) each native input is compared BY VALUE with what the send resolves to:
        a file: the sha256 of the bytes the piece reads, streamed once (read-only), against the sha256 the hub's
                addition carries (the same file by reference: same path and sha256); a file over --stream-max and the
                giant streams (the sealed journal, the ROOT frames / prices / structures spools, the native ledgers) are
                compared BY PIN (path, bytes, sha256: the pins the readers themselves check) and say so;
        a field: the JSON value the piece's reader takes (a receipt field, the cutoff row's record, the account)
                against the value the send resolves to, field by field and row by row (equal / differing / absent
                counted, the first differing path named);
      and gets one verdict: SAME (identical content), FULLER (identical plus extra the hub adds, the extra listed),
      LESS (anything absent or any value differing, each listed with the first difference and the counts). A native
      input not on disk this day is NOT_PRESENT (listed, not compared); the piece's own resume state (OWN) and its
      mechanisms (claim caches, settings, control files, model runtime: MECHANISM) are listed and kept out of the verdict.
  Hub additions no native input of the piece takes are EXTRA (listed; they make the piece FULLER, never LESS).
  Any LESS means the piece is NOT switched.

Writes hub-compare-<day>.json and hub-compare-<day>.md into --out (default: beside --hub-dir, else the current
directory). Read-only everywhere else; never pins itself to CPUs; exit 0 always (the report is the result).
"""
import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

BOX = Path(__file__).resolve().parent
if str(BOX) not in sys.path:
    sys.path.insert(0, str(BOX))
import frankie_box_hub_spokes as S  # noqa: E402

SCHEMA = 'FRANKIE_HUB_COMPARE_V1'
STANDARD = 'same numbers, fuller allowed, never less'
VERDICTS = ('SAME', 'FULLER', 'LESS', 'NOT_PRESENT', 'OWN', 'MECHANISM')
STREAM_MAX = 1 << 30            # a file up to this size is streamed and hashed once; larger ones are compared by pin
JSON_DEEP_MAX = 256 << 20       # a JSON file up to this size may be parsed for a field-by-field comparison
READ = 16 << 20


class Hashes:
    """One streamed sha256 per unchanged file in this process (keyed on path, device, inode, size, mtime)."""

    def __init__(self):
        self.memo, self.streamed_bytes, self.files = {}, 0, 0

    def sha256(self, path):
        p = Path(path)
        st = p.stat()
        key = (str(p.resolve()), st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)
        if key not in self.memo:
            h = hashlib.sha256()
            with p.open('rb') as f:
                for chunk in iter(lambda: f.read(READ), b''):
                    h.update(chunk)
            self.memo[key] = h.hexdigest()
            self.streamed_bytes += st.st_size
            self.files += 1
        return self.memo[key]


def _resolved(path):
    try:
        return str(Path(path).resolve())
    except OSError:
        return str(path)


def _load(path):
    raw = Path(path).read_bytes()
    return json.loads(raw)


# ---------------------------------------------------------------------------------------------------------------------
# value comparison (field by field, row by row)

def deep_compare(native, hub, path='$', acc=None):
    """Counts of leaves equal / differing / absent from the hub (native has it, hub does not) / extra in the hub, the first
    differing and first absent path. Lists are compared by position (rows)."""
    acc = acc if acc is not None else dict(equal=0, differing=0, absent=0, extra=0, first_differing=None,
                                           first_absent=None, extra_paths=[])
    if isinstance(native, dict) and isinstance(hub, dict):
        for k in native:
            if k in hub:
                deep_compare(native[k], hub[k], '%s.%s' % (path, k), acc)
            else:
                acc['absent'] += _leaves(native[k])
                acc['first_absent'] = acc['first_absent'] or '%s.%s' % (path, k)
        for k in hub:
            if k not in native:
                acc['extra'] += _leaves(hub[k])
                if len(acc['extra_paths']) < 20:
                    acc['extra_paths'].append('%s.%s' % (path, k))
        return acc
    if isinstance(native, list) and isinstance(hub, list):
        for i, v in enumerate(native):
            if i < len(hub):
                deep_compare(v, hub[i], '%s[%d]' % (path, i), acc)
            else:
                acc['absent'] += _leaves(v)
                acc['first_absent'] = acc['first_absent'] or '%s[%d]' % (path, i)
        for i in range(len(native), len(hub)):
            acc['extra'] += _leaves(hub[i])
            if len(acc['extra_paths']) < 20:
                acc['extra_paths'].append('%s[%d]' % (path, i))
        return acc
    same = native == hub and type(native) is type(hub) or (
        isinstance(native, float) and isinstance(hub, float) and native != native and hub != hub)
    if same:
        acc['equal'] += 1
    else:
        acc['differing'] += 1
        if acc['first_differing'] is None:
            acc['first_differing'] = dict(path=path, native=_short(native), hub=_short(hub))
    return acc


def _leaves(value):
    if isinstance(value, dict):
        return sum(_leaves(v) for v in value.values()) or 1
    if isinstance(value, list):
        return sum(_leaves(v) for v in value) or 1
    return 1


def _short(value):
    text = json.dumps(value, sort_keys=True, default=str)
    return text if len(text) <= 200 else text[:200] + '...'


def jsonl_compare(native_path, hub_path):
    """Row by row (one JSON value per line), both streamed once: rows equal / differing / absent / extra, the first
    differing row with its first differing field, and the leaf counts of the differing rows."""
    out = dict(rows_equal=0, rows_differing=0, rows_absent=0, rows_extra=0, first_differing_row=None,
               fields=dict(equal=0, differing=0, absent=0, extra=0))
    with Path(native_path).open('rb') as a, Path(hub_path).open('rb') as b:
        ordinal = 0
        while True:
            la, lb = a.readline(), b.readline()
            if not la and not lb:
                break
            if la and not lb:
                out['rows_absent'] += 1
            elif lb and not la:
                out['rows_extra'] += 1
            elif la == lb:
                out['rows_equal'] += 1
            else:
                try:
                    acc = deep_compare(json.loads(la), json.loads(lb), '$[row %d]' % ordinal)
                except ValueError:
                    acc = dict(equal=0, differing=1, absent=0, extra=0, first_differing=dict(path='$[row %d]' % ordinal,
                               native='(not JSON)', hub='(not JSON)'), first_absent=None)
                for k in ('equal', 'differing', 'absent', 'extra'):
                    out['fields'][k] += acc[k]
                if acc['differing'] or acc['absent']:
                    out['rows_differing'] += 1
                    if out['first_differing_row'] is None:
                        out['first_differing_row'] = dict(row=ordinal, first_differing=acc['first_differing'],
                                                          first_absent=acc['first_absent'])
                else:
                    out['rows_equal'] += 1          # every field equal; the hub's row carries extra fields
                    out['rows_fuller'] = out.get('rows_fuller', 0) + 1
            ordinal += 1
    return out


def _verdict_of_counts(differing, absent, extra):
    if differing or absent:
        return 'LESS'
    return 'FULLER' if extra else 'SAME'


# ---------------------------------------------------------------------------------------------------------------------
# one native item against the send

class SendIndex:
    def __init__(self, send):
        self.send = send
        self.by_path, self.by_sha, self.by_base, self.by_name = {}, {}, {}, {}
        for i, a in enumerate(send):
            if a.get('path'):
                self.by_path.setdefault(_resolved(a['path']), i)
                self.by_base.setdefault(Path(a['path']).name, []).append(i)
            if a.get('sha256'):
                self.by_sha.setdefault(a['sha256'], i)
            self.by_name.setdefault(a.get('name'), i)
        self.used = set()


def _addition_ref(a):
    return {k: a.get(k) for k in ('name', 'group', 'producer', 'path', 'bytes', 'sha256', 'sha256_basis', 'filter')
            if a.get(k) is not None}


def compare_item(item, native, index, hashes, stream_max):
    """One resolved native item -> a report row with its verdict."""
    row = dict(input=native['label'], kind=item['kind'], producer=item['producer'], reads_at=item.get('reads_at'),
               filter=item['filter'], compare=item['compare'], native_path=native.get('path') or native.get('container'))
    if item['klass'] in ('own', 'mechanism'):
        row.update(verdict='OWN' if item['klass'] == 'own' else 'MECHANISM',
                   detail='listed; ' + ('the piece\'s own retained resume state, not fed by another piece'
                                        if item['klass'] == 'own' else
                                        'how the piece reads (claim cache, setting, control file or runtime), not a value '
                                        'it is fed') + ('; ' + item['note'] if item.get('note') else ''))
        return row
    if not native.get('present'):
        row.update(verdict='NOT_PRESENT', detail=native.get('reason') or 'not on disk this day')
        return row
    if 'value' in native:
        return _compare_field(row, native, index)
    return _compare_file(row, item, native, index, hashes, stream_max)


def _compare_field(row, native, index):
    container = _resolved(native['container'])
    i = index.by_path.get(container)
    if i is None:
        row.update(verdict='LESS', detail='the hub sends neither the field nor the file that carries it (%s)'
                   % native['container'], counts=dict(absent=_leaves(native['value'])))
        return row
    a = index.send[i]
    index.used.add(i)
    try:
        ok, hub_value = S.dig(_load(a['path']), native['field'])
    except (OSError, ValueError) as error:
        row.update(verdict='LESS', hub=_addition_ref(a), detail='the hub\'s file is not readable: %s' % error)
        return row
    if not ok:
        row.update(verdict='LESS', hub=_addition_ref(a), detail='the hub\'s %s carries no %s' % (a['path'], native['field']))
        return row
    acc = deep_compare(native['value'], hub_value)
    verdict = _verdict_of_counts(acc['differing'], acc['absent'], acc['extra'])
    row.update(verdict=verdict, hub=_addition_ref(a),
               counts={k: acc[k] for k in ('equal', 'differing', 'absent', 'extra')},
               detail=('field %s compared value by value through the hub\'s %s' % (native['field'], a.get('name'))),
               first_differing=acc['first_differing'], first_absent=acc['first_absent'],
               extra=acc['extra_paths'] or None)
    return row


def _compare_file(row, item, native, index, hashes, stream_max):
    path = Path(native['path'])
    try:
        size = path.stat().st_size
    except OSError as error:
        row.update(verdict='NOT_PRESENT', detail='not readable: %s' % error)
        return row
    pin = native.get('pin') or {}
    by_pin = item['compare'] == 'pin' or size > stream_max
    i = index.by_path.get(_resolved(path))
    native_sha, basis = None, None
    if by_pin:
        native_sha = pin.get('sha256')
        basis = ('by pin (the reader\'s pin: path, bytes, sha256; not read whole)' if item['compare'] == 'pin' else
                 'by pin (over --stream-max %d bytes; not read whole)' % stream_max)
        if pin.get('bytes') is not None and pin.get('bytes') != size:
            row.update(verdict='LESS', detail='the reader\'s pin names %s bytes; the file on disk has %d'
                       % (pin.get('bytes'), size))
            return row
    else:
        native_sha = hashes.sha256(path)
        basis = 'by value (the bytes the piece reads, streamed once and hashed)'
        if pin.get('sha256') and pin['sha256'] != native_sha:
            basis += '; NOTE the producer\'s pin %s differs from the bytes on disk' % pin['sha256'][:16]
    if i is None and native_sha:
        i = index.by_sha.get(native_sha)
        if i is not None:
            basis += '; the hub sends the same content at another path'
    if i is None:
        return _compare_by_name(row, path, index, basis, native_sha)
    a = index.send[i]
    index.used.add(i)
    hub_sha = a.get('sha256')
    if hub_sha is None and a.get('path') and not by_pin:
        hub_sha = hashes.sha256(a['path'])           # same path: one stream (the cache)
    if by_pin and native_sha is None:
        # the reader names no sha256 for it (a pin without one): the hub's pin and the size decide
        same = a.get('bytes') in (None, size) and hub_sha is not None and _resolved(a['path']) == _resolved(path)
        row.update(verdict='SAME' if same else 'LESS', hub=_addition_ref(a), basis=basis + '; the reader recorded no '
                   'sha256, so the hub\'s pin and the size on disk were compared',
                   detail='the hub sends this very file by reference' if same else 'no pin to compare against')
        return row
    if hub_sha == native_sha and a.get('bytes') in (None, size):
        row.update(verdict='SAME', hub=_addition_ref(a), basis=basis,
                   detail='byte-identical (sha256 %s, %d bytes): every row and field equal' % (native_sha[:16], size))
        return row
    row.update(verdict='LESS', hub=_addition_ref(a), basis=basis,
               detail='the hub\'s addition names sha256 %s / %s bytes; the piece reads sha256 %s / %d bytes'
                      % ((hub_sha or 'none')[:16], a.get('bytes'), (native_sha or 'none')[:16], size))
    return row


def _compare_by_name(row, path, index, basis, native_sha):
    """No addition at this path or with this content: a hub file of the same name (another version) is compared by
    value (JSON field by field, JSON lines row by row); otherwise the input is absent from the send (LESS)."""
    for i in index.by_base.get(path.name, []):
        a = index.send[i]
        other = Path(a['path'])
        if not other.is_file():
            continue
        index.used.add(i)
        try:
            if path.suffix == '.jsonl':
                rows = jsonl_compare(path, other)
                verdict = 'LESS' if rows['rows_differing'] or rows['rows_absent'] else (
                    'FULLER' if rows['rows_extra'] or rows.get('rows_fuller') else 'SAME')
                row.update(verdict=verdict, hub=_addition_ref(a), basis=basis + '; row by row against the hub\'s '
                           'version of the same name', rows=rows)
                return row
            if path.suffix == '.json' and path.stat().st_size <= JSON_DEEP_MAX and other.stat().st_size <= JSON_DEEP_MAX:
                acc = deep_compare(_load(path), _load(other))
                row.update(verdict=_verdict_of_counts(acc['differing'], acc['absent'], acc['extra']), hub=_addition_ref(a),
                           basis=basis + '; field by field against the hub\'s version of the same name',
                           counts={k: acc[k] for k in ('equal', 'differing', 'absent', 'extra')},
                           first_differing=acc['first_differing'], first_absent=acc['first_absent'],
                           extra=acc['extra_paths'] or None)
                return row
        except (OSError, ValueError) as error:
            row.update(verdict='LESS', hub=_addition_ref(a), detail='the hub\'s version is not comparable: %s' % error)
            return row
    row.update(verdict='LESS', basis=basis, detail='absent from the hub\'s send (no addition at this path, with this '
               'content or of this name)', native_sha256=native_sha)
    return row


# ---------------------------------------------------------------------------------------------------------------------
# the day

def compare_day(day, run=None, *, attempt=None, previous=None, frozen_survivors=None, roots=None,
                stream_max=STREAM_MAX, hash_max=S.HASH_MAX, pieces=None):
    started = time.time()
    sources = S.day_sources(day, run, attempt=attempt, previous=previous, frozen_survivors=frozen_survivors,
                            roots=roots)
    hashes = Hashes()
    inventory = S.inventory()
    report = dict(schema=SCHEMA, standard=STANDARD, day=str(day), run=run,
                  sources={k: (str(v) if isinstance(v, Path) else v) for k, v in sources.items()},
                  stream_max=stream_max, pieces={}, rule='every native input listed; nothing cut; any LESS = the piece '
                                                         'is not switched to the hub')
    for piece in pieces or S.PIECES:
        try:
            send = S.send_set(piece, sources, hash_max=hash_max)
        except Exception as error:  # noqa: BLE001 - the report says it; the other pieces are compared
            report['pieces'][piece] = dict(verdict='LESS', error='the send set could not be built: %s: %s'
                                           % (type(error).__name__, error), inputs=[], extra=[])
            continue
        index = SendIndex(send)
        rows = []
        for n, item in enumerate(inventory[piece]):
            spec = dict(S.NATIVE_INPUTS[piece][n], reads_at=item['reads_at'])
            try:
                natives = S.resolve(spec, sources)
            except Exception as error:  # noqa: BLE001
                natives = [dict(label=item['name'], present=False, reason='not resolvable: %s: %s'
                                % (type(error).__name__, error))]
            for native in natives:
                try:
                    rows.append(compare_item(spec, native, index, hashes, stream_max))
                except Exception as error:  # noqa: BLE001 - one input's failure is its row (LESS), never dropped
                    rows.append(dict(input=native.get('label'), reads_at=item['reads_at'], verdict='LESS',
                                     detail='the comparison failed: %s: %s' % (type(error).__name__, error)))
        extra = [_addition_ref(a) for i, a in enumerate(send) if i not in index.used]
        counts = {v: sum(1 for r in rows if r['verdict'] == v) for v in VERDICTS}
        if piece == 'forecaster':
            verdict = 'NO CONSUMER YET'
        elif counts['LESS']:
            verdict = 'LESS'
        elif counts['FULLER'] or extra:
            verdict = 'FULLER'
        else:
            verdict = 'SAME'
        report['pieces'][piece] = dict(
            verdict=verdict, switchable=verdict in ('SAME', 'FULLER') and not counts['LESS'],
            inventoried=len(inventory[piece]), compared_items=len(rows), counts=counts, extra_count=len(extra),
            send_count=len(send), filter=S.FILTERS[piece], inputs=rows, extra=extra,
            note=S.FORECASTER_NOTE if piece == 'forecaster' else None)
    totals = {v: sum(p.get('counts', {}).get(v, 0) for p in report['pieces'].values()) for v in VERDICTS}
    totals.update(inventoried=sum(p.get('inventoried', 0) for p in report['pieces'].values()),
                  compared_items=sum(p.get('compared_items', 0) for p in report['pieces'].values()),
                  extra=sum(p.get('extra_count', 0) for p in report['pieces'].values()),
                  pieces_less=sorted(k for k, p in report['pieces'].items() if p['verdict'] == 'LESS'))
    report['totals'] = totals
    report['measured'] = dict(seconds=round(time.time() - started, 3), files_streamed=hashes.files,
                              bytes_streamed=hashes.streamed_bytes)
    return report


def render_md(report):
    t = report['totals']
    lines = ['# Hub comparison: %s %s' % (report.get('run') or '', report['day']), '',
             '**Standard: %s.** For every input a piece is fed today, the hub must send the exact same content (the same '
             'planes with the same numbers); it may send more, never less and never a different value. Any LESS means the '
             'piece is not switched.' % STANDARD, '',
             'Verdicts: SAME (identical content), FULLER (identical plus extra the hub adds, listed), LESS (absent or '
             'differing, each listed), NOT_PRESENT (the native input is not on disk this day: listed, not compared), OWN '
             '(the piece\'s own resume state) and MECHANISM (claim caches, settings, control, runtime): listed, outside '
             'the verdict. Files are compared by their streamed sha256; the giant streams (sealed journal, ROOT spools, '
             'native ledgers) and files over the stream limit BY PIN (path, bytes, sha256), as stated per row.', '',
             '## Verdict per piece', '']
    for piece, p in report['pieces'].items():
        c = p.get('counts', {})
        lines.append('- **%s: %s**%s: %d inputs inventoried, %d compared items: SAME %d, FULLER %d, LESS %d, '
                     'NOT_PRESENT %d, OWN %d, MECHANISM %d; %d hub additions sent, %d EXTRA%s' % (
                         piece, p['verdict'], ' (not switched)' if p['verdict'] == 'LESS' else '',
                         p.get('inventoried', 0), p.get('compared_items', 0), c.get('SAME', 0), c.get('FULLER', 0),
                         c.get('LESS', 0), c.get('NOT_PRESENT', 0), c.get('OWN', 0), c.get('MECHANISM', 0),
                         p.get('send_count', 0), p.get('extra_count', 0), ('; ' + p['note']) if p.get('note') else ''))
        if p.get('error'):
            lines.append('  - %s' % p['error'])
    lines += ['', '**Totals:** %d inputs inventoried, %d compared items: SAME %d, FULLER %d, LESS %d, NOT_PRESENT %d, '
              'OWN %d, MECHANISM %d; EXTRA %d; pieces LESS: %s.' % (
                  t['inventoried'], t['compared_items'], t['SAME'], t['FULLER'], t['LESS'], t['NOT_PRESENT'], t['OWN'],
                  t['MECHANISM'], t['extra'], ', '.join(t['pieces_less']) or 'none'),
              '', 'Measured: %(seconds)s s, %(files_streamed)d files streamed, %(bytes_streamed)d bytes.' % report['measured']]
    for piece, p in report['pieces'].items():
        lines += ['', '## %s: %s' % (piece, p['verdict']), '', 'Filter on its own read (stated on every addition sent to '
                  'it, applied by the piece, not the hub): %s' % p.get('filter'), '',
                  '| verdict | input | reading code | native | hub addition | how / detail |', '|---|---|---|---|---|---|']
        for r in p.get('inputs', []):
            hub = r.get('hub') or {}
            detail = '; '.join(x for x in (r.get('basis'), r.get('detail')) if x)
            for key in ('counts', 'rows', 'first_differing', 'first_absent', 'extra'):
                if r.get(key):
                    detail += '; %s %s' % (key, json.dumps(r[key], sort_keys=True, default=str))
            lines.append('| %s | %s | %s | %s | %s | %s |' % (
                r['verdict'], _cell(r.get('input')), _cell(r.get('reads_at')), _cell(r.get('native_path')),
                _cell(hub.get('name') and '%s (%s)' % (hub.get('name'), hub.get('group'))), _cell(detail)))
        extra = p.get('extra') or []
        lines += ['', 'EXTRA in the hub\'s send to %s (%d; FULLER, never LESS):' % (piece, len(extra)), '']
        for a in extra:
            lines.append('- %s (%s): %s' % (a.get('name'), a.get('group'), a.get('path') or 'value'))
    return '\n'.join(lines) + '\n'


def _cell(value):
    return str(value if value is not None else '').replace('|', '/').replace('\n', ' ')


def write_report(report, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = {}
    for suffix, data in (('json', (json.dumps(report, indent=1, sort_keys=True, default=str) + '\n').encode()),
                         ('md', render_md(report).encode())):
        path = out_dir / ('hub-compare-%s.%s' % (report['day'], suffix))
        pending = path.with_name(path.name + '.pending')
        pending.write_bytes(data)
        os.replace(pending, path)
        written[suffix] = str(path)
    return written


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--day', required=True)
    ap.add_argument('--run', help='the experiment run (e.g. e2e-20231018-a2)')
    ap.add_argument('--attempt', help='the ROOT attempt directory (default: the newest <run>-<day>-aN)')
    ap.add_argument('--previous', help='the previous classroom day\'s work/classroom (default: from the classroom receipt)')
    ap.add_argument('--frozen-survivors')
    ap.add_argument('--hub-dir', help='the hub directory; the report goes beside it unless --out')
    ap.add_argument('--out', help='where the two report files are written (the only writes)')
    ap.add_argument('--stream-max', type=int, default=STREAM_MAX, help='stream-hash files up to this many bytes')
    for key, value in S.DEFAULT_ROOTS.items():
        ap.add_argument('--' + key.replace('_', '-'), default=str(value))
    a = ap.parse_args(argv)
    roots = {k: getattr(a, k) for k in S.DEFAULT_ROOTS}
    try:
        report = compare_day(a.day, a.run, attempt=a.attempt, previous=a.previous, frozen_survivors=a.frozen_survivors,
                             roots=roots, stream_max=a.stream_max)
    except Exception as error:  # noqa: BLE001 - exit 0 always; the failure is the report
        report = dict(schema=SCHEMA, standard=STANDARD, day=a.day, run=a.run, pieces={},
                      error='%s: %s' % (type(error).__name__, error),
                      totals=dict(inventoried=0, compared_items=0, extra=0, pieces_less=[], **{v: 0 for v in VERDICTS}),
                      measured=dict(seconds=0, files_streamed=0, bytes_streamed=0))
    out = a.out or (str(Path(a.hub_dir).parent) if a.hub_dir else '.')
    try:
        written = write_report(report, out)
    except OSError as error:
        written = dict(error=str(error))
    t = report['totals']
    print(json.dumps(dict(written=written, totals=t, verdicts={k: p['verdict'] for k, p in report['pieces'].items()},
                          error=report.get('error')), sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
