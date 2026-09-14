"""Immutable, externally governed QSV inputs for native contexts.

This boundary consumes producer artifacts; it does not infer QSV from MBO rows
or authorize the producer. The caller supplies the independently trusted hash.
"""
from dataclasses import asdict, dataclass
import math
import re
import torch
from research.refrag.qsv_registry import QSV_FEATURE_REGISTRY

try:
    from .c15_journal import evidence_hash
except ImportError:
    from c15_journal import evidence_hash


@dataclass(frozen=True)
class QSVRow:
    cursor: int
    entity: tuple[int, int]
    available_at: int
    source_prefix_hash: str
    values: tuple[float, ...]
    mask: tuple[bool, ...]

    def __post_init__(self):
        if (type(self.cursor) is not int or self.cursor < 0
                or type(self.available_at) is not int or self.available_at < 0
                or type(self.entity) is not tuple or len(self.entity) != 2
                or any(type(x) is not int for x in self.entity)):
            raise ValueError('invalid QSV cursor, entity or availability')
        if not isinstance(self.source_prefix_hash,str) or not re.fullmatch('[0-9a-f]{64}',self.source_prefix_hash):
            raise ValueError('QSV requires exact source prefix hash')
        if (type(self.values) is not tuple or type(self.mask) is not tuple
                or len(self.values) != len(QSV_FEATURE_REGISTRY)
                or len(self.mask) != len(self.values)
                or any(type(x) is not bool for x in self.mask)
                or any(type(x) is not float or not math.isfinite(x) for x in self.values)):
            raise ValueError('QSV requires finite float64 values and Boolean per-field masks')


@dataclass(frozen=True)
class QSVContext:
    producer_id: str
    names: tuple[str, ...]
    rows: tuple[QSVRow, ...]

    def __post_init__(self):
        if not isinstance(self.producer_id,str) or not self.producer_id.strip():
            raise ValueError('QSV producer identity required')
        if type(self.names) is not tuple or self.names != QSV_FEATURE_REGISTRY:
            raise ValueError('QSV registry names/order differ')
        if type(self.rows) is not tuple or any(not isinstance(r,QSVRow) for r in self.rows):
            raise ValueError('QSV rows must be immutable records')
        cursors=[r.cursor for r in self.rows]
        if cursors != sorted(set(cursors)):
            raise ValueError('QSV cursors must be unique and ordered')

    @property
    def digest(self):
        return evidence_hash(dict(schema='BOSS_CONTEXT_QSV_V1', **asdict(self)))

    def attach(self, context, *, expected_hash, device):
        if self.digest != expected_hash:
            raise ValueError('QSV differs from trusted artifact identity')
        rows={r.cursor:r for r in self.rows}
        selected=[]
        for e in context:
            r=rows.get(e['cursor'])
            n=e['normalized']
            if (r is None or r.entity != (n['publisher_id'],n['instrument_id'])
                    or r.available_at > n['ts_recv_ns']
                    or r.source_prefix_hash != e['terminal_prefix_hash']):
                raise ValueError('QSV lacks exact causal context/source coverage')
            selected.append(r)
        values=torch.tensor([r.values for r in selected],dtype=torch.float64,device=device).unsqueeze(0)
        mask=torch.tensor([r.mask for r in selected],dtype=torch.bool,device=device).unsqueeze(0)
        # Bind selected rows only: later external suffixes do not rewrite past inputs.
        binding=evidence_hash(dict(schema='BOSS_CONTEXT_QSV_V1',producer=self.producer_id,
                                  names=self.names,rows=[asdict(r) for r in selected]))
        return values,mask,binding
