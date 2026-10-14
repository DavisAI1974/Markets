"""Append-only complete evidence storage. No retention cap or aggregate rows."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import struct
import time
from types import MappingProxyType


class FrozenList(tuple):
    """Immutable owned list, retaining its original list type in exact encoding."""


def freeze(value):
    """Own and recursively freeze the supported evidence vocabulary."""
    if type(value) in (dict, MappingProxyType):
        if not all(type(k) is str for k in value):
            raise ValueError("evidence mapping keys must be strings")
        return MappingProxyType({k: freeze(v) for k, v in value.items()})
    if type(value) in (list, FrozenList):
        return FrozenList(freeze(v) for v in value)
    if type(value) is tuple:
        return tuple(freeze(v) for v in value)
    if value is None or type(value) in (bool, int, float, str, bytes):
        return value
    raise ValueError("unsupported evidence value; explicit representation required")

try:
    from .causal_packet import canonical_bytes
except ImportError:
    from causal_packet import canonical_bytes

SCHEMA = "C15_FULL_EVIDENCE_V1"
_HASH_PREFIX = SCHEMA.encode() + b"\0"
_ENCODING_MODE = os.environ.get('FRANKIE_EVIDENCE_ENCODING') or (
    'shadow' if os.environ.get('FRANKIE_EVIDENCE_SHADOW', '').lower() in ('1', 'true', 'on') else 'fast')
_ENCODING_COUNTS = dict(shadow_calls=0, shadow_bytes=0, legacy_seconds=0.0, candidate_seconds=0.0,
                        prepacked_legacy_calls=0, mismatches=0)


OBSERVATION_SENTINEL = '@@C15-OBSERVATION-SPLICE-9c1f@@'   # the placeholder the compact writer replaces with the observation's bytes


class SerializedObservation:
    """The observation of one closed group as its canonical bytes (the compact path composes them incrementally, the
    writer splices them into the APPLIED body). Not a mapping on purpose: a reader that wants the mapping calls
    materialize(), which decodes THESE bytes, never the live book, so it is the snapshot at that record whenever it
    is read."""
    __slots__ = ('canonical',)

    def __init__(self, canonical):
        if type(canonical) is not bytes or not canonical:
            raise ValueError('canonical observation bytes required')
        self.canonical = canonical

    def materialize(self):
        return unpack(json.loads(self.canonical))

    def __eq__(self, other):
        return type(other) is SerializedObservation and other.canonical == self.canonical

    def __repr__(self):
        return f'SerializedObservation({len(self.canonical)} bytes)'


class PrePacked(dict):
    """A mapping whose tagged tree is already built (the builder's observation, whose orders' and levels' subtrees are
    reused across closed groups while their fields are unchanged; Greg, 2026-09-22). It IS the mapping for every other
    reader; pack() alone reads `tree`, which the producer guarantees equals pack(dict(self)) node for node, so the
    canonical bytes and the digest are those of the plain mapping."""
    __slots__ = ('tree',)


def pack(value, _prepacked=None):
    """Tag every node so exact floats/bytes cannot collide with user mappings.

    canonical_bytes remains the hash authority. IEEE-754 bytes avoid its
    numeric quantization, preserving even NaN payload/sign bits.

    Same output as the original recursive form for every accepted value and the
    same refusal for every other; the branches are ordered by measured frequency
    (int and str are most nodes of a journal payload) and the mapping walk builds
    its items in the one pass that checks its keys.
    """
    kind = type(value)
    if kind is int:
        return ["int", value]
    if kind is str:
        return ["str", value]
    if value is None:
        return ["null"]
    if kind is bool:
        return ["bool", value]
    if kind is float:
        return ["float64", struct.pack(">d", value).hex()]
    if kind is bytes:
        return ["bytes", value.hex()]
    if kind is list or kind is FrozenList:
        return ["list", [pack(v, _prepacked) for v in value]]
    if kind is tuple:
        return ["tuple", [pack(v, _prepacked) for v in value]]
    if kind is dict or kind is MappingProxyType:
        items = []
        for key, val in value.items():
            if type(key) is not str:
                raise ValueError("evidence must use explicit mappings, sequences, bytes and primitive values")
            items.append([key, pack(val, _prepacked)])
        return ["dict", items]
    if kind is PrePacked:
        if _prepacked is not None:
            _prepacked[0] = True
        return value.tree
    raise ValueError("evidence must use explicit mappings, sequences, bytes and primitive values")


def unpack(value):
    kind = value[0]
    if kind == "null":
        return None
    if kind == "float64":
        return struct.unpack(">d", bytes.fromhex(value[1]))[0]
    if kind == "bytes":
        return bytes.fromhex(value[1])
    if kind == "dict":
        return {key: unpack(val) for key, val in value[1]}
    if kind in ("list", "tuple"):
        result = [unpack(v) for v in value[1]]
        return tuple(result) if kind == "tuple" else result
    if kind in ("bool", "int", "str"):
        return value[1]
    raise ValueError("unknown evidence value tag")


def encoding_report(before=None):
    """Process-local instrumentation, or its delta since a supplied snapshot.

    Forked owners take their own starting snapshot so inherited parent counts
    are not reported again. Counters time encoding only, excluding the shared
    pack pass; they never affect scientific content or hashes.
    """
    values = dict(_ENCODING_COUNTS)
    if before is not None:
        values = {key: value - before.get(key, 0) for key, value in values.items()}
    return dict(mode=_ENCODING_MODE, **values)


def evidence_bytes(payload, *, mode=None, shadow=None):
    """The existing exact evidence encoding, without copying an already tagged tree.

    pack's ordinary branches emit only lists and exact strings, integers and
    booleans. The packet canonicalizer is therefore the identity on that tree.
    Mapping entries stay in insertion order: they are a LIST of pairs here, not
    a JSON object. PrePacked can supply an arbitrary tree, so it retains the
    original canonicalizer (including its float/numpy handling).

    FRANKIE_EVIDENCE_ENCODING=legacy|shadow|fast selects the implementation;
    fast is the default. FRANKIE_EVIDENCE_SHADOW=on is a compatibility
    spelling for shadow. Shadow compares both and returns the legacy bytes.
    No scientific input, persisted byte or digest includes the mode.
    """
    selected = mode if mode is not None else _ENCODING_MODE
    if shadow is not None:
        if mode is not None:
            raise ValueError('choose encoding mode or shadow, not both')
        selected = 'shadow' if shadow else 'fast'
    if selected not in ('legacy', 'shadow', 'fast'):
        raise ValueError('evidence encoding must be legacy, shadow or fast')
    prepacked = [False]
    tree = pack(payload, prepacked)
    if selected == 'legacy':
        return canonical_bytes(tree)
    if prepacked[0]:
        _ENCODING_COUNTS['prepacked_legacy_calls'] += 1
        return canonical_bytes(tree)
    began = time.perf_counter() if selected == 'shadow' else None
    encoded = json.dumps(tree, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('utf-8')
    if selected == 'shadow':
        candidate_seconds = time.perf_counter() - began
        began = time.perf_counter()
        legacy = canonical_bytes(tree)
        legacy_seconds = time.perf_counter() - began
        _ENCODING_COUNTS['shadow_calls'] += 1
        _ENCODING_COUNTS['shadow_bytes'] += len(encoded)
        _ENCODING_COUNTS['candidate_seconds'] += candidate_seconds
        _ENCODING_COUNTS['legacy_seconds'] += legacy_seconds
        if encoded != legacy:
            _ENCODING_COUNTS['mismatches'] += 1
            raise ValueError('fast evidence encoding differs from the original canonical bytes')
        return legacy
    return encoded


def evidence_hash_bytes(encoded):
    """Hash bytes already produced by evidence_bytes; callers own their scope."""
    if type(encoded) is not bytes:
        raise TypeError('encoded evidence must be bytes')
    digest = hashlib.sha256(_HASH_PREFIX)
    digest.update(encoded)
    return digest.hexdigest()


def evidence_hash(payload, *, mode=None, shadow=None):
    return evidence_hash_bytes(evidence_bytes(payload, mode=mode, shadow=shadow))


class EvidenceJournal:
    """Single writer; every append commits. Readers stream every stored entry.

    Physical storage exhaustion raises an error, never evicts history. This
    database and its trusted checkpoint must travel together on restart.
    """

    def __init__(self, path, *, create=False):
        self.path = Path(path)
        if create:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("xb"):
                pass
        elif not self.path.is_file():
            raise ValueError("evidence journal is missing")
        self.connection = sqlite3.connect(self.path)
        self.connection.execute("PRAGMA synchronous=FULL")
        if create:
            self.connection.execute("CREATE TABLE entries (ordinal INTEGER PRIMARY KEY, kind TEXT NOT NULL, body BLOB NOT NULL, digest TEXT NOT NULL)")
            for operation in ("UPDATE", "DELETE"):
                self.connection.execute(f"CREATE TRIGGER forbid_{operation.lower()} BEFORE {operation} ON entries BEGIN SELECT RAISE(ABORT, 'evidence is append only'); END")
            self.connection.commit()
        row = self.connection.execute("SELECT ordinal, digest FROM entries ORDER BY ordinal DESC LIMIT 1").fetchone()
        self.count, self.head_hash = (row[0] + 1, row[1]) if row else (0, evidence_hash(dict(schema=SCHEMA)))

    def append(self, kind, payload):
        if type(kind) is not str or not kind:
            raise ValueError("entry kind required")
        envelope = dict(schema=SCHEMA, ordinal=self.count, previous_hash=self.head_hash,
                        kind=kind, payload=payload)
        body = evidence_bytes(envelope)
        digest = evidence_hash_bytes(body)
        with self.connection:
            self.connection.execute("INSERT INTO entries VALUES (?, ?, ?, ?)",
                                    (self.count, kind, body, digest))
        self.count += 1
        self.head_hash = digest
        return digest

    def entries(self):
        """Verify and yield all history in order, with no default result limit."""
        previous, count = evidence_hash(dict(schema=SCHEMA)), 0
        for ordinal, kind, body, digest in self.connection.execute(
                "SELECT ordinal, kind, body, digest FROM entries ORDER BY ordinal"):
            envelope = unpack(json.loads(body))
            encoded = evidence_bytes(envelope)
            if (body != encoded
                    or ordinal != count or envelope["ordinal"] != ordinal
                    or envelope["schema"] != SCHEMA or envelope["kind"] != kind
                    or envelope["previous_hash"] != previous
                    or evidence_hash_bytes(encoded) != digest):
                raise ValueError("evidence journal continuity or hash mismatch")
            previous, count = digest, count + 1
            yield envelope
        if count != self.count or previous != self.head_hash:
            raise ValueError("evidence journal changed during iteration")

    def verify(self, *, count, head_hash):
        for _ in self.entries():
            pass
        if (self.count, self.head_hash) != (count, head_hash):
            raise ValueError("journal differs from checkpoint; existing evidence was retained")

    def close(self):
        self.connection.close()
