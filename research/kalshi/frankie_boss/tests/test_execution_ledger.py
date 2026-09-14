"""Durability and single-send tests using synthetic, non-network callbacks."""
from dataclasses import replace
import multiprocessing
import pytest

from test_execution_policy import fixture, H
from research.kalshi.frankie_boss.execution_contracts import Ratio, SignedRatio
from research.kalshi.frankie_boss.execution_ledger import ExecutionLedger, WireRequest, Observation


def build_ledger(tmp_path):
    ledger=ExecutionLedger(tmp_path/'orders.sqlite',create=True)
    args=fixture(); ledger.create(args['intent'])
    decision=ledger.approve(**args)
    assert decision.allowed
    wire=WireRequest(args['intent'].digest,H,'POST','/synthetic/orders',b'{"synthetic":true}',args['intent'].intent_id)
    return ledger,args,wire


def observation(args,status='FILLED',filled=2,remaining=0):
    return Observation('obs/1',args['intent'].intent_id,args['intent'].digest,
        args['intent'].account,'provider/1',args['intent'].intent_id,status,
        filled,remaining,H,11,True,True,b'{"synthetic":true}')


def reconcile_terminal(ledger,args,obs):
    snapshot=replace(args['account'],observed_ns=obs.observed_ns,pnl_observed_ns=obs.observed_ns,
        exposures=tuple(replace(e,gross=obs.filled_quantity*2,net_min=obs.filled_quantity*2,
                               net_max=obs.filled_quantity*2) for e in args['account'].exposures),
        reflected_intents=(args['intent'].intent_id,))
    return ledger.reconcile(replace(obs,account_snapshot_hash=snapshot.digest),
                            account_snapshot=snapshot,expected_account_hash=snapshot.digest)


def test_dispatch_records_unknown_before_callback_and_never_repeats(tmp_path):
    ledger,args,wire=build_ledger(tmp_path);calls=[]
    def sender(request):
        assert ledger.state(args['intent'].intent_id)['status']=='SENT_UNKNOWN'
        calls.append(request);return b'raw ack'
    assert ledger.dispatch_once(wire=wire,sender=sender,**args)==b'raw ack'
    assert ledger.state(args['intent'].intent_id)['status']=='SENT_UNKNOWN'
    assert len(ledger.reservations())==1
    with pytest.raises(ValueError): ledger.dispatch_once(wire=wire,sender=sender,**args)
    assert len(calls)==1
    ledger.close()


def test_timeout_remains_reserved_and_restore_does_not_resend(tmp_path):
    ledger,args,wire=build_ledger(tmp_path)
    def uncertain(_): raise TimeoutError('fake remote outcome unknown')
    with pytest.raises(TimeoutError): ledger.dispatch_once(wire=wire,sender=uncertain,**args)
    checkpoint=ledger.checkpoint();ledger.close()
    restored=ExecutionLedger(tmp_path/'orders.sqlite',checkpoint=checkpoint)
    assert len(restored.reservations())==1
    with pytest.raises(ValueError): restored.dispatch_once(wire=wire,sender=lambda _:pytest.fail('resend'),**args)
    restored.close()


def test_matching_terminal_reconcile_releases_once_and_retains_history(tmp_path):
    ledger,args,wire=build_ledger(tmp_path)
    ledger.dispatch_once(wire=wire,sender=lambda _:b'ack',**args)
    obs=observation(args);reconcile_terminal(ledger,args,obs)
    checkpoint=ledger.checkpoint()
    assert ledger.reservations()==()
    reconcile_terminal(ledger,args,obs)
    assert ledger.checkpoint()==checkpoint
    ledger.close()
    restored=ExecutionLedger(tmp_path/'orders.sqlite',checkpoint=checkpoint)
    assert restored.state(args['intent'].intent_id)['status']=='FILLED'
    assert restored.reservations()==()
    restored.close()


@pytest.mark.parametrize('changes',[{'complete':False},{'positions_match':False},
    {'filled_quantity':3},{'client_id':'wrong'}, {'intent_hash':'b'*64},
    {'status':'UNRECOGNIZED'}])
def test_unresolved_observation_freezes_and_does_not_release(tmp_path,changes):
    ledger,args,wire=build_ledger(tmp_path);ledger.dispatch_once(wire=wire,sender=lambda _:b'ack',**args)
    assert not ledger.reconcile(replace(observation(args),**changes))
    assert len(ledger.reservations())==1
    assert ledger.killed
    ledger.close()


def test_partial_cancel_race_and_late_fill_cannot_silently_change_terminal(tmp_path):
    ledger,args,wire=build_ledger(tmp_path);ledger.dispatch_once(wire=wire,sender=lambda _:b'ack',**args)
    assert ledger.reconcile(observation(args,'PARTIAL',1,1))
    assert len(ledger.reservations())==1
    obs=replace(observation(args,'CANCELED',1,0),observation_id='obs/2')
    assert reconcile_terminal(ledger,args,obs)
    assert not ledger.reconcile(replace(observation(args),observation_id='obs/3'))
    assert ledger.killed and len(ledger.reservations())==1
    ledger.close()


def test_fraction_reservations_round_outward(tmp_path):
    ledger=ExecutionLedger(tmp_path/'orders.sqlite',create=True);args=fixture()
    valuation=replace(args['valuation'],exposure_per_quantity=Ratio(1,3),side='sell',
        net_min_per_quantity=SignedRatio(-1,3),net_max_per_quantity=SignedRatio(0,1))
    args['valuation']=valuation;args['expected_valuation_hash']=valuation.digest
    args['intent']=replace(args['intent'],valuation_hash=valuation.digest,side='sell')
    ledger.create(args['intent']);assert ledger.approve(**args).allowed
    for exposure in ledger.reservations()[0].exposures:
        assert (exposure.gross,exposure.net_min,exposure.net_max)==(1,-1,0)
    ledger.close()


def test_kill_between_approval_and_dispatch_sends_nothing(tmp_path):
    ledger,args,wire=build_ledger(tmp_path);ledger.latch_kill('operator stop')
    with pytest.raises(ValueError): ledger.dispatch_once(wire=wire,sender=lambda _:pytest.fail('sent'),**args)
    assert len(ledger.reservations())==1
    checkpoint=ledger.checkpoint();ledger.close()
    restored=ExecutionLedger(tmp_path/'orders.sqlite',checkpoint=checkpoint)
    assert restored.killed;restored.close()


def test_uncertain_outbox_commit_calls_no_sender_and_poison_instance(tmp_path,monkeypatch):
    ledger,args,wire=build_ledger(tmp_path);original=ledger.journal.append
    def fail_after_commit(kind,payload):
        result=original(kind,payload)
        if payload['step']=='SENT_UNKNOWN': raise OSError('commit acknowledgement lost')
        return result
    monkeypatch.setattr(ledger.journal,'append',fail_after_commit)
    with pytest.raises(OSError): ledger.dispatch_once(wire=wire,sender=lambda _:pytest.fail('sent'),**args)
    with pytest.raises(ValueError):ledger.checkpoint()
    ledger.close()


def try_other_writer(path,queue):
    try:
        other=ExecutionLedger(path,create=False,checkpoint={'schema':'bad','count':0,'head_hash':H})
    except Exception as exc: queue.put(str(exc))
    else: other.close();queue.put('unexpected success')


def test_second_process_cannot_take_writer_lease(tmp_path):
    ledger,args,wire=build_ledger(tmp_path)
    context=multiprocessing.get_context('spawn');queue=context.Queue()
    child=context.Process(target=try_other_writer,args=(str(tmp_path/'orders.sqlite'),queue))
    child.start();child.join(20)
    assert not child.is_alive()
    assert 'writer lease' in queue.get(timeout=5)
    ledger.close()


def test_second_pending_order_sees_authoritative_reservation(tmp_path):
    ledger,args,wire=build_ledger(tmp_path)
    from test_execution_policy import changed_policy
    args=changed_policy(args,scope_limits=tuple(replace(s,gross=7) for s in args['policy'].scope_limits))
    args['intent']=replace(args['intent'],intent_id='intent/2')
    ledger.create(args['intent'])
    assert not ledger.approve(**args).allowed
    assert len(ledger.reservations())==1
    ledger.close()


def test_unknown_submission_blocks_new_exposure_even_with_budget(tmp_path):
    ledger,args,wire=build_ledger(tmp_path)
    ledger.dispatch_once(wire=wire,sender=lambda _:b'ack',**args)
    args['intent']=replace(args['intent'],intent_id='intent/2');ledger.create(args['intent'])
    with pytest.raises(ValueError,match='unknown submission'):ledger.approve(**args)
    ledger.close()


def test_expired_revalidation_and_wrong_wire_send_nothing(tmp_path):
    ledger,args,wire=build_ledger(tmp_path)
    with pytest.raises(ValueError):
        ledger.dispatch_once(wire=wire,sender=lambda _:pytest.fail('sent'),**{**args,'now':20})
    with pytest.raises(ValueError):
        ledger.dispatch_once(wire=replace(wire,intent_hash='b'*64),sender=lambda _:pytest.fail('sent'),**args)
    assert ledger.state(args['intent'].intent_id)['wire'] is None
    ledger.close()


def test_foreign_suffix_and_old_restore_checkpoint_fail_closed(tmp_path):
    from research.kalshi.frankie_boss.c15_journal import EvidenceJournal
    ledger,args,wire=build_ledger(tmp_path);checkpoint=ledger.checkpoint()
    other=EvidenceJournal(tmp_path/'orders.sqlite');other.append('foreign',{});other.close()
    with pytest.raises(ValueError):ledger.state(args['intent'].intent_id)
    ledger.close()
    with pytest.raises(ValueError):ExecutionLedger(tmp_path/'orders.sqlite',checkpoint=checkpoint)


@pytest.mark.parametrize('restart',[False,True])
def test_terminal_release_requires_reflected_snapshot_and_rejects_stale_reapproval(tmp_path,restart):
    ledger,args,wire=build_ledger(tmp_path)
    ledger.dispatch_once(wire=wire,sender=lambda _:b'ack',**args)
    snapshot=replace(args['account'],observed_ns=11,pnl_observed_ns=11,
        exposures=tuple(replace(e,gross=4,net_min=4,net_max=4) for e in args['account'].exposures),
        reflected_intents=(args['intent'].intent_id,))
    obs=replace(observation(args),account_snapshot_hash=snapshot.digest)
    assert ledger.reconcile(obs,account_snapshot=snapshot,expected_account_hash=snapshot.digest)
    if restart:
        checkpoint=ledger.checkpoint();ledger.close()
        ledger=ExecutionLedger(tmp_path/'orders.sqlite',checkpoint=checkpoint)
    args['intent']=replace(args['intent'],intent_id='intent/2');ledger.create(args['intent'])
    with pytest.raises(ValueError,match='frontier'):ledger.approve(**args)
    with pytest.raises(ValueError,match='frontier'):ledger.approve(**{**args,'account':snapshot})
    assert ledger.approve(**{**args,'account':snapshot,'now':11}).allowed
    ledger.close()


def test_kill_latches_durably_from_other_thread_during_callback(tmp_path):
    import threading
    ledger,args,wire=build_ledger(tmp_path);outcomes=[]
    def sender(_):
        worker=threading.Thread(target=lambda:outcomes.append(ledger.latch_kill('operator stop during send')))
        worker.start();worker.join(2)
        assert not worker.is_alive()
        assert ledger.killed
        return b'ack'
    ledger.dispatch_once(wire=wire,sender=sender,**args)
    assert outcomes[0]['durable'] and outcomes[0]['latched']
    checkpoint=ledger.checkpoint();ledger.close()
    ledger=ExecutionLedger(tmp_path/'orders.sqlite',checkpoint=checkpoint)
    assert ledger.killed;ledger.close()


def test_reflected_fill_still_counts_against_next_order_cap(tmp_path):
    from test_execution_policy import changed_policy, codes
    ledger,args,wire=build_ledger(tmp_path)
    ledger.dispatch_once(wire=wire,sender=lambda _:b'ack',**args)
    snapshot=replace(args['account'],observed_ns=11,pnl_observed_ns=11,
        exposures=tuple(replace(e,gross=4,net_min=4,net_max=4) for e in args['account'].exposures),
        reflected_intents=(args['intent'].intent_id,))
    obs=replace(observation(args),account_snapshot_hash=snapshot.digest)
    assert ledger.reconcile(obs,account_snapshot=snapshot,expected_account_hash=snapshot.digest)
    args=changed_policy(args,scope_limits=tuple(replace(s,gross=7) for s in args['policy'].scope_limits))
    args.update(account=snapshot,now=11,intent=replace(args['intent'],intent_id='intent/2'))
    ledger.create(args['intent'])
    decision=ledger.approve(**args)
    assert not decision.allowed and any(c.startswith('gross:') for c in codes(decision))
    ledger.close()


def crash_after_kill_marker(path,checkpoint):
    import os
    ledger=ExecutionLedger(path,checkpoint=checkpoint)
    ledger.latch_kill('durable before process exit')
    os._exit(0)


def test_pending_kill_marker_survives_process_exit_before_journal_sync(tmp_path):
    ledger,args,wire=build_ledger(tmp_path)
    checkpoint=ledger.checkpoint();ledger.close()
    context=multiprocessing.get_context('spawn')
    child=context.Process(target=crash_after_kill_marker,args=(str(tmp_path/'orders.sqlite'),checkpoint))
    child.start();child.join(20)
    assert not child.is_alive() and child.exitcode==0
    restored=ExecutionLedger(tmp_path/'orders.sqlite',checkpoint=checkpoint)
    assert restored.killed
    with pytest.raises(ValueError):
        restored.dispatch_once(wire=wire,sender=lambda _:pytest.fail('sent after durable kill'),**args)
    assert len(restored.reservations())==1
    restored.close()
