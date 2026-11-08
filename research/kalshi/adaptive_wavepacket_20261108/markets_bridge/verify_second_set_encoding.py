"""Audit the retained second-set encoding and range without trusting component names."""

import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

from .verify_ng_book_replay import expect, git_blob
from .verify_retained_root_inputs import ROOT_PIN


RECEIPT = "artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1/bounded-second-set-read-receipt.json"
FORMATS = {
    "clocks-i64.bin": ("<i8", 7),
    "components-f32.bin": ("<f4", 19),
    "raw-components-f64.bin": ("<f8", 19),
    "states-u8.bin": ("u1", 19),
}


def verified_matrix(member, rows):
    name = Path(member["original_member"]).name
    dtype, columns = FORMATS[name]
    data = bytearray()
    for chunk in member["chunks"]:
        with gzip.open(Path(chunk["path"]), "rb") as stream:
            start = len(data)
            data.extend(stream.read())
        expect(len(data) - start, chunk["uncompressed_bytes"], chunk["path"])
    expect(len(data), member["bytes"], name)
    expect(hashlib.sha256(data).hexdigest(), member["sha256"], name)
    return np.frombuffer(data, dtype=dtype).reshape(rows, columns)


def run():
    receipt = json.loads(git_blob(ROOT_PIN, RECEIPT))
    shape = receipt["source_rows"]
    expect(len(receipt["original_number_names"]), 19, "second-set component count")
    matrices = {
        Path(member["original_member"]).name: verified_matrix(member, shape)
        for member in receipt["source_members"]
    }
    clocks = matrices["clocks-i64.bin"]
    raw = matrices["raw-components-f64.bin"]
    encoded = matrices["components-f32.bin"]
    states = matrices["states-u8.bin"]
    component_checks = {}
    flagged = {}
    for index, name in enumerate(receipt["original_number_names"]):
        state = states[:, index]
        present = state == 0
        before = raw[:, index]
        after = encoded[:, index]
        expect(bool(np.isfinite(before[present]).all()), True, f"{name} present raw finiteness")
        expect(bool(np.array_equal(before[present].astype("<f4").view("<u4"), after[present].view("<u4"))),
               True, f"{name} float32 identity")
        labels, counts = np.unique(state, return_counts=True)
        component_checks[name] = {
            "state_counts_by_code": {str(label): int(count) for label, count in zip(labels, counts, strict=True)},
            "present_float32_identity": int(present.sum()),
            "nonpresent_encoded_zero": int((~present & (after == 0)).sum()),
        }
        if name.startswith("far_absorption_share_"):
            outside = present & ((before < 0) | (before > 1))
            if outside.any():
                worst = int(np.argmax(np.where(outside, before, -np.inf)))
                flagged[name] = {
                    "outside_unit_interval": int(outside.sum()),
                    "max_observed": float(before[worst]),
                    "cursor_at_max": int(clocks[worst, 0]),
                    "known_by_ns_at_max": int(clocks[worst, 4]),
                }
    return {
        "archive_git_commit": ROOT_PIN,
        "rows": shape,
        "components": component_checks,
        "flagged_ratios": flagged,
        "scope": "Byte integrity, identity float32 encoding and range checks. Original market formulae remain held.",
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
