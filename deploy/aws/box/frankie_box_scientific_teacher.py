"""The scientific teacher's turn: every claim tested on the search's counts, day by day, and the lessons written.

Greg, 2026-09-29. Spec: research/kalshi/frankie_boss/SPEC-scientific-teacher.md (the scientific teacher IS the
experiment's search; no model seat, rule R17) and SPEC-experiment-orchestrator.md (sections "Jev" and "His brain").
Code only; no model call.

Takes, each labelled with its author (rule R11: claims, never truth):
  - Jev's claims: JEV_CLAIMS_V1 (clm_sidecar/sit_in.py), each naming its series, direction, lag and cells;
  - Frankie's claims: ONLY the novel findings of his classroom ledgers (dipole_novel_findings). The rest of his ledgers,
    his analysis and his answers are his reasoning and are never read here (rule R09);
  - the historical Dipole claims: HISTORICAL_CLAIMS_V1 (frankie_box_historical_claims.py, committed), author 'historical'.
    Its mapped claims are tested; its not_testable list (every statement the crosswalk did not put in testable form)
    travels with the lessons under `reconsideration`, counted by open status and bound to the claims file by sha256,
    so neither teacher reads the mapped subset as the collection. Every historical result carries `research_rework`:
    a count comparison on stored search evidence is one status; the original calculation's reproduction and any
    repair/reformulation stay pending_teacher_work until a teacher performs them; a prior rejected/dead/no-good label
    is carried as a label and never closes reconsideration (R11, R13; Greg, 2026-10-06). Each mapped claim carries its
    declared reproduction binding and reformulation needs (frankie_box_historical_claims.REPRODUCTIONS /
    REFORMULATIONS, attached by claim id at read time; the committed claims file is untouched), and test() reads any
    hash-bound HISTORICAL_REPRODUCTION_V1 record a teacher's authorized execution wrote under <work>/reproduction/
    (frankie_box_historical_reproduction): performed_matched / performed_differs / not_run, else pending_teacher_work;
  - the search's own candidates: FRANKIE_SEARCH_FINDINGS_V1 (Run.search_knowledge: every beyond-chance row of one day's
    search, with part/row provenance), projected by frankie_box_candidate_claims.py, author 'search' (CCode step #4).
    Their series are matched exactly, and the rows of their own discovery day are listed as ORIGIN EVIDENCE, never
    counted as a test: a second use of the same evidence is not another occurrence.
and every completed experiment search given (frankie_box_experiment_search.py outputs), plus each searched day's
COMPLETED NATIVE EVIDENCE the search pinned and did not search (receipt, result section summaries, sections 4.2 and
4.4, every FINALIZE row), read whole and bound by sha256 (completed_native_evidence), written once per day under
<work>/native/ and carried in every lessons file so both exchange seats cite it; averages are labelled supplements. Trading date and former
discovery/confirmation labels do not gate knowledge use (Greg, 2026-10-06). Each day is reported on its own, never pooled.

For each claim: its series names are matched to the search's series (normalized names; every match listed, an unmatched
name listed as "not in the search"); for each matched pair and each day, the coupling rows (whole-day and every cell)
are read whole and reported as their counts. The search writes both orientations of a pair; the reversed row at the
negated lag with the same counts is the same measurement (D_yx[k] = D_xy[-k]) and is listed under mirrored_rows, never
counted as a second test; a reversed row with no forward counterpart is read on its own with the claim's transforms
swapped and its lag negated. Counts are reported as: same_way, opposite, both_moving, best lag, the chance check's shifts and
how many reached the observed count. Where the claimed direction is stated in a testable form, each day is marked:
  held       beyond chance and moving the claimed way;
  shown_otherwise  beyond chance and moving the other way -> the challenge, worded "the data is showing this instead";
  unresolved not beyond chance, or no claimed direction to compare.
  counts_only  a row outside the claim's transforms, lag or cells, or with an unapplied condition/lag relation:
             its counts are reported, it is never marked as supporting or contradicting that claim.
The disposition word (SUPPORTED_SCOPED, CONTRADICTED_SCOPED, PLAUSIBLE_UNRESOLVED, INSUFFICIENT_EVIDENCE, the words of
dipole_scientific_review) is orientation only (R14); the counts and days are the finding. Lags outside the search's
window, cells the search did not run, transforms it did not run and series it does not carry are listed under
untested / cannot_test_yet, never dropped.

Writes, per author, one lessons file bound to the exact claims it answers (claims_sha256):
  JEV_LESSONS_V1      -> Jev's brain (clm-sidecar/jev-brain/lessons/<day>-<stamp>.json; uploaded through the presigned
                         slot in MAP_URL when given) AND, only after Jev's own claims are sealed and tested here, the
                         tested result enters Frankie's brain as <brain>/<day>-jev-tested/. Jev's blind wall ends after
                         his independent claim is fixed; tested knowledge is not withheld from Frankie afterward;
  FRANKIE_LESSONS_V1  -> kept under /opt/frankie-box/work/experiment-teacher/ and filed into Frankie's brain as the entry
                         <brain>/<day>-lessons/ (frankie_box_brain.write_lessons_entry), read by every later cycle.
  HISTORICAL_LESSONS_V1 -> kept under /opt/frankie-box/work/experiment-teacher/historical/<days>-<catalog sha12>.json,
                         the historical catalog's claims (frankie_box_historical_claims.py) tested on the days given;
                         published into each tested day's lessons entry with original author and scopes intact.
  SEARCH_CANDIDATE_LESSONS_V1 -> kept under /opt/frankie-box/work/experiment-teacher/search/<day>-candidates-<sha12>.json,
                         RETAINED ONLY: frankie_box_brain.write_lessons_entry admits the authors frankie/historical/jev,
                         so these results are not published into any brain until that writer and the LESSONS maps of
                         frankie_box_teacher_knowledge.py / frankie_box_experiment_exchange.py admit the author
                         (Codex-owned files; named in CCODE_STEP4_SOURCE_ROUTE_20261006.md). Acceptance/survivor
                         treatment of a tested candidate is not decided here (step #5 discussion).
"""
import argparse
import gzip
import hashlib
import json
import os
import re
import time
import urllib.request
from pathlib import Path

ROOT = Path('/opt/frankie-box/work/experiment-teacher')
REPRODUCTION_DIR = ROOT / 'reproduction'      # HISTORICAL_REPRODUCTION_V1 records (frankie_box_historical_reproduction.record)
DISPOSITIONS = ('SUPPORTED_SCOPED', 'PLAUSIBLE_UNRESOLVED', 'CONTRADICTED_SCOPED', 'INSUFFICIENT_EVIDENCE')
SAME_WORDS = ('same', 'together', 'positive', 'aligned', 'co-move', 'comove', 'both rise', 'both fall', 'with')
OPPOSITE_WORDS = ('opposite', 'inverse', 'negative', 'against', 'contrary', 'diverge')


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def norm(name):
    return re.sub(r'[^a-z0-9]', '', str(name).lower())


def claimed_direction(text):
    """'same' | 'opposite' | None, from the claim's own words; None = not stated in a testable form (listed)."""
    t = str(text or '').lower()
    opposite = any(w in t for w in OPPOSITE_WORDS)
    same = any(w in t for w in SAME_WORDS)
    return 'opposite' if opposite and not same else 'same' if same and not opposite else None


def claimed_lag(text):
    match = re.search(r'-?\d+', str(text or ''))
    return int(match.group(0)) if match else None


def jev_claims(path):
    raw = Path(path).read_bytes()
    doc = json.loads(raw)
    if doc.get('schema') != 'JEV_CLAIMS_V1':
        raise SystemExit('%s is not a JEV_CLAIMS_V1' % path)
    claims = [dict(id=c['id'], statement=c.get('statement'), kind=c.get('kind'), series=list(c.get('series') or []),
                   direction=claimed_direction(c.get('direction')), direction_text=c.get('direction'),
                   lag=claimed_lag(c.get('lag')), cells=list(c.get('cells') or []), day_made=doc.get('day'),
                   source_claim=c)
              for c in doc.get('claims') or []]
    return dict(author='jev', stamp=doc.get('stamp'), day=doc.get('day'), claims_sha256=sha256_bytes(raw),
                source=str(path), claims=claims)


OPEN_CLASSES = (                 # not_testable reasons of frankie_box_historical_claims -> the open status they stay in
    ('no crosswalk entry', 'awaiting_teacher_binding', 'not put in testable form: a statement with its source line, waiting '
                                                       'for a teacher binding to series the search carries'),
    ('code:', 'code_source_constructions', 'a source file whose constructions and methods are reached through the crosswalk; '
                                           'its claims live in prose sources'),
    ('source unreadable', 'missing_inputs', 'the catalog bytes of the source could not be read where the claims file was built'),
    ('series the search does not carry', 'unsupported_computation', 'the claim names series no search carries yet'),
    ('crosswalk anchor not found', 'missing_inputs', 'the declared anchor is not in the source bytes'),
    ('crosswalk source not in the catalog', 'missing_inputs', 'the declared source is not in the catalog or unreadable'),
)


def open_class(reason):
    for prefix, status, what in OPEN_CLASSES:
        if str(reason or '').startswith(prefix):
            return status, what
    return 'open_other', 'listed by the claims builder with its own reason'


def binding_identity(binding):
    """What makes a reproduction binding the same binding: its status, entry ids and source pins (path, revision,
    sha256), whether it is the tables' shape (entries with sources) or a lessons' projection (a flat sources list)."""
    if not isinstance(binding, dict):
        return None
    sources = [s for e in binding.get('entries') or [] for s in e.get('sources') or []] or list(binding.get('sources') or [])
    return dict(status=binding.get('status'), entry_ids=sorted(binding.get('entry_ids') or []),
                sources=sorted((str(s.get('path')), str(s.get('revision')), str(s.get('sha256'))) for s in sources))


def current_binding(claim, HC):
    """(binding, reform, superseded): the CURRENT declared tables always decide (Greg's step-5 direction, 2026-10-06: a
    known error fixed at its source must not stay active because a record froze it); a binding or reformulation the
    claim carries from an earlier freeze is compared and, when it differs, listed as superseded, never used."""
    binding, reform = HC.reproduction_of(claim['id']), HC.reformulation_of(claim['id'])
    superseded = {}
    retained = claim.get('reproduction')
    if retained is not None and binding_identity(retained) != binding_identity(binding):
        superseded['reproduction'] = dict(retained=binding_identity(retained), current=binding_identity(binding))
    retained_reform = claim.get('reformulation')
    if retained_reform is not None and retained_reform != reform:
        superseded['reformulation'] = dict(retained=retained_reform, current=reform)
    if superseded:
        superseded.update(binding_tables_sha256=HC.binding_tables_sha256(),
                          rule='the declared tables changed after this claim\'s binding was frozen into its lesson: the '
                               'retained binding is not used by any consumer; the lesson bytes stay as evidence; a '
                               'reproduction status read against the superseded binding is not established')
    return binding, reform, superseded or None


def reconsideration(doc, path, raw, claims, records_dir=None, records_selection=None):
    """The historical collection's standing, carried with every lessons file so neither teacher reads a mapped subset
    as the collection, nor a prior rejection label as closure (R11, R13). Four statuses, each counted and bound to the
    claims file by sha256; the full not_testable list stays in that file (path:line, catalog id, statement, reason).
    The reproduction status counts the declared bindings (defined / missing_inputs / not_bound / unmapped) and the
    hash-bound records read under records_dir (performed_matched / performed_differs / not_run); a binding marks nothing
    reproduced, and the bindings cover the mapped claims only: every not_testable statement has none and stays open."""
    import frankie_box_historical_claims as HC
    import frankie_box_historical_reproduction as HR
    not_testable = doc.get('not_testable') or []
    bindings, reforms, performed, records_listed, superseded_claims = {}, {}, {}, [], []
    for c in claims:
        binding, reform, superseded = current_binding(c, HC)
        if superseded:
            superseded_claims.append(dict(claim_id=c['id'],
                                          superseded=sorted(k for k in superseded if k in ('reproduction', 'reformulation'))))
        bindings[binding['status']] = bindings.get(binding['status'], 0) + 1
        reforms[reform['status']] = reforms.get(reform['status'], 0) + 1
        records, listed = HR.records_for(c['id'], records_dir if records_dir is not None else REPRODUCTION_DIR,
                                         selection=records_selection)
        records_listed.extend(listed)
        word = HR.status_of(records)
        performed[word] = performed.get(word, 0) + 1
    by_status = {}
    for item in not_testable:
        status, what = open_class(item.get('reason'))
        entry = by_status.setdefault(status, dict(count=0, what=what, reason_examples=[]))
        entry['count'] += 1
        if len(entry['reason_examples']) < 2 and item.get('reason') not in entry['reason_examples']:
            entry['reason_examples'].append(item.get('reason'))
    prior_labels = [dict(claim_id=c['id'], labels=list((c.get('source_claim') or {}).get('evidence') or []),
                         source_rework=(c.get('source_claim') or {}).get('research_rework'))
                    for c in claims]
    return dict(schema='FRANKIE_HISTORICAL_RECONSIDERATION_V1', catalog=doc.get('catalog'),
                catalog_sha256=doc.get('catalog_sha256'), catalog_version=doc.get('catalog_version'),
                claims_file=str(path), claims_file_sha256=sha256_bytes(raw), sources=len(doc.get('sources') or []),
                candidates=doc.get('candidates'), mapped_claims=len(claims), not_testable=len(not_testable),
                statuses=dict(
                    stored_evidence_reassessed=dict(
                        count=len(claims), status='performed_here_where_tests_exist',
                        what='the mapped claims, read against the stored search counts of the days given (results below); '
                             'a count comparison on stored evidence, NOT a reproduction of the original calculation'),
                    original_calculation_awaiting_teacher_reproduction=dict(
                        count=len(claims),
                        status='pending_teacher_work' if performed.get('pending_teacher_work') or performed.get('not_run')
                               or not performed else 'performed_where_bound',
                        bindings=dict(sorted(bindings.items())), records=dict(sorted(performed.items())),
                        records_listed=records_listed, binding_tables_sha256=HC.binding_tables_sha256(),
                        records_dir=str(records_dir if records_dir is not None else REPRODUCTION_DIR),
                        retained_bindings_superseded=superseded_claims,
                        records_selection_frozen=records_selection is not None,
                        what='each mapped claim\'s original calculation is traced to code at its exact revision '
                             '(REPRODUCTIONS: sources with sha256, entry point, inputs, recorded outputs); `records` counts '
                             'the hash-bound HISTORICAL_REPRODUCTION_V1 records a teacher\'s authorized execution wrote, by '
                             'status; a binding is not a reproduction; the bindings cover the mapped claims only, every '
                             'not_testable statement has none and stays open; Memory A claims are not_bound (Greg, 2026-10-06)'),
                    teacher_repair_or_reformulation=dict(
                        count=len(claims), status='pending_teacher_work', performed=0, needs=dict(sorted(reforms.items())),
                        what='REFORMULATIONS names, per mapped claim, what a declared repair or reformulation needs (a '
                             'condition, a transform, a window, a turn or entry definition: mathematical decisions held for '
                             'Greg); no repair or reformulation of a mapped or unmapped claim is performed or recorded here'),
                    missing_inputs_or_unsupported_computation_open=dict(
                        count=len(not_testable), status='OPEN_MAPPING_OR_REWORK_REQUIRED', by_status=by_status,
                        where='the claims file\'s not_testable list, each with path:line, catalog id, statement and reason; '
                              'carried by reference (claims_file_sha256), never dropped')),
                prior_labels=prior_labels,
                rule='a prior rejected/dead/no-good/discarded label is a claim about the claim (R11); it travels as a label '
                     'and never closes reconsideration (R13); a mapped subset is never the collection; nothing here is '
                     'closed by a disposition word (R14)')


def historical_claims(path, records_dir=None, records_selection=None):
    """HISTORICAL_CLAIMS_V1 (frankie_box_historical_claims.py): the catalog's claims, author 'historical'. Its claims
    are tested; its not_testable list travels with the lessons by reference, counted by open status (reconsideration).
    Each claim carries `reproduction` (its declared binding: frankie_box_historical_claims.reproduction_of) and
    `reformulation` (what a declared repair/reformulation needs: reformulation_of), attached here by claim id; the
    committed claims file is read, never rewritten. Records of performed reproductions are read by test(), not frozen here."""
    import frankie_box_historical_claims as HC
    raw = Path(path).read_bytes()
    doc = json.loads(raw)
    if doc.get('schema') != 'HISTORICAL_CLAIMS_V1':
        raise SystemExit('%s is not a HISTORICAL_CLAIMS_V1' % path)
    claims = [dict(id=c['id'], statement=c['statement'], kind='historical', series=list(c['series']),
                   direction=c.get('direction') if c.get('direction') in ('same', 'opposite') else None,
                   direction_text=c.get('direction'), lag=claimed_lag(c.get('lag')), cells=list(c.get('cells') or []),
                   condition=c.get('condition'), x_transform=c.get('x_transform', 'sign_of_step'),
                   y_transform=c.get('y_transform', 'sign_of_step'), source=c.get('source'), day_made=None,
                   source_claim=c, reproduction=HC.reproduction_of(c['id']), reformulation=HC.reformulation_of(c['id']))
              for c in doc.get('claims') or []]
    return dict(author='historical', stamp=doc['catalog_sha256'][:12], day=None, claims_sha256=sha256_bytes(raw),
                source=str(path), claims=claims,
                reconsideration=reconsideration(doc, path, raw, claims, records_dir=records_dir,
                                                records_selection=records_selection))


def frankie_claims(path, day):
    """Only Dipole findings and the sibling source-bound external-finding projection cross R09."""
    raw = Path(path).read_bytes()
    ledgers = json.loads(raw)
    findings = ledgers.get('dipole_novel_findings') or []
    external = []
    projection_path = Path(path).with_name('external-novel-findings.json')
    projection = None
    source_path = Path(path).with_name('external-code-answers.json')
    if projection_path.is_file() or source_path.is_file():
        source_raw = source_path.read_bytes()
        source_doc = json.loads(source_raw)
        if source_doc.get('schema') != 'FRANKIE_BOX_CLASSROOM_EXTERNAL_CODE_V1':
            raise ValueError('external classroom source schema differs')
        external = source_doc['ledgers']['external_novel_findings']
        if (not isinstance(external, list) or
                any(f.get('schema') != 'FRANKIE_DIPOLE_EXTERNAL_NOVEL_FINDING_V1' for f in external)):
            raise ValueError('external finding schema differs')
        projection = dict(schema='FRANKIE_EXTERNAL_FINDINGS_V1', day=day, findings=external,
                          source=dict(path=str(source_path), sha256=sha256_bytes(source_raw)))
        # Earlier V2 classrooms already retained the findings in this source. Read the same
        # legal subset in place when their separate projection file predates this wiring.
        if projection_path.is_file() and json.loads(projection_path.read_bytes()) != projection:
            raise ValueError('external finding projection differs from its retained source/day')
    claims = []
    for is_external, f in [(False, f) for f in findings] + [(True, f) for f in external]:
        refs = f.get('evidence_refs') or []
        series = [x for r in refs for x in (r.get('left'), r.get('right')) if x]
        premise = f.get('premise') or ''
        same = re.search(r'same way (\d+) times', premise)
        opposite = re.search(r'opposite way (\d+) times', premise)
        direction = None
        if same and opposite:
            s, o = int(same.group(1)), int(opposite.group(1))
            direction = 'same' if s > o else 'opposite' if o > s else None
        claim_id = 'external:' + f['finding_id'] if is_external else f.get('finding_id')
        claims.append(dict(id=claim_id, statement=premise,
                           kind='external_novel_finding' if is_external else 'novel_finding', series=series,
                           direction=direction, direction_text='step counts in the finding: same %s, opposite %s' % (
                               same.group(1) if same else '?', opposite.group(1) if opposite else '?'),
                           lag=None, cells=[], day_made=day, source_claim=f))
        if is_external:
            claims[-1].update(kind='external_finding_direction_projection',
                statement='Directional projection only of the external finding: ' + premise,
                projection_scope=dict(tested='claimed step direction against the existing scoped search counts',
                    not_tested='the original endpoint-versus-step structure on the classroom axis; '
                               'native search counts do not by themselves verify that complete structure'))
    # Preserve the old Dipole-only identity when no external projection exists. A V2 claim set binds both.
    bound = dict(dipole=findings, external=projection) if projection is not None else findings
    return dict(author='frankie', stamp=None, day=day, claims_sha256=sha256_bytes(json.dumps(bound, sort_keys=True).encode()),
                source=str(path), source_note='only novel findings; external IDs are namespaced; private answers excluded (R09)',
                claims=claims)


def load_searches(dirs):
    days = []
    for d in dirs:
        d = Path(d)
        manifest = json.loads((d / 'MANIFEST.json').read_bytes())
        # Greg 2026-10-06: all 30 days contribute learned knowledge, regardless of the old year/role label.
        # Exact search sources and separate per-day measurements remain bound below.
        days.append(dict(dir=d, day=manifest['day'], cycle=manifest['cycle'], lags=manifest['lags'],
                         series=manifest['series'], cells=[tuple(c) for c in manifest['cells']],
                         parts=[d / p['path'] for p in manifest['couplings']['parts']],
                         part_pins={p['path']: p.get('sha256') for p in manifest['couplings']['parts']},
                         native_retained=[x for x in manifest.get('notes') or [] if x.get('source') == 'native' and x.get('retained')],
                         native_reports=[x for x in manifest.get('sources') or [] if str(x.get('source', '')).startswith('native.')],
                         manifest_sha256=sha256_bytes((d / 'MANIFEST.json').read_bytes())))
    if len({x['day'] for x in days}) != len(days):
        raise SystemExit('the same day was given twice (duplicate data declines the run)')
    return days


# ------------------------------------------------------------------------------- completed native evidence, consumed
def _read_pinned(path, sha256, nbytes):
    data = Path(path).read_bytes()
    if len(data) != nbytes or sha256_bytes(data) != sha256:
        raise ValueError('retained native evidence differs from the search\'s pin: %s' % path)
    return json.loads(gzip.decompress(data) if str(path).endswith('.gz') else data)


def _finalize_rows(report):
    """Every FINALIZE (post-stream) row of an exact ledger, whole, by emitting section; the ledger is hashed while it
    streams and must equal the search's pin. Only the ordinals the search listed post_stream_knowledge_only are parsed."""
    ranges = ((report.get('dispositions') or {}).get('post_stream_knowledge_only') or {}).get('ordinal_ranges') or []
    wanted = []
    for r in ranges:
        lo, hi = (r[0], r[1]) if isinstance(r, (list, tuple)) else (r, r)
        wanted.append((int(lo), int(hi)))
    rows, hashed, size = {}, hashlib.sha256(), 0
    with open(report['path'], 'rb') as handle:
        for ordinal, raw in enumerate(handle):
            hashed.update(raw)
            size += len(raw)
            if any(lo <= ordinal <= hi for lo, hi in wanted):
                row = json.loads(raw)
                if (row.get('frankie_emission') or {}).get('phase') != 'FINALIZE':
                    raise ValueError('ordinal %d of %s is not a FINALIZE row the search listed post-stream' % (ordinal, report['path']))
                rows.setdefault(str(row.get('emitting_section') or 'member'), []).append(dict(ordinal=ordinal, row=row))
    if size != report.get('bytes') or hashed.hexdigest() != report.get('sha256'):
        raise ValueError('exact ledger differs from the search\'s pin: %s' % report['path'])
    return rows


def completed_native_evidence(d, out_root):
    """A searched day's completed native evidence, CONSUMED (Greg, 2026-10-06: not listed; read by the teachers): the
    files the search pinned and did not search, read whole with their bytes verified, written once per day under
    <out_root>/native/<day>-completed-native.json and carried in every lessons file for that day (both exchange seats
    read lessons). Exact numbers are evidence; an average is a labelled supplement, never evidence (D37); nothing is
    computed here. What is read: the receipt's verdict and gates; result.json's section summaries (the traversal's own
    numbers, whole) and its averaged companions (supplement); section 4.2's exact first and last book of each
    day-segment-phase and its declarations (its companion rows are averages: supplement); section 4.4's matching rule
    and its STREAM_END rows (its GROUP_CLOSE offers are already searched as native.lifecycle.mirror.*: cross-referenced,
    not duplicated); every FINALIZE row of the exact member and lifecycle ledgers, whole, by section (post-stream: no
    group, no axis position, so never a search step). Returns (reference, listed): the file's identity and counts, or
    what could not be read and why. A search with no native evidence is listed, not an error (older sources keep
    their actual coverage)."""
    listed = []
    retained = {x['role']: x for x in d.get('native_retained') or []}
    reports = {x['source']: x for x in d.get('native_reports') or []}
    if not retained:
        return None, [dict(day=d['day'], reason='the search carries no retained native evidence (none selected for this day)')]
    doc = dict(schema='FRANKIE_COMPLETED_NATIVE_EVIDENCE_V1', day=d['day'], search_manifest_sha256=d['manifest_sha256'],
               read_from={k: dict(path=v['retained'], sha256=v['sha256'], bytes=v['bytes']) for k, v in retained.items()},
               rule='exact numbers are evidence, read whole and bound by sha256; averages are labelled supplements (D37); '
                    'post-stream rows have no axis position and are never search steps; nothing is computed here')
    def get(role):
        x = retained.get(role)
        if x is None:
            listed.append(dict(day=d['day'], role=role, reason='not among the search\'s retained native files'))
            return None
        return _read_pinned(x['retained'], x['sha256'], x['bytes'])
    receipt = get('receipt')
    if receipt is not None:
        doc['receipt'] = {k: receipt.get(k) for k in ('verdict', 'failed_gates', 'groups', 'records', 'span_seconds',
                                                      'candidate_warmup_seconds', 'candidate_min_observations')}
    result = get('result')
    if result is not None:
        layers = result.get('layers') or {}
        summaries = (layers.get('exact_lifecycle_and_runway_ledger') or {}).get('section_summaries')
        averages = layers.get('averaged_companions') or {}
        doc['result'] = dict(layers=sorted(layers), section_summaries=summaries,
                             section_summaries_rule='the traversal\'s own section numbers, whole; evidence where exact',
                             averaged_companions=dict(rows=averages.get('rows'), key_alias_form=averages.get('key_alias_form'),
                                                      rule='averages: a supplement only, never evidence (D37)'))
    s42 = get('bedrock_section_4_2')
    if s42 is not None:
        doc['section_4_2'] = dict(first_last_pairs=s42.get('first_last_pairs'), declarations=s42.get('declarations'),
                                  status=s42.get('status'), reason=s42.get('reason'), count=s42.get('count'),
                                  companion_rows=dict(rows=s42.get('companion_rows'), rule='averages: supplement only (D37)'),
                                  rule='the exact first and last book of each day-segment-phase: evidence; the books '
                                       'themselves are already on the frame axis, so these are read, not re-searched')
    s44 = get('bedrock_section_4_4')
    if s44 is not None:
        rows = s44.get('lifecycle_rows') or []
        live = [r for r in rows if (r.get('frankie_emission') or {}).get('phase') == 'GROUP_CLOSE']
        ended = [r for r in rows if (r.get('frankie_emission') or {}).get('phase') != 'GROUP_CLOSE']
        doc['section_4_4'] = dict(matching_rule=s44.get('matching_rule'), status=s44.get('status'), reason=s44.get('reason'),
                                  group_close_rows=len(live), stream_end_rows=ended,
                                  rule='GROUP_CLOSE offers are searched as native.lifecycle.mirror.* (not duplicated '
                                       'here); STREAM_END rows are post-stream knowledge, read whole')
    finalize = {}
    for name in ('native.member', 'native.lifecycle'):
        report = reports.get(name)
        if report is None:
            listed.append(dict(day=d['day'], role=name, reason='no search report of this ledger'))
            continue
        try:
            finalize[name] = _finalize_rows(report)
        except FileNotFoundError:
            listed.append(dict(day=d['day'], role=name, reason='the exact ledger is not at %s' % report.get('path')))
    doc['finalize_rows'] = dict(by_ledger={k: {sec: len(v) for sec, v in rows.items()} for k, rows in finalize.items()},
                                rows=finalize, rule='every FINALIZE row the search listed post_stream_knowledge_only, whole')
    doc['listed'] = listed
    data = (json.dumps(doc, indent=1, sort_keys=True) + '\n').encode()
    path = Path(out_root) / 'native' / ('%s-completed-native.json' % d['day'])
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError('%s exists with different bytes: the pinned native evidence changed; move it aside first' % path)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    # C1: the reference's IDENTITY is its content, sources and owning manifest (identity below), never where this owner
    # materialized it (path): identical bytes under another output root are the same evidence; different bytes for the
    # same frozen owner are different evidence (native_evidence_identity compares them).
    reference = dict(path=str(path), sha256=sha256_bytes(data), bytes=len(data), day=d['day'],
                     search_manifest_sha256=d['manifest_sha256'], read_from=doc['read_from'],
                     identity=dict(day=d['day'], search_manifest_sha256=d['manifest_sha256'], sha256=sha256_bytes(data),
                                   bytes=len(data), read_from=doc['read_from']),
                     counts=dict(first_last_pairs=len((doc.get('section_4_2') or {}).get('first_last_pairs') or []),
                                 stream_end_rows=len((doc.get('section_4_4') or {}).get('stream_end_rows') or []),
                                 finalize_rows=doc['finalize_rows']['by_ledger'],
                                 averaged_rows=len(((doc.get('result') or {}).get('averaged_companions') or {}).get('rows') or [])),
                     receipt=doc.get('receipt'), matching_rule=(doc.get('section_4_4') or {}).get('matching_rule'),
                     listed=listed)
    return reference, listed


def native_evidence_identity(reference):
    """The storage-independent identity of a completed-native reference (C1): its own `identity` when it carries one,
    else everything but the materialization path (an older reference), so two readings of the same bytes under
    different output roots compare equal and different evidence never does."""
    if not isinstance(reference, dict):
        return reference
    if isinstance(reference.get('identity'), dict):
        return reference['identity']
    return {k: v for k, v in reference.items() if k != 'path'}


def match(name, series):
    """Every search series the claimed name matches (normalized: equal to the whole name, to its part after the source,
    or contained in it); [] = not in the search."""
    n = norm(name)
    if not n:
        return []
    out = []
    for s in series:
        whole, tail = norm(s), norm(s.split('.', 1)[-1])
        if n in (whole, tail) or (len(n) >= 4 and (n in whole)):
            out.append(s)
    return out


def series_role(name):
    """The source ROLE of one search series name, by the reserved search's own classification (Greg, 2026-10-06: market
    conditions only): 'market' for a market quantity; 'context_only' for an ID / date / weekday / entity label that may
    group observations as a search condition; otherwise the search's exclusion reason (bookkeeping, hashes, clocks,
    availability or integrity diagnostics). Older retained searches may still carry such
    channels as series; this reader names them wherever it consumes a row (C2)."""
    import frankie_box_experiment_search as SEARCH
    reason = SEARCH.non_market_reason(name)
    return 'market' if reason is None else reason


def role_reasons(x, y):
    """Why a row of (x, y) is counts only (C2): either side is not a market quantity."""
    reasons = []
    for side, name in (('x', x), ('y', y)):
        role = series_role(name)
        if role == 'context_only':
            reasons.append('%s "%s" is a context label (ID / date / weekday / entity): it may group market signals as a '
                           'search condition and is not a signal, target or explanation; association with it is not a '
                           'market finding' % (side, name))
        elif role != 'market':
            reasons.append('%s "%s" is not a market quantity (%s): retained counts, never a market finding' % (side, name, role))
    return reasons


def row_scope_reasons(claim, row, reverse=False):
    """Decide whether existing counts answer this claim; never alter or recompute the search mathematics."""
    reasons = []
    source = claim.get('source_claim') or {}
    transforms = (claim.get('x_transform', source.get('x_transform', 'sign_of_step')),
                  claim.get('y_transform', source.get('y_transform', 'sign_of_step')))
    if reverse:
        transforms = transforms[::-1]
    actual = (row.get('x_transform', row.get('transform', 'sign_of_step')),
              row.get('y_transform', 'sign_of_step'))
    if actual != transforms:
        reasons.append('another transform pair than the claim')
    lag = claim.get('lag')
    raw_lag = source.get('lag')
    if raw_lag is not None and str(raw_lag).strip() and not re.fullmatch(r'[+-]?\d+', str(raw_lag).strip()):
        reasons.append('the stated lag relation has no exact searched-lag binding')
    elif lag is not None and row['best_lag'] != (-lag if reverse else lag):
        reasons.append('the selected search lag is not the claimed lag in this pair orientation')
    cells = claim.get('cells') or source.get('cells') or []
    labels = {str(row['cell']), '%s=%s' % (row['cell'], row['cell_value']),
              '%s %s' % (row['cell'], row['cell_value'])}
    if row['cell_value'] is not None:
        labels.add(str(row['cell_value']))
    if cells and not any(str(cell) in labels for cell in cells):
        reasons.append('the row is outside the explicitly named cells')
    if claim.get('condition') or source.get('condition'):
        reasons.append('the claimed condition has not been applied to these search counts')
    return reasons


MIRROR_FIELDS = ('same_way', 'opposite', 'both_moving', 'steps', 'null_shifts', 'null_at_or_beyond', 'null_largest',
                 'null_exclusion', 'beyond_chance')   # the whole chance-check contract of couple(): exclusion = max(2L+1, m//10)
                                                     # and beyond_chance = shifts > 0 and reached == 0 are functions of the
                                                     # fields before them, so a true mirror carries them equal; named, not assumed


def mirror_of(row, forward_rows):
    """The forward-orientation row this reversed row mirrors, or None. The search writes every ordered pair, and for
    (y, x) the statistic is the (x, y) one read backwards: D_yx[k] = D_xy[-k], so the counts at the negated best lag
    are the same measurement. Reading it as another test would count the same evidence twice (its tie-break can pick
    the other sign of a tied lag; then nothing mirrors and the row is read on its own, as before)."""
    for f in forward_rows:
        if (f['cell'] == row['cell'] and f['cell_value'] == row['cell_value']
                and f.get('x_transform', f.get('transform')) == row.get('y_transform', 'sign_of_step')
                and f.get('y_transform', 'sign_of_step') == row.get('x_transform', row.get('transform'))
                and f['best_lag'] == -row['best_lag'] and all(f.get(k) == row.get(k) for k in MIRROR_FIELDS)):
            return f
    return None


def test(claims_doc, days, records_dir=None, records_selection=None):
    """records_dir / records_selection (B5): the OWNER's reproduction records directory and the selection of its files
    the owner froze with its other inputs (frankie_box_historical_reproduction.record_selection at the freeze); without
    them the module default REPRODUCTION_DIR is read live (the CLI route). With a frozen selection only those files are
    read, bytes-verified, and later arrivals are listed apart, so a restart of the same frozen operation reads the same
    records and a new file never changes a result across claims."""
    wanted = {}
    per_claim = []
    for c in claims_doc['claims']:
        matched, missing = {}, []
        for name in c['series']:
            if c.get('series_exact'):
                # a precisely named candidate (the search's own series name) is never broadened by the fuzzy matcher
                hits = [name] if any(name in d['series'] for d in days) else []
            else:
                hits = sorted({s for d in days for s in match(name, d['series'])})
            (matched.__setitem__(name, hits) if hits else missing.append(name))
        pairs = sorted({(a, b) for i, x in enumerate(c['series']) for y in c['series'][i + 1:]
                        for a in matched.get(x, []) for b in matched.get(y, []) if a != b})
        for a, b in pairs:
            wanted[(a, b)] = wanted[(b, a)] = True
        per_claim.append((c, matched, missing, pairs))
    rows = {}
    for d in days:
        for part in d['parts']:
            rel = str(Path(part).relative_to(d['dir']))
            with open(part) as handle:
                for ordinal, line in enumerate(handle):
                    r = json.loads(line)
                    if (r['x'], r['y']) in wanted:
                        # the row's exact identity: its part (the search's pin), its ordinal and the raw line's sha256,
                        # the same three values Run.search_knowledge records for a candidate (part_sha256, row, row_sha256)
                        r['_where'] = dict(part=rel, part_sha256=(d.get('part_pins') or {}).get(rel), row=ordinal,
                                           row_sha256=sha256_bytes(line.encode()))
                        rows.setdefault((d['day'], r['x'], r['y']), []).append(r)
    results = []
    for c, matched, missing, pairs in per_claim:
        tests, verdicts, challenges, mirrored = [], [], [], []
        origin = c.get('origin') or {}
        origin_evidence = []
        source_row = c.get('source_claim') if origin else None
        origin_part_bound, origin_row_found = None, False
        for d in days:
            for a, b in pairs:
                forward = rows.get((d['day'], a, b), [])
                for x, y in ((a, b), (b, a)):
                    for r in rows.get((d['day'], x, y), []):
                        m = mirror_of(r, forward) if (x, y) == (b, a) else None
                        observed = 'same' if r['same_way'] > r['opposite'] else 'opposite' if r['opposite'] > r['same_way'] else 'even'
                        tx, ty = r.get('x_transform', r.get('transform', 'sign_of_step')), r.get('y_transform', 'sign_of_step')
                        if origin and d['day'] == origin.get('day'):
                            # the candidate's own discovery day: its rows are the evidence the candidate was read from.
                            # Listed with their counts (a reversed row that mirrors a forward one included, marked as the
                            # mirror), never marked held/shown_otherwise, never counted as a test, never dropped.
                            same_row = bool(source_row) and all(
                                r.get(k) == source_row.get(k) for k in ('x', 'y', 'cell', 'cell_value', 'transform',
                                                                       'x_transform', 'y_transform', 'best_lag',
                                                                       'same_way', 'opposite', 'both_moving', 'steps'))
                            where = r['_where']
                            # the discovery row's identity: the candidate's part sha256, ordinal and raw-line sha256,
                            # all three equal to this row's own; field equality is reported beside it, never instead
                            bound = (where['part_sha256'] == origin.get('part_sha256') and where['row'] == origin.get('row')
                                     and where['row_sha256'] == origin.get('row_sha256'))
                            origin_row_found = origin_row_found or bound
                            origin_part_bound = origin.get('part_sha256') in set((d.get('part_pins') or {}).values())
                            origin_evidence.append(dict(
                                day=d['day'], x=x, y=y, cell=r['cell'], cell_value=r['cell_value'], transform=r['transform'],
                                x_transform=tx, y_transform=ty, lag=r['best_lag'], steps=r['steps'], where=where,
                                counts=dict(same_way=r['same_way'], opposite=r['opposite'], both_moving=r['both_moving'],
                                            x_moves=r['x_moves'], y_moves=r['y_moves']),
                                chance_check=dict(shifts=r['null_shifts'], reached=r['null_at_or_beyond'],
                                                  largest=r['null_largest'], exclusion=r['null_exclusion']),
                                beyond_chance=r['beyond_chance'], search_manifest_sha256=d['manifest_sha256'],
                                series_roles=dict(x=series_role(x), y=series_role(y)), role_reasons=role_reasons(x, y),
                                discovery_row=bound, fields_equal=same_row, origin_part_in_search=origin_part_bound,
                                mark='origin_evidence_mirror' if m is not None else 'origin_evidence',
                                mirror_of=(dict(x=m['x'], y=m['y'], lag=m['best_lag'], where=m['_where']) if m is not None else None),
                                reason='the discovery day: reading the discovery evidence again is not an independent '
                                       'check and is not another occurrence'))
                            continue
                        if m is not None:
                            mirrored.append(dict(day=d['day'], x=x, y=y, cell=r['cell'], cell_value=r['cell_value'],
                                                 lag=r['best_lag'], where=r['_where'],
                                                 mirror_of=dict(x=m['x'], y=m['y'], lag=m['best_lag'], where=m['_where']),
                                                 mark='mirror', reason='the reversed orientation of the same pair, cell '
                                                 'and transform pair at the negated lag carries the same counts: one '
                                                 'measurement, listed once, never a second test'))
                            continue
                        roles = dict(x=series_role(x), y=series_role(y))
                        scope_reasons = role_reasons(x, y) + list(row_scope_reasons(c, r, reverse=(x, y) == (b, a)))
                        if scope_reasons:
                            mark = 'counts_only'  # retained observations, never evidence for an unapplied claim scope
                        elif c['direction'] is None or not r['beyond_chance']:
                            mark = 'unresolved'
                        elif observed == c['direction']:
                            mark = 'held'
                        else:
                            mark = 'shown_otherwise'
                            challenges.append(
                                'the data is showing this instead: on %s (%s%s), %s and %s moved the same way %d times and '
                                'the opposite way %d times at lag %d (x leads y at a positive lag), beyond all %d far shifts; '
                                'the claim said %s' % (d['day'], r['cell'], '' if r['cell_value'] is None else '=%s' % r['cell_value'],
                                                     x, y, r['same_way'], r['opposite'], r['best_lag'], r['null_shifts'], c['direction']))
                        verdicts.append(mark)
                        tests.append(dict(day=d['day'], x=x, y=y, cell=r['cell'], cell_value=r['cell_value'],
                                          transform=r['transform'], x_transform=tx, y_transform=ty,
                                          lag=r['best_lag'], steps=r['steps'], where=r['_where'],
                                          counts=dict(same_way=r['same_way'], opposite=r['opposite'], both_moving=r['both_moving'],
                                                      x_moves=r['x_moves'], y_moves=r['y_moves']),
                                          chance_check=dict(shifts=r['null_shifts'], reached=r['null_at_or_beyond'],
                                                            largest=r['null_largest'], exclusion=r['null_exclusion']),
                                          mark=mark, scope_not_tested=scope_reasons, days_named=[d['day']],
                                          series_roles=roles))
        held, other = verdicts.count('held'), verdicts.count('shown_otherwise')
        disposition = ('INSUFFICIENT_EVIDENCE' if not tests else 'SUPPORTED_SCOPED' if held and not other
                       else 'CONTRADICTED_SCOPED' if other and not held else 'PLAUSIBLE_UNRESOLVED')
        untested = []
        untested.extend(dict.fromkeys(reason for t in tests for reason in t['scope_not_tested']))
        if c['lag'] is not None and days and abs(c['lag']) > min(d['lags'] for d in days):
            untested.append('the claimed lag %d is outside the searched window of +-%d' % (c['lag'], min(d['lags'] for d in days)))
        for cell in c['cells']:
            if not any(norm(cell) in norm('%s %s' % cv) for d in days for cv in d['cells']):
                untested.append('the claimed cell "%s" was not a cell of the search' % cell)
        if c.get('condition'):
            untested.append('the claimed condition "%s" is not applied by the search (conditions not searched yet): the '
                            'counts are over every step of the cell' % c['condition'])
        if c['direction'] is None:
            untested.append('no direction stated in a testable form ("%s"): counts reported, nothing marked held' % c['direction_text'])
        # C2: the claim's own series names classified the same way; a claimed bookkeeping / context series can
        # only be counts, never a market finding, and the claim says so in its untested list.
        for name in c['series']:
            for hit in matched.get(name, []):
                role = series_role(hit)
                if role != 'market':
                    untested.append('the claimed series "%s" (search series "%s") is %s: its rows are retained as counts '
                                    'only; no market finding rests on it' % (name, hit, 'a context label that may group '
                                    'market signals, not a signal' if role == 'context_only' else 'not a market quantity (%s)' % role))
        claimed = (c.get('x_transform', 'sign_of_step'), c.get('y_transform', 'sign_of_step'))
        if not any(t['x_transform'] == claimed[0] and t['y_transform'] == claimed[1] for t in tests):
            untested.append('no search row carries the claimed transform pair %s -> %s on the days given' % claimed)
        if origin:
            if origin.get('day') not in {d['day'] for d in days}:
                untested.append('the origin day %s search was not among the searches given; its discovery row is bound by '
                                'the candidate\'s own provenance, not re-read here' % origin.get('day'))
            elif origin_part_bound is False:
                untested.append('the origin part sha256 %s is not among the parts of the %s search given: the discovery '
                                'row is bound by the candidate\'s provenance only, not identified in that search'
                                % (str(origin.get('part_sha256'))[:12], origin.get('day')))
            elif not origin_row_found:
                untested.append('the discovery row (part %s, row %s, raw-line sha256 %s) was not found among the rows of '
                                'the %s search given for this pair: the origin evidence listed is by field reading only'
                                % (str(origin.get('part_sha256'))[:12], origin.get('row'),
                                   str(origin.get('row_sha256'))[:12], origin.get('day')))
            if not tests:
                untested.append('no completed search of another day was given that carries this pair, cell and transform '
                                'pair: the candidate has its origin evidence only; whether a scientifically checked single '
                                'occurrence is accepted is the pending step #5 decision, not decided by this word')
        result = dict(claim_id=c['id'], statement=c['statement'], author=claims_doc['author'], day_made=c['day_made'],
                      series_matched=matched,
                      cannot_test_yet=[dict(series=m, reason='not in the search (no series of this %sname on any day '
                                                             'given)' % ('exact ' if c.get('series_exact') else ''))
                                       for m in missing],
                      tests=tests, counts=dict(tests=len(tests), held=held, shown_otherwise=other,
                                               unresolved=verdicts.count('unresolved'),
                                               counts_only=verdicts.count('counts_only')),
                      days_tested=sorted({t['day'] for t in tests}), disposition=disposition,
                      disposition_note='orientation only (R14); the counts and days above are the finding',
                      challenge=challenges, untested=untested, mirrored_rows=mirrored,
                      market_context=dict(
                          roles={name: series_role(name) for hits in matched.values() for name in hits},
                          context_only_rows=sum(1 for t in tests if 'context_only' in t['series_roles'].values()),
                          non_market_rows=sum(1 for t in tests if any(v not in ('market', 'context_only')
                                                                      for v in t['series_roles'].values())),
                          cells_rule='the row\'s cell and cell_value group the observations the counts are over; the counts '
                                     'are attributed to the market conditions inside the group, never to the label',
                          rule='market conditions only (Greg, 2026-10-06): a row whose x or y is a context label or a '
                               'bookkeeping / clock / diagnostic channel is counts_only; dates, days and IDs stay attached '
                               'to every row (day, cell, where) as searchable context'))
        source_rework = (c.get('source_claim') or {}).get('research_rework')
        if source_rework is not None or claims_doc['author'] == 'historical':
            # R11/R13: a stored-count reassessment is one status; reproduction and repair stay pending until a teacher
            # performs them; a prior label (the source's evidence list) is carried, never read as closure.
            # The reproduction status is READ, never set here: a hash-bound HISTORICAL_REPRODUCTION_V1 record under
            # REPRODUCTION_DIR (written by the teachers' authorized execution through frankie_box_historical_reproduction)
            # gives performed_matched / performed_differs / not_run; without one the claim's declared binding is named
            # and the status stays pending_teacher_work (not_bound for the retired Memory A claims).
            import frankie_box_historical_claims as HC
            import frankie_box_historical_reproduction as HR
            binding, reform, superseded = current_binding(c, HC)
            directory = records_dir if records_dir is not None else REPRODUCTION_DIR
            records, records_listed = HR.records_for(c['id'], directory, selection=records_selection)
            reproduction = HR.status_of(records)
            if reproduction == 'pending_teacher_work' and binding['status'] == 'not_bound':
                reproduction = 'not_bound'
            result['research_rework'] = dict(source_rework or {}, status='OPEN_REWORK_REQUIRED', closed=False,
                stored_evidence_reassessed=dict(performed=bool(tests), disposition=disposition,
                                                days=sorted({t['day'] for t in tests}), counts=result['counts'],
                                                rule='a count comparison on stored search evidence, not a reproduction'),
                original_calculation_reproduction=reproduction,
                binding_tables_sha256=HC.binding_tables_sha256(), retained_binding_superseded=superseded,
                reproduction_binding=dict(status=binding['status'], entry_ids=binding.get('entry_ids') or [],
                                          reason=binding.get('reason'),
                                          sources=[dict(path=s['path'], revision=s['revision'], sha256=s['sha256'],
                                                        catalog_id=s.get('catalog_id'))
                                                   for e in binding.get('entries') or [] for s in e.get('sources') or []],
                                          inputs_missing=[i.get('path') for e in binding.get('entries') or []
                                                          for i in e.get('inputs') or [] if i.get('status') != 'committed'],
                                          rule='a declared binding; not a reproduction'),
                reproduction_records=dict(records=records, listed=records_listed, directory=str(directory),
                                          selection_frozen=records_selection is not None,
                                          summary=HR.status_summary(records),
                                          rule='every admitted record\'s own status is kept beside the one-word summary; '
                                               'listed records are named with their reason, never dropped'),
                repair_or_reformulation='not_bound' if reform['status'] == 'not_bound' else 'pending_teacher_work',
                reformulation_needs=dict(status=reform['status'], kind=reform.get('kind'), needs=list(reform.get('needs') or []),
                                         where=list(reform.get('where') or []), decision=reform.get('decision')),
                construction=c.get('construction') or (c.get('source_claim') or {}).get('construction'),
                prior_labels=list((c.get('source_claim') or {}).get('evidence') or []),
                rule='a prior rejected/dead/no-good label is a claim about the claim and cannot close reconsideration; '
                     'this result reassesses stored evidence only; the reproduction status is read from a hash-bound '
                     'record of the teachers\' own execution, never set by this reader; repair/reformulation needs are '
                     'named, none is performed here')
        if origin:
            result.update(origin=origin, origin_evidence=origin_evidence,
                          origin_rule='origin-day rows are listed, never counted: the disposition and days_tested cover '
                                      'the other days only; no occurrence minimum or rarity label is applied (R06)')
        results.append(result)
    return results


def write(doc, days, results, out_dir, map_url=None, log=print, brain_dir='/opt/frankie-box/brain', native=None):
    schema = {'jev': 'JEV_LESSONS_V1', 'frankie': 'FRANKIE_LESSONS_V1', 'historical': 'HISTORICAL_LESSONS_V1',
              'search': 'SEARCH_CANDIDATE_LESSONS_V1'}[doc['author']]
    if doc['author'] == 'historical':
        doc = dict(doc, day='-'.join(sorted(d['day'] for d in days)))      # the days tested, each still on its own
    # Carry the exact legal claim projection used by test(), so another owning lane need not open private
    # classroom ledgers or a giant source merely to recover the claim's direction, lag and construction.
    claim_inputs = dict(schema='FRANKIE_SCIENTIFIC_CLAIM_INPUTS_V1', author=doc['author'],
                        claims_sha256=doc['claims_sha256'], claims=doc['claims'],
                        reader_sha256=sha256_bytes(Path(__file__).read_bytes()))
    claim_inputs_sha256 = sha256_bytes(json.dumps(claim_inputs, sort_keys=True).encode())
    lessons = dict(schema=schema, author=doc['author'], day=doc['day'], stamp=doc['stamp'], claims_sha256=doc['claims_sha256'],
                   claims_source=doc['source'], written_by='scientific_teacher', at=time.time(),
                   claim_inputs=claim_inputs, claim_inputs_sha256=claim_inputs_sha256,
                   searches=[dict(day=d['day'], cycle=d['cycle'], dir=str(d['dir']), manifest_sha256=d['manifest_sha256'])
                             for d in days],
                   results=results, model_calls=0,
                   rule='each day on its own, never pooled; counts are the finding, the disposition word is orientation')
    if doc.get('reconsideration') is not None:
        lessons['reconsideration'] = doc['reconsideration']
    if native is not None:
        lessons['completed_native_evidence'] = dict(
            by_day={day: ref for day, (ref, _) in native.items() if ref is not None},
            listed=[item for _, listed in native.values() for item in listed],
            rule='each searched day\'s completed native evidence (receipt, result summaries, sections 4.2/4.4, FINALIZE '
                 'rows) read whole and bound by sha256 for both exchange seats; exact numbers are evidence, averages '
                 'are labelled supplements (D37); post-stream rows are never search steps')
    if doc['author'] == 'search':
        lessons.update(source_manifest_sha256=doc.get('source_manifest_sha256'),
                       origin_rule='the candidates\' own discovery day is origin evidence, listed per claim and never '
                                   'counted as a test; acceptance/survivor treatment is not decided by this file',
                       publication='retained only; no brain writer admits author search yet')
    data = json.dumps(lessons, indent=1, sort_keys=True).encode()
    name = '%s-%s.json' % (doc['day'], doc['stamp'] or 'frankie')
    path = Path(out_dir) / doc['author'] / name
    if path.exists():
        raise SystemExit('%s exists: these claims were already taught (duplicate data declines the run)' % path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    log('%s lessons: %d claims, %s -> %s' % (doc['author'], len(results),
                                              json.dumps({k: sum(r['disposition'] == k for r in results) for k in DISPOSITIONS}), path))
    if doc['author'] == 'jev' and map_url:
        key = 'put:clm-sidecar/jev-brain/lessons/%s' % name
        entries = json.loads(urllib.request.urlopen(map_url, timeout=60).read())
        if key not in entries:
            raise SystemExit('no presigned slot %s in MAP_URL (dispatch with presign=put:frankie-granite42-568968024170-us-east-1/%s)'
                             % (key, key[4:]))
        request = urllib.request.Request(entries[key]['url'], data=data, method='PUT')
        with urllib.request.urlopen(request, timeout=300) as response:
            log('uploaded to Jev\'s brain: %s HTTP %d' % (key[4:], response.status))
    if doc['author'] == 'search':
        log('search candidate lessons retained, NOT published: frankie_box_brain.write_lessons_entry admits the authors '
            'frankie/historical/jev only (its edit, and the LESSONS maps of frankie_box_teacher_knowledge.py and '
            'frankie_box_experiment_exchange.py, are named for Codex in CCODE_STEP4_SOURCE_ROUTE_20261006.md) -> %s' % path)
        return path
    publish_lessons(path, brain_dir=brain_dir, log=log)

    return path



def publish_lessons(path, brain_dir='/opt/frankie-box/brain', log=print):
    """Publish completed test results, including recovery after the result file preceded brain publication.

    This is exact-byte reuse of completed scientific work, never another test or an independent confirmation.
    """
    import frankie_box_brain as brain
    path = Path(path)
    raw = path.read_bytes()
    lesson = json.loads(raw)
    author = lesson.get('author')
    schemas = {'frankie': 'FRANKIE_LESSONS_V1', 'historical': 'HISTORICAL_LESSONS_V1', 'jev': 'JEV_LESSONS_V1',
               'search': 'SEARCH_CANDIDATE_LESSONS_V1'}
    if author not in schemas or lesson.get('schema') != schemas[author] or lesson.get('written_by') != 'scientific_teacher':
        raise ValueError('only completed scientific-teacher lessons may be published')
    if author == 'search':
        raise ValueError('SEARCH_CANDIDATE_LESSONS_V1 has no brain writer: frankie_box_brain.write_lessons_entry admits the '
                         'authors frankie/historical/jev only; the result file is retained, not published (%s)' % path)
    if author == 'jev' and not lesson.get('knowledge_retest'):
        _, reused = brain.write_stage_entry(
            brain_dir, lesson['day'], 'jev-tested', [path],
            summary=dict(author='jev', claims_sha256=lesson['claims_sha256'],
                         searches=[d['day'] for d in lesson['searches']],
                         dispositions={k: sum(r['disposition'] == k for r in lesson['results']) for k in DISPOSITIONS}))
        log('tested Jev knowledge published%s' % (' (reused)' if reused else ''))
        return
    days = [lesson['day']] if author in ('frankie', 'jev') else list(dict.fromkeys(d['day'] for d in lesson['searches']))
    digest = sha256_bytes(raw)
    for day in days:
        entry = Path(brain_dir) / ('%s-lessons' % day)
        manifest_path = entry / 'MANIFEST.json'
        manifest = json.loads(manifest_path.read_bytes()) if manifest_path.is_file() else {}
        existing = next((e for e in manifest.get('entries', []) if e.get('sha256') == digest), None)
        if existing:
            source = entry / existing['name']
            if source.read_bytes() != raw:
                raise ValueError('published scientific-teacher lessons differ from their source: %s' % source)
            log('teacher knowledge %s (exact bytes reused)' % entry)
        else:
            brain.write_lessons_entry(brain_dir, day, path)
            log('teacher knowledge published into %s' % entry)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--search', action='append', required=True, help='a completed experiment search directory (repeat per day)')
    p.add_argument('--jev-claims', help='a JEV_CLAIMS_V1 file (Jev\'s claims of one day)')
    p.add_argument('--jev-stamp', help='fetch clm-sidecar/<stamp>/jev/claims.json through MAP_URL (presign getprefix) instead')
    p.add_argument('--frankie-ledgers', help='Frankie\'s classroom ledgers.json of one day (only its novel findings are read)')
    p.add_argument('--frankie-day', help='the day of those ledgers (YYYYMMDD)')
    p.add_argument('--historical-claims', help='a HISTORICAL_CLAIMS_V1 file (frankie_box_historical_claims.py)')
    p.add_argument('--search-findings', help='a FRANKIE_SEARCH_FINDINGS_V1 file (knowledge-findings.json of one day\'s '
                                             'search): its candidates tested on the OTHER searches given; the candidates\' '
                                             'own day is listed as origin evidence, never as a test')
    p.add_argument('--brain', default='/opt/frankie-box/brain', help='the owning lane plan\'s knowledge directory')
    p.add_argument('--accumulated-day', help='test completed legal knowledge on this one owning day, without a classroom')
    p.add_argument('--accumulated-out', help='the retained accumulated-input/result directory; paired with --accumulated-day')
    a = p.parse_args()
    if a.accumulated_day or a.accumulated_out:
        if (not a.accumulated_day or not re.fullmatch('[0-9]{8}', a.accumulated_day) or
                not a.accumulated_out or len(a.search) != 1 or
                any((a.jev_claims, a.jev_stamp, a.frankie_ledgers, a.frankie_day, a.historical_claims, a.search_findings))):
            p.error('accumulated mode requires one search, --accumulated-day YYYYMMDD and --accumulated-out only')
        import frankie_box_teacher_knowledge as TK
        from frankie_box_durable import write_json, witness
        out = Path(a.accumulated_out)
        result = TK.teach_accumulated(a.accumulated_day, a.search[0], a.brain, out)
        receipt = dict(schema='FRANKIE_ACCUMULATED_LESSONS_V1', day=a.accumulated_day, status='complete',
                       search=witness(Path(a.search[0]) / 'MANIFEST.json'), accumulated_claim_tests=result,
                       model_calls=0)
        write_json(out / 'receipt.json', receipt)
        print(json.dumps(receipt, sort_keys=True), flush=True)
        return
    if a.jev_stamp and not a.jev_claims:
        key = 'clm-sidecar/%s/jev/claims.json' % a.jev_stamp
        entries = json.loads(urllib.request.urlopen(os.environ['MAP_URL'], timeout=60).read())
        if key not in entries:
            raise SystemExit('no presigned GET for %s in MAP_URL (dispatch with presign=getprefix:frankie-granite42-'
                             '568968024170-us-east-1/clm-sidecar/%s/jev/)' % (key, a.jev_stamp))
        target = ROOT / 'inputs' / ('%s-claims.json' % a.jev_stamp)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(urllib.request.urlopen(entries[key]['url'], timeout=300).read())
        a.jev_claims = str(target)
    if a.frankie_ledgers and not (a.frankie_day and len(a.frankie_day) == 8 and a.frankie_day.isdigit()):
        raise SystemExit('--frankie-day YYYYMMDD required with --frankie-ledgers')
    if not (a.jev_claims or a.frankie_ledgers or a.historical_claims or a.search_findings):
        raise SystemExit('give --jev-claims / --jev-stamp, --frankie-ledgers, --historical-claims and/or --search-findings')
    days = load_searches(a.search)
    native = {d['day']: completed_native_evidence(d, ROOT) for d in days}
    for day, (ref, listed) in native.items():
        print('completed native evidence %s: %s' % (day, 'read, %s' % json.dumps(ref['counts'], sort_keys=True) if ref
                                                       else '; '.join(x['reason'] for x in listed)), flush=True)
    candidates = []
    if a.search_findings:
        import frankie_box_candidate_claims as CC
        candidates = [CC.candidate_claims(a.search_findings)]
        if all(d['day'] == candidates[0]['day'] for d in days):
            raise SystemExit('--search-findings needs at least one completed search of ANOTHER day: the candidates\' own '
                             'day %s is origin evidence, not a test' % candidates[0]['day'])
    for doc in ([jev_claims(a.jev_claims)] if a.jev_claims else []) + \
               ([frankie_claims(a.frankie_ledgers, a.frankie_day)] if a.frankie_ledgers else []) + \
               ([historical_claims(a.historical_claims)] if a.historical_claims else []) + candidates:
        write(doc, days, test(doc, days), ROOT, os.environ.get('MAP_URL'), brain_dir=a.brain, native=native)


if __name__ == '__main__':
    main()
