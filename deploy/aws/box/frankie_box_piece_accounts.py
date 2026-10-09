"""Each piece's own first-person account of its step, for the day reports (Greg, 2026-10-09, binding): every piece's
report (ROOT, teacher, classroom) answers, in the piece's own words,

  What actions did I do in my step         the stages / processes actually run, in order, with their times
  What outputs did I generate              every file, table, ledger and layer with counts and bytes (claim / witness)
  What improvements could be made          derived mechanically from the recorded runtime facts: where the time went,
                                           rows per second, re-reads or copies still made, idle CPU stretches from the
                                           heartbeats, the memory peak, could_not / absent / thin items, mismatches,
                                           and every fact the step did not record ("I could not measure X")

Every sentence is carried by a recorded fact and ends with the field it came from in brackets ([file#field]). Nothing
is invented and nothing summarized away: records are rendered field by field and lists whole. A fact a sentence needs
that the step did not record reads "not recorded by my step" and is listed under the improvements; it is never zero.
The only arithmetic is a share of a recorded total or a ratio of two recorded numbers, each with both citations.

Inputs are read by the caller (frankie_box_experiment_day_reports.Day, which witnesses every file it reads); this module
only renders. A rename of a recorded field is one place: the *_FIELDS tables below.
"""
import json
from pathlib import Path

NOT_RECORDED = 'not recorded by my step'

# ---- the recorded fields each piece's account reads (one place per piece)
ROOT_FIELDS = dict(receipt='calculations-receipt.json', derive='work/derive.json',
                   processes='root_processes', not_run='not_run', policy='native_calculation_policy',
                   execution='root_execution', source_writes='source_writes', source_replays='source_replays',
                   model_calls='model_calls', spool_reopen='spool_reopen', retained='retained_evidence_check',
                   failures='failure_count', opening_book='opening_book', status='status',
                   pins=('source_binding', 'calculation_pins', 'derivation', 'digest', 'external_computation'),
                   market_sources='shared_market_sources', layers='layers', bedrock='bedrock',
                   counts=('records', 'rows', 'legacy_rows', 'f_last_groups', 'groups', 'input_records'),
                   workers='runtime-workers-receipt.json', gates='pre-traversal-gates.json')
TEACHER_FIELDS = dict(receipt='receipt.json', account='account', runtime='runtime', phases='phase_seconds',
                      outputs=('rows_file', 'attachment_file', 'teacher_second_set', 'rows_sidecar', 'file_claims',
                               'classroom_carry', 'shared_market_context'),
                      counts=('rows', 'processed', 'entity_rows', 'walk_seconds', 'seconds', 'status'),
                      cpu='cpu_pinning')
CLASSROOM_FIELDS = dict(receipt='receipt.json', phases='phase_timings', saved='saved_phases', received='received',
                        outputs='outputs', side='side_by_side', cpu='cpu_pinning', native='native_entries',
                        second_set='second_set', seconds='seconds')
HEARTBEAT_STAGE = dict(root='root', teacher='teacher', classroom='classroom')


def cite(source, *path):
    return ' [%s#%s]' % (source, '.'.join(str(p) for p in path)) if path else ' [%s]' % source


def show(value):
    if value is None:
        return NOT_RECORDED
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True, default=str)


def flat(value, prefix=''):
    """Every leaf of a nested record as (dotted field, value), in order (nothing dropped)."""
    if isinstance(value, dict):
        out = []
        for key, item in value.items():
            out += flat(item, '%s.%s' % (prefix, key) if prefix else str(key))
        return out or [(prefix, {})]
    if isinstance(value, (list, tuple)) and value and all(isinstance(v, (dict, list, tuple)) for v in value):
        out = []
        for i, item in enumerate(value):
            out += flat(item, '%s[%d]' % (prefix, i))
        return out
    return [(prefix, value)]


def _cell(text):
    return str(text).replace('|', '\\|').replace('\n', ' ')


def table(header, rows):
    out = ['| ' + ' | '.join(header) + ' |', '|' + '---|' * len(header)]
    out += ['| ' + ' | '.join(_cell(c) for c in row) + ' |' for row in rows]
    return out


def record_table(value, source, prefix):
    """A recorded record field by field: what I recorded, its value, where from."""
    rows = [(field, show(v), '%s#%s' % (source, field)) for field, v in flat(value, prefix)]
    return table(['what I recorded', 'value', 'from'], rows)


class Account:
    """The three sections, built sentence by sentence; `missing` collects the facts the step did not record."""

    def __init__(self):
        self.actions, self.outputs, self.improvements, self.missing = [], [], [], []

    def fact(self, section, text, value, source, *path):
        """One sentence carrying one recorded value; an absent value is said and listed."""
        if value is None:
            getattr(self, section).append('- %s: %s%s.' % (text, NOT_RECORDED, cite(source, *path)))
            self.missing.append('%s%s' % (text, cite(source, *path)))
            return False
        getattr(self, section).append('- %s: %s%s.' % (text, show(value), cite(source, *path)))
        return True

    def lines(self):
        L = ['## What actions did I do in my step', ''] + (self.actions or ['- ' + NOT_RECORDED + '.']) + ['']
        L += ['## What outputs did I generate', ''] + (self.outputs or ['- ' + NOT_RECORDED + '.']) + ['']
        L += ['## What improvements could be made in these areas', '']
        L += self.improvements or []
        if self.missing:
            L += ['', 'I could not measure these (each is an improvement: my step did not record it):', '']
            L += ['- %s' % item for item in self.missing]
        if not self.improvements and not self.missing:
            L += ['- Nothing my recorded facts point to.']
        return L + ['']


def _shares(acc, seconds, source, path, label):
    """Where the time went: every recorded phase with its seconds and its share of their recorded sum."""
    items = [(name, v if not isinstance(v, dict) else v.get('seconds')) for name, v in (seconds or {}).items()]
    numbers = [(n, s) for n, s in items if isinstance(s, (int, float))]
    total = sum(s for _, s in numbers)
    rows = [(n, show(s), ('%.1f%%' % (100.0 * s / total)) if total and isinstance(s, (int, float)) else NOT_RECORDED,
             '%s#%s.%s' % (source, path, n)) for n, s in items]
    if not rows:
        acc.missing.append('the time per %s%s' % (label, cite(source, path)))
        return
    acc.improvements += ['Where my time went, %s by %s, each with its share of their recorded sum of %s seconds%s:' % (
        label, label, show(round(total, 3)), cite(source, path)), '']
    acc.improvements += table([label, 'seconds', 'share', 'from'], sorted(rows, key=lambda r: -(
        float(r[1]) if r[1] not in (NOT_RECORDED,) and r[1].replace('.', '', 1).isdigit() else -1))) + ['']


def _cpu_count(ranges):
    """The CPUs a heartbeat's cpu_ranges names ('0-15,32-47' or a list of such), or None."""
    if ranges is None:
        return None
    parts = ranges if isinstance(ranges, (list, tuple)) else str(ranges).split(',')
    count = 0
    try:
        for part in parts:
            part = str(part).strip()
            if not part:
                continue
            if '-' in part:
                a, b = part.split('-', 1)
                count += int(b) - int(a) + 1
            else:
                int(part)
                count += 1
    except ValueError:
        return None
    return count or None


def heartbeat(acc, lines, source, stage):
    """The stage heartbeats (frankie_box_stage_progress samples): the phases seen in order with their first time, the
    final elapsed time and outcome (actions); the memory peak and every sample whose busy CPUs were below the CPUs the
    stage held (improvements). No heartbeat file: listed."""
    if lines is None:
        acc.missing.append('the %s stage heartbeats%s' % (stage, cite(source)))
        return
    if not lines:
        acc.missing.append('any %s heartbeat sample (the file is empty)%s' % (stage, cite(source)))
        return
    phases, seen = [], set()
    for line in lines:
        phase = line.get('phase')
        if phase is not None and phase not in seen:
            seen.add(phase)
            phases.append((phase, line.get('utc'), line.get('elapsed_s')))
    acc.actions += ['', 'The phases my heartbeat saw, in order, with when each was first seen%s:' % cite(source, 'phase'), '']
    acc.actions += (table(['phase', 'first seen (UTC)', 'elapsed s'], [(p, show(u), show(e)) for p, u, e in phases])
                    if phases else ['- ' + NOT_RECORDED + ' (no sample names a phase).'])
    last = lines[-1]
    acc.actions += ['', '- My heartbeat ran from %s to %s, %s seconds, %d samples; the last sample says outcome %s%s.' % (
        show(lines[0].get('utc')), show(last.get('utc')), show(last.get('elapsed_s')), len(lines),
        show(last.get('outcome')), cite(source, 'utc,elapsed_s,outcome'))]
    # where the time went by phase: each phase from its first sample to the next phase's first sample (or the last
    # sample), from the recorded elapsed_s; a phase whose bounds are not recorded is said so
    spans = []
    for i, (phase, utc, start) in enumerate(phases):
        end = phases[i + 1][2] if i + 1 < len(phases) else last.get('elapsed_s')
        spans.append((phase, round(end - start, 1) if isinstance(start, (int, float)) and isinstance(end, (int, float))
                      else None))
    if spans:
        _shares(acc, {p: s for p, s in spans}, source, 'elapsed_s by phase', 'phase')
    rss = [(line.get('rss_bytes'), line.get('utc')) for line in lines if isinstance(line.get('rss_bytes'), int)]
    if rss:
        peak = max(rss, key=lambda item: item[0])
        acc.improvements.append('- My memory peak in the heartbeat samples: %s bytes (%.2f GiB) at %s%s.' % (
            peak[0], peak[0] / 2 ** 30, show(peak[1]), cite(source, 'rss_bytes')))
    else:
        acc.missing.append('the memory of my process tree%s' % cite(source, 'rss_bytes'))
    idle = []
    for line in lines:
        busy, held = line.get('cpus_busy'), _cpu_count(line.get('cpu_ranges'))
        if isinstance(busy, (int, float)) and held and busy < held:
            idle.append((show(line.get('utc')), show(line.get('phase')), busy, held, round(held - busy, 2)))
    if idle:
        acc.improvements += ['', 'Samples where fewer CPUs were busy than I held (each one; the idle CPUs are the '
                             'difference)%s:' % cite(source, 'cpus_busy,cpu_ranges'), '']
        acc.improvements += table(['UTC', 'phase', 'CPUs busy', 'CPUs held', 'CPUs idle'], idle) + ['']
    elif not any(isinstance(line.get('cpus_busy'), (int, float)) for line in lines):
        acc.missing.append('how many CPUs were busy%s' % cite(source, 'cpus_busy'))


# ---------------------------------------------------------------------------------------------------------- ROOT
def root_account(receipt, derive, workers, gates, beats, sources):
    """ROOT's account: calculations-receipt.json, work/derive.json, the bedrock runtime-workers receipt and
    pre-traversal gates, the root stage heartbeats. `sources`: {role: the path string to cite}."""
    F, acc = ROOT_FIELDS, Account()
    R, D = sources.get('receipt', F['receipt']), sources.get('derive', F['derive'])
    receipt, derive = receipt or {}, derive or {}
    if not receipt:
        acc.missing.append('the calculations receipt%s' % cite(R))
    # ---- actions
    processes = receipt.get(F['processes'])
    if isinstance(processes, dict):
        for name, state in processes.items():
            acc.actions.append('- I %s the process %s%s.' % ('ran' if state == 'run' else 'did not run (%s)' % state,
                                                              name, cite(R, F['processes'], name)))
    else:
        acc.fact('actions', 'Which processes I ran', None, R, F['processes'])
    for item in receipt.get(F['not_run']) or []:
        acc.actions.append('- Not run: %s, because %s%s.' % (show(item.get('process')), show(item.get('reason')),
                                                             cite(R, F['not_run'])))
    for key in ('source_writes', 'source_replays', 'model_calls'):
        acc.fact('actions', 'My %s' % key.replace('_', ' '), receipt.get(F[key]), R, F[key])
    for key, label in (('policy', 'The native calculation policy I ran under'), ('execution', 'How I used my lane'),
                       ('spool_reopen', 'What each legacy spool was reopened from'),
                       ('retained', 'How the retained evidence was checked')):
        value = receipt.get(F[key])
        if value is None:
            acc.fact('actions', label, None, R, F[key])
        else:
            acc.actions += ['', '%s (every recorded field)%s:' % (label, cite(R, F[key])), '']
            acc.actions += record_table(value, R, F[key]) + ['']
    bedrock = derive.get(F['bedrock'])
    if isinstance(bedrock, dict):
        for key in ('groups', 'records', 'span_seconds', 'derived', 'could_not', 'verdict', 'candidate_warmup_seconds',
                    'candidate_min_observations', 'skipped', 'reason'):
            if key in bedrock:
                acc.fact('actions', 'The native pass: %s' % key.replace('_', ' '), bedrock.get(key), D, F['bedrock'], key)
        if bedrock.get('sections'):
            acc.actions += ['', 'The native sections and their status%s:' % cite(D, F['bedrock'], 'sections'), '']
            acc.actions += table(['section', 'status'], list(bedrock['sections'].items()))
    elif F['bedrock'] in derive:
        acc.fact('actions', 'The native pass', bedrock, D, F['bedrock'])
    for name, value, role in (('runtime workers', workers, 'workers'), ('pre-traversal gates', gates, 'gates')):
        src = sources.get(role, F[role])
        if value is None:
            acc.missing.append('the native %s receipt%s' % (name, cite(src)))
        else:
            acc.actions += ['', 'The native %s (every recorded field)%s:' % (name, cite(src)), '']
            acc.actions += record_table(value, src, '') + ['']
    heartbeat(acc, beats, sources.get('heartbeat', 'progress/root.jsonl'), 'root')
    # ---- outputs
    layers = derive.get(F['layers'])
    layer_rows = []
    if isinstance(layers, dict):
        for name, entry in layers.items():
            entry = entry if isinstance(entry, dict) else dict(value=entry)
            layer_rows.append((name, show(entry.get('status')), show(entry.get('rows', entry.get('count'))),
                               show(entry.get('bytes')), show(entry.get('reason')), '%s#%s.%s' % (D, F['layers'], name)))
    blayers = (bedrock or {}).get('layers') if isinstance(bedrock, dict) else None
    if isinstance(blayers, dict):
        blayers = [dict(v, name=k) if isinstance(v, dict) else dict(name=k, value=v) for k, v in blayers.items()]
    for i, entry in enumerate(blayers or []):
        if isinstance(entry, dict):
            layer_rows.append((show(entry.get('name') or entry.get('layer')), show(entry.get('status')),
                               show(entry.get('rows', entry.get('count'))), show(entry.get('bytes')),
                               show(entry.get('reason')), '%s#%s.layers[%d]' % (D, F['bedrock'], i)))
    if layer_rows:
        derived = sum(1 for r in layer_rows if r[1] == 'derived')
        acc.outputs += ['I filed %d layers: %d derived, %d not derived, each with its status, rows, bytes and reason%s:' % (
            len(layer_rows), derived, len(layer_rows) - derived, cite(D, F['layers'] + ',' + F['bedrock'] + '.layers')), '']
        acc.outputs += table(['layer', 'status', 'rows', 'bytes', 'reason', 'from'], layer_rows) + ['']
    else:
        acc.fact('outputs', 'My layers', None, D, F['layers'])
    ledgers = (bedrock or {}).get('ledgers') if isinstance(bedrock, dict) else None
    if ledgers is not None:
        acc.outputs += ['My native ledgers (every recorded field)%s:' % cite(D, F['bedrock'], 'ledgers'), '']
        acc.outputs += record_table(ledgers, D, '%s.ledgers' % F['bedrock']) + ['']
    else:
        acc.missing.append('my native ledgers%s' % cite(D, F['bedrock'], 'ledgers'))
    pins = [(name, receipt.get(name)) for name in F['pins']]
    acc.outputs += ['The files my receipt pins (path, bytes, sha256)%s:' % cite(R, ','.join(F['pins'])), '']
    acc.outputs += table(['file', 'path', 'bytes', 'sha256'],
                         [(name, show((p or {}).get('path')), show((p or {}).get('bytes')), show((p or {}).get('sha256')))
                          for name, p in pins]) + ['']
    for name, p in pins:
        if p is None:
            acc.missing.append('the %s pin%s' % (name, cite(R, name)))
    market = receipt.get(F['market_sources'])
    if market:
        acc.outputs += ['The market spools I published for the shared reader%s:' % cite(R, F['market_sources']), '']
        acc.outputs += record_table(market, R, F['market_sources']) + ['']
    acc.fact('outputs', 'My status', receipt.get(F['status']), R, F['status'])
    # ---- improvements
    acc.fact('improvements', 'Records a producer could not use', receipt.get(F['failures']), R, F['failures'])
    for name, status, rows, size, reason, src in layer_rows:
        if status != 'derived':
            acc.improvements.append('- The layer %s is %s: %s [%s].' % (name, status, reason, src))
    for key in ('spool_reopen', 'retained'):
        value = receipt.get(F[key])
        items = value.get('artifacts') if isinstance(value, dict) else value
        for i, item in enumerate(items or []):
            basis = str((item or {}).get('basis', ''))
            if 'read whole' in basis or ('claim' not in basis and basis):
                acc.improvements.append('- I read %s again whole: %s%s.' % (show(item.get('path') or item.get('name')),
                                                                         basis, cite(R, F[key], i, 'basis')))
    if isinstance(bedrock, dict) and isinstance(bedrock.get('records'), (int, float)) and \
            isinstance(bedrock.get('span_seconds'), (int, float)):
        pass                                             # span_seconds is market time, not my time: no rate from it
    return acc


def root_found(receipt, derive, sources):
    """ROOT's 'What I found': the bedrock planes' row counts, the opening book, the input / legacy counts."""
    F = ROOT_FIELDS
    R, D = sources.get('receipt', F['receipt']), sources.get('derive', F['derive'])
    receipt, derive = receipt or {}, derive or {}
    L = ['## What I found', '']
    for key in F['counts']:
        if key in derive:
            L.append('- %s: %s%s.' % (key.replace('_', ' ').capitalize(), show(derive[key]), cite(D, key)))
    bedrock = derive.get(F['bedrock']) if isinstance(derive.get(F['bedrock']), dict) else {}
    for key in ('groups', 'records', 'derived', 'could_not'):
        if key in bedrock:
            L.append('- The native pass %s: %s%s.' % (key.replace('_', ' '), show(bedrock[key]), cite(D, F['bedrock'], key)))
    if bedrock.get('reconciliation') is not None:
        L += ['', 'The native reconciliation (every recorded field)%s:' % cite(D, F['bedrock'], 'reconciliation'), '']
        L += record_table(bedrock['reconciliation'], D, '%s.reconciliation' % F['bedrock'])
    book = receipt.get(F['opening_book'])
    L += ['', 'The opening book (every recorded field)%s:' % cite(R, F['opening_book']), '']
    L += record_table(book, R, F['opening_book']) if book is not None else ['- ' + NOT_RECORDED + '.']
    return L + ['']


# ------------------------------------------------------------------------------------------------------- teacher
def teacher_actions(acc, teacher, source, beats, beats_source):
    F = TEACHER_FIELDS
    teacher = teacher or {}
    runtime = (teacher.get(F['account']) or {}).get(F['runtime']) or {}
    phases = runtime.get(F['phases'])
    if phases:
        acc.actions += ['My phases, in the order I recorded them, with their seconds%s:' % cite(
            source, F['account'], F['runtime'], F['phases']), '']
        acc.actions += table(['phase', 'seconds'], [(k, show(v)) for k, v in phases.items()]) + ['']
    else:
        acc.fact('actions', 'My phases', None, source, F['account'], F['runtime'], F['phases'])
    for key in F['counts']:
        acc.fact('actions', 'My %s' % key.replace('_', ' '), teacher.get(key), source, key)
    cpu = teacher.get(F['cpu'])
    if cpu is not None:
        acc.actions += ['', 'Where my work ran (every recorded field)%s:' % cite(source, F['cpu']), '']
        acc.actions += record_table(cpu, source, F['cpu'])
    heartbeat(acc, beats, beats_source, 'teacher')
    for key in F['outputs']:
        value = teacher.get(key)
        if value is None:
            acc.missing.append('my %s%s' % (key.replace('_', ' '), cite(source, key)))
            continue
        acc.outputs += ['My %s (every recorded field)%s:' % (key.replace('_', ' '), cite(source, key)), '']
        acc.outputs += record_table(value, source, key) + ['']
    _shares(acc, phases, source, '%s.%s.%s' % (F['account'], F['runtime'], F['phases']), 'phase')
    for key in ('rows_per_second', 'memory_peak_kib'):
        acc.fact('improvements', 'My %s' % key.replace('_', ' '), runtime.get(key), source, F['account'], F['runtime'], key)
    one = runtime.get('one_pass') or {}
    for key, value in one.items():
        if isinstance(value, (int, float)) and value and 'again' in key:
            acc.improvements.append('- Rows I read again: %s = %s%s.' % (key, show(value),
                                                                       cite(source, F['account'], F['runtime'], 'one_pass', key)))


# ----------------------------------------------------------------------------------------------------- classroom
def classroom_account(receipt, source, beats, beats_source):
    F, acc = CLASSROOM_FIELDS, Account()
    receipt = receipt or {}
    timings = receipt.get(F['phases'])
    if timings:
        acc.actions += ['My phases, in the order I recorded them: computed or restored from a save, and seconds%s:' % cite(
            source, F['phases']), '']
        acc.actions += table(['phase', 'restored from a save', 'seconds'],
                             [(k, show((v or {}).get('restored') if isinstance(v, dict) else None),
                               show((v or {}).get('seconds') if isinstance(v, dict) else v)) for k, v in timings.items()]) + ['']
    else:
        acc.fact('actions', 'My phases', None, source, F['phases'])
    acc.fact('actions', 'My seconds in all', receipt.get(F['seconds']), source, F['seconds'])
    received = receipt.get(F['received']) or {}
    for key in (F['side'], F['cpu']):
        value = received.get(key)
        if value is None:
            acc.missing.append('my %s%s' % (key.replace('_', ' '), cite(source, F['received'], key)))
        else:
            acc.actions += ['', 'My %s (every recorded field)%s:' % (key.replace('_', ' '), cite(source, F['received'], key)), '']
            acc.actions += record_table(value, source, '%s.%s' % (F['received'], key))
    heartbeat(acc, beats, beats_source, 'classroom')
    outputs = receipt.get(F['outputs']) or {}
    pinned = outputs.get('pinned') or {}
    if pinned:
        acc.outputs += ['The files I produced, each with its pin%s:' % cite(source, F['outputs'], 'pinned'), '']
        acc.outputs += table(['file', 'bytes', 'sha256'],
                             [(name, show((p or {}).get('bytes')), show((p or {}).get('sha256'))) for name, p in pinned.items()]) + ['']
    else:
        acc.fact('outputs', 'The files I produced', None, source, F['outputs'], 'pinned')
    for item in outputs.get('listed') or []:
        acc.outputs.append('- Not produced: %s (%s)%s.' % (show(item.get('name')), show(item.get('reason')),
                                                          cite(source, F['outputs'], 'listed')))
    entry = outputs.get('brain_entry') or {}
    if entry:
        acc.outputs += ['', 'The brain entry I filed: %s%s:' % (show(entry.get('path')), cite(source, F['outputs'], 'brain_entry')), '']
        acc.outputs += table(['file', 'bytes', 'sha256', 'include'],
                             [(show(e.get('name')), show(e.get('bytes')), show(e.get('sha256')), show(e.get('include')))
                              for e in entry.get('manifest_entries') or []]) + ['']
    _shares(acc, timings, source, F['phases'], 'phase')
    restored = [k for k, v in (timings or {}).items() if isinstance(v, dict) and v.get('restored')]
    if restored:
        acc.improvements.append('- Phases restored from a save (computed in an earlier attempt): %s%s.' % (
            ', '.join(restored), cite(source, F['phases'])))
    native = received.get(F['native']) or receipt.get(F['native']) or {}
    for key in ('elapsed_native_seconds', 'peak_rss', 'status', 'series_not_computed'):
        if key in native:
            acc.fact('improvements', 'My native entry arithmetic: %s' % key.replace('_', ' '), native.get(key), source,
                     F['native'], key)
    second = received.get(F['second_set']) or receipt.get(F['second_set'])
    if isinstance(second, dict):
        for role, listing in (second.get('absent') or {}).items():
            acc.improvements.append('- The teacher\'s second set had no %s on %s rows%s.' % (
                role, show(listing.get('rows')), cite(source, F['received'], F['second_set'], 'absent', role)))
        for key in ('mismatched_rows', 'key_cursor_differs'):
            if second.get(key):
                acc.improvements.append('- Second-set %s: %d rows%s.' % (key.replace('_', ' '), len(second[key]),
                                                                       cite(source, F['received'], F['second_set'], key)))
        resolver = ((second.get('anchors_resolved') or {}).get('resolver') or {})
        if resolver.get('note'):
            acc.improvements.append('- %s%s.' % (resolver['note'], cite(source, F['received'], F['second_set'],
                                                                         'anchors_resolved.resolver.note')))
    elif second is None:
        acc.missing.append('the teacher\'s second set I received%s' % cite(source, F['received'], F['second_set']))
    return acc


def read_heartbeats(path):
    """The samples of one stage heartbeat file (JSON lines), or None when the file is not there."""
    path = Path(path)
    if not path.is_file():
        return None
    out = []
    for line in path.read_bytes().splitlines():
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict):
            out.append(value)
    return out
