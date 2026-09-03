# Frankie: the wired code FED with the real Sunday ledgers - the record (2026-09-03, S122)

Greg, verbatim: *"we need to run agents to feed what was wired last chat too."*

This is the record of feeding the code merged at S121 with the only real Sunday data in
existence: the ledgers of run `33630348943` (Sunday 2021-10-03, the a-clean full run on the
box). Nothing was built. Every wired piece was run as it exists at the development tip and
what it did is written down: the exact command, the exit code, the numbers, every refusal
verbatim, wall time and peak memory where measured. A refusal is a result (D37/D60/D76). No
production module was edited.

## 0. Identity, environment, rules

**The data (its identity is the S3 key and the sha256; the local copy is "the fetched copy").**

| object | S3 key (bucket `bento-568968024170-us-east-2-an`) | plain sha256 | plain bytes |
|---|---|---|---|
| exact member ledger | `.../33630348943-1/ledgers/exact_member_rows.jsonl.gz` | `0fd3bbce69311f571f7a5d681fc92539aecc9aedc0efe8fbf4ccc8176a6f92a2` | 10,630,127,166 |
| exact lifecycle and runway ledger | `.../33630348943-1/ledgers/exact_lifecycle_rows.jsonl.gz` | `039b6d0b327f45315b6f5c2f3fca2174314d53fff22954f97736b1cb99745d97` | 265,048,572 |
| legacy observable rows | `.../33630348943-1/ledgers/legacy_observable_rows.jsonl.gz` | `3c75f8b4b779c0ab1e59f9ea28fe12739b7b668edb3763a0c1aecaac3dc7bafa` | 29,329,182 |
| calculation_result.json | `.../33630348943-1/calculation_result.json` | `58e8aef5dc7da112eb9aaffda35808f5f0c35a5239e98ba06f7d019a657c8970` (PLAIN_SHA256SUMS) | 24,811,795 |
| small_artifacts.tar.gz | `.../33630348943-1/small_artifacts.tar.gz` | `e1a94267bc1489b182f95c2a6aee0ec6e0808a05fd0deb5ad3aa8e432ca3245e` (observed; no box digest exists for it, S3 ContentLength is its only witness) | 760,403 |

The run prefix is
`nymex/ng_mbo_5y_v0/frankie/raw_mbo_benchmark/a-clean/full/2dd7044897f1a5c88872f6c395836a2671880ae6/33630348943-1`.
Delivery manifest `FRANKIE_LEDGER_DELIVERY_MANIFEST_V1`, `manifest_sha256`
`68e588a7a27350a495aed286f955dd61cc54e9cc76437b6155be5eb6cc4f24f0`, presigned until
2026-09-09T18:15:57Z. The result: `result_hash`
`d2ab3feba0115a60088ae2a0efa8d2c173be4f911da85f82bbc0ed3375e9b3d9`, verdict `ACCEPTED`,
completion `EVIDENCE_ONLY`, 57,027 records, 43,569 groups (all F_LAST-closed), 19 invocation
cutoffs, 9 save points, identity `run_id` `frankie-a-clean-rt-33630348943-1`, identity arm
`A_CLEAN`, bound `mission_sha256` `027faa7d3d31936d3b026576c7694957319de2d94ef1d95aec5ce1fb5ec4a6f7`.
The box's `PLAIN_SHA256SUMS` and `PLAIN_SIZES` inside `small_artifacts.tar.gz` are
byte-identical to the copies published beside the manifest (sha256 `e973f184...` and
`d0039af2...` respectively, both places).

**The arm (D86/D88).** One arm runs, `A_MEMORY`. This result's IDENTITY arm is `A_CLEAN`
because it is the last run - the only real Sunday data in existence - and Greg ruled the last
run is what seeds memory. Where a CLI takes `--arm`, it was run with `A_MEMORY` first and the
identity mismatch recorded, then with the result's own arm so the numbers are honest. Nothing
was built or defaulted for `A_CLEAN`.

**Environment.** Worktree branch `persona/s122-feed-wired`, cut from the development tip
`a521507` (1,818 tests green at the S121 close). Python 3.11.15, 4 CPUs, 15 GB RAM, ~26 GB
free disk before the fetch. `/usr/bin/time` is absent in this container, so wall time and
peak RSS were taken by an inline `subprocess.run` + `resource.getrusage(RUSAGE_CHILDREN)`
wrapper (`ru_maxrss`, kB). Package `research/kalshi/frankie_raw_mbo_benchmark/`.

**Rules held.** D87: nothing written to the session scratchpad or /tmp; every transient file
lives under the repo's gitignored `data/` and the fetched ledgers are deleted at the end (the
receipts and manifest kept). D84: committed after every step and pushed to
`origin/persona/s122-feed-wired` only. D34: no artifact names a desktop, scratchpad or /tmp
path. D37/D60/D76: counts and the largest individual items, never a mean alone; keep
everything; a refusal is produced, never asserted.

## 1. Step 1 - the fetch with the receipt (`fetch_frankie_ledgers fetch`)

Command, from the worktree root (the manifest and the out-dir are the fetched copies under the
repo's gitignored `data/`):

```
python3 -m research.kalshi.frankie_raw_mbo_benchmark.fetch_frankie_ledgers fetch \
  --manifest  <fetched copy>/delivery_33630348943/delivery_manifest.json \
  --out-dir   <fetched copy>/sunday_ledgers \
  --receipt   <fetched copy>/sunday_ledgers/FRANKIE_LEDGER_DELIVERY_RECEIPT.json
```

**Exit code 0. Wall 180.1 s** (2026-09-03T00:11:53Z to 00:14:53Z: five downloads plus the
10.6 GB gunzip). **Peak RSS 46,480 kB** - the 8 MB chunked download and the streaming gunzip
never hold a ledger in memory. No refusal.

stdout, verbatim:

```
VERIFIED         exact_member_ledger                   10,630,127,166 bytes  <fetched copy>/sunday_ledgers/exact_member_rows.jsonl
VERIFIED         exact_lifecycle_and_runway_ledger        265,048,572 bytes  <fetched copy>/sunday_ledgers/exact_lifecycle_rows.jsonl
VERIFIED         legacy_observable_rows                    29,329,182 bytes  <fetched copy>/sunday_ledgers/legacy_observable_rows.jsonl
receipt sha256 a27c8aa33331e69af8cd97be45cc9efc6751550dfc2caff8ab0ab08c2939ac0a
```

stderr: empty (the wrapper's own line only: `WRAPPER exit=0 wall_s=180.1 peak_rss_kb=46480`).

**The receipt** (`FRANKIE_LEDGER_DELIVERY_RECEIPT_V1`): `receipt_sha256`
`a27c8aa33331e69af8cd97be45cc9efc6751550dfc2caff8ab0ab08c2939ac0a` (the canonical hash the
schema defines, body with the field omitted); the receipt FILE as written hashes to
`47709f3c2cac2c0b02a82e8bff93330851ed74dcf4287d5a326e1f90b14ca868`. `fetched_at`
2026-09-03T00:14:53Z, `all_ledgers_verified` true, `manifest_sha256` equals the manifest's
(`68e588a7...`). Every status, expected against observed:

| ledger | status | gz bytes expected / observed | plain bytes expected / observed | plain sha256 expected = observed |
|---|---|---:|---:|---|
| exact_member_ledger | VERIFIED | 1,673,122,736 / 1,673,122,736 | 10,630,127,166 / 10,630,127,166 | `0fd3bbce...6f92a2` = same |
| exact_lifecycle_and_runway_ledger | VERIFIED | 22,196,720 / 22,196,720 | 265,048,572 / 265,048,572 | `039b6d0b...745d97` = same |
| legacy_observable_rows | VERIFIED | 2,198,595 / 2,198,595 | 29,329,182 / 29,329,182 | `3c75f8b4...c7bafa` = same |

| object | status (S3 ContentLength witness) | expected / observed bytes |
|---|---|---:|
| calculation_result.json | VERIFIED | 24,811,795 / 24,811,795 |
| exact_lifecycle_rows.jsonl.gz | VERIFIED | 22,196,720 / 22,196,720 |
| exact_member_rows.jsonl.gz | VERIFIED | 1,673,122,736 / 1,673,122,736 |
| legacy_observable_rows.jsonl.gz | VERIFIED | 2,198,595 / 2,198,595 |
| small_artifacts.tar.gz | VERIFIED | 760,403 / 760,403 |

Both non-ledger objects were fetched by the same command (they are `OTHER_OBJECTS` in the
module), so no separate `curl` was needed. Two checks the fetch does not take were taken by
hand and are recorded as observations, not as defects in the ledgers:

- `calculation_result.json` hashes to `58e8aef5dc7da112eb9aaffda35808f5f0c35a5239e98ba06f7d019a657c8970`,
  which EQUALS the box's `PLAIN_SHA256SUMS` entry for it. The receipt's status for this
  object is a LENGTH check only (`fetch` consults `PLAIN_SHA256SUMS` for the three ledgers and
  not for the two other objects, although the box's file carries a digest for
  `calculation_result.json` and `source_manifest.json`). **Finding F-feed-1 (minor, for the
  coordinator; `fetch_frankie_ledgers.fetch`, the object loop at the top of the function):**
  a digest witness that exists is not consulted for the result the section 6 gates read.
- `small_artifacts.tar.gz` has no digest witness anywhere (not in the manifest, not in
  `PLAIN_SHA256SUMS`); its observed sha256 is
  `e1a94267bc1489b182f95c2a6aee0ec6e0808a05fd0deb5ad3aa8e432ca3245e`, 43 entries: 10
  checkpoints + 10 gzipped adapter states, 19 spawn requests (`FRANKIE_NATIVE_RAW_MBO_SPAWN_REQUEST_V1`,
  arm `A_CLEAN`, six-key cutoff dicts), `PLAIN_SHA256SUMS`, `PLAIN_SIZES`. The two receipts
  inside are byte-identical to the copies published beside the manifest.
- `source_manifest.json` (2,711 bytes) is in the S3 listing and in `PLAIN_SHA256SUMS`
  (`74c74baa...`) but is NOT among the manifest's objects, because `_expected_objects` lists
  the three ledgers plus `OTHER_OBJECTS` only; it was therefore not delivered. **Finding
  F-feed-2 (minor, for the coordinator):** the run's source roster is not part of the
  delivery although the box receipted it.

Disk after the fetch: 12,351,208 kB under `sunday_ledgers/` (plain 10,924,504,920 bytes +
gzipped 1,697,518,051 bytes + the result, tarball and receipt); 14 GB free remained.

