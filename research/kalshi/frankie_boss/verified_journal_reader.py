"""Read-only, bounded-memory verified reader for existing C15 evidence journals.

Separate implementation identity from c15_journal.EvidenceJournal. This module never
writes, never trusts the database tail, and opens the file read-only. Expensive per-row
JSON/decode/canonical-hash validation can be performed by an explicit bounded worker pool;
ordered continuity and the final trusted checkpoint remain verified by the parent process.

Standalone use is deliberately single-worker. Production chooses journal verification
parallelism independently through FRANKIE_JOURNAL_VERIFY_WORKERS. Rows are yielded in
original ordinal order; no row is dropped, reordered, averaged, normalized, or accepted
without the same structural/hash checks. On Linux the worker pool uses forkserver so it
does not fork an already-initialized PyTorch/OpenMP parent.
"""
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import multiprocessing
import os
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
DEFAULT_WORKERS = 1
WORKER_ENV = "FRANKIE_JOURNAL_VERIFY_WORKERS"


def canonical_tagged_bytes(tree):
    """canonical_bytes() specialised to pack() output."""
    return json.dumps(tree, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def decode_tagged(node):
    """unpack() with structural validation such that pack(decode_tagged(node)) == node."""
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


def _worker_init():
    """Cap nested math pools inside verification workers only, never in the trainer."""
    for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ[name] = "1"


def _validate_row(row):
    """CPU-heavy row-local validation safe to run in a worker process."""
    ordinal, kind, body, digest = row
    if type(body) is not bytes:
        raise ValueError(_MISMATCH)
    tree = json.loads(body)
    envelope = decode_tagged(tree)
    if canonical_tagged_bytes(tree) != body:
        raise ValueError(_MISMATCH)
    if (type(envelope) is not dict or envelope.get("ordinal") != ordinal
            or envelope.get("schema") != SCHEMA or envelope.get("kind") != kind
            or hashlib.sha256(DIGEST_PREFIX + body).hexdigest() != digest):
        raise ValueError(_MISMATCH)
    return ordinal, envelope, digest


def _declared_workers(workers):
    if workers is None:
        raw = os.environ.get(WORKER_ENV, str(DEFAULT_WORKERS))
        try:
            workers = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{WORKER_ENV} must be an integer") from exc
    if type(workers) is not int or not 1 <= workers <= 256:
        raise ValueError("verified journal worker count must be between 1 and 256")
    return workers


def _worker_context():
    """Avoid forking a multithreaded PyTorch parent; Windows/macOS fall back safely."""
    methods = multiprocessing.get_all_start_methods()
    return multiprocessing.get_context("forkserver" if "forkserver" in methods else "spawn")


class VerifiedJournalReader:
    """Stream an existing evidence journal against an independently supplied checkpoint.

    count and head_hash are the supplied expectations, verified against the stored tail
    at open and again after every complete iteration. Validation may be parallel but
    output order and hash-chain continuity remain serial and exact. At most two bounded
    source batches (each workers*4 rows) are active so batch N+1 can validate while the
    caller consumes N without unbounded prefetch.
    """

    def __init__(self, path, *, expected_count, expected_head_hash, workers=None):
        if type(expected_count) is not int or expected_count < 0:
            raise ValueError("independently supplied journal count required")
        if (type(expected_head_hash) is not str or len(expected_head_hash) != 64
                or not _HEX.issuperset(expected_head_hash)):
            raise ValueError("independently supplied journal head hash required")
        self.path = Path(path)
        if self.path.is_symlink() or not self.path.is_file():
            raise ValueError("evidence journal is missing")
        self.workers = _declared_workers(workers)
        self.batch_rows = self.workers * 4
        self._connection = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)
        self._executor = None
        try:
            self._connection.execute("PRAGMA query_only=1")
            if self._stored_tail() != (expected_count, expected_head_hash):
                raise ValueError("journal differs from checkpoint; existing evidence was retained")
            if self.workers > 1:
                self._executor = ProcessPoolExecutor(max_workers=self.workers,
                    mp_context=_worker_context(), initializer=_worker_init)
        except BaseException:
            self._connection.close()
            raise
        self.count, self.head_hash = expected_count, expected_head_hash

    def append(self, *args, **kwargs):
        raise PermissionError("verified journal reader is read-only; appends belong to EvidenceJournal")

    def _validated(self, rows):
        if self._executor is None:
            return map(_validate_row, rows)
        return self._executor.map(_validate_row, rows,
            chunksize=max(1, len(rows)//self.workers))

    def entries(self):
        """Verify/yield history in order with one bounded validation batch prefetched."""
        previous, count = GENESIS_HASH, 0
        cursor = self._connection.execute(
            "SELECT ordinal, kind, body, digest FROM entries ORDER BY ordinal")
        rows = cursor.fetchmany(self.batch_rows)
        validated = self._validated(rows) if rows else None
        while rows:
            next_rows = cursor.fetchmany(self.batch_rows)
            # executor.map submits this batch immediately; its results are not observed
            # until the current ordered batch has been consumed.
            next_validated = self._validated(next_rows) if next_rows else None
            for ordinal, envelope, digest in validated:
                if ordinal != count or envelope.get("previous_hash") != previous:
                    raise ValueError(_MISMATCH)
                previous, count = digest, count + 1
                yield envelope
            rows, validated = next_rows, next_validated
        if count != self.count or previous != self.head_hash or self._stored_tail() != (self.count, self.head_hash):
            raise ValueError("evidence journal changed during iteration")

    def _stored_tail(self):
        row = self._connection.execute(
            "SELECT ordinal, digest FROM entries ORDER BY ordinal DESC LIMIT 1").fetchone()
        return (row[0] + 1, row[1]) if row else (0, GENESIS_HASH)

    def verify(self, *, count, head_hash):
        for _ in self.entries():
            pass
        if (self.count, self.head_hash) != (count, head_hash):
            raise ValueError("journal differs from checkpoint; existing evidence was retained")

    def close(self):
        if self._executor is not None:
            self._executor.shutdown(wait=True, cancel_futures=True)
            self._executor = None
        self._connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
