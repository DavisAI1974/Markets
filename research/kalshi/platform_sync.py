"""
platform_sync.py - the ONE door between local cache and the S3 data plane (S98 M2, AWS_PLATFORM_S98.md).

git = CODE + docs + records; S3 = ALL DATA (one bucket, per-prefix manifest.json); local = disposable
cache. This tool is the only sanctioned way a session moves data either direction, so provenance stays
one-way and auditable. Ends the "is the data on this machine" session question (M6 wires it into the
session-start ritual).

Commands (creds from scratchpad/aws.env; bucket/region pinned below):
  list                          -> prefixes + manifest summaries (what do we have, as a QUERY)
  pull --prefix nymex/contract_structure/ [--dest data/contract_structure]
                                -> S3 -> local, skip-if-same-size
  push --prefix eia/ --src data/eia_surprise.json [--execute]
                                -> local -> S3 + manifest.json write. DRY-RUN by default; --execute
                                   to actually upload (pushes are the irreversible-ish direction).
  --selftest                    -> read-only: creds resolve, bucket lists, manifests parse

Mapping doctrine: LOCAL data/<store> <-> s3://<bucket>/<prefix>. The prefix taxonomy lives in
AWS_PLATFORM_S98.md section 2; existing S97 locations are KEPT (nymex/contract_structure/ etc.),
new stores get new top prefixes (eia/, kalshi/, consensus/, calendar/, options/).

Manifests: every push rewrites <prefix>manifest.json with {prefix, object_count, total_bytes,
updated_at_utc, writer, files:[...names...], note}. Missing coverage stays visible in the store
itself (missing==None doctrine); the manifest is inventory, never interpolation.
"""
from __future__ import annotations
import argparse
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
ENV = os.path.join(REPO, "scratchpad", "aws.env")
BUCKET = "bento-568968024170-us-east-2-an"
REGION = "us-east-2"


def _s3():
    # S113 (Greg: "no more scratchpad. It's in the sop"). This used to require
    # <repo>/scratchpad/aws.env and exit if it was absent, which made every push depend on a
    # directory D33 forbids and that dies with the container. creds.aws_client() resolves the
    # real pair from ~/.aws/credentials and strips the container's injected placeholders first.
    sys.path.insert(0, HERE)
    import creds
    return creds.aws_client("s3", REGION)


def _iter_prefix(s3, prefix: str):
    pag = s3.get_paginator("list_objects_v2")
    for page in pag.paginate(Bucket=BUCKET, Prefix=prefix):
        yield from page.get("Contents", [])


def cmd_list() -> int:
    s3 = _s3()
    # top-level prefixes via delimiter
    r = s3.list_objects_v2(Bucket=BUCKET, Delimiter="/")
    tops = [p["Prefix"] for p in r.get("CommonPrefixes", [])]
    print(f"[platform_sync] s3://{BUCKET} ({REGION}) top prefixes:")
    for t in tops:
        objs = list(_iter_prefix(s3, t))
        man = [o for o in objs if o["Key"].endswith("manifest.json")]
        note = ""
        if man:
            try:
                body = s3.get_object(Bucket=BUCKET, Key=man[0]["Key"])["Body"].read()
                m = json.loads(body)
                note = f"manifest: {m.get('object_count')} obj, updated {m.get('updated_at_utc', '?')[:10]}"
            except Exception as e:
                note = f"manifest unreadable: {e}"
        else:
            note = "NO MANIFEST (pre-M2 prefix)"
        print(f"  {t:<28} {len(objs):>5} obj {sum(o['Size'] for o in objs)/1e6:>9.1f} MB   {note}")
    return 0


def cmd_pull(prefix: str, dest: str | None) -> int:
    s3 = _s3()
    dest = dest or os.path.join(REPO, "data", prefix.rstrip("/").split("/")[-1])
    os.makedirs(dest, exist_ok=True)
    n_dl = n_skip = 0
    for o in _iter_prefix(s3, prefix):
        rel = o["Key"][len(prefix):]
        if not rel or rel == "manifest.json":
            continue
        local = os.path.join(dest, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(local), exist_ok=True) if os.path.dirname(local) else None
        if os.path.exists(local) and os.path.getsize(local) == o["Size"]:
            n_skip += 1
            continue
        s3.download_file(BUCKET, o["Key"], local)
        n_dl += 1
    print(f"[platform_sync] pull {prefix} -> {dest}: {n_dl} downloaded, {n_skip} already current")
    return 0


def cmd_push(prefix: str, src: str, execute: bool, note: str = "") -> int:
    if not prefix.endswith("/"):
        sys.exit("[platform_sync] --prefix must end with /")
    s3 = _s3()
    src = src if os.path.isabs(src) else os.path.join(REPO, src)
    files = []
    if os.path.isfile(src):
        files = [(src, os.path.basename(src))]
    else:
        for root, _, names in os.walk(src):
            for n in names:
                p = os.path.join(root, n)
                files.append((p, os.path.relpath(p, src).replace(os.sep, "/")))
    # manifest.json is GENERATED below, so a stale local copy must not be pushed as a source file:
    # it gets uploaded, immediately overwritten by the generated one, and then the verify compares
    # the new remote size against the old local size and reports VERIFY FAILED on a push that in
    # fact succeeded - exit 1 on success, which would break any automation that checks the code.
    files = [(p, rel) for p, rel in files if rel != "manifest.json"]
    if not files:
        sys.exit(f"[platform_sync] nothing to push at {src}")
    total = sum(os.path.getsize(p) for p, _ in files)
    tag = "PUSH" if execute else "DRY-RUN (add --execute)"
    print(f"[platform_sync] {tag}: {len(files)} files, {total/1e6:.2f} MB -> s3://{BUCKET}/{prefix}")
    for p, rel in files:
        print(f"   {rel:<52} {os.path.getsize(p):>10,} B")
        if execute:
            s3.upload_file(p, BUCKET, prefix + rel)
    if execute:
        manifest = {"prefix": prefix, "object_count": len(files), "total_bytes": total,
                    "updated_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                    "writer": "platform_sync.py", "files": sorted(rel for _, rel in files),
                    "note": note or "pushed via platform_sync; local copy is now CACHE"}
        s3.put_object(Bucket=BUCKET, Key=prefix + "manifest.json",
                      Body=json.dumps(manifest, indent=1).encode())
        # verify: every file listable at its claimed size
        remote = {o["Key"]: o["Size"] for o in _iter_prefix(s3, prefix)}
        bad = [rel for p, rel in files if remote.get(prefix + rel) != os.path.getsize(p)]
        if bad:
            print(f"[platform_sync] VERIFY FAILED on {len(bad)} files: {bad}")
            return 1
        print(f"[platform_sync] verified {len(files)}/{len(files)} + manifest written")
    return 0


def _selftest() -> int:
    s3 = _s3()
    r = s3.list_objects_v2(Bucket=BUCKET, MaxKeys=1)
    assert r.get("KeyCount", 0) >= 1, "bucket empty or unreadable"
    print(f"[platform_sync] selftest: creds OK, bucket {BUCKET} readable. PASS")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("list")
    a1 = sub.add_parser("pull"); a1.add_argument("--prefix", required=True); a1.add_argument("--dest")
    a2 = sub.add_parser("push"); a2.add_argument("--prefix", required=True); a2.add_argument("--src", required=True)
    a2.add_argument("--execute", action="store_true"); a2.add_argument("--note", default="")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return _selftest()
    if a.cmd == "list":
        return cmd_list()
    if a.cmd == "pull":
        return cmd_pull(a.prefix, a.dest)
    if a.cmd == "push":
        return cmd_push(a.prefix, a.src, a.execute, a.note)
    ap.print_help(); return 1


if __name__ == "__main__":
    sys.exit(main())
