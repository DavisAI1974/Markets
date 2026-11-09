"""Resolve a pinned data input to local bytes or a local path, verifying its sha256 against data-manifest.json.

Order: a checkout of the markets-data repository named by MARKETS_DATA_DIR; the session scratchpad mirror;
the Markets repository object store at the manifest's pinned commit (materialized into the scratchpad).
Every read of a hashed entry is verified. Entries whose manifest hash is None (small receipts, the tape
MANIFEST) are returned unverified. Archive-tier entries are not resolvable here by design.
"""

import hashlib
import json
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
MANIFEST = json.loads((HERE / "data-manifest.json").read_text())
BY_PATH = {e["path"]: e for e in MANIFEST["entries"] if e.get("path")}
BY_DATA_PATH = {e["markets_data_path"]: e for e in MANIFEST["entries"] if e.get("markets_data_path")}
SCRATCH = Path(os.environ.get("MARKETS_DATA_MIRROR", "/tmp/claude-0/-home-user-Markets/e6cffa19-4561-5119-b5f4-3474c12f9fe5/scratchpad/markets-data"))


class DataLocatorError(RuntimeError):
    pass


def _entry(path):
    e = BY_PATH.get(path) or BY_DATA_PATH.get(path)
    if e is None:
        raise DataLocatorError(f"not in data-manifest.json: {path}")
    if e["tier"] == "archive":
        raise DataLocatorError(f"archive tier is not resolvable through the locator: {path}")
    return e


def _verify(e, data):
    if e.get("sha256") and hashlib.sha256(data).hexdigest() != e["sha256"]:
        raise DataLocatorError(f"sha256 drift for {e['path']}")
    return data


def read_bytes(path):
    e = _entry(path)
    data_dir = os.environ.get("MARKETS_DATA_DIR")
    if data_dir and e.get("markets_data_path"):
        p = Path(data_dir) / e["markets_data_path"]
        if p.exists():
            return _verify(e, p.read_bytes())
    p = SCRATCH / e["path"]
    if p.exists():
        return _verify(e, p.read_bytes())
    data = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{e['markets_commit']}:{e['path']}"])
    _verify(e, data)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return data


def local_path(path):
    """A local file path for the entry (materializing from the pinned commit if needed), verified."""
    e = _entry(path)
    data_dir = os.environ.get("MARKETS_DATA_DIR")
    if data_dir and e.get("markets_data_path"):
        p = Path(data_dir) / e["markets_data_path"]
        if p.exists():
            _verify(e, p.read_bytes()); return p
    p = SCRATCH / e["path"]
    if not p.exists():
        read_bytes(path)
    else:
        _verify(e, p.read_bytes())
    return p


def tape_bytes(utc_day):
    return read_bytes(f"data/nymex_mbo/ng_v0_oct2023/NG_v0_mbo_{utc_day}.dbn.zst")


def verify_all(tiers=("tape", "export")):
    out = {}
    for e in MANIFEST["entries"]:
        if e["tier"] in tiers and e.get("sha256"):
            try:
                read_bytes(e["path"]); out[e["path"]] = "ok"
            except Exception as exc:  # noqa: BLE001
                out[e["path"]] = f"FAIL {exc}"
    return out


if __name__ == "__main__":
    res = verify_all()
    bad = {k: v for k, v in res.items() if v != "ok"}
    print(f"verified {sum(1 for v in res.values() if v == 'ok')} of {len(res)} hashed entries", "| failures:", bad or "none")
