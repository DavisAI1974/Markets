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


def teach_accumulated(day, search, brain, out_dir):
    """Return actual new result files, exact reuses and explicitly unconsumed inputs.

    Selection is captured once. Restart reads that selection even if publication has
    since added our own results to the brain. No search or claim synthesis occurs here.
    Discovery-day candidates are scheduled like every other claim: the scientific reader
    lists their origin evidence (never a test) from this owner's complete search parts.
    """
    import frankie_box_lane_state as LS
    import frankie_box_brain as BR
    import frankie_box_scientific_teacher as ST
    import frankie_box_experiment_exchange as EX
    import frankie_box_candidate_claims as CC
    import frankie_box_historical_claims as HC
    import frankie_box_historical_reproduction as HR
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
                                                       for m in (LS, BR, ST, EX, CC, HC, HR)})
    input_path = out_dir / 'inputs.json'
    if input_path.is_file():
        inputs = json.loads(input_path.read_bytes())
        if inputs.get('identity') != identity or inputs.get('schema') != 'FRANKIE_TEACHER_KNOWLEDGE_INPUTS_V1':
            raise ValueError('retained scientific knowledge belongs to another search or reader')
        if inputs.get('selection_sha256') != _digest(inputs['selection']):
            raise ValueError('retained scientific knowledge selection differs from its binding')
    else:
        selected = LS.learner_knowledge(day, 'exchange', brain=brain)
        school, school_listed = LS.learner_school(day, brain=brain, versions=selected['versions'])
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
                         selection_listed=selected['listed'], school_listed=school_listed)
        inputs = dict(schema='FRANKIE_TEACHER_KNOWLEDGE_INPUTS_V1', identity=identity,
                      selection=selection, selection_sha256=_digest(selection))
        write_json(input_path, inputs)

    input_hash = witness(input_path)['sha256']
    documents = inputs['selection']['documents']
    listed = list(inputs['selection']['listed'])
    reused, files = [], []

    def claim_key(lesson, claim):
        # Identity deduplication never merges counts, distinct IDs, authors or scopes.
        return _digest([lesson['author'], lesson['claims_sha256'], claim])

    already_tested = set()
    for item in documents:
        lesson = item['lesson']
        current = any(str(s.get('day')) == day and
                      s.get('manifest_sha256') == manifest_witness['sha256']
                      for s in lesson['searches'])
        if current:
            result_ids = {r['claim_id'] for r in lesson['results']}
            for claim in item['claims']:
                if claim['id'] in result_ids:
                    already_tested.add(claim_key(lesson, claim))

    scheduled = set()
    days = None
    for item in documents:
        lesson, claims = item['lesson'], []
        for claim in item['claims']:
            key = claim_key(lesson, claim)
            # A candidate discovered on this owning day is NOT skipped (CCode slice A, 2026-10-06): the reader's own
            # origin path lists its discovery rows from this owner's complete, hash-checked search parts (origin_evidence,
            # each row bound by part sha256 + ordinal + raw-line sha256, discovery_row true only on the exact row) and
            # counts no origin row as a test; its tests/days_tested cover other days only. Nothing is rerun or rewritten.
            if key in already_tested:
                reused.append(dict(source=item['source'], claim_id=claim['id'], claim_sha256=key,
                                   reason='this native claim already tested on the exact current search manifest'))
            elif key in scheduled:
                reused.append(dict(source=item['source'], claim_id=claim['id'], claim_sha256=key,
                                   reason='identical native claim already scheduled from a retained lesson'))
            else:
                scheduled.add(key)
                claims.append(claim)
        if not claims:
            continue
        claim_inputs = dict(schema='FRANKIE_SCIENTIFIC_CLAIM_INPUTS_V1', author=lesson['author'],
                            claims_sha256=lesson['claims_sha256'], claims=claims,
                            reader_sha256=identity['readers'][ST.__name__]['sha256'])
        claim_inputs_sha = _digest(claim_inputs)
        result_identity = dict(input_sha256=input_hash, source_lesson_sha256=item['source']['sha256'],
                               source_lesson_content_sha256=_digest(lesson), original_claim_day=lesson.get('original_claim_day', lesson.get('day')),
                               claim_inputs_sha256=claim_inputs_sha, search_manifest_sha256=manifest_witness['sha256'])
        path = out_dir / 'results' / (_digest(result_identity) + '.json')
        expected = dict(schema=lesson['schema'], author=lesson['author'], day=day,
                        original_claim_day=result_identity['original_claim_day'], stamp=lesson.get('stamp'),
                        claims_sha256=lesson['claims_sha256'], claims_source=lesson.get('claims_source'),
                        written_by='scientific_teacher', claim_inputs=claim_inputs,
                        claim_inputs_sha256=claim_inputs_sha,
                        searches=[dict(day=day, cycle=manifest['cycle'], dir=str(search),
                                       manifest_sha256=manifest_witness['sha256'])],
                        knowledge_retest=result_identity, model_calls=0,
                        rule='prior findings retained unchanged; each new day measured separately, never pooled')
        # Preserve the source collection's open work and completed post-stream
        # references whole. Their original days and hashes are not this day's tests.
        for field in ('reconsideration', 'completed_native_evidence'):
            if field in lesson:
                expected[field] = lesson[field]
        if path.is_file():
            result = json.loads(path.read_bytes())
            header = {k: v for k, v in result.items() if k not in ('results', 'results_sha256')}
            if header != expected or result.get('results_sha256') != _digest(result.get('results')) or \
                    [r['claim_id'] for r in result['results']] != [c['id'] for c in claims]:
                raise ValueError('completed accumulated teaching differs from its exact retained inputs')
            reused.append(dict(path=str(path), reason='completed result reused; no scientific test repeated'))
        else:
            if days is None:
                seen_parts = set()
                for part in manifest['couplings']['parts']:
                    relative = Path(part['path'])
                    if relative.is_absolute() or '..' in relative.parts:
                        raise ValueError('search evidence part must remain under its owning search directory')
                    source = (search / relative).resolve()
                    if not source.is_relative_to(search.resolve()) or source in seen_parts:
                        raise ValueError('search evidence part escapes its owner or repeats an existing part')
                    seen_parts.add(source)
                    actual = witness(source)  # Stream hashes; giant evidence remains on its original lane.
                    if actual['sha256'] != part['sha256'] or \
                            ('bytes' in part and actual['bytes'] != part['bytes']):
                        raise ValueError('owning search evidence differs from its manifest: %s' % source)
                days = ST.load_searches([search])
                if days[0]['manifest_sha256'] != manifest_witness['sha256']:
                    raise ValueError('owning search manifest changed after accumulated input selection')
            results = ST.test(dict(author=lesson['author'], claims=claims), days)
            result = dict(expected, results=results, results_sha256=_digest(results))
            write_json(path, result)
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
    return dict(inputs=dict(path=str(input_path), sha256=input_hash), files=files,
                reused=reused, listed=listed, selection_listed=inputs['selection']['selection_listed'],
                school_listed=inputs['selection']['school_listed'])
