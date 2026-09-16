import json
import sqlite3
from types import SimpleNamespace

import pytest

from research.kalshi.frankie_boss import c15_journal
from research.kalshi.frankie_boss import native_forecast_learning as learning
from research.kalshi.frankie_boss.operations import benchmark_native_learner_direct as direct
from research.kalshi.frankie_boss.operations import build_ec2_rerun_configuration as builder


def _feedback_saved():
    feedback=learning.FrankieFeedback(
        request_id='run-cycle-00',input_hash='1'*64,source_hash='2'*64,available_ns=100,
        principal_receipt_hash='3'*64,
        sessions=(learning.SessionFeedback(session_id='s1',
            timing=(learning.TimingLabel(previous_ns=0,previous_delay_ns=0,next_ns=None,
                observed_through_ns=90,available_ns=100,evidence_hash='4'*64),),
            gap=None,path=()),))
    from dataclasses import asdict
    return dict(feedback=asdict(feedback),feedback_hash=feedback.digest,envelope_hash='5'*64),feedback


def test_typed_feedback_reconstructs_exact_saved_digest():
    saved,expected=_feedback_saved()
    rebuilt=direct._typed_feedback(saved,learning)
    assert rebuilt==expected
    assert rebuilt.digest==saved['feedback_hash']


def test_typed_feedback_rejects_changed_feedback_hash():
    saved,_=_feedback_saved();saved['feedback_hash']='f'*64
    with pytest.raises(ValueError,match='feedback_hash'):
        direct._typed_feedback(saved,learning)


def test_load_stage_rechecks_sqlite_payload_digest(tmp_path):
    path=tmp_path/'cycles.sqlite';value={'feedback':{'x':1}}
    raw=c15_journal.canonical_bytes(c15_journal.pack(value));digest=c15_journal.evidence_hash(value)
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE stages (request TEXT, stage TEXT, payload BLOB, digest TEXT, PRIMARY KEY(request,stage))')
        db.execute('INSERT INTO stages VALUES (?,?,?,?)',('r','feedback',raw,digest));db.commit()
    assert direct._load_stage(path,'r','feedback',unpack=c15_journal.unpack,
                              evidence_hash=c15_journal.evidence_hash)==value
    with sqlite3.connect(path) as db:
        db.execute("UPDATE stages SET digest=? WHERE request='r' AND stage='feedback'",('0'*64,));db.commit()
    with pytest.raises(ValueError,match='digest changed'):
        direct._load_stage(path,'r','feedback',unpack=c15_journal.unpack,
                           evidence_hash=c15_journal.evidence_hash)


def test_completion_ref_requires_reviewed_commit_ancestor(monkeypatch,tmp_path):
    boss='a'*40;tip='b'*40;calls=[]
    monkeypatch.setattr(builder.subprocess,'check_output',
        lambda *a,**k:f'{tip}\trefs/heads/reviewed\n')
    def run(argv,**kwargs):
        calls.append(argv)
        if argv[:3]==['git','merge-base','--is-ancestor']:
            return SimpleNamespace(returncode=0)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(builder.subprocess,'run',run)
    assert builder.completion_ref_contains_commit(tmp_path,'reviewed',boss)==tip
    assert ['git','merge-base','--is-ancestor',boss,tip] in calls


def test_completion_ref_fails_closed_when_reviewed_commit_not_ancestor(monkeypatch,tmp_path):
    boss='a'*40;tip='b'*40
    monkeypatch.setattr(builder.subprocess,'check_output',
        lambda *a,**k:f'{tip}\trefs/heads/reviewed\n')
    def run(argv,**kwargs):
        return SimpleNamespace(returncode=1 if argv[:3]==['git','merge-base','--is-ancestor'] else 0)
    monkeypatch.setattr(builder.subprocess,'run',run)
    with pytest.raises(SystemExit,match='does not contain'):
        builder.completion_ref_contains_commit(tmp_path,'reviewed',boss)
