"""Read-only, bounded-memory verified reader for existing C15 evidence journals.

Separate implementation identity from c15_journal.EvidenceJournal. This module never
writes, never trusts the database tail, opens the file read-only, and is not wired into
any runtime path; integration is documented in SPEC-verified-journal-reader.md.

Per row it performs one JSON parse, one validating decode (unpack with structural checks
guaranteeing pack(decoded) == tagged tree exactly), one canonical serialization of the
tagged tree, and one SHA-256 over the validated bytes under the existing SCHEMA + NUL
prefix. EvidenceJournal.entries() performs parse, unpack, pack, serialize, pack and
serialize again per row; this reader accepts and rejects the same rows.
"""
import hashlib
import json
from pathlib import Path
import sqlite3
import struct

try:
    from .c15_journal import SCHEMA, evidence_hash
except ImportError:
    from c15_journal import SCHEMA, evidence_hash

GENESIS_HASH = evidence_hash(dict(schema=SCHEMA))
DIGEST_PREFIX = SCHEMA.encode() + b"\0"
_HEX = frozenset("0123456789abcdef")
_MALFORMED = "malformed evidence value tag"
_MISMATCH = "evidence journal continuity or hash mismatch"


def canonical_tagged_bytes(tree):
    """canonical_bytes() specialised to pack() output.

    pack() emits only lists, str, bool and int nodes. causal_packet._canon is the identity
    on every one of those (bool before int, str and int unchanged, lists rebuilt in order)
    and sort_keys has nothing to sort, so this is byte-identical to canonical_bytes(tree).
    tests/test_verified_journal_reader.py demonstrates the equivalence differentially.
    """
    return json.dumps(tree, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def decode_tagged(node):
    """unpack() with structural validation such that pack(decode_tagged(node)) == node.

    Every shape pack() cannot produce is rejected: wrong tag arity, a bool under "int",
    a float or bool under "int", non-lowercase or odd-length hex, a float64 whose bits do
    not round-trip, non-string or duplicate mapping keys, and unknown tags. The original
    reader rejects the same rows through repack inequality or an unpack exception.
    """
    if type(node) is not list or not node:
        raise ValueError(_MALFORMED)
    tag = node[0]
    if tag == "null":
        if len(node) != 1:
            raise ValueError(_MALFORMED)
        return None
    if len(node) != 2:
        raise ValueError(_MALFORMED)
    value = node[1]
    if tag == "str":
        if type(value) is not str:
            raise ValueError(_MALFORMED)
        return value
    if tag == "int":
        if type(value) is not int:
            raise ValueError(_MALFORMED)
        return value
    if tag == "bool":
        if type(value) is not bool:
            raise ValueError(_MALFORMED)
        return value
    if tag == "dict":
        if type(value) is not list:
            raise ValueError(_MALFORMED)
        result = {}
        for pair in value:
            if type(pair) is not list or len(pair) != 2 or type(pair[0]) is not str or pair[0] in result:
                raise ValueError(_MALFORMED)
            result[pair[0]] = decode_tagged(pair[1])
        return result
    if tag == "list" or tag == "tuple":
        if type(value) is not list:
            raise ValueError(_MALFORMED)
        items = [decode_tagged(item) for item in value]
        return tuple(items) if tag == "tuple" else items
    if tag == "float64":
        if type(value) is not str or len(value) != 16 or not _HEX.issuperset(value):
            raise ValueError(_MALFORMED)
        number = struct.unpack(">d", bytes.fromhex(value))[0]
        if struct.pack(">d", number).hex() != value:
            raise ValueError(_MALFORMED)
        return number
    if tag == "bytes":
        if type(value) is not str or len(value) % 2 or not _HEX.issuperset(value):
            raise ValueError(_MALFORMED)
        return bytes.fromhex(value)
    raise ValueError("unknown evidence value tag")


class VerifiedJournalReader:
    """Stream an existing evidence journal against an independently supplied checkpoint.

    count and head_hash are the supplied expectations, verified against the stored tail
    at open and again after every complete iteration. Rows are streamed one at a time;
    nothing is cached. The connection is opened read-only; append is refused.
    """

    def __init__(self, path, *, expected_count, expected_head_hash):
        if type(expected_count) is not int or expected_count < 0:
            raise ValueError("independently supplied journal count required")
        if (type(expected_head_hash) is not str or len(expected_head_hash) != 64
                or not _HEX.issuperset(expected_head_hash)):
            raise ValueError("independently supplied journal head hash required")
        self.path = Path(path)
        if self.path.is_symlink() or not self.path.is_file():
            raise ValueError("evidence journal is missing")
        self._connection = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            self._connection.execute("PRAGMA query_only=1")
            if self._stored_tail() != (expected_count, expected_head_hash):
                raise ValueError("journal differs from checkpoint; existing evidence was retained")
        except BaseException:
            self._connection.close()
            raise
        self.count, self.head_hash = expected_count, expected_head_hash

    def append(self, *args, **kwargs):
        raise PermissionError("verified journal reader is read-only; appends belong to EvidenceJournal")

    def entries(self):
        """Verify and yield all history in order, one validated row at a time."""
        previous, count = GENESIS_HASH, 0
        for ordinal, kind, body, digest in self._connection.execute(
                "SELECT ordinal, kind, body, digest FROM entries ORDER BY ordinal"):
            if type(body) is not bytes:
                raise ValueError(_MISMATCH)
            tree = json.loads(body)
            envelope = decode_tagged(tree)
            if canonical_tagged_bytes(tree) != body:  # validated before the bytes are hashed
                raise ValueError(_MISMATCH)
            if (type(envelope) is not dict or ordinal != count
                    or envelope.get("ordinal") != ordinal or envelope.get("schema") != SCHEMA
                    or envelope.get("kind") != kind or envelope.get("previous_hash") != previous
                    or hashlib.sha256(DIGEST_PREFIX + body).hexdigest() != digest):
                raise ValueError(_MISMATCH)
            previous, count = digest, count + 1
            yield envelope
        # The SELECT above has finished, so its read snapshot is released. Reread the stored
        # tail with a fresh statement: in WAL mode a concurrent append is invisible to the
        # iterated rows, and only the stored tail can reveal it.
        if count != self.count or previous != self.head_hash or self._stored_tail() != (self.count, self.head_hash):
            raise ValueError("evidence journal changed during iteration")

    def _stored_tail(self):
        row = self._connection.execute(
            "SELECT ordinal, digest FROM entries ORDER BY ordinal DESC LIMIT 1").fetchone()
        return (row[0] + 1, row[1]) if row else (0, GENESIS_HASH)

    def stored_tail(self):
        """(count, head) as stored on disk right now, through a FRESH read-only connection.

        The reader's own connection may sit inside a read snapshot; a fresh connection sees a
        second handle's append. This is the reader-side contract the prepared-context cache calls
        (every reader class provides it) instead of running SQL against the file itself.
        """
        connection = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            row = connection.execute(
                "SELECT ordinal, digest FROM entries ORDER BY ordinal DESC LIMIT 1").fetchone()
        finally:
            connection.close()
        return (row[0] + 1, row[1]) if row else (0, GENESIS_HASH)

    def verify(self, *, count, head_hash):
        for _ in self.entries():
            pass
        if (self.count, self.head_hash) != (count, head_hash):
            raise ValueError("journal differs from checkpoint; existing evidence was retained")

    def close(self):
        self._connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
