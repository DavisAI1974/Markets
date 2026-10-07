"""Step 5: existing market checks and explicit corrections, never recency-based forgetting.

Older compatible lessons remain active. A contradiction opens research; it does not retire
either lesson. A completed, explicitly scoped correction replaces only its established scope.
This module makes no new scientific acceptance rule.
"""
import hashlib
import json
import re
from pathlib import Path

SCHEMA = 'FRANKIE_KNOWLEDGE_CORRECTION_V1'
TRANSITION_SCHEMA = 'FRANKIE_CORRECTION_OWNER_TRANSITION_V1'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def _at(value, address):
    for key in address:
        if isinstance(value, list):
            if type(key) is not int or not 0 <= key < len(value):
                raise ValueError('correction list address differs')
        elif not isinstance(value, dict) or not isinstance(key, str) or key not in value:
            raise ValueError('correction object address differs')
        value = value[key]
    return value


def _outside(value, scopes, address=()):
    if address in scopes:
        return None
    if isinstance(value, dict):
        return {k: _outside(v, scopes, address + (k,)) for k, v in value.items()}
    if isinstance(value, list):
        return [_outside(v, scopes, address + (i,)) for i, v in enumerate(value)]
    return value


def _lesson_digest(value):
    # The scientific teacher's existing content encoding, distinct from record addressing.
    return digest(json.dumps(value, sort_keys=True, allow_nan=False).encode())


def _transition_operation(pin, lesson):
    """Read the actual frozen accumulated-teacher operation; never manufacture a successor."""
    inputs = json.loads(_read_pin(pin))
    if inputs.get('schema') != 'FRANKIE_TEACHER_KNOWLEDGE_INPUTS_V1':
        raise ValueError('correction transition requires accumulated-teacher frozen inputs')
    selection = inputs['selection']
    if inputs.get('selection_sha256') != _lesson_digest(selection):
        raise ValueError('correction transition selection differs from its binding')
    retest = lesson.get('knowledge_retest') or {}
    sources = [d for d in selection['documents']
               if d['source']['sha256'] == retest.get('source_lesson_sha256')
               and _lesson_digest(d['lesson']) == retest.get('source_lesson_content_sha256')]
    if len(sources) != 1:
        raise ValueError('correction result does not name one exact frozen source lesson')
    source = sources[0]
    claims = lesson['claim_inputs']['claims']
    ids = [c['id'] for c in claims]
    if (len(set(ids)) != len(ids) or not ids
            or [c for c in source['claims'] if c['id'] in set(ids)] != claims
            or any(source['lesson'].get(key) != lesson.get(key) for key in ('schema', 'author', 'claims_sha256'))
            or retest.get('original_claim_day') != source['lesson'].get('original_claim_day', source['lesson'].get('day'))):
        raise ValueError('correction claim projection differs from its exact selected source')
    records = selection.get('reproduction_records')
    if not isinstance(records, dict) or not records.get('binding_tables_sha256'):
        raise ValueError('correction operation lacks its frozen reproduction binding')
    return dict(inputs={k: pin[k] for k in ('path', 'bytes', 'sha256')},
                identity=inputs['identity'], selection_sha256=inputs['selection_sha256'],
                source_lesson_sha256=retest['source_lesson_sha256'],
                source_lesson_content_sha256=retest['source_lesson_content_sha256'],
                reproduction_records_selection_sha256=_lesson_digest(records),
                historical_binding_tables_sha256=records['binding_tables_sha256'])


def _validate_transition(transition, before, after, publication):
    """Check the transported owner binding without exposing private frozen selections."""
    if (not isinstance(transition, dict) or transition.get('schema') != TRANSITION_SCHEMA
            or transition.get('owner') != 'frankie_box_teacher_knowledge.teach_accumulated'):
        raise ValueError('changed claim inputs require an explicit supported scientific-owner transition')
    operations = []
    for name, lesson in (('original', before), ('replacement', after)):
        operation = transition[name]
        pin, identity = operation['inputs'], operation['identity']
        if (not isinstance(pin.get('path'), str) or not pin['path'] or type(pin.get('bytes')) is not int
                or pin['bytes'] < 0 or not re.fullmatch('[0-9a-f]{64}', str(pin.get('sha256')))):
            raise ValueError('correction transition lacks an exact frozen-input witness')
        claims = lesson.get('claim_inputs')
        if (not isinstance(claims, dict) or claims.get('schema') != 'FRANKIE_SCIENTIFIC_CLAIM_INPUTS_V1'
                or lesson.get('claim_inputs_sha256') != _lesson_digest(claims)
                or claims.get('author') != lesson['author']
                or claims.get('claims_sha256') != lesson['claims_sha256']
                or [c['id'] for c in claims['claims']] != [r['claim_id'] for r in lesson['results']]):
            raise ValueError('correction transition has an inconsistent complete claim projection')
        retest = lesson.get('knowledge_retest') or {}
        expected = dict(input_sha256=pin['sha256'], claim_inputs_sha256=lesson['claim_inputs_sha256'],
                        search_manifest_sha256=identity['manifest']['sha256'],
                        source_lesson_sha256=operation['source_lesson_sha256'],
                        source_lesson_content_sha256=operation['source_lesson_content_sha256'])
        if any(retest.get(key) != value for key, value in expected.items()):
            raise ValueError('correction transition differs from its completed result operation')
        for key in ('selection_sha256', 'source_lesson_sha256', 'source_lesson_content_sha256',
                    'reproduction_records_selection_sha256', 'historical_binding_tables_sha256'):
            if not re.fullmatch('[0-9a-f]{64}', str(operation.get(key))):
                raise ValueError('correction transition lacks its complete operation binding: ' + key)
        if (claims.get('reader_sha256') != identity['readers']['frankie_box_scientific_teacher']['sha256']
                or any(claims.get(key) != operation[key] for key in
                       ('reproduction_records_selection_sha256', 'historical_binding_tables_sha256'))
                or identity.get('day') != lesson['day'] or not identity.get('brain')
                or not identity.get('search') or lesson.get('results_sha256') != _lesson_digest(lesson['results'])):
            raise ValueError('correction result differs from its scientific-owner input binding')
        searches = lesson.get('searches') or []
        if (len(searches) != 1 or searches[0].get('day') != identity['day']
                or searches[0].get('dir') != identity['search']
                or searches[0].get('manifest_sha256') != identity['manifest']['sha256']):
            raise ValueError('correction transition must name the actual owning search')
        operations.append(operation)
    if (operations[0]['identity']['brain'] != operations[1]['identity']['brain']
            or operations[1]['identity']['day'] != publication['day']
            or operations[0]['inputs']['sha256'] == operations[1]['inputs']['sha256']
            or operations[0]['inputs']['path'] == operations[1]['inputs']['path']):
        raise ValueError('correction successor needs a distinct retained operation on the same owner day/brain')


def _validate_correction(body, before, after):
    """Validate a declared scientific-owner decision, not decide whether the science is true."""
    decisions = ('demonstrated_source_error', 'researched_partial_replacement', 'researched_full_replacement')
    scopes = body.get('scopes')
    if (body.get('schema') != SCHEMA or body.get('decision') not in decisions
            or not isinstance(body.get('reason'), str) or not body['reason'].strip()
            or not body.get('evidence') or not isinstance(scopes, list) or not scopes
            or any(not isinstance(p, list) or any(type(k) not in (str, int) for k in p) for p in scopes)):
        raise ValueError('correction requires a resolved decision, exact scope, reason and checked evidence')
    publication = body.get('publication') or {}
    if (not re.fullmatch('[0-9]{8}', str(publication.get('day')))
            or publication.get('stage') != 'lessons' or body.get('written_by') != 'scientific_teacher'):
        raise ValueError('correction requires its actual scientific completion day and lessons boundary')
    addresses = {tuple(p) for p in scopes}
    if len(addresses) != len(scopes):
        raise ValueError('duplicate correction address')
    if body['decision'] == 'researched_partial_replacement' and () in addresses:
        raise ValueError('partial replacement cannot replace the whole lesson')
    if body['decision'] == 'researched_full_replacement' and addresses != {()}:
        raise ValueError('full replacement must explicitly name the whole lesson')
    if not isinstance(before, dict) or not isinstance(after, dict) or before == after:
        raise ValueError('correction requires two different complete lesson objects')
    schemas = {'frankie': 'FRANKIE_LESSONS_V1', 'historical': 'HISTORICAL_LESSONS_V1',
               'jev': 'JEV_LESSONS_V1', 'search': 'SEARCH_CANDIDATE_LESSONS_V1'}
    if before.get('schema') != schemas.get(before.get('author')) or before.get('schema') is None:
        raise ValueError('correction accepts only the existing scientific lesson schemas')
    # Exactly the same subject, not text similarity, a newer date or a loosely matching pair.
    for key in ('schema', 'author', 'day', 'claims_sha256'):
        if before.get(key) != after.get(key):
            raise ValueError('correction changes the original lesson subject: ' + key)
    transition = body.get('owner_transition')
    changed_inputs = any(before.get(key) != after.get(key) for key in ('claim_inputs', 'claim_inputs_sha256'))
    if changed_inputs or transition is not None:
        _validate_transition(transition, before, after, publication)
    if not before.get('claims_sha256') or before.get('written_by') != 'scientific_teacher' or after.get('written_by') != 'scientific_teacher':
        raise ValueError('correction needs a claim-bound scientific lesson')
    if [r['claim_id'] for r in before['results']] != [r['claim_id'] for r in after['results']]:
        raise ValueError('correction must retain every original claim identity')
    if 'results_sha256' in after and after['results_sha256'] != digest(json.dumps(after['results'], sort_keys=True).encode()):
        raise ValueError('corrected results differ from their own content binding')
    for address in addresses:
        _at(before, address)
        _at(after, address)
    if canonical(_outside(before, addresses)) != canonical(_outside(after, addresses)):
        raise ValueError('correction changes knowledge outside its declared scope')


def _read_pin(item):
    raw = Path(item['path']).read_bytes()
    if type(item.get('bytes')) is not int or len(raw) != item['bytes'] or digest(raw) != item['sha256']:
        raise ValueError('correction artifact missing or changed: ' + str(item['path']))
    return raw


def _save_object(brain, raw):
    from frankie_box_durable import write_bytes
    path = Path(brain) / 'corrections' / 'objects' / (digest(raw) + '.json')
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('correction object traverses a symbolic link')
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError('correction object differs from its content address')
    else:
        write_bytes(path, raw)
    return dict(path=str(path), bytes=len(raw), sha256=digest(raw))


def record_correction(brain, *, original, replacement, scopes, decision, reason, evidence, publication_day,
                      owner_transition=None):
    """Publish the scientific owner's completed decision. This performs no research or retest.

    Arguments are exact path/bytes/sha256 witnesses. The original must already be legal brain
    knowledge. Full replacement is explicit; a partial replacement retains every other value.
    Evidence stays at its exact owner path; it is not copied into learner-visible knowledge.
    Publication day names the owning workflow day whose lessons stage completed this correction,
    independently of the older lesson's dates. It preserves the existing own-day answer wall.
    Changed accumulated-teacher claim inputs require owner_transition with original_inputs and
    replacement_inputs witnesses. Both actual frozen selections are checked here; transport retains
    their bindings, not their private contents. No scheduling or scientific execution occurs here.
    """
    import fcntl
    import frankie_box_brain as BR
    from frankie_box_durable import write_json, witness
    brain = Path(brain)
    raw_before, raw_after = _read_pin(original), _read_pin(replacement)
    before, after = json.loads(raw_before), json.loads(raw_after)
    for pin in evidence:
        _read_pin(pin)
    body = dict(schema=SCHEMA, written_by='scientific_teacher',
                original={k: original[k] for k in ('path', 'bytes', 'sha256')},
                replacement={k: replacement[k] for k in ('path', 'bytes', 'sha256')},
                scopes=scopes, decision=decision, reason=reason, evidence=evidence,
                publication=dict(day=str(publication_day), stage='lessons'))
    if owner_transition is not None:
        body['owner_transition'] = dict(schema=TRANSITION_SCHEMA,
            owner='frankie_box_teacher_knowledge.teach_accumulated',
            original=_transition_operation(owner_transition['original_inputs'], before),
            replacement=_transition_operation(owner_transition['replacement_inputs'], after))
        if any(Path(body['owner_transition'][name]['identity']['brain']).resolve() != brain.resolve()
               for name in ('original', 'replacement')):
            raise ValueError('correction transition belongs to another publishing brain')
    _validate_correction(body, before, after)
    # Serialize competing owner publications; readers also refuse any competing transported heads.
    directory = brain / 'corrections'
    directory.mkdir(parents=True, exist_ok=True)
    if any(p.is_symlink() for p in (directory, *directory.parents, directory / 'publish.lock')):
        raise ValueError('correction publication traverses a symbolic link')
    with (directory / 'publish.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        existing = corrections([brain])
        legal = {e.get('sha256') for _, m, _ in BR.entries_before(brain, 'snapshot')
                 for e in m.get('entries', []) if e.get('include')}
        legal.update(r['body']['replacement']['sha256'] for r in existing.values())
        if original['sha256'] not in legal:
            raise ValueError('correction original is not published learner knowledge')
        prior = existing.get(original['sha256'])
        if prior and prior['body'] != body:
            raise ValueError('competing correction needs research; never select by recency')
        cursor, visited = replacement['sha256'], {original['sha256']}
        while cursor in existing:
            if cursor in visited:
                raise ValueError('correction cycle')
            visited.add(cursor)
            cursor = existing[cursor]['body']['replacement']['sha256']
        if cursor in visited:
            raise ValueError('correction cycle')
        _save_object(brain, raw_before)
        _save_object(brain, raw_after)
        path = directory / (digest(canonical(body)) + '.json')
        if not path.exists():
            write_json(path, body)
        return dict(path=str(path), **witness(path))


def corrections(roots):
    """Read exact owner-local/transported replacement links; no implicit age/conflict policy."""
    found = {}
    for root in roots:
        for path in sorted((Path(root) / 'corrections').glob('*.json')):
            raw = path.read_bytes()
            body = json.loads(raw)
            if path.stem != digest(canonical(body)):
                raise ValueError('correction record differs from its content address: ' + str(path))
            values, objects = [], []
            for item in (body['original'], body['replacement']):
                if not re.fullmatch('[0-9a-f]{64}', str(item.get('sha256'))):
                    raise ValueError('correction lacks exact artifact identity')
                pin = dict(item, path=str(path.parent / 'objects' / (item['sha256'] + '.json')))
                values.append(json.loads(_read_pin(pin)))
                objects.append(pin)
            _validate_correction(body, *values)
            for item in body['evidence']:
                if (not isinstance(item.get('path'), str) or type(item.get('bytes')) is not int
                        or item['bytes'] < 0 or not re.fullmatch('[0-9a-f]{64}', str(item.get('sha256')))):
                    raise ValueError('correction lacks an exact owner evidence witness')
            sha = body['original']['sha256']
            if sha in found and found[sha]['body'] != body:
                raise ValueError('competing corrections require research: ' + sha)
            found[sha] = dict(body=body, record=dict(path=str(path), bytes=len(raw), sha256=digest(raw)),
                              original=objects[0], replacement=objects[1])
    for start in found:
        cursor, seen = start, set()
        while cursor in found:
            if cursor in seen:
                raise ValueError('correction cycle: ' + cursor)
            seen.add(cursor)
            cursor = found[cursor]['replacement']['sha256']
    return found


def references(value):
    """Recorded hash dependencies only. No date, text similarity or age comparison."""
    refs = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if ((key == 'sha256' or key.endswith('_sha256')) and isinstance(item, str)
                    and re.fullmatch('[0-9a-f]{64}', item)):
                refs.add(item)
            elif isinstance(item, (dict, list)):
                refs.update(references(item))
    elif isinstance(value, list):
        for item in value:
            refs.update(references(item))
    return refs


def _ancestors(sha, records):
    ancestors = set()
    for original in records:
        cursor = original
        while cursor in records:
            cursor = records[cursor]['replacement']['sha256']
            if cursor == sha:
                ancestors.add(original)
                break
    return ancestors


def require_current(documents, records):
    """Reject a pinned pending operation that still depends on an explicitly replaced source.

    Caller supplies the complete selected documents, not a reduced claim list. Known dependencies
    propagate transitively within that selection. Completed old predictions are never rewritten.
    """
    affected = set(records)
    dependencies = {d['sha256']: references(d['content']) - _ancestors(d['sha256'], records) for d in documents}
    while True:
        changed = {sha for sha, refs in dependencies.items() if refs & affected} - affected
        if not changed:
            break
        affected.update(changed)
    pending = [dict(path=d.get('path'), sha256=d['sha256']) for d in documents if d['sha256'] in affected]
    if pending:
        raise ValueError('resolved correction requires a checked successor for these pinned inputs: '
                         + json.dumps(pending, sort_keys=True))


def current_document(document, records, brain, *, day, stage):
    """Deliver a complete corrected lesson, including unchanged portions, with true file pins.

    Existing stage/school containers carry that same corrected source. Derived conclusions are
    never repaired by merely changing their dependency hash: those require a checked successor.
    No unrelated or unresolved conflicting lesson is filtered from the selection.
    """
    result = dict(document)
    if not records:
        return result
    ancestors = _ancestors(result['sha256'], records)
    expected = (records[result['sha256']]['original'] if result['sha256'] in records else
                next((records[sha]['replacement'] for sha in ancestors
                      if records[sha]['replacement']['sha256'] == result['sha256']), None))
    if expected and canonical(result['content']) != canonical(json.loads(_read_pin(expected))):
        raise ValueError('inline knowledge content differs from its correction source identity')
    applied = [records[sha]['record'] for sha in sorted(ancestors)]
    for sha in ancestors:
        if str(day) == records[sha]['body']['publication']['day'] and stage in ('root', 'teacher', 'classroom', 'search'):
            raise ValueError('corrected lesson is beyond this day answer boundary')
    while result['sha256'] in records:
        record = records[result['sha256']]
        publication = record['body']['publication']
        if str(day) == publication['day'] and stage in ('root', 'teacher', 'classroom', 'search'):
            raise ValueError('corrected lesson is beyond this day answer boundary; old error is not a substitute')
        ancestors.add(result['sha256'])
        pin = record['replacement']
        result.update(pin, content=json.loads(_read_pin(pin)))
        applied.append(record['record'])
    content = result['content']
    schema = content.get('schema') if isinstance(content, dict) else None
    changed = False
    # Transform ONLY explicit copied-source containers, never computed result structures.
    if schema in ('FRANKIE_STAGE_KNOWLEDGE_V1', 'FRANKIE_SCHOOL_KNOWLEDGE_V1'):
        content = json.loads(json.dumps(content))
        groups = ([content.get('sources') or []] if schema == 'FRANKIE_STAGE_KNOWLEDGE_V1'
                  else [s.get('items') or [] for s in (content.get('sections') or {}).values() if s])
        for group in groups:
            for item in group:
                if item.get('inline') and 'content' in item and item.get('sha256'):
                    corrected = current_document(item, records, brain, day=day, stage=stage)
                    applied.extend(corrected.get('corrections_applied') or [])
                    if corrected['sha256'] != item['sha256']:
                        item.update({k: corrected[k] for k in ('path', 'bytes', 'sha256', 'content')})
                        changed = True
                elif item.get('sha256') in records:
                    raise ValueError('corrected pointer needs its actual checked source delivered: ' + str(item.get('path')))
        if changed:
            result.update(_save_object(brain, canonical(content)), content=content)
    else:
        # A checked successor may cite its own previous bytes as provenance. That exception
        # is exact to this link, not an exemption for arbitrary stale downstream results.
        stale = (references(content) & set(records)) - ancestors
        if stale:
            raise ValueError('derived knowledge still cites a replaced source; checked successor required: '
                             + ', '.join(sorted(stale)))
    if applied:
        result['corrections_applied'] = list({r['sha256']: r for r in applied}.values())
    return result


def frozen_documents(path):
    """The two existing teacher-selection formats; no inference from arbitrary directory contents."""
    value = json.loads(Path(path).read_bytes())
    if value.get('schema') == 'FRANKIE_TEACHER_KNOWLEDGE_INPUTS_V1':
        return [dict(d['source'], content=d['lesson']) for d in value['selection']['documents']]
    if value.get('schema') == 'FRANKIE_EXCHANGE_KNOWLEDGE_INPUTS_V1':
        return [dict(source, content=doc) for doc, source in value['documents']]
    raise ValueError('unknown frozen knowledge selection: ' + str(path))


def search_findings(target, day):
    """Recheck stored search rows with the existing count arithmetic and field-role policy.

    No scientific run or independent confirmation is performed. Failed rows remain precisely
    listed for correction; valid candidates keep their original values and identities.
    """
    import frankie_box_experiment_search as SEARCH
    import frankie_box_experiment_exchange as EX
    target = Path(target)
    manifest_raw = (target / 'MANIFEST.json').read_bytes()
    manifest = json.loads(manifest_raw)
    if manifest.get('schema') != SEARCH.SCHEMA or str(manifest.get('day')) != str(day):
        raise ValueError('step-5 review must use the owning day search')
    findings, listed, checked = [], [], 0
    seen = set()
    for pin in manifest['couplings']['parts']:
        part = target / pin['path']
        if not part.resolve().is_relative_to(target.resolve()) or pin['path'] in seen:
            raise ValueError('ambiguous/outside search part in review')
        seen.add(pin['path'])
        hashed, size = hashlib.sha256(), 0
        with part.open('rb') as handle:
            for ordinal, raw in enumerate(handle):
                hashed.update(raw)
                size += len(raw)
                row = json.loads(raw)
                if not isinstance(row, dict):
                    raise ValueError('search evidence row is not an object: %s row %d' % (part, ordinal))
                reasons = []
                for field in ('x', 'y', 'cell'):
                    name = row.get(field)
                    if not isinstance(name, str):
                        reasons.append('missing exact ' + field)
                        continue
                    role = SEARCH.non_market_reason(name)
                    if role and not (field == 'cell' and role == 'context_only'):
                        reasons.append('%s: %s' % (field, role))
                projected = dict(row, counts={k: row.get(k) for k in
                    ('same_way', 'opposite', 'both_moving', 'x_moves', 'y_moves')}, lag=row.get('best_lag'),
                    x_transform=row.get('x_transform', row.get('transform', 'sign_of_step')),
                    y_transform=row.get('y_transform', 'sign_of_step'))
                arithmetic, _ = EX.count_margins(projected)
                reasons.extend(arithmetic)
                if type(row.get('beyond_chance')) is not bool:
                    reasons.append('chance result must be the stored boolean decision')
                source = dict(part=pin['path'], part_sha256=pin['sha256'], row=ordinal,
                              row_sha256=digest(raw))
                checked += 1
                if reasons:
                    listed.append(dict(source, reasons=reasons, disposition='needs_source_correction',
                                       counts_as_independent_check=False))
                elif row.get('beyond_chance'):
                    findings.append(dict(source, content=row))
        if hashed.hexdigest() != pin['sha256'] or ('bytes' in pin and size != pin['bytes']):
            raise ValueError('search part differs from its manifest: %s' % part)
    if (target / 'MANIFEST.json').read_bytes() != manifest_raw:
        raise ValueError('search manifest changed during review')
    return dict(schema='FRANKIE_SEARCH_FINDINGS_V1', day=str(day), role=manifest['day_role'],
                findings=findings, manifest_sha256=digest(manifest_raw),
                status='source/arithmetic-checked candidates; existing scientific teachers retain scientific judgment',
                review=dict(rows_checked=checked, listed=listed,
                            checks=['exact source bytes', 'existing count margins', 'market signals/context roles'],
                            independent_observations_added=0, producer_sha256=digest(Path(__file__).read_bytes()),
                            search_reader_sha256=digest(Path(SEARCH.__file__).read_bytes()),
                            arithmetic_reader_sha256=digest(Path(EX.__file__).read_bytes())),
                rule='compatible older knowledge remains; no rarity gate, pooling or knowledge freeze')
