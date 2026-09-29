"""Historical Dipole claims for the scientific teacher: HISTORICAL_CLAIMS_V1 from the shared Dipole catalog.

Brief piece B (CHATGPT_BRIEF_EXPERIMENT_20260929.md), built by Claude on Greg's word ("I'm going to have you do
chatgpts part", 2026-09-29). Rule R11: every entry is a CLAIM with its author ('historical') and its source, never truth.
No model reads anything here (R17); this is code over committed bytes.

INPUT. `research/kalshi/frankie_boss/knowledge/DIPOLE_SHARED_CATALOG_20260922.json` (127 sources, review groups K01-K10)
and `research/kalshi/frankie_boss/DIPOLE_KNOWLEDGE_GAP_REVIEW_20260922.md`. Every source is read at the catalog's own
revision (`git show <revision>:<path>`) and its sha256 must equal the catalog's; the working tree is used only when its
bytes carry that same sha256. A source that cannot be read with the catalog's bytes is listed, never read another way.

THREE PARTS, all in the output:
1. candidates: every statement the extractor finds, mechanically, with file:line (or file#json-path):
     .md    every list item (numbered or bulleted) and every table body row;
     .json  every string under a key that names a statement (CLAIM_KEYS), with its JSON path;
     .py    the source itself, once (code defines constructions and methods; its claims live in the prose sources and
            in the crosswalk below, which anchors into docstrings where a claim is stated there).
   The extraction rule and the count of lines it did not take are recorded per source.
2. claims: the CROSSWALK below, a declared table authored in the repository (by Claude, 2026-09-29, from reading the
   sources; Greg may amend it). Each entry names its source by catalog id and a verbatim ANCHOR that must be found in the
   source's catalog bytes (whitespace-insensitive); the line it is found on is recorded. An entry whose anchor is not
   found is NOT a claim: it goes to not_testable with that reason. Each claim's series must be names the search carries
   (SEARCH_SERIES); a series it does not carry sends the claim to not_testable with the missing names.
3. not_testable: every candidate no verified crosswalk entry covers, every unreadable source and every failed crosswalk
   entry, each with its reason. "No crosswalk entry" means it was not put in testable form here, not that it cannot be.

K01 (keep the constructions distinct): every claim carries `construction` (what the source measured) and
`search_construction` (the nearest series the search carries and how it differs); a centroid-projection claim is never
filed as a C15R3 component claim. The review groups are copied with their headings and status lines.

Output: research/kalshi/frankie_boss/knowledge/HISTORICAL_CLAIMS_V1-<catalog sha12>.json, COMMITTED. It is built where
git history exists (a full clone), not on the box: the box's staged checkout carries one commit and no history, so the
eight sources that exist only at their catalog revision would read as unreadable there. The box's teacher reads the
committed file from its staged checkout (HISTORICAL_CLAIMS in frankie_box_scientific_teacher.sh). Idempotent by
content: the same catalog, crosswalk and builder give the same bytes (no clock in the document).
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

SCHEMA = 'HISTORICAL_CLAIMS_V1'
REPO = Path(__file__).resolve().parents[3]
CATALOG = 'research/kalshi/frankie_boss/knowledge/DIPOLE_SHARED_CATALOG_20260922.json'
REVIEW = 'research/kalshi/frankie_boss/DIPOLE_KNOWLEDGE_GAP_REVIEW_20260922.md'
OUT = REPO / 'research/kalshi/frankie_boss/knowledge'

# The search's series (frankie_box_experiment_search.build_series). Frames and structures are the ROOT legacy spools'
# numeric fields (frankie_box_boss_session: the F_LAST book + BOOK_FIELDS of a_memory_member_first_recalculation_20260828,
# describe_structure); prices the legacy trade rows; events.<action>_<side>[_size] and events.total per group;
# signed_flow buy/sell and roll20 per second; dipole.<component> the C15 normalizer's COLUMNS.
FRAME_FIELDS = ('best_bid', 'best_ask', 'mid', 'depth_imbalance_n', 'spread', 'depth_imbalance_full', 'bid_depth_full',
                'ask_depth_full', 'bid_order_count_full', 'ask_order_count_full', 'bid_price_level_count_full',
                'ask_price_level_count_full')
STRUCTURE_FIELDS = ('component_count', 'distinct_price_count', 'distinct_order_id_count', 'price_raw_min',
                    'price_raw_max', 'price_raw_span', 'matches_carried_native_family')
PRICE_FIELDS = ('price', 'size', 'bid_px_00', 'ask_px_00')
EVENT_PATTERN = re.compile(r'^events\.(total|[A-Z?]+_[A-Z?]+(_size)?)$')
CODE_CANDIDATE = '(source code: constructions and methods)'
CLAIM_KEYS = re.compile(r'(finding|claim|lesson|statement|call|rule|observation|result|conclusion|argument|read|trigger|'
                        r'what_the_day_did|falsifier|caveat|note)s?$', re.I)


def search_series():
    import ast                                # read, not executed: the pinned module's own literal (never edited)
    tree = ast.parse((REPO / 'research/kalshi/frankie_boss/c15_normalizer.py').read_text(encoding='utf-8'))
    COLUMNS = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                   and any(getattr(t, 'id', None) == 'COLUMNS' for t in node.targets))
    names = {'frames.' + f for f in FRAME_FIELDS} | {'structures.' + f for f in STRUCTURE_FIELDS} | \
        {'prices.' + f for f in PRICE_FIELDS} | {'signed_flow.buy', 'signed_flow.sell', 'roll20.value'} | \
        {'dipole.' + c for c in COLUMNS}
    return names


def carried(name, names):
    return name in names or bool(EVENT_PATTERN.match(name))


ROLL20 = ('roll20.value: the causal trailing 20-second signed aggressor-volume imbalance (buy-sell)/(buy+sell) at '
          'one-second resolution, known at the end of its second (native_roll20.roll20); 0 is balance (buy share 0.5)')
DEPTH_IMB = ('frames.depth_imbalance_full: full-depth (bid-ask)/(bid+ask) of the F_LAST book at each group close; '
             'positive = bid-heavy (Memory A: 1,342/698 -> 0.315686)')

# The crosswalk. Authored, declared, anchored; see the module docstring. direction: 'same' | 'opposite' | None
# (None = the source states no pairwise sign in testable form; counts are reported, nothing is marked).
CROSSWALK = (
    dict(id='H01', source_id='review.091', anchor='Strong divergence (aligned <= -0.20) -> ~65% reversal',
         statement='Order flow opposing the price drift (aligned_flow = imbalance level x sign(price drift) <= -0.20 '
                   'over the pre-entry window) precedes a reversal of the drift (~65%, early 70% / late 62%).',
         series=['roll20.value', 'frames.mid'], cells=[], condition='aligned_flow <= -0.20 over the pre-entry window',
         lag='x leads (the flow window precedes the reversal)', target='the next move of the mid against the drift',
         direction=None, review_group='K04',
         construction='odcore.info_dipole.divergence: imb_level over a window of buy/sell volume bars; crypto 1-minute '
                      'bars (btc/eth, 2-day trending window, pooled n=1560)',
         search_construction=ROLL20 + '; a transfer to NG MBO, and the condition is not applied by the search',
         evidence=['info_dipole.py docstring: ~65% reversal, early 70%/late 62%, per cell btc_bybit_sell 100%, '
                   'btc_kraken_buy 84%, btc_bybit_buy neutral']),
    dict(id='H02', source_id='review.091', anchor='EXHAUSTION  the order-flow dipole COLLAPSING toward 0.5',
         statement='The order-flow imbalance collapsing toward balance (|late-half imbalance| < |early-half|) marks the '
                   'leader weakening; stacked with opposing flow it precedes a reversal (64%, n=317).',
         series=['roll20.value', 'frames.mid'], cells=[], condition='|late-half imbalance| < |early-half imbalance|',
         lag='x leads', target='a reversal of the mid', direction=None, review_group='K04',
         construction='odcore.info_dipole.divergence exhausting flag; crypto 1-minute bars',
         search_construction=ROLL20 + '; the collapse (|imbalance| falling) is not one of the search transforms yet',
         evidence=['opposing+exhausting 64% (n=317) > opposing+strengthening 58% > with-trend+weakening 52% > '
                   'with-trend+strengthening 49%']),
    dict(id='H03', source_id='baseline.keep_research_kalshi_knowledge_ng_brain_json',
         anchor="NG's side = sign(dip_imb_level) when strong (|dip_imb_level| >= 0.15)",
         statement="NG's leg side follows the sign of the signed aggressor-flow imbalance when it is strong "
                   '(|dip_imb_level| >= 0.15).',
         series=['roll20.value', 'frames.mid'], cells=[], condition='|dip_imb_level| >= 0.15',
         lag='concurrent to x leads (flow around the trigger push vs the leg)', target='the direction of the leg',
         direction='same', review_group=None,
         construction='dip_imb_level: Lee-Ready signed flow imbalance over a ~300 s window around a leg trigger push '
                      '(NG MBP-10, S92/S95)',
         search_construction=ROLL20 + ' (20 s window, aggressor side from the tape, not Lee-Ready); the |0.15| '
                                      'condition is not applied by the search',
         evidence=['ng_brain: 1,537 legs cleared the bar; sign matched realized leg direction on 87.6 percent',
                   'S95: held-leg sign matched leg dir near-perfect on 5/6 pivotal days']),
    dict(id='H04', source_id='baseline.keep_research_kalshi_knowledge_ng_brain_json',
         anchor='fade the heavy resting side - ask-heavy book -> price runs UP through it (wall = fuel, not floor)',
         statement='When flow is flat, an ask-heavy resting book precedes the price running UP through it (and '
                   'bid-heavy down): the heavy side is fuel, not a floor.',
         series=['frames.depth_imbalance_full', 'frames.mid'], cells=[], condition='flow (dip_imb_level) flat or ambiguous',
         lag='x leads', target='the next move of the mid', direction='opposite', review_group=None,
         construction='imb_R: resting-book imbalance at entry (NG MBP-10, 10 levels)',
         search_construction=DEPTH_IMB + '; full depth, not 10 levels; the flat-flow condition is not applied',
         evidence=['ng_brain direction.book_contrarian: confidence 0.5, PROVISIONAL, support UNCLEAR']),
    dict(id='H05', source_id='baseline.keep_research_kalshi_knowledge_ng_brain_json',
         anchor='fade the heavy resting side - ask-heavy book -> price runs UP through it (wall = fuel, not floor)',
         statement='The same book-contrarian claim read on the top-of-book imbalance.',
         series=['frames.depth_imbalance_n', 'frames.mid'], cells=[], condition='flow flat or ambiguous',
         lag='x leads', target='the next move of the mid', direction='opposite', review_group=None,
         construction='imb_R: resting-book imbalance at entry (NG MBP-10, 10 levels)',
         search_construction='frames.depth_imbalance_n: the F_LAST book imbalance over its first n levels (the '
                             'adapter\'s n; not stated as 10 here)',
         evidence=['ng_brain direction.book_contrarian']),
    dict(id='H06', source_id='baseline.a_memory_promoted_positive_knowledge',
         anchor='Ask-withdrawal-led imbalance (Oct-04 close) and bid-accumulation-led imbalance (Oct-05 close) are '
                'distinct strata',
         statement='Bid-heaviness can be ask-withdrawal-led (the imbalance rises as ask depth falls) or '
                   'bid-accumulation-led (it rises as bid depth rises); the two are distinct strata.',
         series=['frames.depth_imbalance_full', 'frames.ask_depth_full'], cells=['close'],
         condition='the close of the day', lag='0', target='which side leads the imbalance', direction='opposite',
         review_group=None,
         construction='Memory A exact native MBO, Oct 4 and Oct 5 2021 closes (one slice each)',
         search_construction=DEPTH_IMB + '; construction-bound: the imbalance is computed from both depths, so '
                                         'opposite with ask depth is expected by construction; the finding is the '
                                         'count of ask-led against bid-led moves per cell and day (H07)',
         evidence=['Oct-04 close ask-withdrawal-led; Oct-05 bid-accumulation-led; Oct-05 imbalance 0.315686']),
    dict(id='H07', source_id='baseline.a_memory_promoted_positive_knowledge',
         anchor='Ask-withdrawal-led imbalance (Oct-04 close) and bid-accumulation-led imbalance (Oct-05 close) are '
                'distinct strata',
         statement='The bid-accumulation side of the same mechanism claim.',
         series=['frames.depth_imbalance_full', 'frames.bid_depth_full'], cells=['close'],
         condition='the close of the day', lag='0', target='which side leads the imbalance', direction='same',
         review_group=None, construction='Memory A exact native MBO, Oct 4 and Oct 5 2021 closes',
         search_construction=DEPTH_IMB + '; construction-bound as H06',
         evidence=['Oct-05 mean bid depth +21.85%, mean ask depth -0.54%']),
    dict(id='H08', source_id='baseline.a_memory_promoted_positive_knowledge',
         anchor='Use as a conditional stabilization/absorption hypothesis',
         statement='Late in a negative-drift window, a book that stays bid-heavy precedes a price rebound '
                   '(stabilization/absorption), conditional, not a locked direction.',
         series=['frames.depth_imbalance_full', 'frames.mid'], cells=['close'],
         condition='late in a negative-drift window with the final book bid-heavy', lag='x leads',
         target='the next move of the mid', direction='same', review_group=None,
         construction='Memory A: the 41-trade final-window motif, last 298.144 s rebound +0.002/+0.004 (Oct 5 2021)',
         search_construction=DEPTH_IMB + '; the condition is not applied; note H04 claims the opposite sign on the '
                                         'same pair (both are tested)',
         evidence=['+0.002 from the first T print, +0.004 from the first side-resolved T print; depth 1,342/698']),
    dict(id='H09', source_id='baseline.keep_research_kalshi_knowledge_ng_brain_json',
         anchor='turn_far_thinning DEMOTED to noise',
         statement='Far-side book thinning at a turn carries no direction (demoted to noise in the S95 fingerprints).',
         series=['frames.ask_depth_full', 'frames.mid'], cells=[], condition='near a turn', lag='x leads',
         target='the turn', direction=None, review_group=None,
         construction='S95 fingerprint catalog, turn_far_thinning on six pivotal NG days',
         search_construction='frames.ask_depth_full / frames.bid_depth_full at each group close; "no relation" is '
                             'read from the counts (not beyond chance agrees with it); nothing is marked',
         evidence=['s95_fingerprints_note']),
    dict(id='H10', source_id='baseline.keep_research_kalshi_knowledge_ng_brain_json',
         anchor='turn_far_thinning DEMOTED to noise',
         statement='The bid side of the same no-direction claim.',
         series=['frames.bid_depth_full', 'frames.mid'], cells=[], condition='near a turn', lag='x leads',
         target='the turn', direction=None, review_group=None,
         construction='S95 fingerprint catalog, turn_far_thinning', search_construction='as H09',
         evidence=['s95_fingerprints_note']),
)


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def read_source(src):
    """The catalog's bytes of one source, or (None, reason). Revision first, the working tree only on an equal sha."""
    try:
        data = subprocess.run(['git', '-C', str(REPO), 'show', '%s:%s' % (src['revision'], src['path'])],
                              capture_output=True, check=True).stdout
        if sha256_bytes(data) == src['sha256']:
            return data, 'revision %s' % src['revision']
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    path = REPO / src['path']
    if path.is_file():
        data = path.read_bytes()
        if sha256_bytes(data) == src['sha256']:
            return data, 'working tree (same sha256)'
        return None, 'the revision is not in this checkout and the working tree bytes differ from the catalog sha256'
    return None, 'the revision is not in this checkout and the path is absent'


def md_candidates(text, where):
    out, taken = [], 0
    lines = text.split('\n')
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if re.match(r'^(\d+\.|[-*])\s+\S', s) or (s.startswith('|') and not re.match(r'^\|[\s:|-]+\|?$', s)):
            out.append(dict(source=where, line=i, text=s))
            taken += 1
    return out, dict(rule='md: list items and table body rows', lines=len(lines), taken=taken, not_taken=len(lines) - taken)


def json_candidates(data, where):
    out = []
    try:
        doc = json.loads(data)
    except ValueError as error:
        return out, dict(rule='json: strings under statement keys', error='not JSON: %s' % error)

    def walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(v, str) and CLAIM_KEYS.search(str(k)) and v.strip():
                    out.append(dict(source='%s#%s/%s' % (where, path, k), line=None, text=v.strip()))
                else:
                    walk(v, '%s/%s' % (path, k))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, '%s/%d' % (path, i))
    walk(doc, '')
    return out, dict(rule='json: every string under a key matching %s' % CLAIM_KEYS.pattern, taken=len(out))


def find_anchor(text, anchor):
    """(line, matched text) of the anchor in the source, whitespace-insensitive; None when absent."""
    pattern = r'\s+'.join(re.escape(w) for w in anchor.split())
    m = re.search(pattern, text)
    if not m:
        return None
    return text.count('\n', 0, m.start()) + 1, text.count('\n', 0, m.end()) + 1


def build(catalog_path=CATALOG, review_path=REVIEW):
    catalog_bytes = (REPO / catalog_path).read_bytes()
    catalog = json.loads(catalog_bytes)
    review_bytes = (REPO / review_path).read_bytes()
    review = review_bytes.decode('utf-8')
    names = search_series()
    by_id = {s['id']: s for s in catalog['sources']}
    if len(by_id) != len(catalog['sources']):
        raise SystemExit('the catalog repeats a source id (duplicate data declines the run)')
    texts, sources, candidates, not_testable = {}, [], [], []
    for src in catalog['sources']:
        data, how = read_source(src)
        entry = dict(id=src['id'], path=src['path'], status=src['status'], sha256=src['sha256'], read=how if data else None)
        if data is None:
            entry['unreadable'] = how
            not_testable.append(dict(source=src['id'], statement=None, reason='source unreadable with the catalog bytes: ' + how))
            sources.append(entry)
            continue
        text = data.decode('utf-8', errors='replace')
        texts[src['id']] = text
        suffix = src['path'].rsplit('.', 1)[-1].lower()
        if suffix == 'md':
            found, entry['extraction'] = md_candidates(text, src['path'])
        elif suffix == 'json':
            found, entry['extraction'] = json_candidates(data, src['path'])
        else:
            found = [dict(source=src['path'], line=None, text=CODE_CANDIDATE)]
            entry['extraction'] = dict(rule='code: the source once; claims in its docstrings are reached by the crosswalk')
        for c in found:
            c['catalog_id'] = src['id']
        candidates.extend(found)
        entry['candidates'] = len(found)
        sources.append(entry)
    claims, covered = [], {}
    for x in CROSSWALK:
        src = by_id.get(x['source_id'])
        if src is None or x['source_id'] not in texts:
            not_testable.append(dict(source=x['source_id'], statement=x['statement'], crosswalk=x['id'],
                                     reason='crosswalk source not in the catalog or unreadable'))
            continue
        at = find_anchor(texts[x['source_id']], x['anchor'])
        if at is None:
            not_testable.append(dict(source=x['source_id'], statement=x['statement'], crosswalk=x['id'],
                                     reason='crosswalk anchor not found in the catalog bytes: %r' % x['anchor']))
            continue
        missing = [s for s in x['series'] if not carried(s, names)]
        if missing:
            not_testable.append(dict(source='%s:%d' % (src['path'], at[0]), statement=x['statement'], crosswalk=x['id'],
                                     reason='series the search does not carry: %s' % ', '.join(missing)))
            continue
        covered.setdefault(x['source_id'], []).append((x['id'], x['anchor'], at))
        claims.append(dict(id=x['id'], author='historical', catalog_id=x['source_id'],
                           source='%s:%d' % (src['path'], at[0]) + ('' if at[1] == at[0] else '-%d' % at[1]),
                           source_sha256=src['sha256'], anchor=x['anchor'], statement=x['statement'],
                           series=list(x['series']), cells=list(x['cells']), condition=x['condition'], lag=x['lag'],
                           target=x['target'], direction=x['direction'], x_transform='sign_of_step',
                           y_transform='sign_of_step', construction=x['construction'],
                           search_construction=x['search_construction'], review_group=x['review_group'],
                           evidence=list(x['evidence'])))
    def norm(text):
        return re.sub(r'\s+', ' ', text)
    for c in candidates:
        hits = [cid for cid, anchor, (lo, hi) in covered.get(c['catalog_id'], ())
                if (c['line'] is not None and lo <= c['line'] <= hi) or norm(anchor) in norm(c['text'])
                or c['text'] == CODE_CANDIDATE]
        if hits:
            c['claims'] = hits
            continue
        where = c['source'] if c['line'] is None else '%s:%d' % (c['source'], c['line'])
        reason = ('code: defines constructions and methods, not a claim (K01: its constructions stay distinct)'
                  if c['text'] == CODE_CANDIDATE else
                  'no crosswalk entry: not put in testable form here (a testable claim names series the search carries '
                  'and a pairwise step relation); not a judgment that it cannot be tested')
        not_testable.append(dict(source=where, catalog_id=c['catalog_id'], statement=c['text'], reason=reason))
    groups = []
    for m in re.finditer(r'^### (K\d\d) \S+ (.+)$', review, re.M):
        status = re.search(r'\*\*(.+?)\*\*', review[m.end():m.end() + 2000])
        groups.append(dict(id=m.group(1), title=m.group(2).strip(), line=review.count('\n', 0, m.start()) + 1,
                           status=status.group(1) if status else None))
    listed = [g['id'] for g in groups]
    if listed != list(catalog.get('review_groups') or []):
        not_testable.append(dict(source=review_path, statement=None,
                                 reason='the review headings %s differ from the catalog review_groups %s'
                                        % (listed, catalog.get('review_groups'))))
    doc = dict(schema=SCHEMA, author='historical', catalog=catalog_path, catalog_sha256=sha256_bytes(catalog_bytes),
               catalog_version=catalog.get('version'), review=review_path, review_sha256=sha256_bytes(review_bytes),
               crosswalk_sha256=sha256_bytes(json.dumps(CROSSWALK, sort_keys=True).encode()),
               builder_sha256=sha256_bytes(Path(__file__).read_bytes()),
               rule='R11: claims, never truth; each labelled with its source; K01: constructions kept distinct; no '
                    'model (R17); candidates not put in testable form are listed, never dropped',
               sources=sources, review_groups=groups, claims=claims, candidates=len(candidates),
               not_testable=not_testable, model_calls=0)
    return doc


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--out', help='the output file (default %s/HISTORICAL_CLAIMS_V1-<catalog sha12>.json)' % OUT)
    a = p.parse_args()
    sys.path.insert(0, str(REPO))
    doc = build()
    data = (json.dumps(doc, indent=1, sort_keys=True) + '\n').encode()
    out = Path(a.out) if a.out else OUT / ('%s-%s.json' % (SCHEMA, doc['catalog_sha256'][:12]))
    if out.exists():
        if out.read_bytes() == data:
            print('%s exists with the same bytes: nothing to write' % out)
            return
        raise SystemExit('%s exists with different bytes: the catalog or crosswalk changed; move it aside first' % out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    print(json.dumps(dict(out=str(out), sha256=sha256_bytes(data), claims=len(doc['claims']), candidates=doc['candidates'],
                          not_testable=len(doc['not_testable']),
                          unreadable=[s['id'] for s in doc['sources'] if s.get('unreadable')]), indent=1))


if __name__ == '__main__':
    main()
