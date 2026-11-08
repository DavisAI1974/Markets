"""Export a bounded UTC tape prefix for the Linux ROOT comparison."""

import argparse
import base64
import hashlib
from itertools import islice
import json
from pathlib import Path

from .benchmark_root_native_efficiency import MBO_NUMERIC
from .verify_ng_book_replay import TAPE_PIN, read_member, tape_blob


def stage(day, count, directory):
    file_name = f"NG_v0_mbo_{day}.dbn.zst"
    specs = json.loads(tape_blob("MANIFEST.json"))["files"]
    spec = next((item for item in specs if item["file"] == file_name), None)
    if spec is None or not 0 < count <= spec["records"]:
        raise ValueError("UTC member or prefix length is outside the tape manifest")
    tape = read_member(spec)
    if tape.metadata.version != 3:
        raise ValueError("The bounded ROOT input expects a DBN version 3 member")
    counts = dict(rows=0, f_last=0, trades=0, resets=0)
    digest = hashlib.sha256()
    path = directory / f"{day}-input.jsonl"
    with path.open("xb") as stream:
        for record in islice(tape, count):
            wire = bytes(record)
            row = {field: int(getattr(record, field)) for field in MBO_NUMERIC}
            row.update(action=record.action.value, side=record.side.value, dbn_length=wire[0],
                       ts_out=int(record.ts_out) if len(wire) == 64 else None,
                       dbn_wire_b64=base64.b64encode(wire).decode("ascii"))
            encoded = (json.dumps(row, separators=(",", ":")) + "\n").encode("ascii")
            stream.write(encoded)
            digest.update(encoded)
            counts["rows"] += 1
            counts["f_last"] += bool(row["flags"] & 128)
            counts["trades"] += row["action"] == "T"
            counts["resets"] += row["action"] == "R"
    if counts["rows"] != count:
        raise ValueError("Decoded tape did not cover the requested prefix")
    receipt = dict(day=day, tape_pin=TAPE_PIN, source=spec, **counts, sha256=digest.hexdigest())
    with (directory / f"{day}-input-receipt.json").open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2)
        stream.write("\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("day")
    parser.add_argument("--records", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.day, args.records, args.output), indent=2))
