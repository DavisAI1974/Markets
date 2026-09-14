"""Static authority checks: parse source only; never import a production module."""
import ast
import json
from pathlib import Path
import subprocess

import pytest

BOSS = Path(__file__).resolve().parents[1]
ROOT = BOSS.parents[2]
MAP_PATH = BOSS / 'AUTHORITY_MAP.json'


def registry():
    return json.loads(MAP_PATH.read_text(encoding='utf-8'))


def definitions(source):
    found = set()
    def walk(node, parent=''):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            parent = f'{parent}.{node.name}' if parent else node.name
            found.add(parent)
        for child in ast.iter_child_nodes(node):
            walk(child, parent)
    walk(ast.parse(source))
    return found


def source_for(reference):
    if 'commit' in reference:
        return subprocess.check_output(['git', 'show', reference['commit'] + ':' + reference['path']],
                                       cwd=ROOT).decode('utf-8-sig')
    return (ROOT / reference['path']).read_text(encoding='utf-8-sig')


def test_named_authorities_and_readers_exist_without_importing_them():
    data = registry()
    assert data['schema'] == 'BOSS_STATIC_AUTHORITY_MAP_V1'
    assert data['runtime_arbitration'] is False
    ids = [store['id'] for store in data['stores']]
    assert len(ids) == len(set(ids))
    for store in data['stores']:
        assert all(store[field] for field in ('location', 'identity', 'protection', 'attribution'))
        assert not isinstance(store['writer'], list), 'one semantic writer per declared surface'
        refs = store['readers'] + ([store['writer']] if store['writer'] else [])
        for ref in refs:
            assert ref['symbol'] in definitions(source_for(ref)), ref


def inspect_source(source, rules):
    """Conservative file-local syntax checks; not interprocedural path analysis."""
    tree = ast.parse(source)
    aliases, journal_names, protected_names = {}, set(), set()
    nodes = list(ast.walk(tree))
    for node in nodes:
        if isinstance(node, ast.Import):
            for alias in node.names:
                aliases[alias.asname or alias.name.split('.')[0]] = alias.name if alias.asname else alias.name.split('.')[0]
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                aliases[alias.asname or alias.name] = '.'.join(filter(None, (node.module, alias.name)))

    def name(node):
        if isinstance(node, ast.Name):
            return aliases.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            return name(node.value) + '.' + node.attr
        return ''

    def protected(node):
        if node is None:
            return False
        for part in ast.walk(node):
            value = part.value if isinstance(part, ast.Constant) else part.id if isinstance(part, ast.Name) else part.attr if isinstance(part, ast.Attribute) else ''
            if isinstance(value, str) and (value in protected_names or any(
                    marker in value.lower() for marker in rules['protected_path_markers'])):
                return True
        return False

    # Fixed point supports simple chains such as p = ROOT / 'knowledge'; dest = p.
    for _ in range(len(nodes)):
        before = (len(journal_names), len(protected_names))
        for node in nodes:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)) or node.value is None:
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            journal = (isinstance(value, ast.Call) and name(value.func).split('.')[-1] == 'EvidenceJournal') or name(value) in journal_names
            for target in targets:
                if journal:
                    journal_names.add(name(target))
                if protected(value):
                    protected_names.add(name(target))
        if before == (len(journal_names), len(protected_names)):
            break

    found = []
    def walk(node, scope=''):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            scope = f'{scope}.{node.name}' if scope else node.name
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imported = [alias.name for alias in node.names] + ([node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
            if any(part in rules['forbidden_imports'] for item in imported for part in item.split('.')):
                found.append(('protected_import', scope, node.lineno))
        if isinstance(node, ast.Call):
            function = name(node.func)
            leaf = function.split('.')[-1]
            receiver = node.func.value if isinstance(node.func, ast.Attribute) else None
            if leaf == 'EvidenceJournal':
                found.append(('journal_constructors', scope, node.lineno))
            if function == 'sqlite3.connect':
                found.append(('physical_connects', scope, node.lineno))
            if leaf == 'append' and (name(receiver) in journal_names or name(receiver).split('.')[-1] in ('journal', '_journal')):
                found.append(('journal_appends', scope, node.lineno))
            targets = ([receiver] if leaf in ('write', 'write_text', 'write_bytes') else
                       [receiver, *node.args, *(keyword.value for keyword in node.keywords)])
            write = leaf in ('write', 'write_text', 'write_bytes', 'unlink', 'remove', 'rename',
                             'replace', 'rmdir', 'rmtree', 'mkdir', 'makedirs', 'copy', 'copyfile', 'move')
            if leaf == 'open':
                # Builtin/io.open: mode arg1. Path.open: mode arg0; default is read.
                index = 1 if function in ('open', 'io.open', 'builtins.open') else 0
                mode = next((kw.value for kw in node.keywords if kw.arg == 'mode'),
                            node.args[index] if len(node.args) > index else ast.Constant(value='r'))
                write = not isinstance(mode, ast.Constant) or not isinstance(mode.value, str) or any(c in mode.value for c in 'wax+')
            if write and any(protected(target) for target in targets):
                found.append(('protected_write', scope, node.lineno))
        for child in ast.iter_child_nodes(node):
            walk(child, scope)
    walk(tree)
    return found


@pytest.mark.parametrize('source,kind', [
    ('from .c15_journal import EvidenceJournal as E\ndef mutate(p):\n    j=E(p, create=True)\n', 'journal_constructors'),
    ('from . import c15_journal as cj\ndef mutate(p):\n    j=cj.EvidenceJournal(p)\n    j.append("bad", {})\n', 'journal_appends'),
    ('def mutate(owner):\n    owner.journal.append("bad", {})\n', 'journal_appends'),
    ('from sqlite3 import connect as db\ndef mutate(p):\n    db(p)\n', 'physical_connects'),
    ('from pathlib import Path\nROOT=Path("knowledge")\np=ROOT/"ng_brain.json"\np.write_text("bad")\n', 'protected_write'),
    ('def mutate(memory_a_path):\n    with open(memory_a_path,"wb") as out:\n        out.write(b"bad")\n', 'protected_write'),
    ('from pathlib import Path\nPath("A_MEMORY_SEED.json").unlink()\n', 'protected_write'),
    ('from pathlib import Path\nPath("scratch").replace("knowledge/ng_brain.json")\n', 'protected_write'),
    ('from research.kalshi import merge_gate\n', 'protected_import'),
])
def test_new_direct_writer_or_protected_memory_write_is_detected(source, kind):
    assert any(found[0] == kind for found in inspect_source(source, registry()['collision_check']))


def test_actual_boss_direct_journal_users_match_declared_semantic_owners():
    rules = registry()['collision_check']
    actual = {kind: {} for kind in ('journal_constructors', 'journal_appends', 'physical_connects')}
    for path in BOSS.rglob('*.py'):
        relative = path.relative_to(BOSS)
        if any(part in rules['exclude_directories'] for part in relative.parts[:-1]):
            continue
        for kind, symbol, line in inspect_source(path.read_text(encoding='utf-8-sig'), rules):
            assert kind in actual, f'{relative}:{line}: forbidden {kind}'
            actual[kind].setdefault(relative.as_posix(), set()).add(symbol)
    for kind, modules in actual.items():
        declared = {path: set(symbols) for path, symbols in rules[kind].items()}
        assert modules == declared, f'{kind}: direct store users changed; update ownership decision explicitly'
        for path, symbols in declared.items():
            assert symbols <= definitions((BOSS / path).read_text(encoding='utf-8-sig'))


def test_read_only_memory_and_generic_artifact_output_are_not_reported_as_writes():
    source = "from pathlib import Path\ndata=Path('knowledge/ng_brain.json').read_bytes()\nPath('artifact.bin').write_bytes(data)\n"
    assert inspect_source(source, registry()['collision_check']) == []


def test_authority_boundaries_preserve_memory_and_distinct_output_contracts():
    data = registry()
    stores = {item['id']: item for item in data['stores']}
    assert stores['frozen_sunday_memory_a']['writer'] is None
    assert stores['agent_memory_carry']['writer']['commit'] == '996d121cb4b8f723c28c5eb61772fed6719c9c14'
    assert 'original44 VERIFIED' in stores['agent_memory_carry']['protection']
    assert 'Historical maintenance writers exist outside BOSS' in stores['legacy_canonical_brain']['protection']
    assert any('eleven-field' in note and 'twelve-field' in note for note in data['corrections'])
    seed = source_for(stores['agent_memory_carry']['writer'])
    parsed = ast.parse(seed)
    count = next(node.value.value for node in parsed.body if isinstance(node, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == 'HISTORICAL_SEED_FINDING_COUNT' for t in node.targets))
    assert count == 44
    for example in data['legacy_maintenance_examples']:
        text = source_for(example)
        if example['symbol']:
            assert example['symbol'] in definitions(text)
