"""Frankie's data wish list: of the data points he will have wired in when live, which ones his own brain leans on and
the Tue/Wed experiment days do not carry (Greg, 2026-09-29: "ask frankie ... what are his top 10 datapoints from the
over 1900 he'll have wired in when live that he would like historic data for going forward for the next tue/wed runs?
We'll just have to find historical data somewhere").

Frankie has no model seat (SPEC-scientific-teacher: no seat is a model; Granite is not Frankie). So the question is put
to his brain, the CURRENT_BRAIN of his knowledge bundle (research/kalshi/knowledge/ng_brain.json, 90 plays), and his
answer is what his plays depend on, counted, never scored or averaged:
  conditions  plays whose parsed conditions name the data point as their state_path (the strongest: the play cannot
              be evaluated without it);
  text        plays whose trigger, read, call, caveats, falsifier, condition state or health name it (its full dotted
              path, or its field name when that name is distinctive: has an underscore and 8+ characters);
  declines    recorded instances that name it next to an absent/null/not-served input (a play stood down on it).
The universe is the live wiring list, research/kalshi/store/data_points.json (served data points; the registry's own
render DATA_POINTS.md counts served, held, planned, identified and absent). Array indices are folded ([0]..[3] -> []);
a field name shared by several paths credits each and is flagged.

The answer is ranked BY SOURCE FAMILY first (the registry's block: one historical source each, e.g. EIA weekly storage,
CFTC positioning, hourly weather), counting every play that names the family or any of its data points anywhere in its
body. Greg, 2026-09-29, on the first cut (which ordered by parsed conditions and left storage out): "I would think
storage would be one". It is: 33 plays name it, but none of them carries a parsed state_path, so a
conditions-first order undercounts every family whose plays are written in prose. The per-point table follows the
families, nothing dropped.

Already carried on the experiment days (listed, not wished for): anything computed from the NYMEX tape the ingest holds
(Databento MBO), from the exchange/index calendar, the day of week, holidays and free-text notes. Everything else needs a
historical source. Nothing is dropped: the full ranked table is written beside the top 10.

    python3 research/kalshi/frankie_boss/operations/frankie_data_wishlist.py --write
"""
import argparse
import collections
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BRAIN = ROOT / 'research/kalshi/knowledge/ng_brain.json'
REGISTRY = ROOT / 'research/kalshi/store/data_points.json'
OUT = ROOT / 'research/kalshi/frankie_boss/FRANKIE_DATA_WISHLIST_20260929'
TEXT_FIELDS = ('trigger', 'read', 'call', 'caveats', 'falsifier', 'conditions_state', 'health')
CARRIED_BLOCKS = {'tape_conditions', 'vol_regime', 'firehose_present', 'flow_calendar', 'dow', 'holiday', 'note'}
CARRIED_SOURCE_WORDS = ('Databento', 'calendar', 'day of week', 'free-text')
ABSENT = re.compile(r'DATA_ABSENT|INPUT_ABSENT|\babsent\b|not served|\bnull\b')


def fold(path):
    return re.sub(r'\[\d+\]', '[]', path)


def carried(entry):
    return (entry.get('block') in CARRIED_BLOCKS
            or any(w in (entry.get('upstream_source') or '') for w in CARRIED_SOURCE_WORDS))


def rank():
    brain = json.loads(BRAIN.read_bytes())
    served = json.loads(REGISTRY.read_bytes())['served']
    points = {}
    for d in served:
        points.setdefault(fold(d['path']), d)
    leaf_owners = collections.defaultdict(set)
    for p in points:
        leaf_owners[p.split('.')[-1].replace('[]', '')].add(p)
    patterns = {}
    for p in points:
        leaf = p.split('.')[-1].replace('[]', '')
        alts = [re.escape(p).replace(r'\[\]', r'\[\d*\]')]
        if '_' in leaf and len(leaf) >= 8:
            alts.append(r'\b' + re.escape(leaf) + r'\b')
        patterns[p] = re.compile('|'.join(alts))
    cond, text, declines = (collections.defaultdict(set) for _ in range(3))
    status = {play['id']: play.get('status') for play in brain['plays']}
    for play in brain['plays']:
        for c in play.get('conditions') or ():
            if c.get('state_path'):
                cond[fold(c['state_path'])].add(play['id'])
        body = json.dumps({k: play.get(k) for k in TEXT_FIELDS})
        for p, rx in patterns.items():
            if rx.search(body):
                text[p].add(play['id'])
        for inst in play.get('instances') or ():
            s = json.dumps(inst)
            if ABSENT.search(s):
                for p, rx in patterns.items():
                    if rx.search(s):
                        declines[p].add('%s@%s' % (play['id'], inst.get('date')))
    rows = []
    for p in sorted(set(cond) | set(text) | set(declines)):
        d = points.get(p, {})
        plays = cond[p] | text[p]
        leaf = p.split('.')[-1].replace('[]', '')
        rows.append(dict(
            path=p, in_live_list=p in points, block=d.get('block', p.split('.')[0]),
            upstream_source=d.get('upstream_source'), cadence=d.get('cadence'),
            carried_on_experiment_days=carried(d) if d else None,
            plays=len(plays), plays_by_condition=len(cond[p]), plays_by_text=len(text[p]), declines=len(declines[p]),
            play_ids=sorted(plays), play_status=dict(collections.Counter(status.get(i) for i in plays)),
            field_name_shared_with=sorted(leaf_owners[leaf] - {p}) if len(leaf_owners[leaf]) > 1 else [],
            whole_block=('.' not in p)))
    rows.sort(key=lambda r: (-r['plays_by_condition'], -r['plays'], -r['declines'], r['path']))
    families = []
    by_block, leaf_blocks = collections.defaultdict(list), collections.defaultdict(set)
    for d in served:
        by_block[d['block']].append(d)
        leaf_blocks[fold(d['path']).split('.')[-1].replace('[]', '')].add(d['block'])
    for blk, items in by_block.items():
        paths = [fold(d['path']) for d in items]
        # a field name another family also uses (age_days, week_ending, ...) never credits this family: full paths only
        alts = [r'\b' + re.escape(blk) + r'\b']
        for x in dict.fromkeys(paths):
            leaf = x.split('.')[-1].replace('[]', '')
            alts.append(patterns[x].pattern if leaf_blocks[leaf] == {blk} else re.escape(x).replace(r'\[\]', r'\[\d*\]'))
        rx = re.compile('|'.join(alts))
        named, by_cond = set(), set()
        for play in brain['plays']:
            if rx.search(json.dumps(play)):
                named.add(play['id'])
            if any(fold(c.get('state_path') or '').startswith(blk) for c in play.get('conditions') or ()):
                by_cond.add(play['id'])
        if not named:
            continue
        fields = sorted(((len(cond[x] | text[x]), x) for x in dict.fromkeys(paths) if cond[x] | text[x]), reverse=True)
        families.append(dict(family=blk, upstream_source=items[0].get('upstream_source'), cadence=items[0].get('cadence'),
                             data_points=len(items), plays=len(named), plays_by_condition=len(by_cond),
                             carried_on_experiment_days=carried(items[0]),
                             play_status=dict(collections.Counter(status.get(i) for i in named)),
                             fields_named=[dict(path=x, plays=n) for n, x in fields]))
    families.sort(key=lambda f: (-f['plays'], -f['plays_by_condition'], f['family']))
    wish = [r for r in rows if r['in_live_list'] and not r['whole_block'] and r['carried_on_experiment_days'] is False]
    return dict(
        schema='FRANKIE_DATA_WISHLIST_V1', asked_by='Greg, 2026-09-29', answered_by="Frankie's brain (code, no model)",
        brain=dict(path=str(BRAIN.relative_to(ROOT)), sha256=hashlib.sha256(BRAIN.read_bytes()).hexdigest(),
                   plays=len(brain['plays']), version=brain.get('meta', {}).get('version')),
        live_list=dict(path=str(REGISTRY.relative_to(ROOT)), sha256=hashlib.sha256(REGISTRY.read_bytes()).hexdigest(),
                       served_points=len(served), folded_points=len(points)),
        order='families: plays naming the family or any of its points; points: parsed conditions, all plays, declines',
        top10_families=[f for f in families if not f['carried_on_experiment_days']][:10],
        rest_families=[f for f in families if not f['carried_on_experiment_days']][10:],
        carried_families=[f for f in families if f['carried_on_experiment_days']],
        top10=wish[:10], rest_wished=wish[10:],
        carried=[r for r in rows if r['carried_on_experiment_days']],
        whole_blocks=[r for r in rows if r['whole_block']],
        not_in_live_list=[r for r in rows if not r['in_live_list'] and not r['whole_block']])


def render(doc):
    line = lambda r: '| %s | %s | %d | %d | %d | %s |' % (
        r['path'], r['upstream_source'] or '-', r['plays_by_condition'], r['plays'], r['declines'],
        ', '.join('%s %d' % kv for kv in sorted(r['play_status'].items(), key=lambda kv: str(kv[0]))))
    head = ['| data point | source | plays (condition) | plays (all) | declines | play status |', '|---|---|---|---|---|---|']
    out = ["# Frankie's data wish list (2026-09-29)", '',
           "Greg asked: of the data points Frankie will have wired in when live, which 10 would he like historical data for",
           "on the next Tue/Wed runs. Frankie has no model seat, so his brain answers: what his %d plays depend on, counted "
           "(`operations/frankie_data_wishlist.py`, brain sha256 %s, live list %d served points)."
           % (doc['brain']['plays'], doc['brain']['sha256'][:12], doc['live_list']['served_points']), '',
           'Order: %s. Counts, never a score (D37).' % doc['order'], '',
           '## His top 10 sources (not carried on the experiment days; history is needed)', '',
           '| # | source family | source | cadence | plays naming it | of them by parsed condition | data points | the points his plays name |',
           '|---|---|---|---|---|---|---|---|']
    out += ['| %d | %s | %s | %s | %d | %d | %d | %s |' % (i, f['family'], f['upstream_source'] or '-', f['cadence'] or '-', f['plays'],
            f['plays_by_condition'], f['data_points'], ', '.join('%s (%d)' % (x['path'], x['plays']) for x in f['fields_named'][:6]) or '-')
            for i, f in enumerate(doc['top10_families'], 1)]
    fam = lambda f: '| %s | %s | %d | %d |' % (f['family'], f['upstream_source'] or '-', f['plays'], f['data_points'])
    out += ['', '## The other source families he names', '', '| family | source | plays | data points |', '|---|---|---|---|']
    out += [fam(f) for f in doc['rest_families']]
    out += ['', '## Families already carried on the experiment days', '', '| family | source | plays | data points |', '|---|---|---|---|']
    out += [fam(f) for f in doc['carried_families']]
    out += ['', '## His top 10 single data points (parsed conditions first)', ''] + head
    out += [line(r) for r in doc['top10']]
    out += ['', '## The rest he names (same order, nothing dropped)', ''] + head + [line(r) for r in doc['rest_wished']]
    out += ['', '## Single data points already carried on the experiment days (tape, calendar), not wished for', ''] + head
    out += [line(r) for r in doc['carried']]
    out += ['', '## Whole blocks named in prose (not one data point)', ''] + head + [line(r) for r in doc['whole_blocks']]
    if doc['not_in_live_list']:
        out += ['', '## Named by a play but not in the live list', ''] + head + [line(r) for r in doc['not_in_live_list']]
    return '\n'.join(out) + '\n'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--write', action='store_true')
    a = ap.parse_args()
    doc = rank()
    if a.write:
        OUT.with_suffix('.json').write_text(json.dumps(doc, indent=1, sort_keys=True))
        OUT.with_suffix('.md').write_text(render(doc))
    for i, f in enumerate(doc['top10_families'], 1):
        print('%2d. %-20s %3d plays (%d by condition)  %s  | %s' % (i, f['family'], f['plays'], f['plays_by_condition'],
              f['upstream_source'], ', '.join(x['path'] for x in f['fields_named'][:4])))


if __name__ == '__main__':
    main()
