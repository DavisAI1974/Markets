"""Replay completed native scientific claims on one owning lane's existing search.

Only legal lesson claim projections cross this boundary. Prior findings remain intact;
new results name their own search evidence and never count a reused search twice.
"""
import hashlib
import json
from pathlib import Path


LESSONS = {'FRANKIE_LESSONS_V1': 'frankie', 'JEV_LESSONS_V1': 'jev',
           'HISTORICAL_LESSONS_V1': 'historical', 'SEARCH_CANDIDATE_LESSONS_V1': 'search'}


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def teach_successor(day, search, brain, out_dir, *, request):
    """Explicit owner retest of one original result; never a correction decision or publication.

    Request carries original_inputs/original_result path/bytes/sha256 witnesses, reason and
    evidence witnesses. Optional affected_claim_ids selects the claims to recompute;
    replacement_claims and replacement_search pin corrected projections and search manifests.
    Unaffected claims/results keep their original bytes and scientific provenance.
    Its complete result still needs record_correction with a checked decision and exact scopes.
    """
    import fcntl
    directory = Path(out_dir)
    lock_path = directory / 'successor.lock'
    if any(p.is_symlink() for p in (lock_path, *lock_path.parents)):
        raise ValueError('successor owner directory traverses a symbolic link')
    directory.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return teach_accumulated(day, search, brain, directory, _successor=request)


def publish_successor(brain, *, receipt, scopes, decision, reason, evidence):
    """Publish only the owner's explicit checked decision about a retained successor result.

    The decision, scopes and evidence are never inferred from a newer result or its disposition.
    record_correction keeps the unchanged-knowledge guard and owns durable publication/reuse.
    """
    import frankie_box_experiment_review as REVIEW
    completed = json.loads(REVIEW._read_pin(receipt))
    if (completed.get('schema') != 'FRANKIE_TEACHER_SUCCESSOR_RECEIPT_V1'
            or completed.get('publication') != 'awaiting_checked_owner_decision'
            or len(completed.get('files') or []) != 1):
        raise ValueError('successor publication requires one retained complete owner result')
    request, transition = completed['successor_request'], completed['owner_transition']
    if (transition['original_inputs'] != request['original_inputs']
            or transition['replacement_inputs'] != completed['inputs']):
        raise ValueError('successor receipt differs from its operation witnesses')
    frozen = json.loads(REVIEW._read_pin(completed['inputs']))
    if frozen['identity'].get('successor') != request:
        raise ValueError('successor receipt differs from the frozen owner request')
    return REVIEW.record_correction(brain, original=request['original_result'], replacement=completed['files'][0],
                                    scopes=scopes, decision=decision, reason=reason, evidence=evidence,
                                    publication_day=frozen['identity']['day'], owner_transition=transition)


def _successor_document(request, identity, input_path, REVIEW, BR):
    """Resolve explicit witnesses before any scientific work; preserve the original operation."""
    if (not isinstance(request, dict)
            or not {'original_inputs', 'original_result', 'reason', 'evidence'} <= set(request)
            or set(request) - {'original_inputs', 'original_result', 'reason', 'evidence',
                               'affected_claim_ids', 'replacement_claims', 'replacement_search', 'learner_requests'}
            or not isinstance(request['reason'], str) or not request['reason'].strip()
            or not isinstance(request['evidence'], list) or not request['evidence']):
        raise ValueError('successor requires exact original witnesses, reason and evidence')
    for pin in (request['original_inputs'], request['original_result'], *request['evidence']):
        REVIEW._read_pin(pin)
    for target in request.get('learner_requests', []):
        if set(target) != {'request', 'response'}:
            raise ValueError('learner correction target requires original request and response witnesses')
        for pin in target.values():
            REVIEW._read_pin(pin)
        if (Path(target['request']['path']).name != 'session-request.json'
                or Path(target['response']['path']).name != 'session-response.json'
                or Path(target['request']['path']).resolve().parent != Path(target['response']['path']).resolve().parent):
            raise ValueError('learner correction must preserve one exact original native session')
    original = json.loads(REVIEW._read_pin(request['original_result']))
    if (original.get('schema') not in LESSONS or LESSONS[original['schema']] != original.get('author')
            or original.get('written_by') != 'scientific_teacher'):
        raise ValueError('successor needs an original completed scientific lesson')
    operation = REVIEW._transition_operation(request['original_inputs'], original)
    REVIEW._validate_operation(operation, original)
    old = operation['identity']
    search_pin = request.get('replacement_search')
    if search_pin is not None:
        corrected_search = json.loads(REVIEW._read_pin(search_pin))
        if (str(corrected_search.get('day')) != identity['day']
                or Path(search_pin['path']).resolve() != (Path(identity['search']) / 'MANIFEST.json').resolve()
                or {k: search_pin[k] for k in ('bytes', 'sha256')} != identity['manifest']):
            raise ValueError('replacement search must pin the exact corrected owner manifest')
    if (old['day'] != identity['day'] or old['brain'] != identity['brain']
            or (search_pin is None and (old['search'] != identity['search'] or old['manifest'] != identity['manifest']))
            or Path(request['original_inputs']['path']).resolve().parent == input_path.resolve().parent):
        raise ValueError('successor needs a distinct operation on the same owner and an explicit search transition')
    records = REVIEW.corrections([Path(identity['brain'])])
    legal = {e.get('sha256') for _, manifest, _ in BR.entries_before(identity['brain'], 'snapshot')
             for e in manifest.get('entries', []) if e.get('include')}
    legal.update(r['body']['replacement']['sha256'] for r in records.values())
    if request['original_result']['sha256'] not in legal:
        raise ValueError('successor original is not published learner knowledge')
    if request['original_result']['sha256'] in records:
        raise ValueError('successor original already has a checked replacement; select its current owner explicitly')
    frozen = json.loads(REVIEW._read_pin(request['original_inputs']))
    claims = original['claim_inputs']['claims']
    ids = [c['id'] for c in claims]
    affected = request.get('affected_claim_ids', ids)
    if (not isinstance(affected, list) or not affected or len(set(affected)) != len(affected)
            or [i for i in ids if i in affected] != affected):
        raise ValueError('affected claims must be a nonempty ordered subset of original identities')
    source, lesson = request['original_result'], original
    if request.get('replacement_claims') is not None:
        source = request['replacement_claims']
        projection = json.loads(REVIEW._read_pin(source))
        if (projection.get('schema') != 'FRANKIE_SCIENTIFIC_CLAIM_INPUTS_V1'
                or projection.get('author') != original['author']
                or [c['id'] for c in projection['claims']] != ids
                or not projection.get('claims_sha256')
                or any(a != b for a, b in zip(claims, projection['claims']) if a['id'] not in affected)):
            raise ValueError('corrected projection must preserve identities and every unaffected claim')
        claims = projection['claims']
        # Input header only, never a fabricated completed scientific lesson.
        lesson = dict(schema=original['schema'], author=original['author'], day=original['day'],
                      original_claim_day=original.get('original_claim_day', original['day']),
                      stamp=original.get('stamp'), claims_sha256=projection['claims_sha256'],
                      claims_source=source['path'], searches=[], results=[])
    document = dict(source=source, lesson=lesson, claims=claims,
                    original_lesson=original, original_source=request['original_result'],
                    input_kind='explicit_successor', affected_claim_ids=affected)
    return document, original, operation, frozen['selection']['reproduction_records']['files']


def teach_accumulated(day, search, brain, out_dir, *, _successor=None):
    """Return actual new result files, exact reuses and explicitly unconsumed inputs.

    Selection is captured once. Restart reads that selection even if publication has
    since added our own results to the brain. No search or claim synthesis occurs here.
    Discovery-day candidates are scheduled like every other claim: the scientific reader
    lists their origin evidence (never a test) from this owner's complete search parts.
    Every result of this owning day carries the OWNER's completed native evidence (the
    receipt, result summaries, sections 4.2/4.4 and FINALIZE rows the owner's search pinned),
    read whole and bytes-verified by the scientific reader into <out_dir>/native/ once (same
    bytes reuse, different bytes refuse) and set as completed_native_evidence.by_day[day];
    a retained lesson's references for OTHER days are carried unchanged (CCode slice C:
    candidate-only lessons previously produced no native evidence for the owning day).
    """
    import frankie_box_lane_state as LS
    import frankie_box_brain as BR
    import frankie_box_scientific_teacher as ST
    import frankie_box_experiment_exchange as EX
    import frankie_box_candidate_claims as CC
    import frankie_box_historical_claims as HC
    import frankie_box_historical_reproduction as HR
    import frankie_box_experiment_search as SEARCH
    import frankie_box_experiment_review as REVIEW
    from frankie_box_durable import write_json, witness

    day, search, out_dir = str(day), Path(search), Path(out_dir)
    manifest_path = search / 'MANIFEST.json'
    manifest_witness = witness(manifest_path)
    manifest_raw = manifest_path.read_bytes()
    if hashlib.sha256(manifest_raw).hexdigest() != manifest_witness['sha256']:
        raise ValueError('owning search manifest changed while being read')
    manifest = json.loads(manifest_raw)
    if str(manifest.get('day')) != day:
        raise ValueError('accumulated claims must use this owning day search')
    identity = dict(day=day, search=str(search), manifest=manifest_witness, brain=str(brain),
                    producer=witness(__file__), readers={m.__name__: witness(m.__file__)
                                                       for m in (LS, BR, ST, EX, CC, HC, HR, SEARCH, REVIEW)})
    input_path = out_dir / 'inputs.json'
    successor_document = original_result = original_operation = None
    original_records = []
    if _successor is not None:
        successor_document, original_result, original_operation, original_records = _successor_document(
            _successor, identity, input_path, REVIEW, BR)
        # An explicit request is part of restart identity, not a mutable force/retry switch.
        identity['successor'] = _successor
    # B5: the OWNER's reproduction records live beside its other outputs; the selection of its files is frozen with the
    # scientific inputs (below) and consumed by every test of this owner; later arrivals are listed in the receipt only.
    records_dir = out_dir / 'reproduction'
    late_knowledge = dict(listed=[], frozen=False, reproduction_records=[],
                          rule='knowledge published after this owner froze its selection is LISTED here, never consumed by '
                               'the frozen selection: no completed or frozen day is reopened and no frozen input is '
                               'replaced (the late-scheduling decision is held for Greg); it is available at a later '
                               'owner boundary through the same learner_knowledge selection')
    if input_path.is_file():
        if _successor is None:
            LS.require_current_selection(input_path, brain=brain)
        inputs = json.loads(input_path.read_bytes())
        if inputs.get('identity') != identity or inputs.get('schema') != 'FRANKIE_TEACHER_KNOWLEDGE_INPUTS_V1':
            raise ValueError('retained scientific knowledge belongs to another search or reader')
        if inputs.get('selection_sha256') != _digest(inputs['selection']):
            raise ValueError('retained scientific knowledge selection differs from its binding')
        frozen_records = {r['path'] for r in inputs['selection'].get('reproduction_records', {}).get('files') or []}
        late_knowledge.update(frozen=True, listed=late_arrivals(day, brain, inputs['selection'], LS),
                              reproduction_records=[dict(r, reason='arrived after this owner froze its record selection; '
                                                                   'not consumed by the frozen selection')
                                                    for r in HR.record_selection(records_dir) if r['path'] not in frozen_records])
    elif _successor is not None:
        # Keep every original record, including old bindings now listed as inadmissible by
        # the current reader. A new owner directory must not silently erase that evidence.
        retained_records = {r['path']: r for r in original_records}
        if len(retained_records) != len(original_records):
            raise ValueError('original reproduction selection repeats a path')
        for pin in original_records:
            REVIEW._read_pin(pin)
        for pin in HR.record_selection(records_dir):
            if pin['path'] in retained_records and retained_records[pin['path']] != pin:
                raise ValueError('successor reproduction record changed an original witness')
            retained_records[pin['path']] = pin
        selection = dict(documents=[successor_document], listed=[], versions=[],
                         selection_listed=[], school_listed=[],
                         reproduction_records=dict(directory=str(records_dir), files=list(retained_records.values()),
                                                   binding_tables_sha256=HC.binding_tables_sha256(),
                                                   rule='explicit successor owner record selection; later arrivals are not consumed'))
        inputs = dict(schema='FRANKIE_TEACHER_KNOWLEDGE_INPUTS_V1', identity=identity,
                      selection=selection, selection_sha256=_digest(selection))
        write_json(input_path, inputs)
    else:
        selected = LS.learner_knowledge(day, 'exchange', brain=brain)
        school, school_listed = LS.learner_school(day, brain=brain, versions=selected['versions'], stage='exchange')
        documents, listed, seen = [], [], set()

        def take(doc, source, address=()):
            if not isinstance(doc, dict):
                return
            schema = doc.get('schema')
            if schema == 'FRANKIE_STAGE_KNOWLEDGE_V1':
                for i, member in enumerate(doc.get('sources') or []):
                    if member.get('inline') and isinstance(member.get('content'), dict):
                        take(member['content'], dict(path=member['path'], sha256=member['sha256'],
                             container_sha256=source['sha256']), address + ('sources', i, 'content'))
                    else:
                        listed.append(dict(source=member.get('path'), sha256=member.get('sha256'),
                                           reason='stage source has no transported structured claim content'))
                return
            if schema == CC.SCHEMA:
                projected = CC.candidate_claims_doc(doc, claims_sha256=source['sha256'], source=source['path'])
                content_hash = _digest(doc)
                if content_hash in seen:
                    listed.append(dict(source=source, reason='identical search candidates already retained'))
                    return
                seen.add(content_hash)
                lesson = dict(schema='SEARCH_CANDIDATE_LESSONS_V1', author='search', day=projected['day'],
                              stamp=projected['stamp'], claims_sha256=projected['claims_sha256'],
                              claims_source=projected['source'], searches=[], results=[])
                documents.append(dict(lesson=lesson, source=dict(source, address=list(address)),
                                      claims=projected['claims'], claims_listed=None,
                                      input_kind='candidates_not_completed_lessons'))
                return
            if schema not in LESSONS:
                listed.append(dict(source=source, schema=schema,
                                   reason='not a completed native scientific lesson; no claims synthesized'))
                return
            if doc.get('author') != LESSONS[schema] or doc.get('written_by') != 'scientific_teacher' or \
                    not isinstance(doc.get('results'), list) or not isinstance(doc.get('searches'), list):
                raise ValueError('accumulated native lesson author or completion fields differ')
            content_hash = _digest(doc)
            if content_hash in seen:
                listed.append(dict(source=source, reason='identical completed lesson already retained'))
                return
            seen.add(content_hash)
            claims, why = EX.claims_of(doc)
            if why:
                listed.append(dict(source=source, reason=why))
            elif list(claims) != [r['claim_id'] for r in doc['results']]:
                raise ValueError('native claim projection differs from completed lesson result order')
            documents.append(dict(lesson=doc, source=dict(source, address=list(address)),
                                  claims=list(claims.values()), claims_listed=why))

        for source in selected['documents']:
            take(source['content'], {k: v for k, v in source.items() if k != 'content'})
        for row, doc in school:
            section = doc.get('sections', {}).get('scientific_teacher') or {}
            for i, item in enumerate(section.get('items') or []):
                if item.get('inline') and isinstance(item.get('content'), dict):
                    take(item['content'], dict(path=item.get('path') or str(row.get('file')),
                         sha256=item['sha256'], container_sha256=row['sha256']),
                         ('sections', 'scientific_teacher', 'items', i, 'content'))
                else:
                    listed.append(dict(source=item.get('path'), sha256=item.get('sha256'),
                                       reason='school scientific item has no transported structured claim content'))
        selection = dict(documents=documents, listed=listed, versions=selected['versions'],
                         selection_listed=selected['listed'], school_listed=school_listed,
                         reproduction_records=dict(directory=str(records_dir), files=HR.record_selection(records_dir),
                                                   binding_tables_sha256=HC.binding_tables_sha256(),
                                                   rule='the owner-local HISTORICAL_REPRODUCTION records as they were at '
                                                        'this freeze (path, bytes, sha256): the only ones any test of this '
                                                        'owner reads; later files are listed in the receipt, never read'))
        inputs = dict(schema='FRANKIE_TEACHER_KNOWLEDGE_INPUTS_V1', identity=identity,
                      selection=selection, selection_sha256=_digest(selection))
        write_json(input_path, inputs)

    input_hash = witness(input_path)['sha256']
    records_selection = inputs['selection'].get('reproduction_records') or dict(directory=str(records_dir), files=[])
    documents = inputs['selection']['documents']
    if _successor is not None and documents != [successor_document]:
        raise ValueError('successor retained selection differs from its exact original claims')
    if _successor is not None:
        selected_records = {r['path']: r for r in records_selection['files']}
        if any(selected_records.get(r['path']) != r for r in original_records):
            raise ValueError('successor retained selection lost original reproduction evidence')
        for pin in records_selection['files']:
            REVIEW._read_pin(pin)
    listed = list(inputs['selection']['listed'])
    reused, files = [], []
    created_files = 0

    def claim_key(lesson, claim):
        # Identity deduplication never merges counts, distinct IDs, authors or scopes.
        return _digest([lesson['author'], lesson['claims_sha256'], claim])

    already_tested = set()
    for item in documents:
        lesson = item['lesson']
        if _successor is None:
            result_ids = {r['claim_id'] for r in lesson['results']}
            for claim in item['claims']:
                searches = REVIEW.claim_searches(lesson, claim['id'])
                current = any(str(s.get('day')) == day and s.get('manifest_sha256') == manifest_witness['sha256']
                              for s in searches)
                if current and claim['id'] in result_ids:
                    already_tested.add(claim_key(lesson, claim))

    scheduled = set()
    # The owning search's manifest (hash-checked above) names the days, series and parts; its evidence parts are
    # hash-verified below before the first new test. The owner's completed native evidence is read once here so every
    # result header of this day, new or reused, carries the same bytes-bound reference (post-stream knowledge of the
    # completed owner day; never backfilled onto earlier frames: it is a reference in the retest lessons, not a series).
    days = ST.load_searches([search])
    if days[0]['manifest_sha256'] != manifest_witness['sha256']:
        raise ValueError('owning search manifest changed after accumulated input selection')
    # Phase 1 (stacks pass, dedupe F1; the school owner's R3): the claims each document will test and the result file
    # each would write, decided exactly as the loop below decides them (same order, same keys; the reuse entries are
    # kept per item and appended at the item's own place below, so `reused` keeps its order). The documents still to
    # be measured then go to ST.pre_read ONCE: this owner day's completed native evidence and the search-part scan of
    # every such document on one pinned pool, side by side; each ST.test gets its prepared scan (scanned=), used only
    # when its key equals the test's own read plan. Without pre_read (an older scientific teacher) the reads run as
    # before. Bytes unchanged: the same native reference, the same rows, ordinals, raw-line hashes, counts and report.
    planned = []
    for item in documents:
        lesson, claims, item_reused = item['lesson'], [], []
        for claim in item['claims']:
            key = claim_key(lesson, claim)
            if key in already_tested:
                item_reused.append(dict(source=item['source'], claim_id=claim['id'], claim_sha256=key,
                                        reason='this native claim already tested on the exact current search manifest'))
            elif key in scheduled:
                item_reused.append(dict(source=item['source'], claim_id=claim['id'], claim_sha256=key,
                                        reason='identical native claim already scheduled from a retained lesson'))
            else:
                scheduled.add(key)
                claims.append(claim)
        planned.append((item, claims, item_reused))

    def result_plan(item, claims):
        """(claim_inputs, its sha, result_identity, result path) of one document: pure, the same each call."""
        lesson = item['lesson']
        claim_inputs = dict(schema='FRANKIE_SCIENTIFIC_CLAIM_INPUTS_V1', author=lesson['author'],
                            claims_sha256=lesson['claims_sha256'], claims=claims,
                            reader_sha256=identity['readers'][ST.__name__]['sha256'],
                            # B5: the frozen record selection and the binding tables are part of what the test consumed
                            reproduction_records_selection_sha256=_digest(records_selection),
                            historical_binding_tables_sha256=HC.binding_tables_sha256())
        claim_inputs_sha = _digest(claim_inputs)
        result_identity = dict(input_sha256=input_hash, source_lesson_sha256=item['source']['sha256'],
                               source_lesson_content_sha256=_digest(lesson), original_claim_day=lesson.get('original_claim_day', lesson.get('day')),
                               claim_inputs_sha256=claim_inputs_sha, search_manifest_sha256=manifest_witness['sha256'])
        collection = original_result if _successor is not None else lesson
        collection_origin = (collection.get('knowledge_retest') or {}).get('reconsideration_origin')
        if collection_origin is not None:
            result_identity['reconsideration_origin'] = collection_origin
        elif (_successor is not None and 'reconsideration' in collection
              and collection['claims_sha256'] != lesson['claims_sha256']):
            if collection['reconsideration']['claims_file_sha256'] != collection['claims_sha256']:
                raise ValueError('original historical collection lacks its unchanged claims binding')
            result_identity['reconsideration_origin'] = dict(
                claims_sha256=collection['reconsideration']['claims_file_sha256'],
                result={k: _successor['original_result'][k] for k in ('path', 'bytes', 'sha256')})
        if _successor is not None:
            result_identity['claim_operations'] = {
                c['id']: (dict(inputs=_successor['original_inputs'], result=_successor['original_result'],
                               searches=REVIEW.claim_searches(original_result, c['id']))
                          if c['id'] not in item['affected_claim_ids'] else dict(input_sha256=input_hash,
                               searches=[dict(day=day, cycle=manifest['cycle'], dir=str(search),
                                              manifest_sha256=manifest_witness['sha256'])]))
                for c in claims}
        return claim_inputs, claim_inputs_sha, result_identity, out_dir / 'results' / (_digest(result_identity) + '.json')

    def measured_doc(item, claims):
        measured_claims = ([c for c in claims if c['id'] in item['affected_claim_ids']]
                           if _successor is not None else claims)
        return dict(author=item['lesson']['author'], claims=measured_claims)
    to_measure = [k for k, (item, claims, _) in enumerate(planned)
                  if claims and not result_plan(item, claims)[3].is_file()]
    prepared_scans, pre_read_note = {}, None
    if hasattr(ST, 'pre_read'):
        native_list, prepared_list, pre_read_note = ST.pre_read(
            days, [measured_doc(planned[k][0], planned[k][1]) for k in to_measure], out_dir)
        native_ref, native_listed = native_list[0]
        prepared_scans = dict(zip(to_measure, prepared_list))
    else:
        native_ref, native_listed = ST.completed_native_evidence(days[0], out_dir)
        pre_read_note = dict(used=False, reason='this scientific teacher has no pre_read: native evidence and each '
                                                'document\'s parts read on their own, as before')
    for index, (item, claims, item_reused) in enumerate(planned):
        lesson = item['lesson']
        reused.extend(item_reused)
        # A candidate discovered on this owning day is NOT skipped (CCode slice A, 2026-10-06): the reader's own
        # origin path lists its discovery rows from this owner's complete, hash-checked search parts (origin_evidence,
        # each row bound by part sha256 + ordinal + raw-line sha256, discovery_row true only on the exact row) and
        # counts no origin row as a test; its tests/days_tested cover other days only. Nothing is rerun or rewritten.
        # (The claim scheduling itself ran in phase 1 above, in this same order.)
        if not claims:
            continue
        claim_inputs, claim_inputs_sha, result_identity, path = result_plan(item, claims)
        collection = original_result if _successor is not None else lesson
        expected = dict(schema=lesson['schema'], author=lesson['author'], day=day,
                        original_claim_day=result_identity['original_claim_day'], stamp=lesson.get('stamp'),
                        claims_sha256=lesson['claims_sha256'], claims_source=lesson.get('claims_source'),
                        written_by='scientific_teacher', claim_inputs=claim_inputs,
                        claim_inputs_sha256=claim_inputs_sha,
                        searches=[dict(day=day, cycle=manifest['cycle'], dir=str(search),
                                       manifest_sha256=manifest_witness['sha256'])],
                        knowledge_retest=result_identity, model_calls=0,
                        rule='prior findings retained unchanged; each new day measured separately, never pooled')
        # Preserve the source collection's open work whole. Its original days and hashes are not this day's tests.
        if 'reconsideration' in collection:
            expected['reconsideration'] = collection['reconsideration']
        # Completed native evidence: the retained lesson's references for other days unchanged, plus THIS owner's
        # (a candidate-only lesson carries none of its own; the owner's search pins are the only lawful source here).
        carried = (original_result if _successor is not None else lesson).get('completed_native_evidence') or {}
        by_day = dict(carried.get('by_day') or {})
        listed_native = list(carried.get('listed') or [])
        carried_same_day = by_day.get(day)
        if native_ref is not None:
            # C1: compare the reference's IDENTITY (content, sources, owning manifest), not its materialization path:
            # the same bytes read under another output root are the same evidence; different bytes for this owner refuse.
            if carried_same_day is not None and \
                    ST.native_evidence_identity(carried_same_day) != ST.native_evidence_identity(native_ref):
                if _successor is None or not _successor.get('replacement_search'):
                    raise ValueError('retained lesson carries a different completed-native reference for this owning day')
                listed_native.append(dict(day=day, reason='explicit corrected search; previous evidence remains in the '
                                          'original operation and is not counted as a new observation', carried=carried_same_day))
                carried_same_day = None
            if carried_same_day is not None and carried_same_day.get('path') != native_ref.get('path'):
                listed_native.append(dict(day=day, reason='the carried same-day reference is the same evidence materialized '
                                                          'at another path; the owner\'s own materialization is cited',
                                          carried_path=carried_same_day.get('path'), sha256=native_ref.get('sha256')))
            by_day[day] = native_ref
        elif carried_same_day is not None:
            # no completed-native evidence of THIS owner: a carried same-day reference from another manifest never stands
            # in for it; it is listed with its provenance and left out of by_day for this owner (C1).
            by_day.pop(day)
            listed_native.append(dict(day=day, reason='this owner\'s search carries no completed native evidence; the '
                                                      'retained lesson\'s same-day reference (another manifest) is not '
                                                      'read as the owner\'s and is listed with its provenance',
                                      carried=dict(path=carried_same_day.get('path'), sha256=carried_same_day.get('sha256'),
                                                   search_manifest_sha256=carried_same_day.get('search_manifest_sha256'))))
        listed_native += [x for x in native_listed if x not in listed_native]
        expected['completed_native_evidence'] = dict(
            by_day=by_day, listed=listed_native,
            owner_day=dict(day=day, generated=native_ref is not None, search_manifest_sha256=manifest_witness['sha256'],
                           reader='frankie_box_scientific_teacher.completed_native_evidence (owner-local, bytes-bound)'),
            rule=carried.get('rule') or ('each searched day\'s completed native evidence (receipt, result summaries, sections '
                                        '4.2/4.4, FINALIZE rows) read whole and bound by sha256 for both exchange seats; exact '
                                        'numbers are evidence, averages are labelled supplements (D37); post-stream rows are '
                                        'never search steps'))
        if path.is_file():
            result = json.loads(path.read_bytes())
            # evidence_read is the read's own measurement (rows hashed/parsed/selected), not an input: never compared
            header = {k: v for k, v in result.items() if k not in ('results', 'results_sha256', 'evidence_read')}
            if header != expected or result.get('results_sha256') != _digest(result.get('results')) or \
                    [r['claim_id'] for r in result['results']] != [c['id'] for c in claims]:
                raise ValueError('completed accumulated teaching differs from its exact retained inputs')
            reused.append(dict(path=str(path), reason='completed result reused; no scientific test repeated'))
        else:
            # The scientific reader checks hashes/lengths in the actual consumed binary
            # stream; a separate full pre-read adds I/O without binding those later reads.
            doc = measured_doc(item, claims)
            measured_claims = doc['claims']
            read_report = {}     # what the read did (row filter, parts, rows hashed/parsed/selected; school_recovery 2026-10-07)
            extra = dict(scanned=prepared_scans[index]) if prepared_scans.get(index) is not None else {}
            measured = ST.test(doc, days,
                              records_dir=Path(records_selection['directory']), records_selection=records_selection['files'],
                              report=read_report, **extra)
            if [r['claim_id'] for r in measured] != [c['id'] for c in measured_claims]:
                raise ValueError('scientific owner returned a different affected claim set')
            retained = {r['claim_id']: r for r in original_result['results']} if _successor is not None else {}
            retained.update({r['claim_id']: r for r in measured})
            results = [retained[c['id']] for c in claims]
            result = dict(expected, results=results, results_sha256=_digest(results), evidence_read=read_report)
            write_json(path, result)
            created_files += 1
        if _successor is not None:
            transition = dict(schema=REVIEW.TRANSITION_SCHEMA,
                              owner='frankie_box_teacher_knowledge.teach_accumulated',
                              original=original_operation,
                              replacement=REVIEW._transition_operation(dict(path=str(input_path), **witness(input_path)), result))
            REVIEW._validate_transition(transition, original_result, result, dict(day=day))
            # Research result retained whole. Only an explicit checked decision can replace
            # the original; do not publish this candidate as an ordinary additional lesson.
            files.append(dict(path=str(path), **witness(path), author=lesson['author'],
                              claim_ids=[c['id'] for c in claims], publication='awaiting_checked_owner_decision'))
            continue
        # Publication is repeatable, including recovery after the complete file was saved.
        if lesson['author'] == 'search':
            # The standalone CCode publisher still refuses this new author. Use the
            # existing brain writer now that it admits completed owner-local checks.
            entry = Path(brain) / ('%s-lessons' % day)
            entry_manifest = entry / 'MANIFEST.json'
            retained = json.loads(entry_manifest.read_bytes()) if entry_manifest.is_file() else {}
            result_sha = witness(path)['sha256']
            prior = next((e for e in retained.get('entries', []) if e.get('sha256') == result_sha), None)
            if prior is None:
                BR.write_lessons_entry(brain, day, path)
            elif (entry / prior['name']).read_bytes() != path.read_bytes():
                raise ValueError('published candidate lesson differs from its retained result')
        else:
            ST.publish_lessons(path, brain_dir=brain)
        files.append(dict(path=str(path), **witness(path), author=lesson['author'],
                          claim_ids=[c['id'] for c in claims]))
    # C1: the actual scope of this call: a loop that reuses every claim emits no new result file and says so.
    scope = dict(new_result_files=created_files, completed_result_files=len(files),
                 reused=len(reused), inputs_listed=len(listed),
                 claims_scheduled=len(scheduled), claims_already_tested=len(already_tested),
                 all_reused=created_files == 0, owner_native_evidence=native_ref is not None,
                 pre_read=pre_read_note,
                 rule='new_result_files counts the result headers this call wrote; none means every claim was already '
                      'tested on this exact manifest or reused: no new scientific result was written. '
                      'completed_result_files includes exact reuses available for publication')
    result = dict(inputs=dict(path=str(input_path), **witness(input_path)), files=files,
                reused=reused, listed=listed, selection_listed=inputs['selection']['selection_listed'],
                school_listed=inputs['selection']['school_listed'], late_knowledge=late_knowledge, scope=scope)
    if _successor is not None:
        result.update(schema='FRANKIE_TEACHER_SUCCESSOR_RECEIPT_V1',
                      successor_request=_successor, publication='awaiting_checked_owner_decision',
                      owner_transition=dict(original_inputs=_successor['original_inputs'], replacement_inputs=result['inputs']))
        result['scope']['rule'] = ('explicit same-search owner retest, not independent evidence; result files include '
                                  'exact completed reuses; no correction or ordinary lesson was published')
        result['scope'].update(new_result_files=created_files, completed_result_files=len(files),
                               all_reused=created_files == 0)
        write_json(out_dir / 'successor-receipt.json', result)
    return result


def late_arrivals(day, brain, selection, LS):
    """Completed brain documents the learner selection would include NOW that the frozen selection did not see: listed
    (label, kind, day, path, sha256, schema), not consumed. A delivery drop made visible at the unfinished-work boundary;
    the frozen selection, its identity and every retained result are untouched (CCode slice D, 2026-10-06)."""
    seen = set()
    for document in selection.get('documents') or []:
        source = document.get('source') or {}
        seen.update(x for x in (source.get('sha256'), source.get('container_sha256')) if x)
    for item in selection.get('listed') or []:
        source = item.get('source')
        seen.update(x for x in ((source or {}).get('sha256') if isinstance(source, dict) else item.get('sha256'),
                                item.get('sha256')) if x)
    current = LS.learner_knowledge(day, 'exchange', brain=brain)
    return [dict(label=d.get('label'), kind=d.get('kind'), day=d.get('day'), path=d.get('path'), sha256=d.get('sha256'),
                 schema=(d.get('content') or {}).get('schema') if isinstance(d.get('content'), dict) else None,
                 reason='published after this owner froze its scientific selection; not consumed by the frozen selection')
            for d in current['documents'] if d.get('sha256') not in seen]
