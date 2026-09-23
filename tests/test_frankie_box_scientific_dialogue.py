"""Actual retained fake exchanges exercise retrieval, resumption and fail-closed binding."""
import json
from types import SimpleNamespace
import pytest
from test_frankie_box_classroom import C
from deploy.aws.box import frankie_box_classroom_cache as cache_module
from deploy.aws.box import frankie_box_scientific_dialogue as dialogue
from deploy.aws.box import frankie_box_staged_session as staged
from deploy.aws.box import frankie_box_staged_reading as witnesses
from test_frankie_box_staged_session import FakeSession

class DialogueSession(FakeSession):
    def __init__(self,root,answers):
        super().__init__(root)
        self.answers=iter(answers)
    def _classroom_call(self,name,text,parse,lane):
        if self.fail_after is not None and len(self.calls)>=self.fail_after:
            raise RuntimeError('interrupted')
        body=json.dumps(next(self.answers))
        job_id=witnesses.digest(dict(name=name,text=text))
        directory=self.jobs/job_id[:24]
        directory.mkdir()
        (directory/'prompt.txt').write_text(text+('!' if self.corrupt_prompt else ''),encoding='utf-8')
        for filename,value in (
            ('request.json',dict(name=name,body_sha256='d'*64)),
            ('outcome.json',dict(name=name,job_id=job_id,body_sha256='d'*64,
                result_status=200,text=body,incomplete=False,model='retained-model')),
            ('result.json',dict(choices=[dict(finish_reason='stop',message=dict(content=body))]))):
            (directory/filename).write_text(json.dumps(value),encoding='utf-8')
        self.calls.append((name,text))
        return parse(body),dict(attempt=name,job_id=job_id,lane=lane,
            prompt_sha256=witnesses.witness(text)['sha256'],incomplete=False)

QUERY=dict(read_requests=[dict(source_id='evidence',start=0,end=18)])
ANSWER=dict(conclusion='Keep this failed idea available, with its scientific caveat.')

def run(session,cache):
    def parse(text):
        value=json.loads(text)
        if set(value)!={'conclusion'}:raise ValueError('conclusion required')
        return value
    return dialogue.run_task(session,cache,role='principal',phase='test',
        sources={'evidence':b'failed hypothesis\n'},reading_receipt={'plan_hash':'b'*64},
        task_instruction=lambda context:'Assess the earlier failed idea. '+json.dumps(context),
        parse_final=parse,request_hash='a'*64,task_id='whole-run',
        classroom_module=C,staged_module=staged)

def test_exact_prior_failure_is_retrieved_and_all_exchanges_resume(tmp_path):
    session=DialogueSession(tmp_path,[QUERY,ANSWER])
    cache=cache_module.ClassroomCache(tmp_path/'cache',{'test':'same-identity'})
    first=run(session,cache)
    assert first['parsed']==ANSWER
    assert len(first['context_calls'])==1
    assert 'failed hypothesis\\n' in first['call']['prompt']
    assert first['call']['role']=='principal'
    assert len(session.calls)==2
    assert run(session,cache)==first
    assert len(session.calls)==2

def test_interruption_resumes_from_last_completed_exchange(tmp_path):
    session=DialogueSession(tmp_path,[QUERY,ANSWER])
    cache=cache_module.ClassroomCache(tmp_path/'cache',{'test':'same-identity'})
    session.fail_after=1
    with pytest.raises(RuntimeError,match='interrupted'):run(session,cache)
    session.fail_after=None
    result=run(session,cache)
    assert result['parsed']==ANSWER and len(session.calls)==2

def test_no_task_specific_read_is_not_accepted_as_comprehension(tmp_path):
    session=DialogueSession(tmp_path,[ANSWER])
    cache=cache_module.ClassroomCache(tmp_path/'cache',{'test':'same-identity'})
    with pytest.raises(ValueError,match='task-specific'):run(session,cache)

def test_raw_transport_prompt_mismatch_refuses(tmp_path):
    session=DialogueSession(tmp_path,[QUERY])
    session.corrupt_prompt=True
    cache=cache_module.ClassroomCache(tmp_path/'cache',{'test':'same-identity'})
    with pytest.raises(ValueError,match='retained completed'):run(session,cache)

def test_repeated_retrieval_without_progress_refuses(tmp_path):
    session=DialogueSession(tmp_path,[QUERY,QUERY])
    cache=cache_module.ClassroomCache(tmp_path/'cache',{'test':'same-identity'})
    with pytest.raises(ValueError,match='without progress'):run(session,cache)
