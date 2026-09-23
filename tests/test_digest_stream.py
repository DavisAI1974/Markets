"""Additive disk-table codec: differential bytes, independent inverse proof, bounded storage."""
from __future__ import annotations
import importlib.util
import pathlib
import random
import sqlite3
import sys
import pytest
import test_frankie_box_digest_render as FX

DG = FX.DG
MODULE = pathlib.Path(__file__).resolve().parents[1] / 'deploy/aws/box/frankie_box_digest_stream.py'


def stream():
    spec = importlib.util.spec_from_file_location('frankie_box_digest_stream', MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assert_table(tmp_path, name, rows, context=None):
    mod = stream()
    destination = tmp_path / 'table.txt'
    receipt = mod.write_table(destination, name, iter(rows), tmp_path / 'scratch',
                              context={k: iter(v) for k, v in (context or {}).items()})
    assert destination.read_bytes().decode('utf-8') == DG.render_table(name, rows, context)
    assert receipt['rows'] == len(rows)
    assert receipt['verified'] is True
    mod.verify_table(destination, name, iter(rows), tmp_path / 'verify', context=context)


@pytest.mark.parametrize('test_name', [name for name in vars(FX) if name.startswith('test_')])
def test_existing_codec_fixtures_have_identical_bytes(tmp_path, monkeypatch, test_name):
    mod = stream()
    original = DG.render_table
    ordinal = 0

    def disk_render(name, rows, context=None):
        nonlocal ordinal
        ordinal += 1
        destination = tmp_path / ('table-%d.txt' % ordinal)
        receipt = mod.write_table(destination, name, iter(rows), tmp_path / ('scratch-%d' % ordinal),
                                  context=context)
        text = destination.read_bytes().decode('utf-8')
        assert text == original(name, rows, context)
        assert receipt['verified'] is True
        return text

    monkeypatch.setattr(DG, 'render_table', disk_render)
    getattr(FX, test_name)()


def test_late_global_decisions_and_dictionary_order(tmp_path):
    rows = [dict(constant='fixed', late=i, word='unique-%d' % i, repeated='first' if i % 2 else 'second',
                 ts_recv_ns=1633298400000000000 + i * 1000000) for i in range(80)]
    rows[-1]['constant'] = 'differs'
    rows[-1]['word'] = 'contains a space'
    rows[-2]['word'] = 'unique-0'
    assert_table(tmp_path, 'late', rows)


def test_high_distinct_dictionary_cardinality_is_on_disk(tmp_path):
    # Alternating two passes prevents SAME marks from swallowing repeated strings.
    rows = [dict(word='entry-%d' % (i % 2000)) for i in range(4000)]
    assert_table(tmp_path, 'dictionary', rows)


def test_cross_context_accepts_one_pass_iterators_and_falls_back(tmp_path):
    tables = FX._tables()
    name = 'legacy_structure_observables'
    assert_table(tmp_path / 'match', name, tables[name], {'legacy_book_imbalance': tables['legacy_book_imbalance']})
    tables[name][-1]['ts_recv_ns'] += 3
    assert_table(tmp_path / 'fallback', name, tables[name], {'legacy_book_imbalance': tables['legacy_book_imbalance']})


@pytest.mark.parametrize('rows', [[], [{}], [{}, {}], [dict(x=(1, 2))] * 3,
                                  [dict(x=-0.0), dict(x=0.0), dict(x=float('nan'))]])
def test_empty_constant_tuple_and_float_edges(tmp_path, rows):
    assert_table(tmp_path, 'edges', rows)


def test_materializing_compatibility_wrappers_are_not_used(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('whole-table compatibility wrapper used')
    monkeypatch.setattr(DG, 'render_table', forbidden)
    monkeypatch.setattr(DG, 'parse_table', forbidden)
    receipt = stream().write_table(tmp_path / 'table.txt', 'plain',
                                   (dict(x=i, word='word-%d' % (i % 17)) for i in range(500)),
                                   tmp_path / 'scratch')
    assert receipt['verified'] is True


@pytest.mark.parametrize('mutation', ['truncate', 'extra', 'value', 'dictionary'])
def test_inverse_refuses_corruption_and_keeps_evidence(tmp_path, mutation):
    mod = stream()
    rows = [dict(x=i, word='alpha' if i % 2 else 'beta') for i in range(10)]
    path = tmp_path / 'table.txt'
    mod.write_table(path, 'proof', rows, tmp_path / 'scratch')
    text = path.read_text(encoding='utf-8')
    if mutation == 'truncate':
        text = text[:-2]
    elif mutation == 'extra':
        text += '100 Sbad\n'
    elif mutation == 'value':
        text = text.replace('0 @0', '99 @0', 1)
    else:
        text = text.replace('@0="beta"', '@0="wrong"', 1)
    path.write_text(text, encoding='utf-8')
    with pytest.raises((ValueError, KeyError, IndexError)):
        mod.verify_table(path, 'proof', rows, tmp_path / 'verify')
    assert path.read_text(encoding='utf-8') == text
    assert (tmp_path / 'scratch').exists()


def test_existing_destination_and_scratch_are_never_overwritten(tmp_path):
    mod = stream()
    path = tmp_path / 'table.txt'
    path.write_text('retained evidence', encoding='utf-8')
    with pytest.raises(FileExistsError):
        mod.write_table(path, 'x', [dict(x=1)], tmp_path / 'scratch')
    assert path.read_text(encoding='utf-8') == 'retained evidence'
