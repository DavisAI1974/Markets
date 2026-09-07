"""BOSS_NATIVE_MBO_ENCODER_V1: exact evidence tensors and one token per event.

The byte lane is a model input, not a storage sidecar. Every byte contributes
through a position-dependent learned categorical embedding. There is no byte
length cap, identity hashing, field averaging or implicit precision conversion.
"""
from __future__ import annotations
from dataclasses import dataclass
import json
import math
import torch
from torch import nn

try:
    from .c15_journal import pack, unpack, evidence_hash
    from .causal_packet import canonical_bytes
    from .trunk import Trunk, TrunkConfig
except ImportError:
    from c15_journal import pack, unpack, evidence_hash
    from causal_packet import canonical_bytes
    from trunk import Trunk, TrunkConfig

SCHEMA = 'BOSS_NATIVE_MBO_ENCODER_V1'
T_CTX = 4096  # Provisional registry value; no mechanics-probe result claimed.
RAW_FIELDS = ('ts_event', 'ts_recv', 'rtype', 'publisher_id', 'instrument_id',
              'action', 'side', 'price', 'size', 'channel_id', 'order_id',
              'flags', 'ts_in_delta', 'sequence')
ADAPTER_FIELDS = ('ts_event_ns', 'ts_recv_ns', 'ts_in_delta_ns', 'price_raw',
                  'raw_symbol', 'source_dbn_object', 'source_dbn_sha256',
                  'is_snapshot', 'is_last', 'independent_clocks')
# These are named semantic views; exact original values/types also enter bytes.
NUMERIC_FIELDS = ('recv_delta_ns', 'event_delta_ns', 'price', 'size', 'sequence', 'ts_in_delta')
NUMERIC_COLUMNS = tuple(f'{name}.{part}' for name in NUMERIC_FIELDS
                        for part in ('sign', 'high32', 'low32')) + ('age_in_context_ns',)
ACTION_VOCAB = ('UNKNOWN', 'A', 'C', 'M', 'R', 'T', 'F', 'N')
SIDE_VOCAB = ('UNKNOWN', 'A', 'B', 'N')
CAT_CARDINALITIES = (8, 4, 257, 257, 257, 257) + (2,)*9
CAT_COLUMNS = ('action', 'side', 'rtype', 'publisher.high8', 'publisher.low8', 'channel_id') + tuple(f'flags.bit{i}' for i in range(8)) + ('independent_clocks',)


@dataclass(frozen=True)
class NativeRegistry:
    extra_fields: tuple[str, ...] = ()

    def __post_init__(self):
        if (type(self.extra_fields) is not tuple
                or any(type(f) is not str or not f for f in self.extra_fields)
                or len(set(self.fields)) != len(self.fields)):
            raise ValueError('registry extensions must name unique additional fields')

    @property
    def fields(self):
        return RAW_FIELDS + ADAPTER_FIELDS + self.extra_fields

    def payload(self):
        return dict(schema=SCHEMA, fields=self.fields, numeric=NUMERIC_COLUMNS,
                    categorical=CAT_COLUMNS, action=ACTION_VOCAB, side=SIDE_VOCAB,
                    classes={f: ('graph_and_exact_bytes' if f == 'order_id' else
                        'numeric_and_exact_bytes' if f in ('price', 'size', 'sequence', 'ts_event', 'ts_recv', 'ts_in_delta') else
                        'categorical_exact_bytes') for f in self.fields},
                    exact_encoding='journal.pack/canonical_bytes UTF-8; byte vocabulary 0..255',
                    t_ctx=T_CTX, retained_not_encoded=())

    @property
    def digest(self):
        return evidence_hash(self.payload())

    def validate(self, row):
        if type(row) is not dict:
            raise ValueError('explicit source row mapping required')
        unknown = row.keys() - set(self.fields)
        if unknown:
            raise ValueError(f'unmapped native fields: {sorted(unknown)}')
        # Validate all original types even when no semantic projection exists.
        pack(row)


def _value(row, name):
    aliases = {'ts_recv': 'ts_recv_ns', 'ts_event': 'ts_event_ns',
               'ts_in_delta': 'ts_in_delta_ns', 'price': 'price_raw'}
    return row.get(name, row.get(aliases.get(name, name)))


def _parts(value):
    present = type(value) is int and abs(value) <= 2**64-1
    if not present:
        return [0., 0., 0.], [False]*3
    magnitude = abs(value)
    return [float(value < 0), float(magnitude >> 32), float(magnitude & (2**32-1))], [True]*3


def encode(rows, *, as_of, registry, metadata=None):
    """Own every supplied row. Input order is receive order, ties source order.

    Returns batch-one tensors only; inverse reconstruction needs no source copy.
    Known numeric views do not replace the exact byte lane. A missing semantic
    view (unsupported source type/range) is explicit while its bytes still compute.
    """
    if type(as_of) is not int or not 0 <= as_of <= 2**64-1:
        raise ValueError('as_of must be an exact unsigned nanosecond cutoff')
    rows = list(rows)
    if not rows:
        raise ValueError('nonempty context required')
    metadata = [{} for _ in rows] if metadata is None else list(metadata)
    if len(metadata) != len(rows):
        raise ValueError('metadata must account for every event')
    numeric, nmasks, categorical, cmasks, parents, blobs, offsets = [], [], [], [], [], [], [0]
    previous, first = {}, {}
    last_recv = -1
    for i, row in enumerate(rows):
        registry.validate(row)
        meta = metadata[i]
        if type(meta) is not dict or meta.keys() - {'adapter', 'source_context', 'defects'}:
            raise ValueError('unmapped adapter metadata')
        if 'adapter' in meta:
            registry.validate(meta['adapter'])
        recv, event = _value(row, 'ts_recv'), _value(row, 'ts_event')
        if type(recv) is not int or not last_recv <= recv <= as_of:
            raise ValueError('rows must be received by cutoff in receive order')
        last_recv = recv
        n, nm = [], []
        for value in (as_of-recv, as_of-event if type(event) is int else None,
                      _value(row, 'price'), row.get('size'), row.get('sequence'), _value(row, 'ts_in_delta')):
            parts, mask = _parts(value)
            n.extend(parts); nm.extend(mask)
        # Typed exact identity key; no hashing into model vocabulary buckets.
        identity = tuple(canonical_bytes(pack(row.get(f))) for f in ('publisher_id', 'instrument_id', 'order_id'))
        has_order = row.get('order_id') is not None and row.get('order_id') != 0
        parents.append(previous.get(identity, -1) if has_order else -1)
        if has_order:
            first.setdefault(identity, recv)
            previous[identity] = i
        age = recv-first[identity] if has_order else 0
        # Age is a helper only. Raw time deltas above and exact bytes preserve
        # all time bits even for an age too large for direct float64 conversion.
        n.append(float(age) if age <= 2**53 else 0.); nm.append(has_order and age <= 2**53)
        numeric.append(n); nmasks.append(nm)
        action, side = row.get('action'), row.get('side')
        c = [ACTION_VOCAB.index(action) if action in ACTION_VOCAB else 0,
             SIDE_VOCAB.index(side) if side in SIDE_VOCAB else 0]
        cm = [action is not None, side is not None]
        pub = row.get('publisher_id')
        pub_ok = type(pub) is int and 0 <= pub <= 65535
        for value in (row.get('rtype'), pub >> 8 if pub_ok else None,
                      pub & 255 if pub_ok else None, row.get('channel_id')):
            ok = type(value) is int and 0 <= value <= 255
            c.append(value+1 if ok else 0); cm.append(value is not None)
        flags = row.get('flags')
        ok = type(flags) is int and 0 <= flags <= 255
        c.extend([(flags >> bit) & 1 if ok else 0 for bit in range(8)]); cm.extend([ok]*8)
        # The source is Databento with independent capture/exchange clocks.
        clock=row.get('independent_clocks',meta.get('adapter',{}).get('independent_clocks'))
        c.append(int(clock) if type(clock) is bool else 0); cm.append(type(clock) is bool)
        categorical.append(c); cmasks.append(cm)
        blob = canonical_bytes(pack(dict(record=row, metadata=meta)))
        blobs.extend(blob); offsets.append(len(blobs))
    count = len(rows)
    return dict(numeric=torch.tensor([numeric], dtype=torch.float64),
                numeric_mask=torch.tensor([nmasks], dtype=torch.bool),
                categorical=torch.tensor([categorical], dtype=torch.long),
                categorical_mask=torch.tensor([cmasks], dtype=torch.bool),
                parent=torch.tensor([parents], dtype=torch.long),
                venue_id=torch.zeros((1,count), dtype=torch.long),
                instrument_id=torch.zeros((1,count), dtype=torch.long),
                byte_values=torch.tensor(blobs, dtype=torch.uint8),
                byte_offsets=torch.tensor(offsets, dtype=torch.long),
                cutoff=torch.tensor(list(as_of.to_bytes(8, 'big')), dtype=torch.uint8))


def reconstruct_payloads(tokens, registry):
    values = tokens['byte_values'].detach().cpu()
    offsets = tokens['byte_offsets'].detach().cpu()
    if values.dtype != torch.uint8 or offsets.dtype != torch.long or values.ndim != 1 or offsets.ndim != 1:
        raise ValueError('invalid exact-byte tensors')
    bounds = offsets.tolist()
    if not bounds or bounds[0] != 0 or bounds[-1] != values.numel() or any(b <= a for a,b in zip(bounds,bounds[1:])):
        raise ValueError('byte offsets must partition all exact evidence')
    rows = []
    raw = bytes(values.tolist())
    for a,b in zip(bounds,bounds[1:]):
        blob = raw[a:b]
        row = unpack(json.loads(blob))
        if set(row) != {'record', 'metadata'}:
            raise ValueError('invalid exact source envelope')
        registry.validate(row['record'])
        if canonical_bytes(pack(row)) != blob:
            raise ValueError('noncanonical exact field representation')
        rows.append(row)
    return rows


def reconstruct(tokens, registry):
    return [p['record'] for p in reconstruct_payloads(tokens, registry)]


class NativeTrunk(Trunk):
    """Explicit native-input extension. B1 delegates to this represent unchanged.

    All byte positions contribute, including the beginning of long extension
    fields. This is learned model arithmetic over exact inputs, not an average
    or replacement of the source evidence. Zero venue/instrument graph indices
    are neutral: real identities enter the exact byte lane and order link key.
    """
    def __init__(self, registry, **config):
        self.registry = registry
        super().__init__(TrunkConfig(**dict(config, n_numeric=len(NUMERIC_COLUMNS),
            categorical_cardinalities=CAT_CARDINALITIES, n_venues=1, n_instruments=1)))
        self.byte_embedding = nn.Embedding(256, self.cfg.d_model)
        self.byte_projection = nn.Linear(self.cfg.d_model, self.cfg.d_model, bias=False)

    def represent(self, *, tokens, numeric=None, qsv=None, qsv_mask=None):
        if numeric is not None and not torch.equal(numeric, tokens['numeric']):
            raise ValueError('B1 numeric guard input differs from native mapping')
        if self.encoder.numeric.weight.dtype != torch.float64 or tokens['numeric'].dtype != torch.float64:
            raise ValueError('native numeric computation requires float64 model and tensors')
        h = self.encoder(tokens['numeric'], tokens['categorical'], qsv, qsv_mask,
                         tokens['numeric_mask'], tokens['categorical_mask'])
        bounds = tokens['byte_offsets'].tolist()
        if len(bounds) != h.shape[1]+1 or bounds[0] != 0 or bounds[-1] != tokens['byte_values'].numel():
            raise ValueError('every event must own all its exact field bytes')
        embedded = []
        for a,b in zip(bounds,bounds[1:]):
            if b <= a:
                raise ValueError('empty or reversed exact field span')
            values = tokens['byte_values'][a:b].long()
            positions = torch.arange(b-a, device=h.device, dtype=h.dtype).unsqueeze(1)
            frequencies = torch.exp(torch.arange(self.cfg.d_model, device=h.device, dtype=h.dtype)
                                    * (-math.log(10000.)/self.cfg.d_model))
            positional = 1 + torch.sin((positions+1)*frequencies)
            embedded.append((self.byte_embedding(values)*positional).sum(0))
        h = h + self.byte_projection(torch.stack(embedded).unsqueeze(0))
        h = self.graph(h, tokens['venue_id'], tokens['instrument_id'], tokens['parent'])
        for i, attn in enumerate(self.attn):
            h = attn(h)
            if self.mem:
                h = self.mem[i](h)
            h = h + self.ff[i](h)
        return h
