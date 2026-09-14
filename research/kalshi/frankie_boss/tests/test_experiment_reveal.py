import pytest
from experiment_reveal import RevealLedger
from test_experiment_locks import plan
from c15_journal import EvidenceJournal


def create(tmp_path):
    return RevealLedger(tmp_path / 'reveal.sqlite', plan(),
                        outputs={'B0': b'null', 'B1': b'negative'}, create=True)


def test_reveal_is_opt_in_and_retained_result_is_replayed(tmp_path):
    ledger = create(tmp_path)
    calls = []
    def load():
        calls.append(1)
        return b'synthetic outcomes'
    with pytest.raises(ValueError, match='authorization'):
        ledger.reveal(load)
    assert not calls
    assert ledger.reveal(load, authorized=True) == b'synthetic outcomes'
    assert ledger.reveal(load, authorized=True) == b'synthetic outcomes'
    assert calls == [1]
    checkpoint = ledger.checkpoint()
    ledger.close()
    restored = RevealLedger(tmp_path / 'reveal.sqlite', plan(), checkpoint=checkpoint)
    assert restored.reveal(load, authorized=True) == b'synthetic outcomes'
    assert calls == [1]
    restored.close()


def test_failed_or_interrupted_reveal_never_reopens_outcomes(tmp_path):
    ledger = create(tmp_path)
    def fail():
        raise TimeoutError('unknown external completion')
    with pytest.raises(TimeoutError):
        ledger.reveal(fail, authorized=True)
    checkpoint = ledger.checkpoint()
    ledger.close()
    restored = RevealLedger(tmp_path / 'reveal.sqlite', plan(), checkpoint=checkpoint)
    with pytest.raises(ValueError, match='uncertain'):
        restored.reveal(lambda: pytest.fail('must not invoke again'), authorized=True)
    restored.close()


def test_external_append_prevents_loader_invocation(tmp_path):
    ledger = create(tmp_path)
    external = EvidenceJournal(tmp_path / 'reveal.sqlite')
    external.append('foreign', {})
    external.close()
    with pytest.raises(ValueError):
        ledger.reveal(lambda: pytest.fail('untrusted journal'), authorized=True)
    ledger.close()


def test_complete_output_roster_required_before_creation(tmp_path):
    with pytest.raises(ValueError):
        RevealLedger(tmp_path/'reveal.sqlite', plan(), outputs={'B0': b'a'}, create=True)
    assert not (tmp_path/'reveal.sqlite').exists()


def test_unknown_newer_terminal_rejected_on_restart(tmp_path):
    ledger = create(tmp_path)
    old = ledger.checkpoint()
    ledger.reveal(lambda: b'outcomes', authorized=True)
    ledger.close()
    with pytest.raises(ValueError):
        RevealLedger(tmp_path/'reveal.sqlite', plan(), checkpoint=old)


def test_changed_plan_rejects_retained_outputs(tmp_path):
    from dataclasses import replace
    ledger = create(tmp_path)
    checkpoint = ledger.checkpoint()
    ledger.close()
    with pytest.raises(ValueError):
        RevealLedger(tmp_path/'reveal.sqlite', replace(plan(), scorer_hash='c'*64),
                     checkpoint=checkpoint)
