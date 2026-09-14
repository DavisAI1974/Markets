"""Opt-in CPU native B1 producer for the existing retry-safe rolling ledger.

Each target is one explicitly declared session close, including future sessions.
There is no cumulative multi-session net and no protected Frankie projection.
Single writer, synthetic software acceptance only; calibration/ranking is absent.
"""
from dataclasses import asdict
from pathlib import Path
import json
import torch

try:
    from .b1_reasoner import B1Reasoner
    from .context_session import ContextReceipt, journal_prefix
    from .c15_journal import evidence_hash, pack, unpack, canonical_bytes
    from .forecast_contract import sha256_digest
    from .forecast_artifact import DecoderSnapshot, freeze_forecast
    from .forecast_session import ForecastSession
    from .forecast_refresh import ForecastRefreshLoop
    from .rolling_forecast import ForecastCandidate, ForecastTarget
except ImportError:
    from b1_reasoner import B1Reasoner
    from context_session import ContextReceipt, journal_prefix
    from c15_journal import evidence_hash, pack, unpack, canonical_bytes
    from forecast_contract import sha256_digest
    from forecast_artifact import DecoderSnapshot, freeze_forecast
    from forecast_session import ForecastSession
    from forecast_refresh import ForecastRefreshLoop
    from rolling_forecast import ForecastCandidate, ForecastTarget


def session_registry_hash(sessions):
    if type(sessions) is not tuple:
        raise ValueError('complete immutable target/session registry required')
    if any(type(pair) is not tuple or len(pair) != 2 or
           not isinstance(pair[0], ForecastTarget) or not isinstance(pair[1], ForecastSession)
           for pair in sessions):
        raise ValueError('typed target/session pairs required')
    return evidence_hash(tuple((asdict(t), asdict(s)) for t, s in sessions))


def native_execution_hash(model):
    """Bind effective module graph/settings outside protected context identity.

    Tensor contents and declared registries/configs are bound by _model_hash;
    this adds actual module settings such as LayerNorm epsilon and attention scale.
    """
    modules = {}
    for name, module in model.named_modules():
        if module._forward_hooks or module._forward_pre_hooks:
            raise ValueError('unversioned native forward hooks are unsupported')
        settings = {}
        for key, value in vars(module).items():
            if key in ('_parameters', '_buffers', '_modules') or callable(value):
                continue
            try:
                pack(value)
            except ValueError:
                continue  # Structured config/registry identities belong to _model_hash.
            settings[key] = value
        modules[name] = dict(type=f'{type(module).__module__}.{type(module).__qualname__}', settings=settings)
    return evidence_hash(modules)


class NativeForecastRefresh:
    def __init__(self, context, decoder, book, targets, policy):
        if not isinstance(context.model, B1Reasoner):
            raise ValueError('native forecasts require the same-forward B1 representation')
        self.context, self.decoder, self.book = context, decoder, book
        self.targets, self.policy = targets, policy

    @staticmethod
    def artifact_digest(published):
        """Extract the artifact identity only after the ledger has verified its bytes."""
        fields = unpack(json.loads(published.selected.forecast_artifact))
        if fields.pop('schema') != 'BOSS_NATIVE_FORECAST_V1':
            raise ValueError('unexpected forecast artifact schema')
        return evidence_hash(dict(schema='BOSS_FORECAST_CONTRACT_V1', kind='NativeForecastArtifact', fields=fields))

    def update(self, *, sessions, expected_sessions_hash, arm_hash, as_of, source_as_of, source_hash,
               material=False, through_cursor=None):
        sha256_digest(expected_sessions_hash, 'trusted session registry')
        sha256_digest(arm_hash, 'arm')
        sha256_digest(source_hash, 'source')
        if type(as_of) is not int or type(source_as_of) is not int or source_as_of > as_of:
            raise ValueError('causal integer cutoffs required')
        if session_registry_hash(sessions) != expected_sessions_hash:
            raise ValueError('session registry differs from trusted manifest')
        active = tuple(t for t in self.targets if t.target_ns > as_of)
        if tuple(t for t, _ in sessions) != active:
            raise ValueError('provide every active target in the frozen registry order')
        for target, session in sessions:
            if target.instrument != session.instrument or target.target_ns != session.close_ns:
                raise ValueError('native target must be the declared single-session close')
            if (session.event_cutoff_ns, session.receive_cutoff_ns, session.source_hash) != (
                    source_as_of, as_of, source_hash):
                raise ValueError('all sessions must share the same causal source state')
        if any(p.device.type != 'cpu' for p in self.context.model.parameters()):
            raise ValueError('native forecast candidate currently requires CPU arithmetic')
        cursor = self.context.builder.chain.next_cursor-1 if through_cursor is None else through_cursor
        tokens, info, input_hash, teacher, context = self.context._prepare(as_of, cursor)
        if info['source_prefix_hash'] != source_hash:
            raise ValueError('session source differs from the native journal prefix')
        for entry in journal_prefix(self.context.builder, cursor):
            if entry['normalized']['ts_event_ns'] > source_as_of:
                raise ValueError('native source contains event times beyond the declared cutoff')
        native_hash = self.context._model_hash()
        execution_hash = native_execution_hash(self.context.model)
        snapshot = DecoderSnapshot.capture(self.decoder)
        model_hash = evidence_hash(dict(native=native_hash, execution=execution_hash, decoder=snapshot.digest))
        journal = self.context.builder.journal
        journal_state = (journal.count, journal.head_hash)
        generation_hash = evidence_hash(dict(model=model_hash, sessions=expected_sessions_hash,
            input_hash=input_hash, journal_state=journal_state, code=Path(__file__).read_bytes()))
        by_target = dict(sessions)

        def unchanged():
            if (self.context._model_hash() != native_hash or DecoderSnapshot.capture(self.decoder) != snapshot
                    or native_execution_hash(self.context.model) != execution_hash
                    or (journal.count, journal.head_hash) != journal_state):
                raise ValueError('native generation model or source changed during attempt')

        def produce(*, target, **request):
            unchanged()
            kwargs = dict(tokens={k: v.detach().clone() for k, v in tokens.items()})
            kwargs['numeric'] = kwargs['tokens']['numeric']
            for name in ('qsv', 'qsv_mask'):
                if name in kwargs['tokens']:
                    kwargs[name] = kwargs['tokens'].pop(name)
            packet = info if self.context.qsv is None else dict(context=info, input_hash=input_hash)
            with torch.no_grad():
                output = self.context.model.forward_decision(**kwargs, packet_hash=evidence_hash(packet))
            if (output['evidence_scores'].shape != (1, len(context))
                    or any(not torch.isfinite(v).all() for v in output.values())
                    or output.representation.shape != (1, len(context), self.decoder.d_model)):
                raise ValueError('invalid same-forward native output')
            receipt = ContextReceipt(**info, input_hash=input_hash, model_hash=native_hash)
            binding = canonical_bytes(pack(dict(context=asdict(receipt), recurrence=asdict(output.receipt),
                                                native_execution_hash=execution_hash)))
            artifact = freeze_forecast(self.decoder, output.representation[0, -1], by_target[target],
                native_model_hash=native_hash, input_hash=input_hash, arm_hash=arm_hash, context_receipt=binding)
            unchanged()
            return (ForecastCandidate(artifact.digest, target, as_of, source_as_of,
                source_hash, arm_hash, model_hash, artifact.payload, None, None, None),)

        # Existing loop writes a full durable intent before produce can forward.
        loop = ForecastRefreshLoop(self.book, self.targets, self.policy)
        return loop.update(as_of=as_of, source_as_of=source_as_of,
            source_hash=source_hash, arm_hash=arm_hash, generation_hash=generation_hash,
            produce=produce, material=material)
