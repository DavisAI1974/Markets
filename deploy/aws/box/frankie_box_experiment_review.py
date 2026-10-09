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


def claim_searches(lesson, claim_id):
    """Preserved claims keep their actual evidence scope across partial correction chains."""
    operation = (lesson.get('knowledge_retest') or {}).get('claim_operations', {}).get(claim_id)
    return operation['searches'] if operation is not None else lesson['searches']


def _transition_operation(pin, lesson):
    """Read the actual frozen accumulated-teacher operation; never manufacture a successor."""
    inputs = json.loads(_read_pin(pin))
    if inputs.get('schema') == 'FRANKIE_STANDALONE_TEACHER_INPUTS_V1':
        selection = inputs['selection']
        doc = selection['doc']
        if (inputs['selection_sha256'] != _lesson_digest(selection)
                or doc['author'] != lesson['author'] or doc['claims_sha256'] != lesson['claims_sha256']
                or doc['claims'] != lesson['claim_inputs']['claims']):
            raise ValueError('standalone result differs from its frozen claim projection')
        return dict(kind='standalone', inputs={k: pin[k] for k in ('path', 'bytes', 'sha256')},
                    identity=inputs['identity'], selection_sha256=inputs['selection_sha256'],
                    claim_inputs_sha256=_lesson_digest(lesson['claim_inputs']),
                    claims_sha256=doc['claims_sha256'],
                    source=selection['source'], searches=selection['searches'],
                    reproduction_records=selection['reproduction_records'])
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


def _validate_operation(operation, lesson):
    """Check one completed accumulated result against its frozen owner operation."""
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
    if operation.get('kind') == 'standalone':
        expected_searches = [dict(day=s['day'], cycle=s['cycle'], dir=s['dir'],
                                  manifest_sha256=s['manifest']['sha256']) for s in operation['searches']]
        if (lesson.get('scientific_operation') != dict(inputs=pin, selection_sha256=operation['selection_sha256'])
                or lesson['claim_inputs_sha256'] != operation['claim_inputs_sha256']
                or claims['reader_sha256'] != identity['reader_sha256']
                or lesson['claims_sha256'] != operation['claims_sha256']
                or lesson['searches'] != expected_searches or lesson['day'] != identity['day']
                or lesson.get('results_sha256') != _lesson_digest(lesson['results'])):
            raise ValueError('standalone result differs from its exact frozen operation')
        return
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


def _validate_transition(transition, before, after, publication):
    """Check the transported owner binding without exposing private frozen selections."""
    if (not isinstance(transition, dict) or transition.get('schema') != TRANSITION_SCHEMA
            or transition.get('owner') not in ('frankie_box_teacher_knowledge.teach_accumulated',
                                               'frankie_box_scientific_teacher')):
        raise ValueError('changed claim inputs require an explicit supported scientific-owner transition')
    operations = []
    for name, lesson in (('original', before), ('replacement', after)):
        operation = transition[name]
        _validate_operation(operation, lesson)
        operations.append(operation)
    if transition['owner'] == 'frankie_box_scientific_teacher':
        if (any(o.get('kind') != 'standalone' for o in operations)
                or operations[0]['identity']['brain'] != operations[1]['identity']['brain']
                or operations[0]['inputs'] == operations[1]['inputs']
                or operations[0]['inputs']['sha256'] == operations[1]['inputs']['sha256']
                or operations[0]['inputs']['path'] == operations[1]['inputs']['path']
                or publication['day'] not in [s['day'] for s in operations[1]['searches']]):
            raise ValueError('standalone correction requires distinct frozen operations on its publishing owner')
        ids = [r['claim_id'] for r in before['results']]
        affected = transition.get('affected_claim_ids')
        if (not isinstance(affected, list) or not affected or len(set(affected)) != len(affected)
                or [i for i in ids if i in affected] != affected
                or [r['claim_id'] for r in after['results']] != ids):
            raise ValueError('standalone correction needs explicit affected claim identities')
        for old_claim, claim, old_result, result in zip(before['claim_inputs']['claims'],
                                                       after['claim_inputs']['claims'], before['results'], after['results']):
            if old_claim['id'] not in affected and (old_claim != claim or old_result != result):
                raise ValueError('standalone correction changed an unaffected claim/result')
        request = operations[1]['identity'].get('successor')
        if request is not None:
            if (request['original_inputs'] != operations[0]['inputs']
                    or operations[1]['identity'].get('owner_day') != publication['day']
                    or request.get('affected_claim_ids', ids) != affected):
                raise ValueError('standalone successor changed its original request or owning publication day')
            if [s['day'] for s in operations[0]['searches']] != [s['day'] for s in operations[1]['searches']]:
                raise ValueError('standalone successor must preserve its original ordered search scope')
            for old_search, search in zip(operations[0]['searches'], operations[1]['searches']):
                replacement_search = request.get('replacement_search')
                if old_search != search and (search['day'] != publication['day'] or not replacement_search
                        or search['manifest'] != replacement_search
                        or Path(search['dir']) / 'MANIFEST.json' != Path(replacement_search['path'])):
                    raise ValueError('standalone successor changed a search outside its explicit owner replacement')
            if operations[0]['reproduction_records'] != operations[1]['reproduction_records']:
                raise ValueError('standalone successor changed its frozen reproduction selection')
            if before.get('reconsideration') != after.get('reconsideration'):
                raise ValueError('standalone successor changed original historical collection context')
            origin = (before.get('knowledge_retest') or {}).get('reconsideration_origin')
            if before.get('reconsideration') is not None and before['claims_sha256'] != after['claims_sha256'] and origin is None:
                collection = before['reconsideration']
                if collection['claims_file_sha256'] != before['claims_sha256']:
                    raise ValueError('original standalone collection lacks its claims binding')
                origin = dict(claims_sha256=collection['claims_file_sha256'], result=request['original_result'])
            if (after.get('knowledge_retest') or {}).get('reconsideration_origin') != origin:
                raise ValueError('standalone successor changed original historical collection provenance')
            projection = request.get('replacement_claims')
            if (before['claim_inputs']['claims'] != after['claim_inputs']['claims']
                    or before['claims_sha256'] != after['claims_sha256']):
                if projection is None or operations[1]['source'] != projection:
                    raise ValueError('standalone changed claims need the exact explicit replacement projection')
            elif operations[0]['source'] != operations[1]['source'] and projection is None:
                raise ValueError('standalone successor changed its original claim source silently')
            expected = {i: (dict(input_sha256=operations[1]['inputs']['sha256'], searches=after['searches']) if i in affected else
                           dict(inputs=request['original_inputs'], result=request['original_result'],
                                searches=claim_searches(before, i))) for i in ids}
            if (after.get('knowledge_retest') or {}).get('claim_operations') != expected:
                raise ValueError('standalone successor lost exact recomputed/preserved claim provenance')
        return
    if any(o.get('kind') == 'standalone' for o in operations):
        raise ValueError('mixed standalone/accumulated correction owners are not interchangeable')
    if (operations[0]['identity']['brain'] != operations[1]['identity']['brain']
            or operations[0]['identity']['day'] != operations[1]['identity']['day']
            or operations[1]['identity']['day'] != publication['day']
            or operations[0]['inputs']['sha256'] == operations[1]['inputs']['sha256']
            or operations[0]['inputs']['path'] == operations[1]['inputs']['path']):
        raise ValueError('correction successor needs a distinct retained operation on the same owner day/brain')
    request = operations[1]['identity'].get('successor')
    if not request and (before['claim_inputs']['claims'] != after['claim_inputs']['claims']
                        or before['claims_sha256'] != after['claims_sha256']
                        or any(operations[0]['identity'][k] != operations[1]['identity'][k]
                               for k in ('search', 'manifest'))):
        raise ValueError('changed claims/search require an explicit successor request')
    if request:
        if request['original_inputs'] != operations[0]['inputs']:
            raise ValueError('successor did not name this original frozen operation')
        collection = before.get('reconsideration')
        expected_origin = (before.get('knowledge_retest') or {}).get('reconsideration_origin')
        if collection is not None:
            if after.get('reconsideration') != collection:
                raise ValueError('successor changed the retained original collection context')
            if expected_origin is None and before['claims_sha256'] != after['claims_sha256']:
                if collection['claims_file_sha256'] != before['claims_sha256']:
                    raise ValueError('original collection lacks its claims binding')
                expected_origin = dict(claims_sha256=collection['claims_file_sha256'],
                                       result={k: request['original_result'][k] for k in ('path', 'bytes', 'sha256')})
        if after['knowledge_retest'].get('reconsideration_origin') != expected_origin:
            raise ValueError('successor changed the original collection provenance')
        ids = [r['claim_id'] for r in before['results']]
        affected = request.get('affected_claim_ids', ids)
        if (not affected or len(set(affected)) != len(affected)
                or [i for i in ids if i in affected] != affected):
            raise ValueError('successor affected identities differ from the original lesson')
        if [r['claim_id'] for r in after['results']] != ids:
            raise ValueError('successor must retain the original ordered claim identities')
        for old_claim, claim, old_result, result in zip(before['claim_inputs']['claims'],
                                                       after['claim_inputs']['claims'],
                                                       before['results'], after['results']):
            if old_claim['id'] not in affected and (old_claim != claim or old_result != result):
                raise ValueError('successor changed an unaffected claim or its completed result')
        provenance = after['knowledge_retest'].get('claim_operations')
        if provenance is not None:
            expected = {i: (dict(input_sha256=operations[1]['inputs']['sha256'], searches=after['searches']) if i in affected else
                            dict(inputs=request['original_inputs'], result=request['original_result'],
                                 searches=claim_searches(before, i))) for i in ids}
            if provenance != expected:
                raise ValueError('successor claim provenance differs from its recomputed/preserved partition')
        elif affected != ids:
            raise ValueError('partial successor lacks per-claim original operation bindings')
        old_claims, new_claims = before['claim_inputs']['claims'], after['claim_inputs']['claims']
        if old_claims != new_claims or before['claims_sha256'] != after['claims_sha256']:
            projection = request.get('replacement_claims')
            if not projection or operations[1]['source_lesson_sha256'] != projection['sha256']:
                raise ValueError('changed claims require an explicit frozen replacement projection')
        if any(operations[0]['identity'][k] != operations[1]['identity'][k] for k in ('search', 'manifest')):
            search = request.get('replacement_search')
            if (not search or {k: search[k] for k in ('bytes', 'sha256')} != operations[1]['identity']['manifest']
                    or Path(search['path']) != Path(operations[1]['identity']['search']) / 'MANIFEST.json'):
                raise ValueError('changed search requires the exact replacement manifest binding')


def _exchange_digest(value):
    # The exchange's existing canonical encoding includes literal Unicode.
    return digest(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                             allow_nan=False).encode('utf-8'))


def _exchange_sources(receipt, records):
    """Validate only the declared source chains, even when later corrections now exist."""
    supplied = receipt['source_corrections']
    by_hash = {record['record']['sha256']: record for record in records.values()}
    if (not supplied or len({pin['sha256'] for pin in supplied}) != len(supplied)
            or any(pin['sha256'] not in by_hash or pin['bytes'] != by_hash[pin['sha256']]['record']['bytes']
                   for pin in supplied)):
        raise ValueError('exchange source correction is absent from checked owner knowledge')
    selected = {by_hash[pin['sha256']]['original']['sha256']: by_hash[pin['sha256']] for pin in supplied}
    if any(record['body']['written_by'] != 'scientific_teacher' for record in selected.values()):
        raise ValueError('exchange source correction must replace a checked scientific lesson')
    consumed = set()
    for pair in receipt['operation']['documents']:
        old, new = pair['original'], pair['replacement']
        if any(old.get(key) != new.get(key) for key in ('schema', 'author', 'source_id', 'accumulated')):
            raise ValueError('exchange rebuild changed an original lesson slot or blind-wall status')
        cursor = old['sha256']
        seen = set()
        while cursor in selected:
            if cursor in seen:
                raise ValueError('exchange source correction cycle')
            seen.add(cursor)
            consumed.add(cursor)
            cursor = selected[cursor]['replacement']['sha256']
        if cursor != new['sha256'] or (not seen and old != new):
            raise ValueError('exchange source replacement is not its declared checked chain')
    if consumed != set(selected):
        raise ValueError('exchange rebuild supplied an unrelated source correction')
    return consumed


def _exchange_source_ancestry(receipt, records):
    """The declared scientific links and their earlier source ancestry, never later replacements."""
    ancestors = _exchange_sources(receipt, records)
    while True:
        earlier = {sha for sha, record in records.items()
                   if record['body']['written_by'] == 'scientific_teacher'
                   and record['replacement']['sha256'] in ancestors} - ancestors
        if not earlier:
            return ancestors
        ancestors.update(earlier)


def _exchange_wall(view):
    sources = view['sources']['lessons']
    for item in view['items']:
        matches = [source for source in sources if source['sha256'] == item['lessons']['sha256']
                   and source['path'] == item['lessons']['path']
                   and source['author'] == item['author']
                   and bool(source.get('accumulated')) == item['lessons']['accumulated']]
        blind = item['author'] == 'jev' and not item['lessons']['accumulated']
        if not matches or item['blind_jev'] != blind or (view['view'] == 'frankie' and blind):
            raise ValueError('exchange result changed its selected lesson identity or Jev wall')
    for context in view['lesson_contexts']:
        source = context['source']
        blind = source['author'] == 'jev' and not source.get('accumulated')
        if source not in sources or context['blind_jev'] != blind or (view['view'] == 'frankie' and blind):
            raise ValueError('exchange lesson context crossed its selected source or Jev wall')


def _validate_exchange_correction(body, before, after):
    """Transported binding for a deterministic exchange rebuilt from checked lesson corrections."""
    receipt = body['exchange_transition']
    operation = receipt['operation']
    if (receipt.get('schema') != 'FRANKIE_EXCHANGE_SUCCESSOR_RECEIPT_V1'
            or receipt.get('status') != 'complete'
            or receipt.get('owner') != 'frankie_box_experiment_exchange.exchange'
            or operation.get('schema') != 'FRANKIE_EXCHANGE_SUCCESSOR_OPERATION_V1'
            or receipt.get('operation_sha256') != digest(canonical(operation))
            or body['decision'] != 'checked_dependency_rebuild' or body['scopes'] != [[]]
            or body['written_by'] != 'teacher_exchange'
            or body['publication'] != dict(day=receipt['day'], stage='exchange')
            or receipt['original_view'] != body['original'] or receipt['frankie_view'] != body['replacement']
            or any(before.get(k) != after.get(k) for k in ('schema', 'view', 'day', 'run', 'rules'))
            or before.get('schema') != 'FRANKIE_EXPERIMENT_EXCHANGE_V1' or before.get('view') != 'frankie'
            or before['day'] != operation['day'] or before['run'] != operation['run']
            or any(receipt.get(key) != operation.get(key) for key in
                   ('day', 'run', 'brain', 'original_inputs', 'original_view', 'source_corrections'))
            or before['rules'] != operation['rules'] or not operation['source_corrections']
            or receipt['source_corrections'] != operation['source_corrections']
            or before['sources']['teacher_rows'] != after['sources']['teacher_rows']
            or before['sources']['teacher_rows_listed'] != after['sources']['teacher_rows_listed']
            or before['sources']['lessons'] != [p['original'] for p in operation['documents']]
            or after['sources']['lessons'] != [p['replacement'] for p in operation['documents']]
            or any(view['knowledge_inputs'].get(k) != receipt[field][k]
                   for view, field in ((before, 'original_inputs'), (after, 'replacement_inputs'))
                   for k in ('path', 'sha256'))
            or any(view['knowledge_inputs']['sources'] != view['sources']['lessons'] for view in (before, after))
            or any(view.get('exchange_hash') != _exchange_digest({k: v for k, v in view.items()
                                                                 if k != 'exchange_hash'}) for view in (before, after))
            or receipt.get('model_calls') != 0 or receipt.get('scientific_retests') != 0):
        raise ValueError('exchange correction differs from its exact retained owner rebuild')
    pins = [receipt[field] for field in ('original_inputs', 'original_view', 'replacement_inputs', 'full', 'frankie_view')]
    for pin in pins + receipt['source_corrections']:
        if (not isinstance(pin.get('path'), str) or not pin['path'] or type(pin.get('bytes')) is not int
                or pin['bytes'] < 0 or not re.fullmatch('[0-9a-f]{64}', str(pin.get('sha256')))):
            raise ValueError('exchange transition lacks a complete artifact witness')
    if (receipt['original_inputs']['path'] == receipt['replacement_inputs']['path']
            or receipt['original_inputs']['sha256'] == receipt['replacement_inputs']['sha256']
            or before['knowledge_inputs']['versions'] != after['knowledge_inputs']['versions']):
        raise ValueError('exchange successor must retain its original knowledge version selection in a new operation')
    if before == after:
        raise ValueError('exchange correction has no changed dependency/result')
    _exchange_wall(after)


def _validate_exchange_inputs(receipt, before, after, brain, records):
    """Owner-side frozen selection and full/blind projection checks; no exchange math runs."""
    _exchange_sources(receipt, records)
    old = json.loads(_read_pin(receipt['original_inputs']))
    new = json.loads(_read_pin(receipt['replacement_inputs']))
    full = json.loads(_read_pin(receipt['full']))
    operation = receipt['operation']
    old_id, new_id = old['identity'], new['identity']
    expected_identity = dict(old_id, producer_sha256=operation['producer_sha256'],
                             reader_sha256=operation['reader_sha256'], successor_operation=operation)
    if (Path(receipt['brain']).resolve() != Path(brain).resolve()
            or old.get('schema') != 'FRANKIE_EXCHANGE_KNOWLEDGE_INPUTS_V1'
            or new_id != expected_identity
            or any(old_id.get(k) != operation[k] for k in ('day', 'run', 'brain', 'teacher_rows', 'rules'))
            or [source for _, source in old['documents']] != before['sources']['lessons']
            or [source for _, source in new['documents']] != after['sources']['lessons']
            or len(old['documents']) != len(new['documents'])
            or {k: v for k, v in old.items() if k not in ('identity', 'documents', 'claims_by_source')}
               != {k: v for k, v in new.items() if k not in ('identity', 'documents', 'claims_by_source')}):
        raise ValueError('exchange successor changed its original owner or complete frozen selection')
    expected_claims = {}
    for (lesson, source), (successor, next_source) in zip(old['documents'], new['documents']):
        delivered = current_document(dict(source, content=lesson), records, brain,
                                     day=operation['day'], stage='exchange')
        expected_source = dict(source)
        projection = old['claims_by_source'][source['source_id']]
        if delivered['sha256'] != source['sha256']:
            checked = delivered['content']
            expected_source.update({k: delivered[k] for k in ('path', 'bytes', 'sha256')})
            searches = [s for result in checked['results'] for s in claim_searches(checked, result['claim_id'])]
            days = (sorted({str(s['day']) for s in searches}) if (checked.get('knowledge_retest') or {}).get('claim_operations')
                    else sorted(str(s['day']) for s in checked.get('searches') or []))
            expected_source.update(schema=checked['schema'], author=checked['author'], day=checked.get('day'),
                stamp=checked.get('stamp'), days_tested=days, claims_sha256=checked.get('claims_sha256'),
                claims_source=checked.get('claims_source'))
            if 'container_sha256' in expected_source:
                expected_source.update(container_sha256=delivered['sha256'], address=[])
            if checked.get('claim_inputs') != lesson.get('claim_inputs'):
                claims = checked.get('claim_inputs') or {}
                if (claims.get('schema') != 'FRANKIE_SCIENTIFIC_CLAIM_INPUTS_V1'
                        or claims.get('author') != checked['author']
                        or claims.get('claims_sha256') != checked['claims_sha256']
                        or _lesson_digest(claims) != checked.get('claim_inputs_sha256')
                        or [c['id'] for c in claims['claims']] != [r['claim_id'] for r in checked['results']]):
                    raise ValueError('exchange successor changed claims without their checked complete projection')
                projection = dict(claims={c['id']: c for c in claims['claims']}, listed=None)
            elif checked.get('claims_sha256') != lesson.get('claims_sha256'):
                raise ValueError('exchange successor changed its claim source without its legal projection')
        if successor != delivered['content'] or next_source != expected_source:
            raise ValueError('exchange successor document differs from its exact checked replacement')
        expected_claims[source['source_id']] = projection
    if new['claims_by_source'] != expected_claims:
        raise ValueError('exchange successor changed an uncorrected frozen claim projection')
    require_current([dict(source, content=lesson) for lesson, source in new['documents']], records)
    for pin in receipt['source_corrections']:
        _read_pin(pin)
    if (full.get('schema') != before['schema'] or full.get('view') != 'full'
            or full.get('day') != operation['day'] or full.get('run') != operation['run']
            or full.get('rules') != operation['rules'] or full.get('sources') != after['sources']
            or full.get('knowledge_inputs') != after['knowledge_inputs']
            or full.get('exchange_hash') != _exchange_digest({k: v for k, v in full.items() if k != 'exchange_hash'})
            or after.get('full_exchange_hash') != full['exchange_hash']):
        raise ValueError('exchange successor full artifact differs from its learner-view binding')
    _exchange_wall(full)
    if [context['source'] for context in full['lesson_contexts']] != full['sources']['lessons']:
        raise ValueError('exchange full artifact lost a selected lesson context')
    hidden = {item['item_id'] for item in full['items'] if item['blind_jev']}
    expected_view = dict(full, view='frankie', items=[i for i in full['items'] if not i['blind_jev']],
        lesson_contexts=[c for c in full['lesson_contexts'] if not c['blind_jev']],
        teachers_findings=[f for f in full['teachers_findings'] if f['from_item'] not in hidden],
        jev_withheld=dict(items=len(hidden), findings=sum(f['from_item'] in hidden for f in full['teachers_findings']),
                          reason=before['jev_withheld']['reason']), full_exchange_hash=full['exchange_hash'])
    expected_view.pop('exchange_hash')
    expected_view['exchange_hash'] = _exchange_digest(expected_view)
    if after != expected_view:
        raise ValueError('exchange successor learner view differs from the full artifact blind-wall projection')


def _validate_school_correction(body, before, after):
    receipt = body['school_transition']
    operation = receipt['operation']
    if (receipt.get('schema') != 'FRANKIE_SCHOOL_SUCCESSOR_RECEIPT_V1'
            or receipt.get('status') != 'complete'
            or receipt.get('owner') != 'frankie_box_school_knowledge.rebuild_successor'
            or operation.get('schema') != 'FRANKIE_SCHOOL_SUCCESSOR_OPERATION_V1'
            or receipt.get('operation_sha256') != digest(canonical(operation))
            or body['decision'] != 'checked_dependency_rebuild' or body['scopes'] != [[]]
            or body['written_by'] != 'school' or body['publication'] != dict(day=operation['day'], stage='school')
            or receipt['original_school'] != body['original'] or receipt['school'] != body['replacement']
            or receipt['original_school'] != operation['original_school']
            or receipt['source_corrections'] != operation['source_corrections']
            or not receipt['source_corrections'] or before == after
            or before.get('schema') != 'FRANKIE_SCHOOL_KNOWLEDGE_V1'
            or any(before.get(k) != after.get(k) for k in before if k != 'sections')
            or set(before) != set(after) or before['day'] != operation['day'] or before['run'] != operation['run']
            or receipt.get('model_calls') != 0 or receipt.get('scientific_retests') != 0):
        raise ValueError('school correction differs from its exact retained owner rebuild')
    for pin in [receipt['original_school'], receipt['school']] + receipt['source_corrections']:
        if (not isinstance(pin.get('path'), str) or not pin['path'] or type(pin.get('bytes')) is not int
                or pin['bytes'] < 0 or not re.fullmatch('[0-9a-f]{64}', str(pin.get('sha256')))):
            raise ValueError('school correction lacks an exact artifact witness')


def _school_sources(receipt, records):
    """Resolve this operation's declared checked links, never corrections published later."""
    supplied = receipt['source_corrections']
    by_hash = {r['record']['sha256']: r for r in records.values()}
    if (len({p['sha256'] for p in supplied}) != len(supplied)
            or any(p['sha256'] not in by_hash or p['bytes'] != by_hash[p['sha256']]['record']['bytes'] for p in supplied)):
        raise ValueError('school rebuild source is absent from checked owner knowledge')
    selected = {by_hash[p['sha256']]['original']['sha256']: by_hash[p['sha256']] for p in supplied}
    if any(r['body']['written_by'] not in ('scientific_teacher', 'teacher_exchange') for r in selected.values()):
        raise ValueError('school rebuild needs checked scientific/exchange sources')
    return selected


def _school_source_ancestry(receipt, records):
    selected = _school_sources(receipt, records)
    ancestors = set(selected)
    for record in selected.values():
        transition = record['body'].get('exchange_transition')
        if transition is not None:
            ancestors.update(_exchange_source_ancestry(transition, records))
    while True:
        earlier = {sha for sha, record in records.items()
                   if record['replacement']['sha256'] in ancestors} - ancestors
        if not earlier:
            return ancestors
        ancestors.update(earlier)


def _validate_school_inputs(receipt, before, after, records, brain=None):
    import frankie_box_school_knowledge as SK
    selected = _school_sources(receipt, records)
    meeting = None
    if receipt['operation']['meeting_receipt'] is not None:
        meetings = [i for i in after['sections']['exchange']['items'] if i['name'] == 'discussion (meeting)']
        if len(meetings) != 1:
            raise ValueError('school successor lost its complete replacement discussion')
        meeting = meetings[0]
    expected, consumed = SK._successor_projection(before, selected, meeting)
    if expected != after or consumed != {p['sha256'] for p in receipt['source_corrections']}:
        raise ValueError('school successor changed unaffected knowledge or its exact source selection')
    if brain is not None:
        import frankie_box_brain as BR
        operation = receipt['operation']
        if Path(operation['brain']).resolve() != Path(brain).resolve():
            raise ValueError('school successor belongs to another brain owner')
        owned = [row for row in BR._school_index(brain)['rows']
                 if row['day'] == operation['day'] and row['run'] == operation['run']]
        if len(owned) != 1:
            raise ValueError('school successor lacks its original owner index row')
        cursor = owned[0]['sha256']
        while cursor in records:
            cursor = records[cursor]['replacement']['sha256']
        if cursor != receipt['original_school']['sha256']:
            raise ValueError('school successor does not extend its indexed owner chain')
        if meeting is not None:
            views = [i for i in after['sections']['exchange']['items'] if i['name'] == 'exchange_frankie_view']
            if len(views) != 1:
                raise ValueError('school successor lost its owning exchange')
            # Publication requires the actual model completion on its owner, not a copied digest.
            source = next(r['body']['replacement'] for r in selected.values()
                          if r['replacement']['sha256'] == views[0]['source_sha256'])
            found = BR.read_meeting_for_exchange(source['path'])
            if (found['status'] != 'complete' or found['record'] != meeting['content']
                    or found['path'] != meeting['path']
                    or any(found['receipt']['record'][k] != meeting[k] for k in ('bytes', 'sha256'))
                    or json.loads(_read_pin(operation['meeting_receipt'])) != found['receipt']):
                raise ValueError('school successor discussion differs from its completed owner receipt')
        for section in after['sections'].values():
            for item in section['items']:
                if item.get('inline'):
                    current_document(item, records, brain, day=operation['day'], stage='school')


def _validate_correction(body, before, after):
    """Validate a declared scientific-owner decision, not decide whether the science is true."""
    if body.get('school_transition') is not None:
        if body.get('schema') != SCHEMA or not body.get('reason') or not body.get('evidence'):
            raise ValueError('school correction requires its checked source evidence')
        _validate_school_correction(body, before, after)
        return
    if body.get('exchange_transition') is not None:
        if body.get('schema') != SCHEMA or not body.get('reason') or not body.get('evidence'):
            raise ValueError('exchange correction requires its checked source evidence')
        _validate_exchange_correction(body, before, after)
        return
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
    for key in ('schema', 'author', 'day'):
        if before.get(key) != after.get(key):
            raise ValueError('correction changes the original lesson subject: ' + key)
    transition = body.get('owner_transition')
    changed_inputs = any(before.get(key) != after.get(key) for key in (
        'claim_inputs', 'claim_inputs_sha256', 'searches', 'scientific_operation', 'knowledge_retest'))
    if changed_inputs or transition is not None:
        _validate_transition(transition, before, after, publication)
    if before.get('claims_sha256') != after.get('claims_sha256') and not (
            transition and (transition.get('owner') == 'frankie_box_scientific_teacher'
                            or transition['replacement']['identity'].get('successor', {}).get('replacement_claims'))):
        raise ValueError('changed claim source requires an explicit owner projection transition')
    if transition and transition['replacement']['identity'].get('successor'):
        request = transition['replacement']['identity']['successor']
        if body.get('original') is not None and {k: request['original_result'][k] for k in ('path', 'bytes', 'sha256')} != body['original']:
            raise ValueError('owner transition corrected another original result')
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
                      owner_transition=None, exchange_transition=None, school_transition=None):
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
    from frankie_box_durable import write_json, write_bytes, witness
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
    if sum(value is not None for value in (owner_transition, exchange_transition, school_transition)) > 1:
        raise ValueError('one correction cannot have two computation owners')
    if school_transition is not None:
        receipt = json.loads(_read_pin(school_transition['receipt']))
        body.update(written_by='school', school_transition=receipt,
                    publication=dict(day=str(publication_day), stage='school'))
    if exchange_transition is not None:
        if owner_transition is not None:
            raise ValueError('one correction cannot have two computation owners')
        receipt = json.loads(_read_pin(exchange_transition['receipt']))
        body.update(written_by='teacher_exchange', exchange_transition=receipt,
                    publication=dict(day=str(publication_day), stage='exchange'))
    if owner_transition is not None:
        original_operation = _transition_operation(owner_transition['original_inputs'], before)
        body['owner_transition'] = dict(schema=TRANSITION_SCHEMA,
            owner=('frankie_box_scientific_teacher' if original_operation.get('kind') == 'standalone'
                   else 'frankie_box_teacher_knowledge.teach_accumulated'),
            original=original_operation,
            replacement=_transition_operation(owner_transition['replacement_inputs'], after))
        if original_operation.get('kind') == 'standalone':
            body['owner_transition']['affected_claim_ids'] = owner_transition.get('affected_claim_ids')
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
        if exchange_transition is not None or school_transition is not None:
            import frankie_box_lane_state as LS
            existing = corrections(LS.knowledge_roots(brain))
        else:
            existing = corrections([brain])
        legal = {e.get('sha256') for _, m, _ in BR.entries_before(brain, 'snapshot')
                 for e in m.get('entries', []) if e.get('include')}
        legal.update(r['body']['replacement']['sha256'] for r in existing.values())
        if school_transition is not None:
            legal.update(r['sha256'] for r in BR._school_index(brain)['rows']
                         if r['day'] == str(publication_day) and r['run'] == before['run'])
        if original['sha256'] not in legal:
            raise ValueError('correction original is not published learner knowledge')
        prior = existing.get(original['sha256'])
        if prior and prior['body'] != body:
            raise ValueError('competing correction needs research; never select by recency')
        if exchange_transition is not None or school_transition is not None:
            if prior is None:
                if school_transition is not None:
                    _validate_school_inputs(receipt, before, after, existing, brain)
                else:
                    _validate_exchange_inputs(receipt, before, after, brain, existing)
            # A transported exchange must carry the exact scientific decisions it uses.
            # Preserve original owner bodies/bytes and only their public lesson objects;
            # private frozen selections, evidence and the full Jev exchange stay owner-local.
            ancestry = (_school_source_ancestry(receipt, existing) if school_transition is not None
                        else _exchange_source_ancestry(receipt, existing))
            for sha in sorted(ancestry):
                source = existing[sha]
                for item in (source['original'], source['replacement']):
                    _save_object(brain, _read_pin(item))
                source_raw = _read_pin(source['record'])
                source_path = directory / (digest(canonical(source['body'])) + '.json')
                if source_path.exists():
                    if source_path.read_bytes() != source_raw:
                        raise ValueError('retained source correction differs from its exact transported bytes')
                else:
                    write_bytes(source_path, source_raw)
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
    for record in found.values():
        if record['body'].get('exchange_transition') is not None:
            _exchange_sources(record['body']['exchange_transition'], found)
        if record['body'].get('school_transition') is not None:
            _validate_school_inputs(record['body']['school_transition'],
                json.loads(_read_pin(record['original'])), json.loads(_read_pin(record['replacement'])), found)
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
    source_ancestors = set()
    for original in records:
        cursor = original
        path = []
        while cursor in records:
            path.append(records[cursor])
            cursor = records[cursor]['replacement']['sha256']
            if cursor == sha:
                ancestors.add(original)
                for record in path:
                    transition = record['body'].get('exchange_transition')
                    if transition is not None:
                        source_ancestors.update(_exchange_source_ancestry(transition, records))
                    school_transition = record['body'].get('school_transition')
                    if school_transition is not None:
                        source_ancestors.update(_school_source_ancestry(school_transition, records))
                break
    # Only provenance of the exact checked source links used by this rebuilt exchange
    # is exempt. A later correction to their replacements is still a stale dependency.
    ancestors.update(source_ancestors)
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
    for sha in _ancestors(result['sha256'], records) - ancestors:
        publication = records[sha]['body']['publication']
        if str(day) == publication['day'] and stage in ('root', 'teacher', 'classroom', 'search'):
            raise ValueError('corrected lesson is beyond this day answer boundary')
        ancestors.add(sha)
        applied.append(records[sha]['record'])
    content = result['content']
    schema = content.get('schema') if isinstance(content, dict) else None
    changed = False
    # Transform ONLY explicit copied-source containers, never computed result structures.
    if schema == 'FRANKIE_SCHOOL_KNOWLEDGE_V1':
        # The school owner alone replaces copied sources, projections and discussions.
        # A reader cannot repair the container merely by rewriting its nested hashes.
        for section in content['sections'].values():
            for item in section['items']:
                if item.get('source_sha256') in records:
                    raise ValueError('school projected source changed; explicit owner school successor required')
                if item.get('inline') and item.get('sha256'):
                    corrected = current_document(item, records, brain, day=day, stage=stage)
                    if corrected['sha256'] != item['sha256']:
                        raise ValueError('school source changed; explicit owner school successor required')
                    applied.extend(corrected.get('corrections_applied') or [])
                elif item.get('sha256') in records:
                    raise ValueError('school pointer changed; explicit owner school successor required')
    elif schema == 'FRANKIE_SURVIVOR_UPDATE_V1':
        # The survivor/candidate update (frankie_box_survivor_update) is derived from lessons files it cites by sha256.
        # Its checked successor is the NEXT boundary update (which consumes the corrected lessons); until then the
        # document is delivered whole with each affected candidate marked explicitly (stale_sources, status_disposition)
        # rather than refused: a known status stays visible and distinguishable from a corrected one, and a later
        # classroom's day is never rejected for it (missing-coverage rule). Nothing is recomputed or relabelled.
        content = json.loads(json.dumps(content))
        pending = {}
        for candidate in content.get('candidates') or []:
            cited = set()
            for test in (candidate.get('tests') or []) + (candidate.get('own_day_evidence') or []) + \
                    (candidate.get('origin_evidence') or []) + (candidate.get('duplicates') or []):
                if test.get('lesson_sha256'):
                    cited.add(test['lesson_sha256'])
            for lesson in candidate.get('lessons') or []:
                if lesson.get('sha256'):
                    cited.add(lesson['sha256'])
            for known in candidate.get('previously_known') or []:
                if known.get('survivors_sha256'):
                    cited.add(known['survivors_sha256'])
            stale = sorted((cited & set(records)) - ancestors)
            if stale:
                candidate['stale_sources'] = [records[sha]['record'] for sha in stale]
                candidate['status_disposition'] = dict(
                    status='awaiting_next_boundary_update',
                    reason='a cited lessons file has a checked correction (%d); this status was computed on the earlier '
                           'bytes and is carried as previously known, not as current; the next survivor update consumes '
                           'the corrected lesson' % len(stale))
                for sha in stale:
                    pending[sha] = records[sha]['record']
                changed = True
        if changed:
            content['corrections_pending'] = sorted(pending.values(), key=lambda r: r['sha256'])
            content['corrections_pending_rule'] = ('candidates citing a corrected lesson are marked, never dropped or '
                                                   'recomputed here; the checked successor is the next boundary update')
            result.update(_save_object(brain, canonical(content)), content=content)
        else:
            stale = (references(content) & set(records)) - ancestors
            if stale:
                raise ValueError('survivor update cites a replaced source outside its candidates; checked successor required: '
                                 + ', '.join(sorted(stale)))
    elif schema == 'FRANKIE_STAGE_KNOWLEDGE_V1':
        content = json.loads(json.dumps(content))
        groups = [content.get('sources') or []]
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


def review_row(raw):
    """(reasons, row) of one stored coupling row's bytes: the field-role policy, the existing count arithmetic
    (frankie_box_experiment_exchange.count_margins) and the stored chance decision. One definition, used by the search
    worker as it writes the row (the part's review sidecar) and by search_findings on a part without one."""
    import frankie_box_experiment_search as SEARCH
    import frankie_box_experiment_exchange as EX
    row = json.loads(raw)
    if not isinstance(row, dict):
        raise ValueError('search evidence row is not an object')
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
    return reasons, row


def _part_review(target, pin):
    """(listed, findings, rows checked) of one part from its review sidecar (one pass, 2026-10-09): the part's pin from
    the MANIFEST plus a stat check (its size), the sidecar's own pin from the MANIFEST and its last line naming the
    part's bytes and sha256; None when the pin carries no sidecar or any of that differs (the part is then read whole
    as before)."""
    review = pin.get('review')
    if not isinstance(review, dict) or type(pin.get('bytes')) is not int:
        return None
    try:
        part = target / pin['path']
        side = target / review['path']
        if not side.resolve().is_relative_to(target.resolve()) or part.stat().st_size != pin['bytes']:
            return None
        raw = side.read_bytes()
        if len(raw) != review['bytes'] or digest(raw) != review['sha256']:
            return None
        lines = [json.loads(line) for line in raw.splitlines()]
        last = lines.pop()
        if (last.get('part_bytes'), last.get('part_sha256')) != (pin['bytes'], pin['sha256']):
            return None
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        return None
    listed, findings = [], []
    for entry in lines:
        source = dict(part=pin['path'], part_sha256=pin['sha256'], row=entry['row'], row_sha256=entry['row_sha256'])
        if 'reasons' in entry:
            listed.append(dict(source, reasons=entry['reasons'], disposition='needs_source_correction',
                               counts_as_independent_check=False))
        else:
            findings.append(dict(source, content=entry['content']))
    return listed, findings, last['rows_checked']


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
    findings, listed, checked, sidecars = [], [], 0, 0
    seen = set()
    for pin in manifest['couplings']['parts']:
        part = target / pin['path']
        if not part.resolve().is_relative_to(target.resolve()) or pin['path'] in seen:
            raise ValueError('ambiguous/outside search part in review')
        seen.add(pin['path'])
        # one pass (Greg, 2026-10-09): the search worker made these per-row checks as it wrote the part and saved them
        # beside it; with the part's MANIFEST pin, a stat check and the sidecar's own pin, the part is not read again
        sidecar = _part_review(target, pin)
        if sidecar is not None:
            listed.extend(sidecar[0])
            findings.extend(sidecar[1])
            checked += sidecar[2]
            sidecars += 1
            continue
        hashed, size = hashlib.sha256(), 0
        with part.open('rb') as handle:
            for ordinal, raw in enumerate(handle):
                hashed.update(raw)
                size += len(raw)
                try:
                    reasons, row = review_row(raw)
                except ValueError as error:
                    if 'not an object' in str(error):
                        raise ValueError('search evidence row is not an object: %s row %d' % (part, ordinal))
                    raise
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
                            parts_from_write_time_review=sidecars,
                            parts_read_whole=len(seen) - sidecars,
                            independent_observations_added=0, producer_sha256=digest(Path(__file__).read_bytes()),
                            search_reader_sha256=digest(Path(SEARCH.__file__).read_bytes()),
                            arithmetic_reader_sha256=digest(Path(EX.__file__).read_bytes())),
                rule='compatible older knowledge remains; no rarity gate, pooling or knowledge freeze')
