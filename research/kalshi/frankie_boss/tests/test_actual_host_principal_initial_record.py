"""Initial recording validates provenance and labels while classroom correction remains pending."""
import hashlib,json
from pathlib import Path
import pytest
from research.kalshi.frankie_boss.frankie_principal_adapter import FrankiePrincipalAdapter,PrincipalPending,canonical,digest,file_witness
from research.kalshi.frankie_boss.operations.record_actual_frankie_response import record_checked

class PendingClassroom(FrankiePrincipalAdapter):
    def __init__(self,directory,request,sections):
        self.directory=directory
        self.request=request
        self.section_evidence={name:dict(sha256=value) for name,value in sections.items()}
    def _request(self,request_id,attachment):
        assert request_id==self.request['request_id'] and attachment==self.request['attachment']
        return self.request
    def _files(self):
        pass  # The source-file boundary is covered by the adapter's existing tests.
    def recover(self,*args,**kwargs):
        raise PrincipalPending('mandatory correction has not been delivered')

@pytest.mark.parametrize('fault',[None,'sections','availability','host_record'])
def test_initial_recording_does_not_claim_classroom_completion(tmp_path,fault):
    directory=tmp_path/'principal';directory.mkdir();(directory/'receiver').mkdir()
    request=dict(request_id='test-session',attachment=dict(preparation_receipt=dict(outputs=[])),admission=dict(status='TEST_FIXTURE'))
    (directory/'session-request.json').write_bytes(canonical(request))
    sections={'section-'+str(i):hashlib.sha256(str(i).encode()).hexdigest() for i in range(18)}
    adapter=PendingClassroom(directory,request,sections)
    binding=dict(as_of=10,learning_cutoff_ns=20,source_hash='c'*64,sessions=())
    response=dict(session_id='TEST_SESSION_FIXTURE',model_identity_as_reported_by_session='TEST_MODEL_FIXTURE',
                  request_sha256=digest(request),sections=dict(sections),lessons=[],
                  feedback=dict(request_id='test-session',input_hash='b'*64,source_hash='c'*64,available_ns=15,sessions=[]))
    if fault=='sections':response['sections']['section-0']='d'*64
    if fault=='availability':response['feedback']['available_ns']=21
    record=dict(schema='FRANKIE_HOST_AGENT_SESSION_ATTESTATION_V1',mechanism='AGENT_SESSION',
                request_sha256=digest(request),response_sha256=digest(response),
                session_id=response['session_id'],model_identity_as_reported_by_session=response['model_identity_as_reported_by_session'])
    host_record=tmp_path/'host-record.json'
    host_record.write_bytes(canonical(dict(record,host_authority='EXPLICIT_TEST_FIXTURE')))
    attestation=dict(record,host_record=dict(path=str(host_record),**file_witness(host_record)))
    if fault=='host_record':host_record.write_text('{}')
    if fault:
        with pytest.raises(ValueError):
            record_checked(adapter,request,response,attestation,binding,'b'*64,canonical)
        assert not (directory/'session-response.json').exists()
    else:
        envelope=record_checked(adapter,request,response,attestation,binding,'b'*64,canonical)
        assert envelope['principal_receipt']['session_id']=='TEST_SESSION_FIXTURE'
        assert (directory/'session-response.json').exists()
        with pytest.raises(PrincipalPending):adapter.recover(request['request_id'],request['attachment'])
        assert not (directory/'dipole-classroom-completion.json').exists()
