"""Local artifacts -> existing native runtime. No implicit ingest or inference."""
from dataclasses import dataclass, fields
import hashlib
from pathlib import Path

try:
    from .b1_reasoner import B1Reasoner
    from .causal_prefix import SourceScope, SourceMember, ScopeKind
    from .context_session import ContextSessionRunner, journal_prefix
    from .context_qsv import QSVContext, QSVRow
    from .forecast_artifact import DecoderSnapshot
    from .forecast_confidence import CalibrationArtifact, resolve_confidence
    from .forecast_contract import sha256_digest
    from .forecast_heads import KnotPolicy
    from .forecast_session import ForecastSession, PriceObservation
    from .forecast_refresh import RefreshPolicy, ForecastRefreshLoop
    from .mbo_source import MboSourcePin, runtime_hash, ingest_sources, SOURCE_EXTRA_FIELDS
    from .native_forecast_refresh import NativeForecastRefresh, session_registry_hash
    from .native_model_artifact import NativeModelSnapshot, decode_exact
    from .qsv_producer import ProducerConfig
    from .rolling_forecast import ForecastTarget
except ImportError:
    from b1_reasoner import B1Reasoner
    from causal_prefix import SourceScope, SourceMember, ScopeKind
    from context_session import ContextSessionRunner, journal_prefix
    from context_qsv import QSVContext, QSVRow
    from forecast_artifact import DecoderSnapshot
    from forecast_confidence import CalibrationArtifact, resolve_confidence
    from forecast_contract import sha256_digest
    from forecast_heads import KnotPolicy
    from forecast_session import ForecastSession, PriceObservation
    from forecast_refresh import RefreshPolicy, ForecastRefreshLoop
    from mbo_source import MboSourcePin, runtime_hash, ingest_sources, SOURCE_EXTRA_FIELDS
    from native_forecast_refresh import NativeForecastRefresh, session_registry_hash
    from native_model_artifact import NativeModelSnapshot, decode_exact
    from qsv_producer import ProducerConfig
    from rolling_forecast import ForecastTarget


def _keys(value, names):
    if type(value) is not dict or set(value) != set(names):
        raise ValueError('unknown or missing configuration fields')
    return value


def _typed(kind, value):
    return kind(**_keys(value, (f.name for f in fields(kind))))


def _read(root, reference):
    _keys(reference, ('path', 'bytes', 'sha256'))
    sha256_digest(reference['sha256'], 'file sha256')
    if (type(reference['path']) is not str or not reference['path']
            or type(reference['bytes']) is not int or reference['bytes'] <= 0):
        raise ValueError('explicit nonempty local artifact reference required')
    payload = (root/reference['path']).read_bytes()
    if len(payload) != reference['bytes'] or hashlib.sha256(payload).hexdigest() != reference['sha256']:
        raise ValueError('artifact bytes differ from independently pinned configuration')
    return payload


def _session(value):
    value = dict(_keys(value, (f.name for f in fields(ForecastSession))))
    value['knot_policy'] = _typed(KnotPolicy, value['knot_policy'])
    for name in ('prior_close', 'opening'):
        if value[name] is not None:
            value[name] = _typed(PriceObservation, value[name])
    if type(value['known_marks']) is not tuple:
        raise ValueError('immutable known marks required')
    value['known_marks'] = tuple(_typed(PriceObservation, mark) for mark in value['known_marks'])
    session = ForecastSession(**value)
    session.validate_for_publication()
    return session


@dataclass(frozen=True)
class SourceBinding:
    scope: SourceScope
    expected_scope_hash: str
    pin: MboSourcePin
    paths: tuple[Path, ...]
    session_ids: tuple[str, ...]
    raw_symbol: str | None
    evidence: bytes

    def ingest(self, journal_path):
        """Explicit local ingestion; retains failures per the existing source driver."""
        return ingest_sources(self.scope, self.paths, journal_path, self.pin,
            expected_scope_hash=self.expected_scope_hash, session_ids=self.session_ids,
            raw_symbol=self.raw_symbol)


@dataclass(frozen=True)
class ProductionBindings:
    config_bytes: bytes
    source: SourceBinding
    native: NativeModelSnapshot
    decoder: DecoderSnapshot | None
    sessions: tuple
    expected_sessions_hash: str | None
    cadence: RefreshPolicy | None
    entity: tuple[int, int]
    t_ctx: int
    qsv: QSVContext | None
    qsv_mapping_evidence: bytes | None
    calibration: CalibrationArtifact | None
    expected_calibration_hash: str | None

    def ingest(self, journal_path):
        return self.source.ingest(journal_path)

    def context(self, builder, *, expected_builder_state_hash, teacher=None):
        """Assemble a context from a separately trusted complete source checkpoint."""
        sha256_digest(expected_builder_state_hash, 'builder checkpoint')
        if builder.scope.genesis_hash() != self.source.expected_scope_hash:
            raise ValueError('builder source scope differs')
        state = builder.export_state()
        if state['state_hash'] != expected_builder_state_hash:
            raise ValueError('builder checkpoint differs')
        builder.journal.verify(count=state['journal_count'], head_hash=state['journal_hash'])
        for entry in journal_prefix(builder, builder.chain.next_cursor-1):
            if entry['raw_record'].get('dbn_extraction_hash') != self.source.pin.digest:
                raise ValueError('builder extraction pin differs')
            if entry['session_id'] != self.source.session_ids[entry['source_member_index']]:
                raise ValueError('builder source session differs')
        return ContextSessionRunner(self.native.restore(), builder, entity=self.entity,
            t_ctx=self.t_ctx, teacher=teacher, qsv=self.qsv,
            expected_qsv_hash=self.qsv.digest if self.qsv is not None else None)

    def assemble(self, builder, book, *, expected_builder_state_hash, teacher=None):
        """Return the existing B1 forecast bridge; do not invoke its update method."""
        if self.decoder is None:
            raise ValueError('forecast assembly requires B1, decoder and sessions')
        context = self.context(builder, expected_builder_state_hash=expected_builder_state_hash, teacher=teacher)
        if any(session.source_hash != builder.chain.prefix_hash for _, session in self.sessions):
            raise ValueError('session source prefix differs from assembled checkpoint')
        return NativeForecastRefresh(context, self.decoder.restore(), book,
            tuple(target for target, _ in self.sessions), self.cadence)

    def confidence(self, *, logit, policy, context):
        """Existing eligibility resolver; missing/ineligible calibration stays null."""
        return resolve_confidence(logit=logit, policy=policy, context=context,
            artifact=self.calibration, trusted_artifact_hash=self.expected_calibration_hash)


def load_bindings(path, *, expected_sha256):
    """Read pinned local files once. Caller owns the independent config SHA origin.

    Config and artifact files use canonical_bytes(pack(value)), preserving exact
    floats, bytes and tuples. Every optional field is explicitly null when absent.
    Source files are opened only by the subsequent explicit ingest() call.
    """
    path = Path(path)
    sha256_digest(expected_sha256, 'configuration sha256')
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise ValueError('configuration bytes differ')
    config = _keys(decode_exact(payload), ('schema', 'source', 'native', 'decoder',
        'sessions', 'expected_sessions_hash', 'cadence', 'entity', 't_ctx', 'qsv', 'calibration'))
    if config['schema'] != 'BOSS_PRODUCTION_BINDINGS_V1':
        raise ValueError('unknown production configuration schema')
    root = path.parent
    def artifact(ref):
        return decode_exact(_read(root, ref))
    source = _keys(config['source'], ('scope', 'expected_scope_hash', 'pin', 'paths',
                                     'session_ids', 'raw_symbol', 'evidence'))
    scope_value = dict(_keys(source['scope'], ('kind', 'scope_id', 'members', 'adapter_revision')))
    if type(scope_value['members']) is not tuple:
        raise ValueError('immutable complete source roster required')
    scope_value['kind'] = ScopeKind(scope_value['kind'])
    scope_value['members'] = tuple(_typed(SourceMember, member) for member in scope_value['members'])
    scope = SourceScope(**scope_value)
    if scope.genesis_hash() != source['expected_scope_hash']:
        raise ValueError('source scope differs from trusted identity')
    pin = _typed(MboSourcePin, source['pin'])
    if pin.runtime_hash != runtime_hash():
        raise ValueError('source runtime differs')
    for name in ('paths', 'session_ids'):
        if (type(source[name]) is not tuple or len(source[name]) != len(scope.members)
                or any(type(item) is not str or not item for item in source[name])):
            raise ValueError('complete ordered source paths and sessions required')
    if source['raw_symbol'] is not None and type(source['raw_symbol']) is not str:
        raise ValueError('explicit raw symbol or null required')
    source_binding = SourceBinding(scope, scope.genesis_hash(), pin,
        tuple(root/item for item in source['paths']), source['session_ids'], source['raw_symbol'],
        _read(root, source['evidence']))
    native = _typed(NativeModelSnapshot, artifact(config['native']))
    model = native.restore()
    trunk = model.trunk if type(model) is B1Reasoner else model
    if not set(SOURCE_EXTRA_FIELDS).issubset(trunk.registry.extra_fields):
        raise ValueError('native registry must retain complete extraction evidence')
    if (type(config['entity']) is not tuple or len(config['entity']) != 2
            or any(type(n) is not int for n in config['entity'])
            or type(config['t_ctx']) is not int or config['t_ctx'] < 1):
        raise ValueError('explicit entity and positive context length required')
    decoder = cadence = expected_sessions_hash = None
    sessions = ()
    if any(config[key] is not None for key in ('decoder', 'sessions', 'expected_sessions_hash', 'cadence')):
        if type(model) is not B1Reasoner or any(config[key] is None for key in ('decoder', 'sessions', 'expected_sessions_hash', 'cadence')):
            raise ValueError('B1 forecasting requires complete decoder/session/cadence configuration')
        decoder = _typed(DecoderSnapshot, artifact(config['decoder']))
        decoder.restore()
        if decoder.d_model != trunk.cfg.d_model:
            raise ValueError('decoder and native representation dimensions differ')
        rows = artifact(config['sessions'])
        if type(rows) is not tuple or any(type(row) is not tuple or len(row) != 2 for row in rows):
            raise ValueError('complete immutable session registry required')
        sessions = tuple((_typed(ForecastTarget, target), _session(session)) for target, session in rows)
        expected_sessions_hash = config['expected_sessions_hash']
        if session_registry_hash(sessions) != expected_sessions_hash:
            raise ValueError('session registry differs')
        cadence = _typed(RefreshPolicy, config['cadence'])
        ForecastRefreshLoop(None, tuple(t for t, _ in sessions), cadence)
        for target, session in sessions:
            if target.instrument != session.instrument or target.target_ns != session.close_ns:
                raise ValueError('target must be its declared session close')
            cadence.interval(target.target_ns-session.receive_cutoff_ns)
        if len({(s.event_cutoff_ns, s.receive_cutoff_ns, s.source_hash) for _, s in sessions}) != 1:
            raise ValueError('all sessions must share one causal source state')
    qsv = qsv_evidence = None
    if config['qsv'] is not None:
        value = _keys(config['qsv'], ('artifact', 'producer', 'expected_artifact_hash', 'mapping_evidence'))
        producer = _typed(ProducerConfig, value['producer'])
        qsv_value = dict(_keys(artifact(value['artifact']), ('producer_id', 'names', 'rows')))
        if type(qsv_value['rows']) is not tuple:
            raise ValueError('immutable QSV rows required')
        qsv_value['rows'] = tuple(_typed(QSVRow, row) for row in qsv_value['rows'])
        qsv = QSVContext(**qsv_value)
        if qsv.digest != value['expected_artifact_hash'] or qsv.producer_id != producer.digest:
            raise ValueError('QSV producer or artifact differs')
        qsv_evidence = _read(root, value['mapping_evidence'])
    if trunk.cfg.use_qsv and not trunk.encoder._qsv_ablated and qsv is None:
        raise ValueError('unablated QSV requires an explicit artifact')
    calibration = calibration_hash = None
    if config['calibration'] is not None:
        value = _keys(config['calibration'], ('artifact', 'expected_artifact_hash'))
        calibration = _typed(CalibrationArtifact, artifact(value['artifact']))
        calibration_hash = value['expected_artifact_hash']
        if calibration.digest != calibration_hash:
            raise ValueError('calibration artifact differs')
    return ProductionBindings(payload, source_binding, native, decoder, sessions,
        expected_sessions_hash, cadence, config['entity'], config['t_ctx'], qsv,
        qsv_evidence, calibration, calibration_hash)
