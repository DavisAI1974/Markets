import json
import pathlib
import tempfile
import unittest
from family_clock_sources import unpack, find_second_set, seek_line_start
import io


class SourceReaders(unittest.TestCase):
    def test_partitions_keep_each_record_once_at_exact_boundaries(self):
        data = b'a\nbbbbb\nccc\nd\n'
        expected = data.splitlines(keepends=True)
        for boundary in range(1, len(data)):
            observed = []
            for lower, upper in [(0, boundary), (boundary, len(data))]:
                stream = io.BytesIO(data)
                seek_line_start(stream, lower)
                while stream.tell() < upper:
                    observed.append(stream.readline())
            self.assertEqual(observed, expected)

    def test_float_and_exact_integer_are_distinct(self):
        self.assertEqual(unpack(['float64', '40087ced916872b0']), 3.061)
        stamp = 1697576400190836661
        self.assertEqual(unpack(['int', stamp]), stamp)

    def test_variable_line_boundaries_and_absent_cursor(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / 'rows.jsonl'
            with path.open('wb') as handle:
                handle.write(b'{"header":true}\n')
                for cursor in range(0, 400, 2):
                    row = {'key': {'adapter_cursor': cursor}, 'payload': 'x' * (12000 + cursor * 91)}
                    handle.write(json.dumps(row).encode() + b'\n')
            for cursor in range(400):
                found = find_second_set(path, cursor)
                if cursor % 2:
                    self.assertIsNone(found)
                else:
                    self.assertEqual(found[2]['key']['adapter_cursor'], cursor)
                    with path.open('rb') as handle:
                        handle.seek(found[0])
                        self.assertEqual(handle.readline(), found[1])


if __name__ == '__main__':
    unittest.main()
