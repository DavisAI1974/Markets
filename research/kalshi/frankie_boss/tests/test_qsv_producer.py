"""Governed original encoder -> durable artifact -> native context, synthetic."""
from dataclasses import replace

import pytest

from qsv_producer import (BarObservation, ChunkObservation, ProducerConfig,
                          QSVProducerStore, encoder_code_hash, source_input_hash)
from research.refrag.qsv_registry import QSV_FEATURE_REGISTRY
from markets_adapter import MarketChunkEncoder


def config():
    return ProducerConfig('synthetic-source', 'a'*64, 'b'*64, 'c'*64, encoder_code_hash())


def chunks(prefix='d'*64):
    bars = tuple(BarObservation(float(i-8), 100.+i, 100.+i, 101.+i, 99.+i,
                                10., 6., 4., 1, 'e'*64) for i in range(8))
    return (ChunkObservation('chunk/1', 'source/1', 0, 8, bars, 0, (1, 1),
                             prefix, 1, 2, tuple(True for _ in QSV_FEATURE_REGISTRY), 0., 0.),)


def test_original_encoder_output_preserved_and_restart_idempotent(tmp_path, monkeypatch):
    source, cfg = chunks(), config()
    store = QSVProducerStore(tmp_path/'qsv.sqlite', create=True)
    first = store.produce(source, cfg, expected_input_hash=source_input_hash(source, cfg))
    expected = MarketChunkEncoder().encode([source[0].to_market_chunk()])[0]
    assert first.artifact.rows[0].values == tuple(expected)
    checkpoint = store.checkpoint()
    store.close()
    store = QSVProducerStore(tmp_path/'qsv.sqlite', checkpoint=checkpoint)
    monkeypatch.setattr(MarketChunkEncoder, 'encode', lambda *args: pytest.fail('must reuse output'))
    assert store.produce(source, cfg, expected_input_hash=source_input_hash(source, cfg)) == first
    assert store.checkpoint() == checkpoint
    store.close()


@pytest.mark.parametrize('change', [{'available_at': 3}, {'native_receive_ns': 0},
                                   {'mask': (True,)}, {'bars': ()}])
def test_invalid_availability_or_shape_rejected(change):
    with pytest.raises(ValueError):
        replace(chunks()[0], **change)


def test_wrong_source_and_encoder_pins_before_emission(tmp_path):
    store = QSVProducerStore(tmp_path/'qsv.sqlite', create=True)
    source, cfg = chunks(), config()
    with pytest.raises(ValueError):
        store.produce(source, cfg, expected_input_hash='f'*64)
    wrong = replace(cfg, encoder_hash='f'*64)
    with pytest.raises(ValueError):
        store.produce(source, wrong, expected_input_hash=source_input_hash(source, wrong))
    assert store.checkpoint()[0] == 0
    store.close()


def test_masks_and_present_zero_preserved(tmp_path):
    source, cfg = chunks(), config()
    source = (replace(source[0], mask=(False,) + source[0].mask[1:]),)
    store = QSVProducerStore(tmp_path/'qsv.sqlite', create=True)
    result = store.produce(source, cfg, expected_input_hash=source_input_hash(source, cfg))
    assert result.artifact.rows[0].mask[0] is False
    assert result.artifact.rows[0].mask[1] is True
    store.close()


def test_missing_bar_fields_and_nonfinite_values_not_defaulted():
    with pytest.raises(TypeError):
        BarObservation(ts=0., close=1.)
    with pytest.raises(ValueError):
        replace(chunks()[0].bars[0], volume=float('nan'))


def test_journal_requires_trusted_checkpoint(tmp_path):
    path = tmp_path/'qsv.sqlite'
    store = QSVProducerStore(path, create=True)
    checkpoint = store.checkpoint()
    store.produce(chunks(), config(), expected_input_hash=source_input_hash(chunks(), config()))
    store.close()
    with pytest.raises(ValueError):
        QSVProducerStore(path, checkpoint=checkpoint)
    with pytest.raises(ValueError):
        QSVProducerStore(path)


def test_real_encoder_artifact_reaches_native_context(tmp_path):
    from test_context_qsv import make_case
    from context_session import ContextSessionRunner
    builder, model, _ = make_case(tmp_path)
    event = list(builder.evidence_stream())[0]
    source, cfg = chunks(event['terminal_prefix_hash']), config()
    store = QSVProducerStore(tmp_path/'qsv.sqlite', create=True)
    produced = store.produce(source, cfg, expected_input_hash=source_input_hash(source, cfg))
    runner = ContextSessionRunner(model, builder, entity=(1, 1), qsv=produced.artifact,
                                  expected_qsv_hash=produced.artifact.digest)
    tokens, _, _, _, _ = runner._prepare(2, 0)
    assert tokens['qsv'][0, 0].tolist() == list(produced.artifact.rows[0].values)
    assert tokens['qsv_mask'][0, 0].tolist() == list(produced.artifact.rows[0].mask)
    assert runner.run(as_of=2).receipt.input_hash
    store.close()


@pytest.mark.parametrize('field,changed', [('source_manifest_hash', 'f'*64),
                                         ('mask_policy_hash', 'f'*64),
                                         ('mapping_policy_hash', 'f'*64),
                                         ('producer_id', 'another-source')])
def test_all_governed_policies_bind_source_input(field, changed):
    source, cfg = chunks(), config()
    assert source_input_hash(source, replace(cfg, **{field: changed})) != source_input_hash(source, cfg)


@pytest.mark.parametrize('change', [{'cursor': 1}, {'entity': (1, 2)},
                                   {'source_prefix_hash': 'f'*64}, {'native_receive_ns': 3},
                                   {'mask': (False,)*len(QSV_FEATURE_REGISTRY)}])
def test_native_mapping_and_mask_changes_bind_input(change):
    source, cfg = chunks(), config()
    assert source_input_hash((replace(source[0], **change),), cfg) != source_input_hash(source, cfg)


def test_late_bar_cannot_hide_inside_earlier_available_chunk():
    chunk = chunks()[0]
    with pytest.raises(ValueError):
        replace(chunk, bars=(replace(chunk.bars[0], available_at=2), *chunk.bars[1:]))
    with pytest.raises(ValueError):
        replace(chunk.bars[0], ts=1.)


def test_duplicate_cursor_and_mutable_observations_reject():
    source = chunks()
    with pytest.raises(ValueError):
        source_input_hash(source * 2, config())
    with pytest.raises(ValueError):
        replace(source[0], bars=list(source[0].bars))
    with pytest.raises(ValueError):
        source_input_hash(list(source), config())


def test_source_values_are_owned_before_legacy_mutable_encoder_use(tmp_path):
    chunk = replace(chunks()[0], realized_vol=0.5, bic_segment_score=2.0)
    mutable = chunk.to_market_chunk()
    assert (mutable.realized_vol, mutable.bic_segment_score) == (0.5, 2.0)
    mutable.bars[0].close = 999.
    assert chunk.bars[0].close == 100.
    store = QSVProducerStore(tmp_path/'qsv.sqlite', create=True)
    result = store.produce((chunk,), config(), expected_input_hash=source_input_hash((chunk,), config()))
    assert result.artifact.rows[0].values == tuple(MarketChunkEncoder().encode([chunk.to_market_chunk()])[0])
    store.close()


def test_nonfinite_encoder_result_never_enters_journal(tmp_path, monkeypatch):
    source, cfg = chunks(), config()
    store = QSVProducerStore(tmp_path/'qsv.sqlite', create=True)
    monkeypatch.setattr(MarketChunkEncoder, 'encode', lambda self, chunks: [[float('nan')]*len(QSV_FEATURE_REGISTRY)])
    with pytest.raises(ValueError):
        store.produce(source, cfg, expected_input_hash=source_input_hash(source, cfg))
    assert store.checkpoint()[0] == 0
    store.close()


def test_journal_retains_complete_input_not_only_output(tmp_path):
    from c15_journal import pack
    from dataclasses import asdict
    source, cfg = chunks(), config()
    store = QSVProducerStore(tmp_path/'qsv.sqlite', create=True)
    result = store.produce(source, cfg, expected_input_hash=source_input_hash(source, cfg))
    payload = next(store.journal.entries())['payload']
    assert pack(payload['chunks']) == pack(tuple(asdict(c) for c in source))
    assert payload['input_hash'] == result.input_hash
    assert payload['config'] == asdict(cfg)
    store.close()
