"""Immutable, queryable native forecast snapshots; CPU float64 software candidate.

Snapshots contain exact decoder tensors and native state, never future labels.
The runtime/code lock must still match when an artifact is queried later.
"""
from dataclasses import asdict, dataclass, replace
from pathlib import Path
import sys
import json
import math
import struct
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
        # Structural validation must not instantiate today's decoder: archived
        # four-coordinate snapshots remain readable after model/runtime changes.
        weights = unpack(json.loads(self.weights))
        shapes = {}
        for name, width, output in (('gap_median', self.d_model, 1),
                ('gap_tails', self.d_model, 2), ('path_median', self.d_model+2, 1),
                ('path_tails', self.d_model+2, 2), ('time_decoder', self.d_model+2, 2)):
            shapes.update({name+'.0.weight': (self.hidden, width), name+'.0.bias': (self.hidden,),
                           name+'.2.weight': (output, self.hidden), name+'.2.bias': (output,)})
        if type(weights) is not dict or set(weights) != set(shapes) | {'session_projection.weight'}:
            raise ValueError('frozen decoder state keys differ')
        for name, value in weights.items():
            if type(value) is not dict or set(value) != {'dtype', 'shape', 'bytes'}:
                raise ValueError('malformed frozen tensor')
            shape = value['shape']
            valid_shape = (shape in ((self.d_model, 4), (self.d_model, 5))
                           if name == 'session_projection.weight' else shape == shapes[name])
            if (type(shape) is not tuple or any(type(n) is not int or n < 1 for n in shape)
                    or not valid_shape or value['dtype'] != 'torch.float64'
                    or type(value['bytes']) is not bytes or len(value['bytes']) != math.prod(shape)*8
                    or any(not math.isfinite(v) for (v,) in struct.iter_unpack('=d', value['bytes']))):
                raise ValueError('frozen decoder tensor contract differs')

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
            if 'publication_validation' in binding:
                marker = binding.pop('publication_validation')
                fields = asdict(self)
                fields['context_receipt'] = canonical_bytes(pack(binding))
                reproduced_hash = evidence_hash(dict(schema='BOSS_FORECAST_CONTRACT_V1',
                    kind='NativeForecastArtifact', fields=fields))
                if marker != dict(schema='BOSS_NATIVE_PUBLICATION_VALIDATION_V1',
                        runtime=self.snapshot.runtime, reproduced_artifact_hash=reproduced_hash):
                    raise ValueError('publisher reproduction attestation differs from artifact')
        if type(self.representation) is not tuple or len(self.representation) != self.snapshot.d_model:
            raise ValueError('immutable native representation required')
        for value in self.representation:
            finite_number(value, 'native representation')
        if (type(self.points) is not tuple or len(self.points) < 2
                or any(not isinstance(p, ForecastPoint) for p in self.points)):
            raise ValueError('complete immutable path required')
        if (self.points[0].time_ns != self.session.open_ns or self.points[0].quantiles != (0., 0., 0.)
                or self.points[-1].time_ns != self.session.close_ns
                or any(a.time_ns >= b.time_ns for a, b in zip(self.points, self.points[1:]))):
            raise ValueError('path must cover the session in strict time order from zero')
        ForecastPoint(self.session.open_ns, self.gap_quantiles, self.gap_observed)
        finite_number(self.net_usd, 'net')
        if self.net_usd != self.gap_quantiles[1] + self.points[-1].p50:
            raise ValueError('net must equal gap plus terminal, without a separate median claim')
        observed = self.session.event_cutoff_ns >= self.session.open_ns
        if self.gap_observed != observed or (observed and self.gap_quantiles != (self.session.observed_gap,)*3):
            raise ValueError('gap differs from causal observed status/value')
        expected = [(self.session.open_ns, (0., 0., 0.), observed)]
        expected.extend((m.event_ns, (self.session.movement(m),)*3, True) for m in self.session.known_marks)
        if [(p.time_ns, p.quantiles, p.observed) for p in self.points[:len(expected)]] != expected:
            raise ValueError('path differs from certified observed prefix')
        future = self.points[len(expected):]
        if (not future or len(future)-1 > self.session.knot_policy.max_interior
                or any(p.observed or p.time_ns <= max(self.session.open_ns, self.session.event_cutoff_ns)
                       or (p.time_ns-self.session.open_ns) % self.session.knot_policy.quantum_ns for p in future)):
            raise ValueError('forecast points must follow the cutoff on the declared quantum and budget')

    @torch.no_grad()
    def verify_reproduction(self):
        """Explicit current-runtime reproduction; historical reads do not call this."""
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
        return self

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
    def publisher_reproduction_status(self):
        """Ledger-trusted producer claim, never a current-runtime verification."""
        binding = {} if self.context_receipt is None else unpack(json.loads(self.context_receipt))
        return 'publisher_verified' if 'publication_validation' in binding else 'unknown'

    @property
    def payload(self):
        return canonical_bytes(pack(dict(schema='BOSS_NATIVE_FORECAST_V1', **asdict(self))))

    @classmethod
    def from_payload(cls, payload, *, expected_digest, verify_reproduction=False):
        sha256_digest(expected_digest, 'trusted forecast digest')
        if type(payload) is not bytes:
            raise ValueError('immutable forecast bytes required')
        if type(verify_reproduction) is not bool:
            raise ValueError('explicit reproduction verification flag required')
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
        if verify_reproduction:
            artifact.verify_reproduction()
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
    artifact = NativeForecastArtifact(session, snapshot, tuple(native.tolist()), native_model_hash, input_hash,
                                     arm_hash, gap, observed, tuple(points), gap[1]+points[-1].p50, context_receipt)
    artifact.verify_reproduction()
    if context_receipt is not None:
        binding = unpack(json.loads(context_receipt))
        if 'publication_validation' in binding:
            raise ValueError('publication attestation must be made after reproduction')
        binding['publication_validation'] = dict(schema='BOSS_NATIVE_PUBLICATION_VALIDATION_V1',
            runtime=snapshot.runtime, reproduced_artifact_hash=artifact.digest)
        artifact = replace(artifact, context_receipt=canonical_bytes(pack(binding)))
    return artifact
