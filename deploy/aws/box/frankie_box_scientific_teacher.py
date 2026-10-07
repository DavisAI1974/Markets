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
import urllib.error
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


def jev_claims(path, seal_path=None):
    raw = Path(path).read_bytes()
    doc = json.loads(raw)
    if doc.get('schema') != 'JEV_CLAIMS_V1':
        raise SystemExit('%s is not a JEV_CLAIMS_V1' % path)
    # Legacy claims remain readable for inspection, but cannot enter a new scientific
    # operation without the consuming owner's pre-comparison blind seal.
    seal_path = Path(seal_path) if seal_path is not None else Path(path).with_name('claims-seal.json')
    seal = None
    if seal_path.exists():
        from frankie_box_jev_cpu import sealed_claims
        seal = sealed_claims(path, seal_path)
        if Path(path).read_bytes() != raw:
            raise ValueError('Jev claims changed during seal readback')
    claims = [dict(id=c['id'], statement=c.get('statement'), kind=c.get('kind'), series=list(c.get('series') or []),
                   direction=claimed_direction(c.get('direction')), direction_text=c.get('direction'),
                   lag=claimed_lag(c.get('lag')), cells=list(c.get('cells') or []), day_made=doc.get('day'),
                   source_claim=c)
              for c in doc.get('claims') or []]
    return dict(author='jev', stamp=doc.get('stamp'), day=doc.get('day'), claims_sha256=sha256_bytes(raw),
                source=str(path), claims=claims, blind_seal=seal)


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


BINDING_IDENTITY_SCHEMA = 'FRANKIE_BINDING_IDENTITY_V3'
_ENTRY_PARTS = ('status', 'sources', 'inputs', 'command', 'recorded_outputs', 'calculation')


def _json_stable(value):
    """One canonical, JSON-stable shape (lists, dicts, strings, numbers, None) so an identity computed now equals the
    same identity after a JSON round trip (BIND-F: tuples became lists on reload and falsely differed)."""
    return json.loads(json.dumps(value, sort_keys=True, default=str))


def binding_identity(binding):
    """The COMPLETE semantic identity of a reproduction binding (BIND-F), PER ENTRY: for each entry id its status,
    source pins, input pins (committed with revision/sha256, others by path and status), command (entry point), comparison
    declarations (recorded outputs) and calculation, kept together so a reassignment of a pin between entries differs.
    From the tables' shape (entries) every part is established. A lessons' projection carrying `identity` of THIS schema
    is read as it is, re-validated. An OLDER projection (flat sources, or an earlier identity schema) yields an identity
    that names the parts it cannot establish (per-entry association included) so no consumer infers equality."""
    if not isinstance(binding, dict):
        return None
    embedded = binding.get('identity')
    if isinstance(embedded, dict) and embedded.get('schema') == BINDING_IDENTITY_SCHEMA:
        return _validate_identity(_json_stable(embedded))
    if isinstance(embedded, dict) and embedded.get('schema') == 'FRANKIE_BINDING_IDENTITY_V2':
        # the earlier schema established per-entry commands, declarations and calculations, and FLAT source/input pins
        # (no per-entry association): converted, with exactly those associations named unestablished, never dropped
        v2 = _json_stable(embedded)
        per_entry = {}
        for entry_id in v2.get('entry_ids') or []:
            per_entry[str(entry_id)] = dict(command=(v2.get('commands') or {}).get(str(entry_id)),
                                            recorded_outputs=(v2.get('recorded_outputs') or {}).get(str(entry_id)),
                                            calculation=(v2.get('calculations') or {}).get(str(entry_id)))
        identity = dict(schema=BINDING_IDENTITY_SCHEMA, status=v2.get('status'),
                        entry_ids=sorted(str(x) for x in v2.get('entry_ids') or []), entries=per_entry,
                        flat_sources=sorted(list(x) for x in v2.get('sources') or []),
                        flat_inputs=v2.get('inputs'), converted_from='FRANKIE_BINDING_IDENTITY_V2',
                        unestablished=['per-entry association of sources and inputs (V2 kept them flat)'], complete=False)
        return _validate_identity(_json_stable(identity))
    entries = binding.get('entries')
    if isinstance(entries, list) and all(isinstance(e, dict) for e in entries):
        per_entry = {}
        for e in entries:
            per_entry[str(e.get('id'))] = dict(
                status=e.get('status'),
                sources=sorted([str(x.get('path')), str(x.get('revision')), str(x.get('sha256'))] for x in e.get('sources') or []),
                inputs=sorted([str(i.get('path')), str(i.get('status')), str(i.get('revision')), str(i.get('sha256'))]
                              for i in e.get('inputs') or []),
                command=e.get('entry'), recorded_outputs=e.get('recorded_outputs') or [], calculation=e.get('calculation'))
        identity = dict(schema=BINDING_IDENTITY_SCHEMA, status=binding.get('status'),
                        entry_ids=sorted(str(x) for x in binding.get('entry_ids') or []), entries=per_entry,
                        unestablished=[], complete=True)
        return _validate_identity(_json_stable(identity))
    # an older projection: flat sources with no entry association and no inputs/commands/declarations
    flat = sorted([str(x.get('path')), str(x.get('revision')), str(x.get('sha256'))] for x in binding.get('sources') or [])
    identity = dict(schema=BINDING_IDENTITY_SCHEMA, status=binding.get('status'),
                    entry_ids=sorted(str(x) for x in binding.get('entry_ids') or []),
                    entries=None, flat_sources=flat,
                    unestablished=['entries (per-entry association of sources)', 'inputs', 'command', 'recorded_outputs', 'calculation'],
                    complete=False)
    return _validate_identity(_json_stable(identity))


def _validate_identity(identity):
    """`complete`/`unestablished` are never trusted alone: the parts actually present decide (BIND-F)."""
    missing = []
    entries = identity.get('entries')
    if not isinstance(entries, dict):
        missing.append('entries (per-entry association of sources)')
    elif not entries and list(identity.get('entry_ids') or []):
        missing.append('entries (per-entry association of sources)')
    else:                        # an empty entries dict with no entry ids (an unmapped claim) establishes everything: nothing to bind
        for entry_id, parts in entries.items():
            for part in _ENTRY_PARTS:
                if not isinstance(parts, dict) or part not in parts:
                    missing.append('%s.%s' % (entry_id, part))
        if sorted(entries) != list(identity.get('entry_ids') or []):
            missing.append('entry_ids do not match the entries recorded')
    declared = list(identity.get('unestablished') or [])
    unestablished = sorted(set(declared) | set(missing))
    return dict(identity, unestablished=unestablished, complete=not unestablished)


def binding_identities_differ(retained, current):
    """(differs, unestablished): compares only the parts the RETAINED identity establishes; everything it cannot
    establish is named and never inferred equal. With the per-entry shape, differing means any entry's status, pins,
    command, declarations or calculation differs, or the entry set differs."""
    if retained is None or current is None:
        return True, ['identity']
    retained, current = _json_stable(retained), _json_stable(current)
    unestablished = list(retained.get('unestablished') or [])
    if retained.get('status') != current.get('status') or retained.get('entry_ids') != current.get('entry_ids'):
        return True, unestablished
    if not isinstance(retained.get('entries'), dict):
        # an older flat projection: status, entry ids and the flat source pins are its only established parts; they are
        # compared against the current flat pins and equality of those parts establishes nothing more
        current_flat = sorted(src for parts in (current.get('entries') or {}).values() for src in parts.get('sources') or [])
        if retained.get('flat_sources') is not None and retained['flat_sources'] != current_flat:
            return True, unestablished
        return False, unestablished
    # per entry: every part PRESENT on both sides is compared (a difference there is a real difference, complete or
    # not); a part absent on the retained side stays unestablished; flat pins a converted identity carries are compared
    # against the current flat pins
    current_entries = current.get('entries') or {}
    if retained.get('flat_sources') is not None:
        current_flat = sorted(src for parts in current_entries.values() for src in parts.get('sources') or [])
        if retained['flat_sources'] != current_flat:
            return True, unestablished
    for entry_id, parts in retained['entries'].items():
        other = current_entries.get(entry_id)
        if not isinstance(other, dict) or not isinstance(parts, dict):
            return True, unestablished
        for part in _ENTRY_PARTS:
            if part in parts and part in other and parts[part] != other[part]:
                return True, unestablished
    return False, unestablished


def current_binding(claim, HC):
    """(binding, reform, superseded): the CURRENT declared tables always decide (Greg's step-5 direction, 2026-10-06: a
    known error fixed at its source must not stay active because a record froze it); a binding or reformulation the
    claim carries from an earlier freeze is compared and, when it differs, listed as superseded, never used."""
    binding, reform = HC.reproduction_of(claim['id']), HC.reformulation_of(claim['id'])
    superseded = {}
    retained = claim.get('reproduction')
    if retained is not None:
        differs, unestablished = binding_identities_differ(binding_identity(retained), binding_identity(binding))
        if differs:
            superseded['reproduction'] = dict(status='superseded', retained=binding_identity(retained),
                                              current=binding_identity(binding))
        elif unestablished:
            superseded['reproduction'] = dict(status='equivalence_not_established', unestablished=unestablished,
                                              retained=binding_identity(retained), current=binding_identity(binding),
                                              rule='the retained binding identity is incomplete (an older projection): the '
                                                   'established parts agree, the rest is not inferred; the current binding '
                                                   'is used and nothing read against the retained one is established')
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
        manifest_raw = (d / 'MANIFEST.json').read_bytes()
        manifest = json.loads(manifest_raw)
        parts, part_pins, part_bytes, seen = [], {}, {}, set()
        for pin in manifest['couplings']['parts']:
            relative = Path(pin['path'])
            part = d / relative
            resolved = part.resolve()
            if (relative.is_absolute() or '..' in relative.parts
                    or not resolved.is_relative_to(d.resolve()) or resolved in seen):
                raise ValueError('search evidence part escapes its owner or repeats an existing part')
            seen.add(resolved)
            rel = str(relative)
            if not isinstance(pin.get('sha256'), str) or not re.fullmatch('[0-9a-f]{64}', pin['sha256']):
                raise ValueError('search evidence part lacks its exact sha256: %s' % part)
            parts.append(part)
            part_pins[rel] = pin['sha256']
            if 'bytes' in pin:
                part_bytes[rel] = pin['bytes']
        # Greg 2026-10-06: all 30 days contribute learned knowledge, regardless of the old year/role label.
        # Exact search sources and separate per-day measurements remain bound below.
        sources = manifest.get('sources') or []
        days.append(dict(dir=d, day=manifest['day'], cycle=manifest['cycle'], lags=manifest['lags'],
                         series=manifest['series'], cells=[tuple(c) for c in manifest['cells']],
                         parts=parts, part_pins=part_pins, part_bytes=part_bytes,
                         native_retained=[x for x in manifest.get('notes') or [] if x.get('source') == 'native' and x.get('retained')],
                         native_reports=[x for x in sources if str(x.get('source', '')).startswith('native.')],
                         # the all-99 coverage inputs (frankie_box_all99_coverage): the search's plane receipt (one row per
                         # calculation/clock entry), every source receipt (placed series/cells, exclusions) and the
                         # shared-market read; an older manifest without them is listed by that reader, never refused
                         planes=manifest.get('planes') if isinstance(manifest.get('planes'), dict) else None,
                         sources=[{k: v for k, v in s.items() if k in ('source', 'placed_series', 'placed_cells', 'exclusions',
                                                                        'status', 'missing', 'reason', 'identity', 'coverage',
                                                                        'absent_layers', 'all_fields', 'frame_sections')}
                                  for s in sources if isinstance(s, dict)],
                         shared_market=next((s for s in sources if isinstance(s, dict) and s.get('source') == 'shared_market'), None),
                         manifest_sha256=sha256_bytes(manifest_raw)))
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
    wanted, previous_end = [], -1
    for r in ranges:
        if isinstance(r, (list, tuple)):
            if len(r) != 2:
                raise ValueError('FINALIZE ordinal range must name an inclusive start and end')
            lo, hi = r
        else:
            lo = hi = r
        if type(lo) is not int or type(hi) is not int or not previous_end < lo <= hi:
            raise ValueError('FINALIZE ordinal ranges must be exact, ordered and disjoint')
        wanted.append((lo, hi))
        previous_end = hi
    rows, hashed, size, selection, selected = {}, hashlib.sha256(), 0, 0, 0
    with open(report['path'], 'rb') as handle:
        for ordinal, raw in enumerate(handle):
            hashed.update(raw)
            size += len(raw)
            # Search emits ordered inclusive ranges. Advance through them once;
            # still hash every original row, including rows not selected here.
            while selection < len(wanted) and ordinal > wanted[selection][1]:
                selection += 1
            if selection < len(wanted) and wanted[selection][0] <= ordinal:
                row = json.loads(raw)
                if (row.get('frankie_emission') or {}).get('phase') != 'FINALIZE':
                    raise ValueError('ordinal %d of %s is not a FINALIZE row the search listed post-stream' % (ordinal, report['path']))
                rows.setdefault(str(row.get('emitting_section') or 'member'), []).append(dict(ordinal=ordinal, row=row))
                selected += 1
    if size != report.get('bytes') or hashed.hexdigest() != report.get('sha256'):
        raise ValueError('exact ledger differs from the search\'s pin: %s' % report['path'])
    if selected != sum(hi - lo + 1 for lo, hi in wanted):
        raise ValueError('FINALIZE ordinal selection extends beyond its pinned ledger')
    return rows


def completed_native_evidence(d, out_root):
    """Read and materialize a searched day's selected completed native evidence: the
    files the search pinned and did not search, read whole with their bytes verified, written once per day under
    <out_root>/native/<day>-completed-native.json and referenced in every lessons file for that day (both exchange seats
    read the references, not these source rows). This is not semantic calculation consumption. Exact numbers are
    evidence; an average is a labelled supplement, never evidence (D37); nothing is
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


NEEDLE_LIMIT = 64   # the row filter below: with at most this many distinct claimed series names the needle scan is cheaper
                    # than parsing every row; above it every row is parsed as before (the same rows are selected either way)


def test(claims_doc, days, records_dir=None, records_selection=None, report=None):
    """records_dir / records_selection (B5): the OWNER's reproduction records directory and the selection of its files
    the owner froze with its other inputs (frankie_box_historical_reproduction.record_selection at the freeze); without
    them the module default REPRODUCTION_DIR is read live (the CLI route). With a frozen selection only those files are
    read, bytes-verified, and later arrivals are listed apart, so a restart of the same frozen operation reads the same
    records and a new file never changes a result across claims.
    report (optional dict): filled with what the read did (row_filter, parts_read, rows_hashed, rows_parsed,
    rows_selected) for the operation's receipt; it changes nothing the function computes."""
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
    # Efficiency (Greg, 2026-10-07; performance-optimization: the data shape first): a part carries every ordered pair x
    # cell x transform pair of the day and a claim names two or three series, so nearly every line is a row of other
    # series. Every byte is still hashed (the manifest pin is verified on exactly the bytes consumed); a line that does
    # not contain the JSON encoding of any claimed series name cannot carry a wanted (x, y) and is not parsed. The
    # search writes rows with json.dumps(row, sort_keys=True) (ensure_ascii), the same encoding as the needles, so the
    # selected rows, their ordinals and raw-line hashes are invariant. Above NEEDLE_LIMIT names every row is parsed.
    # both encodings of every name (ASCII-escaped and raw UTF-8) so a writer's ensure_ascii choice can never hide a row
    needles = sorted({json.dumps(name, ensure_ascii=flag).encode('utf-8') for pair in wanted for name in pair
                      for flag in (True, False)})
    needle_filter = 0 < len(needles) <= 2 * NEEDLE_LIMIT
    hashed_rows = parsed_rows = selected_rows = parts_read = 0
    for d in days:
        seen_parts = set()
        for part in d['parts']:
            rel = str(Path(part).relative_to(d['dir']))
            resolved = Path(part).resolve()
            if (not resolved.is_relative_to(Path(d['dir']).resolve()) or resolved in seen_parts
                    or '..' in Path(rel).parts):
                raise ValueError('search evidence part escapes its owner or repeats an existing part')
            seen_parts.add(resolved)
            pin = (d.get('part_pins') or {}).get(rel)
            if not isinstance(pin, str) or not re.fullmatch('[0-9a-f]{64}', pin):
                raise ValueError('search evidence part lacks its exact sha256: %s' % part)
            hashed, size = hashlib.sha256(), 0
            # Verify exactly the bytes consumed, in the same pass as parsing. Text-mode
            # newline normalization must never change the discovery row's raw-line hash.
            parts_read += 1
            with open(part, 'rb') as handle:
                for ordinal, line in enumerate(handle):
                    hashed.update(line)
                    size += len(line)
                    hashed_rows += 1
                    if needle_filter and not any(n in line for n in needles):
                        continue
                    r = json.loads(line)
                    parsed_rows += 1
                    if (r['x'], r['y']) in wanted:
                        # the row's exact identity: its part (the search's pin), its ordinal and the raw line's sha256,
                        # the same three values Run.search_knowledge records for a candidate (part_sha256, row, row_sha256)
                        r['_where'] = dict(part=rel, part_sha256=pin, row=ordinal,
                                           row_sha256=sha256_bytes(line))
                        rows.setdefault((d['day'], r['x'], r['y']), []).append(r)
                        selected_rows += 1
            expected_size = (d.get('part_bytes') or {}).get(rel)
            if hashed.hexdigest() != pin or (expected_size is not None and size != expected_size):
                raise ValueError('search evidence differs from its manifest: %s' % part)
    if report is not None:
        report.update(row_filter='needle' if needle_filter else 'parse_all', needles=len(needles), needle_limit=NEEDLE_LIMIT,
                      parts_read=parts_read, rows_hashed=hashed_rows, rows_parsed=parsed_rows, rows_selected=selected_rows,
                      rule='every byte of every part hashed against the manifest pin; the needle filter skips parsing lines '
                           'that cannot carry a claimed series; selected rows, ordinals and raw-line hashes are invariant')
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
                                          reason=binding.get('reason'), identity=binding_identity(binding),
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


def submit_correction_work(run, day, *, request=None, successor_id=None, decision=None):
    """Scientific-owner intake for explicit researched work; never infer a decision from counts.

    Request and decision use the existing successor contracts. The decision names the actual
    completed research receipt and scoped evidence; the dispatcher rechecks them before filing.
    Calling this boundary queues work only. The held owner loop alone can run or publish it.
    """
    import frankie_box_successor_dispatch as S
    if request is not None:
        if decision is not None or successor_id is not None:
            raise ValueError('scientific request and completed decision are separate owner operations')
        return S.enqueue(run, day, request)
    if decision is None or successor_id is None:
        raise ValueError('completed scientific decision needs its retained successor identity')
    return S.submit_decision(run, day, successor_id, decision)


def publish_standalone_correction(brain, *, original, replacement, original_inputs, replacement_inputs,
                                  affected_claim_ids, scopes, decision, reason, evidence, publication_day):
    """Publish an explicitly researched standalone correction using both actual operations.

    A retained candidate is produced with --retain-only in its own --out-dir. It does not
    become ordinary learner knowledge before this checked, scoped owner decision is supplied.
    """
    import frankie_box_experiment_review as R
    return R.record_correction(brain, original=original, replacement=replacement, scopes=scopes,
        decision=decision, reason=reason, evidence=evidence, publication_day=publication_day,
        owner_transition=dict(original_inputs=original_inputs, replacement_inputs=replacement_inputs,
                              affected_claim_ids=affected_claim_ids))


def standalone_successor_inputs(day, search, brain, request):
    """Resolve one explicit standalone correction without testing or choosing a scientific decision."""
    import frankie_box_brain as BR
    import frankie_box_experiment_review as R
    required = {'original_inputs', 'original_result', 'reason', 'evidence'}
    if (not required <= set(request) or set(request) - required - {
            'affected_claim_ids', 'replacement_claims', 'replacement_search', 'learner_requests'}
            or not isinstance(request['reason'], str) or not request['reason'].strip()
            or not isinstance(request['evidence'], list) or not request['evidence']):
        raise ValueError('standalone successor needs exact original witnesses, reason and evidence')
    for pin in (request['original_inputs'], request['original_result'], *request['evidence']):
        R._read_pin(pin)
    for target in request.get('learner_requests', []):
        if set(target) != {'request', 'response'}:
            raise ValueError('standalone learner target needs its original session witnesses')
        for pin in target.values():
            R._read_pin(pin)
        if (Path(target['request']['path']).name != 'session-request.json'
                or Path(target['response']['path']).name != 'session-response.json'
                or Path(target['request']['path']).resolve().parent != Path(target['response']['path']).resolve().parent):
            raise ValueError('standalone correction must retain its original native session')
    before = json.loads(R._read_pin(request['original_result']))
    old = json.loads(R._read_pin(request['original_inputs']))
    operation = R._transition_operation(request['original_inputs'], before)
    R._validate_operation(operation, before)
    if operation.get('kind') != 'standalone' or Path(operation['identity']['brain']).resolve() != Path(brain).resolve():
        raise ValueError('standalone correction belongs to another scientific owner')
    selected = json.loads(json.dumps(old['selection']))
    owning = [s for s in selected['searches'] if s['day'] == day]
    if len(owning) != 1:
        raise ValueError('standalone correction day must be one exact search in its frozen operation')
    if request.get('replacement_search') is not None:
        pin = request['replacement_search']
        manifest = json.loads(R._read_pin(pin))
        if manifest.get('day') != day or Path(pin['path']).resolve() != (Path(search) / 'MANIFEST.json').resolve():
            raise ValueError('standalone replacement search must be the completed owner day manifest')
        owning[0].update(dir=str(search), cycle=manifest['cycle'], manifest=pin)
    if Path(owning[0]['dir']).resolve() != Path(search).resolve():
        raise ValueError('standalone correction cannot select another owning search implicitly')
    for source in selected['searches']:
        R._read_pin(source['manifest'])
    R._read_pin(selected['source'])
    for pin in selected['reproduction_records']['files']:
        R._read_pin(pin)
    ids = [c['id'] for c in before['claim_inputs']['claims']]
    affected = request.get('affected_claim_ids', ids)
    if (not isinstance(affected, list) or not affected or len(set(affected)) != len(affected)
            or [i for i in ids if i in affected] != affected):
        raise ValueError('standalone affected claims must be an ordered nonempty original subset')
    if request.get('replacement_claims') is not None:
        pin = request['replacement_claims']
        projection = json.loads(R._read_pin(pin))
        if (projection.get('schema') != 'FRANKIE_SCIENTIFIC_CLAIM_INPUTS_V1'
                or projection.get('author') != before['author'] or not projection.get('claims_sha256')
                or [c['id'] for c in projection['claims']] != ids
                or any(a != b for a, b in zip(before['claim_inputs']['claims'], projection['claims'])
                       if a['id'] not in affected)):
            raise ValueError('standalone replacement must retain all identities and unaffected claims')
        selected['doc'].update(claims=projection['claims'], claims_sha256=projection['claims_sha256'], source=pin['path'])
        selected['source'] = pin
    records = R.corrections([brain])
    legal = {e.get('sha256') for _, manifest, _ in BR.entries_before(brain, 'snapshot')
             for e in manifest.get('entries', []) if e.get('include')}
    legal.update(r['replacement']['sha256'] for r in records.values())
    if request['original_result']['sha256'] not in legal or request['original_result']['sha256'] in records:
        raise ValueError('standalone successor must explicitly select current published learner knowledge')
    return before, old, selected, affected


def teach_standalone_successor(day, search, brain, out_dir, *, request):
    """Recompute only affected claims using the frozen original search scope; retain the rest exactly."""
    import frankie_box_experiment_review as R
    import frankie_box_historical_claims as HC
    import frankie_box_historical_reproduction as HR
    import frankie_box_experiment_search as SEARCH
    from frankie_box_successor_dispatch import lock, once, pin, read
    out = Path(out_dir)
    with lock(out / 'successor.lock'):
        receipt_path = out / 'successor-receipt.json'
        if receipt_path.exists():
            completed = read(pin(receipt_path))
            if (completed.get('schema') != 'FRANKIE_TEACHER_SUCCESSOR_RECEIPT_V1'
                    or completed['successor_request'] != request or completed['publication_day'] != day):
                raise ValueError('standalone successor receipt belongs to another operation')
            for source in [completed['inputs'], *completed['files']]:
                read(source)
            return completed
        before, old, selected, affected = standalone_successor_inputs(day, search, brain, request)
        if selected['reproduction_records']['binding_tables_sha256'] != HC.binding_tables_sha256():
            raise ValueError('standalone correction cannot silently change its frozen reproduction binding')
        identity = dict(old['identity'], brain=str(brain), reader_sha256=pin(__file__)['sha256'],
                        readers={m.__name__: pin(m.__file__) for m in (HC, HR, SEARCH, R)},
                        successor=request, owner_day=day)
        frozen = dict(schema='FRANKIE_STANDALONE_TEACHER_INPUTS_V1', identity=identity,
                      selection=selected, selection_sha256=R._lesson_digest(selected))
        inputs = once(out / 'inputs.json', frozen)
        if Path(request['original_inputs']['path']).resolve() == Path(inputs['path']).resolve():
            raise ValueError('standalone successor cannot overwrite its original operation')
        result_path = out / 'result.json'
        if result_path.exists():
            after = read(pin(result_path))
        else:
            days = load_searches([s['dir'] for s in selected['searches']])
            if any(d['manifest_sha256'] != s['manifest']['sha256'] for d, s in zip(days, selected['searches'])):
                raise ValueError('standalone search changed after its successor selection was frozen')
            measured = dict(selected['doc'], claims=[c for c in selected['doc']['claims'] if c['id'] in affected])
            records = selected['reproduction_records']
            results = test(measured, days, records_dir=Path(records['directory']), records_selection=records['files'])
            if [r['claim_id'] for r in results] != affected:
                raise ValueError('standalone retest changed its affected claim identities')
            by_id = {r['claim_id']: r for r in results}
            claims = dict(before['claim_inputs'], claims=selected['doc']['claims'],
                          claims_sha256=selected['doc']['claims_sha256'], reader_sha256=identity['reader_sha256'])
            searches = [dict(day=s['day'], cycle=s['cycle'], dir=s['dir'], manifest_sha256=s['manifest']['sha256'])
                        for s in selected['searches']]
            # Complete retained successor, preserving original metadata and every unaffected result.
            after = dict(before, claims_source=selected['doc']['source'], claims_sha256=claims['claims_sha256'],
                         claim_inputs=claims, claim_inputs_sha256=R._lesson_digest(claims), searches=searches,
                         results=[by_id.get(r['claim_id'], r) for r in before['results']],
                         scientific_operation=dict(inputs=inputs, selection_sha256=frozen['selection_sha256']))
            after['results_sha256'] = R._lesson_digest(after['results'])
            # the all-99 coverage of the successor's own read: every searched day listed again from the retained
            # (unaffected) and recomputed (affected) rows together; the original's lists stay in the original file
            historical = before.get('reconsideration')
            after['all99_coverage'] = all99_for_operation(
                'scientific_teacher_successor', days, after['results'], out,
                knowledge_inputs=dict(historical=(dict(mapped_claims=historical.get('mapped_claims'),
                                                        not_testable=historical.get('not_testable'),
                                                        catalog_sha256=historical.get('catalog_sha256')) if historical else None),
                                      brain_documents=None, frankie=before['author'] == 'frankie',
                                      jev=before['author'] == 'jev', search_candidates=before['author'] == 'search'),
                outputs=dict(output_knowledge_retrieval_receipts=inputs,
                             output_source_state_manifest_code_model_run_hashes=inputs),
                code_root=os.environ.get('CODE_ROOT'))
            after['knowledge_retest'] = dict(before.get('knowledge_retest') or {}, claim_operations={
                c['id']: (dict(input_sha256=inputs['sha256'], searches=searches) if c['id'] in affected else
                          dict(inputs=request['original_inputs'], result=request['original_result'],
                               searches=R.claim_searches(before, c['id']))) for c in claims['claims']})
            collection = before.get('reconsideration')
            if collection is not None and before['claims_sha256'] != after['claims_sha256']:
                origin = (before.get('knowledge_retest') or {}).get('reconsideration_origin')
                if origin is None:
                    if collection['claims_file_sha256'] != before['claims_sha256']:
                        raise ValueError('original standalone collection lacks its claim binding')
                    origin = dict(claims_sha256=collection['claims_file_sha256'], result=request['original_result'])
                after['knowledge_retest']['reconsideration_origin'] = origin
            if request.get('replacement_search') is not None:
                native = before.get('completed_native_evidence') or {}
                replacement, listed = completed_native_evidence(next(d for d in days if d['day'] == day), out)
                by_day = dict(native.get('by_day') or {})
                previous = by_day.pop(day, None)
                if replacement is not None:
                    by_day[day] = replacement
                after['completed_native_evidence'] = dict(native, by_day=by_day,
                    listed=list(native.get('listed') or []) + listed + ([dict(day=day, retained_original=previous,
                        reason='original native evidence preserved; explicit corrected owner search selected')] if previous else []))
            once(result_path, after)
        transition = dict(schema=R.TRANSITION_SCHEMA, owner='frankie_box_scientific_teacher',
                          original=R._transition_operation(request['original_inputs'], before),
                          replacement=R._transition_operation(inputs, after), affected_claim_ids=affected)
        R._validate_transition(transition, before, after, dict(day=day, stage='lessons'))
        completed = dict(schema='FRANKIE_TEACHER_SUCCESSOR_RECEIPT_V1', status='complete',
                         publication='awaiting_checked_owner_decision', publication_day=day,
                         successor_request=request, inputs=inputs, files=[pin(result_path)],
                         owner_transition=dict(original_inputs=request['original_inputs'], replacement_inputs=inputs,
                                               affected_claim_ids=affected), model_calls=0)
        once(receipt_path, completed)
        return completed


def freeze_operation(doc, days, out_dir, brain_dir):
    """Pin standalone scientific inputs before testing; never infer an old operation later."""
    if doc['author'] == 'jev' and not doc.get('blind_seal'):
        raise ValueError('Jev scientific testing requires the exact consuming-owner blind seal; legacy claims preserved')
    import frankie_box_historical_claims as HC
    import frankie_box_historical_reproduction as HR
    import frankie_box_experiment_review as R
    import frankie_box_experiment_search as SEARCH
    from frankie_box_durable import witness, write_json
    day = '-'.join(sorted(d['day'] for d in days)) if doc['author'] == 'historical' else doc['day']
    name = '%s-%s.json' % (day, doc['stamp'] or 'frankie')
    path = Path(out_dir) / doc['author'] / (name + '.inputs.json')
    if path.with_name(name).exists() and not path.exists():
        raise ValueError('legacy standalone result has no frozen operation; explicit historical rework is required')
    source = dict(path=doc['source'], **witness(doc['source']))
    searches = [dict(day=d['day'], cycle=d['cycle'], dir=str(d['dir']),
                     manifest=dict(path=str(d['dir'] / 'MANIFEST.json'), **witness(d['dir'] / 'MANIFEST.json')))
                for d in days]
    if any(s['manifest']['sha256'] != d['manifest_sha256'] for s, d in zip(searches, days)):
        raise ValueError('standalone search changed before operation freeze')
    identity = dict(day=day, brain=str(brain_dir), reader_sha256=witness(__file__)['sha256'],
                    readers={m.__name__: witness(m.__file__) for m in (HC, HR, SEARCH, R)})
    saved = json.loads(path.read_bytes()) if path.exists() else None
    records = (saved['selection']['reproduction_records'] if saved is not None else
               dict(directory=str(REPRODUCTION_DIR), files=HR.record_selection(REPRODUCTION_DIR),
                    binding_tables_sha256=HC.binding_tables_sha256()))
    if doc['author'] == 'historical':
        # The collection summary and tests must consume the same frozen records.
        # Later records cannot change a resumed historical operation's projection.
        current = historical_claims(doc['source'], records_dir=Path(records['directory']),
                                    records_selection=records['files'])
        if (current['claims_sha256'] != source['sha256'] or current['claims_sha256'] != doc['claims_sha256']
                or current['stamp'] != doc['stamp'] or current['claims'] != doc['claims']):
            raise ValueError('historical claims changed while their operation was being frozen')
        doc = current
    if path.exists():
        if (saved.get('schema') != 'FRANKIE_STANDALONE_TEACHER_INPUTS_V1' or saved['identity'] != identity
                or saved['selection']['doc'] != doc or saved['selection']['source'] != source
                or saved['selection']['searches'] != searches
                or saved['selection_sha256'] != R._lesson_digest(saved['selection'])
                or saved['selection']['reproduction_records']['binding_tables_sha256'] != HC.binding_tables_sha256()):
            raise ValueError('standalone operation changed; an explicit successor directory is required')
    else:
        selection = dict(doc=doc, source=source, searches=searches, reproduction_records=records)
        saved = dict(schema='FRANKIE_STANDALONE_TEACHER_INPUTS_V1', identity=identity,
                     selection=selection, selection_sha256=R._lesson_digest(selection))
        write_json(path, saved)
    for item in saved['selection']['reproduction_records']['files']:
        R._read_pin(item)
    return dict(path=str(path), **witness(path)), saved


def all99_for_operation(stage, days, results, out_root, *, knowledge_inputs, outputs, code_root=None):
    """The all-99 coverage list of every searched day for one operation: the rows the operation's tests read (tests
    and origin-evidence rows alike) against the day's search plane/source receipts; each day's list retained once under
    <out_root>/coverage/ and returned as {day: pin-with-summary}. A day whose manifest carries no plane receipt is still
    listed (every entry absent with that reason); nothing refuses."""
    import frankie_box_all99_coverage as A99
    by_day = {}
    for d in days:
        tests = [t for r in results for t in (r.get('tests') or []) if t.get('day') == d['day']]
        tests += [t for r in results for t in (r.get('origin_evidence') or []) if t.get('day') == d['day']]
        coverage = A99.day_coverage(d['day'], manifest_sha256=d['manifest_sha256'], planes=d.get('planes'),
                                    sources=d.get('sources'), tests=tests, knowledge_inputs=knowledge_inputs,
                                    outputs=outputs, stage=stage, code_root=code_root, shared_market=d.get('shared_market'))
        by_day[d['day']] = A99.retain(coverage, out_root)
    return dict(by_day=by_day, rule=A99.RULE)


def write(doc, days, results, out_dir, map_url=None, log=print, brain_dir='/opt/frankie-box/brain', native=None,
          operation=None, publish=True, all99=None, read_report=None):
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
    if operation is not None:
        import frankie_box_experiment_review as R
        frozen = json.loads(R._read_pin(operation))
        lessons['scientific_operation'] = dict(inputs=operation, selection_sha256=frozen['selection_sha256'])
        lessons['results_sha256'] = R._lesson_digest(results)
        R._validate_operation(R._transition_operation(operation, lessons), lessons)
    if doc.get('reconsideration') is not None:
        lessons['reconsideration'] = doc['reconsideration']
    if all99 is not None:
        # the all-99 coverage of every searched day (frankie_box_all99_coverage): the pin and summary per day; the full
        # per-entry list stays in the coverage file. Carried so every later reader (school, exchange, survivors) can
        # name which entries reached these tests without re-reading the search.
        lessons['all99_coverage'] = all99
    if read_report is not None:
        lessons['evidence_read'] = read_report
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
    from frankie_box_durable import write_bytes
    write_bytes(path, data)
    log('%s lessons: %d claims, %s -> %s' % (doc['author'], len(results),
                                              json.dumps({k: sum(r['disposition'] == k for r in results) for k in DISPOSITIONS}), path))
    if not publish:
        return path
    if doc['author'] == 'jev':
        upload_jev_lessons(path, map_url, log=log)
    if doc['author'] == 'search':
        log('search candidate lessons retained, NOT published: frankie_box_brain.write_lessons_entry admits the authors '
            'frankie/historical/jev only (its edit, and the LESSONS maps of frankie_box_teacher_knowledge.py and '
            'frankie_box_experiment_exchange.py, are named for Codex in CCODE_STEP4_SOURCE_ROUTE_20261006.md) -> %s' % path)
        return path
    publish_lessons(path, brain_dir=brain_dir, log=log)

    return path



def upload_jev_lessons(path, map_url=None, log=print):
    """Deliver retained teacher bytes to their existing Jev object, including interrupted-write recovery.

    Repeating this PUT reuses the exact lesson, never another scientific test. HTTP acceptance
    is transport evidence only; consumer-side seal/readback remains the CPU owner's contract.
    """
    if not map_url:
        return None
    path = Path(path)
    data = path.read_bytes()
    lesson = json.loads(data)
    if (lesson.get('schema') != 'JEV_LESSONS_V1' or lesson.get('author') != 'jev'
            or lesson.get('written_by') != 'scientific_teacher'):
        raise ValueError('only completed Jev scientific-teacher lessons may be uploaded')
    name = '%s-%s.json' % (lesson['day'], lesson['stamp'] or 'frankie')
    if path.name != name:
        raise ValueError('Jev lesson filename differs from its retained day/stamp')
    key = 'put:clm-sidecar/jev-brain/lessons/%s' % name
    with urllib.request.urlopen(map_url, timeout=60) as response:
        entries = json.loads(response.read())
    if key not in entries:
        raise SystemExit('no presigned slot %s in MAP_URL (dispatch with presign=put:frankie-granite42-568968024170-us-east-1/%s)'
                         % (key, key[4:]))
    # Idempotency (api-and-interface-design: intent recorded before the call; three outcomes, success / failure /
    # UNKNOWN): the intent (key, bytes, sha256) is written beside the lesson BEFORE the PUT; the result after it. A
    # retry that finds an intent without a result knows the previous attempt's fate is unknown (a timeout after the
    # bytes left) and PUTs the same bytes to the same key again, which is safe: the key is derived from the lesson's
    # day/stamp, not from the attempt. The same completed result is reused, never a second upload.
    from frankie_box_durable import write_json
    intent_path = path.with_name(path.name + '.upload-intent.json')
    result_path = path.with_name(path.name + '.upload-result.json')
    intent = dict(schema='FRANKIE_JEV_LESSONS_UPLOAD_INTENT_V1', key=key[4:], bytes=len(data), sha256=sha256_bytes(data))
    if result_path.is_file():
        previous = json.loads(result_path.read_bytes())
        if previous.get('intent') == intent and previous.get('outcome') == 'success':
            log('retained Jev lessons already uploaded: %s HTTP %d (reused)' % (key[4:], previous['http_status']))
            return dict(previous, reused=True)
    if intent_path.is_file():
        earlier = json.loads(intent_path.read_bytes())
        if earlier.get('sha256') != intent['sha256'] or earlier.get('key') != intent['key']:
            raise ValueError('Jev lessons upload intent belongs to other bytes or another key: %s' % intent_path)
        log('earlier upload of %s has no recorded result: its fate is unknown; the same bytes are PUT again' % key[4:])
    else:
        write_json(intent_path, dict(intent, at=time.time()))
    request = urllib.request.Request(entries[key]['url'], data=data, method='PUT')
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            status = response.status
    except Exception as error:      # noqa: BLE001 - the outcome is recorded (failure or unknown) and the error re-raised
        # an HTTP status is the server's answer: a failure; a transport error or timeout leaves the fate unknown
        write_json(result_path, dict(intent=intent, outcome='failure' if isinstance(error, urllib.error.HTTPError) else 'unknown',
                                     error=type(error).__name__ + ': ' + str(error), at=time.time(),
                                     rule='unknown = the bytes may have landed; a retry PUTs the same bytes to the same key'))
        raise
    result = dict(intent=intent, outcome='success', key=key[4:], bytes=len(data), sha256=intent['sha256'], http_status=status,
                  at=time.time())
    write_json(result_path, result)
    log('uploaded retained Jev lessons: %s HTTP %d' % (key[4:], status))
    return dict(key=key[4:], bytes=len(data), sha256=intent['sha256'], http_status=status)


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
    p.add_argument('--jev-seal', help='the consuming-owner JEV_CPU_BLIND_SEAL_V1 for those exact claims')
    p.add_argument('--jev-stamp', help='fetch clm-sidecar/<stamp>/jev/claims.json through MAP_URL (presign getprefix) instead')
    p.add_argument('--frankie-ledgers', help='Frankie\'s classroom ledgers.json of one day (only its novel findings are read)')
    p.add_argument('--frankie-day', help='the day of those ledgers (YYYYMMDD)')
    p.add_argument('--historical-claims', help='a HISTORICAL_CLAIMS_V1 file (frankie_box_historical_claims.py)')
    p.add_argument('--search-findings', help='a FRANKIE_SEARCH_FINDINGS_V1 file (knowledge-findings.json of one day\'s '
                                             'search): its candidates tested on the OTHER searches given; the candidates\' '
                                             'own day is listed as origin evidence, never as a test')
    p.add_argument('--brain', default='/opt/frankie-box/brain', help='the owning lane plan\'s knowledge directory')
    p.add_argument('--out-dir', default=str(ROOT), help='immutable standalone operation/result directory')
    p.add_argument('--retain-only', action='store_true', help='retain candidate results for an explicit checked correction')
    p.add_argument('--accumulated-day', help='test completed legal knowledge on this one owning day, without a classroom')
    p.add_argument('--accumulated-out', help='the retained accumulated-input/result directory; paired with --accumulated-day')
    a = p.parse_args()
    if a.jev_seal and not (a.jev_claims or a.jev_stamp):
        p.error('--jev-seal requires the exact Jev claims source')
    if a.accumulated_day or a.accumulated_out:
        if (not a.accumulated_day or not re.fullmatch('[0-9]{8}', a.accumulated_day) or
                not a.accumulated_out or len(a.search) != 1 or
                any((a.jev_claims, a.jev_stamp, a.frankie_ledgers, a.frankie_day, a.historical_claims, a.search_findings))):
            p.error('accumulated mode requires one search, --accumulated-day YYYYMMDD and --accumulated-out only')
        import frankie_box_teacher_knowledge as TK
        from frankie_box_durable import write_json, witness
        out = Path(a.accumulated_out)
        started = time.time()
        result = TK.teach_accumulated(a.accumulated_day, a.search[0], a.brain, out)
        receipt = dict(schema='FRANKIE_ACCUMULATED_LESSONS_V1', day=a.accumulated_day, status='complete',
                       search=witness(Path(a.search[0]) / 'MANIFEST.json'), accumulated_claim_tests=result,
                       model_calls=0)
        receipt.update(_accumulated_report(a, result, out, started))
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
    native = {d['day']: completed_native_evidence(d, Path(a.out_dir)) for d in days}
    for day, (ref, listed) in native.items():
        print('completed native evidence %s: %s' % (day, 'read, %s' % json.dumps(ref['counts'], sort_keys=True) if ref
                                                       else '; '.join(x['reason'] for x in listed)), flush=True)
    candidates, listed = [], []
    if a.search_findings:
        import frankie_box_candidate_claims as CC
        candidates = [CC.candidate_claims(a.search_findings)]
        if all(d['day'] == candidates[0]['day'] for d in days):
            # Day-quantity agnostic (Greg, 2026-10-07): a run of one day has no other completed search yet. The
            # candidates are still taught: their own day is listed as origin evidence, every claim comes back
            # INSUFFICIENT_EVIDENCE with the reason in its untested list, and the next day's search tests them.
            listed.append(dict(what='search_findings', day=candidates[0]['day'],
                               reason='no completed search of another day was given: the candidates\' own day is origin '
                                      'evidence, not a test; the claims are retained with their origin evidence only'))
            print('search candidates of %s: no other searched day yet; origin evidence listed, no test (the day stays)'
                  % candidates[0]['day'], flush=True)
    operations = []
    code_root = os.environ.get('CODE_ROOT')
    for doc in ([jev_claims(a.jev_claims, a.jev_seal)] if a.jev_claims else []) + \
               ([frankie_claims(a.frankie_ledgers, a.frankie_day)] if a.frankie_ledgers else []) + \
               ([historical_claims(a.historical_claims, records_selection=[])] if a.historical_claims else []) + candidates:
        started = time.time()
        operation, frozen = freeze_operation(doc, days, a.out_dir, a.brain)
        doc = frozen['selection']['doc']
        records = frozen['selection']['reproduction_records']
        name = '%s-%s.json' % (frozen['identity']['day'], doc['stamp'] or 'frankie')
        result_path = Path(a.out_dir) / doc['author'] / name
        record = dict(author=doc['author'], day=doc['day'], stamp=doc['stamp'], claims=len(doc['claims']),
                      claims_sha256=doc['claims_sha256'], claims_source=doc['source'], operation=operation,
                      searched_days=[d['day'] for d in days])
        if result_path.exists():
            import frankie_box_experiment_review as R
            from frankie_box_durable import witness
            raw = result_path.read_bytes()
            retained = json.loads(raw)
            R._validate_operation(R._transition_operation(operation, retained), retained)
            publication = 'retained_only'
            if not a.retain_only and doc['author'] != 'search':
                import frankie_box_lane_state as LS
                R.require_current([dict(path=str(result_path), sha256=sha256_bytes(raw), content=retained)],
                                  R.corrections(LS.knowledge_roots(a.brain)))
                if doc['author'] == 'jev':
                    upload_jev_lessons(result_path, os.environ.get('MAP_URL'))
                publish_lessons(result_path, brain_dir=a.brain)
                publication = 'published_exact_bytes_reused'
            record.update(status='reused', lessons=dict(path=str(result_path), **witness(result_path)),
                          publication=publication, all99_coverage=retained.get('all99_coverage'),
                          evidence_read=retained.get('evidence_read'),
                          reason='these claims were already taught on this exact frozen operation; no test repeated',
                          seconds=round(time.time() - started, 3))
            operations.append(record)
            continue
        read_report = {}
        results = test(doc, days, records_dir=Path(records['directory']), records_selection=records['files'], report=read_report)
        historical = doc.get('reconsideration')
        knowledge_inputs = dict(
            historical=(dict(mapped_claims=historical.get('mapped_claims'), not_testable=historical.get('not_testable'),
                             catalog_sha256=historical.get('catalog_sha256')) if historical else None),
            brain_documents=None, frankie=doc['author'] == 'frankie', jev=doc['author'] == 'jev',
            search_candidates=doc['author'] == 'search')
        outputs = dict(output_knowledge_retrieval_receipts=operation,
                       output_source_state_manifest_code_model_run_hashes=operation)
        all99 = all99_for_operation('scientific_teacher', days, results, Path(a.out_dir), knowledge_inputs=knowledge_inputs,
                                    outputs=outputs, code_root=code_root)
        path = write(doc, days, results, a.out_dir, os.environ.get('MAP_URL'), brain_dir=a.brain, native=native,
                     operation=operation, publish=not a.retain_only, all99=all99, read_report=read_report)
        from frankie_box_durable import witness
        lesson_pin = dict(path=str(path), **witness(path))
        # the lessons file is the candidate-discoveries and negative/inconclusive ledger output of this stage: the
        # retained coverage lists name it under those two registry outputs only now that it exists
        for day_pin in all99['by_day'].values():
            day_pin['outputs_after_write'] = dict(output_candidate_discoveries=lesson_pin,
                                                  output_negative_sparse_inconclusive_ledger=lesson_pin)
        record.update(status='written', lessons=lesson_pin,
                      publication='retained_only' if a.retain_only or doc['author'] == 'search' else 'published',
                      dispositions={k: sum(r['disposition'] == k for r in results) for k in DISPOSITIONS},
                      counts=dict(tests=sum(len(r.get('tests') or []) for r in results),
                                  origin_evidence_rows=sum(len(r.get('origin_evidence') or []) for r in results),
                                  held=sum(r['counts']['held'] for r in results),
                                  shown_otherwise=sum(r['counts']['shown_otherwise'] for r in results),
                                  unresolved=sum(r['counts']['unresolved'] for r in results),
                                  counts_only=sum(r['counts']['counts_only'] for r in results),
                                  untested_notes=sum(len(r.get('untested') or []) for r in results),
                                  cannot_test_yet=sum(len(r.get('cannot_test_yet') or []) for r in results)),
                      all99_coverage=all99, evidence_read=read_report, seconds=round(time.time() - started, 3))
        operations.append(record)
    _write_teacher_receipt(a, days, native, operations, listed, code_root)


def _knowledge_inputs_of(documents):
    """What knowledge an accumulated selection took, for the all-99 list: the brain documents selected and the
    historical collection among them (mapped claims tested, not_testable carried by reference)."""
    historical = None
    for item in documents or []:
        lesson = item.get('lesson') or {}
        if lesson.get('author') == 'historical':
            collection = lesson.get('reconsideration') or {}
            historical = dict(mapped_claims=(historical or {}).get('mapped_claims', 0) + len(item.get('claims') or []),
                              not_testable=collection.get('not_testable'), catalog_sha256=collection.get('catalog_sha256'))
    return dict(historical=historical, brain_documents=len(documents or []),
                frankie=any((i.get('lesson') or {}).get('author') == 'frankie' for i in documents or []),
                jev=any((i.get('lesson') or {}).get('author') == 'jev' for i in documents or []),
                search_candidates=any((i.get('lesson') or {}).get('author') == 'search' for i in documents or []))


def _accumulated_report(a, result, out, started):
    """The accumulated receipt's inspection fields (Greg, 2026-10-07: every piece reports what it received, how it used
    it and what it produced): the all-99 coverage of the owning day from the result files' test rows, and the
    FRANKIE_PIECE_WORKFLOW_REPORT_V1 the one-day reporter projects whole. Reads only this owner's own files."""
    import frankie_box_experiment_review as R
    from frankie_box_durable import witness
    days = load_searches([a.search[0]])
    tests_results = []
    for pin in result.get('files') or []:
        try:
            tests_results.extend(json.loads(R._read_pin(pin)).get('results') or [])
        except (OSError, ValueError) as error:
            # an unreadable result file is an integrity finding of this receipt, never a reason to drop the day
            tests_results.append(dict(tests=[], origin_evidence=[], integrity=str(error), file=pin))
    inputs_pin = result.get('inputs')
    documents = []
    if inputs_pin:
        try:
            documents = json.loads(R._read_pin(inputs_pin)).get('selection', {}).get('documents') or []
        except (OSError, ValueError):
            documents = []
    files = result.get('files') or []
    outputs = dict(output_candidate_discoveries=files[0] if files else None,
                   output_negative_sparse_inconclusive_ledger=files[0] if files else None,
                   output_knowledge_retrieval_receipts=inputs_pin,
                   output_source_state_manifest_code_model_run_hashes=inputs_pin)
    all99 = all99_for_operation('carried_claims', days, tests_results, out, knowledge_inputs=_knowledge_inputs_of(documents),
                                outputs=outputs, code_root=os.environ.get('CODE_ROOT'))
    scope = result.get('scope') or {}
    report = dict(
        schema='FRANKIE_PIECE_WORKFLOW_REPORT_V1', piece='carried',
        inputs=dict(search=dict(path=str(Path(a.search[0]) / 'MANIFEST.json'), **witness(Path(a.search[0]) / 'MANIFEST.json')),
                    operation_inputs=inputs_pin, brain=str(a.brain), documents_selected=len(documents),
                    documents=[dict(source=(d.get('source') or {}).get('path'), sha256=(d.get('source') or {}).get('sha256'),
                                    author=(d.get('lesson') or {}).get('author'), claims=len(d.get('claims') or []),
                                    input_kind=d.get('input_kind')) for d in documents],
                    reproduction_records=(result.get('late_knowledge') or {}).get('reproduction_records')),
        use=dict(scope=scope, reused=result.get('reused'), listed=result.get('listed'),
                 selection_listed=result.get('selection_listed'), school_listed=result.get('school_listed'),
                 late_knowledge=result.get('late_knowledge'),
                 all99_coverage={day: pin['summary'] for day, pin in all99['by_day'].items()},
                 rule='every skipped claim, listed input and late arrival above is the owner\'s own disposition; the all-99 '
                      'list names which registry entries the tests actually read'),
        outputs=dict(files=files, all99_coverage_files={day: {k: v for k, v in pin.items() if k != 'summary'}
                                                        for day, pin in all99['by_day'].items()},
                     publication='published per file unless awaiting a checked owner decision'),
        seconds=round(time.time() - started, 3), model_calls=0)
    return dict(all99_coverage=all99, workflow_report=report)


def _write_teacher_receipt(a, days, native, operations, listed, code_root):
    """The standalone call's receipt (FRANKIE_SCIENTIFIC_TEACHER_RECEIPT_V1): every operation of this call (written or
    reused), its lessons pin, dispositions, the all-99 coverage pins per searched day, what the read did, and the
    FRANKIE_PIECE_WORKFLOW_REPORT_V1 for the one-day reporter. Printed as the last line (the caller records it) and
    retained content-addressed under <out_dir>/receipts/; the same bytes reuse, different bytes under the same address
    cannot occur (the address is the content)."""
    from frankie_box_durable import write_bytes
    report = dict(
        schema='FRANKIE_PIECE_WORKFLOW_REPORT_V1', piece='findings',
        inputs=dict(searches=[dict(day=d['day'], dir=str(d['dir']), manifest_sha256=d['manifest_sha256'],
                                   planes_receipt=d.get('planes') is not None, sources=len(d.get('sources') or []))
                              for d in days],
                    claims=[dict(author=o['author'], day=o['day'], stamp=o['stamp'], claims=o['claims'],
                                 claims_sha256=o['claims_sha256'], source=o['claims_source']) for o in operations],
                    brain=str(a.brain), out_dir=str(a.out_dir), retain_only=bool(a.retain_only),
                    completed_native_evidence={day: (dict(path=ref['path'], sha256=ref['sha256'], bytes=ref['bytes'], counts=ref['counts'])
                                                     if ref else None) for day, (ref, _) in native.items()}),
        use=dict(operations=[dict(author=o['author'], day=o['day'], status=o['status'], publication=o.get('publication'),
                                  reason=o.get('reason'), dispositions=o.get('dispositions'), counts=o.get('counts'),
                                  evidence_read=o.get('evidence_read'), seconds=o.get('seconds'),
                                  all99_coverage={day: pin.get('summary') for day, pin in ((o.get('all99_coverage') or {}).get('by_day') or {}).items()})
                             for o in operations],
                 listed=listed + [item for _, items in native.values() for item in items],
                 rule='an operation reused repeated no test; the all-99 list per searched day names which registry entries '
                      'its tests read; listed items are dispositions, never dropped evidence'),
        outputs=dict(lessons=[dict(author=o['author'], day=o['day'], **o['lessons']) for o in operations],
                     all99_coverage_files=[{k: v for k, v in pin.items() if k != 'summary'}
                                           for o in operations for pin in ((o.get('all99_coverage') or {}).get('by_day') or {}).values()]),
        model_calls=0)
    receipt = dict(schema='FRANKIE_SCIENTIFIC_TEACHER_RECEIPT_V1', status='complete', searched_days=[d['day'] for d in days],
                   operations=operations, listed=listed, workflow_report=report, model_calls=0, code_root=code_root)
    data = (json.dumps(receipt, indent=1, sort_keys=True, default=str) + '\n').encode()
    path = Path(a.out_dir) / 'receipts' / (sha256_bytes(data) + '.json')
    if not path.exists():
        write_bytes(path, data)
    receipt['receipt'] = dict(path=str(path), bytes=len(data), sha256=sha256_bytes(data))
    print(json.dumps(receipt, sort_keys=True, default=str), flush=True)
    return receipt


if __name__ == '__main__':
    main()
