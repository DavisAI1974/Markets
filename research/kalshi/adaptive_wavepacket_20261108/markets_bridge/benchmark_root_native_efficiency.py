"""Benchmark lossless ROOT and Native book changes on pinned NG tape prefixes."""

import argparse
import difflib
import gc
import hashlib
from itertools import islice
import json
import os
from pathlib import Path
from statistics import median
import subprocess
import sys
from time import perf_counter
from types import ModuleType
from urllib.request import urlopen

from .verify_ng_book_replay import ADAPTER_PATH, ADAPTER_PIN, TAPE_PIN, read_member, tape_blob


NATIVE_PIN = "2ebb8ce8ef4834545ad99a4ecdff50c18c5b3134"
NATIVE_DIRECTORY = "research/kalshi/frankie_raw_mbo_benchmark"
NATIVE_PACKAGE = NATIVE_DIRECTORY.replace("/", ".")
ADAPTER_MODULE = ADAPTER_PATH.removesuffix(".py").replace("/", ".")
CAPTURE_PATH = f"{NATIVE_DIRECTORY}/native_full_capture_adapter.py"
DAYS = ("20231003", "20231018")
MBO_NUMERIC = (
    "instrument_id", "publisher_id", "channel_id", "order_id", "price", "size",
    "flags", "sequence", "ts_event", "ts_recv", "ts_in_delta", "rtype",
)


def pinned_source(pin, path):
    env = dict(os.environ, GIT_NO_LAZY_FETCH="1")
    tree = subprocess.check_output(["git", "ls-tree", pin, "--", path], env=env).split()
    if len(tree) < 4 or tree[1] != b"blob":
        raise ValueError(f"No pinned Git blob for {pin}:{path}")
    oid = tree[2].decode()
    try:
        raw = subprocess.check_output(["git", "cat-file", "blob", oid], stderr=subprocess.DEVNULL, env=env)
    except subprocess.CalledProcessError:
        with urlopen(f"https://raw.githubusercontent.com/DavisAI1974/Markets/{pin}/{path}", timeout=20) as stream:
            raw = stream.read()
    if hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest() != oid:
        raise ValueError(f"Source bytes differ from {pin}:{path}")
    return raw.decode("utf-8")


def load_module(name, source, source_path=None):
    module = ModuleType(name)
    module.__file__ = str(Path(source_path or name.replace(".", "/")).resolve())
    sys.modules[name] = module
    exec(compile(source, name, "exec"), module.__dict__)
    return module


def replace_once(source, before, after):
    if source.count(before) != 1:
        raise ValueError(f"Candidate does not match the pinned producer at {before!r}")
    return source.replace(before, after)


def reuse_queue_ages(source):
    source = replace_once(source, "    vals = sorted(float(x) for x in values)\n    if not vals:",
        "    return _quantile_sorted(sorted(float(x) for x in values), q)\n\n\n"
        "def _quantile_sorted(vals: list[float], q: float) -> float | None:\n    if not vals:")
    source = replace_once(source, '        out: dict[str, Any] = {\n            "side": side,',
        '        sorted_ages = sorted(ages)\n        out: dict[str, Any] = {\n            "side": side,')
    source = replace_once(source, "_quantile(ages, 0.5)", "_quantile_sorted(sorted_ages, 0.5)")
    source = replace_once(source, "_quantile(ages, 0.9)", "_quantile_sorted(sorted_ages, 0.9)")
    source = replace_once(source, "            for order in orders:\n                queue.append",
        "            for order, age in zip(orders, ages):\n                queue.append")
    return replace_once(source, '"priority_age_s": max(0.0, (now_ns - order.priority_recv_ns) / 1e9),',
        '"priority_age_s": age,')


def reuse_live_book(source):
    return replace_once(source, "        book = self.books.setdefault(msg.instrument_id, InstrumentBook(msg.instrument_id))",
        "        book = self.books.get(msg.instrument_id)\n"
        "        if book is None:\n            book = self.books[msg.instrument_id] = InstrumentBook(msg.instrument_id)")


def tape_prefixes(count):
    specs = {entry["file"]: entry for entry in json.loads(tape_blob("MANIFEST.json"))["files"]}
    for day in DAYS:
        tape = tuple(islice(read_member(specs[f"NG_v0_mbo_{day}.dbn.zst"]), count))
        if len(tape) != count:
            raise ValueError(f"Incomplete replay prefix for {day}")
        mappings = tuple({
            **{field: int(getattr(record, field)) for field in MBO_NUMERIC},
            "action": record.action.value, "side": record.side.value,
        } for record in tape)
        yield tape, mappings


def replay(path, adapter_source, capture_source, samples, *, verify):
    module = load_module(ADAPTER_MODULE, adapter_source)
    capture = (load_module(f"{NATIVE_PACKAGE}.native_full_capture_adapter", capture_source)
               if path == "native" else None)
    gc.collect()
    digest = hashlib.sha256()
    frames = 0
    start = perf_counter()
    for tape, mappings in samples:
        adapter = capture.FullCaptureAdapter() if capture else module.V4MboAdapter()
        for record in mappings if capture else tape:
            frame, legacy = adapter.apply(record, "NGX3")
            full = None
            if frame is not None:
                frames += 1
                if not capture:
                    full = adapter.books[frame["instrument_id"]].book_snapshot(
                        frame["ts_recv_ns"], include_full_depth=True, include_order_ids=True,
                    )
            if verify:
                digest.update((json.dumps((frame, full, legacy), separators=(",", ":")) + "\n").encode())
    return perf_counter() - start, frames, digest.hexdigest()


def compare(path, variants, samples, rounds):
    results = {name: [] for name in variants}
    verification = {
        name: replay(path, adapter, capture, samples, verify=True)[1:]
        for name, (adapter, capture) in variants.items()
    }
    if len(set(verification.values())) != 1:
        raise ValueError(f"Candidate changes ordered frame or legacy output: {path}, {verification}")
    names = tuple(variants)
    for round_index in range(rounds):
        for name in names if round_index % 2 == 0 else names[::-1]:
            results[name].append(replay(path, *variants[name], samples, verify=False)[0])
    return {
        "verified_frames": verification[names[0]][0], "ordered_output_sha256": verification[names[0]][1],
        "seconds": {name: [round(elapsed, 4) for elapsed in times] for name, times in results.items()},
        "median_seconds": {name: round(median(times), 4) for name, times in results.items()},
    }


def write_patch(path, before, after, source_path):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.writelines(difflib.unified_diff(
            before.splitlines(keepends=True), after.splitlines(keepends=True),
            fromfile=f"a/{source_path}", tofile=f"b/{source_path}",
        ))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=int, default=2000, help="Source rows per UTC tape member")
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--stage-patches", type=Path, help="Write the checked ROOT and Native patches to a new directory")
    args = parser.parse_args()
    if args.records < 1000 or args.rounds < 3:
        parser.error("Use at least 1,000 records per member and three timing rounds")

    package = ModuleType(NATIVE_PACKAGE)
    package.__path__ = []
    sys.modules[NATIVE_PACKAGE] = package
    for name, source_path in (
        ("flow_calendar", "research/kalshi/flow_calendar.py"),
        ("research.kalshi.plant_calendar", "research/kalshi/plant_calendar.py"),
        (f"{NATIVE_PACKAGE}.native_session", f"{NATIVE_DIRECTORY}/native_session.py"),
    ):
        load_module(name, pinned_source(NATIVE_PIN, source_path), source_path)
    root = pinned_source(ADAPTER_PIN, ADAPTER_PATH)
    native = pinned_source(NATIVE_PIN, ADAPTER_PATH)
    capture = pinned_source(NATIVE_PIN, CAPTURE_PATH)
    samples = tuple(tape_prefixes(args.records))
    root_ages = reuse_queue_ages(root)
    native_ages = reuse_queue_ages(native)
    result = {
        "tape_pin": TAPE_PIN, "utc_members": list(DAYS), "records_per_member": args.records,
        "root_pin": ADAPTER_PIN, "native_pin": NATIVE_PIN,
        "scope": "In-process book and legacy output. Excludes whole-stage encoding, IPC, checkpoint and disk I/O.",
        "root": compare("root", {
            "baseline": (root, None),
            "reuse_queue_ages": (root_ages, None),
        }, samples, args.rounds),
        "native": compare("native", {
            "baseline": (native, capture),
            "reuse_queue_ages": (native_ages, capture),
            "legacy_summary_backport": (root, capture),
            "reuse_live_book": (native, reuse_live_book(capture)),
            "reuse_queue_ages_and_legacy_summary": (root_ages, capture),
        }, samples, args.rounds),
    }
    if args.stage_patches is not None:
        args.stage_patches.mkdir(exist_ok=False)
        write_patch(args.stage_patches / "root-queue-ages.patch", root, root_ages, ADAPTER_PATH)
        write_patch(args.stage_patches / "native-queue-ages-and-legacy-summary.patch", native, root_ages, ADAPTER_PATH)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
