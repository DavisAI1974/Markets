"""Immutable, queryable native forecast snapshots; CPU float64 software candidate.

Snapshots contain exact decoder tensors and native state, never future labels.
The runtime/code lock must still match when an artifact is queried later.
"""
from dataclasses import asdict, dataclass
from pathlib import Path
import sys
import json
import torch

try:
    from .c15_journal import evidence_hash, pack, unpack, canonical_bytes
    from .context_session import tensor_identity
    from .forecast_contract import HashedContract, finite_number, sha256_digest
    from .forecast_heads import NativeForecastHeads, KnotPolicy
    from .forecast_session import ForecastSession, PriceObservation
except ImportError:
    from c15_journal import evidence_hash, pack, unpack, canonical_bytes
    from context_session import tensor_identity
    from forecast_contract import HashedContract, finite_number, sha256_digest
    from forecast_heads import NativeForecastHeads, KnotPolicy
    from forecast_session import ForecastSession, PriceObservation


def runtime_hash():
    names = ('forecast_heads.py', 'forecast_session.py', 'forecast_artifact.py')
    subnormal = torch.frombuffer(bytearray.fromhex('0100000000000000'), dtype=torch.float64)
    denormal_probe = (subnormal + subnormal).view(torch.uint8).numpy().tobytes()
    return evidence_hash(dict(code={n: Path(__file__).with_name(n).read_bytes() for n in names},
        python=sys.version, torch=str(torch.__version__), device='cpu', dtype='float64',
        byteorder=sys.byteorder, cpu=torch.backends.cpu.get_cpu_capability(),
        torch_build=torch.__config__.show(), denormal_probe=denormal_probe,
        mkldnn=torch.backends.mkldnn.enabled, default_device=str(torch.get_default_device()),
        deterministic=torch.are_deterministic_algorithms_enabled(),
        threads=torch.get_num_threads(), interop_threads=torch.get_num_interop_threads()))


@dataclass(frozen=True, slots=True)
class DecoderSnapshot(HashedContract):
    d_model: int
    hidden: int
    weights: bytes
    runtime: str

    def __post_init__(self):
        if (any(type(v) is not int or v < 1 for v in (self.d_model, self.hidden))
                or type(self.weights) is not bytes or not self.weights):
            raise ValueError('immutable decoder weights and positive dimensions required')
        sha256_digest(self.runtime, 'runtime')

    @classmethod
    def capture(cls, decoder):
        if (type(decoder) is not NativeForecastHeads or any(m.training for m in decoder.modules())
                or any(p.dtype != torch.float64 or p.device.type != 'cpu'
                       or not torch.isfinite(p).all() for p in decoder.parameters())):
            raise ValueError('native snapshot requires finite float64 CPU decoder in eval mode')
        with torch.random.fork_rng(devices=[]):
            canonical = NativeForecastHeads(decoder.d_model, decoder.hidden).eval()
        expected = dict(canonical.named_modules())
        methods = ('forward', 'gap', 'path', 'knots', 'condition', 'next_time')
        if (repr(decoder) != repr(canonical) or
                any(type(module) is not type(expected.get(name))
                    or any(method in vars(module) for method in methods)
                    or module._forward_hooks or module._forward_pre_hooks
                    for name, module in decoder.named_modules())):
            raise ValueError('decoder architecture differs from the versioned snapshot implementation')
        return cls(decoder.d_model, decoder.hidden, canonical_bytes(pack(tensor_identity(decoder.state_dict()))), runtime_hash())

    def restore(self):
        if self.runtime != runtime_hash():
            raise ValueError('frozen forecast runtime or code differs')
        # Construction must not consume the caller's RNG stream. No B1 forward.
        with torch.random.fork_rng(devices=[]):
            decoder = NativeForecastHeads(self.d_model, self.hidden).eval()
        weights = unpack(json.loads(self.weights))
        if set(weights) != set(decoder.state_dict()):
            raise ValueError('frozen decoder state keys differ')
        for name, value in weights.items():
            if value['dtype'] != 'torch.float64' or tuple(value['shape']) != tuple(decoder.state_dict()[name].shape):
                raise ValueError('frozen decoder tensor contract differs')
        decoder.load_state_dict({name: torch.frombuffer(bytearray(value['bytes']), dtype=torch.float64)
                                 .reshape(value['shape']).clone() for name, value in weights.items()})
        if any(not torch.isfinite(p).all() for p in decoder.parameters()):
            raise ValueError('nonfinite frozen weights')
        decoder.requires_grad_(False)
        return decoder


@dataclass(frozen=True, slots=True)
class ForecastPoint:
    time_ns: int
    quantiles: tuple[float, float, float]
    observed: bool

    def __post_init__(self):
        if (type(self.time_ns) is not int or type(self.observed) is not bool
                or type(self.quantiles) is not tuple or len(self.quantiles) != 3):
            raise ValueError('immutable typed forecast point required')
        for value in self.quantiles:
            finite_number(value, 'quantile')
        if not self.quantiles[0] <= self.quantiles[1] <= self.quantiles[2]:
            raise ValueError('crossing quantiles')

    @property
    def p50(self):
        return self.quantiles[1]


@dataclass(frozen=True, slots=True)
class NativeForecastArtifact(HashedContract):
    session: ForecastSession
    snapshot: DecoderSnapshot
    representation: tuple[float, ...]
    native_model_hash: str
    input_hash: str
    arm_hash: str
    gap_quantiles: tuple[float, float, float]
    gap_observed: bool
    points: tuple[ForecastPoint, ...]
    net_usd: float
    context_receipt: bytes | None = None

    def __post_init__(self):
        if not isinstance(self.session, ForecastSession) or not isinstance(self.snapshot, DecoderSnapshot):
            raise ValueError('typed session and decoder snapshot required')
        for name in ('native_model_hash', 'input_hash', 'arm_hash'):
            sha256_digest(getattr(self, name), name)
        if self.context_receipt is not None:
            if type(self.context_receipt) is not bytes:
                raise ValueError('immutable context receipt required')
            binding = unpack(json.loads(self.context_receipt))
            if (binding['context']['input_hash'] != self.input_hash
                    or binding['context']['model_hash'] != self.native_model_hash
                    or binding['context']['source_prefix_hash'] != self.session.source_hash
                    or binding['context']['as_of'] != self.session.receive_cutoff_ns):
                raise ValueError('context receipt differs from forecast source/model')
        if type(self.representation) is not tuple or len(self.representation) != self.snapshot.d_model:
            raise ValueError('immutable native representation required')
        for value in self.representation:
            finite_number(value, 'native representation')
        if (type(self.points) is not tuple or len(self.points) < 2
                or any(not isinstance(p, ForecastPoint) for p in self.points)):
            raise ValueError('complete immutable path required')
        if (self.points[0].time_ns != self.session.open_ns or self.points[0].p50 != 0
                or self.points[-1].time_ns != self.session.close_ns
                or any(a.time_ns >= b.time_ns for a, b in zip(self.points, self.points[1:]))):
            raise ValueError('path must cover the session in strict time order from zero')
        finite_number(self.net_usd, 'net')
        if self.net_usd != self.gap_quantiles[1] + self.points[-1].p50:
            raise ValueError('net must equal gap plus terminal, without a separate median claim')
        decoder = self.snapshot.restore()
        z = decoder.condition(torch.tensor(self.representation, dtype=torch.float64), self.session.features)
        s = self.session
        times = decoder.knots(z, duration_ns=s.duration_ns,
            start_ns=s.anchor_ns-s.open_ns, policy=s.knot_policy)
        expected_times = ((s.open_ns,) + tuple(m.event_ns for m in s.known_marks)
                          + tuple(s.open_ns+t for t in times[1:]))
        if tuple(p.time_ns for p in self.points) != expected_times:
            raise ValueError('path times differ from frozen endogenous emissions')
        observed = self.session.event_cutoff_ns >= self.session.open_ns
        expected_gap = ((self.session.observed_gap,) * 3 if observed else tuple(decoder.gap(z).tolist()))
        if type(self.gap_observed) is not bool or self.gap_observed != observed or self.gap_quantiles != expected_gap:
            raise ValueError('gap differs from frozen native/observed value')
        for point in self.points:
            if (type(point.observed) is not bool or point.observed != (observed and point.time_ns <= self.session.anchor_ns)
                    or point.quantiles != self._query(point.time_ns, decoder, z)):
                raise ValueError('point differs from frozen native query or observation')

    def _query(self, time_ns, decoder, z):
        s = self.session
        if type(time_ns) is not int or not s.open_ns <= time_ns <= s.close_ns:
            raise ValueError('query must be absolute integer UTC ns inside the session')
        if time_ns == s.open_ns:
            return (0., 0., 0.)
        if time_ns <= s.anchor_ns:
            marks = {m.event_ns: m for m in s.known_marks}
            if time_ns not in marks:
                raise ValueError('past query has no certified observed mark; interpolation is forbidden')
            return (s.movement(marks[time_ns]),) * 3
        anchor = (s.anchor_ns - s.open_ns) / s.duration_ns
        amount = s.movement(s.known_marks[-1]) if s.known_marks else 0.
        return tuple(decoder.path(z, (time_ns-s.open_ns)/s.duration_ns,
                                  anchor=anchor, anchor_usd=amount).tolist())

    def query(self, time_ns):
        with torch.no_grad():
            decoder = self.snapshot.restore()
            z = decoder.condition(torch.tensor(self.representation, dtype=torch.float64), self.session.features)
            return self._query(time_ns, decoder, z)

    @property
    def payload(self):
        return canonical_bytes(pack(dict(schema='BOSS_NATIVE_FORECAST_V1', **asdict(self))))

    @classmethod
    def from_payload(cls, payload, *, expected_digest):
        sha256_digest(expected_digest, 'trusted forecast digest')
        if type(payload) is not bytes:
            raise ValueError('immutable forecast bytes required')
        fields = unpack(json.loads(payload))
        if fields.pop('schema') != 'BOSS_NATIVE_FORECAST_V1':
            raise ValueError('unsupported native forecast schema')
        session = fields['session']
        session['knot_policy'] = KnotPolicy(**session['knot_policy'])
        for name in ('prior_close', 'opening'):
            if session[name] is not None:
                session[name] = PriceObservation(**session[name])
        session['known_marks'] = tuple(PriceObservation(**m) for m in session['known_marks'])
        fields['session'] = ForecastSession(**session)
        fields['snapshot'] = DecoderSnapshot(**fields['snapshot'])
        fields['points'] = tuple(ForecastPoint(**p) for p in fields['points'])
        artifact = cls(**fields)
        if artifact.digest != expected_digest or artifact.payload != payload:
            raise ValueError('forecast differs from trusted artifact identity')
        return artifact


def freeze_forecast(decoder, representation, session, *, native_model_hash, input_hash, arm_hash, context_receipt=None):
    decoder._state(representation)
    snapshot = DecoderSnapshot.capture(decoder)
    # Generate using the same frozen weights used by subsequent audit queries.
    frozen = snapshot.restore()
    native = representation.detach().cpu().clone()
    z = frozen.condition(native, session.features)
    observed = session.event_cutoff_ns >= session.open_ns
    with torch.no_grad():
        gap = (session.observed_gap,) * 3 if observed else tuple(frozen.gap(z).tolist())
        times = frozen.knots(z, duration_ns=session.duration_ns,
            start_ns=session.anchor_ns-session.open_ns, policy=session.knot_policy)
        points = [ForecastPoint(session.open_ns, (0., 0., 0.), observed)]
        points.extend(ForecastPoint(m.event_ns, (session.movement(m),)*3, True) for m in session.known_marks)
        anchor = (session.anchor_ns-session.open_ns)/session.duration_ns
        amount = session.movement(session.known_marks[-1]) if session.known_marks else 0.
        for offset in times[1:]:
            values = tuple(frozen.path(z, offset/session.duration_ns, anchor=anchor, anchor_usd=amount).tolist())
            points.append(ForecastPoint(session.open_ns+offset, values, False))
    return NativeForecastArtifact(session, snapshot, tuple(native.tolist()), native_model_hash, input_hash,
                                  arm_hash, gap, observed, tuple(points), gap[1]+points[-1].p50, context_receipt)
