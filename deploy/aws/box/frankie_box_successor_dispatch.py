"""Owner-local Step 5 inbox and acknowledgment; the existing day loop owns execution.

Contracts: request = teach_successor's exact request; decision = {receipt, scopes, decision,
reason, evidence}. All receipts/evidence are path/bytes/sha256 witnesses. A request's content
address is its idempotency key. No dates choose winners, no scientific decision is inferred,
and no provider, worker or CPU booking is created here.
"""
import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import time

import frankie_box_durable as D
import frankie_box_experiment_review as R


SCHEMA = 'FRANKIE_SUCCESSOR_OPERATION_V1'


def pin(path):
    return dict(path=str(path), **D.witness(path))


def read(witness):
    return json.loads(R._read_pin(witness))


@contextmanager
def lock(path):
    path = Path(path)
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('successor path traverses a symbolic link')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def once(path, value):
    if path.exists():
        if read(pin(path)) != value:
            raise ValueError('retained successor intent differs: ' + str(path))
    else:
        D.write_json(path, value)
    return pin(path)


def owner(run, day):
    import frankie_box_experiment as X
    if not any(e['day'] == day for e in run.plan['days']):
        raise ValueError('successor day is outside its saved plan')
    if read(pin(run.dir / 'plan.json')) != run.plan:
        raise ValueError('successor owner plan changed')
    if run.remote_root(day):
        raise ValueError('successor belongs on the retained remote owner; no central dispatch')
    return dict(run=run.plan['run'], day=day, plan_sha256=X.plan_digest(run.plan),
                commit=run.commit, brain=str(run.plan.get('brain') or X.BRAIN))


def enqueue(run, day, request):
    """File an explicit owner request, idempotently. No scientific work or worker launch."""
    identity = owner(run, day)
    original = read(request['original_inputs'])
    standalone = original.get('schema') == 'FRANKIE_STANDALONE_TEACHER_INPUTS_V1'
    if original['identity']['brain'] != identity['brain'] or (not standalone and original['identity']['day'] != day):
        raise ValueError('successor request belongs to another scientific owner')
    search = run.receipt('search', day) or {}
    replacement_search = request.get('replacement_search')
    if standalone:
        owning = [s for s in original['selection']['searches'] if s['day'] == day]
        if len(owning) != 1:
            raise ValueError('standalone successor must name one of its exact original search days')
        original_search = owning[0]['dir']
        original_manifest = {k: owning[0]['manifest'][k] for k in ('bytes', 'sha256')}
    else:
        original_search, original_manifest = original['identity']['search'], original['identity']['manifest']
    selected_search = str(Path(replacement_search['path']).parent) if replacement_search else original_search
    selected_manifest = ({k: replacement_search[k] for k in ('bytes', 'sha256')} if replacement_search else original_manifest)
    if (search.get('status') not in ('done', 'reused') or search.get('target') != selected_search
            or D.witness(Path(search['target']) / 'MANIFEST.json') != selected_manifest):
        raise ValueError('successor request must use this run/day completed owning search')
    directory = run.dir / 'successors' / day
    body = dict(schema=SCHEMA, owner=identity, search=selected_search, request=request)
    key = R.digest(R.canonical(body))
    with lock(directory / 'inbox.lock'):
        path = directory / 'requests' / (key + '.json')
        if not path.exists():
            if (directory / 'closed.json').exists() or run.finished('jev', day):
                raise ValueError('completed owner boundary is closed; no implicit reopening of its day')
            for other in (directory / 'requests').glob('*.json'):
                if operation(other, identity)['request']['original_result']['sha256'] == request['original_result']['sha256']:
                    raise ValueError('another explicit successor already owns this original result: ' + other.stem)
            # Validate at intake, before an invalid request can block a day. Exact repeats
            # remain reusable even after their correction has replaced the original.
            import frankie_box_teacher_knowledge as TK
            import frankie_box_brain as BR
            if standalone:
                import frankie_box_scientific_teacher as ST
                ST.standalone_successor_inputs(day, selected_search, identity['brain'], request)
            else:
                TK._successor_document(request, dict(original['identity'], search=selected_search, manifest=selected_manifest),
                                       directory / 'intake' / 'inputs.json', R, BR)
        return dict(id=key, operation=once(path, body))


def operation(path, expected=None):
    value = read(pin(path))
    if (value.get('schema') != SCHEMA or path.stem != R.digest(R.canonical(value))
            or (expected is not None and value['owner'] != expected)):
        raise ValueError('successor request identity changed')
    return value


def submit_decision(run, day, key, decision):
    """File the scientific owner's decision only after its exact completed candidate exists."""
    identity = owner(run, day)
    if not isinstance(key, str) or len(key) != 64 or any(c not in '0123456789abcdef' for c in key):
        raise ValueError('successor id must be its full content hash')
    directory = run.dir / 'successors' / day
    value = operation(directory / 'requests' / (key + '.json'), identity)
    candidate = directory / 'work' / key / 'successor-receipt.json'
    if (set(decision) != {'receipt', 'scopes', 'decision', 'reason', 'evidence'}
            or decision['receipt'] != pin(candidate)):
        raise ValueError('checked decision must bind the exact retained successor receipt')
    completed = read(decision['receipt'])
    if completed['successor_request'] != value['request']:
        raise ValueError('checked decision names another successor request')
    before, after = read(value['request']['original_result']), read(completed['files'][0])
    original_operation = R._transition_operation(completed['owner_transition']['original_inputs'], before)
    standalone = original_operation.get('kind') == 'standalone'
    transition = dict(schema=R.TRANSITION_SCHEMA,
                      owner='frankie_box_scientific_teacher' if standalone else 'frankie_box_teacher_knowledge.teach_accumulated',
                      original=original_operation,
                      replacement=R._transition_operation(completed['owner_transition']['replacement_inputs'], after))
    if standalone:
        transition['affected_claim_ids'] = completed['owner_transition']['affected_claim_ids']
    for witness in decision['evidence']:
        R._read_pin(witness)
    R._validate_correction(dict(schema=R.SCHEMA, written_by='scientific_teacher',
                                publication=dict(day=day, stage='lessons'), owner_transition=transition,
                                **{k: decision[k] for k in ('scopes', 'decision', 'reason', 'evidence')}), before, after)
    with lock(directory / 'inbox.lock'):
        return once(directory / 'decisions' / (key + '.json'), decision)


def retry(run, day, key, failure):
    """Explicit retry of one recorded failure; the original request/output identity is retained."""
    identity = owner(run, day)
    if not isinstance(key, str) or len(key) != 64 or any(c not in '0123456789abcdef' for c in key):
        raise ValueError('successor id must be its full content hash')
    directory = run.dir / 'successors' / day
    operation(directory / 'requests' / (key + '.json'), identity)
    target = directory / 'work' / key
    with lock(directory / 'inbox.lock'):
        if failure != pin(target / 'failure.json'):
            raise ValueError('retry must name the exact current failed attempt')
        D.write_json(target / 'retry.json', dict(failure=failure))
        return pin(target / 'retry.json')


def control(run, day, saved):
    """Pause/resume this successor boundary, not the host or an unrelated day."""
    identity = owner(run, day)
    path = run.dir / 'successors' / day / 'control.json'
    with lock(path.with_suffix('.lock')):
        D.write_json(path, dict(owner=identity, saved=bool(saved)))
        return pin(path)


def status(run_dir):
    """Read-only pending/completed inventory; never dispatch from a status query."""
    rows = []
    for path in sorted((Path(run_dir) / 'successors').glob('*/requests/*.json')):
        value = operation(path)
        target = path.parent.parent / 'work' / path.stem
        state = read(pin(target / 'state.json')) if (target / 'state.json').exists() else {}
        if (target / 'ack.json').exists():
            acknowledgment(path, value)
        rows.append(dict(day=value['owner']['day'], id=path.stem,
                         status='done' if (target / 'ack.json').exists() else state.get('status', 'queued'),
                         operation=pin(path), reason=state.get('reason')))
    return rows


def acknowledgment(path, value):
    """Readback of the full request -> publication -> checked correction completion chain."""
    target = path.parent.parent / 'work' / path.stem
    saved = read(pin(target / 'ack.json'))
    published = read(saved['publication'])
    if (saved['operation'] != pin(path) or published['operation'] != pin(path)
            or published['correction'] != saved['correction']
            or published['decision'] != pin(path.parent.parent / 'decisions' / path.name)):
        raise ValueError('successor acknowledgment differs from its request/publication/decision')
    correction = read(saved['correction'])
    records = R.corrections([Path(value['owner']['brain'])])
    record = records.get(value['request']['original_result']['sha256'])
    if not record or record['body'] != correction or record['record'] != saved['correction']:
        raise ValueError('successor acknowledgment has no matching checked brain correction')
    if saved.get('dependents') != pin(target / 'dependents.json'):
        raise ValueError('successor acknowledgment lacks its exact completed dependent receipt')
    dependent_receipt(path, value)
    return pin(target / 'ack.json')


def recover_sync(brain):
    """Finish an interrupted knowledge acknowledgment before changing its snapshot payload."""
    config = os.environ.get('FRANKIE_LANE_MAILBOX')
    if not config:
        return
    pending = Path(config).with_name('rpc-pending.json')
    prior = read(pin(pending)) if pending.exists() else {}
    if not prior.get('waiting'):
        return
    if (prior.get('body') or {}).get('op') != 'sync':
        raise ValueError('another lane operation must be recovered by its owner before successor dispatch')
    import frankie_box_lane_state as LS
    recovered = LS.recover_request()
    for document in recovered['result'].get('knowledge', []):
        if document['owner'] != os.environ['FRANKIE_LANE_OWNER']:
            LS.merge_snapshot(document, brain=brain)


def close_day(run, day):
    """Serialize final acknowledgment with intake; late requests cannot reopen a completed day.

    One drain, then the inbox is read under its lock: every request acknowledged = the day closed (the closed.json pin,
    as before). A request still unacknowledged when the drain returns (the waiting_school branch breaks out of a
    waiting owner school recovery, or a second waiting_school after a complete one in the same drain call; a request
    admitted during the drain) is NOT looped on here: the result is
    {'status': 'waiting', 'pending': [...], ...} naming them, and the caller (the queue's _finish_day) records the day
    waiting and lets its slot go; the next worker start drains again (CCode, Step 8, on the parent's assignment of
    2026-10-07: the previous loop re-entered the drain without a pause, holding the finish thread). The drain's own
    in-request waits (a failed child awaiting its named retry, a candidate awaiting the scientific-owner decision, a
    save) are unchanged: they poll inside drain with their state recorded on the day's successors receipt."""
    directory = run.dir / 'successors' / day
    completed = drain(run, day)
    with lock(directory / 'inbox.lock'):
        requests = sorted((directory / 'requests').glob('*.json'))
        pending = [p.name for p in requests if not (directory / 'work' / p.stem / 'ack.json').is_file()]
        if pending or len(completed) != len(requests):
            return dict(status='waiting', acknowledged=len(completed), requests=len(requests), pending=pending,
                        reason='%d of %d successor request(s) of the day unacknowledged after this drain (%s); the day is '
                               'not closed; drained again at the next start' % (
                                   len(pending), len(requests), ', '.join(pending) or 'the inbox changed during the drain'))
        return once(directory / 'closed.json', dict(owner=owner(run, day), acknowledgments=completed))


def prepare_dependents(run, day, value, target, correction):
    """Freeze exact dependent inputs before rebuilding, publishing or invalidating anything."""
    import frankie_box_lane_state as LS
    path = target / 'dependents-intent.json'
    operation_path = target.parent.parent / 'requests' / (target.name + '.json')
    binding = dict(operation=pin(operation_path), publication=pin(target / 'publication.json'),
                   owner=value['owner'], correction=correction)
    if path.exists():
        saved = read(pin(path))
        if saved.get('schema') != 'FRANKIE_DEPENDENTS_INTENT_V1' or any(saved.get(k) != v for k, v in binding.items()):
            raise ValueError('retained dependent intent belongs to another successor publication')
        return saved
    brain = value['owner']['brain']
    records = R.corrections(LS.knowledge_roots(brain))
    available = sorted((r['record'] for r in records.values()), key=lambda p: p['sha256'])
    exchange = run.receipt('exchange', day) or {}
    selected = None
    if exchange.get('frankie_view'):
        view = pin(exchange['frankie_view'])
        inputs = exchange.get('successor_inputs') or pin(Path(view['path']).parent / 'learner-knowledge.json')
        retained = read(inputs)
        chains = {}
        for _, source in retained['documents']:
            cursor, visited = source['sha256'], set()
            while cursor in records:
                if cursor in visited:
                    raise ValueError('dependent lesson correction chain cycles')
                visited.add(cursor)
                record = records[cursor]
                chains[record['record']['sha256']] = record['record']
                cursor = record['replacement']['sha256']
        if chains:
            selected = dict(original_inputs=inputs, original_view=view,
                            source_corrections=[chains[k] for k in sorted(chains)], original_receipt=exchange,
                            original_voice=run.receipt('voice', day))
    import frankie_box_school_knowledge as SK
    retained_school = SK.retained_school(brain, day)
    school = None
    if retained_school is not None and (retained_school['status'] == 'requires_successor' or
            (selected and selected['original_view']['sha256'] in R.references(retained_school['content']))):
        if retained_school['content']['run'] != value['owner']['run']:
            raise ValueError('dependent school belongs to another owner run')
        school = dict(original_school=retained_school['original'], row=retained_school['row'],
                      original_receipt=run.receipt('school', day))
    sessions = value['request'].get('learner_requests') or []
    if sessions and school is None:
        from research.kalshi.frankie_boss import frankie_principal_adapter as PA
        for session in sessions:
            # Canonical files and attested original session are checked before durable intent.
            PA.select_knowledge_corrections(original_request=session['request'], original_response=session['response'],
                                            brain=brain, correction_sha256s=[p['sha256'] for p in available])
    saved = dict(schema='FRANKIE_DEPENDENTS_INTENT_V1', **binding, exchange=selected,
                 available_corrections=available, learner_sessions=sessions, school=school)
    once(path, saved)
    return saved


def dependency_result(target):
    """Read the held-child output against its immutable parent-prepared intent."""
    intent_pin = pin(target / 'dependents-intent.json')
    intent = read(intent_pin)
    result = read(pin(target / 'dependencies-result.json'))
    if (result.get('schema') != 'FRANKIE_DEPENDENTS_COMPUTATION_V1' or result.get('status') != 'complete'
            or result.get('intent') != intent_pin or result.get('operation') != intent['operation']):
        raise ValueError('dependent computation differs from its exact retained intent')
    original, rebuilt = intent['exchange'], result.get('exchange')
    if original is None:
        if rebuilt is not None:
            raise ValueError('dependent computation invented an exchange')
    else:
        if (not isinstance(rebuilt, dict) or rebuilt.get('original_inputs') != original['original_inputs']
                or rebuilt.get('original_view') != original['original_view']
                or rebuilt.get('source_corrections') != original['source_corrections']
                or read(rebuilt['receipt']) != {k: v for k, v in rebuilt.items() if k != 'receipt'}):
            raise ValueError('dependent computation changed its original exchange or checked source chains')
        for key in ('replacement_inputs', 'full', 'frankie_view'):
            read(rebuilt[key])
    return intent, result


def rebuild_dependents(run, day, value, target, correction):
    """Parent publication/recovery; exchange calculations run only in the held child."""
    intent = prepare_dependents(run, day, value, target, correction)
    if not (target / 'dependencies-result.json').exists():
        return dict(status='dispatch', reason='held-lane dependent computation required')
    intent, computed = dependency_result(target)
    brain, rebuilt = value['owner']['brain'], computed['exchange']
    checked = {p['sha256']: p for p in intent['available_corrections']}
    exchange_publication = voice_invalidation = None
    if rebuilt is not None:
        selected = intent['exchange']
        record = R.record_correction(brain, original=selected['original_view'], replacement=rebuilt['frankie_view'],
            scopes=[[]], decision='checked_dependency_rebuild',
            reason='original teacher exchange recomputed from its checked corrected lesson inputs',
            evidence=selected['source_corrections'], publication_day=day,
            exchange_transition=dict(receipt=rebuilt['receipt']))
        exchange_publication = once(target / 'exchange-publication.json',
            dict(intent=pin(target / 'dependents-intent.json'), computation=pin(target / 'dependencies-result.json'),
                 original=selected['original_view'], replacement=rebuilt['frankie_view'], correction=record))
        checked[record['sha256']] = record
        current = run.receipt('exchange', day) or {}
        if current != selected['original_receipt'] and not (
                current.get('frankie_view') == rebuilt['frankie_view']['path'] and current.get('correction') == record
                and current.get('successor_inputs') == rebuilt['replacement_inputs']):
            raise ValueError('another exchange receipt cannot complete this dependent intent')
        if current == selected['original_receipt']:
            run.record('exchange', day, 'done', exchange=rebuilt['full']['path'],
                frankie_view=rebuilt['frankie_view']['path'], exchange_sha256=rebuilt['frankie_view']['sha256'],
                successor_inputs=rebuilt['replacement_inputs'], correction=record)
        # This intent survives a crash after the exchange receipt but before voice reset.
        voice_path = target / 'voice-invalidation.json'
        expected = dict(exchange_publication=exchange_publication, original_receipt=selected['original_voice'])
        if not voice_path.exists():
            voice = run.receipt('voice', day)
            original_voice = selected['original_voice']
            if original_voice and original_voice.get('status') in ('done', 'reused'):
                if voice == original_voice:
                    run.record('voice', day, 'waiting', reason='checked exchange successor requires its own meeting',
                               original_receipt=original_voice, invalidated_by=exchange_publication)
                elif not voice or voice.get('invalidated_by') != exchange_publication or voice.get('status') != 'waiting':
                    raise ValueError('voice receipt changed outside this dependent invalidation')
        voice_invalidation = once(voice_path, expected)
    school_recovery = None
    if intent.get('school') is not None:
        import frankie_box_school_knowledge as SK
        selected_school = intent['school']
        invalidation_path = target / 'school-invalidation.json'
        expected = dict(intent=pin(target / 'dependents-intent.json'),
                        original_school=selected_school['original_school'],
                        original_receipt=selected_school['original_receipt'], exchange_publication=exchange_publication)
        if not invalidation_path.exists():
            original_receipt = selected_school['original_receipt']
            current = run.receipt('school', day)
            if original_receipt and original_receipt.get('status') in ('done', 'reused'):
                if current == original_receipt:
                    run.record('school', day, 'waiting', reason='checked source successor requires owner school recovery',
                               original_receipt=original_receipt, invalidated_by=expected)
                elif not current or current.get('invalidated_by') != expected:
                    raise ValueError('school receipt changed outside its exact dependent invalidation')
        invalidation = once(invalidation_path, expected)
        retained = SK.retained_school(brain, day)
        if retained is None or retained['row'] != selected_school['row']:
            raise ValueError('dependent school lost its original indexed owner')
        if retained['status'] != 'complete':
            # The owning coordinator must resume its existing voice -> school steps without
            # recursively draining this inbox. Never deliver a stale school to the learner.
            return dict(status='waiting_school', reason='owner meeting/school successor must complete before dependent delivery',
                        recovery_intent=invalidation, stages=['voice', 'school'])
        records = R.corrections([brain])
        cursor, links = selected_school['original_school']['sha256'], []
        while cursor in records:
            record = records[cursor]
            if record['body'].get('school_transition') is None:
                raise ValueError('dependent school lost its explicit owner transition')
            links.append(record['record'])
            checked[record['record']['sha256']] = record['record']
            cursor = record['replacement']['sha256']
        if not links or cursor != retained['original']['sha256']:
            raise ValueError('dependent school is not its exact checked successor')
        school_recovery = once(target / 'school-recovery.json', dict(invalidation=invalidation,
            original=selected_school['original_school'], replacement=retained['original'], corrections=links))
    native_path = target / 'native-dependents-intent.json'
    if intent['learner_sessions']:
        from research.kalshi.frankie_boss import frankie_principal_adapter as PA
    if native_path.exists():
        native = read(pin(native_path))
        if native.get('intent') != pin(target / 'dependents-intent.json') or native.get('exchange_publication') != exchange_publication:
            raise ValueError('native dependent selection belongs to another exchange publication')
    else:
        selections = [PA.select_knowledge_corrections(original_request=s['request'], original_response=s['response'],
                        brain=brain, correction_sha256s=sorted(checked)) for s in intent['learner_sessions']]
        native = dict(intent=pin(target / 'dependents-intent.json'), exchange_publication=exchange_publication,
                      selections=selections, corrections=[checked[k] for k in sorted(checked)])
        once(native_path, native)
    receipts = []
    for index, selection in enumerate(native['selections']):
        # Recheck canonical supplied originals even after the preparation/publication crash boundary.
        current = PA.select_knowledge_corrections(original_request=selection['original_request'],
            original_response=selection['original_response'], brain=brain,
            correction_sha256s=[p['sha256'] for p in native['corrections']])
        if current != selection:
            raise ValueError('native dependent selection changed after its durable intent')
        if selection['status'] == 'not_affected':
            receipts.append(dict(selection=index, status='not_affected'))
            continue
        directory = Path(selection['directory'])
        followup = PA.prepare_knowledge_correction(directory, selection['request_id'], brain=brain,
                                                   correction_sha256s=selection['correction_sha256s'])
        key = PA.digest(followup)
        request = pin(directory / 'knowledge-corrections' / key / 'request.json')
        try:
            recovered = PA.recover_knowledge_correction(directory, key)
        except PA.PrincipalPending:
            return dict(status='waiting', reason='same-session correction consumption awaits original host response',
                        request=request, native_intent=pin(native_path))
        completed = once(target / 'native-results' / (str(index) + '.json'),
            dict(selection=index, native_intent=pin(native_path), request=request,
                 response=pin(directory / 'knowledge-corrections' / key / 'response.json'), receipt=recovered))
        receipts.append(dict(selection=index, status='complete', result=completed))
    completed = dict(schema='FRANKIE_DEPENDENTS_RECEIPT_V1', status='complete', operation=intent['operation'],
        publication=intent['publication'], intent=pin(target / 'dependents-intent.json'),
        computation=pin(target / 'dependencies-result.json'), exchange_publication=exchange_publication,
        voice_invalidation=voice_invalidation, native_intent=pin(native_path), native_results=receipts)
    if intent.get('school') is not None:
        completed['school_recovery'] = school_recovery
    once(target / 'dependents.json', completed)
    return completed


def dependent_receipt(path, value):
    """Completion requires every frozen dependency and original-session response witness."""
    target = path.parent.parent / 'work' / path.stem
    saved = read(pin(target / 'dependents.json'))
    intent, computed = dependency_result(target)
    if (saved.get('schema') != 'FRANKIE_DEPENDENTS_RECEIPT_V1' or saved.get('status') != 'complete'
            or saved.get('operation') != pin(path) or saved.get('publication') != pin(target / 'publication.json')
            or saved.get('intent') != pin(target / 'dependents-intent.json')
            or saved.get('computation') != pin(target / 'dependencies-result.json')
            or intent.get('owner') != value['owner']
            or intent.get('learner_sessions') != (value['request'].get('learner_requests') or [])):
        raise ValueError('dependent completion is not bound to this exact owner operation')
    native = read(saved['native_intent'])
    if (saved['native_intent'] != pin(target / 'native-dependents-intent.json')
            or native['intent'] != saved['intent'] or native['exchange_publication'] != saved['exchange_publication']
            or len(saved['native_results']) != len(native['selections'])
            or len(native['selections']) != len(intent['learner_sessions'])):
        raise ValueError('dependent completion changed its original native selection')
    if computed['exchange'] is not None:
        published = read(saved['exchange_publication'])
        invalidation = read(saved['voice_invalidation'])
        if (saved['exchange_publication'] != pin(target / 'exchange-publication.json')
                or saved['voice_invalidation'] != pin(target / 'voice-invalidation.json')
                or published['intent'] != saved['intent'] or published['computation'] != saved['computation']
                or published['original'] != intent['exchange']['original_view']
                or published['replacement'] != computed['exchange']['frankie_view']
                or invalidation != dict(exchange_publication=saved['exchange_publication'],
                                        original_receipt=intent['exchange']['original_voice'])):
            raise ValueError('dependent completion lacks its exact exchange/voice recovery chain')
        correction = read(published['correction'])
        if correction['original'] != published['original'] or correction['replacement'] != published['replacement']:
            raise ValueError('dependent exchange correction binds another result')
        import frankie_box_lane_state as LS
        records = R.corrections(LS.knowledge_roots(value['owner']['brain']))
        checked = records.get(published['original']['sha256'])
        if not checked or checked['body'] != correction or checked['record'] != published['correction']:
            raise ValueError('dependent exchange correction is not its checked published record')
    elif saved['exchange_publication'] is not None or saved['voice_invalidation'] is not None:
        raise ValueError('dependent receipt invented an exchange publication')
    if intent.get('school') is not None:
        recovered = read(saved['school_recovery'])
        if (saved['school_recovery'] != pin(target / 'school-recovery.json')
                or recovered['invalidation'] != pin(target / 'school-invalidation.json')
                or recovered['original'] != intent['school']['original_school']):
            raise ValueError('dependent completion lacks the exact school recovery intent')
        invalidation = read(recovered['invalidation'])
        if invalidation != dict(intent=saved['intent'], original_school=recovered['original'],
                original_receipt=intent['school']['original_receipt'], exchange_publication=saved['exchange_publication']):
            raise ValueError('dependent school recovery changed its original owner binding')
        read(recovered['original'])
        read(recovered['replacement'])
        records = R.corrections([value['owner']['brain']])
        cursor = recovered['original']['sha256']
        for pin_record in recovered['corrections']:
            record = records.get(cursor)
            if not record or record['record'] != pin_record or record['body'].get('school_transition') is None:
                raise ValueError('dependent completion lacks its checked school successor chain')
            cursor = record['replacement']['sha256']
        if not recovered['corrections'] or cursor != recovered['replacement']['sha256']:
            raise ValueError('dependent school completion changed its replacement')
    elif saved.get('school_recovery') is not None:
        raise ValueError('dependent receipt invented a school recovery')
    if intent['learner_sessions']:
        from research.kalshi.frankie_boss import frankie_principal_adapter as PA
    for index, (selection, result, original) in enumerate(zip(native['selections'], saved['native_results'], intent['learner_sessions'])):
        if (result.get('selection') != index or selection['original_request'] != original['request']
                or selection['original_response'] != original['response']):
            raise ValueError('dependent receipt substituted another native session')
        current = PA.select_knowledge_corrections(original_request=original['request'], original_response=original['response'],
            brain=value['owner']['brain'], correction_sha256s=[p['sha256'] for p in native['corrections']])
        if current != selection:
            raise ValueError('dependent receipt changed its canonical originals or applicable correction subset')
        if selection['status'] == 'not_affected':
            if result != dict(selection=index, status='not_affected'):
                raise ValueError('unaffected native session has an invented consumption receipt')
            continue
        if result.get('result') != pin(target / 'native-results' / (str(index) + '.json')):
            raise ValueError('dependent native result is outside its canonical owner output')
        completed = read(result['result'])
        request, response = read(completed['request']), read(completed['response'])
        proof = completed['receipt']
        key = PA.digest(request)
        directory = Path(selection['directory']) / 'knowledge-corrections' / key
        recovered = PA.recover_knowledge_correction(selection['directory'], key)
        if (result['status'] != 'complete' or completed['selection'] != index
                or completed['native_intent'] != saved['native_intent']
                or completed['request'] != pin(directory / 'request.json')
                or completed['response'] != pin(directory / 'response.json')
                or request.get('request_id') != selection['request_id']
                or request.get('original_request_sha256') != selection['original_request_sha256']
                or request.get('original_response_sha256') != selection['original_response_sha256']
                or [c['record']['sha256'] for c in request.get('corrections', [])] != selection['correction_sha256s']
                or proof != recovered
                or proof.get('schema') != 'FRANKIE_KNOWLEDGE_CORRECTION_FOLLOWUP_RECEIPT_V1'
                or proof['request_sha256'] != PA.digest(request) or proof['response_sha256'] != PA.digest(response['response'])
                or proof['host_attestation_sha256'] != PA.digest(response['host_attestation'])):
            raise ValueError('dependent receipt lacks the exact consumed native follow-up')
    return pin(target / 'dependents.json')


def execute(path, phase):
    """Existing staged child entrypoint; no scheduling or fresh attempt identity."""
    import frankie_box_teacher_knowledge as TK
    value = operation(path)
    directory = path.parent.parent
    target = directory / 'work' / path.stem
    identity = value['owner']
    import frankie_box_experiment as X
    import frankie_box_cores as C
    expected = X.RUNS / identity['run'] / 'successors' / identity['day'] / 'requests' / path.name
    plan = read(pin(X.RUNS / identity['run'] / 'plan.json'))
    booking = os.environ.get('FRANKIE_CPU_BOOKING')
    held, _ = C.held_booking(booking) if booking else (None, None)
    if (path.resolve() != expected.resolve() or identity['commit'] != os.environ.get('MARKETS_SHA')
            or X.plan_digest(plan) != identity['plan_sha256']
            or str(plan.get('brain') or X.BRAIN) != identity['brain']
            or not held or held.get('run') != identity['run'] or held.get('day') != identity['day']
            or held.get('kind') != 'day-run' or len(held.get('cpus') or []) != 16):
        raise ValueError('successor child lacks its exact staged plan/code/held owner lane')
    # An orphaned child may still finish after its parent dies. A second child waits for
    # that operation, then reads its exact completed receipt rather than rewriting it.
    with lock(target / 'execute.lock'):
        if phase == 'research':
            candidate = target / 'successor-receipt.json'
            if candidate.exists():
                saved = read(pin(candidate))
                if saved.get('schema') != 'FRANKIE_TEACHER_SUCCESSOR_RECEIPT_V1' or saved['successor_request'] != value['request']:
                    raise ValueError('retained candidate belongs to another request')
                read(saved['inputs'])
                for result in saved['files']:
                    read(result)
                return
            if read(value['request']['original_inputs']).get('schema') == 'FRANKIE_STANDALONE_TEACHER_INPUTS_V1':
                import frankie_box_scientific_teacher as ST
                ST.teach_standalone_successor(identity['day'], value['search'], identity['brain'], target, request=value['request'])
            else:
                TK.teach_successor(identity['day'], value['search'], identity['brain'], target, request=value['request'])
        elif phase == 'publish':
            decision_pin = pin(directory / 'decisions' / path.name)
            decision = read(decision_pin)
            if read(decision['receipt'])['successor_request'] != value['request']:
                raise ValueError('publication decision belongs to another request')
            completed = read(decision['receipt'])
            if read(value['request']['original_inputs']).get('schema') == 'FRANKIE_STANDALONE_TEACHER_INPUTS_V1':
                import frankie_box_scientific_teacher as ST
                if (completed.get('publication_day') != identity['day']
                        or read(completed['inputs'])['identity'].get('successor') != value['request']):
                    raise ValueError('standalone publication differs from its frozen successor owner')
                record = ST.publish_standalone_correction(identity['brain'], original=value['request']['original_result'],
                    replacement=completed['files'][0], **completed['owner_transition'], publication_day=identity['day'],
                    **{k: decision[k] for k in ('scopes', 'decision', 'reason', 'evidence')})
            else:
                record = TK.publish_successor(identity['brain'], **decision)
            once(target / 'publication.json', dict(operation=pin(path), decision=decision_pin, correction=record))
        elif phase == 'dependencies':
            intent_pin = pin(target / 'dependents-intent.json')
            intent = read(intent_pin)
            if (intent.get('schema') != 'FRANKIE_DEPENDENTS_INTENT_V1' or intent.get('operation') != pin(path)
                    or intent.get('owner') != identity or intent.get('publication') != pin(target / 'publication.json')):
                raise ValueError('dependent child lacks its parent-prepared exact intent')
            if (target / 'dependencies-result.json').exists():
                dependency_result(target)
                return
            rebuilt = None
            if intent['exchange'] is not None:
                import frankie_box_experiment_exchange as EX
                selected = intent['exchange']
                rebuilt = EX.rebuild_successor(identity['day'], identity['run'], identity['brain'], target / 'exchange',
                    original_inputs=selected['original_inputs'], original_view=selected['original_view'],
                    source_corrections=selected['source_corrections'])
            once(target / 'dependencies-result.json', dict(schema='FRANKIE_DEPENDENTS_COMPUTATION_V1',
                status='complete', operation=pin(path), intent=intent_pin, exchange=rebuilt))
        else:
            raise ValueError('unknown successor child phase')


def drain(run, day):
    """Consume the inbox inside the existing held day. Save/decision waits keep that booking.

    One drain owns the day inbox at a time (class and ROOT loops can meet the same boundary).
    Completion follows correction readback AND the existing lane knowledge sync acknowledgment.
    A crashed child can only resume its same frozen operation; completed results/publications
    are reused. A returned failure remains pending until an explicit retry names that failure.
    """
    directory = run.dir / 'successors' / day
    if not (directory / 'requests').is_dir():
        return []
    identity = owner(run, day)
    completed = []
    with lock(directory / 'drain.lock'):
        for path in sorted((directory / 'requests').glob('*.json')):
            value = operation(path, identity)
            key, target = path.stem, directory / 'work' / path.stem
            ack = target / 'ack.json'
            if ack.is_file():
                completed.append(acknowledgment(path, value))
                continue
            school_completed = None      # F7: at most ONE 'complete' owner school recovery per operation per drain call
            while True:
                held, why = run.cores.held_booking(getattr(run, 'slot_booking', None)) if getattr(run, 'slot_booking', None) else (None, 'no held day booking')
                if (not held or held.get('run') != identity['run'] or held.get('day') != day
                        or held.get('kind') != 'day-run' or len(held.get('cpus') or []) != 16):
                    raise ValueError('successor requires its original held day lane: ' + str(why))
                state_path = target / 'state.json'
                def state(status, **facts):
                    body = dict(operation=pin(path), status=status, **facts)
                    if not state_path.exists() or read(pin(state_path)) != body:
                        D.write_json(state_path, body)
                        run.record('successors', day, status, operation=pin(path), progress=pin(state_path))
                control_path = directory / 'control.json'
                paused = read(pin(control_path)) if control_path.exists() else {}
                if paused and paused['owner'] != identity:
                    raise ValueError('successor save control belongs to another owner')
                if run.save_requested() or paused.get('saved'):
                    state('saved', reason='cooperative save acknowledged; original operation and CPU booking held')
                    time.sleep(5)
                    continue
                failure = target / 'failure.json'
                retry = target / 'retry.json'
                if failure.exists() and (not retry.exists() or read(pin(retry)).get('failure') != pin(failure)):
                    state('waiting', reason='child failed; explicit retry must name the retained failure', failure=pin(failure))
                    time.sleep(5)
                    continue
                publication = target / 'publication.json'
                candidate = target / 'successor-receipt.json'
                decision = directory / 'decisions' / path.name
                phase = 'research' if not candidate.exists() else 'publish'
                if not publication.exists() and phase == 'publish' and not decision.exists():
                    state('waiting', reason='complete candidate awaits the checked scientific-owner decision', candidate=pin(candidate))
                    time.sleep(5)
                    continue
                try:
                    recover_sync(identity['brain'])
                    if not publication.exists():
                        # Intent precedes child creation. The same work directory holds every recovery.
                        state('running', phase=phase, slot_booking=run.slot_booking)
                        code, log = run.child('lessons', day + '-successor-' + key,
                                              'frankie_box_teacher_successor.sh',
                                              dict(SUCCESSOR_OPERATION=path, SUCCESSOR_PHASE=phase,
                                                   SUCCESSOR_OWNER_DAY=day))
                        if code != 0:
                            D.write_json(failure, dict(operation=pin(path), phase=phase, exit_code=code,
                                                       log=log, at=time.time()))
                            continue
                        if not (candidate if phase == 'research' else publication).is_file():
                            raise ValueError('successor child exited without its completed phase receipt')
                        for retained in (run._cpu, run._knowledge):
                            item = retained.pop(('lessons', day + '-successor-' + key), None)
                            if item is not None:
                                retained[('successors', day)] = item
                        continue
                    published = read(pin(publication))
                    if published['operation'] != pin(path) or published['decision'] != pin(decision):
                        raise ValueError('publication does not bind the queued request and decision')
                    correction = read(published['correction'])
                    if correction['original'] != {k: value['request']['original_result'][k] for k in ('path', 'bytes', 'sha256')}:
                        raise ValueError('publication corrected another original result')
                    records = R.corrections([Path(identity['brain'])])
                    checked = records.get(value['request']['original_result']['sha256'])
                    if not checked or checked['record'] != published['correction'] or checked['body'] != correction:
                        raise ValueError('successor publication is not the checked brain correction')
                    downstream = rebuild_dependents(run, day, value, target, published['correction'])
                    if downstream['status'] == 'dispatch':
                        phase = 'dependencies'
                        state('running', phase=phase, slot_booking=run.slot_booking)
                        code, log = run.child('lessons', day + '-successor-' + key,
                            'frankie_box_teacher_successor.sh', dict(SUCCESSOR_OPERATION=path,
                            SUCCESSOR_PHASE=phase, SUCCESSOR_OWNER_DAY=day))
                        if code != 0:
                            D.write_json(failure, dict(operation=pin(path), phase=phase, exit_code=code,
                                                       log=log, at=time.time()))
                            continue
                        dependency_result(target)
                        for retained in (run._cpu, run._knowledge):
                            item = retained.pop(('lessons', day + '-successor-' + key), None)
                            if item is not None:
                                retained[('successors', day)] = item
                        continue
                    if downstream['status'] == 'waiting_school':
                        # CCode (Step 8): the owner's own voice then school on this held lane, the nested inbox drain
                        # skipped for exactly this recovery (this drain holds drain.lock; close_day takes inbox.lock only
                        # after the drain returns); then rebuild_dependents again verifies the checked chain. Never a
                        # second drain, scheduler or model runtime.
                        if school_completed is not None:
                            # F7 (second review): a recovery already ended 'complete' in THIS drain call and the chain
                            # still reads waiting_school (for example another correction landed meanwhile). No second
                            # recovery (it would dispatch the school child again): recorded waiting with the reason,
                            # the ordinary poll interval, and the drain moves on; the next drain call tries it once more.
                            state('waiting', **dict({k: v for k, v in downstream.items() if k != 'status'},
                                                    recovery=school_completed,
                                                    reason='the school stage ended done but the chain still requires a '
                                                           'successor (one complete recovery per operation per drain call)'))
                            time.sleep(5)
                            break
                        recovered = run.recover_school(day, downstream['recovery_intent'])
                        if recovered.get('status') == 'complete':
                            school_completed = recovered
                            # the recovered school (file, row sha256, status) reaches the day reports on this held lane
                            # (correction_consumer, stage 12): a revision under the same number when the reports were
                            # rendered on the replaced school (Run.reports_stale reads the school receipt). The nested
                            # drain is skipped for exactly this call (this drain holds drain.lock; re-entering it would
                            # block on its own flock); a report failure is the reports step's own receipt.
                            # F6 (second review): three distinct dispositions, never 'current' when no reports exist
                            entry = next((x for x in run.plan['days'] if x['day'] == day), None)
                            reports = run.receipt('reports', day) or {}
                            exchange = run.receipt('exchange', day) or {}
                            if entry is None:
                                recovered['reports'] = dict(status='not_applicable', reason='the day is not in the run plan')
                            elif reports.get('status') != 'done':
                                recovered['reports'] = dict(status='not_rendered', prior=reports.get('status'),
                                                            reason='no reports rendered yet (the reports stage renders on '
                                                                   'the current school when it runs)')
                            elif exchange.get('status') not in ('done', 'reused'):
                                recovered['reports'] = dict(status='exchange_not_done', prior=exchange.get('status'),
                                                            reason='the exchange is not done; the reports revise after it')
                            else:
                                run._school_recovery.add(day)
                                try:
                                    if run.reports_stale(entry):
                                        recovered['reports'] = {k: (run.guarded('reports', entry) or {}).get(k)
                                                                for k in ('status', 'reason', 'report_number')}
                                    else:
                                        recovered['reports'] = dict(status='current',
                                                                    reason='the reports already carry this school')
                                finally:
                                    run._school_recovery.discard(day)
                        state('waiting', **dict({k: v for k, v in downstream.items() if k != 'status'}, recovery=recovered))
                        if recovered.get('status') != 'complete':
                            # the operation stays unacknowledged (its state carries the recovery's stage, inputs, use and
                            # outputs; a failed stage is the day's own failed receipt, retried by the ordinary path);
                            # the next drain call tries it once more. The ordinary poll interval first: close_day drains
                            # ONCE and returns 'waiting' for an unacknowledged request, but the class worker's keep() and
                            # every child boundary drain again, and recover_school dispatches nothing twice, so without it
                            # those repeated drains would spin hot on reads and receipt rewrites.
                            time.sleep(5)
                            break
                        continue
                    if downstream['status'] != 'complete':
                        state('waiting', **{k: v for k, v in downstream.items() if k != 'status'})
                        time.sleep(5)
                        continue
                    dependents_pin = once(target / 'dependents.json', downstream)
                    # Full readback before any acknowledgment, including legacy missing receipts.
                    dependent_receipt(path, value)
                    import frankie_box_lane_state as LS
                    available = LS.boundary(day, 'lessons', brain=identity['brain'])
                    once(ack, dict(operation=pin(path), publication=pin(publication),
                                   correction=published['correction'], dependents=dependents_pin))
                    state('done', acknowledgment=pin(ack), knowledge_available=available)
                    completed.append(pin(ack))
                    break
                except SystemExit as error:
                    if error.code != 75:
                        raise
                    # child/checkpoint may observe save after a completed durable write. Never
                    # propagate it into the queue's generic failure/release path for this operation.
                    state('saved', reason='phase interrupted by cooperative save; resume identical retained operation')
                except Exception as error:
                    D.write_json(failure, dict(operation=pin(path), phase=phase,
                                               error=type(error).__name__ + ': ' + str(error), at=time.time()))
    return completed


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--operation', required=True)
    p.add_argument('--phase', choices=('research', 'publish', 'dependencies'), required=True)
    a = p.parse_args()
    execute(Path(a.operation), a.phase)


if __name__ == '__main__':
    main()
