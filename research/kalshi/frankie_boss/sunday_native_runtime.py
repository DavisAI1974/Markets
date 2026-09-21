"""Explicit development initialization and full-context admission, without calls.

This selects a new untrained native candidate, not a fitted production model.
Market session anchors and feedback are supplied by their attested authorities;
this module never manufactures them from a runner's market calculations.
"""
from dataclasses import asdict
import copy
import hashlib
import random

import numpy as np
import torch

from .b1_reasoner import B1Config, B1Reasoner
from .c15_journal import evidence_hash
from .c15_normalizer import NormalizerConfig, SCALE_FLOORS
from .c15_normalizer_r3 import NormalizerR3
from .c15_teacher_r3 import JournalTeacherR3
from .context_session import ContextReceipt, ContextSessionRunner, journal_prefix
from .forecast_heads import NativeForecastHeads
from .granite_context import map_native_context
from .granite_context_route import context_route
from .granite_runpod_admission import CONTEXT as SERVICE_CONTEXT
from .granite_run_artifacts import canonical
from .native_forecast_learning import LearningConfig, optimizer_identity
from .native_forecast_refresh import NativeForecastRefresh, session_registry_hash
from .native_mbo_encoder import NativeRegistry, NativeTrunk
from .mbo_source import SOURCE_EXTRA_FIELDS


DEVELOPMENT = dict(schema='BOSS_SUNDAY_DEVELOPMENT_V1', seed=20260915,
    native=dict(d_model=256, n_heads=4, n_layers=4, window=128,
                d_ff_mult=4, use_delta_memory=True, use_qsv=False),
    recurrence=dict(k_max=8, k_fixed=8, halt_policy='FIXED', conv_tau=1e-3,
                    inject_input=True, step_embedding=True),
    decoder=dict(d_model=256, hidden=128), context_rows=4096,
    dtype='float64', device='cpu', teacher='C15R3_UPDATING',
    qsv='explicitly unavailable: lawful source-to-QSV mapping not yet supplied',
    optimizer=dict(lr=0.0001, betas=(0.9, 0.999), eps=1e-8,
                   weight_decay=0.01, amsgrad=False, maximize=False,
                   foreach=False, capturable=False, differentiable=False, fused=False),
    stage='timing', presence_weight=1.0, delay_weight=1.0,
    gap_weight=0.0, path_weight=0.0,
    empirical_claim='none; one supplied source is development training only')


def initialize(builder):
    """Fresh initialization only; restore checkpoints before continuing a run.

    R3 consumes every prefix record. Its online normalizer starts empty and uses
    only earlier observations; cold-start/missing target masks remain explicit.
    NG raw tick 1e6 is $0.001 at DBN 1e9 scale, matching build_anchor_block.py.
    """
    random.seed(DEVELOPMENT['seed'])
    np.random.seed(DEVELOPMENT['seed'])
    torch.manual_seed(DEVELOPMENT['seed'])
    native = B1Reasoner(NativeTrunk(NativeRegistry(extra_fields=SOURCE_EXTRA_FIELDS), **DEVELOPMENT['native']),
                        B1Config(**DEVELOPMENT['recurrence'])).double().eval()
    decoder = NativeForecastHeads(**DEVELOPMENT['decoder']).double().eval()
    teacher = JournalTeacherR3({111313: 1000000}, normalizer=NormalizerR3(
        NormalizerConfig(instrument_ids=(111313,), mode='UPDATING',
                         n_norm=4096, n_warm=256, floors=SCALE_FLOORS, clip=8.0)))
    context = ContextSessionRunner(native, builder, entity=(1, 111313),
                                   t_ctx=4096, teacher=teacher)
    optimizer = torch.optim.AdamW(list(native.parameters())+list(decoder.parameters()),
                                  **DEVELOPMENT['optimizer'])
    identity = dict(config=copy.deepcopy(DEVELOPMENT), native_hash=context._model_hash(),
                    teacher_binding=teacher.binding, teacher_normalizer=teacher.normalizer.export(),
                    optimizer_hash=optimizer_identity(optimizer))
    return context, decoder, optimizer, identity


def learning_config(optimizer, sessions, *, timing_policy_hash, query_policy_hash, split_hash):
    """Timing precision/labels must have an attested policy, never hidden defaults."""
    return LearningConfig(stage='timing', presence_weight=1.0, delay_weight=1.0,
        gap_weight=0.0, path_weight=0.0,
        session_weights=tuple((session.session_id, 1.0) for _, session in sessions),
        timing_policy_hash=timing_policy_hash, query_policy_hash=query_policy_hash,
        split_hash=split_hash, optimizer_hash=optimizer_identity(optimizer))


def assemble_request(context, decoder, book, *, sessions, expected_sessions_hash,
                     refresh_policy, metadata, request_id, as_of, source_as_of,
                     through_cursor, source_hash, development_identity,
                     optimizer, checkpoint, expected_checkpoint_hash):
    """Bind the actual attested roster to native forecast/controller arguments.

    All retained evidence remains in the builder. A selected interior prefix is
    causal training input; later source rows belong only to principal feedback.
    """
    if not sessions or session_registry_hash(sessions) != expected_sessions_hash:
        raise ValueError('full attested session roster required')
    for target, session in sessions:
        session.validate_for_publication()
        if (target.instrument != session.instrument or target.target_ns != session.close_ns
                or session.close_ns <= as_of
                or (session.event_cutoff_ns, session.receive_cutoff_ns, session.source_hash)
                   != (source_as_of, as_of, source_hash)):
            raise ValueError('unfinished sessions and exact causal source required')
    if development_identity['config'] != DEVELOPMENT:
        raise ValueError('development initialization configuration changed')
    current = current_training_identity(context, decoder, optimizer, checkpoint,
                                         expected_checkpoint_hash=expected_checkpoint_hash)
    if current['optimizer_hash'] != development_identity['optimizer_hash']:
        raise ValueError('optimizer configuration changed since initialization')
    bridge = NativeForecastRefresh(context, decoder, book,
        tuple(target for target, _ in sessions), refresh_policy)
    request = dict(request_id=request_id, sessions=sessions,
        expected_sessions_hash=expected_sessions_hash,
        arm_hash=evidence_hash(dict(initialization=development_identity, current=current)), as_of=as_of,
        source_as_of=source_as_of, source_hash=source_hash,
        through_cursor=through_cursor, metadata=metadata)
    return bridge, request


def current_training_identity(context, decoder, optimizer, checkpoint, *, expected_checkpoint_hash):
    """Bind current weights/optimizer to the independently pinned committed state."""
    from .boss_training_checkpoint import BossTrainingCheckpoint, _decode, encode_state
    if (type(checkpoint) is not BossTrainingCheckpoint
            or checkpoint.checkpoint_hash != expected_checkpoint_hash
            or checkpoint.models['native'] is not context.model
            or checkpoint.models['decoder'] is not decoder
            or checkpoint.optimizer is not optimizer or checkpoint._failed):
        raise ValueError('current trusted native training checkpoint required')
    raw, digest = checkpoint.db.execute(
        'SELECT payload,digest FROM checkpoints ORDER BY sequence DESC LIMIT 1').fetchone()
    if digest != expected_checkpoint_hash or hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError('checkpoint journal differs from current trusted pin')
    state = _decode(raw)
    if any(encode_state(model.state_dict()) != encode_state(state['models'][role]['weights'])
           for role, model in checkpoint.models.items()):
        raise ValueError('live model differs from committed training state')
    if encode_state(optimizer.state_dict()) != encode_state(state['optimizer']):
        raise ValueError('live optimizer differs from committed training state')
    return dict(checkpoint_hash=digest, training_cursor=checkpoint.training_cursor,
        native_hash=context._model_hash(), optimizer_hash=optimizer_identity(optimizer))


def prepare_critic_request(context, *, as_of, through_cursor, source_as_of,
                           served_model_name='granite42-smoke', output_tokens=None,
                           context_encoding='compact_v1', context_encoding_options=None,
                           service_context=SERVICE_CONTEXT):
    """No forward, remote call or publication. Preserve every prepared context row.

    Return exact compact service bytes for LocalTokenizerAdmission; capacity
    failure must be resolved before any paid Pod resume. No truncation/fallback.
    THE OUTPUT HAS NO CAP (Greg Davis, 2026-09-21): output_tokens defaults to the whole
    service context as a placeholder that LocalTokenizerAdmission.with_remaining_output
    replaces with the exact remaining context; a body dispatched without that admission
    is refused by the service (input plus output over the context), never truncated.
    """
    if output_tokens is None:
        output_tokens = service_context
    if (type(service_context) is not int or service_context != SERVICE_CONTEXT
            or type(output_tokens) is not int
            or not 1 <= output_tokens <= service_context):
        raise ValueError('explicit service-compatible output token budget required')
    tokens, info, input_hash, teacher, rows = context._prepare(as_of, through_cursor)
    if any(row['normalized']['ts_event_ns'] > source_as_of
           for row in journal_prefix(context.builder, through_cursor)):
        raise ValueError('context event beyond causal cutoff')
    receipt = ContextReceipt(**info, input_hash=input_hash, model_hash=context._model_hash())
    packet = info if context.qsv is None else dict(context=info, input_hash=input_hash)
    qsv_binding = None
    if context.qsv is not None:
        _, _, qsv_binding = context.qsv.attach(rows, expected_hash=context.expected_qsv_hash,
                                              device=tokens['qsv'].device)
    mapped = map_native_context(tokens=tokens, receipt=receipt, entity=context.entity,
        registry=context.model.trunk.registry, expected_input_hash=input_hash,
        expected_packet_hash=evidence_hash(packet), source_as_of=source_as_of,
        expected_qsv_binding=qsv_binding)
    route = context_route(context_encoding)
    snapshot = route.encode(mapped, **(context_encoding_options or {}))
    prompt = route.build_prompt(snapshot)
    body = canonical(dict(model=served_model_name, messages=[dict(role='user', content=prompt.text)],
        temperature=0, max_tokens=output_tokens, stream=False,
        chat_template_kwargs=dict(enable_thinking=False)))
    return body, dict(schema='BOSS_ACTUAL_CRITIC_INPUT_V1', context=asdict(receipt),
        request_sha256=hashlib.sha256(body).hexdigest(), request_bytes=len(body),
        prompt_sha256=hashlib.sha256(prompt.text.encode()).hexdigest(),
        native_snapshot_hash=mapped.hash,
        **({'compact_snapshot_hash':snapshot.hash} if context_encoding=='compact_v1' else
           {'encoded_snapshot_hash':snapshot.hash,'context_encoding':context_encoding,
            'context_encoding_options':context_encoding_options}),
        teacher_binding=context.teacher.binding if context.teacher is not None else None,
        model_forward_performed=False, inference_performed=False)
