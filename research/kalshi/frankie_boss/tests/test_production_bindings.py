"""Configured local SDK source and native forecast, entirely synthetic."""
from dataclasses import asdict
import hashlib
import pytest
import torch
from b1_reasoner import B1Reasoner, B1Config
from c15_journal import canonical_bytes, pack
from context_qsv import QSVContext, QSVRow
from forecast_artifact import DecoderSnapshot
from forecast_confidence import CalibrationArtifact, ForecastErrorPolicy, ConfidenceContext
from forecast_heads import NativeForecastHeads, KnotPolicy
from forecast_refresh import RefreshPolicy
from forecast_session import ForecastSession, PriceObservation
from native_forecast_refresh import session_registry_hash
from native_mbo_encoder import NativeTrunk, NativeRegistry
from native_model_artifact import NativeModelSnapshot
from mbo_source import SOURCE_EXTRA_FIELDS
from production_bindings import load_bindings
from qsv_producer import ProducerConfig
from research.refrag.qsv_registry import QSV_FEATURE_REGISTRY
from rolling_forecast import ForecastTarget, RollingForecastBook
from source_conformance import SourceConformanceDriver
from test_mbo_source import source, dbn_bytes, record, pin

H = 'a'*64


def saved(tmp_path, name, value):
    payload = canonical_bytes(pack(value))
    (tmp_path/name).write_bytes(payload)
    return dict(path=name, sha256=hashlib.sha256(payload).hexdigest(), bytes=len(payload))


def configuration(tmp_path, *, b1=True, qsv=False, records=1):
    from mbo_source import ingest_sources
    path, scope = source(tmp_path, dbn_bytes([record(i+1) for i in range(records)]), records)
    extraction = pin()
    result = ingest_sources(scope, (path,), tmp_path/'source.sqlite', extraction,
        expected_scope_hash=scope.genesis_hash(), session_ids=('SYN',))
    driver = SourceConformanceDriver.restore(scope, tmp_path/'source.sqlite', result.checkpoint,
        expected_scope_hash=scope.genesis_hash(), expected_state_hash=result.completion.builder_state_hash)
    native = NativeTrunk(NativeRegistry(SOURCE_EXTRA_FIELDS), d_model=16, n_heads=2,
                         n_layers=1, use_qsv=qsv).double().eval()
    model = B1Reasoner(native, B1Config(k_max=1, k_fixed=1)).double().eval() if b1 else native
    decoder = NativeForecastHeads(16, 8).eval()
    with torch.no_grad():
        decoder.time_decoder[-1].weight.zero_()
        decoder.time_decoder[-1].bias[:] = torch.tensor([0., 1.])
    target = ForecastTarget('SYN', 'close', 2000)
    session = ForecastSession('SYN', 'SYN', 1000, 2000, 100, 101, 1., .01,
        H, H, driver._builder.chain.prefix_hash, KnotPolicy(1, 8),
        prior_close=PriceObservation(0, 0, 100., H))
    sessions = ((target, session),)
    config = dict(schema='BOSS_PRODUCTION_BINDINGS_V1',
        source=dict(scope=dict(kind=scope.kind.value, scope_id=scope.scope_id,
            members=tuple(asdict(m) for m in scope.members), adapter_revision=scope.adapter_revision),
            expected_scope_hash=scope.genesis_hash(), pin=asdict(extraction), paths=(path.name,),
            session_ids=('SYN',), raw_symbol=None,
            evidence=saved(tmp_path, 'source-evidence.json', {'explicit_source_mapping': 'synthetic fixture'})),
        native=saved(tmp_path, 'native.json', asdict(NativeModelSnapshot.capture(model))),
        decoder=saved(tmp_path, 'decoder.json', asdict(DecoderSnapshot.capture(decoder))) if b1 else None,
        sessions=saved(tmp_path, 'sessions.json', tuple((asdict(t), asdict(s)) for t,s in sessions)) if b1 else None,
        expected_sessions_hash=session_registry_hash(sessions) if b1 else None,
        cadence=asdict(RefreshPolicy(((10000, 1),))) if b1 else None,
        entity=(1, 1), t_ctx=64, qsv=None, calibration=None)
    if qsv:
        producer = ProducerConfig('synthetic bars', H, H, H, H)
        artifact = QSVContext(producer.digest, QSV_FEATURE_REGISTRY, (
            QSVRow(0, (1, 1), 101, session.source_hash,
                   (0.,)*len(QSV_FEATURE_REGISTRY), (True,)*len(QSV_FEATURE_REGISTRY)),))
        config['qsv'] = dict(artifact=saved(tmp_path, 'qsv.json', asdict(artifact)),
            producer=asdict(producer), expected_artifact_hash=artifact.digest,
            mapping_evidence=saved(tmp_path, 'mapping.json', {'mapping': 'explicit synthetic mapping'}))
    return config, driver, result


def load(tmp_path, config):
    ref = saved(tmp_path, 'config.json', config)
    return load_bindings(tmp_path/ref['path'], expected_sha256=ref['sha256'])


@pytest.mark.parametrize('b1,qsv', [(False, False), (True, False), (True, True)])
def test_local_configuration_drives_existing_runtime(tmp_path, b1, qsv):
    config, driver, ingestion = configuration(tmp_path, b1=b1, qsv=qsv)
    try:
        bundle = load(tmp_path, config)
        checkpoint = ingestion.completion.builder_state_hash
        context = bundle.context(driver._builder, expected_builder_state_hash=checkpoint)
        output = context.run(as_of=101)
        assert output.receipt.consumed_rows == 1
        if b1:
            book = RollingForecastBook(tmp_path/'forecast.sqlite', create=True)
            try:
                bridge = bundle.assemble(driver._builder, book, expected_builder_state_hash=checkpoint)
                session = bundle.sessions[0][1]
                result = bridge.update(sessions=bundle.sessions,
                    expected_sessions_hash=bundle.expected_sessions_hash, arm_hash=H,
                    as_of=101, source_as_of=100, source_hash=session.source_hash)
                assert len(result) == 1 and result[0].selected.score is None
            finally: book.close()
        else:
            with pytest.raises(ValueError, match='B1'): bundle.assemble(driver._builder, None, expected_builder_state_hash=checkpoint)
        # Explicit ingestion uses configured coordinates, never runs during loading.
        assert not (tmp_path/'second.sqlite').exists()
        second = bundle.ingest(tmp_path/'second.sqlite')
        assert second.completion == ingestion.completion
    finally: driver.close()


@pytest.mark.parametrize('change', ['config_pin', 'file_bytes', 'extra', 'missing', 'runtime', 'sessions', 'dimension', 'qsv_required'])
def test_bad_binding_fails_before_runtime_use(tmp_path, change):
    config, driver, _ = configuration(tmp_path)
    try:
        if change == 'config_pin':
            ref=saved(tmp_path,'config.json',config)
            with pytest.raises(ValueError): load_bindings(tmp_path/ref['path'], expected_sha256='0'*64)
            return
        if change == 'file_bytes': (tmp_path/'native.json').write_bytes(b'changed')
        if change == 'extra': config['unknown'] = True
        if change == 'missing': del config['entity']
        if change == 'runtime': config['source']['pin']['runtime_hash'] = '0'*64
        if change == 'sessions': config['expected_sessions_hash'] = '0'*64
        if change == 'dimension': config['decoder'] = saved(tmp_path, 'decoder.json', asdict(DecoderSnapshot.capture(NativeForecastHeads(8,8).eval())))
        if change == 'qsv_required':
            model = B1Reasoner(NativeTrunk(NativeRegistry(SOURCE_EXTRA_FIELDS), d_model=16,n_heads=2,n_layers=1,use_qsv=True), B1Config()).double().eval()
            config['native'] = saved(tmp_path,'native.json',asdict(NativeModelSnapshot.capture(model)))
        with pytest.raises(ValueError): load(tmp_path,config)
    finally: driver.close()


def test_wrong_checkpoint_or_extraction_rejected(tmp_path):
    config, driver, ingestion = configuration(tmp_path)
    try:
        bundle = load(tmp_path, config)
        with pytest.raises(ValueError, match='checkpoint'):
            bundle.context(driver._builder, expected_builder_state_hash='0'*64)
        config['source']['pin']['dbn_version'] = 2
        wrong = load(tmp_path, config)
        with pytest.raises(ValueError, match='extraction'):
            wrong.context(driver._builder, expected_builder_state_hash=ingestion.completion.builder_state_hash)
    finally: driver.close()


def test_calibration_uses_existing_nullable_eligibility(tmp_path):
    config, driver, _ = configuration(tmp_path)
    try:
        policy = ForecastErrorPolicy(1., 1., 1., H, H)
        context = ConfidenceContext(H, H, 'synthetic', 10)
        assert load(tmp_path,config).confidence(logit=0., policy=policy, context=context).probability is None
        artifact = CalibrationArtifact(H,H,policy.digest,H,('synthetic',),0,20,1.,0.)
        config['calibration'] = dict(artifact=saved(tmp_path,'calibration.json',asdict(artifact)), expected_artifact_hash=artifact.digest)
        bound = load(tmp_path,config)
        assert bound.confidence(logit=0.,policy=policy,context=context).probability == .5
        assert bound.confidence(logit=0.,policy=policy,context=ConfidenceContext(H,H,'other',10)).probability is None
    finally: driver.close()


def test_loading_never_forwards_or_ingests(tmp_path, monkeypatch):
    import production_bindings
    config, driver, _ = configuration(tmp_path)
    def forbidden(*args, **kwargs):
        raise AssertionError('loader performed operational work')
    try:
        monkeypatch.setattr(production_bindings, 'ingest_sources', forbidden)
        monkeypatch.setattr(B1Reasoner, 'forward_decision', forbidden)
        assert load(tmp_path, config).sessions
    finally: driver.close()


@pytest.mark.parametrize('change', ['source_evidence', 'path_roster', 'native_registry', 'qsv_identity', 'calibration_pin'])
def test_nested_binding_evidence_is_required(tmp_path, change):
    config, driver, _ = configuration(tmp_path, qsv=True)
    try:
        if change == 'source_evidence': (tmp_path/'source-evidence.json').write_bytes(b'x')
        if change == 'path_roster': config['source']['paths'] = ()
        if change == 'native_registry':
            model = B1Reasoner(NativeTrunk(NativeRegistry(),d_model=16,n_heads=2,n_layers=1),B1Config()).double().eval()
            config['native']=saved(tmp_path,'native.json',asdict(NativeModelSnapshot.capture(model)))
        if change == 'qsv_identity': config['qsv']['expected_artifact_hash']='0'*64
        if change == 'calibration_pin':
            policy=ForecastErrorPolicy(1.,1.,1.,H,H)
            artifact=CalibrationArtifact(H,H,policy.digest,H,('synthetic',),0,20,1.,0.)
            config['calibration']=dict(artifact=saved(tmp_path,'cal.json',asdict(artifact)),expected_artifact_hash='0'*64)
        with pytest.raises(ValueError): load(tmp_path,config)
    finally: driver.close()


def test_configured_session_and_qsv_coverage_reach_existing_guards(tmp_path):
    config, driver, ingestion = configuration(tmp_path, qsv=True)
    try:
        config['source']['session_ids']=('different',)
        bundle=load(tmp_path,config)
        with pytest.raises(ValueError,match='source session'):
            bundle.context(driver._builder,expected_builder_state_hash=ingestion.completion.builder_state_hash)
        config['source']['session_ids']=('SYN',)
        from native_model_artifact import decode_exact
        qsv_value=decode_exact((tmp_path/'qsv.json').read_bytes())
        qsv_value['rows'][0]['source_prefix_hash']='0'*64
        config['qsv']['artifact']=saved(tmp_path,'qsv.json',qsv_value)
        changed=QSVContext(qsv_value['producer_id'],qsv_value['names'],tuple(QSVRow(**r) for r in qsv_value['rows']))
        config['qsv']['expected_artifact_hash']=changed.digest
        bundle=load(tmp_path,config)
        context=bundle.context(driver._builder,expected_builder_state_hash=ingestion.completion.builder_state_hash)
        with pytest.raises(ValueError,match='QSV lacks'):
            context.run(as_of=101)
    finally: driver.close()


def test_complete_source_required_but_causal_prefix_remains_available(tmp_path):
    from mbo_source import extract_mbo
    config, driver, ingestion = configuration(tmp_path, records=2)
    partial = SourceConformanceDriver(driver.scope, tmp_path/'partial.sqlite',
        expected_scope_hash=driver.scope.genesis_hash())
    try:
        partial.append(extract_mbo(record(), pin()), cursor=0, source_member_index=0,
            source_sha256=driver.scope.members[0].sha256, session_id='SYN')
        bundle = load(tmp_path,config)
        with pytest.raises(ValueError,match='incomplete'):
            bundle.context(partial._builder,
                expected_builder_state_hash=partial._builder.export_state()['state_hash'])
        context = bundle.context(driver._builder,
            expected_builder_state_hash=ingestion.completion.builder_state_hash)
        assert context.run(as_of=101,through_cursor=0).receipt.consumed_rows == 1
    finally:
        partial.close()
        driver.close()


def test_existing_builder_must_match_configured_raw_symbol(tmp_path):
    config, driver, ingestion = configuration(tmp_path)
    try:
        config['source']['raw_symbol']='DIFFERENT-FROM-JOURNAL'
        with pytest.raises(ValueError,match='raw symbol'):
            load(tmp_path,config).context(driver._builder,
                expected_builder_state_hash=ingestion.completion.builder_state_hash)
    finally: driver.close()


def test_qsv_cannot_be_bound_to_model_without_qsv_path(tmp_path):
    config, driver, _ = configuration(tmp_path,qsv=True)
    try:
        model=B1Reasoner(NativeTrunk(NativeRegistry(SOURCE_EXTRA_FIELDS),d_model=16,
            n_heads=2,n_layers=1,use_qsv=False),B1Config(k_max=1,k_fixed=1)).double().eval()
        config['native']=saved(tmp_path,'native.json',asdict(NativeModelSnapshot.capture(model)))
        with pytest.raises(ValueError,match='QSV'):
            load(tmp_path,config)
    finally: driver.close()
