"""Measure lossless compression of sealed ROOT frame spools."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter, process_time

import zstandard as zstd


READ_BYTES = 8 << 20
EXTENT_BYTES = 128 << 10
SECTOR_BYTES = 4 << 10


def sectors(size):
    return (size + SECTOR_BYTES - 1) // SECTOR_BYTES


def measure(source, expected, archive):
    length = source.stat().st_size
    digest = hashlib.sha256()
    compressors = {level: zstd.ZstdCompressor(level=level) for level in (1, 3)}
    approximate = {level: 0 for level in compressors}
    start, cpu = perf_counter(), process_time()
    read_bytes = 0
    with source.open('rb') as raw, archive.open('xb') as compressed:
        with zstd.ZstdCompressor(level=1).stream_writer(compressed, closefd=False) as writer:
            for block in iter(lambda: raw.read(READ_BYTES), b''):
                read_bytes += len(block)
                digest.update(block)
                writer.write(block)
                view = memoryview(block)
                for start_byte in range(0, len(view), EXTENT_BYTES):
                    extent = view[start_byte:start_byte + EXTENT_BYTES]
                    for level, compressor in compressors.items():
                        encoded = compressor.compress(extent)
                        approximate[level] += min(sectors(len(extent)), sectors(len(encoded))) * SECTOR_BYTES
        compressed.flush()
        os.fsync(compressed.fileno())
    if (read_bytes, digest.hexdigest()) != (length, expected):
        raise ValueError('Source differs from its sealed byte count or SHA-256')
    seconds, cpu_seconds = perf_counter() - start, process_time() - cpu
    check_start = perf_counter()
    with archive.open('rb') as stream, zstd.ZstdDecompressor().stream_reader(stream) as decoded:
        readback = hashlib.file_digest(decoded, 'sha256').hexdigest()
        decoded_size = decoded.tell()
    if (readback, decoded_size) != (expected, length):
        raise ValueError('Decompressed archive differs from the sealed source')
    return dict(
        logical_bytes=length, logical_sha256=expected, zstd_level_1_archive_bytes=archive.stat().st_size,
        zstd_level_1_archive_sha256=hash_archive(archive),
        modeled_extent_bytes=EXTENT_BYTES, modeled_sector_bytes=SECTOR_BYTES,
        modeled_allocation_bytes=approximate, all_codec_pass_wall_seconds=round(seconds, 2),
        all_codec_pass_cpu_seconds=round(cpu_seconds, 2),
        archive_readback_wall_seconds=round(perf_counter() - check_start, 2),
        decoded_sha256=readback, decoded_bytes=decoded_size,
    )


def hash_archive(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('source_sha256')
    parser.add_argument('archive', type=Path)
    args = parser.parse_args()
    print(json.dumps(measure(args.source, args.source_sha256, args.archive), indent=2))