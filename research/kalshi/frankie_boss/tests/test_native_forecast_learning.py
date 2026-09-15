"""New supervised feedback mechanics with synthetic evidence, not a market run."""
from dataclasses import replace
import pytest
import torch
from native_forecast_learning import (LearningConfig, FrankieFeedback, SessionFeedback,
    TimingLabel, ValueLabel, NativeForecastLearner, optimizer_identity)
from native_forecast_refresh import session_registry_hash
from test_native_forecast_refresh import build_refresh, H


def case(tmp_path, stage='timing', missing=False):
    bridge, sessions = build_refresh(tmp_path)
    # The serving fixture deliberately zeros these weights to force immediate STOP.
    # This training fixture needs a real derivative back to the B1 representation.
    with torch.no_grad():
        bridge.decoder.time_decoder[-1].weight.fill_(.1)
    sessions = sessions[:1]
    optimizer = torch.optim.AdamW(list(bridge.context.model.parameters()) +
        list(bridge.decoder.parameters()), lr=.001, weight_decay=0.)
    config = LearningConfig(stage, 1., 1., 1., 1., ((sessions[0][1].session_id, 1.),),
        H, H, H, optimizer_identity(optimizer))
    _, _, input_hash, _, _ = bridge.context._prepare(2, 0)
    labels = SessionFeedback(sessions[0][1].session_id,
        (TimingLabel(0, 0, 400, 1400, 1400, H),
         TimingLabel(400, 400, None, 2000, 2000, H)),
        ValueLabel(0, None if missing else 1., 1000, 1000, H),
        (ValueLabel(800, None if missing else 2., 1800, 1800, H),))
    feedback = FrankieFeedback('request-1', input_hash, sessions[0][1].source_hash,
        2000, H, (labels,))
    learner = NativeForecastLearner(bridge.context, bridge.decoder, optimizer, config)
    args = dict(request_id='request-1', as_of=2, through_cursor=0,
        source_hash=sessions[0][1].source_hash, input_hash=input_hash,
        sessions=sessions, expected_sessions_hash=session_registry_hash(sessions),
        feedback=feedback, expected_feedback_hash=feedback.digest, learning_cutoff_ns=2000)
    return bridge, learner, args


def test_timing_feedback_updates_native_b1_and_timing_only(tmp_path):
    bridge, learner, args = case(tmp_path)
    before = {k:v.clone() for k,v in bridge.context.model.state_dict().items()}
    decoder_before = {k:v.clone() for k,v in bridge.decoder.state_dict().items()}
    receipt = learner.step(**args)
    assert receipt['updated'] and receipt['input_hash'] == args['input_hash']
    assert any(not torch.equal(v, before[k]) for k,v in bridge.context.model.state_dict().items())
    assert any(not torch.equal(v, decoder_before['time_decoder.'+k])
        for k,v in bridge.decoder.time_decoder.state_dict().items())
    assert all(torch.equal(v, decoder_before[k]) for k,v in bridge.decoder.state_dict().items()
        if k.startswith(('gap_', 'path_')))
    assert not bridge.context.model.training


def test_future_feedback_is_rejected_before_gradients(tmp_path):
    bridge, learner, args = case(tmp_path)
    args['learning_cutoff_ns'] = 1999
    before = {k:v.clone() for k,v in bridge.context.model.state_dict().items()}
    with pytest.raises(ValueError, match='available'):
        learner.step(**args)
    assert all(p.grad is None for p in bridge.context.model.parameters())
    assert all(torch.equal(v,before[k]) for k,v in bridge.context.model.state_dict().items())
    assert not learner.optimizer.state


def test_path_stage_keeps_timing_policy_and_b1_frozen(tmp_path):
    bridge, learner, args = case(tmp_path, 'path_gap')
    native = {k:v.clone() for k,v in bridge.context.model.state_dict().items()}
    before = {k:v.clone() for k,v in bridge.decoder.state_dict().items()}
    receipt = learner.step(**args)
    assert receipt['updated']
    assert all(torch.equal(v,native[k]) for k,v in bridge.context.model.state_dict().items())
    assert all(torch.equal(v,before[k]) for k,v in bridge.decoder.state_dict().items()
        if k.startswith(('time_decoder', 'session_projection', 'gap_tails', 'path_tails')))
    assert any(not torch.equal(v,before[k]) for k,v in bridge.decoder.state_dict().items()
        if k.startswith(('gap_median', 'path_median')))


def test_missing_value_labels_skip_update_and_preserve_mask(tmp_path):
    bridge, learner, args = case(tmp_path, 'path_gap', missing=True)
    before = {k:v.clone() for k,v in bridge.decoder.state_dict().items()}
    receipt = learner.step(**args)
    assert not receipt['updated'] and receipt['masked_labels'] == 2
    assert all(torch.equal(v,before[k]) for k,v in bridge.decoder.state_dict().items())
    assert not learner.optimizer.state


def test_changed_input_or_feedback_binding_is_rejected(tmp_path):
    _, learner, args = case(tmp_path)
    args['expected_feedback_hash'] = 'b'*64
    with pytest.raises(ValueError, match='feedback'):
        learner.step(**args)


def test_all_declared_native_context_rows_reach_training(tmp_path):
    from test_c15_full_evidence import submit, row
    bridge, learner, args = case(tmp_path)
    for i in (1, 2):
        submit(bridge.context.builder, row(i, oid=i+1))
    sessions = tuple((t,replace(s, event_cutoff_ns=201, receive_cutoff_ns=202,
        source_hash=bridge.context.builder.chain.prefix_hash)) for t,s in args['sessions'])
    tokens, _, input_hash, _, _ = bridge.context._prepare(202, 2)
    feedback = replace(args['feedback'], input_hash=input_hash, source_hash=sessions[0][1].source_hash)
    args.update(as_of=202,through_cursor=2,sessions=sessions,input_hash=input_hash,
        source_hash=sessions[0][1].source_hash,expected_sessions_hash=session_registry_hash(sessions),
        feedback=feedback,expected_feedback_hash=feedback.digest)
    receipt = learner.step(**args)
    assert receipt['consumed_rows'] == tokens['numeric'].shape[1] == 3
    assert receipt['outside_context_rows'] == 0


def test_masked_path_label_is_not_a_zero_target(tmp_path):
    bridge, learner, args = case(tmp_path, 'path_gap')
    labels = args['feedback'].sessions[0]
    masked = ValueLabel(900,None,1900,1900,H)
    feedback = replace(args['feedback'],sessions=(replace(labels,path=(*labels.path,masked)),))
    args.update(feedback=feedback,expected_feedback_hash=feedback.digest)
    receipt = learner.step(**args)
    assert receipt['masked_labels'] == 1
    assert receipt['updated'] and len(receipt['losses'][0]['terms']) == 2


def test_unclosed_stop_and_disordered_timing_fail_before_update(tmp_path):
    _, learner, args = case(tmp_path)
    labels = args['feedback'].sessions[0]
    invalid = replace(labels.timing[-1], observed_through_ns=1900)
    feedback = replace(args['feedback'], sessions=(replace(labels,timing=(labels.timing[0],invalid)),))
    args.update(feedback=feedback,expected_feedback_hash=feedback.digest)
    with pytest.raises(ValueError,match='available'):
        learner.step(**args)
    assert not learner.optimizer.state


def test_training_preserves_qsv_mask_and_serving_packet_binding(tmp_path, monkeypatch):
    from test_context_qsv import make_case, runner
    from b1_reasoner import B1Reasoner, B1Config
    from c15_journal import evidence_hash
    base = tmp_path/'base'; base.mkdir()
    qsv_dir = tmp_path/'qsv'; qsv_dir.mkdir()
    bridge, old_learner, args = case(base)
    builder, trunk, artifact = make_case(qsv_dir)
    boss = B1Reasoner(trunk, B1Config(k_max=1,k_fixed=1)).double().eval()
    context = runner(builder,boss,artifact)
    optimizer = torch.optim.AdamW(list(boss.parameters())+list(bridge.decoder.parameters()),
        lr=.001,weight_decay=0.)
    learner = NativeForecastLearner(context,bridge.decoder,optimizer,
        replace(old_learner.config,optimizer_hash=optimizer_identity(optimizer)))
    tokens, info, input_hash, _, _ = context._prepare(2,0)
    feedback = replace(args['feedback'],input_hash=input_hash)
    args.update(input_hash=input_hash,feedback=feedback,expected_feedback_hash=feedback.digest)
    original = boss.forward_decision
    observed = []
    def capture(**kwargs):
        assert kwargs['packet_hash'] == evidence_hash(dict(context=info,input_hash=input_hash))
        assert torch.equal(kwargs['qsv'],tokens['qsv'])
        assert torch.equal(kwargs['qsv_mask'],tokens['qsv_mask'])
        for name,value in tokens.items():
            if name not in ('qsv','qsv_mask'):
                assert torch.equal(kwargs['tokens'][name],value)
        observed.append(True)
        return original(**kwargs)
    monkeypatch.setattr(boss,'forward_decision',capture)
    receipt = learner.step(**args)
    assert observed == [True] and receipt['updated']
