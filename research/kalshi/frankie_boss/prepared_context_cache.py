"""Prepare a native context once, then reuse the exact preparation inside one process.

The first-cutoff preparation (journal prefix scan, native encoding, inverse reconstruction,
teacher attachment) is expensive and today runs again for every native forecast and critic
request. This cache invokes ContextSessionRunner._prepare exactly once at creation, owns
detached copies of the full tuple (tokens, info, input_hash, teacher, rows) and hands out
independent copies while every identity it was prepared under still holds: cutoff, journal
path and trusted source checkpoint, scope, entity, context length, model weights/config,
teacher binding (which covers the normalizer), QSV identity and the current training
checkpoint. A changed identity is refused; nothing is ever recomputed silently.

No model forward, inference, training or service call happens here. Nothing is persisted
and nothing is loaded from a serialized request. Not wired into any module; Codex owns host
integration.
"""
import copy
from pathlib import Path
import threading

import torch

try:
    from .c15_journal import SCHEMA as JOURNAL_SCHEMA, evidence_hash, pack
except ImportError:
    from c15_journal import SCHEMA as JOURNAL_SCHEMA, evidence_hash, pack

SCHEMA = 'BOSS_PREPARED_CONTEXT_CACHE_V1'
_HEX = frozenset('0123456789abcdef')


def own(value):
    """Independent copy: detached tensor clones, fresh containers, deepcopy for other objects."""
    if isinstance(value, torch.Tensor):
        return value.detach().clone()
    if type(value) is dict:
        return {key: own(item) for key, item in value.items()}
    if type(value) is list:
        return [own(item) for item in value]
    if type(value) is tuple:
        return tuple(own(item) for item in value)
    if value is None or type(value) in (bool, int, float, str, bytes):
        return value
    return copy.deepcopy(value)


def _sha256(value, name):
    if type(value) is not str or len(value) != 64 or not _HEX.issuperset(value):
        raise ValueError(f'{name} must be a sha256 hex digest')
    return value


def _stored_tail(journal):
    """The stored tail, not the handle's cached attributes: a second handle's append is visible."""
    row = journal.connection.execute('SELECT ordinal, digest FROM entries ORDER BY ordinal DESC LIMIT 1').fetchone()
    return (row[0] + 1, row[1]) if row else (0, evidence_hash(dict(schema=JOURNAL_SCHEMA)))


class PreparedContextCache:
    """Holds one preparation; prepare() returns independent copies under unchanged identities."""

    def __init__(self, context, *, as_of, through_cursor, expected_source_checkpoint, expected_model_hash,
                 expected_teacher_binding, checkpoint_hash, current_checkpoint_hash):
        if type(as_of) is not int or type(through_cursor) is not int or through_cursor < 0:
            raise ValueError('exact integer cutoff required')
        if (type(expected_source_checkpoint) is not dict or set(expected_source_checkpoint) != {'count', 'head_hash'}
                or type(expected_source_checkpoint['count']) is not int or expected_source_checkpoint['count'] < 0):
            raise ValueError('trusted source checkpoint {count, head_hash} required')
        _sha256(expected_source_checkpoint['head_hash'], 'source head hash')
        _sha256(expected_model_hash, 'expected model hash')
        _sha256(checkpoint_hash, 'training checkpoint hash')
        if expected_teacher_binding is not None:
            _sha256(expected_teacher_binding, 'teacher binding')
        if not callable(current_checkpoint_hash):
            raise ValueError('current_checkpoint_hash must be callable')
        self._context = context
        self._cutoff = (as_of, through_cursor)
        self._source = dict(expected_source_checkpoint)
        self._model_hash = expected_model_hash
        self._teacher_binding = expected_teacher_binding
        self._checkpoint_hash = checkpoint_hash
        self._current_checkpoint_hash = current_checkpoint_hash
        self._lock = threading.Lock()
        self._closed = False
        # Cheap identity checks first: a mismatch must not cost a full preparation.
        self._identity = self._bindings()
        self._assert_identity()
        tokens, info, input_hash, teacher, rows = context._prepare(as_of, through_cursor)
        if (type(tokens) is not dict or type(info) is not dict or type(rows) is not list
                or not all(isinstance(v, torch.Tensor) for v in tokens.values())):
            raise ValueError('unexpected native preparation shape')
        _sha256(input_hash, 'prepared input hash')
        if (info.get('as_of') != as_of or info.get('t_ctx') != context.t_ctx
                or (teacher is None) != (expected_teacher_binding is None)
                or info.get('teacher_binding') != expected_teacher_binding):
            raise ValueError('preparation does not carry the bound cutoff, context length or teacher')
        self._prepared = dict(tokens=own(tokens), info=own(info), input_hash=input_hash,
                              teacher=own(teacher), rows=own(rows))
        self._receipt = dict(schema=SCHEMA, bindings=own(self._identity),
            bindings_hash=evidence_hash(self._identity), input_hash=input_hash,
            source_prefix_hash=info['source_prefix_hash'], journal_prefix_hash=info['journal_prefix_hash'],
            journal_entries=info['journal_entries'], consumed_rows=info['consumed_rows'],
            context_cursors=tuple(info['context_cursors']), teacher_hash=info['teacher_hash'],
            preparations_performed=1, model_forward_performed=False, inference_performed=False,
            persisted=False)
        # The preparation itself may have taken long; re-verify the identities it ran under.
        self._assert_identity()

    def _bindings(self):
        context, builder = self._context, self._context.builder
        journal = builder.journal
        teacher = context.teacher
        return dict(as_of=self._cutoff[0], through_cursor=self._cutoff[1],
            journal_path=str(Path(journal.path).resolve()),
            source_checkpoint=dict(self._source),
            scope_kind=builder.scope.kind.value, scope_hash=builder.scope.genesis_hash(),
            scope_id=builder.scope.scope_id, next_cursor=builder.chain.next_cursor,
            entity=tuple(context.entity), t_ctx=context.t_ctx,
            model_hash=self._model_hash, teacher_binding=self._teacher_binding,
            teacher_class=None if teacher is None else type(teacher).__module__ + '.' + type(teacher).__qualname__,
            qsv_hash=context.expected_qsv_hash, checkpoint_hash=self._checkpoint_hash)

    def _assert_identity(self):
        context, builder = self._context, self._context.builder
        if self._bindings() != self._identity:
            raise ValueError('context identity differs from the prepared bindings')
        if builder._failed:
            raise ValueError('builder stopped after failure; prepared context is not reusable')
        if self._cutoff[1] >= builder.chain.next_cursor:
            raise ValueError('cutoff cursor outside applied journal')
        # Source: the stored tail (no decode, no scan) must still equal the trusted checkpoint.
        if _stored_tail(builder.journal) != (self._source['count'], self._source['head_hash']):
            raise ValueError('journal differs from the trusted source checkpoint; prepared context refused')
        if (builder.journal.count, builder.journal.head_hash) != (self._source['count'], self._source['head_hash']):
            raise ValueError('journal handle differs from the trusted source checkpoint')
        if context._model_hash() != self._model_hash:
            raise ValueError('native model differs from the prepared model identity')
        teacher = context.teacher
        if (teacher is None) != (self._teacher_binding is None) or (
                teacher is not None and teacher.binding != self._teacher_binding):
            raise ValueError('teacher binding or normalizer differs from the prepared identity')
        if context.qsv is not None and context.qsv.digest != context.expected_qsv_hash:
            raise ValueError('QSV artifact differs from its trusted identity')
        current = self._current_checkpoint_hash()
        if current != self._checkpoint_hash:
            raise ValueError('training checkpoint advanced; prepared context belongs to an earlier checkpoint')

    def _open(self):
        if self._closed:
            raise ValueError('prepared context cache is closed')

    @property
    def receipt(self):
        with self._lock:
            self._open()
            return own(self._receipt)

    def prepare(self, as_of, through_cursor):
        """Return independent copies of (tokens, info, input_hash, teacher, rows) for the bound cutoff."""
        with self._lock:
            self._open()
            if (as_of, through_cursor) != self._cutoff:
                raise ValueError('prepared context is bound to a different cutoff; prepare a new cache')
            self._assert_identity()
            prepared = self._prepared
            return (own(prepared['tokens']), own(prepared['info']), prepared['input_hash'],
                    own(prepared['teacher']), own(prepared['rows']))

    def close(self):
        with self._lock:
            self._closed = True
            self._prepared = None
            self._receipt = None
            self._context = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def prepare_context_cache(context, *, as_of, through_cursor, expected_source_checkpoint, expected_model_hash,
                          expected_teacher_binding, checkpoint_hash, current_checkpoint_hash):
    """Prepare once and return the cache; a failed preparation raises and caches nothing."""
    return PreparedContextCache(context, as_of=as_of, through_cursor=through_cursor,
        expected_source_checkpoint=expected_source_checkpoint, expected_model_hash=expected_model_hash,
        expected_teacher_binding=expected_teacher_binding, checkpoint_hash=checkpoint_hash,
        current_checkpoint_hash=current_checkpoint_hash)


def same_preparation(left, right):
    """Exact structural equality of two prepared tuples (tensors by dtype, shape and bits)."""
    if isinstance(left, torch.Tensor) or isinstance(right, torch.Tensor):
        return (isinstance(left, torch.Tensor) and isinstance(right, torch.Tensor)
                and left.dtype == right.dtype and left.shape == right.shape and torch.equal(left.cpu(), right.cpu()))
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return list(left) == list(right) and all(same_preparation(left[k], right[k]) for k in left)
    if type(left) in (list, tuple):
        return len(left) == len(right) and all(same_preparation(a, b) for a, b in zip(left, right))
    if hasattr(left, '__dict__') and not isinstance(left, type):
        return same_preparation(vars(left), vars(right))
    if hasattr(left, '__slots__'):
        return all(same_preparation(getattr(left, s, None), getattr(right, s, None)) for s in left.__slots__)
    return pack(left) == pack(right) if type(left) in (float, bytes) else left == right
