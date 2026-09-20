"""Durable completed controller -> Frankie principal -> native training cycle.

Remote intent is committed before principal execution. Only explicit recovery can
resolve an interrupted attempt. Model construction/forward belongs inside the
checkpoint's lazy callback; completed cycle replay never opens an old controller.
"""
import asyncio
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import uuid

from .agent_file_handoff import export_handoff
from .c15_journal import canonical_bytes, evidence_hash, pack, unpack
from .forecast_artifact import NativeForecastArtifact
from .native_forecast_learning import FrankieFeedback


class AmbiguousPrincipalCall(RuntimeError):
    """An existing principal intent has no recoverable verified output."""


def _not_dispatched_signals():
    """Adapter-owned recovery contract, resolved lazily so this module never redefines it.

    PrincipalNotDispatched (adapter) means no durable session request exists, so the
    coordinator's saved intent never reached the principal and dispatch is safe.
    PrincipalPending means a durable request exists without a response and must
    propagate untouched. Until the adapter exports PrincipalNotDispatched, nothing is
    caught and an intent without output remains ambiguous, exactly as before.
    """
    from . import frankie_principal_adapter as adapter
    signal = getattr(adapter, 'PrincipalNotDispatched', None)
    return (signal,) if isinstance(signal, type) and issubclass(signal, BaseException) else ()


def _requested_session_ids(sessions):
    """Session IDs of the requested (name, session) roster, in order; shape is explicit."""
    if type(sessions) not in (list, tuple):
        raise ValueError('explicit requested session roster required')
    ids = []
    for pair in sessions:
        if type(pair) not in (list, tuple) or len(pair) != 2 or not hasattr(pair[1], 'session_id'):
            raise ValueError('requested sessions must be (name, session) pairs')
        ids.append(pair[1].session_id)
    return tuple(ids)


def file_hash(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _plain(value):
    if is_dataclass(value):
        return _plain(asdict(value))
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return tuple(_plain(v) for v in value)
    return value


@contextmanager
def _exclusive(path):
    """Process lifetime lock: an actual process crash releases the OS lock."""
    with Path(path).open('a+b') as stream:
        stream.seek(0, 2)
        if not stream.tell():
            stream.write(b'0'); stream.flush()
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def _export_verified(directory, export_args, result, learning, superseded=None):
    """Real exporter plus readback; preserve unfinished exports for diagnosis.

    superseded maps a pin name ('boss_commit', 'agent_commit') to the OLD values an operator
    declaration accepts for a retained export (2026-09-20: a host code advance during an open
    cycle moved boss_commit while the exported files, result and artifacts are hash-verified
    below exactly as before). Undeclared differences still refuse.
    """
    directory = Path(directory)
    if not directory.exists():
        staging = directory.with_name(directory.name+'.partial-'+uuid.uuid4().hex)
        export_handoff(staging, **export_args)
        staging.rename(directory)
    manifest = json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    superseded = superseded or {}
    for name in ('request_id', 'boss_commit', 'agent_commit', 'controller_checkpoint', 'native_checkpoint'):
        if manifest[name] != export_args[name] and manifest[name] not in superseded.get(name, ()):
            raise ValueError('retained export differs from independently supplied pins')
    if (manifest['request_id'] != result['request_id']
            or result.get('status') not in ('complete', 'incomplete')
            or manifest['status'] != result['status']
            or manifest['request_hash'] != result['request_hash']
            or manifest['source']['prefix_hash'] != learning['source_hash']
            or manifest['source']['through_cursor'] != learning['through_cursor']
            or manifest['source']['as_of'] != learning['as_of']):
        raise ValueError('export does not bind verified cycle source/request')
    for item in manifest['files']:
        if Path(item['path']).name != item['path']:
            raise ValueError('invalid export member path')
        member = directory/item['path']
        if member.stat().st_size != item['bytes'] or file_hash(member) != item['sha256']:
            raise ValueError('export member bytes changed')
    state = unpack(json.loads((directory/'state.c15.json').read_bytes()))
    if evidence_hash(state['result']) != evidence_hash(result):
        raise ValueError('exported controller result changed')
    if not manifest['targets']:
        raise ValueError('completed cycle requires native forecast targets')
    for target in manifest['targets']:
        if Path(target['artifact_path']).name != target['artifact_path']:
            raise ValueError('invalid forecast artifact path')
        artifact = NativeForecastArtifact.from_payload((directory/target['artifact_path']).read_bytes(),
            expected_digest=target['artifact_digest'])
        if artifact.input_hash != learning['input_hash']:
            raise ValueError('feedback input differs from actual exported native input')
    return manifest


class CycleCoordinator:
    def __init__(self, path, *, lessons_path, frozen_memory_path, frozen_memory_sha256,
                 create=False, phase_callback=None):
        self.path = Path(path)
        self.memory = Path(frozen_memory_path)
        self.memory_hash = frozen_memory_sha256
        self.lessons_path = Path(lessons_path)
        if len({self.path.resolve(), self.lessons_path.resolve(), self.memory.resolve()}) != 3:
            raise ValueError('cycle, new lessons and frozen Memory A must be separate')
        self._memory_unchanged()
        self.phase_callback = phase_callback
        self._lock = asyncio.Lock()
        if create:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.lessons_path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open('xb'): pass
            with self.lessons_path.open('xb'): pass
        elif not self.path.is_file() or not self.lessons_path.is_file():
            raise ValueError('retained cycle and lessons databases required')
        self.db = sqlite3.connect(self.path)
        self.lessons = sqlite3.connect(self.lessons_path)
        for db in (self.db, self.lessons):
            db.execute('PRAGMA synchronous=FULL')
        if create:
            self.db.execute('CREATE TABLE stages (request TEXT, stage TEXT, payload BLOB, digest TEXT, PRIMARY KEY(request,stage))')
            self.lessons.execute('CREATE TABLE lessons (request TEXT PRIMARY KEY, available_ns INTEGER, payload BLOB, digest TEXT)')
            self.db.commit(); self.lessons.commit()

    def _memory_unchanged(self):
        if file_hash(self.memory) != self.memory_hash:
            raise ValueError('frozen Memory A identity changed')

    def _load(self, request_id, stage):
        row = self.db.execute('SELECT payload,digest FROM stages WHERE request=? AND stage=?',
                              (request_id, stage)).fetchone()
        if row is None: return None
        value = unpack(json.loads(row[0]))
        if evidence_hash(value) != row[1]: raise ValueError('cycle evidence changed')
        return value

    def _save(self, request_id, stage, value):
        digest = evidence_hash(value)
        old = self._load(request_id, stage)
        if old is not None:
            if evidence_hash(old) != digest: raise ValueError('saved cycle stage changed')
            return old
        with self.db:
            self.db.execute('INSERT INTO stages VALUES (?,?,?,?)',
                (request_id, stage, canonical_bytes(pack(value)), digest))
        return value

    IDENTITY_SUPERSEDE_SUFFIX = '.identity-supersede.json'
    IDENTITY_ACCEPTED_SUFFIX = '.identity-supersede-accepted.json'

    def _binding_supersede(self, request_id, saved, binding):
        """Accept a saved cycle binding that differs only by a host code advance.

        The training identity encodes the hash of every source file, so a host code advance made
        while a cycle is open (2026-09-20: the runner's own resume fixes) changes
        training_identities.code_hash; and because the training checkpoint digest encodes those
        identities, the request plan's controller arm_hash (evidence over the initialization and
        the CURRENT training identity, whose checkpoint_hash is that digest) changes with it while
        the weights, optimizer, sessions and source are the same (run 35528504894 measured exactly
        those two differences). The request, the controller result and the principal request are
        unchanged. Nothing is accepted silently: an operator declaration next to the cycle store
        (<cycles.sqlite>.identity-supersede.json) must name this request and the OLD code_hash it
        supersedes (and the new one, when it names it); an arm_hash difference is accepted only
        when the declaration also names the OLD arm_hash and the controller result is already
        retained (the arm is spent, nothing runs under the new one). The old binding is archived
        under its own stage before the new one replaces it, and the acceptance is appended to
        <cycles.sqlite>.identity-supersede-accepted.json. Any other difference still refuses.
        """
        declared = Path(str(self.path) + self.IDENTITY_SUPERSEDE_SUFFIX)
        if not declared.exists(): return False
        try:
            entries = json.loads(declared.read_bytes())
        except ValueError:
            return False
        old_identities = saved.get('training_identities') if type(saved) is dict else None
        new_identities = binding.get('training_identities')
        if type(old_identities) is not dict or type(new_identities) is not dict: return False
        old_hash, new_hash = old_identities.get('code_hash'), new_identities.get('code_hash')
        if type(old_hash) is not str or type(new_hash) is not str or old_hash == new_hash: return False
        masked = dict(saved, training_identities=dict(old_identities, code_hash=new_hash))
        old_controller, new_controller = saved.get('controller'), binding.get('controller')
        if type(old_controller) is not dict or type(new_controller) is not dict: return False
        old_arm, new_arm = old_controller.get('arm_hash'), new_controller.get('arm_hash')
        arm_change = old_arm != new_arm
        if arm_change:
            if type(old_arm) is not str or type(new_arm) is not str: return False
            if self._load(request_id, 'controller') is None: return False  # the arm must be spent
            masked = dict(masked, controller=dict(old_controller, arm_hash=new_arm))
        if evidence_hash(masked) != evidence_hash(binding): return False
        if not any(type(e) is dict and e.get('request_id') == request_id and e.get('old_code_hash') == old_hash
                   and e.get('new_code_hash') in (None, new_hash)
                   and (not arm_change or e.get('old_arm_hash') == old_arm)
                   for e in (entries if type(entries) is list else [])):
            return False
        archive = 'binding-superseded-' + old_hash[:12]
        self._save(request_id, archive, saved)
        with self.db:
            self.db.execute('UPDATE stages SET payload=?, digest=? WHERE request=? AND stage=?',
                (canonical_bytes(pack(binding)), evidence_hash(binding), request_id, 'binding'))
        accepted = Path(str(self.path) + self.IDENTITY_ACCEPTED_SUFFIX)
        record = dict(schema='FRANKIE_CYCLE_IDENTITY_SUPERSEDE_ACCEPTED_V1', request_id=request_id,
                      old_code_hash=old_hash, new_code_hash=new_hash, archived_stage=archive)
        if arm_change:
            record.update(old_arm_hash=old_arm, new_arm_hash=new_arm)
        existing = json.loads(accepted.read_bytes()) if accepted.exists() else []
        if record not in existing:
            existing.append(record)
            accepted.write_bytes(json.dumps(existing, sort_keys=True, indent=1).encode())
        return True

    EXPORT_PINS = ('boss_commit', 'agent_commit')

    def _export_pin_supersede(self, request_id):
        """OLD export pins the operator declaration names for this request (see _binding_supersede)."""
        declared = Path(str(self.path) + self.IDENTITY_SUPERSEDE_SUFFIX)
        if not declared.exists(): return {}
        try:
            entries = json.loads(declared.read_bytes())
        except ValueError:
            return {}
        accepted = {}
        for entry in (entries if type(entries) is list else []):
            if type(entry) is not dict or entry.get('request_id') != request_id: continue
            for name in self.EXPORT_PINS:
                old = entry.get('old_' + name)
                if type(old) is str and old: accepted.setdefault(name, set()).add(old)
        return accepted

    def _record_pin_supersede(self, request_id, manifest, export_args):
        """Append one acceptance record per retained export pin that differs from the live one."""
        records = [dict(schema='FRANKIE_CYCLE_EXPORT_PIN_SUPERSEDE_ACCEPTED_V1', request_id=request_id,
                        pin=name, old=manifest[name], new=export_args[name])
                   for name in self.EXPORT_PINS if manifest[name] != export_args[name]]
        if not records: return
        accepted = Path(str(self.path) + self.IDENTITY_ACCEPTED_SUFFIX)
        existing = json.loads(accepted.read_bytes()) if accepted.exists() else []
        added = [record for record in records if record not in existing]
        if added:
            accepted.write_bytes(json.dumps(existing + added, sort_keys=True, indent=1).encode())

    def _observe(self, phase, request_id):
        if self.phase_callback is not None:
            self.phase_callback(phase, request_id=request_id)

    def _save_lessons(self, request_id, feedback, envelope, training):
        record = dict(request_id=request_id, available_ns=feedback.available_ns,
            feedback_hash=feedback.digest, principal_receipt_hash=feedback.principal_receipt_hash,
            training_checkpoint_hash=training['checkpoint_hash'], lessons=envelope['lessons'],
            frozen_memory_sha256=self.memory_hash)
        digest = evidence_hash(record)
        with self.lessons:
            old = self.lessons.execute('SELECT digest FROM lessons WHERE request=?', (request_id,)).fetchone()
            if old is not None and old[0] != digest: raise ValueError('saved new lessons changed')
            if old is None:
                self.lessons.execute('INSERT INTO lessons VALUES (?,?,?,?)',
                    (request_id, feedback.available_ns, canonical_bytes(pack(record)), digest))
        return dict(lessons_hash=digest, available_ns=feedback.available_ns)

    def lessons_available(self, cutoff_ns):
        if type(cutoff_ns) is not int: raise ValueError('integer lesson availability cutoff required')
        result = []
        for raw, digest in self.lessons.execute('SELECT payload,digest FROM lessons WHERE available_ns<=? ORDER BY available_ns,request', (cutoff_ns,)):
            value = unpack(json.loads(raw))
            if evidence_hash(value) != digest: raise ValueError('new lessons evidence changed')
            result.append(value)
        return result

    def _check_chronology(self, request_id, as_of):
        """A learned state may only serve at or after its feedback availability."""
        requests = self.db.execute("SELECT request FROM stages WHERE stage='binding' AND request<>?",
                                   (request_id,)).fetchall()
        for (previous,) in requests:
            if self._load(previous, 'complete') is None:
                raise ValueError('finish the retained prior cycle before starting another request')
            feedback = self._load(previous, 'feedback')
            if feedback is None or as_of < feedback['feedback']['available_ns']:
                raise ValueError('new request precedes learned feedback availability')

    async def run(self, *, request_id, controller_factory, controller_kwargs, export_kwargs,
                  principal, checkpoint, learner_factory, learning_kwargs):
        """Factories are lazy; export_kwargs may read final checkpoints from result.

        principal is FrankiePrincipalAdapter (prepare/execute/recover/verify).
        learner_factory must return the configured NativeForecastLearner; its step
        is invoked only inside BossTrainingCheckpoint.apply_completed. Sessions,
        source/input hashes, full context cursor and learning cutoff are explicit.
        """
        if type(request_id) is not str or not request_id: raise ValueError('request ID required')
        if 'request_id' in controller_kwargs or 'request_id' in learning_kwargs:
            raise ValueError('request ID is owned by cycle coordinator')
        for forbidden in ('feedback', 'expected_feedback_hash'):
            if forbidden in learning_kwargs: raise ValueError('feedback is owned by verified principal')
        binding = dict(request_id=request_id, controller=_plain(controller_kwargs),
            learning=_plain(learning_kwargs), training_identities=checkpoint.identities,
            frozen_memory_sha256=self.memory_hash)
        async with self._lock:
            with _exclusive(str(self.path)+'.lock'):
                saved = self._load(request_id, 'binding')
                if (saved is not None and evidence_hash(saved) != evidence_hash(binding)
                        and not self._binding_supersede(request_id, saved, binding)):
                    raise ValueError('cycle request identity changed')
                # The lookup deliberately precedes model/controller construction.
                completed = self._load(request_id, 'complete')
                if completed is not None: return completed
                self._check_chronology(request_id, learning_kwargs['as_of'])
                self._memory_unchanged()
                self._save(request_id, 'binding', binding)
                result = self._load(request_id, 'controller')
                if result is None:
                    self._observe('boss_reasoning', request_id)
                    controller = controller_factory()
                    result = await controller.refresh(request_id=request_id, **controller_kwargs)
                    if (result.get('request_id') != request_id
                            or result.get('status') not in ('complete', 'incomplete')):
                        raise ValueError('cycle requires actual verified integrated controller result')
                    self._save(request_id, 'controller', result)
                result_hash = evidence_hash(result)
                directory = self.path.parent/('handoff-'+hashlib.sha256(request_id.encode()).hexdigest())
                envelope = self._load(request_id, 'principal_output')
                if envelope is None:
                    self._observe('causal_handoff', request_id)
                    export_args = export_kwargs(result) if callable(export_kwargs) else dict(export_kwargs)
                    if export_args.get('request_id', request_id) != request_id:
                        raise ValueError('export request identity differs from cycle request')
                    export_args = dict(export_args, request_id=request_id)
                    manifest = _export_verified(directory, export_args, result, learning_kwargs,
                                                superseded=self._export_pin_supersede(request_id))
                    self._record_pin_supersede(request_id, manifest, export_args)
                    self._save(request_id, 'export', manifest)
                    attachment = self._load(request_id, 'attachment')
                    if attachment is None:
                        attachment = await asyncio.to_thread(principal.prepare, directory)
                        self._save(request_id, 'attachment', attachment)
                    intent = self._load(request_id, 'principal_intent')
                    self._observe('frankie_calculations', request_id)
                    if intent is not None:
                        # Saved intent precedes the adapter's durable request. Only the adapter's
                        # explicit PrincipalNotDispatched proves nothing was sent; PrincipalPending
                        # and every other failure propagate, and a missing result stays ambiguous.
                        try:
                            envelope = await asyncio.to_thread(principal.recover, request_id, attachment)
                        except _not_dispatched_signals():
                            envelope = await asyncio.to_thread(principal.execute, request_id, attachment)
                        if envelope is None:
                            raise AmbiguousPrincipalCall('principal completion unknown; retained output or explicit reconciliation required')
                    else:
                        self._save(request_id, 'principal_intent', dict(request_id=request_id,
                            attachment_hash=evidence_hash(attachment), controller_result_hash=result_hash))
                        envelope = await asyncio.to_thread(principal.execute, request_id, attachment)
                    self._save(request_id, 'principal_output', envelope)
                feedback = principal.verify(envelope, request_id=request_id,
                    input_hash=learning_kwargs['input_hash'], source_hash=learning_kwargs['source_hash'],
                    learning_cutoff_ns=learning_kwargs['learning_cutoff_ns'])
                if not isinstance(feedback, FrankieFeedback): raise ValueError('typed principal feedback required')
                if type(envelope.get('lessons')) not in (list, tuple):
                    raise ValueError('principal must explicitly supply separate lessons')
                if (feedback.request_id != request_id or feedback.input_hash != learning_kwargs['input_hash']
                        or feedback.source_hash != learning_kwargs['source_hash']
                        or not learning_kwargs['as_of'] <= feedback.available_ns <= learning_kwargs['learning_cutoff_ns']):
                    raise ValueError('principal feedback causal binding differs')
                # Roster check precedes both the saved feedback and the training update so a
                # rejected envelope never enters apply_completed and never poisons the checkpoint.
                if (type(feedback.sessions) is not tuple or tuple(s.session_id for s in feedback.sessions)
                        != _requested_session_ids(learning_kwargs['sessions'])):
                    raise ValueError('principal feedback session roster differs from requested sessions in order')
                self._save(request_id, 'feedback', dict(feedback=asdict(feedback), feedback_hash=feedback.digest,
                    envelope_hash=evidence_hash(envelope)))
                self._memory_unchanged()
                self._observe('native_learning', request_id)
                def update():
                    learner = learner_factory()
                    return learner.step(request_id=request_id, feedback=feedback,
                        expected_feedback_hash=feedback.digest, **learning_kwargs)
                training = checkpoint.apply_completed(request_id, controller_result_hash=result_hash,
                    training_cursor=learning_kwargs['through_cursor'], update=update)
                self._save(request_id, 'training', training)
                self._observe('checkpoint_readback', request_id)
                lessons = self._save_lessons(request_id, feedback, envelope, training)
                self._memory_unchanged()
                completed = dict(schema='FRANKIE_BOSS_FEEDBACK_CYCLE_V1', request_id=request_id,
                    controller_result_hash=result_hash, feedback_hash=feedback.digest, training=training, **lessons)
                self._save(request_id, 'complete', completed)
                self._observe('saved_completion', request_id)
                return completed

    def close(self):
        self.db.close(); self.lessons.close()
