"""Extend the saved two-day watchlist comparison without rerunning any producer."""

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

from audit_october18_touch_mechanisms import capture_groups, git_blob, git_rows, TOUCH
from research_dipole_cell_drift import cells, score

REVISION = '5e39ddc7e'
ROOT = 'tasks/family-research-20261022/claude-code'
DAY0_18 = 1697576400


def load(name):
    raw = git_blob(REVISION, f'{ROOT}/{name}')
    return raw, [json.loads(line) for line in gzip.decompress(raw).splitlines()]


def outcome(row):
    call, move = row['sources']['next_seed'], row['targets']['net300']
    return ('no_call' if call not in (-1, 1) else 'unavailable' if move is None else
            'flat' if move == 0 else 'with' if call * move > 0 else 'against')


def main(output):
    datasets, pins = {}, {}
    for tag in ('oct02', 'oct03', 'oct17', 'oct18'):
        name = f'stack-direction-sources-{tag}-events.jsonl.gz'
        raw, datasets[tag] = load(name)
        pins[tag] = dict(path=f'{ROOT}/{name}', sha256=hashlib.sha256(raw).hexdigest())
    volumes = sorted(row['pre300_volume'] for row in datasets['oct18'])
    cuts = volumes[len(volumes)//3], volumes[2*len(volumes)//3]
    result = dict(revision=REVISION, inputs=pins, common_oct18_cuts=cuts, variants={}, examples=[])
    for variant, bounds in (('day_native_cuts', None), ('shared_oct18_cuts', cuts)):
        days = {}
        for tag, rows in datasets.items():
            table = cells(rows, bounds)
            watched = [r for r in rows if r['a_state'] == 'A-fast-collapse' and
                       (r['vol_tercile'] == 'mid' if bounds is None else bounds[0] < r['pre300_volume'] <= bounds[1])]
            selected = {source: {target: score(watched, source, target)
                                 for target in ('net300', 'net600', 'first3')}
                        for source in ('next_seed', 'book10')}
            for row in selected.values():
                for value in row.values():
                    if value:
                        assert sum(value[k] for k in ('n', 'flat', 'unavailable', 'no_call')) == len(watched)
            if bounds is None:
                original = json.loads(git_blob(REVISION, f'{ROOT}/stack-direction-sources-{tag}-summary.json'))
                for source, targets in selected.items():
                    for target, value in targets.items():
                        saved = original['by_state_x_tercile']['A-fast-collapse|mid'][source][target]
                        assert (value['hits'], value['flat'], value['n']-value['hits']) == (saved['with_'], saved['flat'], saved['against'])
            days[tag] = dict(events=len(rows), watchlist_population=len(watched), watchlist=selected,
                             dispositions=dict(Counter(map(outcome, watched))), cells=table)
        result['variants'][variant] = days

    # Earliest post-midnight October 18 case in each outcome class; no selection by move size.
    examples = {}
    for row in datasets['oct18']:
        if row['a_state'] == 'A-fast-collapse' and row['vol_tercile'] == 'mid' and row['t0'] >= 10800:
            examples.setdefault(outcome(row), row)
    waiting = sorted((DAY0_18 + row['t0'] + 60, label, row) for label, row in examples.items()
                     if label in ('with', 'against', 'flat'))
    snapshots, selected_groups = {}, []
    prior = None
    for row in git_rows(TOUCH):
        if waiting and prior and row['prints'] and row['receive_ns'] >= waiting[0][0]*1_000_000_000:
            anchor, label, case = waiting.pop(0)
            snapshots[row['close_cursor']] = (prior, row)
            selected_groups.append(dict(outcome=label, candidate=case, anchor_ns=anchor*1_000_000_000,
                                        first_print_group= row, prior_group=prior))
        prior = row
        if not waiting:
            break
    assert not waiting
    traces = capture_groups(snapshots)
    for item in selected_groups:
        item['order_trace'] = traces[item['first_print_group']['close_cursor']]
    result['examples'] = selected_groups
    result['scope'] = ('All four are full-session raw-tape research, including the October 1/16 prefixes. '
                       'Original October 2/17 RunPod outputs remain partial. Historical t0+60 anchor; '
                       'seed is labeled known at t0+61 in its source, and day-native activity cuts are retrospective. '
                       'These retained counts are not simulator entry results. Hourly margins use realized outcomes. '
                       'Example anchor_ns is the START of the nominal anchor second; a print within that '
                       'second may already contribute to the anchor input and is not a postdecision observation.')
    output.write_bytes(gzip.compress((json.dumps(result, sort_keys=True)+'\n').encode(), mtime=0))
    for variant, days in result['variants'].items():
        for tag, data in days.items():
            print(variant, tag, data['watchlist_population'], data['dispositions'], data['watchlist']['next_seed']['net300'])
    for item in selected_groups:
        print('example', item['outcome'], item['candidate']['t0'], item['candidate']['sources']['next_seed'],
              item['candidate']['targets']['net300'], item['first_print_group']['group_ordinal'], item['order_trace']['messages'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    main(parser.parse_args().output)
