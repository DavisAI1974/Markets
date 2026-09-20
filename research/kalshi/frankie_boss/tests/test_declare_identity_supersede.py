"""The identity-supersede declaration helper: reads the saved binding, computes the live identity."""
import json
from pathlib import Path
import sqlite3

import pytest

from research.kalshi.frankie_boss.c15_journal import canonical_bytes, evidence_hash, pack
from research.kalshi.frankie_boss.operations import declare_identity_supersede as declare


def _tree(root):
    for relative, body in (('research/kalshi/frankie_boss/a.py', 'a=1\n'),
                           ('research/kalshi/frankie_boss/tests/t.py', 'ignored\n'),
                           ('research/refrag/b.py', 'b=2\n'),
                           ('research/kalshi/frankie_boss/operations/run_actual_sunday.py', 'host\n')):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)


def _store(run, code_hash):
    run.mkdir(parents=True, exist_ok=True)
    binding = dict(request_id='r-cycle-00', controller=dict(arm_hash='p'*64), learning={}, training_identities=dict(
        training_config_hash='a'*64, code_hash=code_hash, source_hash='c'*64, model_hash='d'*64),
        frozen_memory_sha256='m'*64)
    db = sqlite3.connect(run / 'cycles.sqlite')
    db.execute('CREATE TABLE stages (request TEXT, stage TEXT, payload BLOB, digest TEXT, PRIMARY KEY(request,stage))')
    db.execute('INSERT INTO stages VALUES (?,?,?,?)', ('r-cycle-00', 'binding', canonical_bytes(pack(binding)), evidence_hash(binding)))
    export = dict(request_id='r-cycle-00', boss_commit='0'*40, agent_commit='1'*40)
    db.execute('INSERT INTO stages VALUES (?,?,?,?)', ('r-cycle-00', 'export', canonical_bytes(pack(export)), evidence_hash(export)))
    db.commit(); db.close()


def test_code_identity_matches_the_host_map_shape_and_excludes_tests(tmp_path):
    _tree(tmp_path)
    code, digest = declare.code_identity(tmp_path)
    assert set(code) == {'research/kalshi/frankie_boss/a.py', 'research/refrag/b.py',
                         'research/kalshi/frankie_boss/operations/run_actual_sunday.py', 'host_script'}
    assert digest == evidence_hash(code)


def test_declares_once_and_reports_not_stale(tmp_path, capsys):
    _tree(tmp_path)
    _, live = declare.code_identity(tmp_path)
    run = tmp_path / 'run'
    _store(run, 'x'*64)
    receipts = tmp_path / 'receipts'; receipts.mkdir()
    argv = ['--run-directory', str(run), '--tools-root', str(tmp_path), '--request-id', 'r-cycle-00',
            '--reason', 'advance', '--receipt-directory', str(receipts)]
    assert declare.main(argv) == 0
    entries = json.loads((run / 'cycles.sqlite.identity-supersede.json').read_bytes())
    assert len(entries) == 1 and entries[0]['old_code_hash'] == 'x'*64 and entries[0]['new_code_hash'] == live
    assert entries[0]['old_arm_hash'] == 'p'*64
    assert entries[0]['old_boss_commit'] == '0'*40 and entries[0]['old_agent_commit'] == '1'*40
    assert declare.main(argv) == 0
    assert len(json.loads((run / 'cycles.sqlite.identity-supersede.json').read_bytes())) == 1
    assert 'already_declared' in capsys.readouterr().out
    # a store whose binding already carries the live identity declares nothing
    fresh = tmp_path / 'fresh'
    _store(fresh, live)
    assert declare.main(['--run-directory', str(fresh), '--tools-root', str(tmp_path), '--request-id', 'r-cycle-00',
                         '--reason', 'advance', '--receipt-directory', str(receipts)]) == 0
    assert not (fresh / 'cycles.sqlite.identity-supersede.json').exists()
    assert 'not_stale' in capsys.readouterr().out


def test_supersede_principal_declares_the_old_attachment_hash_even_when_not_stale(tmp_path, capsys):
    _tree(tmp_path)
    _, live = declare.code_identity(tmp_path)
    run = tmp_path / 'run'
    _store(run, live)
    attachment = dict(prompt='p', prompt_witness=dict(bytes=1, sha256='a'*64), attachment_hash='h'*64)
    db = sqlite3.connect(run / 'cycles.sqlite')
    db.execute('INSERT INTO stages VALUES (?,?,?,?)', ('r-cycle-00', 'attachment', canonical_bytes(pack(attachment)), evidence_hash(attachment)))
    db.commit(); db.close()
    receipts = tmp_path / 'receipts'; receipts.mkdir()
    argv = ['--run-directory', str(run), '--tools-root', str(tmp_path), '--request-id', 'r-cycle-00',
            '--reason', 'ledger', '--receipt-directory', str(receipts), '--supersede-principal']
    assert declare.main(argv) == 0
    entries = json.loads((run / 'cycles.sqlite.identity-supersede.json').read_bytes())
    assert len(entries) == 1 and entries[0]['supersede_principal'] is True
    assert entries[0]['old_attachment_hash'] == evidence_hash(attachment)
    assert declare.main(argv) == 0 and 'already_declared' in capsys.readouterr().out
    # a retained principal output refuses the declaration
    db = sqlite3.connect(run / 'cycles.sqlite')
    output = dict(feedback={}, lessons=[])
    db.execute('INSERT INTO stages VALUES (?,?,?,?)', ('r-cycle-00', 'principal_output', canonical_bytes(pack(output)), evidence_hash(output)))
    db.commit(); db.close()
    with pytest.raises(SystemExit, match='never superseded'):
        declare.main(argv)
