"""Synthetic, no-forward composition proofs across classroom and lawful recovery.

Host infrastructure/runtime loading is stubbed; the governed teacher attachment,
classroom builder, retention, lazy adapter factory and adapter constructor are real.
No retained market evidence, principal dispatch, learner step or service is used.
"""
import ast
import inspect
import json
import sys
from types import SimpleNamespace

import pytest

from research.kalshi.frankie_boss import sunday_execution as execution
from research.kalshi.frankie_boss.c15_normalizer import IdentityNormalizer
from research.kalshi.frankie_boss.c15_teacher import JournalTeacher
from research.kalshi.frankie_boss.dipole_classroom_integration import IntegratedDipoleClassroomPrincipalAdapter
from research.kalshi.frankie_boss.frankie_principal_adapter import SECTIONS, canonical, digest, file_witness
from research.kalshi.frankie_boss.operations import run_actual_sunday as lawful
from research.kalshi.frankie_boss.operations import run_actual_sunday_classroom as classroom
from research.kalshi.frankie_boss.operations import run_actual_sunday_ec2 as ec2


def test_governed_attachment_to_exact_runtime_and_lazy_adapter(tmp_path, monkeypatch):
    from test_c15_full_evidence import build, row, submit
    builder = build(tmp_path)
    try:
        for i in range(3):
            submit(builder, row(i, oid=i + 1))
        evidence = list(builder.evidence_stream())
        teacher = JournalTeacher({1: 1}, normalizer=IdentityNormalizer((1,)))
        attachment = teacher.attach(evidence, evidence, as_of=202, source_manifest_hash='a' * 64)
        source_checkpoint = dict(count=builder.journal.count, head_hash=builder.journal.head_hash)
    finally:
        builder.journal.close()
    # Classroom must consume the existing attachment; attaching again is a defect.
    monkeypatch.setattr(JournalTeacher, 'attach', lambda *a, **k: pytest.fail('teacher recomputed'))
    binding = dict(cycle_index=0, as_of=202, source_as_of=202, through_cursor=2,
                   source_hash=evidence[-1]['terminal_prefix_hash'], contract_sha256='b' * 64,
                   sessions=())
    cycle = tmp_path / 'cycle-00'
    cycle.mkdir()
    schedule = tmp_path / 'schedule.json'
    schedule.write_bytes(canonical([binding]))
    host = object.__new__(classroom.ClassroomActualHost)
    host.config = dict(run_id='synthetic')
    host.coordinator = SimpleNamespace(learning_policy=None)
    host.host = dict(schedule=dict(path=str(schedule), sha256=file_witness(schedule)['sha256']))
    host.api = SimpleNamespace(driver=execution)
    host.classroom_package = None
    preparations = []

    def prepared(as_of, through_cursor):
        preparations.append((as_of, through_cursor))
        return None, None, 'c' * 64, attachment, evidence

    host.cache = SimpleNamespace(prepare=prepared, receipt=dict(
        input_hash='c' * 64, context_cursors=attachment['context_cursors']))
    monkeypatch.setattr(lawful.ActualHost, 'prime_cache', lambda *a: None)
    host.prime_cache(binding, cycle)
    package = host.classroom_package
    assert preparations == [(202, 2)]
    assert package['source']['context_cursors'] == (0, 1, 2)
    assert package['source']['teacher_attachment_hash'] == attachment['attachment_hash']
    assert tuple(r['target_hash'] for r in package['source']['rows']) == tuple(
        target.target_hash for target in attachment['targets'])

    runtime = execution.SundayRuntime(
        context=None, decoder=None, optimizer=None, checkpoint=None, expected_checkpoint_hash='d' * 64,
        development_identity={}, refresh_policy=None, input_hash='c' * 64,
        expected_native_hash='e' * 64, expected_critic_config_hash='f' * 64,
        expected_critic_identity_hash='1' * 64, critic_factory=lambda: pytest.fail('critic called'),
        source_journal_path=str(tmp_path / 'evidence.sqlite'), source_journal_checkpoint=source_checkpoint)
    monkeypatch.setattr(lawful.ActualHost, 'runtime', lambda *a: runtime)
    host.classroom_package = {'stale': True}
    assert host.runtime(binding, cycle, None) is runtime
    assert runtime.classroom_package == package
    assert runtime.principal_adapter_class is IntegratedDipoleClassroomPrincipalAdapter

    handoff = tmp_path / 'handoff'
    handoff.mkdir()
    source = dict(prefix_hash=binding['source_hash'], through_cursor=2, as_of=202, source_as_of=202)
    manifest = dict(source=source, agent_commit='2' * 40, boss_commit='3' * 40,
                    controller_checkpoint={}, native_checkpoint={})
    (handoff / 'manifest.json').write_bytes(canonical(manifest))
    execution._save(cycle / 'principal-export.c15.json', dict(
        directory=str(handoff), manifest_sha256=file_witness(handoff / 'manifest.json')['sha256']))
    principal = cycle / 'principal'
    principal.mkdir()
    # Exercise the actual retained-prefix factory path with exact independent pins.
    (principal / 'bound-mapping.json').write_bytes(canonical(dict(
        boss_source=source, mapping_sha256='4' * 64, journal_checkpoint=source_checkpoint)))
    retained = tmp_path / 'retained'
    retained.mkdir()
    witnesses = {}
    for name in ('sunday_spawn_prompt.md', 'KNOWLEDGE_RECEIPT.json', 'KNOWLEDGE_BUNDLE.md',
                 'FROZEN_MEMORY_A_20211003.json', *(f'sections/contract_section_{s}.json' for s in SECTIONS)):
        path = retained / name
        path.parent.mkdir(exist_ok=True)
        path.write_text('synthetic historical witness: ' + name)
        witnesses[name] = dict(path=str(path), **file_witness(path))
    witness_path = retained / 'retained-witnesses.json'
    witness_path.write_bytes(canonical(dict(files=witnesses)))
    delivery = dict(manifest_sha256='5' * 64)
    delivery['receipt_sha256'] = digest(delivery)
    delivery_path = retained / 'delivery.json'
    delivery_path.write_bytes(canonical(delivery))
    result_path = retained / 'result.json'
    result_path.write_bytes(canonical(dict(result_hash='6' * 64, layers=dict(identity_receipt=dict(
        run_id='historical', arm='retained', source_manifest_hash='7' * 64)))))
    configuration = dict(mapping_directory=str(retained), expected_mapping_sha256='4' * 64,
        receiver_root=str(tmp_path / 'receiver'), receiver_commit='2' * 40, python=sys.executable,
        retained_directory=str(retained), expected_retained_witnesses_sha256=file_witness(witness_path)['sha256'],
        delivery_receipt=str(delivery_path), expected_delivery_file_sha256=file_witness(delivery_path)['sha256'],
        result_path=str(result_path), session_executor=lambda *a: pytest.fail('principal dispatched'))
    lazy = execution._LazyPrincipal(configuration, binding, cycle, runtime)
    adapter = lazy._get()
    assert type(adapter) is IntegratedDipoleClassroomPrincipalAdapter
    assert adapter.classroom_package == package
    assert lazy._get() is adapter
    assert adapter.audit_directory == cycle / 'classroom-audit'
    assert not adapter.audit_directory.is_relative_to(principal)
    assert not (principal / 'session-request.json').exists()


@pytest.mark.parametrize('missing', ['all', 'source', 'teacher-key', 'pre-message', 'binding'])
def test_partial_current_cycle_never_inherits_prior_package(tmp_path, monkeypatch, missing):
    host = object.__new__(classroom.ClassroomActualHost)
    host.api = SimpleNamespace(driver=execution)
    host.classroom_package = {'binding': {'request_id': 'previous-cycle'}}
    paths = host._classroom_paths(tmp_path)
    for name, path in paths.items():
        if missing not in ('all', name):
            execution._save(path, {'current': name})
    seen = []

    def runtime(self, *args):
        seen.append(self.classroom_package)
        return SimpleNamespace()

    monkeypatch.setattr(lawful.ActualHost, 'runtime', runtime)
    with pytest.raises(ValueError, match='package must exist'):
        host.runtime({}, tmp_path, None)
    assert seen == [None]
    assert host.classroom_package is None


def test_classroom_and_ec2_composition_do_not_assign_module_or_class_attributes():
    # Local object state is legitimate; rebinding imported dependencies is not.
    for module in (classroom, ec2):
        tree = ast.parse(inspect.getsource(module))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Attribute):
                        root = target.value
                        while isinstance(root, ast.Attribute):
                            root = root.value
                        assert isinstance(root, ast.Name) and root.id in ('self', 'runtime', 'host', 'sys')
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in ('setattr', 'exec')
