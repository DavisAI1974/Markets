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


SCAN_BLOCK = 16 * 1024 * 1024   # one read: hashed whole, then split at its last newline (the box's read-ahead is 4 MB)


def _segments(path, hashed, start=0, end=None):
    """Yield (segment, first_ordinal, lines) over a file read in SCAN_BLOCK blocks: each segment is a run of whole lines in
    file order (b'\\n' ends a line, exactly as binary-mode line iteration splits; only a final line at EOF may lack it).
    Every byte read is hashed exactly once, in file order, and every byte lands in exactly one segment, so the segment
    lengths sum to the file size and the ordinals are the binary line iterator's own (Greg, 2026-10-07: faster, same
    bytes; the per-line Python loop over lines no claim can use was the scan's cost). start/end (a line-start byte range,
    _part_ranges): only those bytes, ordinals counted from the range's first line; hashed None: not hashed here (the
    part's whole-file hash is its own task, in file order)."""
    ordinal, carry, left = 0, b'', None if end is None else end - start
    with open(path, 'rb', buffering=0) as handle:
        if start:
            handle.seek(start)
        while left is None or left > 0:
            block = handle.read(SCAN_BLOCK if left is None else min(SCAN_BLOCK, left))
            if not block:
                break
            if left is not None:
                left -= len(block)
            if hashed is not None:
                hashed.update(block)
            data = carry + block if carry else block
            cut = data.rfind(b'\n') + 1
            if not cut:
                carry = data
                continue
            segment, carry = data[:cut], data[cut:]
            count = segment.count(b'\n')
            yield segment, ordinal, count
            ordinal += count
    if carry:
        yield carry, ordinal, 1


# A part above SCAN_RANGE_MIN_BYTES is scanned as ordered line-start ranges by several pinned workers (the decoded_spool
# pattern of frankie_box_experiment_search.py: ranges cut at line starts, results joined in file order, the bytes hashed
# whole in file order by their own task and checked against the pin exactly as before). Ordinals are the range's own
# plus the lines of every earlier range, so every row's ordinal, raw-line sha256 and selection are the whole-part scan's.
SCAN_RANGE_MIN_BYTES = 64 << 20
SCAN_RANGE_BYTES = 32 << 20


def _part_ranges(path, size, pieces):
    """Ordered [start, end) byte ranges of the file, each starting at a line start (frankie_box_experiment_search
    _spool_ranges, copied: that module is not imported by the teacher)."""
    cuts = [0]
    with open(path, 'rb') as handle:
        for k in range(1, pieces):
            nominal = size * k // pieces
            if nominal <= cuts[-1]:
                continue
            handle.seek(nominal - 1)
            handle.readline()                      # ends just after the newline at or after byte nominal - 1
            cut = handle.tell()
            if cuts[-1] < cut < size:
                cuts.append(cut)
    cuts.append(size)
    return [(a, b) for a, b in zip(cuts, cuts[1:]) if b > a]


def _hash_part(path):
    """(sha256 hex, bytes) of a whole part in file order, SCAN_BLOCK reads (the range scans' verification)."""
    hashed, size = hashlib.sha256(), 0
    with open(path, 'rb', buffering=0) as handle:
        for block in iter(lambda: handle.read(SCAN_BLOCK), b''):
            hashed.update(block)
            size += len(block)
    return hashed.hexdigest(), size


LAST_PART_PINS = {}     # path -> how a large part's pin was taken by the last _part_tasks (pre_read's note)


def _part_pinned(path, rel, pin, expected, size):
    """One pass (2026-10-09): the basis on which a large search part is taken at its MANIFEST pin without a whole-file
    hash beside its range scans: a FRANKIE_FILE_CLAIM row naming the pin that still holds (_held), else, with no
    holding claim, its size equal to the MANIFEST's bytes and its mtime no later than the MANIFEST's (unchanged since
    the search wrote and pinned it). None: the part is hashed whole as before."""
    held = _held(path, pin, expected if expected is not None else size)
    if held is not None:
        return held
    if _claims_full() or expected is None or size != expected:
        return None
    try:
        manifest = Path(path).parents[len(Path(rel).parts) - 1] / 'MANIFEST.json'
        if os.stat(path).st_mtime_ns <= os.stat(manifest).st_mtime_ns:
            return 'the search MANIFEST pin: size equal and not modified since %s was written' % manifest
    except (OSError, IndexError):
        return None
    return None


def _part_tasks(parts):
    """(tasks, layout) for the shared scan of parts [(path, rel, pin[, MANIFEST bytes])]: a part below
    SCAN_RANGE_MIN_BYTES (or one whose size cannot be read: its own task then raises where the whole scan would) is one
    ('scan', part) task; a larger part is one pin task and its ('range', (path, rel, pin, start, end)) tasks. The pin
    task is ('pinned', (path, pin, size)) when _part_pinned takes the MANIFEST pin (no read: one pass, 2026-10-09),
    else ('hash', path), the whole-file hash as before. layout[i] = the task indexes of part i (one index, or the pin
    index then its range indexes in file order)."""
    tasks, layout = [], []
    LAST_PART_PINS.clear()
    for path, rel, pin, *rest in parts:
        try:
            size = os.stat(path).st_size
        except OSError:
            size = 0
        if size < SCAN_RANGE_MIN_BYTES:
            layout.append([len(tasks)])
            tasks.append(('scan', (path, rel, pin)))
            continue
        ranges = _part_ranges(path, size, size // SCAN_RANGE_BYTES + 1)
        layout.append(list(range(len(tasks), len(tasks) + 1 + len(ranges))))
        basis = _part_pinned(path, rel, pin, rest[0] if rest else None, size)
        LAST_PART_PINS[str(path)] = basis or 'hashed whole (no holding claim; size or mtime not the MANIFEST\'s)'
        tasks.append(('pinned', (path, pin, size)) if basis is not None else ('hash', path))
        tasks += [('range', (path, rel, pin, a, b)) for a, b in ranges]
    return tasks, layout


def _merge_part(indexes, values):
    """One part's per-document tuples from its task values: the whole-part scan's own, or the hash then the ranges joined
    in file order (sizes and line counts summed, each range's ordinals moved past the lines of the ranges before it)."""
    if len(indexes) == 1:
        return values[indexes[0]]
    digest, _ = values[indexes[0]]
    merged, size, lines = None, 0, 0
    for index in indexes[1:]:
        per_doc = values[index]
        if merged is None:
            merged = [[0, []] for _ in per_doc]
        for k, (_, part_size, part_lines, parsed, selected) in enumerate(per_doc):
            merged[k][0] += parsed
            for r in selected:
                r['_where']['row'] += lines
                merged[k][1].append(r)
        size += per_doc[0][1] if per_doc else 0
        lines += per_doc[0][2] if per_doc else 0
    return [(digest, size, lines, parsed, selected) for parsed, selected in merged or []]


def _line_at(segment, start):
    """(the raw line starting at offset `start` of a segment, newline included when present; the next line's offset)."""
    end = segment.find(b'\n', start)
    end = len(segment) if end < 0 else end + 1
    return segment[start:end], end


def _lane_pin():
    """The shared pin helper (frankie_box_lane_pin: lane_cpus, core_order, placement, ordered_map, record), imported the
    way the box imports its modules, or from the repository package."""
    try:
        import frankie_box_lane_pin as LP
    except ImportError:
        from deploy.aws.box import frankie_box_lane_pin as LP
    return LP


def _lane_order():
    """(the lane's CPUs ordered one hardware thread of every physical core first, then the sibling threads; how):
    frankie_box_lane_pin.core_order over lane_cpus() (FRANKIE_LANE_CPUS / FRANKIE_BOOKED_CPUS within this process's
    affinity; the box: 16 cores, siblings N and N+16). Plain affinity order when the helper cannot be read, named."""
    try:
        LP = _lane_pin()
        order, how = LP.core_order(LP.lane_cpus())
        return list(order), 'lane %s: %s' % (','.join(map(str, sorted(order))), how)
    except Exception as error:  # noqa: BLE001 - the lane order is placement only, never the result
        cpus = sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else [0]
        return cpus, 'lane helper not read (%s: %s): affinity order' % (type(error).__name__, error)


POOL_NOTES = []        # every pool _pinned_map ran in this process, in order: CPU map, mode, worker deaths, redone tasks


def _report_units(label, done, total):
    """The stage heartbeat's units (frankie_box_stage_progress.report_phase: the heartbeat derives units/min and its
    report-only stall flag at 600 s). A no-op outside a Run.child stage; never raises."""
    try:
        import frankie_box_stage_progress as SP
        SP.report_phase(label, units_done=done, units_total=total, unit='items', every=15)
    except Exception:  # noqa: BLE001 - a probe is never the stage's outcome
        pass


def _default_sigterm(job):
    """A pool task: SIGTERM back to its default action in the worker first (a worker forked from a parent that handles
    SIGTERM, e.g. an in-process caller of this module, must still end when the pool is terminated: the a2 shard exit
    hang of 2026-10-07 was an inherited handler swallowing terminate() before an unbounded join), and one BLAS/OpenMP
    thread per worker; then the task itself, unchanged."""
    import signal
    fn, arg = job
    if signal.getsignal(signal.SIGTERM) is not signal.SIG_DFL:
        try:
            signal.signal(signal.SIGTERM, signal.SIG_DFL)
        except (ValueError, OSError):
            pass
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '1'
    return fn(arg)


def _pinned_map(fn, args, label, *, on_item=None, stop=None):
    """[fn(a) for a in args], in order, on the shared pinned fork pool (frankie_box_lane_pin.ordered_map): sized from the
    booked lane (one worker per lane CPU but the coordinator's, never more than the items), each worker pinned to its
    placement CPU (physical cores first, the coordinator's sibling last), at most two tasks per worker in flight, results
    in args order. A dead worker never stops, hangs or is waited on: its lost task is redone with the same arguments at
    the same slot and the window shrinks by one per death (Greg, 2026-10-07: "continue but with just one less worker");
    after the helper's tries the task runs in this process. An exception raised BY fn propagates at its own place in
    order, exactly as in the serial loop. One CPU, one item or a threaded caller (never fork a threaded process): in
    this process, as before. Every pool is noted in POOL_NOTES (the receipt's `pools`: the lane_pin.record CPU map,
    mode, reason, worker deaths and redone tasks, seconds) and its units reach the stage heartbeat; the placement line
    also goes to stderr (the last stdout line stays the step's receipt)."""
    import sys
    import threading
    args = list(args)
    order, how = _lane_order()
    workers = max(1, min(len(args), len(order) - 1))
    note = dict(label=label, items=len(args), lane=how)
    POOL_NOTES.append(note)
    started = time.time()
    if workers <= 1 or threading.active_count() > 1:
        note.update(mode='in_process', reason=('nothing to run' if not args else 'one item' if len(args) == 1 else
                                               'one lane CPU for workers' if len(order) <= 2 else
                                               'a threaded caller: a threaded process is never forked'))
        out = []
        for i, a in enumerate(args):
            if stop is not None and stop():
                note['stopped'] = 'a save was requested: %d of %d items done, the rest left for the resume' % (i, len(args))
                break
            out.append(fn(a))
            if on_item is not None:
                on_item(i, out[-1])
            _report_units(label, i + 1, len(args))
        note['seconds'] = round(time.time() - started, 3)
        return out
    import multiprocessing
    LP = _lane_pin()
    recovery = {}
    try:
        note.update(mode='ordered_map', cpu_map=LP.record(workers, order, what=label))
    except Exception as error:  # noqa: BLE001 - the CPU map is a receipt field, never the work
        note.update(mode='ordered_map', cpu_map=None, cpu_map_error='%s: %s' % (type(error).__name__, error))
    print('%s: %d pinned workers (%s)' % (label, workers, how), file=sys.stderr, flush=True)
    out = []
    try:
        for _, value in LP.ordered_map(_default_sigterm, [(fn, a) for a in args], workers,
                                       context=multiprocessing.get_context('fork'), cpus=order, window=2 * workers,
                                       report=recovery, stop=stop):
            out.append(value)
            if on_item is not None:
                on_item(len(out) - 1, value)
            _report_units(label, len(out), len(args))
    finally:
        note.update(worker_deaths=recovery.get('worker_deaths') or [], redone=recovery.get('redone') or [],
                    completed=len(out), seconds=round(time.time() - started, 3))
        if len(out) < len(args):
            note['stopped'] = 'a save was requested: %d of %d items done, the rest left for the resume' % (len(out), len(args))
        if recovery.get('worker_deaths'):
            print('%s: %d worker death(s), %d task(s) redone with one fewer worker each'
                  % (label, len(recovery['worker_deaths']), len(recovery.get('redone') or [])), file=sys.stderr, flush=True)
    return out


def _scan_part(args):
    """One search coupling part: (sha256 hex of every byte read, bytes, lines hashed, lines parsed, the selected rows in
    line order, each with its exact identity _where). Verify exactly the bytes consumed, in the same pass as parsing;
    text-mode newline normalization never changes a row's raw-line hash. A top-level function (the fork pool's target).
    With the needle filter the part is read in blocks (_segments): every block hashed whole, the needles found by C-level
    search, and only the lines holding one are cut out and parsed, with their ordinal counted from the newlines before
    them; the lines parsed, rows selected, ordinals and raw-line hashes are the line loop's own (a needle is a JSON string
    and never holds a raw newline, so a hit always lies inside one line)."""
    path, rel, pin, wanted, needles, needle_filter = args
    hashed, size, lines, parsed, selected = hashlib.sha256(), 0, 0, 0, []
    if needle_filter:
        for segment, base, count in _segments(path, hashed):
            size += len(segment)
            lines += count
            starts = set()
            for needle in needles:
                position = segment.find(needle)
                while position >= 0:
                    starts.add(segment.rfind(b'\n', 0, position) + 1)
                    end = segment.find(b'\n', position)
                    if end < 0:
                        break
                    position = segment.find(needle, end + 1)
            ordinal, previous = base, 0
            for start in sorted(starts):
                ordinal += segment.count(b'\n', previous, start)
                previous = start
                line, _ = _line_at(segment, start)
                r = json.loads(line)
                parsed += 1
                if (r['x'], r['y']) in wanted:
                    r['_where'] = dict(part=rel, part_sha256=pin, row=ordinal, row_sha256=sha256_bytes(line))
                    selected.append(r)
        return hashed.hexdigest(), size, lines, parsed, selected
    with open(path, 'rb') as handle:
        for ordinal, line in enumerate(handle):
            hashed.update(line)
            size += len(line)
            lines += 1
            if needle_filter and not any(n in line for n in needles):
                continue
            r = json.loads(line)
            parsed += 1
            if (r['x'], r['y']) in wanted:
                # the row's exact identity: its part (the search's pin), its ordinal and the raw line's sha256, the same
                # three values Run.search_knowledge records for a candidate (part_sha256, row, row_sha256)
                r['_where'] = dict(part=rel, part_sha256=pin, row=ordinal, row_sha256=sha256_bytes(line))
                selected.append(r)
    return hashed.hexdigest(), size, lines, parsed, selected


_SHARED_SPECS = ()     # set by shared_scan before its pool forks (inherited, never pickled per part); () otherwise


def _line_starts(segment):
    """Every line start of a segment in order (b'\\n' ends a line, exactly as binary line iteration splits)."""
    starts, position = [], 0
    while position < len(segment):
        starts.append(position)
        end = segment.find(b'\n', position)
        if end < 0:
            break
        position = end + 1
    return starts


def _scan_part_shared(args):
    """One search part read ONCE for every claim document in _SHARED_SPECS: [(digest, bytes, lines hashed, lines parsed,
    selected rows) per document], each tuple exactly _scan_part's own for that document's (wanted, needles, filter). The
    part is hashed once (the cost every per-document scan repeated); each distinct needle is searched once per block and
    its hits shared by every document naming it; a line's ordinal, raw-line sha256 and (x, y) are computed once (one
    json.loads per line however many documents admit it). Each document counts every line its own filter admits as parsed
    and receives its own row object for every line it selects (never one object in two documents' results), so its parsed
    count, selection, ordinals and _where are those of its own scan. A top-level function (the fork pool's target)."""
    path, rel, pin = args[:3]
    start, end = args[3:5] if len(args) == 5 else (0, None)   # a range of a large part (_part_tasks): not hashed here
    specs = _SHARED_SPECS
    hashed, size, lines = (hashlib.sha256() if end is None else None), 0, 0
    out = [[0, []] for _ in specs]
    distinct = sorted({n for _, needles, flag in specs if flag for n in needles})
    parse_all = [i for i, (_, _, flag) in enumerate(specs) if not flag]
    for segment, base, count in _segments(path, hashed, start, end):
        size += len(segment)
        lines += count
        hits = {}
        for needle in distinct:
            starts = set()
            position = segment.find(needle)
            while position >= 0:
                starts.add(segment.rfind(b'\n', 0, position) + 1)
                end = segment.find(b'\n', position)
                if end < 0:
                    break
                position = segment.find(needle, end + 1)
            hits[needle] = starts
        ordinal_of, raw_of = {}, {}
        if parse_all:
            every = _line_starts(segment)
            ordinal_of = {start: base + k for k, start in enumerate(every)}
        else:
            ordinal, previous = base, 0
            for start in sorted(set().union(*hits.values()) if hits else ()):
                ordinal += segment.count(b'\n', previous, start)
                previous = start
                ordinal_of[start] = ordinal
        def line_at(start):
            if start not in raw_of:
                line, _ = _line_at(segment, start)
                raw_of[start] = (line, None)
            return raw_of[start][0]
        def line_sha(start):
            line, digest = raw_of[start]
            if digest is None:
                digest = sha256_bytes(line)
                raw_of[start] = (line, digest)
            return digest
        parsed_of = {}      # line start -> [the parsed row not yet handed to a document, or None; its (x, y)]
        for i, (wanted, needles, flag) in enumerate(specs):
            if flag:
                starts = sorted(set().union(*(hits[n] for n in needles)) if needles else ())
            else:
                starts = every
            for start in starts:
                entry = parsed_of.get(start)
                if entry is None:
                    r = json.loads(line_at(start))
                    entry = parsed_of[start] = [r, (r['x'], r['y'])]
                out[i][0] += 1
                if entry[1] in wanted:
                    r, entry[0] = entry[0], None
                    if r is None:
                        r = json.loads(line_at(start))   # a second document selecting the line gets its own row object
                    r['_where'] = dict(part=rel, part_sha256=pin, row=ordinal_of[start], row_sha256=line_sha(start))
                    out[i][1].append(r)
    digest = hashed.hexdigest() if hashed is not None else None
    return [(digest, size, lines, parsed, selected) for parsed, selected in out]


def _shared_plan(claims_docs, days, minimum=2):
    """(members, plans, jobs) of a shared read of the search parts for these claim documents, or None when fewer than
    `minimum` documents have a read to share (shared_scan: 2; pre_read: 1, so even one document's scan runs side by side
    with the native evidence reads). members = the documents whose read is over the same parts and pins."""
    plans = []
    for doc in claims_docs:
        try:
            _, wanted, needles, needle_filter, jobs = _read_plan(doc, days)
        except Exception:  # noqa: BLE001 - the document's own test() raises it at its own point
            plans.append(None)
            continue
        plans.append((wanted, needles, needle_filter, jobs) if jobs else None)
    if sum(p is not None for p in plans) < minimum:
        return None
    jobs = next(p for p in plans if p is not None)[3]
    members = [i for i, p in enumerate(plans) if p is not None and p[3] == jobs]   # the same parts and pins (same searches)
    if len(members) < minimum:
        return None
    return members, plans, jobs


def _shared_specs(members, plans):
    return tuple((frozenset(plans[i][0]), tuple(plans[i][1]), bool(plans[i][2])) for i in members)


def _shared_prepared(members, plans, jobs, per_part, count):
    """The per-document prepared reads (test(..., scanned=...)) from the per-part shared scan results."""
    prepared = [None] * count
    for k, i in enumerate(members):
        wanted, needles, needle_filter, _ = plans[i]
        prepared[i] = dict(key=_plan_key(wanted, needles, needle_filter, jobs), parts=[part[k] for part in per_part])
    return prepared


def shared_scan(claims_docs, days):
    """Read the search parts ONCE for several claim documents tested on the same searches (Greg, 2026-10-07: the Sept 29
    pattern for the remaining serial walks; every test() call re-read and re-hashed every byte of every part, once per
    document). Returns a list aligned with claims_docs: per document None (test() then scans on its own, exactly as before)
    or its prepared read for test(..., scanned=...), keyed by its read plan so test() uses it only when it is exactly its
    own read. Nothing is skipped: every byte of every part is still hashed and verified against its pin by each test()
    (the digest is computed once and checked per document); each document's rows, ordinals, raw-line hashes and read
    report are those of its own scan.
    Fewer than two documents with a read to share: all None (nothing to share). A plan that cannot be made, or any error
    during the shared read: every entry None, so each test() reads its parts itself and any error is raised by that
    test() at exactly the point it is raised without the shared read (L-2: a lost worker's parts are re-read on one fewer
    worker by _pinned_map, and no document's result depends on the shared read having worked)."""
    global _SHARED_SPECS
    import sys
    plan = _shared_plan(claims_docs, days)
    if plan is None:
        return [None] * len(claims_docs)
    members, plans, jobs = plan
    _SHARED_SPECS = _shared_specs(members, plans)
    tasks, layout = _part_tasks([(path, rel, pin, nbytes) for _, path, rel, pin, nbytes in jobs])
    try:
        out = _pinned_map(_pre_read_task, tasks, 'shared scientific scan of %d search parts (%d tasks) for %d claim '
                                                 'documents' % (len(jobs), len(tasks), len(members)))
    except Exception as error:  # noqa: BLE001 - every document then reads its own parts (its error raised there)
        print('shared scientific scan not used (%s: %s); each document reads its own parts' % (type(error).__name__, error),
              file=sys.stderr, flush=True)
        return [None] * len(claims_docs)
    finally:
        _SHARED_SPECS = ()
    failed = [text for status, text in out if status == 'error']
    if failed:
        print('shared scientific scan not used (%s); each document reads its own parts' % failed[0], file=sys.stderr,
              flush=True)
        return [None] * len(claims_docs)
    values = [value for _, value in out]
    return _shared_prepared(members, plans, jobs, [_merge_part(ix, values) for ix in layout], len(claims_docs))


# ------------------------------------------------------------------------- save / restore (ROOT's contract, session 5)
# Greg, 2026-10-07 night: "every workflow piece needs their restore save code updated to match ROOT's". The route is
# ROOT's (frankie_box_experiment_root.calculate_day): SIGTERM or the lane's FRANKIE_LANE_STOP_FILE only MARKS the save;
# the piece runs on to its next boundary (a pre-read task, or a claim document written), writes its exact state and
# exits 75 (SAVE_EXIT), which the queue records as saved, never failure. Forked workers never inherit the mark-only
# handler (os.register_at_fork resets SIGTERM to its default in every child: the a2 shard hang).
# The exact state is the pre-read checkpoint: an append-only pickle stream (key order kept) under <out>/saves/, one
# header (the identity: every task, the shared specs, the function-level code identity of the code that computes the
# values) then one record per finished task (its value and its file's position), flushed and fsynced at every save
# point: periodically (SAVE_EVERY_SECONDS), on a requested save and at the end. A crash loses at most the tasks after
# the last fsync and a partial final record (dropped on load, listed). A resumed task's file is checked by
# frankie_box_boss_session._resume_row_spool's rule, mirrored (the parts are immutable pinned files, not a RowSpool):
# same size, device, inode and mtime and the same last line (_line_ending_at) -> the saved value, no read; anything else
# (or an old-shape record without the position) -> ONE full pass (the task again: every byte hashed, the pin checked by
# test() / the native assembly exactly as before). Identity is content (frankie_box_experiment_root.content_rebinds):
# the saved header against the one this checkout builds; checkout moves are recorded under <saves>/checkout-rebinds/,
# any other difference refuses (an unfinished save) or sets aside (a completed one: nothing to resume). The header's
# code identity is RECORDED, NEVER COMPARED (Greg, 2026-10-09): only SAVE_SCHEMA, the tasks and the specs compare.
SAVE_SCHEMA = 'FRANKIE_SCIENTIFIC_PRE_READ_SAVE_V1'
SAVE_EXIT = 75
SAVE_EVERY_SECONDS = 60
SAVE_CODE_NAMES = ('sha256_bytes', 'SCAN_BLOCK', '_segments', '_line_at', '_line_starts', '_scan_part_shared',
                   'SCAN_RANGE_MIN_BYTES', 'SCAN_RANGE_BYTES', '_part_ranges', '_hash_part', '_part_tasks', '_part_pinned',
                   '_pre_read_task',
                   '_read_pinned', '_finalize_rows', '_line_start_from_end', 'NATIVE_ROLES', 'NATIVE_LEDGERS', '_LEDGER_ABSENT', '_native_projection',
                   '_native_read', '_native_read_kept', '_native_tasks')
_SAVE = dict(requested=False, installed=False)


class SaveRefused(ValueError):
    """A save this checkout refuses (different code or inputs, or a claim that differs at the seal): visible, never
    read around."""


_LAST_SAVE = []    # the pre-read save of this call, finished by main() once every document is written


class ScientificSaved(SystemExit):
    """A requested save reached its boundary: the exact state is on disk; the process exits SAVE_EXIT (75)."""
    def __init__(self, reason):
        super().__init__(SAVE_EXIT)
        self.reason = reason


def _child_default_sigterm():
    import signal
    try:
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
    except (ValueError, OSError):
        pass


def install_save_route():
    """ROOT's save route in this process: SIGTERM marks the save (never stops mid-task); every forked child gets the
    default SIGTERM back. Idempotent; only the CLI installs it (an importing caller keeps its own handlers)."""
    import signal
    if _SAVE['installed']:
        return
    signal.signal(signal.SIGTERM, lambda *_: _SAVE.__setitem__('requested', True))
    if hasattr(os, 'register_at_fork'):
        os.register_at_fork(after_in_child=_child_default_sigterm)
    _SAVE['installed'] = True


def save_requested():
    """The mark (SIGTERM) or the lane's stop file (FRANKIE_LANE_STOP_FILE, set by Run.child), as ROOT's save_requested."""
    stop_file = os.environ.get('FRANKIE_LANE_STOP_FILE')
    return _SAVE['requested'] or bool(stop_file and Path(stop_file).exists())


def _task_file(task):
    """The one file a pre-read task reads (its position is what a save records)."""
    kind, payload = task
    if kind == 'native':
        role_kind, _, pin = payload
        return pin['retained'] if role_kind == 'file' else pin.get('path')
    if kind == 'hash':
        return payload
    return payload[0]                   # 'scan', 'range' and 'pinned' name their file first


def _task_identity(task):
    kind, payload = task
    return [kind, sha256_bytes(json.dumps(payload, sort_keys=True, default=str).encode())]


def _file_position(path):
    """The saved position of an input file (frankie_box_boss_session._saved_spool_position's `resume` block, minus the
    running hash: these files are read whole, never appended): size, device, inode, mtime and the last line's offset and
    sha256; None when the file cannot be stat'ed or does not end on a whole line (a resume then makes one full pass)."""
    try:
        observed = os.stat(path)
        import frankie_box_boss_session as BS
        tail = BS._line_ending_at(Path(path), observed.st_size)
    except Exception:  # noqa: BLE001 - no position: the resume reads the file again (one full pass)
        return None
    return dict(path=str(path), bytes=observed.st_size, device=observed.st_dev, inode=observed.st_ino,
                mtime_ns=observed.st_mtime_ns, tail_offset=tail['offset'], tail_sha256=tail['sha256'])


def _position_unchanged(position):
    """frankie_box_boss_session._resume_row_spool's rule, mirrored: (True, how) when the file is the one saved."""
    if not position:
        return False, 'one full pass: the save recorded no position (an older save, or no whole last line)'
    now = _file_position(position['path'])
    if now is None:
        return False, 'one full pass: the file cannot be read back now'
    if (now['bytes'], now['device'], now['inode'], now['mtime_ns']) != (
            position['bytes'], position['device'], position['inode'], position['mtime_ns']):
        return False, 'one full pass: the file is not the one saved (size, device, inode or mtime differ)'
    if (now['tail_offset'], now['tail_sha256']) != (position['tail_offset'], position['tail_sha256']):
        return False, 'one full pass: its last line differs from the saved one'
    return True, 'unchanged file: stat and last line checked, no full read'


def _save_identity(tasks):
    """The header a save binds: every task in order, the shared specs, and the function-level code identity of the code
    that computes the saved values (frankie_box_bedrock.code_identity; a comment or an unrelated edit keeps it)."""
    specs = [[sorted([list(p) for p in wanted]), [n.decode('utf-8', 'replace') for n in needles], flag]
             for wanted, needles, flag in _SHARED_SPECS]
    try:
        import frankie_box_bedrock as BED
    except ImportError:
        from deploy.aws.box import frankie_box_bedrock as BED
    try:
        code = BED.code_identity(Path(__file__), SAVE_CODE_NAMES)
    except Exception as error:  # recorded only (Greg, 2026-10-09): never a refusal
        code = dict(unavailable='%s: %s' % (type(error).__name__, error))
    return dict(schema=SAVE_SCHEMA, tasks=[_task_identity(t) for t in tasks], specs=specs, code=code)


SAVE_RECORDED_CODE = ('code', 'code_sha256')


def _compared_save_identity(identity):
    """A save header without its recorded-only code fields (Greg, 2026-10-09: the code is recorded, never compared)."""
    return {k: v for k, v in identity.items() if k not in SAVE_RECORDED_CODE}


class PreReadSave:
    """The pre-read checkpoint (see the section note): load() the saved values that may be reused, add() a finished
    task, flush() at a save point (fsync), finish() at the end. Never changes a value: a reused value is the pickled
    value of the same task on the same unchanged file (the code identity is recorded beside it, never compared)."""

    def __init__(self, directory, tasks):
        self.directory = Path(directory)
        self.identity = _save_identity(tasks)
        self.key = sha256_bytes(json.dumps(self.identity['tasks'] + [self.identity['specs']], sort_keys=True).encode())[:24]
        self.path = self.directory / ('%s.pkl' % self.key)
        self.note = dict(path=str(self.path), reused=0, full_pass=[], saved=0, flushes=0, dropped_tail=None,
                         rebinds=None, old_shape=False)
        self.handle, self.last_flush = None, time.time()
        self.positions = {}

    def seal(self, every, reuse):
        """The seal check (ROOT's _check_spool_claims): every reused value's file is checked again by the same rule at the
        end of the pre-read; FRANKIE_SCIENTIFIC_SEAL_FULL=1 also re-runs each reused task (a full witness read) and
        compares its value with the saved claim. Any difference refuses, visibly."""
        full = os.environ.get('FRANKIE_SCIENTIFIC_SEAL_FULL') == '1'
        for index in sorted(reuse):
            same, how = _position_unchanged(self.positions.get(index))
            if not same:
                raise SaveRefused('the saved pre-read claim for task %d differs at the seal (%s); retained for recovery'
                                 % (index, how))
            if full and _pre_read_task(every[index]) != reuse[index]:
                raise SaveRefused('the saved pre-read claim for task %d differs from its full read at the seal; retained '
                                 'for recovery' % index)
        self.note['seal'] = dict(checked=len(reuse), full_read=full,
                                 rule='every reused task\'s file re-checked (stat + last line); a full read with '
                                      'FRANKIE_SCIENTIFIC_SEAL_FULL=1')

    def load(self):
        """{task index: value} that may be reused (each file checked as _resume_row_spool does); notes every full pass."""
        import pickle
        if not self.path.is_file():
            return {}
        header, records, complete = None, [], False
        with open(self.path, 'rb') as handle:
            while True:
                at = handle.tell()
                try:
                    item = pickle.load(handle)
                except EOFError:
                    break
                except Exception as error:  # noqa: BLE001 - a partial final record of a crash: dropped, listed
                    self.note['dropped_tail'] = dict(at=at, reason='%s: %s' % (type(error).__name__, error))
                    break
                if header is None:
                    header = item
                elif item.get('complete'):
                    complete = True
                else:
                    records.append(item)
        if complete:
            # one pass (Greg, 2026-10-09): a completed save of the same tasks is a receipt of reads already done; its
            # values are reused on every file still unchanged (the same stat + last-line rule as a resume), never read
            # again. A completed save of other code or inputs is set aside below.
            self.note['completed_save_reused'] = True
        saved_identity = (header or {}).get('identity')
        if saved_identity is not None and (not isinstance(saved_identity, dict) or 'tasks' not in saved_identity):
            # a save with no task list: nothing in it can be matched to a task; one full pass
            self.note['old_shape'] = True
            saved_identity = None
        if saved_identity is None:
            self._set_aside('the save has no identity this code can check (an older shape): one full pass of every task')
            return {}
        # Greg, 2026-10-09 (standing): the code version is recorded, never compared. The save's code identity and this
        # checkout's are recorded in the note; only SAVE_SCHEMA (the pickle format), the tasks and the specs compare.
        self.note['code_recorded'] = dict(saved=saved_identity.get('code'), current=self.identity.get('code'),
                                          differs=saved_identity.get('code') != self.identity.get('code'),
                                          rule='recorded, never compared (Greg, 2026-10-09)')
        import frankie_box_experiment_root as XR
        moves = XR.content_rebinds(_compared_save_identity(saved_identity), _compared_save_identity(self.identity))
        if moves is None:
            if complete:
                self._set_aside('a completed save of different inputs: nothing to resume, set aside')
                return {}
            raise SaveRefused('the saved scientific pre-read %s differs from what this checkout builds (its inputs: '
                             'tasks, specs or save format; code is never compared); retained for recovery: move it '
                             'aside to start the pre-read again' % self.path)
        if moves:
            from frankie_box_durable import write_json
            write_json(self.directory / 'checkout-rebinds' / ('%s-%d.json' % (self.key, time.time_ns())),
                       dict(schema='FRANKIE_ROOT_CHECKOUT_REBIND_V1', save=str(self.path), moves=moves))
            self.note['rebinds'] = len(moves)
        reuse = {}
        for record in records:
            index = record.get('index')
            same, how = _position_unchanged(record.get('position'))
            if same:
                reuse[index] = record['value']
                self.positions[index] = record['position']
            else:
                self.note['full_pass'].append(dict(index=index, file=(record.get('position') or {}).get('path'), how=how))
        self.note['reused'] = len(reuse)
        self._records = records
        return reuse

    def _set_aside(self, reason):
        target = self.path.with_name(self.path.name + '.set-aside-%d' % time.time_ns())
        os.replace(self.path, target)
        self.note.setdefault('set_aside', []).append(dict(path=str(target), reason=reason))

    def _open(self):
        import pickle
        if self.handle is None:
            self.directory.mkdir(parents=True, exist_ok=True)
            existing = self.path.is_file()
            self.handle = open(self.path, 'ab')
            if not existing:
                pickle.dump(dict(identity=self.identity), self.handle, protocol=pickle.HIGHEST_PROTOCOL)
            elif self.note.get('dropped_tail'):
                # never append after a partial record: rewrite the readable records, then continue
                self.handle.close()
                records = getattr(self, '_records', [])
                pending = self.path.with_name(self.path.name + '.pending')
                with open(pending, 'wb') as out:
                    pickle.dump(dict(identity=self.identity), out, protocol=pickle.HIGHEST_PROTOCOL)
                    for record in records:
                        pickle.dump(record, out, protocol=pickle.HIGHEST_PROTOCOL)
                    out.flush()
                    os.fsync(out.fileno())
                os.replace(pending, self.path)
                self.handle = open(self.path, 'ab')

    def add(self, index, task, value):
        import pickle
        self._open()
        pickle.dump(dict(index=index, position=_file_position(_task_file(task)), value=value), self.handle,
                    protocol=pickle.HIGHEST_PROTOCOL)
        self.note['saved'] += 1
        if save_requested() or time.time() - self.last_flush >= SAVE_EVERY_SECONDS:
            self.flush()

    def flush(self):
        if self.handle is not None:
            self.handle.flush()
            os.fsync(self.handle.fileno())
            self.note['flushes'] += 1
        self.last_flush = time.time()

    def finish(self):
        import pickle
        self._open()
        pickle.dump(dict(complete=True, at=time.time()), self.handle, protocol=pickle.HIGHEST_PROTOCOL)
        self.flush()
        self.handle.close()
        self.handle = None


def _pre_read_task(task):
    """One item of pre_read's single pool: ('native', a completed-native read) -> _native_read_kept's ('ok'|'error', v);
    ('scan', a part) -> ('ok', _scan_part_shared's tuples) or ('error', text) (the documents then scan on their own)."""
    kind, payload = task
    if kind == 'native':
        return _native_read_kept(payload)
    if kind == 'pinned':
        return 'ok', (payload[1], payload[2])      # the MANIFEST pin taken by _part_pinned: nothing read
    try:
        return 'ok', (_hash_part(payload) if kind == 'hash' else _scan_part_shared(payload))
    except Exception as error:  # noqa: BLE001 - each document then reads its own parts and raises there
        return 'error', '%s: %s' % (type(error).__name__, error)


def pre_read(days, claims_docs, out_root, save_dir=None):
    """Every searched day's completed native evidence AND the search-part scan of every claim document to be tested, on
    ONE pinned lane pool side by side (Greg, 2026-10-07: sub-steps of a piece run side by side where independent; the
    native reads of every day and the claim scan read different files and never depend on each other). Returns
    (native, prepared, note): native = completed_native_evidence_many(days, out_root)'s own [(reference, listed)] (each
    day assembled and written in this process in the serial order, a read that raised re-run here at its own place);
    prepared = shared_scan's per-document entries, one document already enough (its scan is the shared scan of one
    spec, whose rows, ordinals, raw-line hashes and counts are _scan_part's own); note = what the read did, for the
    receipt. Any scan error: prepared all None (each test() scans itself and raises at its own point). The combined pool
    failing in any other way: the native reads run as completed_native_evidence_many and prepared is all None."""
    global _SHARED_SPECS
    import sys
    started = time.time()
    tasks, plans = _native_tasks(days, out_root)
    plan = _shared_plan(claims_docs, days, minimum=1)
    parts = [] if plan is None else [(path, rel, pin, nbytes) for _, path, rel, pin, nbytes in plan[2]]
    part_tasks, layout = _part_tasks(parts)
    note = dict(native_reads=len(tasks), scan_parts=len(parts), scan_tasks=len(part_tasks),
                native_kept=[p[0]['day'] for p in plans if p[4] is not None], part_pins=dict(LAST_PART_PINS),
                ranged_parts=sum(1 for ix in layout if len(ix) > 1), documents=len(claims_docs),
                scan_documents=0 if plan is None else len(plan[0]), side_by_side=bool(tasks and parts))
    if plan is not None:
        _SHARED_SPECS = _shared_specs(plan[0], plan[1])
    every = [('native', t) for t in tasks] + part_tasks
    save = reuse = None
    try:
        if save_dir is not None and every:
            # the exact save of this pre-read (see the save section): finished tasks reused on an unchanged file
            save = PreReadSave(save_dir, every)
            reuse = save.load()
        reuse = reuse or {}
        run = [i for i in range(len(every)) if i not in reuse]
        _report_units('scientific pre-read: %d of %d tasks resumed from the save' % (len(reuse), len(every)),
                      len(reuse), len(every))
        values = dict(reuse)

        def finished(k, value):
            values[run[k]] = value
            if save is not None and value[0] == 'ok':
                save.add(run[k], every[run[k]], value)
        _pinned_map(_pre_read_task, [every[i] for i in run],
                    'scientific pre-read: %d native evidence reads of %d days and %d search parts for %d claim '
                    'documents, side by side (%d resumed)' % (len(tasks), len(days), len(parts), note['scan_documents'],
                                                              len(reuse)),
                    on_item=finished, stop=save_requested if save is not None else None)
        if save is not None:
            note['save'] = save.note
            if len(values) < len(every):
                save.flush()
                save.handle and save.handle.close()
                raise ScientificSaved('a save was requested: %d of %d pre-read tasks saved at %s'
                                      % (len(values), len(every), save.path))
            save.seal(every, reuse)
            save.flush()
            _LAST_SAVE.append(save)     # finished (complete) by main() after the last document is written
        out = [values[i] for i in range(len(every))]
    except ScientificSaved:
        raise
    except Exception as error:  # noqa: BLE001 - the serial route below reads everything itself
        if isinstance(error, SaveRefused):
            raise                                   # a save this checkout refuses is visible, never read around
        print('scientific pre-read not used (%s: %s); native evidence and parts read on their own'
              % (type(error).__name__, error), file=sys.stderr, flush=True)
        note.update(used=False, reason='%s: %s' % (type(error).__name__, error), seconds=round(time.time() - started, 3))
        return completed_native_evidence_many(days, out_root), [None] * len(claims_docs), note
    finally:
        _SHARED_SPECS = ()
    reads, scans = out[:len(tasks)], out[len(tasks):]
    native = [_native_document(d, retained, reports, tasks, reads, index, out_root, kept=kept)
              for d, retained, reports, index, kept in plans]
    failed = [text for status, text in scans if status == 'error']
    if plan is None or failed:
        prepared = [None] * len(claims_docs)
        if failed:
            note['scan_listed'] = 'a part scan raised (%s): every document reads its own parts' % failed[0]
    else:
        values = [value for _, value in scans]
        prepared = _shared_prepared(plan[0], plan[1], plan[2], [_merge_part(ix, values) for ix in layout],
                                    len(claims_docs))
    note.update(used=True, prepared=sum(p is not None for p in prepared), seconds=round(time.time() - started, 3))
    return native, prepared, note


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
# ---- one pass over the data (Greg, 2026-10-09): what an earlier step read whole and receipted is taken from its claim
# (FRANKIE_FILE_CLAIM_V1/V2: a sealed file's bytes and sha256 with its inode, size, mtime_ns, filesystem and the sha256
# of its last 64 KiB; ingest_block_sources.claim_still_holds, one 64 KiB read), never hashed again here. The claim rows
# are found by the file's identity (inode, size, mtime_ns), so a data-export hardlink of a ROOT file takes the ROOT's
# row: in every ancestor directory's file-claims.jsonl and work/file-claims.jsonl, and in the claim files an ancestor
# export MANIFEST.json lists (hashing.claims.files). A file with no holding claim is read whole as before.
# FRANKIE_ROOT_LEGACY_REUSE_CHECK=full (or FRANKIE_ROOT_NATIVE_REUSE_CHECK=full) restores every whole read.
_CLAIM_ROWS = {}        # claims file -> {(inode, size, mtime_ns): row}, read once per process
_MANIFEST_CLAIM_FILES = {}


def _claims_full():
    return 'full' in (os.environ.get('FRANKIE_ROOT_LEGACY_REUSE_CHECK'), os.environ.get('FRANKIE_ROOT_NATIVE_REUSE_CHECK'))


def _claim_rows(candidate):
    key = str(candidate)
    if key not in _CLAIM_ROWS:
        rows = {}
        try:
            from research.kalshi.frankie_boss.operations.ingest_block_sources import claim_identity
            for line in Path(candidate).read_bytes().splitlines():
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                identity = claim_identity(row)
                if identity is not None:
                    rows[identity] = row
        except (ImportError, OSError):
            rows = {}
        _CLAIM_ROWS[key] = rows
    return _CLAIM_ROWS[key]


def _claim_files_near(path):
    out = []
    for parent in Path(path).parents:
        for candidate in (parent / 'file-claims.jsonl', parent / 'work' / 'file-claims.jsonl'):
            if candidate.is_file():
                out.append(candidate)
        manifest = parent / 'MANIFEST.json'
        if manifest.is_file():
            key = str(manifest)
            if key not in _MANIFEST_CLAIM_FILES:
                try:
                    listed = ((json.loads(manifest.read_bytes()).get('hashing') or {}).get('claims') or {}).get('files') or []
                    _MANIFEST_CLAIM_FILES[key] = [Path(f['path']) for f in listed if isinstance(f, dict) and f.get('path')]
                except (OSError, ValueError, AttributeError, TypeError):
                    _MANIFEST_CLAIM_FILES[key] = []
            out += [c for c in _MANIFEST_CLAIM_FILES[key] if c.is_file()]
    return out


def _held(path, sha256, nbytes=None):
    """The basis text when a saved claim row naming these bytes and this sha256 still holds for the file at `path`;
    else None (the caller reads it whole). Never raises."""
    if _claims_full():
        return None
    try:
        observed = os.stat(path)
        if nbytes is not None and observed.st_size != nbytes:
            return None
        from research.kalshi.frankie_boss.operations.ingest_block_sources import claim_still_holds
        identity = (observed.st_ino, observed.st_size, observed.st_mtime_ns)
        for candidate in _claim_files_near(path):
            row = _claim_rows(candidate).get(identity)
            if row is None or row.get('sha256') != sha256 or row.get('bytes') != observed.st_size:
                continue
            held = claim_still_holds(row, path)
            if held is not None:
                return 'by claim (%s): %s' % (candidate, held['text'])
    except Exception:  # noqa: BLE001 - a claim is a hint: without one the file is read whole
        return None
    return None


def _read_pinned(path, sha256, nbytes):
    data = Path(path).read_bytes()
    if len(data) != nbytes or (sha256_bytes(data) != sha256 and _held(path, sha256, nbytes) is None):
        raise ValueError('retained native evidence differs from the search\'s pin: %s' % path)
    return json.loads(gzip.decompress(data) if str(path).endswith('.gz') else data)


def _line_start_from_end(path, size, lines_back):
    """The byte offset where the last `lines_back` lines of the file begin (b'\\n' ends a line; a final line without
    one counts as a line), read backwards in SCAN_BLOCK blocks: only the tail is read."""
    if lines_back <= 0:
        return size
    with open(path, 'rb', buffering=0) as handle:
        handle.seek(size - 1)
        ends_with_newline = handle.read(1) == b'\n'
        need = lines_back + (1 if ends_with_newline else 0)     # newlines from the end, the one before the first line
        position, seen = size, 0
        while position > 0:
            low = max(0, position - SCAN_BLOCK)
            handle.seek(low)
            block = handle.read(position - low)
            count = block.count(b'\n')
            if seen + count >= need:
                at = len(block)
                for _ in range(need - seen):
                    at = block.rfind(b'\n', 0, at)
                return low + at + 1
            seen += count
            position = low
    return 0


def _finalize_rows(report):
    """Every FINALIZE (post-stream) row of an exact ledger, whole, by emitting section. Only the ordinals the search listed
    post_stream_knowledge_only are parsed. One pass (2026-10-09): when the ledger's claim holds (its bytes and sha256
    are the search's pin) and the search recorded its row count, the FINALIZE rows are read by seeking: the tail from
    the first listed ordinal to the end (the post-stream rows end the ledger) is read and nothing before it; the line
    count from that offset to the end must equal the rows the search counted. Without a holding claim the ledger is
    hashed while it streams from byte 0 and must equal the search's pin, as before."""
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
    total = report.get('rows')
    claimed = (_held(report['path'], report.get('sha256'), report.get('bytes'))
               if type(total) is int and total >= 0 and (not wanted or wanted[-1][1] < total) else None)
    Path(report['path']).stat()                    # an absent ledger raises FileNotFoundError here, as the read did
    rows, hashed, size, selection, selected = {}, None, 0, 0, 0
    if claimed is not None:
        first = wanted[0][0] if wanted else total
        start = _line_start_from_end(report['path'], report['bytes'], total - first)
        base_ordinal = first
    else:
        hashed, start, base_ordinal = hashlib.sha256(), 0, 0
    counted = 0
    # Read in blocks (_segments; Greg, 2026-10-07: faster, same bytes); a block with no listed ordinal is only counted
    # (C-level newline count); inside a block holding listed ordinals the lines are walked to them and exactly those raw
    # lines parsed, in order, with the line iterator's ordinals. Each ordered inclusive range is advanced through once.
    for segment, base, count in (_segments(report['path'], hashed, start) if start < report.get('bytes', 0) or hashed
                                 is not None else ()):
        base += base_ordinal
        size += len(segment)
        counted += count
        stop = base + count                       # this segment's lines are ordinals base .. stop - 1
        while selection < len(wanted) and wanted[selection][1] < base:
            selection += 1
        ordinal, offset = base, 0
        while selection < len(wanted) and wanted[selection][0] < stop:
            lo, hi = wanted[selection]
            while ordinal < lo:                   # lo < stop: every line stepped over ends with its newline
                offset = segment.find(b'\n', offset) + 1
                ordinal += 1
            while ordinal <= hi and ordinal < stop:
                raw, offset = _line_at(segment, offset)
                row = json.loads(raw)
                if (row.get('frankie_emission') or {}).get('phase') != 'FINALIZE':
                    raise ValueError('ordinal %d of %s is not a FINALIZE row the search listed post-stream' % (ordinal, report['path']))
                rows.setdefault(str(row.get('emitting_section') or 'member'), []).append(dict(ordinal=ordinal, row=row))
                selected += 1
                ordinal += 1
            if hi >= stop:
                break                             # the range continues in the next segment
            selection += 1
    if hashed is not None:
        if size != report.get('bytes') or hashed.hexdigest() != report.get('sha256'):
            raise ValueError('exact ledger differs from the search\'s pin: %s' % report['path'])
    elif size != report['bytes'] - start or counted != total - base_ordinal:
        raise ValueError('exact ledger tail differs from the search\'s row count: %s' % report['path'])
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
    return completed_native_evidence_many([d], out_root)[0]


NATIVE_ROLES = ('receipt', 'result', 'bedrock_section_4_2', 'bedrock_section_4_4')
NATIVE_LEDGERS = ('native.member', 'native.lifecycle')
_LEDGER_ABSENT = ('__ledger_absent__',)


def _native_projection(role, value):
    """The doc fragment of one retained native file (completed_native_evidence's own projections, unchanged); None when
    the file's JSON is null (the fragment is then absent, as before)."""
    if value is None:
        return None
    if role == 'receipt':
        return {k: value.get(k) for k in ('verdict', 'failed_gates', 'groups', 'records', 'span_seconds',
                                          'candidate_warmup_seconds', 'candidate_min_observations')}
    if role == 'result':
        layers = value.get('layers') or {}
        summaries = (layers.get('exact_lifecycle_and_runway_ledger') or {}).get('section_summaries')
        averages = layers.get('averaged_companions') or {}
        return dict(layers=sorted(layers), section_summaries=summaries,
                    section_summaries_rule='the traversal\'s own section numbers, whole; evidence where exact',
                    averaged_companions=dict(rows=averages.get('rows'), key_alias_form=averages.get('key_alias_form'),
                                             rule='averages: a supplement only, never evidence (D37)'))
    if role == 'bedrock_section_4_2':
        return dict(first_last_pairs=value.get('first_last_pairs'), declarations=value.get('declarations'),
                    status=value.get('status'), reason=value.get('reason'), count=value.get('count'),
                    companion_rows=dict(rows=value.get('companion_rows'), rule='averages: supplement only (D37)'),
                    rule='the exact first and last book of each day-segment-phase: evidence; the books '
                         'themselves are already on the frame axis, so these are read, not re-searched')
    rows = value.get('lifecycle_rows') or []
    live = [r for r in rows if (r.get('frankie_emission') or {}).get('phase') == 'GROUP_CLOSE']
    ended = [r for r in rows if (r.get('frankie_emission') or {}).get('phase') != 'GROUP_CLOSE']
    return dict(matching_rule=value.get('matching_rule'), status=value.get('status'), reason=value.get('reason'),
                group_close_rows=len(live), stream_end_rows=ended,
                rule='GROUP_CLOSE offers are searched as native.lifecycle.mirror.* (not duplicated '
                     'here); STREAM_END rows are post-stream knowledge, read whole')


def _native_read(task):
    """One read of completed_native_evidence: ('file', role, retained pin) -> the role's fragment (bytes verified against
    the pin, then projected); ('ledger', name, report) -> the ledger's FINALIZE rows by section, or _LEDGER_ABSENT when
    the exact ledger is not at its path (FileNotFoundError, listed by the caller as before)."""
    kind, role, payload = task
    if kind == 'ledger':
        try:
            return _finalize_rows(payload)
        except FileNotFoundError:
            return _LEDGER_ABSENT
    return _native_projection(role, _read_pinned(payload['retained'], payload['sha256'], payload['bytes']))


def _native_read_kept(task):
    """_native_read in a pool worker: ('ok', value), or ('error', text) when it raised. The caller re-runs an errored read
    in its own process at that read's place in the original order, so the exception (its type and message, unpickled
    never) is raised exactly where the serial code raised it, after everything before it was assembled."""
    try:
        return 'ok', _native_read(task)
    except Exception as error:  # noqa: BLE001 - re-raised by the caller's in-process re-run
        return 'error', '%s: %s' % (type(error).__name__, error)


def completed_native_evidence_many(days, out_root):
    """completed_native_evidence for every searched day, [(reference, listed)] in the days' order. Every file read of
    every day (the four retained files and the two exact ledgers, each hashed against its pin) is an independent read: all
    of them run side by side on pinned lane workers (physical cores first; Greg, 2026-10-07: the Sept 29 pattern; a
    one-day run read its six files one after another, the two whole-ledger hashes in series). Each day's document is then
    assembled in this process in exactly the serial order (receipt, result, 4.2, 4.4, member, lifecycle), with the same
    listed entries in the same order and the same bytes written; a read that raised in a worker is re-run here at its own
    place, so the first error in that order is raised as before. A broken pool re-reads everything here, in order (L-2)."""
    tasks, plans = _native_tasks(days, out_root)
    reads = _pinned_map(_native_read_kept, tasks, 'completed native evidence: %d reads of %d searched days'
                        % (len(tasks), len(days))) if tasks else []
    out = []
    for d, retained, reports, index, kept in plans:
        out.append(_native_document(d, retained, reports, tasks, reads, index, out_root, kept=kept))
    return out


def _native_tasks(days, out_root=None):
    """(tasks, plans) of completed_native_evidence_many: every file read of every day in the serial order, and per day
    (d, retained, reports, index of its first read, kept). kept (one pass, 2026-10-09): the day's own earlier
    <out_root>/native/<day>-completed-native.json when it is the receipt of these very inputs (_native_kept): that day
    gets no read at all and its reference is the kept document's."""
    tasks, plans = [], []
    for d in days:
        retained = {x['role']: x for x in d.get('native_retained') or []}
        reports = {x['source']: x for x in d.get('native_reports') or []}
        index = len(tasks)
        kept = _native_kept(d, retained, reports, out_root) if (retained and out_root is not None) else None
        if retained and kept is None:
            tasks += [('file', role, retained[role]) for role in NATIVE_ROLES if role in retained]
            tasks += [('ledger', name, reports[name]) for name in NATIVE_LEDGERS if name in reports]
        plans.append((d, retained, reports, index, kept))
    return tasks, plans


NATIVE_DOC_SCHEMA = 'FRANKIE_COMPLETED_NATIVE_EVIDENCE_V1'


def _unchanged_since(path, pin, written_ns):
    """The basis when the pinned file is the one the kept document was made from: its claim holds, or (no holding
    claim) its size is the pin's and it was last modified no later than the kept document was written."""
    held = _held(path, pin['sha256'], pin['bytes'])
    if held is not None:
        return held
    if _claims_full():
        return None
    try:
        observed = os.stat(path)
    except OSError:
        return None
    if observed.st_size == pin['bytes'] and observed.st_mtime_ns <= written_ns:
        return 'size equal to the pin and not modified since the completed-native document was written'
    return None


def _native_kept(d, retained, reports, out_root):
    """(reference, listed) from the day's existing <out_root>/native/<day>-completed-native.json when it was made from
    exactly these inputs: same schema and day, the same search manifest sha256 (which pins the ledger reports), the same
    read_from pins, and every file it read unchanged since (_unchanged_since: its claim, else size + mtime). Else None
    (the reads run). The kept document is the receipt of the earlier reads: nothing it was made from is read again."""
    path = Path(out_root) / 'native' / ('%s-completed-native.json' % d['day'])
    try:
        written = path.stat().st_mtime_ns
        data = path.read_bytes()
        doc = json.loads(data)
    except (OSError, ValueError):
        return None
    read_from = {k: dict(path=v['retained'], sha256=v['sha256'], bytes=v['bytes']) for k, v in retained.items()}
    if (not isinstance(doc, dict) or doc.get('schema') != NATIVE_DOC_SCHEMA or doc.get('day') != d['day']
            or doc.get('search_manifest_sha256') != d['manifest_sha256'] or doc.get('read_from') != read_from):
        return None
    pins = list(read_from.values()) + [reports[name] for name in NATIVE_LEDGERS
                                       if name in ((doc.get('finalize_rows') or {}).get('rows') or {}) and name in reports]
    for pin in pins:
        if _unchanged_since(pin['path'], pin, written) is None:
            return None
    return _native_reference(d, doc, data, path, doc.get('listed') or [])


def _native_reference(d, doc, data, path, listed):
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


def _native_document(d, retained, reports, tasks, reads, index, out_root, kept=None):
    """Assemble and write one day's FRANKIE_COMPLETED_NATIVE_EVIDENCE_V1 from its reads (completed_native_evidence's
    document, listed entries and reference, unchanged); a kept document (_native_kept) is returned as it stands."""
    if kept is not None:
        return kept
    listed = []
    if not retained:
        return None, [dict(day=d['day'], reason='the search carries no retained native evidence (none selected for this day)')]
    doc = dict(schema=NATIVE_DOC_SCHEMA, day=d['day'], search_manifest_sha256=d['manifest_sha256'],
               read_from={k: dict(path=v['retained'], sha256=v['sha256'], bytes=v['bytes']) for k, v in retained.items()},
               rule='exact numbers are evidence, read whole and bound by sha256; averages are labelled supplements (D37); '
                    'post-stream rows have no axis position and are never search steps; nothing is computed here')
    def take():
        nonlocal index
        status, value = reads[index]
        task = tasks[index]
        index += 1
        return _native_read(task) if status == 'error' else value
    for role, key in zip(NATIVE_ROLES, ('receipt', 'result', 'section_4_2', 'section_4_4')):
        if role not in retained:
            listed.append(dict(day=d['day'], role=role, reason='not among the search\'s retained native files'))
            continue
        fragment = take()
        if fragment is not None:
            doc[key] = fragment
    finalize = {}
    for name in NATIVE_LEDGERS:
        report = reports.get(name)
        if report is None:
            listed.append(dict(day=d['day'], role=name, reason='no search report of this ledger'))
            continue
        rows = take()
        if rows == _LEDGER_ABSENT:
            listed.append(dict(day=d['day'], role=name, reason='the exact ledger is not at %s' % report.get('path')))
        else:
            finalize[name] = rows
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
    return _native_reference(d, doc, data, path, listed)


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


def _read_plan(claims_doc, days):
    """(per_claim, wanted, needles, needle_filter, jobs): what test() reads for these claims on these searches. A pure
    function of the claims and the searches' manifests (no file of a part is opened), so shared_scan can prepare the read
    of several claim documents before any of them is tested and test() can prove a prepared read is its own."""
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
    jobs = []
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
            jobs.append((d['day'], str(part), rel, pin, (d.get('part_bytes') or {}).get(rel)))
    return per_claim, wanted, needles, needle_filter, jobs


def _plan_key(wanted, needles, needle_filter, jobs):
    """The identity of one read: the (x, y) pairs it selects, its needles and filter mode, and every part it reads with
    the part's pin. Two reads with equal keys select exactly the same rows from exactly the same verified bytes."""
    return (frozenset(wanted), tuple(needles), bool(needle_filter), tuple((p, rel, pin) for _, p, rel, pin, _ in jobs))


def test(claims_doc, days, records_dir=None, records_selection=None, report=None, scanned=None):
    """records_dir / records_selection (B5): the OWNER's reproduction records directory and the selection of its files
    the owner froze with its other inputs (frankie_box_historical_reproduction.record_selection at the freeze); without
    them the module default REPRODUCTION_DIR is read live (the CLI route). With a frozen selection only those files are
    read, bytes-verified, and later arrivals are listed apart, so a restart of the same frozen operation reads the same
    records and a new file never changes a result across claims.
    report (optional dict): filled with what the read did (row_filter, parts_read, rows_hashed, rows_parsed,
    rows_selected) for the operation's receipt; it changes nothing the function computes.
    scanned (optional): this document's entry of shared_scan(...), the per-part read already done for several claim
    documents in one pass over the same parts. Used only when its key equals this call's own read plan (the same pairs,
    needles, filter mode, parts and pins), so the rows, ordinals, raw-line hashes, counts and every verification below are
    exactly those of the call's own scan; None, or a read made for another plan, and the parts are scanned here as before."""
    per_claim, wanted, needles, needle_filter, jobs = _read_plan(claims_doc, days)
    rows = {}
    hashed_rows = parsed_rows = selected_rows = parts_read = 0
    # Efficiency (Greg, 2026-10-07; performance-optimization): the parts are independent files, each hashed and filtered
    # on its own; they are scanned by the step's lane workers (a fork pool over the CPUs this child was given, the day's
    # held lane) and merged in the original order (day, part, line), so the selected rows, their ordinals, raw-line hashes
    # and every verification are exactly the one-process result. One part or one CPU: in this process.
    # Each pool process is pinned to one lane CPU, physical cores first (_pinned_map; Greg, 2026-10-07); a threaded caller
    # still scans in-process (never fork a threaded process), and a broken pool rescans in-process, in order.
    if isinstance(scanned, dict) and scanned.get('key') == _plan_key(wanted, needles, needle_filter, jobs):
        scanned = scanned['parts']
    else:
        scan_args = [(path, rel, pin, frozenset(wanted), needles, needle_filter) for _, path, rel, pin, _ in jobs]
        scanned = _pinned_map(_scan_part, scan_args, 'scientific scan of %d search parts' % len(scan_args))
    for (day_of, path, rel, pin, expected_size), (digest, size, hashed, parsed, selected) in zip(jobs, scanned):
        parts_read += 1
        hashed_rows += hashed
        parsed_rows += parsed
        if digest != pin or (expected_size is not None and size != expected_size):
            raise ValueError('search evidence differs from its manifest: %s' % path)
        for r in selected:
            rows.setdefault((day_of, r['x'], r['y']), []).append(r)
            selected_rows += 1
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
        # the reader pins are recorded, never compared (Greg, 2026-10-09): a retained inputs.json frozen under other
        # reader bytes is kept and is the operation's binding from here on (its identity is the one carried below)
        inputs = once(out / 'inputs.json', frozen)
        frozen = read(inputs)
        identity = frozen['identity']
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
    # Greg, 2026-10-09 (standing): the reader pins (reader_sha256, readers) are RECORDED, NEVER COMPARED: a frozen
    # operation written under other code bytes is the same operation when its data (day, brain, doc, source, searches,
    # selection, binding tables) is the same; the retained file is kept as written (its pins are its record).
    recorded = ('reader_sha256', 'readers')
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
        if (saved.get('schema') != 'FRANKIE_STANDALONE_TEACHER_INPUTS_V1'
                or {k: v for k, v in saved['identity'].items() if k not in recorded}
                != {k: v for k, v in identity.items() if k not in recorded}
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
        raise ValueError('SEARCH_CANDIDATE_LESSONS_V1 is not published by this standalone publisher: the search author\'s '
                         'completed owner-local candidate checks are published by frankie_box_teacher_knowledge through '
                         'frankie_box_brain.write_lessons_entry (which admits author search with knowledge_retest); the '
                         'result file is retained here, not published (%s)' % path)
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


def teacher_second_set_reads(day_names, brain, out_dir, *, single=None):
    """The scientific teacher's own reading of the BOSS teacher's WHOLE second set for each day it works on (Greg,
    2026-10-09: BOTH teachers get the second set): the day's teacher rows are found through its <day>-teacher brain
    entry (summary.rows: learner-legal knowledge at this stage), and frankie_box_teacher_rows.second_set_reading streams
    every sidecar row (key, clocks, the plane references to the ROOT's stream rows, the book columns, the per-row state
    split) and reads the day's state split, the account and the full lists whole, written to
    <out_dir>/teacher-second-set/<day>.json (single: that one file instead; the same files reuse it). Read beside the
    claim tests, never changing a lesson's bytes or a test; {day: reference}; an absent part or day is listed, never
    fatal."""
    import frankie_box_teacher_rows as TR
    out = {}
    for day in day_names:
        try:
            rows, looked = None, []
            try:
                import frankie_box_lane_state as LS
                roots = [Path(r) for r in LS.knowledge_roots(brain)]
            except Exception:  # noqa: BLE001 - the owning brain alone
                roots = [Path(brain)]
            for root in roots:
                entry = root / ('%s-teacher' % day) / 'stage-knowledge.json'
                looked.append(str(entry))
                if entry.is_file():
                    rows = (json.loads(entry.read_bytes()).get('summary') or {}).get('rows')
                    if rows:
                        break
            if not rows:
                out[day] = dict(status='absent', reason='no <day>-teacher brain entry names the teacher rows of this day',
                                looked=looked)
                print('teacher second set %s (scientific teacher): absent (no teacher entry names its rows)' % day,
                      flush=True)
                continue
            target = Path(single) if single else Path(out_dir) / 'teacher-second-set' / ('%s.json' % day)
            record, pin, how = TR.second_set_reading_file(Path(rows).parent, target, 'scientific_teacher')
            out[day] = TR.reading_reference(record, pin, how)
            print('teacher second set %s (scientific teacher): %s; %s' % (day, how, TR.reading_sentence(record)),
                  flush=True)
        except Exception as error:  # noqa: BLE001 - added knowledge: listed, never the call's failure
            out[day] = dict(status='failed', reason='%s: %s' % (type(error).__name__, error))
    return out


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
        second_set = teacher_second_set_reads([a.accumulated_day], a.brain, out,
                                              single=out / 'teacher-second-set-read.json')
        result = TK.teach_accumulated(a.accumulated_day, a.search[0], a.brain, out)
        receipt = dict(schema='FRANKIE_ACCUMULATED_LESSONS_V1', day=a.accumulated_day, status='complete',
                       search=witness(Path(a.search[0]) / 'MANIFEST.json'), accumulated_claim_tests=result,
                       model_calls=0)
        receipt.update(_accumulated_report(a, result, out, started))
        # added field (Day-1 visibility): every pinned pool this call ran (CPU map, mode or in-process reason, worker
        # deaths, tasks redone, seconds); the result files and their bytes are untouched
        receipt['pools'] = list(POOL_NOTES)
        receipt['workflow_report'].setdefault('use', {})['pools'] = list(POOL_NOTES)
        # added field (2026-10-09): what this teacher read of the BOSS teacher's second set (whole; listed when absent)
        receipt['teacher_second_set_read'] = second_set
        write_json(out / 'receipt.json', receipt)
        print(json.dumps(receipt, sort_keys=True), flush=True)
        return
    # ROOT's save route for this call (the accumulated mode above has no save point of this module: its own result
    # files are its resume point, and SIGTERM keeps its default meaning there)
    install_save_route()
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
    second_set = teacher_second_set_reads([d['day'] for d in days], a.brain, a.out_dir)
    # The claim documents are read first (pure reads: nothing is written before the native evidence, as before), so the
    # native evidence of every day and the search-part scan of every document to be tested run side by side on ONE pinned
    # lane pool (pre_read; Greg, 2026-10-07: sub-steps side by side, every part read and hashed once per stage). The
    # printed lines, the native files written and any error keep the serial order: native evidence first (a native read
    # that raised re-raises at its own place), then the candidates' line, then a claims-document error at its own place.
    candidates, listed, candidate_lines, docs, docs_error = [], [], [], None, None
    try:
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
                candidate_lines.append('search candidates of %s: no other searched day yet; origin evidence listed, no test '
                                       '(the day stays)' % candidates[0]['day'])
        docs = ([jev_claims(a.jev_claims, a.jev_seal)] if a.jev_claims else []) + \
               ([frankie_claims(a.frankie_ledgers, a.frankie_day)] if a.frankie_ledgers else []) + \
               ([historical_claims(a.historical_claims, records_selection=[])] if a.historical_claims else []) + candidates
    except (Exception, SystemExit) as error:  # noqa: BLE001 - re-raised below, after the native evidence, as before
        docs_error = error
    shared_started = time.time()
    # One read of the search parts for every document this call will test (Greg, 2026-10-07, the Sept 29 pattern): a
    # document whose result file already exists is reused below and reads nothing, so it is left out (the document
    # boundary is this stage's save point: a restart reuses every document already written and tests the rest). The
    # claims read are the given documents' own; freeze_operation refuses any frozen document whose claims differ, and
    # test() uses a prepared read only when it is exactly its own plan. The loop below is unchanged: each document is
    # still frozen, tested, written and published in this order (brain publication order kept), and any document
    # without a prepared read scans its parts itself.
    to_test = [] if docs_error is not None else [
        index for index, doc in enumerate(docs)
        if not (Path(a.out_dir) / doc['author'] / ('%s-%s.json' % (
            '-'.join(sorted(d['day'] for d in days)) if doc['author'] == 'historical' else doc['day'],
            doc['stamp'] or 'frankie'))).exists()]
    try:
        native_list, prepared_list, pre_note = pre_read(days, [docs[index] for index in to_test], Path(a.out_dir),
                                                        save_dir=Path(a.out_dir) / 'saves')
    except ScientificSaved as saved:
        _print_saved(a, days, 'pre_read', saved.reason, documents_left=len(to_test))
        raise
    native = dict(zip([d['day'] for d in days], native_list))
    for day, (ref, native_listed) in native.items():
        print('completed native evidence %s: %s' % (day, 'read, %s' % json.dumps(ref['counts'], sort_keys=True) if ref
                                                       else '; '.join(x['reason'] for x in native_listed)), flush=True)
    for line in candidate_lines:
        print(line, flush=True)
    if docs_error is not None:
        raise docs_error
    operations = []
    code_root = os.environ.get('CODE_ROOT')
    prepared = dict(zip(to_test, prepared_list))
    shared = dict(documents=len(to_test), prepared=sum(v is not None for v in prepared.values()),
                  parts=sum(len(d['parts']) for d in days), seconds=round(time.time() - shared_started, 3),
                  pre_read=pre_note, documents_resumed=len(docs) - len(to_test),
                  rule='the search parts read once for every document tested here (each part hashed once, each needle '
                       'searched once per block), side by side with every day\'s native evidence reads; every '
                       'document\'s rows, ordinals, raw-line hashes, pin checks and read report are its own scan\'s; '
                       'prepared 0 = each document read its own parts; documents_resumed = result files already written '
                       '(reused below, nothing re-tested)')
    for index, doc in enumerate(docs):
        if index and save_requested():
            # ROOT's route: the save is marked; this boundary (every earlier document written and published) is the
            # exact state: the next call reuses those result files and tests the rest. Exit 75, never a failure.
            _print_saved(a, days, 'document_boundary', 'a save was requested: %d of %d claim documents done'
                         % (index, len(docs)), documents_left=len(docs) - index, operations=operations)
            raise ScientificSaved('document boundary %d of %d' % (index, len(docs)))
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
        results = test(doc, days, records_dir=Path(records['directory']), records_selection=records['files'], report=read_report,
                       scanned=prepared.pop(index, None))
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
    for save in _LAST_SAVE:
        save.finish()                 # every document written: the save is complete (a later call sets it aside)
    _write_teacher_receipt(a, days, native, operations, listed, code_root, shared_read=shared, second_set=second_set)


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


def _print_saved(a, days, boundary, reason, documents_left=None, operations=None):
    """The last stdout line of a saved call (FRANKIE_SCIENTIFIC_TEACHER_RECEIPT_V1, status 'saved'): where it stopped,
    why, what is left and every pool so far; the caller reads exit 75 as saved, never as a failure."""
    print(json.dumps(dict(schema='FRANKIE_SCIENTIFIC_TEACHER_RECEIPT_V1', status='saved', exit_code=SAVE_EXIT,
                          boundary=boundary, reason=reason, documents_left=documents_left,
                          searched_days=[d['day'] for d in days], out_dir=str(a.out_dir),
                          operations=operations or [], pools=list(POOL_NOTES), model_calls=0,
                          resume='the same call again: written result files are reused, saved pre-read tasks on '
                                 'unchanged files are reused, the rest runs'), sort_keys=True, default=str), flush=True)


def _write_teacher_receipt(a, days, native, operations, listed, code_root, shared_read=None, second_set=None):
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
                 shared_read=shared_read, pools=list(POOL_NOTES),
                 rule='an operation reused repeated no test; the all-99 list per searched day names which registry entries '
                      'its tests read; listed items are dispositions, never dropped evidence'),
        outputs=dict(lessons=[dict(author=o['author'], day=o['day'], **o['lessons']) for o in operations],
                     all99_coverage_files=[{k: v for k, v in pin.items() if k != 'summary'}
                                           for o in operations for pin in ((o.get('all99_coverage') or {}).get('by_day') or {}).values()]),
        model_calls=0)
    receipt = dict(schema='FRANKIE_SCIENTIFIC_TEACHER_RECEIPT_V1', status='complete', searched_days=[d['day'] for d in days],
                   operations=operations, listed=listed, workflow_report=report, model_calls=0, code_root=code_root)
    if shared_read is not None:
        receipt['shared_read'] = shared_read      # added field (how the parts were read); absent on a caller without it
    receipt['pools'] = list(POOL_NOTES)           # added field: every pinned pool of this call (CPU map, deaths, redo)
    if second_set is not None:
        # added field (2026-10-09): per searched day, what this teacher read of the BOSS teacher's whole second set
        receipt['teacher_second_set_read'] = second_set
        report['inputs']['teacher_second_set'] = {day: (ref.get('reading') if isinstance(ref, dict) else None)
                                                  for day, ref in second_set.items()}
    data = (json.dumps(receipt, indent=1, sort_keys=True, default=str) + '\n').encode()
    path = Path(a.out_dir) / 'receipts' / (sha256_bytes(data) + '.json')
    if not path.exists():
        write_bytes(path, data)
    receipt['receipt'] = dict(path=str(path), bytes=len(data), sha256=sha256_bytes(data))
    print(json.dumps(receipt, sort_keys=True, default=str), flush=True)
    return receipt


if __name__ == '__main__':
    main()
