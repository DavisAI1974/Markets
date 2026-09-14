"""Export verified durable BOSS evidence. Never refresh, infer or invoke an agent."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
import subprocess

try:
    from .c15_journal import canonical_bytes, evidence_hash, pack
    from .controller_journal import ControllerJournal
    from .rolling_forecast import RollingForecastBook, ForecastCandidate, ForecastTarget
    from .forecast_artifact import NativeForecastArtifact
    from .frankie_forecast_consumer import _computation_binding
except ImportError:
    from c15_journal import canonical_bytes, evidence_hash, pack
    from controller_journal import ControllerJournal
    from rolling_forecast import RollingForecastBook, ForecastCandidate, ForecastTarget
    from forecast_artifact import NativeForecastArtifact
    from frankie_forecast_consumer import _computation_binding

SCHEMA = 'BOSS_AGENT_FILE_HANDOFF_V1'


def _json(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def _commit(value):
    if type(value) is not str or re.fullmatch('[0-9a-f]{40}', value) is None:
        raise ValueError('full lowercase software commit required')
    return value


def _verify_sources(repository):
    """A Git HEAD label alone does not identify modified or untracked code."""
    scope = 'research/kalshi/frankie_boss'
    changes = subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=all', '--', scope],
                                      cwd=repository, text=True)
    if changes.strip():
        raise ValueError('BOSS source tree differs from committed software')
    subprocess.check_call(['git', 'ls-files', '--error-unmatch', '--', scope+'/agent_file_handoff.py'],
                          cwd=repository, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _verify_generation(configuration):
    directory = Path(__file__).resolve().parent
    code = configuration['code']
    if not code or any(Path(name).name != name or (directory/name).read_bytes() != data
                       for name, data in code.items()):
        raise ValueError('retained generation code differs from declared BOSS commit')
    # Transport source can be an in-repository service or a committed test fixture.
    tracked = subprocess.check_output(['git', 'ls-files', '--', '*.py'],
                                      cwd=directory, text=True).splitlines()
    if not any((directory/name).read_bytes() == configuration['transport_code'] for name in tracked):
        raise ValueError('retained transport is not part of declared BOSS commit')


def _open(factory, path, checkpoint):
    try:
        return factory(path, checkpoint=checkpoint)
    except (KeyError, TypeError, IndexError, json.JSONDecodeError) as exc:
        raise ValueError('malformed retained journal') from exc


def _causal_histories(controller, native, request_id, request):
    """A full archive exposed as input must not carry any later request evidence."""
    last = None
    for entry in controller.journal.entries():
        last = entry['payload']
        if last['step'] == 'INTENT':
            earlier = last['payload']['request']
            if any(type(earlier[key]) is not int or earlier[key] > request[key]
                   for key in ('as_of', 'source_as_of', 'through_cursor')):
                raise ValueError('controller archive contains later causal evidence')
    if last is None or last['request_id'] != request_id or last['step'] != 'RESULT':
        raise ValueError('selected result must end the controller checkpoint')
    for entry in native.journal.entries():
        payload = entry['payload']
        candidates = payload.get('candidates', (payload,))
        for candidate in candidates:
            if any(type(candidate[key]) is not int or candidate[key] > request[key]
                   for key in ('as_of', 'source_as_of')):
                raise ValueError('native archive contains later causal evidence')
            if 'candidates' in payload:
                typed = ForecastCandidate(**dict(candidate, target=ForecastTarget(**candidate['target'])))
                _, binding, _ = _candidate_artifact(typed)
                context = binding['context']
                if (context['prefix_rows'] > request['through_cursor'] + 1 or
                        any(cursor > request['through_cursor'] for cursor in context['context_cursors'])):
                    raise ValueError('native artifact context exceeds export cursor')


def _candidate_artifact(candidate):
    artifact = NativeForecastArtifact.from_payload(candidate.forecast_artifact,
                                                   expected_digest=candidate.candidate_id)
    binding = _computation_binding(artifact)
    context = binding['context']
    session = artifact.session
    model = evidence_hash(dict(native=artifact.native_model_hash,
                               execution=binding['native_execution_hash'], decoder=artifact.snapshot.digest))
    if (candidate.target.instrument != session.instrument or candidate.target.target_ns != session.close_ns
            or candidate.as_of != session.receive_cutoff_ns or candidate.source_as_of != session.event_cutoff_ns
            or candidate.source_hash != session.source_hash or candidate.arm_hash != artifact.arm_hash
            or model != candidate.model_hash
            or context['source_prefix_hash'] != candidate.source_hash
            or context['as_of'] != candidate.as_of):
        raise ValueError('artifact computation differs from retained publication')
    return artifact, binding, model


def _publication(book, record, request, configuration):
    publication = book.publication(record['publication_hash'])
    candidate = publication.selected
    if (asdict(candidate.target) != record['target'] or publication.revision != record['revision']
            or candidate.candidate_id != record['artifact_digest']
            or candidate.as_of != request['as_of'] or candidate.source_as_of != request['source_as_of']
            or candidate.source_hash != request['source_hash'] or candidate.arm_hash != request['arm_hash']):
        raise ValueError('publication differs from retained controller source/target/arm')
    _, _, model = _candidate_artifact(candidate)
    if model != configuration['native_hash']:
        raise ValueError('artifact model differs from retained controller configuration')
    return candidate.forecast_artifact


def export_handoff(destination, *, controller_path, native_path, request_id,
                   controller_checkpoint, native_checkpoint, boss_commit, agent_commit):
    """Reopen against independent pins and create a deterministic exclusive export.

    boss_commit must match this executing checkout. agent_commit is the declared
    receiver version, checked independently on that side of the file boundary.
    A final manifest appears only after every payload has been written. Failed
    partial directories remain unusable and are never silently overwritten.
    """
    _commit(boss_commit)
    _commit(agent_commit)
    repository = Path(__file__).resolve().parents[3]
    actual_commit = subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=repository, text=True).strip()
    if boss_commit != actual_commit:
        raise ValueError('BOSS commit differs from executing checkout')
    _verify_sources(repository)
    if type(request_id) is not str or not request_id:
        raise ValueError('explicit request ID required')
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(destination)
    controller = _open(ControllerJournal, controller_path, controller_checkpoint)
    try:
        native = _open(RollingForecastBook, native_path, native_checkpoint)
        try:
            state = controller.state(request_id)
            if state is None or state['result'] is None:
                raise ValueError('request has no committed result')
            result = state['result']
            intent = state['intent']
            request, configuration = intent['request'], intent['configuration']
            _verify_generation(configuration)
            _causal_histories(controller, native, request_id, request)
            if state['native']['checkpoint'] != native_checkpoint:
                raise ValueError('native checkpoint differs from retained completion')
            if result['status'] not in ('complete', 'incomplete', 'idle'):
                raise ValueError('unknown durable status')
            expected_targets = [target for target, _ in request['sessions']]
            if [record['target'] for record in result['records']] != expected_targets:
                raise ValueError('result differs from full requested target roster')
            source = dict(prefix_hash=request['source_hash'], through_cursor=request['through_cursor'],
                          as_of=request['as_of'], source_as_of=request['source_as_of'], arm_hash=request['arm_hash'])
            payloads = {'state.c15.json': (canonical_bytes(pack(state)), 'controller_state')}
            for name, journal in [('controller', controller.journal), ('native', native.journal)]:
                payloads[f'{name}.c15.jsonl'] = (
                    b''.join(canonical_bytes(pack(entry)) + b'\n' for entry in journal.entries()),
                    f'{name}_journal')
            if state['critic_intent'] is not None:
                for label, key in [('snapshot', 'snapshot_text'), ('prompt', 'prompt_text')]:
                    payloads[f'critic-{label}.txt'] = (state['critic_intent'][key].encode('utf-8'), f'critic_{label}')
            targets = []
            for index, record in enumerate(result['records']):
                artifact = _publication(native, record, request, configuration)
                record_path, artifact_path = f'record-{index:06d}.json', f'forecast-{index:06d}.bin'
                payloads[record_path] = (record['record_json'].encode('utf-8'), 'record')
                payloads[artifact_path] = (artifact, 'forecast_artifact')
                targets.append({**{key: record[key] for key in (
                    'target', 'revision', 'publication_hash', 'artifact_digest', 'record_digest')},
                    'record_path': record_path, 'artifact_path': artifact_path})
            # Guard against another writer moving either retained journal during export.
            if controller.checkpoint() != controller_checkpoint or native.checkpoint() != native_checkpoint:
                raise ValueError('journal changed during export')
            native.journal.verify(count=native_checkpoint['count'], head_hash=native_checkpoint['head_hash'])
            manifest = dict(schema=SCHEMA, boss_commit=boss_commit, agent_commit=agent_commit,
                request_id=request_id, request_hash=state['request_hash'], status=result['status'],
                controller_checkpoint=controller_checkpoint, native_checkpoint=native_checkpoint,
                configuration_hash=evidence_hash(configuration), source=source, targets=targets,
                files=[dict(path=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), purpose=purpose)
                       for name, (data, purpose) in sorted(payloads.items())])
        except (KeyError, TypeError, IndexError) as exc:
            raise ValueError('malformed retained handoff evidence') from exc
        finally:
            native.close()
    finally:
        controller.close()
    destination.mkdir(parents=False, exist_ok=False)
    for name, (data, _) in sorted(payloads.items()):
        with (destination/name).open('xb') as stream:
            stream.write(data)
    with (destination/'manifest.json').open('xb') as stream:
        stream.write(_json(manifest))
    return manifest
