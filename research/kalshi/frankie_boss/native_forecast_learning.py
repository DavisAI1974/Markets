"""Supervised native BOSS updates from separately attested Frankie feedback.

This callback never computes market labels. The caller verifies principal authorship,
query selection and the authorized chronological partition, then pins feedback bytes.
Granite is not optimized. Durable exactly-once updates/checkpoints belong to the
coordinator: on failure after mutation, restore its last checkpoint before retry.
"""
from dataclasses import dataclass, asdict
import time
import torch
from torch.nn import functional as F

try:
    from .forecast_contract import HashedContract, finite_number, sha256_digest
    from .c15_journal import evidence_hash
    from .context_session import tensor_identity, journal_prefix
    from .b1_reasoner import B1Reasoner
    from .native_forecast_refresh import session_registry_hash
except ImportError:
    from forecast_contract import HashedContract, finite_number, sha256_digest
    from c15_journal import evidence_hash
    from context_session import tensor_identity, journal_prefix
    from b1_reasoner import B1Reasoner
    from native_forecast_refresh import session_registry_hash


def optimizer_identity(optimizer):
    """Bind the effective optimizer, including every group's explicit settings."""
    return evidence_hash(dict(type=f'{type(optimizer).__module__}.{type(optimizer).__qualname__}',
        defaults=optimizer.defaults,
        groups=[{k:v for k,v in g.items() if k != 'params'} for g in optimizer.param_groups]))


@dataclass(frozen=True)
class LearningConfig(HashedContract):
    stage: str
    presence_weight: float
    delay_weight: float
    gap_weight: float
    path_weight: float
    session_weights: tuple[tuple[str, float], ...]
    timing_policy_hash: str
    query_policy_hash: str
    split_hash: str
    optimizer_hash: str

    def __post_init__(self):
        if self.stage not in ('timing', 'path_gap'):
            raise ValueError('explicit timing or path_gap stage required')
        weights = (self.presence_weight, self.delay_weight, self.gap_weight, self.path_weight)
        for value in weights:
            finite_number(value, 'loss weight')
            if value < 0:
                raise ValueError('nonnegative loss weights required')
        active = weights[:2] if self.stage == 'timing' else weights[2:]
        if sum(active) <= 0:
            raise ValueError('stage requires a positive loss weight')
        if type(self.session_weights) is not tuple or not self.session_weights:
            raise ValueError('explicit immutable session weights required')
        names = []
        for pair in self.session_weights:
            if type(pair) is not tuple or len(pair) != 2 or type(pair[0]) is not str or not pair[0]:
                raise ValueError('named session weights required')
            finite_number(pair[1], 'session weight')
            if pair[1] <= 0:
                raise ValueError('positive session weights required')
            names.append(pair[0])
        if len(set(names)) != len(names):
            raise ValueError('unique session weights required')
        for name in ('timing_policy_hash', 'query_policy_hash', 'split_hash', 'optimizer_hash'):
            sha256_digest(getattr(self, name), name)


@dataclass(frozen=True)
class TimingLabel:
    previous_ns: int
    previous_delay_ns: int
    next_ns: int | None
    observed_through_ns: int
    available_ns: int
    evidence_hash: str


@dataclass(frozen=True)
class ValueLabel:
    query_ns: int
    value_usd: float | None
    observed_through_ns: int
    available_ns: int
    evidence_hash: str


@dataclass(frozen=True)
class SessionFeedback:
    session_id: str
    timing: tuple[TimingLabel, ...]
    gap: ValueLabel | None
    path: tuple[ValueLabel, ...]


@dataclass(frozen=True)
class FrankieFeedback(HashedContract):
    request_id: str
    input_hash: str
    source_hash: str
    available_ns: int
    principal_receipt_hash: str
    sessions: tuple[SessionFeedback, ...]


class NativeForecastLearner:
    def __init__(self, context, decoder, optimizer, config, event=None):
        if not isinstance(context.model, B1Reasoner) or not isinstance(config, LearningConfig):
            raise ValueError('native B1 context and explicit learning configuration required')
        if event is not None and not callable(event):
            raise ValueError('native learning diagnostic event must be callable')
        self.context, self.decoder, self.optimizer, self.config = context, decoder, optimizer, config
        self.event = event
        owned = list(context.model.parameters()) + list(decoder.parameters())
        supplied = [p for group in optimizer.param_groups for p in group['params']]
        if len(set(map(id, supplied))) != len(supplied) or set(map(id, supplied)) != set(map(id, owned)):
            raise ValueError('optimizer must own exactly the native B1 and decoder parameters')
        if optimizer_identity(optimizer) != config.optimizer_hash:
            raise ValueError('optimizer configuration differs from its pin')

    def _emit(self, started, request_id, stage, **values):
        """Best-effort safe telemetry; observer failure cannot alter training."""
        if self.event is None:
            return
        payload = dict(request_id=request_id, stage=stage,
            elapsed_seconds=max(0.0, time.perf_counter()-started), **values)
        try:
            self.event(payload)
        except Exception:
            pass

    def _validate(self, sessions, feedback, as_of, learning_cutoff_ns):
        if type(learning_cutoff_ns) is not int or learning_cutoff_ns < as_of:
            raise ValueError('causal learning cutoff required')
        if type(feedback.available_ns) is not int or not as_of <= feedback.available_ns <= learning_cutoff_ns:
            raise ValueError('feedback is not available at this learning cutoff')
        sha256_digest(feedback.principal_receipt_hash, 'principal receipt')
        if type(feedback.sessions) is not tuple or tuple(f.session_id for f in feedback.sessions) != tuple(s.session_id for _,s in sessions):
            raise ValueError('feedback must preserve the entire session roster and order')
        if tuple(n for n,_ in self.config.session_weights) != tuple(s.session_id for _,s in sessions):
            raise ValueError('session weights differ from the complete roster')
        for (_, session), labels in zip(sessions, feedback.sessions):
            session.validate_for_publication()
            if type(labels) is not SessionFeedback or type(labels.timing) is not tuple or type(labels.path) is not tuple:
                raise ValueError('immutable typed feedback labels required')
            previous = max(0, session.event_cutoff_ns-session.open_ns)
            previous_delay = 0
            for i, label in enumerate(labels.timing):
                if type(label) is not TimingLabel or any(type(v) is not int for v in
                        (label.previous_ns, label.previous_delay_ns)):
                    raise ValueError('integer timing labels required')
                if (label.previous_ns, label.previous_delay_ns) != (previous, previous_delay):
                    raise ValueError('timing labels must use chronological teacher forcing')
                if label.next_ns is None:
                    if i != len(labels.timing)-1:
                        raise ValueError('STOP must end the timing label sequence')
                    needed = session.close_ns
                else:
                    if type(label.next_ns) is not int or not previous < label.next_ns < session.duration_ns:
                        raise ValueError('timing label must be a strictly future interior event')
                    needed = session.open_ns+label.next_ns
                    previous_delay, previous = label.next_ns-previous, label.next_ns
                self._available(label, needed, feedback.available_ns)
            if labels.gap is not None:
                if (type(labels.gap) is not ValueLabel or type(labels.gap.query_ns) is not int
                        or labels.gap.query_ns != 0):
                    raise ValueError('gap label must identify the opening')
                if session.event_cutoff_ns >= session.open_ns:
                    raise ValueError('known postopen gap is an observation, not a forecast label')
                self._value(labels.gap, session.open_ns, feedback.available_ns)
            queries = []
            for label in labels.path:
                if type(label) is not ValueLabel or type(label.query_ns) is not int or not (
                    max(0, session.event_cutoff_ns-session.open_ns) < label.query_ns <= session.duration_ns):
                    raise ValueError('path labels require future session query coordinates')
                self._value(label, session.open_ns+label.query_ns, feedback.available_ns)
                queries.append(label.query_ns)
            if queries != sorted(set(queries)):
                raise ValueError('path query labels must be unique and ordered')

    @staticmethod
    def _available(label, needed, available):
        sha256_digest(label.evidence_hash, 'label observation evidence')
        if (type(label.observed_through_ns) is not int or type(label.available_ns) is not int
                or not needed <= label.observed_through_ns <= label.available_ns <= available):
            raise ValueError('label observation is not available at its declared cutoff')

    @classmethod
    def _value(cls, label, needed, available):
        cls._available(label, needed, available)
        if label.value_usd is not None:
            finite_number(label.value_usd, 'observed USD label')

    def step(self, *, request_id, as_of, through_cursor, source_hash, input_hash,
             sessions, expected_sessions_hash, feedback, expected_feedback_hash, learning_cutoff_ns):
        """One optimizer step. Caller journals intent and persists/reloads all state."""
        started = time.perf_counter()
        if type(as_of) is not int or type(through_cursor) is not int:
            raise ValueError('integer source cutoff required')
        if type(feedback) is not FrankieFeedback or feedback.digest != expected_feedback_hash:
            raise ValueError('feedback differs from its independently trusted attestation')
        if (feedback.request_id, feedback.input_hash, feedback.source_hash) != (request_id, input_hash, source_hash):
            raise ValueError('feedback request/input/source binding mismatch')
        if session_registry_hash(sessions) != expected_sessions_hash:
            raise ValueError('session roster differs from its trusted manifest')
        self._validate(sessions, feedback, as_of, learning_cutoff_ns)
        if optimizer_identity(self.optimizer) != self.config.optimizer_hash:
            raise ValueError('optimizer configuration changed')
        journal = self.context.builder.journal
        journal_state = (journal.count, journal.head_hash)
        self._emit(started, request_id, 'prepare_start')
        try:
            tokens, info, prepared_hash, teacher, context = self.context._prepare(as_of, through_cursor)
        except Exception as error:
            self._emit(started, request_id, 'step_failed', error_type=type(error).__name__)
            raise
        self._emit(started, request_id, 'prepare_complete', context_rows=len(context))
        if prepared_hash != input_hash or info['source_prefix_hash'] != source_hash:
            raise ValueError('training source/input differs from completed forecast')
        for _, session in sessions:
            if session.receive_cutoff_ns != as_of or session.source_hash != source_hash:
                raise ValueError('session differs from causal source input')
        try:
            for entry in journal_prefix(self.context.builder, through_cursor):
                if any(entry['normalized']['ts_event_ns'] > s.event_cutoff_ns for _,s in sessions):
                    raise ValueError('training source includes future event time')
        except Exception as error:
            self._emit(started, request_id, 'step_failed', error_type=type(error).__name__)
            raise
        self._emit(started, request_id, 'causal_scan_complete', context_rows=len(context))
        parameters = list(self.context.model.parameters()) + list(self.decoder.parameters())
        before = evidence_hash(dict(native=tensor_identity(self.context.model.state_dict()),
                                    decoder=tensor_identity(self.decoder.state_dict())))
        # Eval mode keeps audited causal preparation valid; it does not disable autograd.
        # Path fitting freezes every dependency of timing, not just the final MLP.
        enabled = list(self.context.model.parameters()) if self.config.stage == 'timing' else []
        modules = ((self.decoder.time_decoder, self.decoder.session_projection)
            if self.config.stage == 'timing' else (self.decoder.gap_median, self.decoder.path_median))
        enabled += [p for module in modules for p in module.parameters()]
        enabled_ids = set(map(id, enabled))
        flags = [p.requires_grad for p in parameters]
        for p in parameters:
            p.requires_grad_(id(p) in enabled_ids)
            p.grad = None
        try:
            kwargs = dict(tokens={k:v.detach().clone() for k,v in tokens.items()})
            kwargs['numeric'] = kwargs['tokens']['numeric']
            for name in ('qsv', 'qsv_mask'):
                if name in kwargs['tokens']:
                    kwargs[name] = kwargs['tokens'].pop(name)
            packet = info if self.context.qsv is None else dict(context=info, input_hash=input_hash)
            self._emit(started, request_id, 'forward_start', context_rows=len(context))
            output = self.context.model.forward_decision(**kwargs, packet_hash=evidence_hash(packet))
            if output.representation.shape != (1, len(context), self.decoder.d_model):
                raise ValueError('training did not consume every declared context record')
            self._emit(started, request_id, 'forward_complete', context_rows=len(context))
            losses, components, masked = [], [], 0
            for (_,session), labels, (_,weight) in zip(sessions, feedback.sessions, self.config.session_weights):
                z = self.decoder.condition(output.representation[0,-1], session.features)
                terms = {}
                if self.config.stage == 'timing':
                    presence, delay = [], []
                    for label in labels.timing:
                        pred = self.decoder.next_time(z, label.previous_ns/session.duration_ns,
                                                      label.previous_delay_ns/session.duration_ns)
                        presence.append(F.binary_cross_entropy_with_logits(pred[1],
                            pred.new_tensor(float(label.next_ns is None))))
                        if label.next_ns is not None:
                            target = (label.next_ns-label.previous_ns)/(session.duration_ns-label.previous_ns)
                            delay.append(.5*torch.abs(pred[0]-target))
                    if presence: terms['presence'] = torch.stack(presence).mean()
                    if delay: terms['delay'] = torch.stack(delay).mean()
                else:
                    if labels.gap is not None:
                        if labels.gap.value_usd is None: masked += 1
                        else: terms['gap'] = .5*torch.abs(self.decoder.gap(z)[1]-labels.gap.value_usd)
                    path = []
                    anchor = (session.anchor_ns-session.open_ns)/session.duration_ns
                    anchor_usd = session.movement(session.known_marks[-1]) if session.known_marks else 0.
                    for label in labels.path:
                        if label.value_usd is None: masked += 1; continue
                        prediction = self.decoder.path(z, label.query_ns/session.duration_ns,
                                                       anchor=anchor, anchor_usd=anchor_usd)[1]
                        path.append(.5*torch.abs(prediction-label.value_usd))
                    if path: terms['path'] = torch.stack(path).mean()
                weighted = [value*getattr(self.config, name+'_weight') for name,value in terms.items()
                            if getattr(self.config, name+'_weight') > 0]
                if weighted: losses.append(sum(weighted)*weight)
                components.append(dict(session_id=session.session_id,
                    terms={name:float(value.detach()) for name,value in terms.items()}))
            self._emit(started, request_id, 'loss_complete', losses=len(losses), masked_labels=masked)
            journal.verify(count=journal_state[0], head_hash=journal_state[1])
            if losses:
                loss = sum(losses)/sum(weight for _,weight in self.config.session_weights)
                if not torch.isfinite(loss): raise ValueError('nonfinite native learning loss')
                self._emit(started, request_id, 'backward_start', losses=len(losses), masked_labels=masked)
                loss.backward()
                self._emit(started, request_id, 'backward_complete', losses=len(losses), masked_labels=masked)
                if any(p.grad is not None and not torch.isfinite(p.grad).all() for p in parameters):
                    raise ValueError('nonfinite native learning gradient')
                self._emit(started, request_id, 'optimizer_start', losses=len(losses), masked_labels=masked)
                self.optimizer.step()
                self._emit(started, request_id, 'optimizer_complete', losses=len(losses), masked_labels=masked)
                if any(not torch.isfinite(p).all() for p in parameters):
                    raise ValueError('nonfinite updated native parameter; restore prior checkpoint')
            after = evidence_hash(dict(native=tensor_identity(self.context.model.state_dict()),
                                       decoder=tensor_identity(self.decoder.state_dict())))
            self._emit(started, request_id, 'step_complete', context_rows=len(context),
                losses=len(losses), masked_labels=masked)
            return dict(schema='BOSS_NATIVE_FORECAST_LEARNING_V1', request_id=request_id,
                config_hash=self.config.digest, feedback_hash=feedback.digest,
                input_hash=input_hash, source_hash=source_hash, stage=self.config.stage,
                learning_cutoff_ns=learning_cutoff_ns, consumed_rows=info['consumed_rows'],
                outside_context_rows=info['outside_context_rows'], teacher_hash=info['teacher_hash'],
                recurrence_hash=evidence_hash(asdict(output.receipt)),
                teacher_optimized=False, masked_labels=masked, losses=components,
                updated=bool(losses), loss=float(loss.detach()) if losses else None,
                before_hash=before, after_hash=after)
        except Exception as error:
            self._emit(started, request_id, 'step_failed', error_type=type(error).__name__)
            raise
        finally:
            for parameter, flag in zip(parameters, flags):
                parameter.requires_grad_(flag)
                parameter.grad = None
