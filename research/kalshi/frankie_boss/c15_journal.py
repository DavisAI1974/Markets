"""Append-only complete evidence storage. No retention cap or aggregate rows."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import struct
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


def pack(value):
    """Tag every node so exact floats/bytes cannot collide with user mappings.

    canonical_bytes remains the hash authority. IEEE-754 bytes avoid its
    numeric quantization, preserving even NaN payload/sign bits.
    """
    if value is None:
        return ["null"]
    if type(value) is bool:
        return ["bool", value]
    if type(value) is int:
        return ["int", value]
    if type(value) is float:
        return ["float64", struct.pack(">d", value).hex()]
    if type(value) is str:
        return ["str", value]
    if type(value) is bytes:
        return ["bytes", value.hex()]
    if type(value) in (list, tuple, FrozenList):
        return ["tuple" if type(value) is tuple else "list", [pack(v) for v in value]]
    if type(value) in (dict, MappingProxyType) and all(type(k) is str for k in value):
        return ["dict", [[key, pack(val)] for key, val in value.items()]]
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


def evidence_hash(payload):
    return hashlib.sha256(SCHEMA.encode() + b"\0" + canonical_bytes(pack(payload))).hexdigest()


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
        body = canonical_bytes(pack(envelope))
        digest = evidence_hash(envelope)
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
            if (body != canonical_bytes(pack(envelope))
                    or ordinal != count or envelope["ordinal"] != ordinal
                    or envelope["schema"] != SCHEMA or envelope["kind"] != kind
                    or envelope["previous_hash"] != previous
                    or evidence_hash(envelope) != digest):
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
