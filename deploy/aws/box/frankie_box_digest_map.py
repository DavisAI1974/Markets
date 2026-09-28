"""The derivation digest as the reading reads it: its map (Greg, 2026-09-28: "do whatever is faster, and smallest without
changing the science").

EVERY line of the digest verbatim except each table's dictionary line and its rows past the first `sample_rows`, which
are listed by exact UTF-8 byte range [start, end) of the unchanged file, so any of them is read on demand (the classroom
tasks retrieve exact ranges with read_requests). One streaming pass; the digest is never rewritten or held whole.
Used for this cycle's digest (frankie_box_boss_session.reading_corpus) and for digests the brain carries
(frankie_box_brain.load).
"""
import hashlib
import re

SCHEMA = 'DIGEST_MAP_V1'
_HEADER = re.compile(rb'### table (\S+): (\d+) rows')


def digest_map(path, label, sample_rows=3):
    """(text, stats) for the digest file at `path`; `label` names the source the byte ranges belong to."""
    out, tables, offset, by_range = [], 0, 0, 0
    sha = hashlib.sha256()
    where = label.encode('utf-8')
    with open(path, 'rb') as source:
        def advance():
            raw = source.readline()
            sha.update(raw)
            return raw
        line = advance()
        while line:
            m = _HEADER.match(line)
            if m is None:
                out.append(line)
                offset += len(line)
                line = advance()
                continue
            name, n = m.group(1), int(m.group(2))
            tables += 1
            out.append(line)
            offset += len(line)
            line = advance()
            while line.startswith((b'constants: ', b'scales: ', b'shapes: ', b'lengths: ')):
                out.append(line)
                offset += len(line)
                line = advance()
            if line.startswith(b'dictionary: '):
                out.append(b'[dictionary of %s: %d entries at bytes %d-%d of %s; read by range]\n'
                           % (name, line.count(b'\t@') + 1, offset, offset + len(line), where))
                by_range += len(line)
                offset += len(line)
                line = advance()
            start, taken = offset, 0
            while taken < n and line:
                if taken < sample_rows:
                    out.append(line)
                else:
                    by_range += len(line)
                offset += len(line)
                taken += 1
                line = advance()
            if taken != n:
                raise ValueError('digest table %s ends after %d of %d rows' % (name.decode('utf-8', 'replace'), taken, n))
            if n > sample_rows:
                out.append(b'[rows of %s: %d rows at bytes %d-%d of %s (the first %d above); every row read by range]\n'
                           % (name, n, start, offset, where, sample_rows))
    text = b''.join(out).decode('utf-8', errors='replace')
    return text, dict(schema=SCHEMA, source=label, tables=tables, digest_bytes=offset, digest_sha256=sha.hexdigest(),
                      map_bytes=len(text.encode('utf-8')), bytes_by_range=by_range, sample_rows=sample_rows)
