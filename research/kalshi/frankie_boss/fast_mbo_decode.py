"""The MBO record decode of mbo_source._records, many records per decoder call (Greg, 2026-09-29: "Do 1-5 now", item 5).

mbo_source._records builds a new DBNDecoder for EVERY record (2.1M per trading day) and decodes one wire record at a
time. This reads the decompressed stream in chunks, cuts it into whole wire records by their length byte, decodes a
whole batch with one decoder call, and keeps every check the original makes, per record:
  - the record length byte is at least 2 words, the rtype is MBO (160), the length agrees with ts_out;
  - the SDK returns exactly one MBOMsg per wire record, with no remainder and nothing buffered;
  - bytes(record) reproduces the wire record exactly;
and yields mbo_source._extract(record) unchanged: the same dict, field for field, as the original. Nothing is skipped: a
record that fails a check raises, as the original does. mbo_source.py is not edited (it is the pinned extractor).
"""
try:
    from . import mbo_source
except ImportError:   # flat import
    import mbo_source

CHUNK_BYTES = 8 * 1024 * 1024


def records(stream, pin, ts_out, dbn):
    """Every MBO record of the stream in order, as mbo_source._records yields them."""
    expected = 64 if ts_out else 56
    buffer = b''
    while True:
        chunk = stream.read(CHUNK_BYTES)
        if chunk:
            buffer += chunk
        wires, position = [], 0
        while position < len(buffer):
            size = buffer[position] * 4
            if size < 2:
                raise ValueError('invalid DBN record length')
            if position + size > len(buffer):
                break                                           # the rest arrives with the next chunk
            wire = buffer[position:position + size]
            if wire[1] != 160:
                raise ValueError('non-MBO record in declared MBO source; no record is skipped')
            if size != expected:
                raise ValueError('MBO record length disagrees with metadata ts_out')
            wires.append(wire)
            position += size
        buffer = buffer[position:]
        if wires:
            decoder = dbn.DBNDecoder(has_metadata=False, ts_out=ts_out, input_version=pin.dbn_version,
                                     upgrade_policy=dbn.VersionUpgradePolicy.AS_IS)
            try:
                decoded = decoder.write_and_decode(b''.join(wires))
                remainder = decoder.decode()
            except dbn.DBNError as exc:
                raise ValueError('invalid MBO wire record') from exc
            if len(decoded) != len(wires) or remainder or decoder.buffer():
                raise ValueError('SDK did not decode exactly one record per wire record')
            for record, wire in zip(decoded, wires):
                if type(record) is not dbn.MBOMsg or bytes(record) != wire:
                    raise ValueError('SDK did not reproduce exact source record bytes')
                yield mbo_source._extract(record, pin, dbn)
        if not chunk:
            if buffer:
                raise ValueError('truncated DBN source')
            return
