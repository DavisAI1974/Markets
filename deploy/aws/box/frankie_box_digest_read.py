"""What Granite reads of a derivation digest: everything the 6-hour run's read held (Greg, 2026-09-28: "Do what we did on
Sunday night to the full Monday"; "we're doing this for Monday too").

The 6-hour run (glbx-mdp3-20211003, read of 09-21: 248,111 tokens) read the digest's header, layer statuses and the
legacy tables, whole; the bedrock section came to the digest later (DIGEST_V6). So the read is the digest file from its
first byte up to the `## Bedrock (` heading, verbatim and whole, every record of the day, no cutoff inside any table; the
bedrock tables stay calculated and retained in the same unchanged file on the box. One streaming pass also gives the
whole file's bytes and sha256 (the file runs to GBs; the bedrock part is never held in memory).
"""
import hashlib

SCHEMA = 'DIGEST_READ_LEGACY_V1'
BEDROCK = b'\n## Bedrock ('
CHUNK = 1 << 24


def legacy_read(path):
    """(text, stats): the digest up to its bedrock heading (the whole file when it has none)."""
    sha, data, total, cut = hashlib.sha256(), bytearray(), 0, None
    with open(path, 'rb') as source:
        while True:
            block = source.read(CHUNK)
            if not block:
                break
            sha.update(block)
            total += len(block)
            if cut is None:                                   # data holds the file from byte 0 until the heading is found
                start = max(0, len(data) - len(BEDROCK) + 1)  # a heading straddling two blocks is still found
                data += block
                at = data.find(BEDROCK, start)
                if at >= 0:
                    cut = at + 1                              # keep the newline before the heading; drop the heading on
                    del data[cut:]
    return bytes(data).decode('utf-8', errors='replace'), dict(
        schema=SCHEMA, digest_bytes=total, digest_sha256=sha.hexdigest(), read_bytes=len(data),
        bedrock_at=cut, bedrock_bytes=(total - cut) if cut is not None else 0)
