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

REPRODUCTIONS / REFORMULATIONS (CCode slice B, 2026-10-06, below the crosswalk): declared tables the scientific teacher
attaches at read time by claim id (frankie_box_scientific_teacher.historical_claims); they are not part of build()'s
output. build() is unchanged by them except builder_sha256, which names the builder that built the committed file; the
committed file is not rebuilt under the hold and stays byte-identical.
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


# ------------------------------------------------------------------------------- reproduction bindings (CCode, slice B)
# REPRODUCTIONS: per crosswalk claim, the ORIGINAL calculation traced to code at its exact revision (CCode, 2026-10-06,
# from reading the sources; every sha256 computed where git history exists and never recomputed on the box, which has
# no history). A binding names what the teachers would stage, run and compare; it is NOT a reproduction and marks
# nothing reproduced. The committed claims file stays byte-identical: frankie_box_scientific_teacher.historical_claims
# attaches these tables at read time by claim id, and frankie_box_historical_reproduction.py holds the stage / plan /
# run / compare / record capability (never invoked under the hold; run() refuses without the authorization literal).
#   status  'defined'         every source and input is committed at the revision named: stageable from git history
#           'missing_inputs'  the sources are committed; the inputs are not in the repository (named; the teachers supply
#                             them where execution is authorized)
#           'not_bound'       no reproduction is built; the reason is stated and the original evidence stays preserved
# A recorded output is compared field by field: 'printed' = a regex over the driver's stdout with the expected values;
# 'json_file' = a file the run produces against the recorded file at its pin, leaf by leaf; 'prose' = a number recorded
# in text (a brain or a docstring) that no driver prints at this revision: declared, listed, not comparable by code.
BB28 = 'bb28b35eefd3cb2dc602031800ac9b7d3d2d5175'
C21DF = '21df8f140e6e59e713bf4a7f1d3e9d614faefa1b'
B4F3 = 'b4f364f0812cd964c68faf3cef948b28d4603c90'


def _src(path, revision, sha256, role, catalog_id=None):
    return dict(path=path, revision=revision, sha256=sha256, role=role, catalog_id=catalog_id)


TEST_BARS = {
    'fingerprint_dataset/test_bars/btc_bybit_perp_minbars.json': 'f804b3f883d2626951e403e9f9bfefc6f4cc7e48536528adda778e40e5fac510',
    'fingerprint_dataset/test_bars/btc_coinbase_minbars.json': 'b5e0f30dcc77115854a371e574ac854224c4fd38cc9f406bc951e0163e683bea',
    'fingerprint_dataset/test_bars/btc_kraken_minbars.json': '58dfa5b73c6b529b778de67b0be46fee5bc0192ee8ab5122cd38273dd65eecf2',
    'fingerprint_dataset/test_bars/eth_bybit_perp_minbars.json': 'eb475f743286e519dc78550fab2099588ac0b34a11b4afb8db5700e423c7e73e',
    'fingerprint_dataset/test_bars/eth_coinbase_minbars.json': '8876a78b8bd2d93b05f742947218d35f6ffc19eb8e16488c71d70984031b16d8',
    'fingerprint_dataset/test_bars/eth_kraken_minbars.json': '53cfd00e6d9885c6d1e2355aaf6383ac626977d6ac2acbec0a0a5b78811bb8fa',
}
INFO_DIPOLE = _src('odcore/info_dipole.py', BB28, '0fb1f3d868973fcf0ee25be30d7ffe1f7b388a9235a19d893f8495012c0df23b',
                   'operator: divergence(), signed_flow_features(), _imbalance()', 'review.091')
NG_BRAIN = _src('research/kalshi/knowledge/ng_brain.json', BB28,
                'bf473faef4d5a1b8fc68a214616e6c6163f0db1794ac98818a5401225563da57',
                'recorded output in prose (plays 0, 1, 3; fingerprints.measures)',
                'baseline.keep_research_kalshi_knowledge_ng_brain_json')
NG_SOURCES = [
    _src('research/kalshi/month_characterize.py', C21DF, '9480cbe7f62f3d10a3e51068d170f47813ac2f1df3195386f4c6f0b7946a36aa',
         'per-leg characterizer: characterize_day() -> dipole_pieces() (dip_imb_level), depth_pieces() (imb_R, '
         'aligned_imb_R, book), turn_pieces() (turn_far_thinning), move_path() (dir, continuation)',
         'swept.research.kalshi.month_characterize.py:c8b86cf'),
    _src('research/kalshi/event_move_baseline.py', C21DF, '1d84f91f5a6b3faf24803b7564ee6b29652dd683159cc7e4afc6c86fdba5a503',
         'depth_features() (imb_R = _imbalance(bid depth, ask depth) at the index; far_thinning; exhaustion) and the '
         'raw tape reader load_cont_day(source="s3")', 'swept.research.kalshi.event_move_baseline.py:a152ab5'),
    _src('research/kalshi/characterize_turns.py', C21DF, '8544d26475c5baedce90c0df210095b2027dedcc2c0a3dc5d646c0793751bc7d',
         'driver: characterize_day("NG", day, source="s3") per day, merged into renders/ng_refine_s95/fingerprints.json',
         'swept.research.kalshi.characterize_turns.py:cf8c349'),
    _src('research/kalshi/lag_join.py', C21DF, '1af5dc0bdd92c4b550302b29740014b4255dbf1313ff895d7a7853bfbc64ce59',
         'leg definition: scan_moves(ts, price, TRIG["NG"] = 0.015, CONFIRM_S, COOLDOWN_S) (imported by the characterizer)'),
    _src('research/kalshi/forward_curve.py', C21DF, '80b083469ab7c611c9bd25dae0aa4d299d6d4de9e1a3393b37d3d6f729b1614a',
         'regime tags (imported by the characterizer; its caches are not in the repository)'),
    _src('research/kalshi/nws_temp_feed.py', C21DF, '53a0f09853524962e2fb7ad487ec8317d1e77fb19632e149ffddd03ae0722d63',
         'regime tags (imported by the characterizer; its caches are not in the repository)'),
    INFO_DIPOLE,
    _src('research/kalshi/renders/ng_refine_s95/fingerprints.json', C21DF,
         'e215180898ad260e555edbde643e334538f2cb649fe3b444b59a3c5a658a7099',
         'recorded output: per-leg fingerprint rows by day (108 days at this revision; the S95 demotion read the six '
         'pivotal days 20250916 20250925 20250929 20251008 20251016 20251020); NOT in the catalog (no "dipole" in its '
         'text): bound here by path, revision and sha256'),
    NG_BRAIN,
]
NG_INPUTS = [
    dict(path='NG MBP-10 continuous day tapes, read by event_move_baseline.load_cont_day(root="NG", day, source="s3")',
         where='AWS S3 (bucket bento-568968024170-us-east-2-an, prefix nymex_mbp10/; credentials and authorization required)',
         status='not_in_repository'),
    dict(path='weather / forward-curve caches read by month_characterize._regime_tags (forward_curve, nws_temp_feed)',
         where='local caches of the research tree, not committed', status='not_in_repository'),
]
NG_PRODUCED = 'renders/ng_refine_s95/fingerprints.json'
# B2: the recorded file holds 108 days; the driver runs six. Compare on the argv days only; legs aligned by entry_idx
# (never by list position); members present on one side only are listed, not matched.
_NG_SCOPE = dict(top_level='argv', member_key='entry_idx')

REPRODUCTIONS = (
    dict(id='crypto_trend_flip', claims=['H01', 'H02'], status='defined',
         calculation='for each winner onset, signed_flow_features over the strictly pre-entry 30-minute window '
                     '(WIN_S = 1800) of 1-minute buy/sell volume bars; drift = close[-1] - close[0] of that window; '
                     'continuation = the next 30 minutes (FWD_S = 1800) move the same sign; split confirm / diverge by '
                     'sign(imb_level) against sign(drift); the DIVERGENCE gate aligned_flow <= -0.2; the 2-factor gate '
                     'divergence x exhaustion computed with odcore.info_dipole.divergence itself',
         entry=dict(cwd='.', script='_info_dipole_trend_flip.py', argv=[], produces=[],
                    note='prints the table; no file is written'),
         sources=[INFO_DIPOLE,
                  _src('_info_dipole_trend_flip.py', BB28, '954f6699bd38483a5df1489a14b3fb71b822ed2c55b47b58b2ed2ef15b73cb35',
                       'driver (pooled n=1560 and per cell); its docstring records the finding', 'review.112'),
                  _src('_info_dipole_flow_detrend.py', BB28, '69e8ba1ea42794aa40cddc62b7538766a356bda823958d8d7a0686968b782dfc',
                       'the cited negative result (signed flow as a direct direction predictor: trend artifact); not run '
                       'by the driver', 'review.107')],
         inputs=[dict(path=path, revision=BB28, sha256=sha, status='committed') for path, sha in sorted(TEST_BARS.items())]
                + [dict(path='fingerprint_dataset/onsets/winner_onsets.json', revision=BB28,
                        sha256='32e713310e2464a34f5f0eb2b5bdebc118add94b30c8d0911d42da099f5ca6b5', status='committed',
                        note='1,560 winner onsets (asset, venue, side, true_onset_ts_utc)')],
         recorded_outputs=[
             dict(kind='printed', what='the POOLED row: n, continuation, confirm n / continuation, diverge n / continuation, edge',
                  pattern=r'^POOLED\s+(?P<n>\d+)\s+(?P<cont>\d+)\s+\|\s+(?P<n_conf>\d+)\s+(?P<cont_conf>\d+)\s+\|\s+'
                          r'(?P<n_div>\d+)\s+(?P<cont_div>\d+)\s+\|\s+(?P<edge>[+-]\d+)',
                  expected=dict(n=1560, cont_conf=50, cont_div=38, edge=12),
                  recorded_in='_info_dipole_trend_flip.py docstring: pooled n=1560, confirm -> 50% continuation, diverge -> 38%, +12pp'),
             dict(kind='printed', what='temporal early half: edge', pattern=r'^\s+temporal early: edge (?P<edge>[+-]\d+)',
                  expected=dict(edge=4), recorded_in='_info_dipole_trend_flip.py docstring: +4 early'),
             dict(kind='printed', what='temporal late half: edge', pattern=r'^\s+temporal late: edge (?P<edge>[+-]\d+)',
                  expected=dict(edge=18), recorded_in='_info_dipole_trend_flip.py docstring: +18 late'),
             dict(kind='printed', what='the DIVERGENCE reversal gate (aligned <= -0.2), pooled',
                  pattern=r'DIVERGENCE reversal gate \(aligned <= -0\.2\): pooled reversal=(?P<reversal>\d+)% \(n=(?P<n>\d+)\)',
                  expected=dict(reversal=65), tolerance=dict(reversal=1),
                  recorded_in='odcore/info_dipole.py divergence docstring: "~65% reversal" (approximate as recorded)'),
             dict(kind='printed', what='per-cell reversal under the gate: btc_bybit_sell',
                  pattern=r'^\s+btc_bybit_sell\s+reversal=\s*(?P<reversal>\d+)%\s+\(n=(?P<n>\d+)\)', expected=dict(reversal=100),
                  recorded_in='odcore/info_dipole.py divergence docstring: btc_bybit_sell 100%'),
             dict(kind='printed', what='per-cell reversal under the gate: btc_kraken_buy',
                  pattern=r'^\s+btc_kraken_buy\s+reversal=\s*(?P<reversal>\d+)%\s+\(n=(?P<n>\d+)\)', expected=dict(reversal=84),
                  recorded_in='odcore/info_dipole.py divergence docstring: btc_kraken_buy 84%'),
             dict(kind='printed', what='2-factor gate: oppose+exhaust n and reversal',
                  pattern=r'^\s+oppose\+exhaust\s+n=\s*(?P<n>\d+)\s+reversal=\s*(?P<reversal>\d+)%', expected=dict(n=317, reversal=64),
                  recorded_in='odcore/info_dipole.py divergence docstring: opposing+exhausting = 64% reversal (n=317)'),
             dict(kind='printed', what='2-factor gate: oppose+strengthen reversal',
                  pattern=r'^\s+oppose\+strengthen\s+n=\s*(?P<n>\d+)\s+reversal=\s*(?P<reversal>\d+)%', expected=dict(reversal=58),
                  recorded_in='odcore/info_dipole.py divergence docstring: opposing+strengthening 58%'),
             dict(kind='printed', what='2-factor gate: withtrend+exhaust reversal',
                  pattern=r'^\s+withtrend\+exhaust\s+n=\s*(?P<n>\d+)\s+reversal=\s*(?P<reversal>\d+)%', expected=dict(reversal=52),
                  recorded_in='odcore/info_dipole.py divergence docstring: with-trend+weakening 52%'),
             dict(kind='printed', what='2-factor gate: withtrend+strengthen reversal',
                  pattern=r'^\s+withtrend\+strengthen\s+n=\s*(?P<n>\d+)\s+reversal=\s*(?P<reversal>\d+)%', expected=dict(reversal=49),
                  recorded_in='odcore/info_dipole.py divergence docstring: with-trend+strengthening 49%'),
             dict(kind='prose', what='strong-divergence reversal by half: early 70% / late 62%',
                  recorded_in='odcore/info_dipole.py divergence docstring',
                  note='the driver at this revision prints the per-half continuation edge, not the per-half reversal of '
                       'the strong gate; declared, not comparable by code'),
             dict(kind='prose', what='btc_bybit_buy neutral under the gate', recorded_in='odcore/info_dipole.py divergence docstring',
                  note='"neutral" names no number; the per-cell line prints only for n >= 15')],
         limits='crypto 1-minute bars of two days (2026-05-23..24), pooled n=1560 and per cell: the docstring itself calls the '
                'data thin and the deploy map unvalidated (DEPLOY_VALIDATED = False); a match reproduces the recorded numbers, '
                'not an edge'),
    dict(id='crypto_harness', claims=['H01', 'H02'], status='missing_inputs',
         calculation='the falsification harness: the same R-bps reversal timing trigger for both detectors; champion filter = '
                     'trailing order-flow imbalance threshold, challenger filter = odcore.info_dipole.divergence '
                     '(divergence + exhaustion); ZigZag pivots at theta = 20 bps as truth; tune on the first 60 percent, score '
                     'the last 40 percent out of sample: calls, TP, FP, FN, recall, precision, bps_to_turn, net_oos (taker) and '
                     'net_oos_maker per venue',
         entry=dict(cwd='.', script='_info_dipole_harness.py', argv=[], produces=['_info_dipole_harness_results.json']),
         sources=[INFO_DIPOLE,
                  _src('_info_dipole_harness.py', BB28, 'c0adfc40dcc07e2e296daa26b5da9c4e20c7d00a6b34445df5ca1687e3222dda',
                       'driver (writes _info_dipole_harness_results.json)', 'review.095'),
                  _src('_info_dipole_swing_backtest.py', BB28, '7f0f9ce36cc3feec0e1e509b190d4b6ca0c1614ffaab288b969f128b59f94964',
                       'dependency: load_series("realbins"), zigzag(), trailing_imbalance()', 'review.111'),
                  _src('_info_dipole_harness_results.json', BB28, 'ace94a10b8bb2b35f45a37a519ef7fb364c138f10508ce5d6a72c3a8026130e8',
                       'recorded output', 'review.096')],
         inputs=[dict(path='realbins/*_bins.json (1-second bins; the live collectors\' format, dict keyed by ts)',
                      where='not in the repository (the realbins directory is not committed at any revision)',
                      status='not_in_repository')],
         recorded_outputs=[dict(kind='json_file', what='per venue, champion and challenger: n_calls, TP, FP, FN, n_turns, recall, '
                                                       'precision, bps_to_turn, net_oos, net_oos_maker, params; config',
                                produced='_info_dipole_harness_results.json', recorded='_info_dipole_harness_results.json',
                                fields=['config', 'per_venue'])],
         limits='the challenger is the divergence() read used as a turn FILTER on 1-second bins; the recorded net_oos values are '
                'negative at the taker fee for every venue (the file records them); nothing here is an edge claim; '
                'MARKET_ADMISSION[crypto_harness]: cost-selected, historical context only (B7)'),
    dict(id='ng_leg_fingerprints', claims=['H03', 'H04', 'H05', 'H09', 'H10'], status='missing_inputs',
         calculation='per NG day: legs = lag_join.scan_moves on the raw tape (trigger TRIG["NG"] = 0.015 USD); per leg: '
                     'dipole_pieces (dip_imb_level = odcore.info_dipole imb_level over the ~300 s Lee-Ready signed-flow window '
                     'around the entry), depth_pieces (imb_R = _imbalance(bid depth, ask depth) over the resting book at entry, '
                     'aligned_imb_R = imb_R x move sign, book = support / oppose), turn_pieces (turn_far_thinning = '
                     'depth_features far_thinning from entry to the favourable peak within POST_S), move_path (dir, continuation = '
                     'retention >= RUN_THR); written per day into fingerprints.json',
         entry=dict(cwd='research/kalshi', script='characterize_turns.py',
                    argv=['20250916', '20250925', '20250929', '20251008', '20251016', '20251020'],
                    produces=[NG_PRODUCED],
                    note='the driver MERGES into an existing fingerprints.json; the recorded file is staged APART (never in '
                         'the tree), so the produced file holds only the days run; compared on those days only (scope)'),
         sources=NG_SOURCES, inputs=NG_INPUTS,
         recorded_outputs=[
             dict(kind='json_file', what='H03: per leg dip_imb_level and dir', produced=NG_PRODUCED,
                  recorded='research/kalshi/renders/ng_refine_s95/fingerprints.json', claims=['H03'],
                  fields=['*.*.day', '*.*.entry_idx', '*.*.dir', '*.*.dip_imb_level'], scope=_NG_SCOPE),
             dict(kind='json_file', what='H04/H05: per leg imb_R, aligned_imb_R, book and dir', produced=NG_PRODUCED,
                  recorded='research/kalshi/renders/ng_refine_s95/fingerprints.json', claims=['H04', 'H05'],
                  fields=['*.*.day', '*.*.entry_idx', '*.*.dir', '*.*.imb_R', '*.*.aligned_imb_R', '*.*.book'], scope=_NG_SCOPE),
             dict(kind='json_file', what='H09/H10: per leg turn_far_thinning and continuation', produced=NG_PRODUCED,
                  recorded='research/kalshi/renders/ng_refine_s95/fingerprints.json', claims=['H09', 'H10'],
                  fields=['*.*.day', '*.*.entry_idx', '*.*.dir', '*.*.turn_far_thinning', '*.*.continuation'], scope=_NG_SCOPE),
             dict(kind='prose', claims=['H03'], what='1,537 legs cleared |dip_imb_level| >= 0.15; sign matched realized leg '
                                                      'direction on 87.6 percent',
                  recorded_in='ng_brain.json plays/0/instances/0 (what_the_state_said, what_the_day_did)',
                  note='the aggregation over legs (sign(dip_imb_level) == leg dir under the bar) is stated in prose; no '
                       'committed module computes it; the brain\'s own audit recounts 2,459/3,697 = 0.665 over 6,351 legs on '
                       '108 days and an inverted strength gradient (plays/0/audit/could_evidence_have_come_out_otherwise): '
                       'both numbers are recorded claims, neither is truth'),
             dict(kind='prose', claims=['H04', 'H05'], what='direction.book_contrarian: confidence 0.5, status PROVISIONAL, '
                                                             'support UNCLEAR, forward evidence NONE',
                  recorded_in='ng_brain.json plays/1 (confidence, status, support, forward)',
                  note='no count or rate is recorded for the book-contrarian claim; the per-leg imb_R values are the only '
                       'recorded numbers (fingerprints.json)'),
             dict(kind='prose', claims=['H09', 'H10'], what='turn_far_thinning did NOT confirm as the hold-vs-fade '
                                                             'discriminator (held legs only ~half negative-tft); DEMOTED to noise',
                  recorded_in='ng_brain.json plays/3/legacy_notes/evidence/s95_fingerprint_nonconfirm; meta/s95_fingerprints_note',
                  note='"held legs" is not defined in code (the nearest per-leg field is continuation); the reading is declared, '
                       'not source-defined; compare the per-leg values, not the aggregate')],
         limits='the per-leg arithmetic is defined in the committed modules; the aggregates the brain records are prose; the raw '
                'inputs live on S3 and the regime caches are local, so this binding is stageable in code only: inputs missing'),
    dict(id='memory_a_retired', claims=['H06', 'H07', 'H08'], status='not_bound',
         reason='Memory A retired by Greg 2026-10-06; original evidence preserved',
         calculation='Memory A exact native MBO: the Oct 4 / Oct 5 2021 close slices (depth 1,342/698 -> imbalance 0.315686; the '
                     '41-trade final-window motif, +0.002/+0.004 rebound). NOT bound for reproduction: no Memory A path is built',
         entry=None, inputs=[dict(path='the A-memory ledger (sha bc0788b5...)', status='not_bound')],
         sources=[_src('research/kalshi/agents/frankie_native_raw_mbo_knowledge/A_MEMORY_POSITIVE_KNOWLEDGE_20260828.md', B4F3,
                       'bc84a77d33393c7d04185fcbfa82794cef0efd45b4fd31f0b2ee245cfb8d9131', 'the A-memory positive knowledge document (evidence preserved; not staged)',
                       'baseline.a_memory_promoted_positive_knowledge'),
                  _src('research/kalshi/frankie_raw_mbo_benchmark/AMEMORY_MEMBER_FIRST_RECALCULATION_RECEIPT_20260828.json', B4F3,
                       '094c32a4177edee9c16e92a288427d6e5d3777f23db8d2f954f0c6d5f310a7c1', 'the member-first recalculation receipt (evidence preserved; not staged)',
                       'baseline.a_memory_member_first_recalculation_receipt')],
         recorded_outputs=[dict(kind='prose', what='receipt counts; imbalance 0.315686; depth 1,342/698; Oct-05 mean bid depth '
                                                   '+21.85 percent, mean ask depth -0.54 percent; rebound +0.002/+0.004',
                                recorded_in='the two catalog sources above', note='preserved as historical evidence; not compared')],
         limits='the recalculation script a_memory_member_first_recalculation_20260828.py is not in this repository\'s history '
                '(git log --all finds no file of that name) and not in the catalog; CLAUDE.md 2026-09-27 removed the Memory A '
                'requirement and preserved the historical files as evidence; the three claims keep their statements, labels '
                'and rationale as historical claims'),
)

# REFORMULATIONS: per claim, what a declared repair or reformulation NEEDS before a teacher could perform it on the
# search's series: the exact producer/consumer contract and the decision that is missing. Nothing here applies a
# condition, adds a transform or chooses a window: those are mathematical decisions (Greg) in the reserved search
# module (frankie_box_experiment_search.py / frankie_box_experiment_transforms.TRANSFORMS /
# frankie_box_experiment_surface.state_masks, which builds exact categorical and numeric SIGN states but is not wired).
_SEARCH_TRANSFORMS = 'frankie_box_experiment_transforms.TRANSFORMS = sign_of_step, run_length, magnitude_class, level_crossing, acceleration'
_STATE_MASKS = ('frankie_box_experiment_surface.state_masks: exact categorical states and numeric sign states at the decision '
                'row, built but not wired (the search module lists "conditions beyond the text cells" as held)')
REFORMULATIONS = (
    dict(claim='H01', status='awaiting_definition', kind='numeric-state condition, not searched',
         needs=['the derived quantity aligned_flow = roll20.value x sign(drift of frames.mid over a pre-entry window): a '
                'derived series the search does not carry; which window on the F_LAST group-close axis stands for the '
                'original 30 minutes of 1-minute bars is a mathematical decision',
                'the condition aligned_flow <= -0.20 at the decision row: a THRESHOLD state; ' + _STATE_MASKS + ' carries sign '
                'states only, so a threshold state is a new definition',
                'the target: the next move of frames.mid against the drift (a sign relation at a lag), stated by the search\'s '
                'coupling at the searched lags once the condition exists'],
         where=[_STATE_MASKS, 'frankie_box_experiment_search.build_series (derived series)'], decision='Greg: mathematical decision'),
    dict(claim='H02', status='awaiting_definition', kind='transform: |imbalance| falling',
         needs=['a transform of roll20.value: |late-half imbalance| < |early-half imbalance| over a window (the original '
                'exhausting flag of odcore.info_dipole.divergence: the two halves of the pre-entry window); ' + _SEARCH_TRANSFORMS
                + ' holds no windowed two-half comparison, so this is a new transform with a window parameter',
                'the same pre-entry window decision as H01'],
         where=[_SEARCH_TRANSFORMS], decision='Greg: mathematical decision'),
    dict(claim='H03', status='awaiting_definition', kind='numeric-state condition |dip_imb_level| >= 0.15 and a construction transfer',
         needs=['whether roll20.value (20-second causal aggressor-side imbalance at 1-second resolution) stands for dip_imb_level '
                '(Lee-Ready signed flow over ~300 s around a leg\'s trigger push on NG MBP-10): a construction decision, not a '
                'rename',
                'the threshold condition |x| >= 0.15 at the decision row (' + _STATE_MASKS + ')',
                'the target: a LEG and its SIDE (lag_join.scan_moves over TRIG["NG"] = 0.015 with CONFIRM_S / COOLDOWN_S) has '
                'no definition on the F_LAST group-close axis; frames.mid steps are not legs'],
         where=[_STATE_MASKS, 'frankie_box_experiment_search.build_series'], decision='Greg: mathematical decision'),
    dict(claim='H04', status='awaiting_definition', kind='flat-flow condition with no numeric bar in the source',
         needs=['the source states "flow (dip_imb_level) flat/ambiguous" with no threshold: a numeric bar must be declared before '
                'any condition can be built',
                'imb_R is the resting-book imbalance over the first 10 levels AT THE LEG ENTRY; frames.depth_imbalance_full is the '
                'full-depth imbalance at EVERY group close: the entry (trigger) definition is missing on this axis',
                'the condition itself (' + _STATE_MASKS + ')'],
         where=[_STATE_MASKS], decision='Greg: mathematical decision (the bar and the entry definition)'),
    dict(claim='H05', status='awaiting_definition', kind='as H04 on the top-of-book imbalance',
         needs=['everything H04 needs', 'frames.depth_imbalance_n uses the adapter\'s n (frankie_box_boss_session BOOK_FIELDS), '
                                        'not 10 levels: whether n stands for the original 10 is a construction decision'],
         where=[_STATE_MASKS], decision='Greg: mathematical decision'),
    dict(claim='H06', status='not_bound', kind='Memory A retired', needs=[], where=[],
         decision='Greg 2026-10-06: Memory A is no longer used; no reformulation is built; the claim stays historical'),
    dict(claim='H07', status='not_bound', kind='Memory A retired', needs=[], where=[],
         decision='Greg 2026-10-06: Memory A is no longer used; no reformulation is built; the claim stays historical'),
    dict(claim='H08', status='not_bound', kind='Memory A retired',
         needs=['(listed only) the condition "late in a negative-drift window with the final book bid-heavy" has no definition on '
                'the F_LAST axis either; nothing is built'],
         where=[], decision='Greg 2026-10-06: Memory A is no longer used; no reformulation is built; the claim stays historical'),
    dict(claim='H09', status='awaiting_definition', kind='a turn definition',
         needs=['the original turn = the leg\'s favourable peak within POST_S after entry (turn_pieces: argmax of sign x (p - p0)); '
                '"near a turn" has no definition on the F_LAST group-close axis',
                'far_thinning is the consumed side\'s resting-depth CHANGE from entry to the peak (event_move_baseline.depth_features); '
                'frames.ask_depth_full / frames.bid_depth_full are depth LEVELS at each group close: the entry-to-peak difference '
                'is a derived series that needs the turn definition first',
                'the no-direction reading needs no mechanism: counts not beyond chance agree with it and nothing is marked'],
         where=['frankie_box_experiment_search.build_series (a turn-anchored derived series)'], decision='Greg: mathematical decision'),
    dict(claim='H10', status='awaiting_definition', kind='a turn definition (bid side of H09)',
         needs=['everything H09 needs, on frames.bid_depth_full'],
         where=['frankie_box_experiment_search.build_series'], decision='Greg: mathematical decision'),
)


# MARKET_ADMISSION (B7 / C2, Codex's review 2026-10-06; Greg: market conditions only, costs and bookkeeping are never
# signals, objectives or verdicts): per reproduction binding, what its ORIGINAL calculation selected or labelled by
# execution cost, traced in the pinned sources, and therefore what a byte-matched reproduction of it IS and IS NOT
# admissible as. The original bytes and recorded results stay bound above, intact, as identified historical context
# (so the prior conclusion can be explained and reworked); nothing is rewritten, rebuilt or rerun. Where a cost-free
# route needs a mathematical choice the source never made, that choice is named and left to Greg, never taken here.
MARKET_ADMISSION = {
    'crypto_trend_flip': dict(
        status='market_conditions',
        trace=['_info_dipole_trend_flip.py @ ' + BB28 + ': no fee, cost or profit enters the arithmetic; the printed rates '
               'are continuation/reversal COUNTS over winner onsets (confirm vs diverge split, aligned <= -0.2 gate, the '
               '2-factor gate); its "best flip detector (pooled edge)" line ranks detectors by a count difference, not by net'],
        admissible_as='market-condition evidence of the ORIGINAL calculation on its original inputs (reproduction status as '
                      'recorded); provisional like every historical result; the pooled lines are pooled (never the lead)',
        not_admissible_as=None, pending_choice=None),
    'crypto_harness': dict(
        status='cost_selected_historical_context',
        trace=['_info_dipole_harness.py @ ' + BB28 + ' (sha256 c0adfc40...): run_calls() subtracts FEE_RT (10 bps taker) or '
               'FEE_MAKER (4 bps) per leg; tune_and_score() picks best = (R, W, T) by that fee-adjusted IN-SAMPLE net '
               '(line "if best is None or net > best[0]"), then computes the OOS calls/TP/FP/FN/recall/precision/'
               'bps_to_turn at those selected params; SWING_THETA = 20 bps is declared the tradeable fee-floor swing that '
               'DEFINES the true turns (zigzag(p, SWING_THETA)), so FN/TP/recall are measured against a cost-defined truth',
               '_info_dipole_swing_backtest.py @ ' + BB28 + ' (dependency): the minimum tradeable swing is the one that '
               'beats the round-trip fee; its sweep is a fee sweep',
               'every per_venue field of _info_dipole_harness_results.json is downstream of that selection or that truth: '
               'net_oos / net_oos_maker (profit), params (fee-selected), n_calls / TP / FP / FN / n_turns / recall / '
               'precision / bps_to_turn (at fee-selected params against fee-floor turns); config carries fee_rt_bps and '
               'swing_theta_bps'],
        admissible_as='identified historical context: an audit of what the prior cost-based run produced (a byte-matched '
                      'reproduction says the recorded numbers were reproduced, nothing more), kept whole so the prior '
                      'conclusion can be explained and reworked',
        not_admissible_as='independent market-condition evidence on H01/H02; a market verdict (support or dismissal) on the '
                          'divergence/exhaustion relation; a tuning objective; excluding net_oos/net_oos_maker or zeroing the '
                          'fee does not remove the profit-selected params or the fee-floor turn definition',
        pending_choice='a cost-free selection rule for (R, W, T) and a cost-free turn definition (the ZigZag theta without '
                       'a fee-floor rationale) are mathematical choices the source never states: Greg; none is taken here'),
    'ng_leg_fingerprints': dict(
        status='market_conditions_under_a_fee_justified_threshold',
        trace=['month_characterize.py @ ' + C21DF + ': no fee, cost or profit enters dipole_pieces / depth_pieces / '
               'turn_pieces / move_path; TRIG["NG"] = 0.015 USD is the leg trigger, whose comment calls it a "fee-justified '
               'trigger" (a threshold VALUE motivated by a fee floor; the arithmetic on legs is cost-free)',
               'lag_join.py @ ' + C21DF + ': fee_cents() exists for the Kalshi echo study; scan_moves() (the leg definition '
               'the characterizer imports) uses only the trigger, CONFIRM_S and COOLDOWN_S',
               'event_move_baseline.py @ ' + C21DF + ': retention / run_thr / far_thinning are price and depth geometry'],
        admissible_as='market-condition evidence of the ORIGINAL per-leg calculation under its named trigger; the trigger '
                      'value is a threshold choice (already an open H03 LEG/threshold need in REFORMULATIONS)',
        not_admissible_as='a verdict that the 0.015 trigger is the market\'s own leg definition: its value was fee-motivated',
        pending_choice='a trigger / LEG definition stated without a fee rationale (REFORMULATIONS H03): Greg'),
    'memory_a_retired': dict(status='not_bound', trace=['Memory A retired by Greg 2026-10-06; nothing is reproduced'],
                             admissible_as=None, not_admissible_as=None, pending_choice=None),
}
# C2: the same distinction for the fields a consumer may meet (the teachers' explanations use these words).
MARKET_ROLE_RULE = ('Greg, 2026-10-07: "We never have transaction costs in market conditions work." '
                    'IDs, dates, weekdays and availability codes may GROUP market signals as search conditions; they are '
                    'never numerical signals, targets or explanations; execution costs and profit are never objectives '
                    'or verdicts; market prices, spreads, signed flow, depth, FIFO rank/age, elapsed market durations, '
                    'positioning and derived geometry remain the quantities (Greg, 2026-10-06)')


def market_admission_of(claim_id):
    """The market admission of every binding covering one claim: {status, entries: {entry_id: admission}}. status =
    'cost_selected_historical_context' when any covering binding is cost-selected (its reproduction can never be read as
    a market verdict), else the bindings' own word, 'unmapped' with no binding."""
    entries = {e['id']: MARKET_ADMISSION.get(e['id'], dict(status='undeclared')) for e in REPRODUCTIONS if claim_id in e['claims']}
    words = {a['status'] for a in entries.values()}
    status = ('unmapped' if not entries else 'cost_selected_historical_context'
              if 'cost_selected_historical_context' in words else next(iter(sorted(words))))
    return dict(status=status, entries=entries, rule=MARKET_ROLE_RULE)


def reproduction_of(claim_id):
    """The reproduction binding(s) covering one crosswalk claim: {status, entries}. status = 'not_bound' when any entry is
    not bound; else 'defined' when any entry is stageable from history; else 'missing_inputs'; 'unmapped' with no entry.
    A binding is a declared route for the teachers; it marks nothing reproduced."""
    entries = [e for e in REPRODUCTIONS if claim_id in e['claims']]
    if not entries:
        status = 'unmapped'
    elif any(e['status'] == 'not_bound' for e in entries):
        status = 'not_bound'
    elif any(e['status'] == 'defined' for e in entries):
        status = 'defined'
    else:
        status = 'missing_inputs'
    return dict(status=status, entry_ids=[e['id'] for e in entries], entries=entries,
                reason=next((e.get('reason') for e in entries if e.get('reason')), None),
                rule='a binding names sources at exact revisions with sha256, the entry point, the inputs and the recorded outputs; '
                     'it is not a reproduction and marks nothing reproduced (R11, R13)')


def reformulation_of(claim_id):
    """What a declared repair or reformulation of one claim needs, or {status: unmapped}."""
    entry = next((r for r in REFORMULATIONS if r['claim'] == claim_id), None)
    return dict(entry) if entry else dict(claim=claim_id, status='unmapped', needs=[], where=[], decision=None)


def binding_tables_sha256():
    """The sha256 of both declared tables (canonical JSON), so a record or lessons file can say which bindings it read."""
    return hashlib.sha256(json.dumps(dict(reproductions=REPRODUCTIONS, reformulations=REFORMULATIONS,
                                          market_admission=MARKET_ADMISSION), sort_keys=True).encode()).hexdigest()


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
                           evidence=list(x['evidence']),
                           research_rework=dict(status='OPEN_REWORK_REQUIRED', closed=False,
                               original_calculation_reproduction='pending_teacher_work',
                               repair_or_reformulation='pending_teacher_work')))
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
    for item in not_testable:
        item['research_status'] = 'OPEN_MAPPING_OR_REWORK_REQUIRED'
        item['closed'] = False
    doc = dict(schema=SCHEMA, author='historical', catalog=catalog_path, catalog_sha256=sha256_bytes(catalog_bytes),
               catalog_version=catalog.get('version'), review=review_path, review_sha256=sha256_bytes(review_bytes),
               crosswalk_sha256=sha256_bytes(json.dumps(CROSSWALK, sort_keys=True).encode()),
               builder_sha256=sha256_bytes(Path(__file__).read_bytes()),
               rule='R11: claims, never truth; each labelled with its source; K01: constructions kept distinct; no '
                    'model (R17); candidates not put in testable form are listed, never dropped; '
                    'old rejected/dead/no-good conclusions are not truth or closure: original calculations must be '
                    'reproduced and repair/reformulation investigated by both teachers before closure is considered',
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
