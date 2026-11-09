"""Stage the tape and export tiers into a local checkout of the markets-data repository.

Usage: python3 stage_markets_data_repo.py /path/to/markets-data-checkout
Copies every tape and export entry of data-manifest.json to its markets_data_path, verifies each hash
after the copy, writes MANIFEST.json (the same manifest) and a README at the checkout root, and prints the
archive-tier entries with their S3 targets, which this script does not move. Commit and push the checkout
yourself; nothing here touches a remote.
"""

import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import data_locator as L  # noqa: E402


def main():
    dest = Path(sys.argv[1]).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    copied = 0
    for e in L.MANIFEST["entries"]:
        if e["tier"] == "archive":
            continue
        src = L.local_path(e["path"])
        tgt = dest / e["markets_data_path"]
        tgt.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, tgt)
        if e.get("sha256") and hashlib.sha256(tgt.read_bytes()).hexdigest() != e["sha256"]:
            raise SystemExit(f"hash drift after copy: {e['path']}")
        copied += 1
    (dest / "MANIFEST.json").write_text(json.dumps(L.MANIFEST, indent=2) + "\n")
    (dest / "README.md").write_text(
        "# markets-data\n\nPinned data inputs for DavisAI1974/Markets: Databento NG MBO UTC-day members, standalone group exports,\n"
        "sealed touch-print decisions and the October 18 candidate inputs and ledgers. Every file is listed in MANIFEST.json\n"
        "with its sha256; loaders verify on read (see Markets: tasks/family-research-20261022/claude-code/data_locator.py).\n"
        "ROOT frame spools are not here; MANIFEST.json lists them with their S3 targets and part hashes.\n"
        "No code lives here. No file is ever rewritten in place; a corrected file gets a new path and a new manifest entry.\n")
    print(f"staged {copied} files into {dest}")
    for e in L.MANIFEST["entries"]:
        if e["tier"] == "archive":
            print(f"  archive not moved: {e['path']} ({e['parts']} parts, {e['bytes_uncompressed'] / 1e9:.0f} GB uncompressed) -> {e['target']}")


if __name__ == "__main__":
    main()
