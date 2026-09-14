"""Small synthetic native fixture for real Granite integration; never a Frankie launcher.

Preparation does not invoke a model. The explicit run uses the existing native
controller and SageMaker service, retaining original bytes and actual outcomes.
The probe-only source, random native weights and three toy horizons establish
software wiring only, not fitted forecasts, calibration or production capacity.
"""
from dataclasses import asdict, dataclass
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys

import torch

from .b1_reasoner import B1Config, B1Reasoner
from .c15_builder import ADAPTER_REVISION, C15Builder
from .causal_prefix import ScopeKind, SourceMember, SourceScope
from .c15_journal import canonical_bytes, evidence_hash, pack
from .context_session import ContextReceipt, ContextSessionRunner, tensor_identity
from .controller_journal import ControllerJournal
from .forecast_artifact import DecoderSnapshot
from .forecast_heads import KnotPolicy, NativeForecastHeads
from .forecast_refresh import RefreshPolicy
from .forecast_session import ForecastSession, PriceObservation
from .frankie_controller import FrankieForecastController, native_model_pin
from .granite_context import map_native_context
from .granite_context_route import context_route
from .granite_sagemaker import build_sagemaker_service, _client
from .granite_shadow import GraniteIdentity
from .granite_contract import SCHEMA_VERSION
from .native_forecast_refresh import NativeForecastRefresh, session_registry_hash
from .native_mbo_encoder import NativeRegistry, NativeTrunk
from .rolling_forecast import ForecastTarget, RollingForecastBook

SCHEMA = 'GRANITE_SYNTHETIC_CONTROLLER_FIXTURE_V1'
TOKENIZER_FILES = {'config.json','generation_config.json','tokenizer.json','tokenizer_config.json',
                   'chat_template.jinja','special_tokens_map.json','vocab.json','merges.txt'}
TOKENIZER_VERSIONS = {'transformers':'5.8.0','tokenizers':'0.22.2'}


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _save(path, data):
    with Path(path).open('xb') as stream:
        stream.write(data)


def _preview(runner, *, as_of, through_cursor, source_as_of):
    tokens, info, input_hash, _, _ = runner._prepare(as_of, through_cursor)
    receipt = ContextReceipt(**info, input_hash=input_hash, model_hash=runner._model_hash())
    mapped = map_native_context(tokens=tokens, receipt=receipt, entity=runner.entity,
        registry=runner.model.trunk.registry, expected_input_hash=input_hash,
        expected_packet_hash=evidence_hash(info), source_as_of=source_as_of)
    route = context_route('compact_v1')
    snapshot = route.encode(mapped)
    return mapped, snapshot, route.build_prompt(snapshot)


def _request_payload(request):
    return dict(request, sessions=tuple((asdict(t),asdict(s)) for t,s in request['sessions']))


def measure_fixture(fixture, tokenizer_directory, *, output_tokens=1200):
    """Measure the exact service message using the selected image's tokenizer versions."""
    from . import granite_run_artifacts as artifacts
    from transformers import AutoTokenizer
    versions = {name:importlib.metadata.version(name) for name in TOKENIZER_VERSIONS}
    if versions != TOKENIZER_VERSIONS:
        raise ValueError('tokenizer implementation differs from selected image')
    if type(output_tokens) is not int or output_tokens <= 0:
        raise ValueError('explicit positive output budget required')
    directory = Path(tokenizer_directory)
    manifest = artifacts.strict_json(artifacts.DEFAULT_MANIFEST.read_bytes())
    rows = [row for row in manifest['files'] if row['path'] in TOKENIZER_FILES]
    if {p.name for p in directory.iterdir()} != TOKENIZER_FILES:
        raise ValueError('exact tokenizer file roster required')
    for row in rows:
        artifacts.verify_file(directory/row['path'], row)
    tokenizer = AutoTokenizer.from_pretrained(str(directory), local_files_only=True, trust_remote_code=False)
    ids = tokenizer.apply_chat_template([{'role':'user','content':fixture.prompt.text}], tokenize=True,
                                        add_generation_prompt=True, enable_thinking=False)
    if type(ids) is not list or not ids or any(type(token) is not int or token < 0 for token in ids):
        raise ValueError('tokenizer did not return exact complete token IDs')
    positional_limit = artifacts.strict_json((directory/'config.json').read_bytes())['max_position_embeddings']
    required = len(ids) + output_tokens
    if type(positional_limit) is not int or required > positional_limit:
        raise ValueError('complete input and output exceed model positional limit')
    tokenizer_manifest = dict(schema='GRANITE_TOKENIZER_MANIFEST_V1', files=rows, versions=versions,
        invocation=dict(message_roles=['user'],add_generation_prompt=True,enable_thinking=False,tokenize=True))
    result = dict(schema='GRANITE_TOKEN_ADMISSION_V1', prompt_sha256=fixture.manifest['prompt_sha256'],
        input_tokens=len(ids), output_tokens=output_tokens, max_model_len=required,
        positional_limit=positional_limit, token_ids_sha256=_sha(artifacts.canonical(ids)),
        tokenizer_manifest=tokenizer_manifest, tokenizer_sha256=_sha(artifacts.canonical(tokenizer_manifest)))
    _save(fixture.directory/'chat-token-ids.json', artifacts.canonical(ids))
    _save(fixture.directory/'token-admission.json', artifacts.canonical(result))
    return result


def identity_from_runtime(startup, admission):
    """Use only a previously descriptor/log-verified startup receipt from the deployer."""
    from .granite_run_artifacts import canonical
    if (startup['schema'] != 'GRANITE_STARTUP_RUNTIME_V1' or
            admission['schema'] != 'GRANITE_TOKEN_ADMISSION_V1' or
            any(startup['runtime']['packages'][name] != value for name,value in TOKENIZER_VERSIONS.items()) or
            startup['environment']['GRANITE_MAX_MODEL_LEN'] != str(admission['max_model_len'])):
        raise ValueError('runtime differs from tokenizer/context admission')
    if _sha(canonical(admission['tokenizer_manifest'])) != admission['tokenizer_sha256']:
        raise ValueError('tokenizer manifest identity mismatch')
    route = context_route('compact_v1')
    return GraniteIdentity(startup['mount']['manifest_sha256'], None, admission['tokenizer_sha256'], 'none',
        canonical(startup).decode(), False, 0, admission['output_tokens'],
        _sha(route.system_text.encode()), SCHEMA_VERSION, route.parser_code_hash(), None)


@dataclass
class LiveFixture:
    directory: Path
    bridge: NativeForecastRefresh
    request: dict
    snapshot: object
    prompt: object
    manifest: dict

    def close(self):
        self.bridge.book.close()
        self.bridge.context.builder.journal.close()


def prepare_fixture(directory):
    """Freeze actual tiny source/model state and exact critic input before hosting."""
    directory = Path(directory)
    directory.mkdir(parents=False, exist_ok=False)
    record = dict(instrument_id=1, publisher_id=1, channel_id=1, order_id=1,
        action='A', side='A', price=101, size=10, flags=128, sequence=0,
        ts_event=1, ts_recv=2, ts_in_delta=1)
    raw = canonical_bytes(pack(record))
    _save(directory/'synthetic-source.c15.json', raw)
    source = dict(schema=SCHEMA, kind='SYNTHETIC_PROBE_ONLY', member='synthetic-source.c15.json',
                  bytes=len(raw), sha256=_sha(raw), records=1)
    scope = SourceScope(ScopeKind.PROBE_ONLY, evidence_hash(source),
        (SourceMember(0, source['member'], source['sha256'], source['bytes'], 1),), ADAPTER_REVISION)
    builder = C15Builder(scope, directory/'evidence.sqlite')
    builder.apply(record, source_member_index=0, session_id='synthetic',
                  raw_symbol='SYN', source_dbn_object=source['member'])
    torch.manual_seed(20)
    native = B1Reasoner(NativeTrunk(NativeRegistry(), d_model=16, n_heads=2, n_layers=1),
                       B1Config(k_max=1, k_fixed=1)).double().eval()
    runner = ContextSessionRunner(native, builder, entity=(1, 1), t_ctx=1)
    torch.manual_seed(8)
    decoder = NativeForecastHeads(16, 8).double().eval()
    with torch.no_grad():
        decoder.time_decoder[-1].weight.zero_()
        decoder.time_decoder[-1].bias[:] = torch.tensor([0., 1.], dtype=torch.float64)
    prior = dict(schema=SCHEMA, kind='SYNTHETIC_PRIOR_CLOSE', event_ns=0, receive_ns=0, price=100.)
    rules = dict(schema=SCHEMA, kind='SYNTHETIC_SESSION_RULES', units=2., tick=.01,
                 opening_ns=[1000,3000,5000], closing_ns=[2000,4000,6000])
    sessions = tuple((ForecastTarget('SYN', str(i), 2000+i*2000),
        ForecastSession('SYN', str(i), 1000+i*2000, 2000+i*2000, 1, 2, 2., .01,
            evidence_hash(rules), evidence_hash(prior), builder.chain.prefix_hash, KnotPolicy(1, 8),
            prior_close=PriceObservation(0, 0, 100., evidence_hash(prior)))) for i in range(3))
    bridge = NativeForecastRefresh(runner, decoder,
        RollingForecastBook(directory/'forecasts.sqlite', create=True),
        tuple(t for t, _ in sessions), RefreshPolicy(((10000, 1),)))
    metadata = dict(specialist='native', group='synthetic', date='19691231',
        reasoning='Synthetic integration fixture; random native weights, no trading or empirical forecast claim.',
        plays_fired=[], plays_stood_down=[], state_defects_and_gaps_reported=[], disposition='ABSTAIN')
    arm = dict(schema=SCHEMA, kind='EVENT_ONLY_UNTRAINED_INTEGRATION', native_seed=20, decoder_seed=8,
               qsv='absent under original event-only encoder policy', teacher='absent')
    request = dict(request_id='synthetic-compact/1', sessions=sessions,
        expected_sessions_hash=session_registry_hash(sessions), arm_hash=evidence_hash(arm),
        as_of=2, source_as_of=1, source_hash=builder.chain.prefix_hash, through_cursor=0,
        metadata=tuple((target.digest, dict(metadata)) for target, _ in sessions))
    mapped, snapshot, prompt = _preview(runner, as_of=2, through_cursor=0, source_as_of=1)
    payloads = {'native-state.c15.json': canonical_bytes(pack(tensor_identity(native.state_dict()))),
                'decoder-state.c15.json': canonical_bytes(pack(asdict(DecoderSnapshot.capture(decoder)))),
                'fixture-inputs.c15.json': canonical_bytes(pack(dict(source=source, scope=scope.public_dict(),
                    prior=prior, rules=rules, arm=arm, request=_request_payload(request)))),
                'compact-snapshot.txt': snapshot.text.encode(), 'compact-prompt.txt': prompt.text.encode()}
    for name, data in payloads.items():
        _save(directory/name, data)
    manifest = dict(schema=SCHEMA, evidence_class='SYNTHETIC_UNTRAINED_NOT_AGENT_FINDINGS',
        source=source, request_hash=evidence_hash(_request_payload(request)),
        native_hash=native_model_pin(bridge), context_encoding='compact_v1',
        snapshot_hash=snapshot.hash, native_snapshot_hash=mapped.hash, prompt_sha256=_sha(prompt.text.encode()),
        source_checkpoint=dict(count=builder.journal.count, head_hash=builder.journal.head_hash),
        files=[dict(path=n,bytes=len(d),sha256=_sha(d)) for n,d in sorted(payloads.items())])
    _save(directory/'fixture-manifest.c15.json', canonical_bytes(pack(manifest)))
    return LiveFixture(directory, bridge, request, snapshot, prompt, manifest)


async def run_fixture(fixture, *, config, identity, expected_prompt_sha256, admission=None, client_factory=None):
    """One real-service request, then trusted reopen/retry with no new calls."""
    if config.region != 'us-east-1' or not config.endpoint_name.startswith('frankie-granite42-'):
        raise ValueError('explicit owned us-east-1 endpoint required')
    if _sha(fixture.prompt.text.encode()) != expected_prompt_sha256:
        raise ValueError('fixture prompt differs from independently frozen pin')
    if evidence_hash(_request_payload(fixture.request)) != fixture.manifest['request_hash']:
        raise ValueError('frozen controller request changed')
    source_data = (fixture.directory/fixture.manifest['source']['member']).read_bytes()
    if _sha(source_data) != fixture.manifest['source']['sha256']:
        raise ValueError('frozen synthetic source bytes changed')
    fixture.bridge.context.builder.journal.verify(**fixture.manifest['source_checkpoint'])
    _, current_snapshot, current_prompt = _preview(fixture.bridge.context, **{
        name:fixture.request[name] for name in ('as_of','through_cursor','source_as_of')})
    if _sha(current_prompt.text.encode()) != expected_prompt_sha256 or current_snapshot.hash != fixture.snapshot.hash:
        raise ValueError('current context differs from frozen predeployment input')
    if client_factory is None and admission is None:
        raise ValueError('real provider call requires measured tokenizer admission')
    if admission is not None and (admission['prompt_sha256'] != expected_prompt_sha256 or
            admission['output_tokens'] != identity.max_tokens or admission['tokenizer_sha256'] != identity.tokenizer_sha):
        raise ValueError('measured admission differs from real request identity')
    for member in fixture.manifest['files']:
        data = (fixture.directory/member['path']).read_bytes()
        if len(data) != member['bytes'] or _sha(data) != member['sha256']:
            raise ValueError('frozen fixture file changed')
    route = context_route('compact_v1')
    route.validate_identity(identity)
    calls = dict(native_forwards=0, provider_calls=0)
    wire = []
    class CountedClient:
        def __init__(self, client):
            self.client = client
        def invoke_endpoint(self, **kwargs):
            calls['provider_calls'] += 1
            wire.append(dict(kwargs))
            return self.client.invoke_endpoint(**kwargs)
    service = build_sagemaker_service(enabled=True, config=config, identity=identity,
        client_factory=lambda selected: CountedClient((client_factory or _client)(selected)))
    journal = ControllerJournal(fixture.directory/'controller.sqlite', create=True)
    controller = FrankieForecastController(enabled=True, bridge=fixture.bridge, journal=journal, critic=service,
        expected_native_hash=fixture.manifest['native_hash'], expected_critic_config_hash=service.config_hash,
        expected_critic_identity_hash=identity.identity_hash, context_encoding='compact_v1')
    code = B1Reasoner.forward_decision.__code__
    previous_profile = sys.getprofile()
    if previous_profile is not None:
        journal.close()
        raise ValueError('fixture forward counter requires an unoccupied profiling hook')
    def profile(frame, event, arg):
        if event == 'call' and frame.f_code is code:
            calls['native_forwards'] += 1
    sys.setprofile(profile)
    try:
        result = await controller.refresh(**fixture.request)
        state = journal.state(fixture.request['request_id'])
        if state['critic_intent']['snapshot_hash'] != fixture.snapshot.hash:
            raise ValueError('actual controller input differs from predeployment fixture')
        checkpoint, native_checkpoint = journal.checkpoint(), fixture.bridge.book.checkpoint()
        before = dict(calls)
        if before != dict(native_forwards=3, provider_calls=1):
            raise ValueError('integration did not perform exactly three native forwards and one provider call')
        journal.close()
        journal = ControllerJournal(fixture.directory/'controller.sqlite', checkpoint=checkpoint)
        fixture.bridge.book.close()
        fixture.bridge.book = RollingForecastBook(fixture.directory/'forecasts.sqlite', checkpoint=native_checkpoint)
        controller.journal = journal
        repeated = await controller.refresh(**fixture.request)
        if evidence_hash(repeated) != evidence_hash(result) or calls != before:
            raise ValueError('trusted restart/retry changed output or invoked work')
        receipt = dict(schema='GRANITE_LIVE_CONTROLLER_RECEIPT_V1', evidence_class=fixture.manifest['evidence_class'],
            result=result, identity=asdict(identity), config=asdict(config), calls=calls,
            retry_identical=True, controller_checkpoint=checkpoint, native_checkpoint=native_checkpoint,
            fixture_hash=evidence_hash(fixture.manifest), prompt_sha256=expected_prompt_sha256)
        if admission is not None:
            import base64
            provider = result['critic']['receipt']['provider_json']
            observed = None
            if provider is not None:
                try:
                    outer = json.loads(provider)
                    if outer.get('body_base64') is not None:
                        response = json.loads(base64.b64decode(outer['body_base64'], validate=True))
                        usage = response.get('usage') if type(response) is dict else None
                        observed = usage.get('prompt_tokens') if type(usage) is dict else None
                except (ValueError, TypeError, UnicodeError) as exc:
                    receipt['provider_usage_error'] = type(exc).__name__
            receipt['token_admission'] = admission
            receipt['provider_prompt_tokens'] = observed
            receipt['token_count_matches'] = type(observed) is int and observed == admission['input_tokens']
        receipt['integration_status'] = ('complete' if result['status'] == 'complete' and
            (admission is None or receipt['token_count_matches']) else 'incomplete')
        _save(fixture.directory/'live-controller-receipt.c15.json', canonical_bytes(pack(receipt)))
        return receipt
    finally:
        sys.setprofile(previous_profile)
        _save(fixture.directory/'provider-requests.c15.json', canonical_bytes(pack(tuple(wire))))
        journal.close()
