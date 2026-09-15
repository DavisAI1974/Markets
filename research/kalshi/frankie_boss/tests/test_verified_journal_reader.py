"""Differential and corruption evidence for VerifiedJournalReader against EvidenceJournal.

Every journal here is a fresh temporary file written by the existing writer; no retained
database is opened. No suite reruns, no model, source, cloud or principal action.
"""
import hashlib
import json
import math
import struct

import pytest

from c15_journal import EvidenceJournal, SCHEMA, canonical_bytes, evidence_hash, pack
from verified_journal_reader import (GENESIS_HASH, VerifiedJournalReader, canonical_tagged_bytes,
                                     decode_tagged)


def bits(hex16):
    return struct.unpack(">d", bytes.fromhex(hex16))[0]


VALUES = [
    None, True, False, 0, 1, -1, 2**63, 2**80, 10**100, -(10**100),
    0.0, -0.0, 1.0, -1.5, 1.1234567890123457, 5e-324, 1.7976931348623157e308, float("inf"), float("-inf"),
    bits("7ff8000000000001"), bits("fff8000000000001"), bits("7ff0000000000001"),
    "", "plain", "é中\U0001f600", "quote\"back\\slash\n\t\x00\x7f", "\ud83d",
    b"", b"\x00\xff", bytes(range(256)),
    [], (), [1], (1,), [1, (2, [3, ()])], ([],),
    {}, {"a": 1}, {"z": {"y": {"x": (1, [2], b"\x01")}}, "": None},
    [True, 1, 1.0, "1", b"1"], {"b": [1, (2.0, b"x")], "a": "é", "n": -0.0, "big": 2**80},
]


def build(tmp_path, values=VALUES, name="journal.sqlite"):
    journal = EvidenceJournal(tmp_path / name, create=True)
    for index, value in enumerate(values):
        journal.append("KIND-%d" % (index % 3), dict(value=value, index=index))
    journal.append("ALL", dict(values=values, nested={"t": tuple(values), "l": list(values)}))
    return journal


def reader_for(journal):
    return VerifiedJournalReader(journal.path, expected_count=journal.count, expected_head_hash=journal.head_hash)


def same(left, right):
    """Exact-type structural equality including float bit patterns."""
    if type(left) is not type(right):
        return False
    if type(left) is float:
        return struct.pack(">d", left) == struct.pack(">d", right)
    if type(left) is dict:
        return list(left) == list(right) and all(same(left[k], right[k]) for k in left)
    if type(left) in (list, tuple):
        return len(left) == len(right) and all(same(a, b) for a, b in zip(left, right))
    return left == right


def test_reader_yields_exactly_the_original_entries_with_exact_types(tmp_path):
    journal = build(tmp_path)
    reader = reader_for(journal)
    original, fast = list(journal.entries()), list(reader.entries())
    assert len(original) == len(fast) == len(VALUES) + 1
    assert all(same(a, b) for a, b in zip(original, fast))
    negative_zero = next(i for i, v in enumerate(VALUES) if type(v) is float and v == 0 and math.copysign(1, v) < 0)
    assert math.copysign(1, fast[negative_zero]["payload"]["value"]) == -1
    assert reader.count == journal.count and reader.head_hash == journal.head_hash
    reader.verify(count=journal.count, head_hash=journal.head_hash)
    reader.close(); journal.close()


def test_specialised_serializer_is_byte_identical_to_canonical_bytes(tmp_path):
    journal = build(tmp_path)
    for body, digest in journal.connection.execute("SELECT body, digest FROM entries ORDER BY ordinal"):
        tree = json.loads(body)
        assert canonical_tagged_bytes(tree) == canonical_bytes(tree) == body
        envelope = decode_tagged(tree)
        assert pack(envelope) == tree
        assert canonical_bytes(pack(envelope)) == body
        assert hashlib.sha256(SCHEMA.encode() + b"\0" + body).hexdigest() == evidence_hash(envelope) == digest
    for value in VALUES:
        tree = pack(value)
        assert canonical_tagged_bytes(tree) == canonical_bytes(tree)
        assert same(decode_tagged(tree), value)
    journal.close()


def test_expected_count_and_head_hash_are_required_and_checked_at_open(tmp_path):
    journal = build(tmp_path)
    path, count, head = journal.path, journal.count, journal.head_hash
    for bad in (dict(expected_count=count - 1, expected_head_hash=head),
                dict(expected_count=count, expected_head_hash="0" * 64),
                dict(expected_count=count + 1, expected_head_hash=head)):
        with pytest.raises(ValueError, match="differs from checkpoint"):
            VerifiedJournalReader(path, **bad)
    for bad in (dict(expected_count="3", expected_head_hash=head), dict(expected_count=-1, expected_head_hash=head),
                dict(expected_count=count, expected_head_hash=head.upper()),
                dict(expected_count=count, expected_head_hash=head[:-1])):
        with pytest.raises(ValueError, match="independently supplied"):
            VerifiedJournalReader(path, **bad)
    with pytest.raises(TypeError):
        VerifiedJournalReader(path)
    empty = EvidenceJournal(tmp_path / "empty.sqlite", create=True)
    assert empty.head_hash == GENESIS_HASH
    reader = VerifiedJournalReader(empty.path, expected_count=0, expected_head_hash=GENESIS_HASH)
    assert list(reader.entries()) == []
    reader.close()
    with pytest.raises(ValueError, match="differs from checkpoint"):
        VerifiedJournalReader(empty.path, expected_count=0, expected_head_hash="0" * 64)
    with pytest.raises(ValueError, match="missing"):
        VerifiedJournalReader(tmp_path / "absent.sqlite", expected_count=0, expected_head_hash=GENESIS_HASH)
    empty.close(); journal.close()


def test_reader_is_read_only_and_leaves_the_file_untouched(tmp_path):
    journal = build(tmp_path)
    journal.close()
    before = hashlib.sha256(journal.path.read_bytes()).hexdigest()
    reader = VerifiedJournalReader(journal.path, expected_count=journal.count, expected_head_hash=journal.head_hash)
    with pytest.raises(PermissionError, match="read-only"):
        reader.append("KIND", dict(value=1))
    with pytest.raises(sqlite3_error()):
        reader._connection.execute("INSERT INTO entries VALUES (99, 'x', X'00', 'y')")
    with pytest.raises(sqlite3_error()):
        reader._connection.execute("DROP TRIGGER forbid_update")
    assert len(list(reader.entries())) == len(VALUES) + 1
    reader.close()
    assert hashlib.sha256(journal.path.read_bytes()).hexdigest() == before


def sqlite3_error():
    import sqlite3
    return sqlite3.OperationalError


def test_entries_stream_row_by_row_and_stop_at_the_first_bad_row(tmp_path):
    journal = build(tmp_path, values=[1, 2, 3, 4])
    corrupt(journal, "UPDATE entries SET kind='WRONG' WHERE ordinal=2")
    reader = reader_for(journal)
    stream = reader.entries()
    assert next(stream)["payload"]["value"] == 1
    assert next(stream)["payload"]["value"] == 2
    with pytest.raises(ValueError, match="continuity or hash mismatch"):
        next(stream)
    reader.close(); journal.close()


def corrupt(journal, statement, parameters=()):
    """Simulate external file modification, never a supported journal write."""
    for operation in ("update", "delete"):
        journal.connection.execute("DROP TRIGGER IF EXISTS forbid_" + operation)
    journal.connection.execute(statement, parameters)
    journal.connection.commit()


def row(journal, ordinal):
    return journal.connection.execute("SELECT body, digest FROM entries WHERE ordinal=?", (ordinal,)).fetchone()


def rewrite(journal, ordinal, tree, *, digest=None):
    body = canonical_bytes(tree)
    digest = hashlib.sha256(SCHEMA.encode() + b"\0" + body).hexdigest() if digest is None else digest
    corrupt(journal, "UPDATE entries SET body=?, digest=? WHERE ordinal=?", (body, digest, ordinal))


def retag(tree, path, replacement):
    node = tree
    for step in path[:-1]:
        node = node[step]
    node[path[-1]] = replacement
    return tree


def tagged(journal, ordinal):
    return json.loads(row(journal, ordinal)[0])


CORRUPTIONS = {
    "altered canonical bytes, same JSON": lambda j: corrupt(j, "UPDATE entries SET body=? WHERE ordinal=1",
        (json.dumps(json.loads(row(j, 1)[0]), indent=2).encode(),)),
    "digest column altered": lambda j: corrupt(j, "UPDATE entries SET digest=? WHERE ordinal=1", ("0" * 64,)),
    "ordinal gap": lambda j: corrupt(j, "UPDATE entries SET ordinal=7 WHERE ordinal=1"),
    "wrong kind column": lambda j: corrupt(j, "UPDATE entries SET kind='OTHER' WHERE ordinal=1"),
    "broken previous hash": lambda j: rewrite(j, 1, retag(tagged(j, 1), [1, 2, 1, 1], "1" * 64)),
    "changed body, stale digest": lambda j: rewrite(j, 1, retag(tagged(j, 1), [1, 4, 1, 1, 0, 1, 1], 999),
                                                   digest=row(j, 1)[1]),
    "changed body, recomputed digest breaks chain": lambda j: rewrite(j, 1, retag(tagged(j, 1), [1, 4, 1, 1, 0, 1, 1], 999)),
    "deleted middle row": lambda j: corrupt(j, "DELETE FROM entries WHERE ordinal=1"),
    "body stored as text": lambda j: corrupt(j, "UPDATE entries SET body=CAST(body AS TEXT) WHERE ordinal=1"),
    "unknown tag": lambda j: rewrite(j, 1, retag(tagged(j, 1), [1, 4, 1, 1, 0, 1], ["nope", 1])),
    "bool under int": lambda j: rewrite(j, 1, retag(tagged(j, 1), [1, 4, 1, 1, 0, 1], ["int", True])),
    "float under int": lambda j: rewrite(j, 1, retag(tagged(j, 1), [1, 4, 1, 1, 0, 1], ["int", 1.5])),
    "int under bool": lambda j: rewrite(j, 1, retag(tagged(j, 1), [1, 4, 1, 1, 0, 1], ["bool", 1])),
    "uppercase float hex": lambda j: rewrite(j, 1, retag(tagged(j, 1), [1, 4, 1, 1, 0, 1], ["float64", "3FF0000000000000"])),
    "short float hex": lambda j: rewrite(j, 1, retag(tagged(j, 1), [1, 4, 1, 1, 0, 1], ["float64", "3ff00"])),
    "odd bytes hex": lambda j: rewrite(j, 1, retag(tagged(j, 1), [1, 4, 1, 1, 0, 1], ["bytes", "abc"])),
    "uppercase bytes hex": lambda j: rewrite(j, 1, retag(tagged(j, 1), [1, 4, 1, 1, 0, 1], ["bytes", "AB"])),
    "null with payload": lambda j: rewrite(j, 1, retag(tagged(j, 1), [1, 4, 1, 1, 0, 1], ["null", 0])),
    "tag arity": lambda j: rewrite(j, 1, retag(tagged(j, 1), [1, 4, 1, 1, 0, 1], ["int", 1, 2])),
    "empty node": lambda j: rewrite(j, 1, retag(tagged(j, 1), [1, 4, 1, 1, 0, 1], [])),
    "json object node": lambda j: rewrite(j, 1, retag(tagged(j, 1), [1, 4, 1, 1, 0, 1], {"int": 1})),
    "duplicate mapping keys": lambda j: rewrite(j, 1, retag(tagged(j, 1), [1, 4, 1],
        ["dict", [["value", ["int", 1]], ["value", ["int", 2]], ["index", ["int", 1]]]])),
    "non-string mapping key": lambda j: rewrite(j, 1, retag(tagged(j, 1), [1, 4, 1], ["dict", [[1, ["int", 1]]]])),
    "list under tuple tag": lambda j: rewrite(j, 1, retag(tagged(j, 1), [1, 4, 1, 1, 0, 1], ["tuple", ["int", 1]])),
    "envelope not a mapping": lambda j: rewrite(j, 1, ["list", [["int", 1]]]),
    "envelope missing kind": lambda j: rewrite(j, 1, ["dict", [p for p in tagged(j, 1)[1] if p[0] != "kind"]]),
    "envelope schema changed": lambda j: rewrite(j, 1, retag(tagged(j, 1), [1, 0, 1, 1], "OTHER_SCHEMA")),
}


@pytest.mark.parametrize("name", list(CORRUPTIONS))
def test_every_corruption_rejected_by_both_readers(tmp_path, name):
    journal = build(tmp_path, values=[1, 2, 3])
    count, head = journal.count, journal.head_hash
    assert tagged(journal, 1)[1][4][1][1][0][1] == ["int", 2]  # payload.value of ordinal 1, the retag anchor
    CORRUPTIONS[name](journal)
    with pytest.raises((ValueError, KeyError, TypeError, IndexError)):
        list(journal.entries())
    try:
        reader = VerifiedJournalReader(journal.path, expected_count=count, expected_head_hash=head)
    except ValueError as refused:
        assert "differs from checkpoint" in str(refused)  # tail row itself was altered
    else:
        with pytest.raises(ValueError):
            list(reader.entries())
        reader.close()
    journal.close()


def test_tail_mismatch_after_open_and_incomplete_iteration(tmp_path):
    journal = build(tmp_path, values=[1, 2, 3])
    reader = reader_for(journal)
    journal.append("LATE", dict(value=4))
    with pytest.raises(ValueError, match="changed during iteration"):
        list(reader.entries())
    with pytest.raises(ValueError, match="changed during iteration"):
        reader.verify(count=reader.count, head_hash=reader.head_hash)
    reader.close()
    reader = reader_for(journal)
    with pytest.raises(ValueError, match="differs from checkpoint"):
        reader.verify(count=reader.count - 1, head_hash=reader.head_hash)
    corrupt(journal, "DELETE FROM entries WHERE ordinal=4")
    with pytest.raises(ValueError, match="changed during iteration"):
        list(reader.entries())
    reader.close(); journal.close()
