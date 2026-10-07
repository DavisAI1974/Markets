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
    if (original['identity']['day'] != day or original['identity']['brain'] != identity['brain']):
        raise ValueError('successor request belongs to another scientific owner')
    search = run.receipt('search', day) or {}
    replacement_search = request.get('replacement_search')
    selected_search = str(Path(replacement_search['path']).parent) if replacement_search else original['identity']['search']
    selected_manifest = ({k: replacement_search[k] for k in ('bytes', 'sha256')} if replacement_search
                         else original['identity']['manifest'])
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
    transition = dict(schema=R.TRANSITION_SCHEMA, owner='frankie_box_teacher_knowledge.teach_accumulated',
                      original=R._transition_operation(completed['owner_transition']['original_inputs'], before),
                      replacement=R._transition_operation(completed['owner_transition']['replacement_inputs'], after))
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
    """Serialize final acknowledgment with intake; late requests cannot reopen a completed day."""
    directory = run.dir / 'successors' / day
    while True:
        completed = drain(run, day)
        with lock(directory / 'inbox.lock'):
            requests = sorted((directory / 'requests').glob('*.json'))
            if len(completed) != len(requests):
                continue
            return once(directory / 'closed.json', dict(owner=owner(run, day), acknowledgments=completed))


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
            TK.teach_successor(identity['day'], value['search'], identity['brain'], target, request=value['request'])
        else:
            decision_pin = pin(directory / 'decisions' / path.name)
            decision = read(decision_pin)
            if read(decision['receipt'])['successor_request'] != value['request']:
                raise ValueError('publication decision belongs to another request')
            record = TK.publish_successor(identity['brain'], **decision)
            once(target / 'publication.json', dict(operation=pin(path), decision=decision_pin, correction=record))


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
                    import frankie_box_lane_state as LS
                    available = LS.boundary(day, 'lessons', brain=identity['brain'])
                    once(ack, dict(operation=pin(path), publication=pin(publication),
                                   correction=published['correction']))
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
    p.add_argument('--phase', choices=('research', 'publish'), required=True)
    a = p.parse_args()
    execute(Path(a.operation), a.phase)


if __name__ == '__main__':
    main()
