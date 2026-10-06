"""Immutable, host-attested outcome follow-up for a retained pending forecast.

This adapter does not dispatch a session, derive labels, prepare model inputs or
update a model. The authorized host supplies the later response and its existing
independent session attestation. The coordinator alone completes native learning.
Callers hold their existing actual-host/coordinator single-writer locks.
"""
from dataclasses import asdict
import json
from pathlib import Path
from types import SimpleNamespace

from .c15_journal import evidence_hash
from .forecast_contract import sha256_digest
from .frankie_principal_adapter import PrincipalPending, digest, json_form
from .native_forecast_learning import (
    FrankieFeedback, NativeForecastLearner, SessionFeedback, TimingLabel, ValueLabel,
)
from .native_forecast_refresh import session_registry_hash


CONTINUATION_SCHEMA = 'FRANKIE_PENDING_FEEDBACK_CONTINUATION_V1'
REQUEST_SCHEMA = 'FRANKIE_PENDING_TARGET_OUTCOME_REQUEST_V1'
RESPONSE_SCHEMA = 'FRANKIE_PENDING_TARGET_OUTCOME_RESPONSE_V1'


class PendingTargetFeedbackAdapter:
    """Wrap the actual source principal; never accept an unauthenticated envelope.

    ``original_envelope`` comes from the coordinator's retained principal output.
    ``sessions`` and their hash come from the original authored source contract.
    Re-authentication uses the original concrete adapter on every operation,
    including its mandatory classroom completion and independent host witnesses.
    """

    def __init__(self, source_principal, *, original_envelope, sessions,
                 expected_sessions_hash):
        if session_registry_hash(sessions) != expected_sessions_hash:
            raise ValueError('outcome follow-up requires the original complete session roster')
        if source_principal.session_executor is not None:
            raise ValueError('outcome follow-up requires a recovery-only source principal')
        self.source_principal = source_principal
        self.original_envelope = original_envelope
        self.sessions = sessions
        self.expected_sessions_hash = expected_sessions_hash

    def _request(self, request_id, continuation):
        required = {'schema', 'request_id', 'original_binding_hash',
                    'controller_result_hash', 'original_principal_output_hash',
                    'pending_feedback_hash', 'original_export_hash', 'learning'}
        if (type(continuation) is not dict or set(continuation) != required
                or continuation['schema'] != CONTINUATION_SCHEMA
                or continuation['request_id'] != request_id):
            raise ValueError('exact pending-feedback continuation identity required')
        for key in required - {'schema', 'request_id', 'learning'}:
            sha256_digest(continuation[key], key)
        if evidence_hash(self.original_envelope) != continuation['original_principal_output_hash']:
            raise ValueError('original principal output differs from continuation')
        learning = continuation['learning']
        source = self.source_principal
        contract = source.feedback_contract
        cutoff = learning['learning_cutoff_ns']
        if (type(cutoff) is not int or type(learning['as_of']) is not int
                or cutoff <= learning['as_of']
                or contract.get('learning_cutoff_ns') is not None
                or contract.get('feedback_status') != 'pending_target_outcomes'):
            raise ValueError('pending source and explicit later learning cutoff required')
        for key in ('as_of', 'through_cursor', 'source_hash', 'expected_sessions_hash'):
            if learning[key] != contract[key]:
                raise ValueError('outcome continuation changed original ' + key)
        if learning['expected_sessions_hash'] != self.expected_sessions_hash:
            raise ValueError('outcome continuation changed session roster hash')
        plain_sessions = [(asdict(target), asdict(session)) for target, session in self.sessions]
        if json_form(learning['sessions']) != json_form(plain_sessions):
            raise ValueError('outcome continuation changed original target/session values')
        pending = self.original_envelope.get('pending_feedback')
        if (self.original_envelope.get('feedback') is not None
                or self.original_envelope.get('feedback_status') != 'pending_target_outcomes'
                or not isinstance(pending, dict)):
            raise ValueError('original pending principal envelope required')
        # Calling the concrete adapter preserves initial and correction session
        # verification. recover() cannot dispatch; no new classroom is requested.
        if source.verify(self.original_envelope, request_id=request_id,
                input_hash=learning['input_hash'], source_hash=learning['source_hash'],
                learning_cutoff_ns=None) is not None:
            raise ValueError('original source principal is not awaiting outcomes')
        target = contract.get('forecast_target')
        if not target or json_form(pending.get('forecast_target')) != json_form(target):
            raise ValueError('pending target differs from original authored forecast target')
        original_request = json.loads((source.directory / 'session-request.json').read_bytes())
        original = json.loads((source.directory / 'session-response.json').read_bytes())
        source._attest_host(original['response'], original['host_attestation'], original_request)
        host_path = original['host_attestation']['host_record']['path']
        authority = json.loads(Path(host_path).read_bytes())['host_authority']
        return dict(schema=REQUEST_SCHEMA, mechanism='AGENT_SESSION', request_id=request_id,
            continuation=json_form(continuation), continuation_hash=evidence_hash(continuation),
            original_request_sha256=digest(original_request),
            original_response_sha256=digest(original['response']),
            original_principal_receipt=json_form(self.original_envelope['principal_receipt']),
            original_session_id=original['response']['session_id'],
            host_authority=authority, forecast_target=json_form(target),
            original_feedback_contract=json_form(contract), learning_cutoff_ns=cutoff,
            instruction=(
                'Supply separately observed target outcomes for this original pending forecast. '
                'Preserve its request, source, input, target and entire session roster. '
                'original_feedback_contract remains the unchanged pending contract; '
                'learning_cutoff_ns is the separately declared later outcome cutoff. '
                'Do not rerun the forecast or classroom, derive replacement predictions, change '
                'the objective, or invent unavailable labels. Return schema '
                + RESPONSE_SCHEMA + ', request_sha256, continuation_hash, forecast_target, '
                'session_id, model_identity_as_reported_by_session, feedback without '
                'principal_receipt_hash, and lessons containing only this later outcome work. '
                'Every label requires its actual observation evidence hash and availability; '
                'STOP requires observations through the target session close. The authorized '
                'host must independently attest this exact request and response.'))

    def _paths(self, continuation):
        directory = self.source_principal.directory / (
            'pending-target-feedback-' + evidence_hash(continuation))
        return directory / 'request.c15.json', directory / 'response.c15.json'

    def _retained_request(self, request_id, continuation, *, create):
        from .sunday_execution import _load, _save
        request = self._request(request_id, continuation)
        request_path, response_path = self._paths(continuation)
        if not request_path.exists():
            if not create:
                raise ValueError('outcome response cannot precede durable follow-up request')
            request_path.parent.mkdir(parents=True, exist_ok=True)
            _save(request_path, request)
        if _load(request_path) != request:
            raise ValueError('retained outcome follow-up request changed')
        return request, response_path

    def _validate_response(self, request, retained):
        if type(retained) is not dict or set(retained) != {'response', 'host_attestation'}:
            raise ValueError('independently attested outcome response required')
        response, attestation = retained['response'], retained['host_attestation']
        self.source_principal._attest_host(response, attestation, request)
        authority = json.loads(Path(attestation['host_record']['path']).read_bytes())['host_authority']
        if authority != request['host_authority']:
            raise ValueError('outcome authority differs from original independently attested host')
        for key, expected in dict(schema=RESPONSE_SCHEMA, request_sha256=digest(request),
                continuation_hash=request['continuation_hash'],
                forecast_target=request['forecast_target']).items():
            if response.get(key) != expected:
                raise ValueError('outcome response differs from follow-up ' + key)
        if type(response.get('lessons')) not in (list, tuple):
            raise ValueError('outcome response must explicitly supply its later lessons')
        body = response.get('feedback')
        if not isinstance(body, dict) or 'principal_receipt_hash' in body:
            raise ValueError('actual outcome feedback without a self-authored receipt required')
        receipt = dict(schema='FRANKIE_PENDING_TARGET_OUTCOME_RECEIPT_V1',
            mechanism='AGENT_SESSION', session_id=response['session_id'],
            model_identity_as_reported_by_session=response['model_identity_as_reported_by_session'],
            request_sha256=digest(request), response_sha256=digest(response),
            host_attestation_hash=digest(attestation), continuation_hash=request['continuation_hash'],
            original_principal_receipt=request['original_principal_receipt'])
        receipt['receipt_sha256'] = digest(receipt)
        body = dict(body, principal_receipt_hash=receipt['receipt_sha256'])
        sessions = tuple(SessionFeedback(session_id=item['session_id'],
            timing=tuple(TimingLabel(**label) for label in item['timing']),
            gap=ValueLabel(**item['gap']) if item['gap'] is not None else None,
            path=tuple(ValueLabel(**label) for label in item['path'])) for item in body['sessions'])
        feedback = FrankieFeedback(**dict(body, sessions=sessions))
        learning = request['continuation']['learning']
        if (feedback.request_id, feedback.input_hash, feedback.source_hash) != (
                request['request_id'], learning['input_hash'], learning['source_hash']):
            raise ValueError('outcome feedback changed original request/input/source identity')
        validator = object.__new__(NativeForecastLearner)
        validator.config = SimpleNamespace(session_weights=tuple(
            (session.session_id, 1.0) for _, session in self.sessions))
        validator._validate(self.sessions, feedback, learning['as_of'], learning['learning_cutoff_ns'])
        if not any(item.timing or item.gap is not None or item.path for item in feedback.sessions):
            raise ValueError('empty labels cannot complete pending target outcomes')
        envelope = dict(feedback=body, lessons=response['lessons'], principal_receipt=receipt,
            continuation_hash=request['continuation_hash'])
        return envelope, feedback

    def recover_pending_feedback(self, request_id, continuation):
        from .sunday_execution import _load
        request, path = self._retained_request(request_id, continuation, create=True)
        if not path.exists():
            raise PrincipalPending('authorized outcome host must consume ' + str(path.parent / 'request.c15.json'))
        return self._validate_response(request, _load(path))[0]

    def verify_pending_feedback(self, envelope, *, request_id, input_hash, source_hash,
                                learning_cutoff_ns, continuation):
        from .sunday_execution import _load
        request, path = self._retained_request(request_id, continuation, create=False)
        trusted, feedback = self._validate_response(request, _load(path))
        if trusted != envelope:
            raise ValueError('outcome feedback envelope differs from retained host response')
        if (input_hash, source_hash, learning_cutoff_ns) != (
                feedback.input_hash, feedback.source_hash,
                continuation['learning']['learning_cutoff_ns']):
            raise ValueError('outcome verifier received different learning identity')
        return feedback

    def record_pending_feedback_response(self, response, *, host_attestation,
                                         request_id, continuation):
        """Host recorder: validate all provenance and labels before immutable write.

        The existing host command supplies independently hashed response/attestation
        files under its actual-host lock. This method cannot author a host record.
        """
        from .sunday_execution import _save
        request, path = self._retained_request(request_id, continuation, create=False)
        retained = dict(response=response, host_attestation=host_attestation)
        envelope, _ = self._validate_response(request, retained)
        _save(path, retained)
        return envelope
