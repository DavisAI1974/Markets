"""Governed complete chunks -> original QSV encoder -> durable provenance.

No source acquisition, bar construction from MBO, segmentation or fitting.
Caller policies/masks and source mappings are explicit assertions, not inferred.
"""
from dataclasses import asdict, dataclass
import hashlib
import math
from pathlib import Path

import numpy as np
import markets_adapter
from markets_adapter import MarketBar, MarketChunk, MarketChunkEncoder
from research.refrag.qsv_registry import QSV_FEATURE_REGISTRY

try:
    from .c15_journal import EvidenceJournal, evidence_hash
    from .context_qsv import QSVContext, QSVRow
    from .forecast_contract import sha256_digest
except ImportError:
    from c15_journal import EvidenceJournal, evidence_hash
    from context_qsv import QSVContext, QSVRow
    from forecast_contract import sha256_digest

SCHEMA = 'BOSS_QSV_PRODUCTION_V1'
BAR_FIELDS = ('ts', 'close', 'open_', 'high', 'low', 'volume', 'buy_vol', 'sell_vol')


def _name(value):
    if type(value) is not str or not value.strip():
        raise ValueError('explicit nonempty identity required')


def _clock(value):
    if type(value) is not int or value < 0:
        raise ValueError('nonnegative integer nanosecond availability required')


def encoder_code_hash():
    return evidence_hash(dict(schema=SCHEMA, encoder_code=hashlib.sha256(
        Path(markets_adapter.__file__).read_bytes()).hexdigest(),
        producer_code=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        numpy_version=np.__version__, names=QSV_FEATURE_REGISTRY))


@dataclass(frozen=True)
class BarObservation:
    ts: float
    close: float
    open_: float
    high: float
    low: float
    volume: float
    buy_vol: float
    sell_vol: float
    available_at: int
    source_hash: str

    def __post_init__(self):
        for name in BAR_FIELDS:
            value = getattr(self, name)
            if type(value) is not float or not math.isfinite(value):
                raise ValueError(f'explicit finite float {name} required')
        _clock(self.available_at)
        numerator, denominator = self.ts.as_integer_ratio()
        if numerator * 1_000_000_000 > self.available_at * denominator:
            raise ValueError('bar timestamp exceeds receive availability')
        sha256_digest(self.source_hash, 'bar source')

    def to_market_bar(self):
        return MarketBar(**{name: getattr(self, name) for name in BAR_FIELDS})


@dataclass(frozen=True)
class ChunkObservation:
    chunk_id: str
    source_id: str
    window_start: int
    window_end: int
    bars: tuple[BarObservation, ...]
    cursor: int
    entity: tuple[int, int]
    source_prefix_hash: str
    available_at: int
    native_receive_ns: int
    mask: tuple[bool, ...]
    realized_vol: float
    bic_segment_score: float

    def __post_init__(self):
        _name(self.chunk_id)
        _name(self.source_id)
        if any(type(value) is not float or not math.isfinite(value)
               for value in (self.realized_vol, self.bic_segment_score)):
            raise ValueError('explicit finite source chunk descriptors required')
        if (type(self.window_start) is not int or self.window_start < 0
                or type(self.window_end) is not int or self.window_end <= self.window_start
                or type(self.bars) is not tuple or not self.bars
                or any(type(bar) is not BarObservation for bar in self.bars)
                or len(self.bars) != self.window_end - self.window_start):
            raise ValueError('complete immutable chunk bounds and bars required')
        for bar in self.bars:
            bar.__post_init__()
        if any(a.ts >= b.ts for a, b in zip(self.bars, self.bars[1:])):
            raise ValueError('bar timestamps must be strictly ordered')
        _clock(self.available_at)
        _clock(self.native_receive_ns)
        if any(bar.available_at > self.available_at for bar in self.bars) or self.available_at > self.native_receive_ns:
            raise ValueError('chunk unavailable at mapped native receive time')
        # Reuse the governed artifact's exact cursor/entity/mask validation.
        QSVRow(self.cursor, self.entity, self.available_at, self.source_prefix_hash,
               tuple(0.0 for _ in QSV_FEATURE_REGISTRY), self.mask)

    def to_market_chunk(self):
        return MarketChunk(self.chunk_id, self.source_id, self.window_start,
                           self.window_end, [bar.to_market_bar() for bar in self.bars],
                           self.realized_vol, self.bic_segment_score)


@dataclass(frozen=True)
class ProducerConfig:
    producer_id: str
    source_manifest_hash: str
    mask_policy_hash: str
    mapping_policy_hash: str
    encoder_hash: str

    def __post_init__(self):
        _name(self.producer_id)
        for name in ('source_manifest_hash', 'mask_policy_hash', 'mapping_policy_hash', 'encoder_hash'):
            sha256_digest(getattr(self, name), name)

    @property
    def digest(self):
        return evidence_hash(dict(schema=SCHEMA, config=asdict(self)))


def source_input_hash(chunks, config):
    if type(config) is not ProducerConfig:
        raise ValueError('explicit producer config required')
    config.__post_init__()
    if type(chunks) is not tuple or not chunks or any(type(chunk) is not ChunkObservation for chunk in chunks):
        raise ValueError('immutable complete chunk observations required')
    for chunk in chunks:
        chunk.__post_init__()
    cursors = tuple(chunk.cursor for chunk in chunks)
    if cursors != tuple(sorted(set(cursors))):
        raise ValueError('native cursor mapping must be unique and ordered')
    return evidence_hash(dict(schema=SCHEMA, config=asdict(config), chunks=tuple(asdict(chunk) for chunk in chunks)))


@dataclass(frozen=True)
class QSVProduction:
    artifact: QSVContext
    input_hash: str
    receipt_hash: str


def _restore(payload):
    if type(payload) is not dict or set(payload) != {'schema', 'config', 'chunks', 'input_hash', 'artifact'}:
        raise ValueError('invalid QSV production record')
    if payload['schema'] != SCHEMA:
        raise ValueError('unknown QSV production schema')
    config = ProducerConfig(**payload['config'])
    chunks = tuple(ChunkObservation(**dict(chunk, bars=tuple(BarObservation(**bar) for bar in chunk['bars'])))
                   for chunk in payload['chunks'])
    if source_input_hash(chunks, config) != payload['input_hash']:
        raise ValueError('stored producer source mismatch')
    value = payload['artifact']
    if type(value) is not dict or set(value) != {'producer_id', 'names', 'rows'}:
        raise ValueError('unknown artifact fields')
    artifact = QSVContext(value['producer_id'], value['names'], tuple(QSVRow(**row) for row in value['rows']))
    if artifact.producer_id != config.digest or len(artifact.rows) != len(chunks):
        raise ValueError('stored producer artifact mismatch')
    for row, chunk in zip(artifact.rows, chunks):
        if (row.cursor, row.entity, row.available_at, row.source_prefix_hash, row.mask) != (
                chunk.cursor, chunk.entity, chunk.available_at, chunk.source_prefix_hash, chunk.mask):
            raise ValueError('stored source-to-native mapping mismatch')
    return QSVProduction(artifact, payload['input_hash'], evidence_hash(payload))


class QSVProducerStore:
    """Single-writer append-only producer log with externally trusted restart."""

    def __init__(self, path, *, create=False, checkpoint=None):
        if type(create) is not bool or (create and checkpoint is not None) or (not create and checkpoint is None):
            raise ValueError('new store or independently trusted restart checkpoint required')
        self.journal = EvidenceJournal(path, create=create)
        try:
            if checkpoint is not None:
                if (type(checkpoint) is not tuple or len(checkpoint) != 2
                        or type(checkpoint[0]) is not int or checkpoint[0] < 0):
                    raise ValueError('exact count/head checkpoint required')
                sha256_digest(checkpoint[1], 'producer checkpoint')
                self.journal.verify(count=checkpoint[0], head_hash=checkpoint[1])
            self._checkpoint = (self.journal.count, self.journal.head_hash)
        except Exception:
            self.journal.close()
            raise

    def checkpoint(self):
        self.journal.verify(count=self._checkpoint[0], head_hash=self._checkpoint[1])
        return self._checkpoint

    def produce(self, chunks, config, *, expected_input_hash):
        sha256_digest(expected_input_hash, 'independent producer input')
        input_hash = source_input_hash(chunks, config)
        if input_hash != expected_input_hash:
            raise ValueError('producer observations differ from trusted source')
        self.checkpoint()
        previous = None
        for entry in self.journal.entries():
            if entry['kind'] != SCHEMA:
                raise ValueError('unknown producer journal entry')
            result = _restore(entry['payload'])
            if result.input_hash == input_hash:
                previous = result
        if previous is not None:
            return previous
        if config.encoder_hash != encoder_code_hash():
            raise ValueError('encoder differs from pinned runtime')
        encoder = MarketChunkEncoder(d_enc=len(QSV_FEATURE_REGISTRY))
        if encoder.feature_registry != QSV_FEATURE_REGISTRY:
            raise ValueError('encoder registry differs')
        vectors = encoder.encode([chunk.to_market_chunk() for chunk in chunks])
        if len(vectors) != len(chunks):
            raise ValueError('encoder dropped a source chunk')
        artifact = QSVContext(config.digest, QSV_FEATURE_REGISTRY, tuple(
            QSVRow(chunk.cursor, chunk.entity, chunk.available_at, chunk.source_prefix_hash,
                   tuple(vector), chunk.mask) for chunk, vector in zip(chunks, vectors)))
        payload = dict(schema=SCHEMA, config=asdict(config), chunks=tuple(asdict(chunk) for chunk in chunks),
                       input_hash=input_hash, artifact=asdict(artifact))
        result = _restore(payload)
        self.journal.append(SCHEMA, payload)
        self._checkpoint = (self.journal.count, self.journal.head_hash)
        return result

    def close(self):
        self.journal.close()
