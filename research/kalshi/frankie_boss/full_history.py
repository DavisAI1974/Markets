"""Inference over every submitted, ordered BOSS tensor row.

This is a tensor consumption boundary, not a native MBO field mapper. No row
window, chunk sampling, carry-state approximation or implicit dtype conversion.
The caller must retain the native evidence and provide its complete mapping.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import hashlib

import torch

try:
    from .b1_reasoner import B1Reasoner
    from .c15_journal import pack
    from .causal_packet import canonical_bytes
    from .trunk import Trunk, TRUNK_SCHEMA
except ImportError:
    from b1_reasoner import B1Reasoner
    from c15_journal import pack
    from causal_packet import canonical_bytes
    from trunk import Trunk, TRUNK_SCHEMA

SCHEMA = 'BOSS_ORDERED_TENSOR_SESSION_V1'
BASE_KEYS = frozenset(('numeric', 'categorical', 'venue_id', 'instrument_id', 'parent', 'qsv'))
MASK_KEYS = frozenset(('numeric_mask', 'categorical_mask', 'qsv_mask'))


@dataclass(frozen=True)
class TensorConsumptionReceipt:
    schema: str
    trunk_schema: str
    input_hash: str
    model_hash: str
    packet_ranges: tuple[tuple[str, int, int], ...]
    source_packet_hashes: tuple[str, ...]
    row_ids: tuple[str, ...]
    consumed_rows: int


@dataclass(frozen=True)
class HistoryOutput:
    heads: dict
    receipt: TensorConsumptionReceipt
    recurrence_receipt: object | None


class FullHistoryRunner:
    """An inference session owns every appended tensor row until explicitly closed.

    Parent indices are absolute positions in this session. Session/member
    transitions do not reset history. A failed forward leaves the complete
    prefix available for retry; appending more input is blocked until resolved.
    Export owns independent copies of all inputs and binds the required model for restart.
    This receipt proves ordered tensor-session consumption, not source causality
    or native mapping completeness; upstream causal receipts remain required.
    """

    def __init__(self, model):
        if not isinstance(model, (Trunk, B1Reasoner)):
            raise TypeError('full-history model must be Trunk or B1Reasoner')
        self.model = model
        self._inputs = None
        self._row_ids = ()
        self._packet_hashes = ()
        self._packet_ranges = ()
        self._pending = False
        self._check_model()

    def _check_model(self):
        trunk = self.model.trunk if isinstance(self.model, B1Reasoner) else self.model
        if self.model.training or any(module.training for module in self.model.modules()):
            raise ValueError('complete-history inference requires eval mode')
        if not trunk.cfg.use_qsv or trunk.encoder._qsv_ablated:
            raise ValueError('complete-history inference requires unablated QSV')
        attentions = list(trunk.attn)
        if isinstance(self.model, B1Reasoner):
            attentions.append(self.model.swa_r)
        if trunk.cfg.window is not None or any(a.w is not None for a in attentions):
            raise ValueError('complete-history inference forbids finite attention windows')
        return trunk

    def append(self, inputs, *, row_ids, packet_hash):
        if self._pending:
            raise ValueError('previous input is retained but has not completed inference; retry run()')
        trunk = self._check_model()
        if not isinstance(packet_hash, str) or len(packet_hash) != 64 or any(c not in '0123456789abcdef' for c in packet_hash):
            raise ValueError('source packet hash must be lowercase 64-hex')
        if not BASE_KEYS <= inputs.keys() or inputs.keys() - BASE_KEYS - MASK_KEYS:
            raise ValueError('every tensor field must be explicitly mapped; missing/extra keys')
        if any(not isinstance(x, torch.Tensor) for x in inputs.values()):
            raise TypeError('all mapped inputs must be tensors')
        owned = {k: v.detach().clone() for k, v in inputs.items()}
        numeric = owned['numeric']
        if numeric.ndim != 3 or numeric.shape[0] != 1 or numeric.shape[1] < 1:
            raise ValueError('complete-history input must be nonempty batch one')
        n = numeric.shape[1]
        row_ids = tuple(row_ids)
        if (len(row_ids) != n or any(type(r) is not str or not r for r in row_ids)
                or len(set(self._row_ids + row_ids)) != len(self._row_ids) + n):
            raise ValueError('one unique source row identity required per tensor row')
        for name in BASE_KEYS:
            if owned[name].shape[:2] != (1, n):
                raise ValueError(f'{name} must cover every appended row')
        for name in ('numeric', 'qsv'):
            if owned[name].dtype != trunk.encoder.numeric.weight.dtype:
                raise ValueError(f'{name} dtype differs from model; implicit precision reduction forbidden')
        for name in ('categorical', 'venue_id', 'instrument_id', 'parent'):
            if owned[name].dtype != torch.long:
                raise ValueError(f'{name} must be exact integer indices')
        if any(v.device != trunk.encoder.numeric.weight.device for v in owned.values()):
            raise ValueError('inputs and model must share a device')
        for name in ('numeric', 'categorical', 'qsv'):
            key = name + '_mask'
            mask = owned.get(key)
            if mask is None:
                mask = torch.ones_like(owned[name], dtype=torch.bool)
            if name == 'qsv' and mask.ndim == 2:
                mask = mask.unsqueeze(-1)
            if name == 'qsv' and mask.shape == owned[name].shape[:-1] + (1,):
                mask = mask.expand_as(owned[name]).clone()
            # Validate before bool conversion, which could hide an invalid mask.
            owned[key] = trunk.encoder._field_mask(owned[name], mask, name)
        with torch.no_grad():
            trunk.encoder(owned['numeric'], owned['categorical'], owned['qsv'],
                          owned['qsv_mask'], owned['numeric_mask'], owned['categorical_mask'])
        for name, bound in (('venue_id', trunk.cfg.n_venues), ('instrument_id', trunk.cfg.n_instruments)):
            if owned[name].shape != (1, n) or ((owned[name] < 0) | (owned[name] >= bound)).any():
                raise ValueError(f'{name} contains an unmapped identifier')
        parent = owned['parent']
        positions = torch.arange(len(self._row_ids), len(self._row_ids) + n, device=parent.device)
        if parent.shape != (1, n) or ((parent < -1) | (parent >= positions)).any():
            raise ValueError('parent must be -1 or an earlier absolute row index')
        if self._inputs is not None:
            owned = {k: torch.cat((self._inputs[k], owned[k]), dim=1) for k in owned}
        self._inputs = owned
        self._packet_ranges += ((packet_hash, len(self._row_ids), len(self._row_ids) + n),)
        self._row_ids += row_ids
        self._packet_hashes += (packet_hash,)
        self._pending = True

    def _input_hash(self):
        tensor_state = {k: dict(dtype=str(v.dtype), shape=tuple(v.shape),
                                data=v.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes())
                        for k, v in sorted(self._inputs.items())}
        body = dict(schema=SCHEMA, tensors=tensor_state, rows=self._row_ids,
                    packets=self._packet_hashes, packet_ranges=self._packet_ranges)
        return hashlib.sha256(canonical_bytes(pack(body))).hexdigest()

    def _model_hash(self):
        trunk = self._check_model()
        from research.refrag.qsv_registry import QSV_FEATURE_REGISTRY
        weights = {k: dict(dtype=str(v.dtype), shape=tuple(v.shape),
                           data=v.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes())
                   for k, v in sorted(self.model.state_dict().items())}
        code = {name: Path(__file__).with_name(name).read_bytes()
                for name in ('trunk.py', 'b1_reasoner.py', 'full_history.py')}
        body = dict(schema=TRUNK_SCHEMA, config=asdict(trunk.cfg), weights=weights,
                    qsv_registry=tuple(QSV_FEATURE_REGISTRY), code=code,
                    recurrence=asdict(self.model.config) if isinstance(self.model, B1Reasoner) else None)
        return hashlib.sha256(canonical_bytes(pack(body))).hexdigest()

    def run(self):
        self._check_model()
        if self._inputs is None:
            raise ValueError('no input has been appended')
        # Mark pending even on a rerun: any inference failure must block append.
        self._pending = True
        with torch.no_grad():
            if isinstance(self.model, B1Reasoner):
                heads = self.model.forward_decision(**self._inputs, packet_hash=self._packet_hashes[-1])
            else:
                heads = self.model(**self._inputs)
        n = len(self._row_ids)
        if heads['evidence_scores'].shape != (1, n):
            raise ValueError('model did not return an evidence score for every row')
        if any(not torch.isfinite(v).all() for v in heads.values()):
            raise ValueError('nonfinite inference output; complete inputs retained')
        receipt = TensorConsumptionReceipt(SCHEMA, TRUNK_SCHEMA, self._input_hash(), self._model_hash(), self._packet_ranges,
                                           self._packet_hashes, self._row_ids, n)
        self._pending = False
        return HistoryOutput(dict(heads), receipt, getattr(heads, 'receipt', None))

    def export(self):
        if self._inputs is None:
            raise ValueError('no input history')
        return dict(schema=SCHEMA, input_hash=self._input_hash(), model_hash=self._model_hash(),
                    inputs={k: v.detach().clone() for k, v in self._inputs.items()},
                    row_ids=self._row_ids, packet_hashes=self._packet_hashes, packet_ranges=self._packet_ranges)

    @classmethod
    def restore(cls, model, state, *, expected_input_hash, expected_model_hash):
        if set(state) != {'schema', 'input_hash', 'model_hash', 'inputs', 'row_ids', 'packet_hashes', 'packet_ranges'} or state['schema'] != SCHEMA:
            raise ValueError('unsupported complete-history checkpoint')
        if not state['packet_hashes']:
            raise ValueError('missing source packet lineage')
        boundary = 0
        packets = []
        for packet_hash, start, end in state['packet_ranges']:
            if (type(start) is not int or type(end) is not int or start != boundary or end <= start
                    or not isinstance(packet_hash, str) or len(packet_hash) != 64
                    or any(c not in '0123456789abcdef' for c in packet_hash)):
                raise ValueError('invalid row-to-packet membership')
            boundary = end
            packets.append(packet_hash)
        if boundary != len(state['row_ids']) or tuple(packets) != tuple(state['packet_hashes']):
            raise ValueError('packet ranges do not cover complete tensor history')
        result = cls(model)
        if state['model_hash'] != expected_model_hash or result._model_hash() != expected_model_hash:
            raise ValueError('model differs from trusted checkpoint model hash')
        result.append(state['inputs'], row_ids=state['row_ids'], packet_hash=state['packet_hashes'][-1])
        result._packet_hashes = tuple(state['packet_hashes'])
        result._packet_ranges = tuple(tuple(r) for r in state['packet_ranges'])
        if result._input_hash() != expected_input_hash or state['input_hash'] != expected_input_hash:
            raise ValueError('complete-history checkpoint differs from trusted input hash')
        return result
