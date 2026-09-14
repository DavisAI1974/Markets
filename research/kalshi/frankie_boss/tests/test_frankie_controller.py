"""Actual synthetic native forecasts plus required native-context critic."""
import asyncio
import json
from dataclasses import asdict
import pytest

from controller_journal import ControllerJournal
from frankie_controller import FrankieForecastController, native_model_pin
from test_native_forecast_refresh import build_refresh, H
from test_frankie_forecast_consumer import context as metadata
from native_forecast_refresh import session_registry_hash


def test_journal_completed_retry_restore_and_changed_request(tmp_path):
    journal = ControllerJournal(tmp_path/'controller.sqlite', create=True)
    state = journal.begin('run', {'source': H})
    journal.record('run', 'NATIVE_COMPLETE', {'publications': (), 'checkpoint': {}})
    result = dict(request_id='run',request_hash=state['request_hash'],status='idle',records=())
    journal.record('run', 'RESULT', result)
    checkpoint = journal.checkpoint()
    journal.close()
    restored = ControllerJournal(tmp_path/'controller.sqlite', checkpoint=checkpoint)
    assert restored.begin('run', {'source': H})['result'] == result
    with pytest.raises(ValueError, match='changed'):
        restored.begin('run', {'source': 'b'*64})
    restored.close()


def test_disabled_calls_legacy_without_dependencies():
    sentinel = object()
    controller = FrankieForecastController(enabled=False, legacy=lambda: sentinel)
    assert asyncio.run(controller.refresh()) is sentinel


def test_enabled_requires_pinned_critic_before_native_work(tmp_path):
    bridge, _ = build_refresh(tmp_path)
    with pytest.raises(ValueError, match='critic'):
        FrankieForecastController(enabled=True, bridge=bridge, journal=object(),
                                  expected_native_hash=native_model_pin(bridge))


class Critic:
    enabled = True
    config_hash = 'c'*64

    def __init__(self, *, verdict='CONFLICTED', delay=False):
        import hashlib
        from research.kalshi.frankie_boss.granite_shadow import GraniteIdentity
        from research.kalshi.frankie_boss.granite_context import SYSTEM_TEXT, native_parser_code_hash
        from research.kalshi.frankie_boss.granite_output_schema import SCHEMA_VERSION
        self.identity = GraniteIdentity('a'*64,None,'b'*64,'none','synthetic/1',False,0,1200,
            hashlib.sha256(SYSTEM_TEXT.encode()).hexdigest(),SCHEMA_VERSION,native_parser_code_hash(),None)
        self.calls = 0
        self.verdict = verdict
        self.delay = delay
        self.request_timeout = .001 if delay else 1.

    async def critique_native(self, snapshot, *, request_id):
        from research.kalshi.frankie_boss.granite_shadow import serve_native_shadow, ShadowResponse
        from research.kalshi.frankie_boss.granite_bedrock import BedrockReceipt
        from test_granite_parser import valid_output
        from c15_journal import evidence_hash
        self.calls += 1
        async def transport(request):
            if self.delay:
                await asyncio.sleep(.02)
            value = valid_output(snapshot)
            value['evidence_refs'] = [{'row':0,'field':'/record/price'}]
            value['evidence_verdict'] = self.verdict
            return ShadowResponse(request.request_hash,request.identity.identity_hash,json.dumps(value))
        shadow = await serve_native_shadow(snapshot,self.identity,request_id=request_id,
                                            timeout_seconds=self.request_timeout,transport=transport)
        import hashlib
        call_hash = hashlib.sha256(json.dumps(dict(config_hash=self.config_hash,
            request_hash=shadow.request.request_hash),sort_keys=True,separators=(',',':')).encode()).hexdigest()
        return BedrockReceipt(shadow,self.config_hash,call_hash,None,None)


def build_controller(tmp_path, **critic_options):
    bridge, sessions = build_refresh(tmp_path)
    critic = Critic(**critic_options)
    journal = ControllerJournal(tmp_path/'controller.sqlite',create=True)
    controller = FrankieForecastController(enabled=True,bridge=bridge,journal=journal,critic=critic,
        expected_native_hash=native_model_pin(bridge),expected_critic_config_hash=critic.config_hash,
        expected_critic_identity_hash=critic.identity.identity_hash)
    request = dict(request_id='refresh/1',sessions=sessions,
        expected_sessions_hash=session_registry_hash(sessions),arm_hash=H,
        as_of=2,source_as_of=1,source_hash=bridge.context.builder.chain.prefix_hash,
        through_cursor=0,metadata=tuple((t.digest,metadata()) for t,s in sessions))
    return controller, bridge, critic, request


def test_all_horizons_required_critic_and_completed_retry_no_extra_forward(tmp_path, monkeypatch):
    from frankie_forecast_consumer import consume_forecast
    controller, bridge, critic, request = build_controller(tmp_path)
    original = bridge.context.model.forward_decision
    calls = []
    def forward(**kwargs):
        calls.append(1)
        return original(**kwargs)
    monkeypatch.setattr(bridge.context.model,'forward_decision',forward)
    result = asyncio.run(controller.refresh(**request))
    assert result['status'] == 'complete'
    assert len(result['records']) == len(calls) == 3
    assert critic.calls == 1
    for entry in result['records']:
        expected = consume_forecast(enabled=True,legacy=None,book=bridge.book,
            publication_hash=entry['publication_hash'],metadata=metadata())
        assert entry['record_json'] == expected.to_json()
    assert asyncio.run(controller.refresh(**request)) == result
    assert len(calls) == 3 and critic.calls == 1


def test_partial_native_commit_retry_does_not_regenerate_completed_target(tmp_path,monkeypatch):
    controller,bridge,critic,request = build_controller(tmp_path)
    original = bridge.context.model.forward_decision
    calls = []
    def fail_second(**kwargs):
        calls.append(1)
        if len(calls) == 2: raise RuntimeError('synthetic second-target failure')
        return original(**kwargs)
    monkeypatch.setattr(bridge.context.model,'forward_decision',fail_second)
    with pytest.raises(RuntimeError,match='second-target'):
        asyncio.run(controller.refresh(**request))
    assert critic.calls == 0
    result = asyncio.run(controller.refresh(**request))
    assert result['status'] == 'complete'
    assert len(calls) == 4 and critic.calls == 1
    assert all(r['revision'] == 1 for r in result['records'])


def test_unknown_critic_completion_requires_explicit_linked_recovery(tmp_path,monkeypatch):
    controller,bridge,critic,request = build_controller(tmp_path)
    original = critic.critique_native
    async def uncertain(*args,**kwargs):
        raise RuntimeError('unknown external completion')
    monkeypatch.setattr(critic,'critique_native',uncertain)
    with pytest.raises(RuntimeError,match='unknown external'):
        asyncio.run(controller.refresh(**request))
    state = controller.journal.state(request['request_id'])
    assert state['critic_intent'] is not None and state['critic_result'] is None
    monkeypatch.setattr(critic,'critique_native',original)
    with pytest.raises(ValueError,match='completion unknown'):
        asyncio.run(controller.refresh(**request))
    result = asyncio.run(controller.refresh(**request,recovery_attempt_id='explicit-recovery/1'))
    assert result['status'] == 'complete' and critic.calls == 1
    state = controller.journal.state(request['request_id'])
    assert state['attempts'][-1] == 'explicit-recovery/1' and len(state['attempts']) == 2


def test_malformed_critic_keeps_native_and_frankie_record_without_false_success(tmp_path):
    controller,bridge,critic,request = build_controller(tmp_path,verdict='NOT_AN_ALLOWED_VERDICT')
    result = asyncio.run(controller.refresh(**request))
    assert result['status'] == 'incomplete'
    assert result['critic']['receipt']['shadow']['status'] == 'rejected'
    assert len(result['records']) == 3
    assert all(json.loads(r['record_json'])['payload']['confidence'] is None for r in result['records'])
    assert asyncio.run(controller.refresh(**request)) == result and critic.calls == 1


def test_journal_external_suffix_cannot_be_silently_accepted(tmp_path):
    from c15_journal import EvidenceJournal
    journal = ControllerJournal(tmp_path/'controller.sqlite',create=True)
    journal.begin('run',{'source':H})
    other = EvidenceJournal(tmp_path/'controller.sqlite')
    other.append('foreign',{'unexpected':True})
    other.close()
    with pytest.raises(ValueError,match='journal'):
        journal.state('run')


def test_changed_metadata_rejected_before_more_native_or_critic_calls(tmp_path):
    controller,bridge,critic,request = build_controller(tmp_path)
    asyncio.run(controller.refresh(**request))
    changed = tuple((key,{**value,'reasoning':'changed caller metadata'}) for key,value in request['metadata'])
    with pytest.raises(ValueError,match='changed'):
        asyncio.run(controller.refresh(**{**request,'metadata':changed}))
    assert critic.calls == 1


def test_completed_combined_receipt_restores_without_model_or_provider_call(tmp_path,monkeypatch):
    from rolling_forecast import RollingForecastBook
    controller,bridge,critic,request = build_controller(tmp_path)
    result = asyncio.run(controller.refresh(**request))
    journal_checkpoint,book_checkpoint = controller.journal.checkpoint(),bridge.book.checkpoint()
    controller.journal.close()
    bridge.book.close()
    bridge.book = RollingForecastBook(tmp_path/'forecasts.sqlite',checkpoint=book_checkpoint)
    journal = ControllerJournal(tmp_path/'controller.sqlite',checkpoint=journal_checkpoint)
    restored = FrankieForecastController(enabled=True,bridge=bridge,journal=journal,critic=critic,
        expected_native_hash=native_model_pin(bridge),expected_critic_config_hash=critic.config_hash,
        expected_critic_identity_hash=critic.identity.identity_hash)
    def forbidden(**kwargs): pytest.fail('completed replay must not forward')
    monkeypatch.setattr(bridge.context.model,'forward_decision',forbidden)
    assert asyncio.run(restored.refresh(**request)) == result
    assert critic.calls == 1


def test_critic_timeout_is_incomplete_and_preserves_publications(tmp_path):
    controller,bridge,critic,request = build_controller(tmp_path,delay=True)
    result = asyncio.run(controller.refresh(**request))
    assert result['status'] == 'incomplete'
    assert result['critic']['receipt']['shadow']['status'] == 'timeout'
    assert len(result['records']) == 3
    assert all(bridge.book.publication(row['publication_hash']).revision == 1 for row in result['records'])


def test_uncertain_controller_append_stops_instance_without_truncation(tmp_path,monkeypatch):
    journal = ControllerJournal(tmp_path/'controller.sqlite',create=True)
    old_checkpoint = journal.checkpoint()
    original = journal.journal.append
    def persist_then_fail(*args,**kwargs):
        original(*args,**kwargs)
        raise OSError('synthetic uncertain commit')
    monkeypatch.setattr(journal.journal,'append',persist_then_fail)
    with pytest.raises(OSError): journal.begin('run',{'source':H})
    with pytest.raises(ValueError,match='uncertain'): journal.checkpoint()
    journal.close()
    with pytest.raises(ValueError):
        ControllerJournal(tmp_path/'controller.sqlite',checkpoint=old_checkpoint)


def test_invalid_causal_request_rejected_before_controller_intent(tmp_path):
    controller,bridge,critic,request = build_controller(tmp_path)
    with pytest.raises(ValueError):
        asyncio.run(controller.refresh(**{**request,'source_as_of':3}))
    assert controller.journal.checkpoint()['count'] == 0
    assert critic.calls == 0 and bridge.book.checkpoint()['count'] == 0


@pytest.mark.parametrize('field',['call_hash','timeout'])
def test_foreign_critic_call_or_timeout_cannot_complete(tmp_path,monkeypatch,field):
    from dataclasses import replace
    controller,bridge,critic,request = build_controller(tmp_path)
    original = critic.critique_native
    async def corrupt(*args,**kwargs):
        receipt = await original(*args,**kwargs)
        if field == 'call_hash': return replace(receipt,call_hash='f'*64)
        return replace(receipt,shadow=replace(receipt.shadow,
            request=replace(receipt.shadow.request,timeout_seconds=999.)))
    monkeypatch.setattr(critic,'critique_native',corrupt)
    with pytest.raises(ValueError): asyncio.run(controller.refresh(**request))
    assert controller.journal.state(request['request_id'])['result'] is None


@pytest.mark.parametrize('field',['critic_hash','artifact_digest','publication_hash','status'])
def test_self_consistent_journal_rejects_broken_combined_links(tmp_path,field):
    from c15_journal import EvidenceJournal,pack,unpack
    import controller_journal
    controller,bridge,critic,request = build_controller(tmp_path)
    asyncio.run(controller.refresh(**request))
    entries = list(controller.journal.journal.entries())
    forged = EvidenceJournal(tmp_path/'forged.sqlite',create=True)
    for entry in entries:
        event = unpack(pack(entry['payload']))
        if event['step'] == 'RESULT':
            value = event['payload']
            if field in ('artifact_digest','publication_hash'):
                value['records'][0][field] = 'f'*64
            elif field == 'status': value['status'] = 'incomplete'
            else: value[field] = 'f'*64
        forged.append(entry['kind'],event)
    checkpoint = dict(schema=controller_journal.SCHEMA,count=forged.count,head_hash=forged.head_hash)
    forged.close()
    with pytest.raises(ValueError): ControllerJournal(tmp_path/'forged.sqlite',checkpoint=checkpoint)


def test_physical_source_append_during_critic_cannot_complete(tmp_path,monkeypatch):
    from c15_journal import EvidenceJournal
    controller,bridge,critic,request = build_controller(tmp_path)
    original = critic.critique_native
    async def external_append(*args,**kwargs):
        receipt = await original(*args,**kwargs)
        other = EvidenceJournal(bridge.context.builder.journal.path)
        other.append('external_writer',{'unexpected':True})
        other.close()
        return receipt
    monkeypatch.setattr(critic,'critique_native',external_append)
    with pytest.raises(ValueError,match='journal'):
        asyncio.run(controller.refresh(**request))
    assert controller.journal.state(request['request_id'])['result'] is None


def test_replay_rechecks_critic_parser_even_when_combined_hashes_are_recomputed(tmp_path):
    from c15_journal import EvidenceJournal,pack,unpack,evidence_hash
    import controller_journal
    controller,bridge,critic,request = build_controller(tmp_path)
    asyncio.run(controller.refresh(**request))
    entries = list(controller.journal.journal.entries())
    forged = EvidenceJournal(tmp_path/'forged-parser.sqlite',create=True)
    changed = None
    for entry in entries:
        event = unpack(pack(entry['payload']))
        if event['step'] == 'CRITIC_RESULT':
            event['payload']['receipt']['shadow']['response']['text'] = 'not valid JSON'
            changed = event['payload']
        if event['step'] == 'RESULT':
            event['payload']['critic'] = changed
            event['payload']['critic_hash'] = evidence_hash(changed)
        forged.append(entry['kind'],event)
    checkpoint = dict(schema=controller_journal.SCHEMA,count=forged.count,head_hash=forged.head_hash)
    forged.close()
    with pytest.raises(ValueError): ControllerJournal(tmp_path/'forged-parser.sqlite',checkpoint=checkpoint)


@pytest.mark.parametrize('kind',['missing_hash','boolean_timeout'])
def test_enabled_pins_and_timeout_require_strict_values(tmp_path,kind):
    bridge,_ = build_refresh(tmp_path)
    critic = Critic()
    if kind == 'missing_hash': critic.config_hash = None
    else: critic.request_timeout = True
    with pytest.raises(ValueError):
        FrankieForecastController(enabled=True,bridge=bridge,journal=object(),critic=critic,
            expected_native_hash=native_model_pin(bridge),expected_critic_config_hash=critic.config_hash,
            expected_critic_identity_hash=critic.identity.identity_hash)


def test_overlapping_controller_run_is_rejected(tmp_path,monkeypatch):
    controller,bridge,critic,request = build_controller(tmp_path)
    original = critic.critique_native
    async def scenario():
        started,finish = asyncio.Event(),asyncio.Event()
        async def waiting(*args,**kwargs):
            started.set()
            await finish.wait()
            return await original(*args,**kwargs)
        monkeypatch.setattr(critic,'critique_native',waiting)
        first = asyncio.create_task(controller.refresh(**request))
        await started.wait()
        with pytest.raises(ValueError,match='in flight'):
            await controller.refresh(**{**request,'request_id':'different'})
        finish.set()
        return await first
    assert asyncio.run(scenario())['status'] == 'complete'
    assert critic.calls == 1


def test_controller_operates_configured_sagemaker_native_service(tmp_path):
    import io
    from botocore.response import StreamingBody
    from research.kalshi.frankie_boss.granite_sagemaker import SageMakerConfig,build_sagemaker_service
    from research.kalshi.frankie_boss.granite_context import NativeContext
    from test_granite_parser import valid_output
    bridge,sessions = build_refresh(tmp_path)
    calls = []
    config = SageMakerConfig('us-east-1','synthetic-granite','granite-4.2-8b',True,1,1,2)
    class Client:
        def invoke_endpoint(self,**kwargs):
            calls.append(kwargs)
            assert kwargs['EndpointName'] == config.endpoint_name
            body = json.loads(kwargs['Body'])
            assert body['model'] == 'granite-4.2-8b'
            state = NativeContext(body['messages'][0]['content'].split('\nnative_context:\n',1)[1])
            response = valid_output(state)
            response['evidence_refs'] = [{'row':0,'field':'/record/price'}]
            output = dict(model=config.served_model_name,object='chat.completion',
                choices=[dict(index=0,finish_reason='stop',message=dict(role='assistant',
                    content=json.dumps(response),reasoning=None,tool_calls=[]))])
            raw = json.dumps(output).encode()
            return dict(Body=StreamingBody(io.BytesIO(raw),len(raw)),ContentType='application/json')
    service = build_sagemaker_service(enabled=True,config=config,identity=Critic().identity,
                                      client_factory=lambda cfg:Client())
    journal = ControllerJournal(tmp_path/'controller.sqlite',create=True)
    controller = FrankieForecastController(enabled=True,bridge=bridge,journal=journal,critic=service,
        expected_native_hash=native_model_pin(bridge),expected_critic_config_hash=service.config_hash,
        expected_critic_identity_hash=service.identity.identity_hash)
    result = asyncio.run(controller.refresh(request_id='sagemaker/1',sessions=sessions,
        expected_sessions_hash=session_registry_hash(sessions),arm_hash=H,as_of=2,source_as_of=1,
        source_hash=bridge.context.builder.chain.prefix_hash,through_cursor=0,
        metadata=tuple((t.digest,metadata()) for t,s in sessions)))
    assert result['status'] == 'complete' and len(result['records']) == 3
    assert len(calls) == 1
    assert result['critic']['receipt']['provider_json'] is not None
