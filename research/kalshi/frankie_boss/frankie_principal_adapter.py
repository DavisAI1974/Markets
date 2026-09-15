"""Executable receiver and agent-session boundary for new BOSS feedback.

The session executor is supplied by the authorized host, never inferred from an
installed CLI. Historical section evidence is reused with its original hashes;
only the feedback is newly authored. This module computes no market labels.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid

try:
    from .native_forecast_learning import FrankieFeedback, SessionFeedback, TimingLabel, ValueLabel
except ImportError:
    from native_forecast_learning import FrankieFeedback, SessionFeedback, TimingLabel, ValueLabel

FROZEN_MEMORY_SHA256 = '4a47b09d5b19a9165c570f9432d2f3190a657843009536d5dad9a6bd99d83f4a'

SECTIONS = ('4.0', '4.0b') + tuple(f'4.{i}' for i in range(1, 17))


class PrincipalNotDispatched(RuntimeError):
    """No adapter request exists: the host provably has not dispatched a session."""


class PrincipalPending(RuntimeError):
    """An existing session must finish or supply its retained response; never retry."""


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_witness(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('regular evidence file required')
    count, hashed = 0, hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            count += len(block)
            hashed.update(block)
    return {'bytes': count, 'sha256': hashed.hexdigest()}


def _write(path, body):
    with Path(path).open('xb') as handle:
        handle.write(canonical(body))
        handle.flush()
        os.fsync(handle.fileno())


def _checked_receipt(path):
    body = json.loads(Path(path).read_bytes())
    if body.get('receipt_sha256') != digest({k: v for k, v in body.items() if k != 'receipt_sha256'}):
        raise ValueError('receipt self hash differs')
    return body


def rebind_delivery_receipt(original, expected_original_sha256, local_directory, output):
    """Attest a new local delivery by rehashing every original plaintext witness.

    Original receipt bytes are retained and independently pinned. The new receipt
    explicitly cites those bytes and does not impersonate the historical fetch.
    """
    if file_witness(original)['sha256'] != expected_original_sha256:
        raise ValueError('original delivery receipt differs from independent pin')
    prior = _checked_receipt(original)
    body = json.loads(canonical(prior))
    local = Path(local_directory).resolve()
    for entry in body['ledgers'].values():
        target = local / entry['file']
        if target.parent != local:
            raise ValueError('ledger path escapes delivery directory')
        witness = file_witness(target)
        if witness != {'bytes': entry['plain_bytes_expected'], 'sha256': entry['plain_sha256_expected']}:
            raise ValueError(f'plaintext ledger differs: {target.name}')
        entry.update(local_path=str(target), plain_bytes_observed=witness['bytes'],
                     plain_sha256_observed=witness['sha256'], status='VERIFIED')
    for name, entry in body['objects'].items():
        target = local / name
        if target.parent != local:
            raise ValueError('object path escapes delivery directory')
        witness = file_witness(target)
        if witness['bytes'] != entry['content_length_expected']:
            raise ValueError(f'delivery object size differs: {name}')
        expected = entry.get('sha256_expected') or entry.get('sha256_observed')
        if expected and expected != witness['sha256']:
            raise ValueError(f'delivery object hash differs: {name}')
        entry.update(local_path=str(target), bytes_observed=witness['bytes'],
                     sha256_observed=witness['sha256'], status='VERIFIED')
    body['out_dir'] = str(local)
    body['local_redelivery'] = {'method': 'rehash_retained_plaintext_and_objects',
        'original_receipt_file_sha256': expected_original_sha256,
        'original_receipt_sha256': prior['receipt_sha256']}
    body['receipt_sha256'] = digest({k: v for k, v in body.items() if k != 'receipt_sha256'})
    _write(output, body)
    return body


def retained_knowledge(receipt_path, receipt_sha256, bundle_path, bundle_sha256):
    """Verify historical bytes directly; never rebuild from post-Sunday checkout."""
    if file_witness(receipt_path)['sha256'] != receipt_sha256:
        raise ValueError('retained knowledge receipt bytes differ')
    receipt = _checked_receipt(receipt_path)
    witness = file_witness(bundle_path)
    if witness != {'bytes': receipt['model_visible_context_bytes'],
                   'sha256': receipt['model_visible_context_sha256']} or witness['sha256'] != bundle_sha256:
        raise ValueError('retained knowledge bundle bytes differ')
    seeds = [a for a in receipt['artifacts'] if a['id'] == 'seed_a_memory_20260902']
    if len(seeds) != 1 or seeds[0]['sha256'] != FROZEN_MEMORY_SHA256 or seeds[0]['bytes'] != 166700:
        raise ValueError('only the frozen pre-Sunday Memory A is admissible')
    bundle = Path(bundle_path).read_bytes()
    marker = ('===== BEGIN KNOWLEDGE seed_a_memory_20260902 ' + FROZEN_MEMORY_SHA256 + ' =====\n').encode()
    if bundle.count(marker) != 1:
        raise ValueError('frozen prior memory missing from retained bundle')
    seed = bundle.split(marker, 1)[1].split(b'===== END KNOWLEDGE seed_a_memory_20260902 =====', 1)[0]
    if not any(len(raw) == 166700 and hashlib.sha256(raw).hexdigest() == FROZEN_MEMORY_SHA256
               for raw in (seed, seed[:-1])):
        raise ValueError('embedded frozen Memory A bytes differ')
    return receipt


class FrankiePrincipalAdapter:
    """Durable outbox/inbox around a real frozen receiver and authorized session.

    preparation: kwargs accepted by frozen prepare_boss_attachment CLI (except
    directory/output_directory, supplied here). render: explicit emitter CLI
    arguments including pinned pre-Sunday knowledge-receipt. protected_files and
    section_evidence map names to {path, bytes, sha256} independently trusted by
    the host. session_executor(request) may dispatch a host agent and return its
    response, or be None for an outbox consumed by the host's session tools.
    """
    def __init__(self, *, receiver_root, receiver_commit, python, directory,
                 preparation, render, protected_files, section_evidence,
                 feedback_contract, session_executor=None):
        self.receiver_root = Path(receiver_root).resolve()
        self.receiver_commit = receiver_commit
        self.python = str(python)
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        if self.directory.is_relative_to(self.receiver_root):
            raise ValueError('principal evidence must be outside frozen receiver checkout')
        self.preparation, self.render = dict(preparation), dict(render)
        for key in ('knowledge-receipt', 'knowledge-receipt-sha256', 'knowledge-bundle-sha256'):
            if not self.render.get(key):
                raise ValueError('explicit pinned pre-Sunday knowledge receipt and bundle required')
        common_render = {'knowledge-receipt', 'knowledge-receipt-sha256', 'knowledge-bundle-sha256'}
        if self.render.get('retained-prompt'):
            if set(self.render) - common_render - {'retained-prompt', 'retained-prompt-sha256'}:
                raise ValueError('unexpected retained-prompt configuration')
            if not self.render.get('retained-prompt-sha256'):
                raise ValueError('retained prompt independent hash required')
        else:
            if set(self.render) - common_render - {'result', 'delivery-receipt', 'stream-receipt',
                    'outputs-receipt', 'sealed-proof', 'ledger-dir', 'evidence-uri'}:
                raise ValueError('unexpected emitter configuration')
            for render_key, preparation_key in (('result', 'result_path'), ('delivery-receipt', 'delivery_receipt')):
                if preparation_key not in self.preparation:
                    raise ValueError('preparation result and delivery paths required')
                supplied = self.render.get(render_key, self.preparation[preparation_key])
                if Path(supplied).resolve() != Path(self.preparation[preparation_key]).resolve():
                    raise ValueError('emitter paths differ from receiver preparation')
                self.render[render_key] = str(Path(supplied).resolve())
        if set(section_evidence) != set(SECTIONS) or not protected_files:
            raise ValueError('all 18 preserved sections and frozen memory witnesses required')
        self.protected_files = protected_files
        self.section_evidence = section_evidence
        self.feedback_contract = json.loads(canonical(feedback_contract))
        self.session_executor = session_executor

    def _config_hash(self):
        return digest({'receiver_root': str(self.receiver_root), 'receiver_commit': self.receiver_commit,
            'python': self.python, 'preparation': {k: str(v) for k, v in self.preparation.items()},
            'render': {k: str(v) for k, v in self.render.items()},
            'protected_files': self.protected_files, 'section_evidence': self.section_evidence,
            'feedback_contract': self.feedback_contract, 'mechanism': 'AGENT_SESSION'})

    def _code(self):
        observed = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=self.receiver_root, text=True).strip()
        if observed != self.receiver_commit:
            raise ValueError('frozen receiver commit differs')
        changed = subprocess.check_output(['git', 'status', '--porcelain', '--', 'research'], cwd=self.receiver_root, text=True)
        if changed.strip():
            raise ValueError('frozen receiver sources changed')

    def _files(self):
        for witness in list(self.protected_files.values()) + list(self.section_evidence.values()):
            if file_witness(witness['path']) != {k: witness[k] for k in ('bytes', 'sha256')}:
                raise ValueError('frozen memory or preserved section evidence changed')

    def _run(self, module, args):
        self._code()
        command = [self.python, '-m', 'research.kalshi.frankie_raw_mbo_benchmark.' + module]
        for name, value in args.items():
            command.extend(['--' + name.replace('_', '-'), str(value)])
        result = subprocess.run(command, cwd=self.receiver_root, capture_output=True, check=False)
        if result.returncode:
            raise ValueError(f'{module} refused: ' + result.stderr.decode('utf-8', errors='replace')[-2000:])
        self._code()

    def prepare(self, handoff_directory):
        self._files()
        config = {'config_hash': self._config_hash()}
        config_path = self.directory / 'adapter-config.json'
        if config_path.exists():
            if json.loads(config_path.read_bytes()) != config:
                raise ValueError('retained principal configuration differs')
        else:
            _write(config_path, config)
        handoff_directory = str(Path(handoff_directory).resolve())
        prepared = self.directory / 'receiver'
        receipt_file = prepared / 'preparation-receipt.json'
        if prepared.exists() and not receipt_file.exists():
            if prepared.is_symlink() or prepared.resolve().parent != self.directory:
                raise ValueError('unsafe partial receiver directory')
            retained = self.directory / ('receiver.partial-' + uuid.uuid4().hex)
            prepared.rename(retained)  # preserve incomplete evidence; never overwrite/delete
        if not receipt_file.exists():
            self._run('prepare_boss_attachment', dict(self.preparation,
                directory=handoff_directory, output_directory=prepared))
        receipt = _checked_receipt(receipt_file)
        if receipt['input_paths']['directory'] != handoff_directory:
            raise ValueError('retained receiver receipt belongs to another handoff')
        self._check_preparation(receipt)
        bundle = Path(self.render['knowledge-receipt']).parent / 'KNOWLEDGE_BUNDLE.md'
        retained_knowledge(self.render['knowledge-receipt'], self.render['knowledge-receipt-sha256'],
                           bundle, self.render['knowledge-bundle-sha256'])
        prompt = self.directory / 'prompt.md'
        if not prompt.exists():
            if self.render.get('retained-prompt'):
                self._render_retained(prompt, prepared)
            else:
                self._run('emit_frankie_spawn', dict({k:v for k,v in self.render.items() if k not in ('knowledge-receipt-sha256', 'knowledge-bundle-sha256')}, output=prompt,
                    **{'boss-attachment-request': prepared / 'attachment-request.json'}))
        knowledge_bundle = Path(self.render['knowledge-receipt']).parent / 'KNOWLEDGE_BUNDLE.md'
        attachment = {'config_hash': self._config_hash(), 'preparation_receipt': receipt, 'prompt': str(prompt),
            'knowledge_bundle': str(knowledge_bundle), 'knowledge_bundle_witness': file_witness(knowledge_bundle),
            'prompt_witness': file_witness(prompt), 'section_evidence': self.section_evidence,
            'protected_files': self.protected_files, 'feedback_contract': self.feedback_contract}
        attachment['attachment_hash'] = digest(attachment)
        return attachment

    def _receiver_input_block(self, prepared):
        self._code()
        # Existing frozen verifier remains authoritative; this code only transports its bytes.
        program = ("import sys; from research.kalshi.frankie_raw_mbo_benchmark.native_boss_attachment "
            "import load_request,verify_attachment; "
            "v=verify_attachment(load_request(sys.argv[1]),result_path=sys.argv[2],delivery_receipt=sys.argv[3]); "
            "sys.stdout.buffer.write(v.input_block().encode('utf-8'))")
        result = subprocess.run([self.python, '-c', program, str(prepared / 'attachment-request.json'),
            str(self.preparation['result_path']), str(self.preparation['delivery_receipt'])],
            cwd=self.receiver_root, capture_output=True)
        if result.returncode:
            raise ValueError('frozen receiver refused retained-prompt attachment: ' +
                result.stderr.decode('utf-8', errors='replace')[-2000:])
        self._code()
        return result.stdout

    def _render_retained(self, prompt, prepared):
        prior = Path(self.render['retained-prompt'])
        if file_witness(prior)['sha256'] != self.render['retained-prompt-sha256']:
            raise ValueError('retained historical prompt bytes differ')
        bundle = Path(self.render['knowledge-receipt']).parent / 'KNOWLEDGE_BUNDLE.md'
        retained_knowledge(self.render['knowledge-receipt'], self.render['knowledge-receipt-sha256'],
                           bundle, self.render['knowledge-bundle-sha256'])
        original = prior.read_bytes()
        original_copy = self.directory / 'historical-prompt.md'
        if original_copy.exists():
            if original_copy.read_bytes() != original:
                raise ValueError('saved historical prompt changed')
        else:
            with original_copy.open('xb') as handle:
                handle.write(original)
        block = self._receiver_input_block(prepared)
        prefix = ("# Current authorized continuation\n"
            "Sunday 2021-10-03 is the sole source and run day. No separate source day or October 1 "
            "prerequisite applies. Reuse completed principal-authored sections with their original "
            "authorship; author only the new source convention and BOSS feedback. Preserve frozen "
            "pre-Sunday Memory A; store new lessons separately. The original historical prompt follows "
            "unchanged for provenance, followed by the newly verified BOSS attributed input. Its "
            "multi-day sequencing is overridden by this current single-day instruction.\n"
            "Actual local delivery: " + str(self.preparation['delivery_receipt']) + "\n"
            "Feedback contract: " + canonical(self.feedback_contract).decode() + "\n\n"
            "# Preserved historical principal prompt (exact bytes follow)\n").encode()
        with Path(prompt).open('xb') as handle:
            handle.write(prefix + original + block)
            handle.flush()
            os.fsync(handle.fileno())

    def _check_preparation(self, receipt):
        self._code()
        if receipt['executing_agent_commit'] != self.receiver_commit:
            raise ValueError('preparation ran a different receiver commit')
        pins = Path(self.preparation['pins_path'])
        if file_witness(pins)['sha256'] != self.preparation['expected_pins_sha256']:
            raise ValueError('independent preparation pins changed')
        if receipt['pins_file'] != file_witness(pins):
            raise ValueError('retained preparation belongs to different pins')
        for name, path in (('result', self.preparation['result_path']),
                           ('delivery_receipt', self.preparation['delivery_receipt']),
                           ('mapping', self.preparation['mapping_artifact'])):
            if file_witness(path) != receipt['inputs'][name]:
                raise ValueError('prepared input file changed')
        handoff = Path(receipt['input_paths']['directory'])
        if file_witness(handoff / 'manifest.json') != receipt['inputs']['manifest']:
            raise ValueError('prepared manifest changed')
        manifest = json.loads((handoff / 'manifest.json').read_bytes())
        for item in manifest['files']:
            member = handoff / item['path']
            if member.resolve().parent != handoff.resolve() or file_witness(member) != {
                    'bytes': item['bytes'], 'sha256': item['sha256']}:
                raise ValueError('prepared BOSS attachment member changed')
        for name, witness in receipt['outputs'].items():
            if file_witness(self.directory / 'receiver' / name) != witness:
                raise ValueError('receiver preparation output changed')

    def _request(self, request_id, attachment):
        self._files()
        if attachment.get('config_hash') != self._config_hash():
            raise ValueError('principal configuration differs from retained attachment')
        if attachment.get('attachment_hash') != digest({k: v for k, v in attachment.items() if k != 'attachment_hash'}):
            raise ValueError('attachment record changed')
        if file_witness(attachment['prompt']) != attachment['prompt_witness']:
            raise ValueError('principal prompt changed')
        if file_witness(attachment['knowledge_bundle']) != attachment['knowledge_bundle_witness']:
            raise ValueError('principal knowledge bundle changed')
        self._check_preparation(attachment['preparation_receipt'])
        return {'schema': 'FRANKIE_BOSS_SESSION_REQUEST_V1', 'request_id': request_id,
            'attachment': attachment, 'mechanism': 'AGENT_SESSION',
            'instruction': ('Read the full delivered causal evidence and actual BOSS attributed input. '
                'Reuse the preserved Frankie-authored 18-section evidence with its original authorship; '
                'do not rerun completed calculations or substitute runner findings. This authorized run '
                'is Sunday only and requires no separate source day. Preserve Memory A. Author new '
                'feedback and lessons against feedback_contract; use null for unavailable values. '
                'Cite every retained section hash. Supply feedback without principal_receipt_hash, '
                'lessons, sections (section ID to retained SHA256), session_id and '
                'model_identity_as_reported_by_session. The host attests actual session identity.')}

    def execute(self, request_id, attachment):
        request = self._request(request_id, attachment)
        path = self.directory / 'session-request.json'
        if path.exists():
            if json.loads(path.read_bytes()) != request:
                raise ValueError('session request identity changed')
            recovered = self.recover(request_id, attachment)
            if recovered is not None:
                return recovered
            raise PrincipalPending('existing principal intent has no completed response; do not resubmit')
        _write(path, request)  # durable intent before the session tool/remote call
        if self.session_executor is None:
            raise PrincipalPending(f'authorized host session must consume {path}')
        dispatched = self.session_executor(request)
        response_path = self.directory / 'session-response.json'
        if response_path.exists():
            # A host waiter may receive the response through the separately
            # locked, validating recorder. Never overwrite that immutable record.
            if json.loads(response_path.read_bytes()) != dispatched:
                raise ValueError('recorded principal response differs from host return')
            self._attest_host(dispatched['response'], dispatched['host_attestation'], request)
        else:
            self.record_session_response(dispatched['response'], host_attestation=dispatched['host_attestation'])
        return self.recover(request_id, attachment)

    def _attest_host(self, response, host_attestation, request):
        if (not isinstance(response, dict) or not isinstance(host_attestation, dict) or
                any(not isinstance(response.get(k),str) or not response[k].strip()
                    for k in ('session_id','model_identity_as_reported_by_session'))):
            raise ValueError('actual session identity and host attestation are required')
        expected = {'schema': 'FRANKIE_HOST_AGENT_SESSION_ATTESTATION_V1', 'mechanism': 'AGENT_SESSION',
            'request_sha256': digest(request), 'response_sha256': digest(response),
            'session_id': response['session_id'],
            'model_identity_as_reported_by_session': response['model_identity_as_reported_by_session']}
        if any(host_attestation.get(k) != v for k,v in expected.items()):
            raise ValueError('host attestation does not bind the actual request/response/session')
        record = host_attestation.get('host_record')
        if not isinstance(record, dict) or set(record) != {'path', 'bytes', 'sha256'}:
            raise ValueError('independent host session record witness required')
        if file_witness(record['path']) != {k:record[k] for k in ('bytes', 'sha256')}:
            raise ValueError('host session record bytes changed')
        host_record = json.loads(Path(record['path']).read_bytes())
        if any(host_record.get(k) != v for k,v in expected.items()) or not host_record.get('host_authority'):
            raise ValueError('host record does not attest this session response')
        return host_attestation

    def record_session_response(self, response, *, host_attestation):
        """Host-only: require its own retained dispatch/output witness, not model claims."""
        request_path = self.directory / 'session-request.json'
        if not request_path.exists():
            raise PrincipalNotDispatched('response cannot precede durable principal intent')
        self._files()
        request = json.loads(request_path.read_bytes())
        self._attest_host(response, host_attestation, request)
        _write(self.directory / 'session-response.json', {'response':response, 'host_attestation':host_attestation})

    def recover(self, request_id, attachment):
        request_path, response_path = (self.directory / name for name in ('session-request.json', 'session-response.json'))
        if not request_path.exists():
            raise PrincipalNotDispatched('no adapter request exists; no session was dispatched')
        if not response_path.exists():
            raise PrincipalPending('durable request exists without a response; wait for that session')
        request = self._request(request_id, attachment)
        if json.loads(request_path.read_bytes()) != request:
            raise ValueError('retained principal intent differs')
        retained = json.loads(response_path.read_bytes())
        response = retained['response']
        host_attestation = self._attest_host(response, retained['host_attestation'], request)
        for name in ('session_id', 'model_identity_as_reported_by_session'):
            if not isinstance(response.get(name), str) or not response[name].strip():
                raise ValueError('actual agent session identity is required')
        if response.get('request_sha256') != digest(request):
            raise ValueError('session response does not attest this exact request')
        if response.get('sections') != {k: v['sha256'] for k, v in self.section_evidence.items()}:
            raise ValueError('all 18 preserved section hashes must be cited exactly')
        receipt = {'schema': 'FRANKIE_BOSS_SESSION_RECEIPT_V1', 'mechanism': 'AGENT_SESSION',
            'session_id': response['session_id'],
            'model_identity_as_reported_by_session': response['model_identity_as_reported_by_session'],
            'request_sha256': digest(request), 'response_sha256': digest(response),
            'attachment_hash': attachment['attachment_hash'], 'host_attestation_hash': digest(host_attestation)}
        receipt['receipt_sha256'] = digest(receipt)
        feedback = dict(response['feedback'])
        if 'principal_receipt_hash' in feedback:
            raise ValueError('principal must not mint its own host receipt hash')
        feedback['principal_receipt_hash'] = receipt['receipt_sha256']
        return {'feedback': feedback, 'lessons': response['lessons'], 'principal_receipt': receipt}

    def verify(self, envelope, request_id, input_hash, source_hash, learning_cutoff_ns):
        request = json.loads((self.directory / 'session-request.json').read_bytes())
        trusted = self.recover(request_id, request['attachment'])
        if trusted != envelope:
            raise ValueError('feedback envelope differs from retained session response')
        body = envelope['feedback']
        if (body['request_id'], body['input_hash'], body['source_hash']) != (request_id, input_hash, source_hash):
            raise ValueError('principal feedback request/input/source binding differs')
        if type(body['available_ns']) is not int or not 0 <= body['available_ns'] <= learning_cutoff_ns:
            raise ValueError('principal feedback is not causally available')
        sessions = tuple(SessionFeedback(session_id=s['session_id'],
            timing=tuple(TimingLabel(**v) for v in s['timing']),
            gap=ValueLabel(**s['gap']) if s['gap'] is not None else None,
            path=tuple(ValueLabel(**v) for v in s['path'])) for s in body['sessions'])
        return FrankieFeedback(**dict(body, sessions=sessions))
