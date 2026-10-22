"""Source readers for observational family replay; no prediction target."""
import json
import struct


def seek_line_start(handle, offset):
    """Start at the first full record at or after an arbitrary byte offset."""
    if offset == 0:
        handle.seek(0)
    else:
        handle.seek(offset - 1)
        if handle.read(1) != b'\n':
            handle.readline()
    return handle.tell()


def unpack(value):
    if not isinstance(value, list) or not value:
        return value
    tag = value[0]
    if tag == 'dict':
        return {key: unpack(item) for key, item in value[1]}
    if tag in ('list', 'tuple', 'set', 'frozenset'):
        return [unpack(item) for item in value[1]]
    if tag == 'float64':
        return struct.unpack('>d', bytes.fromhex(value[1]))[0]
    if tag == 'null':
        return None
    if len(value) == 2 and tag in ('str', 'int', 'float', 'bool'):
        return value[1]
    return value


def find_second_set(path, cursor):
    """Exact cursor lookup, finishing with a sequential boundary scan.

    Return byte offset, raw record and decoded record. The final scan includes
    a record crossing the upper byte bound; that bound can lie inside a line.
    """
    with open(path, 'rb') as handle:
        handle.readline()  # Source header, not a market observation.
        lower = handle.tell()
        handle.seek(0, 2)
        upper = handle.tell()
        while upper - lower > 4 * 1024 * 1024:
            middle = (lower + upper) // 2
            handle.seek(middle)
            handle.readline()
            position = handle.tell()
            if position >= upper:
                upper = middle
                continue
            raw = handle.readline()
            row = json.loads(raw)
            key = row['key']['adapter_cursor']
            if key == cursor:
                return position, raw, row
            if key < cursor:
                lower = handle.tell()
            else:
                upper = position
        handle.seek(lower)
        while handle.tell() <= upper:
            position = handle.tell()
            raw = handle.readline()
            if not raw:
                break
            row = json.loads(raw)
            key = row['key']['adapter_cursor']
            if key == cursor:
                return position, raw, row
            if key > cursor:
                break
    return None

