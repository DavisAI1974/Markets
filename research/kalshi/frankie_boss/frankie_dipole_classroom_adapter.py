"""Frankie principal adapter with a mandatory two-turn Dipole classroom.

This subclasses the existing durable principal boundary instead of creating a
second model path. The ordinary feedback/lessons envelope is returned unchanged,
but only after the complete classroom finishes. Audit-only material (the source
snapshot with every retained value and state, the teacher key, the full post-grade)
is persisted in a host-owned audit directory beside the principal directory, never in
the model-facing principal directory and never in the model attachment. Note the
limit of that layout: it withholds nothing from a session that can read the whole
run directory; the guard that matters is the session's filesystem scope.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .dipole_classroom_render import render_transcript
from .dipole_classroom_resolution import bind_resolution_requirement, validate_correction_resolutions
from .dipole_classroom_session import (
    correction_request,
    finish,
    grade_initial_response,
    model_visible_classroom,
    validate_correction_response,
    validate_package,
)
from .frankie_principal_adapter import (
    FrankiePrincipalAdapter,
    PrincipalPending,
    canonical,
    digest,
    file_witness,
    json_form,
    _write,
)


class DipoleClassroomPrincipalAdapter(FrankiePrincipalAdapter):
    """Existing principal protocol plus a mandatory same-session classroom."""

    def __init__(self, *args, classroom_package, audit_directory=None, shared_knowledge=None, **kwargs):
        self.classroom_package = validate_package(classroom_package)
        if shared_knowledge is not None:
            from .dipole_shared_knowledge import validate_descriptor
            shared_knowledge=validate_descriptor(shared_knowledge)
            if self.classroom_package['pre_message'].get('shared_knowledge')!=shared_knowledge:
                raise ValueError('principal and teacher research snapshots differ')
        self.shared_knowledge=shared_knowledge
        super().__init__(*args, **kwargs)
        self.audit_directory = (Path(audit_directory) if audit_directory is not None
                                else self.directory.parent / "classroom-audit").resolve()
        if self.audit_directory == self.directory or self.audit_directory.is_relative_to(self.directory):
            raise ValueError("classroom audit directory must be outside the model-facing principal directory")
        self.audit_directory.mkdir(parents=True, exist_ok=True)

    def _config_hash(self):
        return digest({
            "principal_config_hash": super()._config_hash(),
            "dipole_classroom_binding_hash": self.classroom_package["binding"]["classroom_binding_hash"],
            "teacher_key_hash": self.classroom_package["teacher_key"]["teacher_key_hash"],
            "mechanism": "AGENT_SESSION_WITH_DIPOLE_CLASSROOM",
        })

    def _retain(self, name, body, *, directory=None):
        path = (self.directory if directory is None else directory) / name
        raw = canonical(body)
        if path.exists():
            if path.read_bytes() != raw:
                raise ValueError("retained Dipole classroom artifact changed")
        else:
            with path.open("xb") as handle:
                handle.write(raw);handle.flush();os.fsync(handle.fileno())
        return path

    def _retain_audit(self, name, body):
        """Host-owned audit evidence: retained beside, never inside, the principal directory."""
        return self._retain(name, body, directory=self.audit_directory)

    def _retain_text(self, name, text):
        path = self.directory / name
        raw = text.encode("utf-8")
        if path.exists():
            if path.read_bytes() != raw:
                raise ValueError("retained Dipole classroom transcript changed")
        else:
            with path.open("xb") as handle:
                handle.write(raw);handle.flush();os.fsync(handle.fileno())
        return path

    def prepare(self, handoff_directory):
        attachment = super().prepare(handoff_directory)
        visible = model_visible_classroom(self.classroom_package)
        attachment = dict(attachment)
        attachment["dipole_classroom"] = visible
        attachment["attachment_hash"] = digest({k:v for k,v in attachment.items() if k != "attachment_hash"})
        self._retain_audit("dipole-classroom-source.json", self.classroom_package["source"])
        self._retain_audit("dipole-classroom-teacher-key.audit.json", self.classroom_package["teacher_key"])
        self._retain("dipole-classroom-pre-message.json", self.classroom_package["pre_message"])
        self._retain("dipole-classroom-model-visible.json", visible)
        return attachment

    def _request(self, request_id, attachment):
        request = super()._request(request_id, attachment)
        visible = attachment.get("dipole_classroom")
        if visible != model_visible_classroom(self.classroom_package):
            raise ValueError("principal attachment Dipole classroom differs from model-visible contract")
        request = dict(request)
        request["instruction"] += (
            " Before giving feedback, complete the attached Dipole classroom lesson. Your response must include "
            "dipole_teachback with schema DIPOLE_CLASSROOM_TEACHBACK_V1 and cover all 19 dimensions in governed "
            "order. For every dimension provide state_counts for PRESENT/MISSING/INVALID/ABLATED, terminal_state, "
            "first-to-last PRESENT direction, what happened, why, market behavior, FIFO/full-book/order linkage "
            "where justified, evidence, uncertainty, and any specifically notable relationships. Set "
            "relationship_pairs_considered to 171 and future_outcome_claimed false. In addition, provide "
            "dipole_observation_review as exactly 19 ordered objects {name, observations}; observations must include "
            "every retained cursor for that dimension as {cursor,state,value,explanation}, with value null for every "
            "non-PRESENT state. Also provide dipole_relationship_scan as exactly 171 canonical ordered pair objects "
            "{left,right,direction_relation,correlation_interpretation,developing_structure}; direction_relation must "
            "be SAME_DIRECTION, OPPOSITE_DIRECTION, or UNRESOLVED, correlation_interpretation must explain what the "
            "current causal evidence does or does not support, and developing_structure must be null or an explicitly "
            "labeled hypothesis. Do not skip repetitive, neutral, missing, invalid, or ablated evidence. Distinguish "
            "observation, interpretation, hypothesis, and anything not yet knowable. The host will return Dipole's "
            "point-by-point grade to this same session; you must resolve and acknowledge every correction before this "
            "cycle can complete."
        )
        request["dipole_classroom_model_visible_hash"] = visible["model_visible_hash"]
        return request

    def execute(self, request_id, attachment):
        request = self._request(request_id, attachment)
        path = self.directory / "session-request.json"
        if path.exists():
            if json.loads(path.read_bytes()) != json_form(request):
                raise ValueError("session request identity changed")
            return self.recover(request_id, attachment)
        _write(path, request)
        if self.session_executor is None:
            raise PrincipalPending(f"authorized host session must consume {path}")
        dispatched = self.session_executor(request)
        response_path = self.directory / "session-response.json"
        if response_path.exists():
            if json.loads(response_path.read_bytes()) != dispatched:
                raise ValueError("recorded principal response differs from host return")
            self._attest_host(dispatched["response"], dispatched["host_attestation"], request)
        else:
            self.record_session_response(dispatched["response"], host_attestation=dispatched["host_attestation"])
        return self._recover_with_classroom(request_id, attachment, dispatch_followup=True)

    def recover(self, request_id, attachment):
        return self._recover_with_classroom(request_id, attachment, dispatch_followup=False)

    def _record_correction_response(self, correction, dispatched):
        if type(dispatched) is not dict or set(dispatched) != {"response", "host_attestation"}:
            raise ValueError("recorded classroom correction response envelope differs")
        self._attest_host(dispatched["response"], dispatched["host_attestation"], correction)
        path = self.directory / "classroom-correction-response.json"
        body = {"response":dispatched["response"], "host_attestation":dispatched["host_attestation"]}
        if path.exists():
            if json.loads(path.read_bytes()) != json_form(body):
                raise ValueError("retained classroom correction response changed")
        else:
            _write(path, body)
        return body

    def _recover_with_classroom(self, request_id, attachment, *, dispatch_followup):
        envelope = super().recover(request_id, attachment)
        request = json.loads((self.directory / "session-request.json").read_bytes())
        retained = json.loads((self.directory / "session-response.json").read_bytes())
        initial_response = retained["response"]
        teachback, grade = grade_initial_response(self.classroom_package, initial_response)
        self._retain("dipole-classroom-teachback.json", teachback)
        self._retain_audit("dipole-classroom-post-grade.json", grade)

        correction = bind_resolution_requirement(correction_request(
            original_request_sha256=digest(request), response=initial_response, grade=grade))
        correction_path = self.directory / "classroom-correction-request.json"
        created = False
        if correction_path.exists():
            if json.loads(correction_path.read_bytes()) != json_form(correction):
                raise ValueError("retained Dipole classroom correction request changed")
        else:
            _write(correction_path, correction);created = True

        response_path = self.directory / "classroom-correction-response.json"
        if not response_path.exists():
            if not created or not dispatch_followup or self.session_executor is None:
                raise PrincipalPending("same Frankie session must consume Dipole classroom correction")
            dispatched = self.session_executor(correction)
            self._record_correction_response(correction, dispatched)
        correction_envelope = json.loads(response_path.read_bytes())
        self._attest_host(correction_envelope["response"], correction_envelope["host_attestation"], correction)
        base_acknowledgement = validate_correction_response(correction=correction,
            response=correction_envelope["response"], initial_response=initial_response, grade=grade)
        acknowledgement = validate_correction_resolutions(
            correction_envelope["response"].get("dipole_acknowledgement"), grade, base_acknowledgement)
        self._retain("dipole-classroom-acknowledgement.json", acknowledgement)
        completion = finish(self.classroom_package, teachback=teachback, grade=grade, acknowledgement=acknowledgement)
        self._retain("dipole-classroom-completion.json", completion)
        transcript = render_transcript(self.classroom_package["pre_message"], teachback, grade, acknowledgement)
        transcript_path = self._retain_text("dipole-classroom-transcript.md", transcript)
        self._retain("dipole-classroom-receipt.json", {
            "schema":"FRANKIE_DIPOLE_CLASSROOM_RECEIPT_V1",
            "classroom_binding_hash":self.classroom_package["binding"]["classroom_binding_hash"],
            "teacher_key_hash":self.classroom_package["teacher_key"]["teacher_key_hash"],
            "completion_hash":completion["completion_hash"],
            "exhaustive_audit_hash":completion["exhaustive_audit_hash"],
            "observation_claims_reviewed":completion["observation_claims_reviewed"],
            "relationship_pairs_explicitly_reviewed":completion["relationship_pairs_explicitly_reviewed"],
            "correction_resolutions":len(acknowledgement["correction_resolutions"]),
            "transcript":file_witness(transcript_path),
            "initial_session_id":initial_response["session_id"],
            "correction_session_id":correction_envelope["response"]["session_id"],
            "teacher_complete":completion["teacher_complete"],
        })
        return envelope
