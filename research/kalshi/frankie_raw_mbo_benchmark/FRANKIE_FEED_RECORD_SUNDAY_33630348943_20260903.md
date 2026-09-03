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

**Rules held.** D87: nothing written to either of the two temporary locations the rule
forbids; every transient file lives under the repo's gitignored `data/` and the fetched
ledgers are deleted at the end (the receipts and manifest kept). D84: committed after every step and pushed to
`origin/persona/s122-feed-wired` only. D34: no artifact names a desktop path or either
temporary location. D37/D60/D76: counts and the largest individual items, never a mean alone; keep
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

## 2. Step 2 - the causal stream on the real ledgers (`native_causal_stream`)

```
python3 -m research.kalshi.frankie_raw_mbo_benchmark.native_causal_stream \
  --member-ledger    <fetched copy>/sunday_ledgers/exact_member_rows.jsonl \
  --lifecycle-ledger <fetched copy>/sunday_ledgers/exact_lifecycle_rows.jsonl \
  --legacy-ledger    <fetched copy>/sunday_ledgers/legacy_observable_rows.jsonl \
  --run-id 33630348943 --arm A_MEMORY \
  --receipt <fetched copy>/stream/stream_receipt_A_MEMORY_full.json --progress-every 5000
```

The FULL pass, first time, no `--limit`: **exit 0, `complete: true`, wall 569.3 s**
(2026-09-03T00:16:51Z to 00:26:21Z), **peak RSS 259,404 kB** for a 10.6 GB member ledger plus
the two sidecars (the withheld lifecycle rows are held in memory until exhaustion, which is
where the 259 MB is). stderr: eight progress lines (`delivered 5,000 groups; cutoff
1633298454057998545` ... `delivered 40,000 groups; cutoff 1633303339933468014`) and the
wrapper line. No refusal on any of the 43,569 groups: the receive clock never moved
backwards, every row declared `causal_availability_clock: "ts_recv_ns"`, every derived
clock chain was in order, and every per-group `FRANKIE_NATIVE_RAW_MBO_CAUSAL_GROUP_DELIVERY_V1`
receipt passed `validate_causal_group_delivery_receipt` for the 55 causal-stream layers of
arm `A_MEMORY`. Note on the arm (D86/D88): the ledger rows carry no arm field and the stream
compares none, so `--arm A_MEMORY` on the A_CLEAN-identity run is accepted without comment;
the arm selects the validator's layer set only.

**The stream receipt** (`FRANKIE_NATIVE_RAW_MBO_CAUSAL_STREAM_RECEIPT_V1`): `receipt_sha256`
`6a188eab9a8b1aff9ea9ded76d9c67cb1c4186c0f75573815a3dd33c0b4ea675`; the receipt FILE (1,092,915
bytes, it carries all 43,569 cutoffs) hashes to
`77842b5eaf52d38c12d94485ae6fab52fb2b4389792252d202f4c3897e77e3d5`. Registry sha256
`d6c72dfed8d76417679bf4fd78037eb889c27bf8fe7054b482d35ace55fad8aa`. Chain: genesis
`e3b0c442...` (sha256 of nothing) to `last_delivery_receipt_sha256`
`d65dccf7362ba12b18015cf6d876959f6187d8665ba7bce474dc0bf8ec907323`.

| quantity | value |
|---|---:|
| groups delivered | 43,569 (= the run's `groups_seen`, all F_LAST-closed) |
| bytes delivered (member line + attached sidecar lines) | 10,883,588,427; `sha256_delivered` `2ed11601ba679ce819df23a12ad8ddfd4966d829a66c08817158ff171f8f012e` |
| member ledger | 43,569 rows, 10,630,127,166 bytes, sha256 `0fd3bbce69311f571f7a5d681fc92539aecc9aedc0efe8fbf4ccc8176a6f92a2` - **identical to the delivery receipt's observed sha and to the sink's**: delivered byte-identical, D81 |
| first cutoff / last cutoff (ns) | 1633287605008387796 / 1633305596372071705 (2021-10-03 19:40:05 UTC to 2021-10-04 00:39:56 UTC) |
| cutoffs | 43,569, non-decreasing, **42,170 distinct** (1,399 groups share an F_LAST receive nanosecond with another group) |
| causal clocks basis | `groups_with_row_own` **0**, `groups_with_derived_from_legacy_clocks` **43,569** (every row predates `a540b2d`; three clocks derived, four declared NOT_ON_THIS_ROW - step 6) |
| legacy ledger | 22,380 read = 22,380 attached (29,329,182 bytes), 0 withheld, 0 late, identity holds |
| lifecycle ledger | 377,454 read = **267,922 attached** (224,132,079 bytes) + **109,532 withheld** + 0 pending; identity holds; **1,713 late arrivals** (available at or before the PREVIOUS cutoff, attached to the next group because the row behind a blocked row waits: head-of-line) |

**THE F-20 MEASUREMENT ON REAL DATA** (the number the clocks persona needs). Of the 377,454
lifecycle rows, **109,532 (29.0%) cannot be placed inside any group by their own clock**:

| reason | rows | detail |
|---|---:|---|
| `withheld_no_own_clock` | **43,569** | `mirror`: 43,569 - every `mirror` row emitted on `GROUP_CLOSE` names no receive clock at any depth |
| `withheld_close_occasion` | **65,960** | `mirror|STREAM_END` 43,569; `lineage|STREAM_END` 21,651; `queue|STREAM_END` 597; `response|STREAM_END` 91; `replenishment|STREAM_END` 51; `exhaustion|STREAM_END` 1 (no `SEGMENT_CLOSE` rows exist on this run) |
| `withheld_beyond_last_cutoff` | **3** | available after the last delivered cutoff (horizon-matured rows) |

Per section, what reaches the principal IN-STREAM against what the ledger holds (counted on
the ledger itself, 4.2 s): ladder 87,138 of 87,138; replenishment 73,429 of 73,480 (51
STREAM_END); recurrence 43,569 of 43,569; absorption 43,569 of 43,569; queue 19,408 of 20,005
(597 STREAM_END); response 539 of 630 (91 STREAM_END); episode 182 of 182; candidate 91 of 91;
**mirror 0 of 87,138** (43,569 no own clock + 43,569 STREAM_END); **lineage 0 of 21,651** (all
STREAM_END); **exhaustion 0 of 1** (STREAM_END). Sum of attached 267,925 less the 3 beyond the
last cutoff = 267,922, the receipt's figure. Sections `flow_substrate` (4.0) and
`detector_coverage` (4.0b) have NO rows on this run at all: the driver began retaining them
in `4096fcb`, after the box's code `2dd7044` (in the run prefix), which is why the crosswalk
reads them "0 rows on this run" (step 4).

**Finding F-feed-7 (for the clocks persona, the F-20 target list):** the mirror section's
`GROUP_CLOSE` rows are the only rows withheld for naming no clock, and they are half of the
second-largest lifecycle section; stamping them with the group's F_LAST receive clock at write
time (`native_mirror` / the sink) moves 43,569 rows in-stream. The 65,960 `STREAM_END` rows are
correctly withheld until exhaustion - their content is fixed at a close instant the row does
not carry - and `lineage` reaching him only after the stream ends is a property of how that
section is written, stated here so it is decided rather than discovered.

## 3. Step 3 - the size witness (`report_ledger_size.py`, `verify_ledger_size_witness.py`)

**3a. The size report.** `python3 -m research.kalshi.frankie_raw_mbo_benchmark.report_ledger_size
--result <fetched copy>/sunday_ledgers/calculation_result.json --output <fetched copy>/witness/size_report.md`.
**Exit 0**, no stderr, no refusal (the result carries the `ledger_retention` block the module
refuses without). What it rendered, exact where the module says exact:

- 443,403 exact ledger rows, **10,924,504,920 bytes**, **191,567 bytes per record** over 57,027
  records (the figure the module exists to state correctly).
- By ledger (exact): member 43,569 rows / 10,630,127,166 bytes (97.3%); lifecycle 377,454 rows /
  265,048,572 (2.4%); legacy 22,380 rows / 29,329,182 (0.3%).
- By emitting section (exact, merged across ledgers), largest first: the member ledger itself;
  replenishment 73,480 rows / 93,642,870; ladder 87,138 / 52,972,261; absorption 43,569 /
  35,840,608; legacy rows 22,380 / 29,329,182; queue 20,005 / 26,381,228; mirror 87,138 /
  20,375,362; recurrence 43,569 / 13,868,311; response 630 / 12,887,634; lineage 21,651 /
  7,108,056; episode 182 / 1,892,318; candidate 91 / 78,679; exhaustion 1 / 1,245.
- By field (SAMPLED 1 row in 97, 4,570 rows - estimates, marked so by the module): `book_full`
  ~10,131,179,453 bytes, ~92.7% of every ledger byte; `book` ~212 MB; `activity` ~114 MB;
  `activity_full` ~47.5 MB; `structure` ~47.1 MB; `change_points` ~30.5 MB.
- The read surface: 13,136 averaged companion rows, ALIASED, 12,365,788 bytes as written
  (17,914,881 unaliased; 5,549,093 saved, 31.0%, 55 names).
- Fed: 4.16 event-driven change points **88,071, `FED_BY_THE_TRAVERSAL`** - this run is on the
  D79 configuration; the "zero change points" sentence in the S121 handoff's section 4 describes
  run 33605852433, as the report's own note says. Candidates 91, episode rows 182, response
  tracks 91, queue rows applied 57,027, lineage nodes 21,651, recurrence sequences 43,569,
  ladder transitions 87,138, replenishment observations 49,197, absorption runways 43,569.

**3b. The independent witness.** `python3 -m research.kalshi.frankie_raw_mbo_benchmark.verify_ledger_size_witness
--result <the fetched result> --objects <S3 key -> size, built from the manifest run's s3_listing.json, 6 keys>
--box-sizes <basename -> plain bytes, built from the box's PLAIN_SIZES>
--observed-sha256 exact_member_ledger=0fd3bbce... --observed-sha256 exact_lifecycle_and_runway_ledger=039b6d0b...
--observed-sha256 legacy_observable_rows=3c75f8b4... --output <fetched copy>/witness/witness.md`.
**Exit 0 = CONFIRMED** (the module's vocabulary is CONFIRMED / CONTRADICTED / WITNESS_UNAVAILABLE;
the brief's "WITNESSED" is its CONFIRMED). Run witnessed, derived from the keys and not passed in:
`.../a-clean/full/2dd7044897f1a5c88872f6c395836a2671880ae6/33630348943-1`. Per ledger:

| ledger | sink bytes | witnessed bytes | witness used | delta | status |
|---|---:|---:|---|---:|---|
| exact_lifecycle_and_runway_ledger | 265,048,572 | 265,048,572 | BOX_WC_OVER_THE_PLAIN_FILE | +0 | CONFIRMED |
| exact_member_ledger | 10,630,127,166 | 10,630,127,166 | BOX_WC_OVER_THE_PLAIN_FILE | +0 | CONFIRMED |
| legacy_observable_rows | 29,329,182 | 29,329,182 | BOX_WC_OVER_THE_PLAIN_FILE | +0 | CONFIRMED |

S3 holds every ledger gzipped, so the witness used the box's `wc -c` over the plain file for all
three and says so ("the weaker witness"); S3's ContentLength witnessed the gzips at the fetch
(step 1). The denominator CONFIRMED: `layers.identity_receipt.total_mbo_records`,
`traversal.records_seen` and `coverage.records_seen` all 57,027. Content CONFIRMED on all three
(sink sha256 = downloaded sha256). Bytes per record 191,567, numerator and denominator both
named, neither the sink's own tally.

## 4. Step 4 - the crosswalk on the real result WITH receipts (`native_layer_crosswalk`)

S121 could only compute the crosswalk with no receipts at all. It was computed here four
ways, all exit 0 unless stated, all with `--result <the fetched result> --ledger-dir <the
fetched ledgers>`: (a) delivery receipt only, both arms (an attribution baseline); (b)
delivery + stream receipts, `--arm A_MEMORY`; (c) the same, `--arm A_CLEAN`; (d) as (b) with
`--enforce-gate`.

```
python3 -m research.kalshi.frankie_raw_mbo_benchmark.native_layer_crosswalk \
  --result <fetched copy>/sunday_ledgers/calculation_result.json \
  --delivery-receipt <fetched copy>/sunday_ledgers/FRANKIE_LEDGER_DELIVERY_RECEIPT.json \
  --stream-receipt <fetched copy>/stream/stream_receipt_A_MEMORY_full.json \
  --ledger-dir <fetched copy>/sunday_ledgers --arm A_MEMORY \
  --out <fetched copy>/crosswalk/crosswalk_A_MEMORY.md --json <fetched copy>/crosswalk/crosswalk_A_MEMORY.json
```

**The arm (D86/D88).** The crosswalk reads NO arm off the result (`crosswalk()` never consults
`layers.identity_receipt.arm` or `evidence_identity.arm`; verified by reading
`native_layer_crosswalk.py:1149-1240` and by grep). `--arm` selects group applicability only,
so `--arm A_MEMORY` on the A_CLEAN-identity run is accepted silently: the three
`a_memory_overlay` layers become applicable (PRODUCED_NOT_DELIVERED - no knowledge receipt
names them) and the one `a_clean_overlay` layer becomes NOT_APPLICABLE. That is the whole
effect of the identity mismatch: 77 applicable inputs instead of 75, 68 offenders instead of
66. Nothing was built or defaulted for A_CLEAN; (c) exists so the numbers are honest against
the result's own identity. **Finding F-feed-10 (coordinator):** an arm mismatch between the
flag and the result is neither refused nor reported by the crosswalk or the stream.

**Status counts** (identical between (a) and (b)/(c) except the mismatch column):

| count | S121 render (no receipts, A_CLEAN) | (a) delivery only, A_CLEAN | (c) delivery + stream, A_CLEAN | (b) delivery + stream, A_MEMORY |
|---|---:|---:|---:|---:|
| registered / applicable | 99 / 96 | 99 / 96 | 99 / 96 | 99 / 98 |
| inputs_applicable | 75 | 75 | 75 | 77 |
| inputs_delivered | 0 | 9 | 9 | 9 |
| inputs_not_delivered | 75 | 66 | 66 | 68 |
| DELIVERED | 0 | 9 | 9 | 9 |
| RECEIPTED_CARRIER_ABSENT | 0 | 45 | 45 | 45 |
| PRODUCED_NOT_DELIVERED | 60 | 6 | 6 | 8 |
| BOUND_TO_INVENTORY_DOCUMENT | 14 | 14 | 14 | 14 |
| NO_PRODUCER_FOUND | 1 | 1 | 1 | 1 |
| SEALED_UNPROVEN / SEALED_PROVEN | 9 / 0 | 9 / 0 | 9 / 0 | 9 / 0 |
| OUTPUT_PENDING / OUTPUT_FILED | 10 / 0 | 10 / 0 | 10 / 0 | 10 / 0 |
| SHADOW_DISABLED | 2 | 2 | 2 | 2 |
| carrier_claim_mismatches | 0 | 0 | 10 | 10 |
| crosswalk sha256 | `37ff36e8...` | `f379bfd0...` | `57174e81...` | `97213d87...` |

Render header of (b): delivery receipt `a27c8aa3...`, stream receipt `6a188eab...` (complete
`True`), knowledge / outputs / sealed proof `None`, member rows censused `None`, legacy keys
from `DELIVERED_LEDGER_FIRST_ROWS` (the crosswalk opened the delivered legacy file and read
its first 1,000 rows - the one place it reads a delivered ledger).

**The delta against the S121 no-receipt render** (`LAYER_CROSSWALK_SUNDAY_33630348943_RENDER_20260902.md`,
99 rows parsed by layer id):

- **A_CLEAN** against the S121 render (99 rows parsed): 54 of 99 layers changed status; transitions: PRODUCED_NOT_DELIVERED -> RECEIPTED_CARRIER_ABSENT: 45; PRODUCED_NOT_DELIVERED -> DELIVERED: 9.
  - PRODUCED_NOT_DELIVERED -> DELIVERED (9): `resilience_and_recovery`, `legacy_price`, `legacy_book_imbalance`, `derived_ancestry_gaps`, `derived_unresolved_age_chain_trajectory`, `prebirth_predecessor_at_risk_state`, `prebirth_unresolved_chain_extension_state`, `prebirth_ancestry_successor_opportunity`, `clock_prospective_discovery_confirmation`
  - PRODUCED_NOT_DELIVERED -> RECEIPTED_CARRIER_ABSENT (45): `canonical_sep_nov_2021_dbn_mbo_objects`, `october_first_source_window`, `canonical_predecessor_bootstrap_objects`, `native_acmrtfn_messages`, `snapshot_bootstrap_reset_messages`, `raw_source_identity_provenance_clocks_integrity`, `order_lifecycle_adds`, `order_lifecycle_cancels`, `order_lifecycle_modifies`, `order_lifecycle_replaces`, `order_lifecycle_trades`, `order_lifecycle_fills`, `order_lifecycle_clears`, `order_identity_transitions`, `contract_session_roll_state`, `full_bid_ask_depth`, `price_level_and_order_counts`, `fifo_queues`, `queue_age_and_survival`, `queue_concentration`, `orders_and_volume_ahead`, `spread_and_depth_imbalance`, `complete_state_reset_bootstrap_receipts`, `mechanics_actions_by_side_and_level`, `aggressor_and_native_signed_flow`, `depletion_and_replenishment`, `churn_and_queue_turnover`, `price_and_book_path`, `missingness_and_integrity_flags`, `legacy_native_signed_flow`, `legacy_per_second_roll20`, `legacy_structure_observables`, `derived_roll20_and_dipole_state`, `derived_d_family_geometry`, `derived_open_world_predecessor_state`, `derived_price_flow_book_paths`, `derived_v4_mechanics_fifo_features`, `derived_feature_availability_timestamps`, `prebirth_stopped_chain_false_context_controls`, `prebirth_negative_opportunity_cases`, `clock_event_time`, `clock_receive_time`, `clock_event_known_by`, `clock_feature_availability`, `clock_model_evaluation`
- **A_MEMORY** against the S121 render (99 rows parsed): 58 of 99 layers changed status; transitions: PRODUCED_NOT_DELIVERED -> RECEIPTED_CARRIER_ABSENT: 45; PRODUCED_NOT_DELIVERED -> DELIVERED: 9; NOT_APPLICABLE -> PRODUCED_NOT_DELIVERED: 3; PRODUCED_NOT_DELIVERED -> NOT_APPLICABLE: 1.

The 14 BOUND, the 1 NO_PRODUCER_FOUND (`clock_lock_time`), the 6 binding/capsule/extra-agent
PRODUCED_NOT_DELIVERED ("producer found; no knowledge receipt names this layer" - the
knowledge receipt is S122's slice 3, not yet landed), the 9 sealed, the 10 outputs and the 2
shadows are unchanged. **The stream receipt changed the status of no layer**; its only effect
was the mismatch column.

**What the 45 RECEIPTED_CARRIER_ABSENT rows actually are**, read off their evidence details:

- **36 - "(the result carries no field census)"**: every member-path carrier (`clocks.*`,
  `ts_event_ns`, `ts_recv_ns`, `book_full.*`, `activity.*`, `structure.*`, `integrity.*`, ...) is
  checked ONLY against `layers.exact_member_ledger.field_census` in the result
  (`observed_carriers`, `native_layer_crosswalk.py:960-965`), and this pre-census run has none.
  The fields are physically on every delivered row (step 6 read them on row 0; step 2
  delivered all 43,569). **Finding F-feed-4 (HIGH, knowledge persona, owner of the
  crosswalk):** with `--ledger-dir` pointing at the delivered member ledger the crosswalk
  never opens it - it opens only the legacy file (`:994-1004`) - so "carrier absent from the
  run" and "census absent from the result" compute to the same status and the same
  headline. On the re-run (census present) the 36 resolve themselves; the defect is that the
  status cannot tell the two apart. Least new code: census the delivered member ledger's
  first rows the way the legacy path does, or compute a distinct status.
- **4 - `raw_actions[]` "produced and dropped before the ledger"**: `native_acmrtfn_messages`,
  `order_lifecycle_adds`, `_cancels`, `_modifies` (F-30 on real data; the other five
  `order_lifecycle_*` and `order_identity_transitions` carry the same loss under the census
  wording).
- **5 - "0 rows on this run"**: `legacy_native_signed_flow`, `legacy_per_second_roll20`,
  `derived_roll20_and_dipole_state` (section `flow_substrate`, 4.0) and
  `prebirth_stopped_chain_false_context_controls`, `prebirth_negative_opportunity_cases`
  (section `detector_coverage`, 4.0b). Accurate: the run's ledger holds neither section
  (step 2), because the driver began retaining them in `4096fcb`, after the box's `2dd7044`.

**The 10 carrier-claim mismatches** (new with the stream receipt): the stream receipt's
`layer_carriers` claims ONE carrier set per GROUP (`order_lifecycle`, `full_book_fifo_queue`,
`microstructure_mechanics`, `causal_clocks` on `member`; `legacy_observable_crosswalk` on
`legacy`), while ten layers declare two: `order_lifecycle_trades` (member + legacy),
`queue_age_and_survival`, `aggressor_and_native_signed_flow`, `depletion_and_replenishment`,
`price_and_book_path` (member + lifecycle), `resilience_and_recovery` and
`clock_prospective_discovery_confirmation` (lifecycle only - and both are DELIVERED),
`legacy_native_signed_flow`, `legacy_per_second_roll20` (legacy + lifecycle),
`legacy_structure_observables` (member + lifecycle). **Finding F-feed-8 (knowledge persona
with the clocks persona):** `native_causal_stream.LAYER_CARRIERS` (per group) and
`native_layer_crosswalk.LAYER_PRODUCERS[*].ledgers` (per layer) disagree for these ten; the
per-group receipt therefore under-claims what two DELIVERED layers actually ride on.

**(d) The gate, enforced.** Same command as (b) with `--enforce-gate`: **exit 3.** The gate's
message, verbatim, and its offender list (68):

```
spawn refused for arm A_MEMORY: 68 of 77 applicable input layers are not DELIVERED: controlling_rt_mission=PRODUCED_NOT_DELIVERED, native_calculation_contract=PRODUCED_NOT_DELIVERED, anchored_knowledge_manifest=PRODUCED_NOT_DELIVERED, selected_same_arm_profile=PRODUCED_NOT_DELIVERED, a_memory_promoted_positive_capsule=PRODUCED_NOT_DELIVERED, a_memory_prior_lessons_package=PRODUCED_NOT_DELIVERED, a_memory_prior_package_proof=PRODUCED_NOT_DELIVERED, authoritative_s135_construction=BOUND_TO_INVENTORY_DOCUMENT, complete_s105_9_brain=BOUND_TO_INVENTORY_DOCUMENT, doctrine_reasoning_play_index_evidence=BOUND_TO_INVENTORY_DOCUMENT, lawful_prior_session_carry=BOUND_TO_INVENTORY_DOCUMENT, october_outcome_wall_enforcement=BOUND_TO_INVENTORY_DOCUMENT, learned_d_structures_and_families=BOUND_TO_INVENTORY_DOCUMENT, learned_dipoles_and_geometry=BOUND_TO_INVENTORY_DOCUMENT, learned_pair_triplet_recurrence=BOUND_TO_INVENTORY_DOCUMENT, learned_chains_extensions_reappearances_ancestry=BOUND_TO_INVENTORY_DOCUMENT, phase1_discoveries_structural_falsifiers=BOUND_TO_INVENTORY_DOCUMENT, phase2_findings_modules_timing_pox_negatives=BOUND_TO_INVENTORY_DOCUMENT, predecessor_ancestry_unresolved_chain_state=BOUND_TO_INVENTORY_DOCUMENT, historical_timing_lifespan_context=BOUND_TO_INVENTORY_DOCUMENT, learned_structure_proposal_index_material=BOUND_TO_INVENTORY_DOCUMENT, extra_agent_corrected_information_and_gap_diagnoses=PRODUCED_NOT_DELIVERED, canonical_sep_nov_2021_dbn_mbo_objects=RECEIPTED_CARRIER_ABSENT, october_first_source_window=RECEIPTED_CARRIER_ABSENT, canonical_predecessor_bootstrap_objects=RECEIPTED_CARRIER_ABSENT, native_acmrtfn_messages=RECEIPTED_CARRIER_ABSENT, snapshot_bootstrap_reset_messages=RECEIPTED_CARRIER_ABSENT, raw_source_identity_provenance_clocks_integrity=RECEIPTED_CARRIER_ABSENT, order_lifecycle_adds=RECEIPTED_CARRIER_ABSENT, order_lifecycle_cancels=RECEIPTED_CARRIER_ABSENT, order_lifecycle_modifies=RECEIPTED_CARRIER_ABSENT, order_lifecycle_replaces=RECEIPTED_CARRIER_ABSENT, order_lifecycle_trades=RECEIPTED_CARRIER_ABSENT, order_lifecycle_fills=RECEIPTED_CARRIER_ABSENT, order_lifecycle_clears=RECEIPTED_CARRIER_ABSENT, order_identity_transitions=RECEIPTED_CARRIER_ABSENT, contract_session_roll_state=RECEIPTED_CARRIER_ABSENT, full_bid_ask_depth=RECEIPTED_CARRIER_ABSENT, price_level_and_order_counts=RECEIPTED_CARRIER_ABSENT, fifo_queues=RECEIPTED_CARRIER_ABSENT, queue_age_and_survival=RECEIPTED_CARRIER_ABSENT, queue_concentration=RECEIPTED_CARRIER_ABSENT, orders_and_volume_ahead=RECEIPTED_CARRIER_ABSENT, spread_and_depth_imbalance=RECEIPTED_CARRIER_ABSENT, complete_state_reset_bootstrap_receipts=RECEIPTED_CARRIER_ABSENT, mechanics_actions_by_side_and_level=RECEIPTED_CARRIER_ABSENT, aggressor_and_native_signed_flow=RECEIPTED_CARRIER_ABSENT, depletion_and_replenishment=RECEIPTED_CARRIER_ABSENT, churn_and_queue_turnover=RECEIPTED_CARRIER_ABSENT, price_and_book_path=RECEIPTED_CARRIER_ABSENT, missingness_and_integrity_flags=RECEIPTED_CARRIER_ABSENT, legacy_native_signed_flow=RECEIPTED_CARRIER_ABSENT, legacy_per_second_roll20=RECEIPTED_CARRIER_ABSENT, legacy_structure_observables=RECEIPTED_CARRIER_ABSENT, derived_roll20_and_dipole_state=RECEIPTED_CARRIER_ABSENT, derived_d_family_geometry=RECEIPTED_CARRIER_ABSENT, derived_open_world_predecessor_state=RECEIPTED_CARRIER_ABSENT, derived_price_flow_book_paths=RECEIPTED_CARRIER_ABSENT, derived_v4_mechanics_fifo_features=RECEIPTED_CARRIER_ABSENT, derived_feature_availability_timestamps=RECEIPTED_CARRIER_ABSENT, prebirth_stopped_chain_false_context_controls=RECEIPTED_CARRIER_ABSENT, prebirth_negative_opportunity_cases=RECEIPTED_CARRIER_ABSENT, clock_event_time=RECEIPTED_CARRIER_ABSENT, clock_receive_time=RECEIPTED_CARRIER_ABSENT, clock_event_known_by=RECEIPTED_CARRIER_ABSENT, clock_feature_availability=RECEIPTED_CARRIER_ABSENT, clock_model_evaluation=RECEIPTED_CARRIER_ABSENT, clock_lock_time=NO_PRODUCER_FOUND
```

The (b) render is committed verbatim beside this record as
`LAYER_CROSSWALK_SUNDAY_33630348943_FED_RENDER_20260903.md` (sha256
`dae20966e936426c5ed55c41bcdb74048f45ae742c64ba6703595a2f664b522e`), registered as a RECORD.

## 5. Step 5 - the emitter against the real result and receipt (`emit_frankie_spawn`)

```
python3 -m research.kalshi.frankie_raw_mbo_benchmark.emit_frankie_spawn \
  --result <fetched copy>/sunday_ledgers/calculation_result.json \
  --delivery-receipt <fetched copy>/sunday_ledgers/FRANKIE_LEDGER_DELIVERY_RECEIPT.json \
  --output <fetched copy>/emit/FRANKIE_SPAWN_PROMPT_attempt.md
```

**Exit 2. REFUSED. No prompt written.** stderr, verbatim:

```
REFUSED: the mission on disk hashes to 2b10b24556e6544742e2343fa47d43ec3113c6b05fdb0a343665e97eae855cce but the run bound 027faa7d3d31936d3b026576c7694957319de2d94ef1d95aec5ce1fb5ec4a6f7. Section 10 requires this mission's exact bytes and SHA-256 to be the ones loaded into Frankie, so emitting would bind him to a document the run never saw. Restore the bound bytes, or re-run the traversal.
```

**Diagnosis.** The delivery receipt itself passed (`_load_delivery_receipt`: schema, own hash,
every exact ledger VERIFIED with an existing local path and an observed sha256), and the
verdict gate passed (`ACCEPTED`). The refusal is the mission-hash gate at
`emit_frankie_spawn.py:169`, which sits BEFORE the raw-MBO-marker gate (`:180`), the contract
gate (`:191`) and the field-census gates (`:362`, `:367`). S121's section 2 recorded the census
refusal for this same result; it is no longer the first gate to fire because the mission moved
under it during S121. The mission file's history, each blob hashed:

| commit | mission sha256 | subject |
|---|---|---|
| `53c4943` (2026-09-02) | `027faa7d...` = THE BOUND VALUE | Mission section 10: the receipt is a file contract, not a provider record |
| `34a0c16` (2026-09-02) | `ae5da7be...` | The raw-MBO question is in the mission, and the spawn refuses a mission that omits it |
| `f717d9b` (2026-09-02) | `2b10b245...` = ON DISK NOW | Mission: the principal computes the sixteen sections from the complete causal stream |

The calculation contract moved too: the run bound `6c460731...` and the file on disk hashes to
`822d2cfd...`, so the contract gate (`:191`) would refuse next even if the mission were restored.

**Produced, not asserted: the bound bytes are refused as well.** The two files were extracted
at `53c4943` with `git archive` into a directory under `data/` (no worktree, no checkout of the
repo) and `emit()` was called with `repo_root` pointing there - the function's own documented
parameter, nothing edited. Both files hashed to the bound values (`027faa7d...`, `6c460731...`).
Result, verbatim:

```
REFUSED: the mission at research/kalshi/agents/frankie_native_raw_mbo_oct45_realtime_mission_20260828.md does not carry '### 9a. The raw MBO', so it never asks the raw-MBO retention question and a spawn against it cannot answer it. D68 requires the report to cover the calcs AND the full raw MBO. Restore section 9a rather than spawning against a mission that omits it.
```

So the last run cannot be spawned against by the current emitter under ANY state of the mission
file: the bytes on disk fail section 10's hash, the bytes the run bound fail the section-9a
gate, and behind both sit the contract gate and the census gates that S121 expected. Nothing
was weakened to get past any of them. **This is the correct outcome and the drop-in's ITEM ONE
already says why**: only the Sunday re-run on the wired code binds a mission the emitter
accepts. **Finding F-feed-3 (observation for the knowledge persona, owner of
`emit_frankie_spawn`):** the gate order means a pre-edit result's census refusal is now masked
by the hash refusal, so the S121 sentence "the emitter refuses it (pre-census code)" is true
but no longer the refusal you will see. And **for the coordinator (D88):** the D88 seed is by
definition a pre-edit run, so the seed route must never pass through `emit()` - it is memory
content, not a spawn.

## 6. Step 6 - the seven clocks on a real row

The first line of the delivered `exact_member_rows.jsonl` (group_index 0, `source_day`
20211003, `session_phase` PRE_OPEN, `source_role` SCORED_FINDINGS_DAY, `continuity_segment`
18904, 99,306 bytes, 245 components, `event_group_complete_f_last` true, schema
`NG_MBO_V4_NATIVE_EVENT_FRAME_V1`, `adapter_revision`
`NG_EXHAUSTION_MBO_V4_STATE_ADAPTER_V2_20260823`) carries **48 top-level fields**. It carries
NO `causal_clocks` block and NO `causal_clocks_basis` (these exist only on rows written by the
S121 code, `a540b2d`); its clocks live in a five-field `clocks` object plus two top-level
timestamps, exactly as the crosswalk's `SEVEN_CLOCKS` diagnostic
(`native_layer_crosswalk.py:772`) describes the pre-S121 row. Read off the row itself:

| registry clock | on the OLD row? | field name(s) on this row | value on group 0 |
|---|---|---|---|
| clock_event_time | YES | `clocks.first_component_ts_event_ns`; `ts_event_ns` (the F_LAST record) | 1633277168182000000; 1633287604754563461 |
| clock_receive_time | YES | `clocks.first_component_ts_recv_ns`; `clocks.f_last_ts_recv_ns`; `ts_recv_ns` | 1633277168244072526; 1633287605008387796; 1633287605008387796 |
| clock_event_known_by | YES, group level | `clocks.first_lawful_availability_ns` (= F_LAST `ts_recv_ns`); `causal_availability_clock` = `"ts_recv_ns"` | 1633287605008387796 |
| clock_feature_availability | NO field of its own | the same `first_lawful_availability_ns` is reused by convention; no per-component max-of-contributing value | - |
| clock_prospective_discovery_confirmation | NO, not on the member row | lifecycle `episode` rows carry `recognized_recv_ns`, `candidate` rows `available_second` (the crosswalk reads it DELIVERED off those rows, step 4) | - |
| clock_model_evaluation | BY CONVENTION | `clocks.decision_ts_recv_ns` with `decision_basis` = `REPLAY_EARLIEST_LAWFUL_AVAILABILITY` and `f_last_to_decision_delay_ns` = 0; the 19 staged spawn requests in `small_artifacts.tar.gz` carry a six-key cutoff dict (`continuity_segment`, `first_lawful_availability_ns`, `group_index`, `recv_ns`, `session_phase`, `source_day`) and NO `clock_model_evaluation_ns` | 1633287605008387796 (delay 0) |
| clock_lock_time | NO | none; his own first-lock entry | - |

Other facts on the same row that the personas asked about: `raw_actions` is ABSENT (F-30
confirmed on the real row: the per-record A/C/M/R/T/F/N messages are not on the ledger);
`activity` and `activity_full` are keyed `'1','5','20','60','300'` - the fixed windows of D83,
present on the real row; `event_to_receive_latency_ns` is a per-component list of 245 entries
(62,072,526 ns for the first, 253,824,335 ns for the rest shown); `formation_latency_ns` =
`max_within_group_receive_gap_ns` = 10,436,764,315,270 ns (2.9 hours - group 0 is the pre-open
bootstrap group whose first component was received at 1633277168244072526 and whose F_LAST at
1633287605008387796); `ts_in_delta_ns` 0; `snapshot_bootstrap_only` false.

**What the wired stream does with such a row** (`native_causal_stream.py:497-508`, executed in
step 2 on all 43,569 rows): `causal_clocks` absent, so
`native_clocks.causal_clock_layers_from_legacy_clocks` (`native_clocks.py:382-412`) derives
THREE by registry id from the legacy object - event time (first component + F_LAST event
times), receive time (first component + F_LAST), event_known_by (`first_lawful_availability_ns`,
basis F_LAST receive of the group) - and declares FOUR `NOT_ON_THIS_ROW` with a null value:
feature availability, prospective discovery/confirmation, model evaluation, lock time. The
delivery is stamped `causal_clocks_basis` = `DERIVED_FROM_LEGACY_CLOCKS_OBJECT`, and the stream
receipt counts the groups on each basis (step 2). **Finding F-feed-5 (observation for the
clocks persona):** the old row DOES carry a model-evaluation instant with a declared basis
(`clocks.decision_ts_recv_ns` + `decision_basis`), and the legacy derivation declares
`clock_model_evaluation` NOT_ON_THIS_ROW rather than carrying that value under its basis. The
docstring says the four are "declared rather than filled with anything", so this is a choice
to confirm, not a defect to fix; it is recorded because the value is on the row.

## 7. Step 7 - the staging read-back (`native_staging read-back`)

**The honest state.** No principal artifact exists for run 33630348943: the principal was never
spawned against it (step 5 shows it cannot be, under any mission state), so there is no
`FRANKIE_NATIVE_RAW_MBO_PRINCIPAL_FINDINGS_V1` artifact and no output bundle to read back.
**No committed on-disk fixture exists either**: every read-back test builds its artifact,
bundle and result in a `tempfile` directory (`tests/outputs_bundle_fixture.py`,
`tests/test_native_staging.py::_stage(tmp)`, and the CLI test at `test_native_staging.py:830`
runs the module against that temporary directory). The only committed principal artifact in
the repository is another run's: `principal_runs/33605852433/frankie_principal_findings.json`
(`run_id` `frankie-a-clean-rt-33605852433-1`, `evidence_result_hash` `cb685e0e...`), whose
result is not committed (it lives on S3).

**Produced, not asserted: the refusal.** The read-back CLI was run once, as a cross-run
NEGATIVE test, with that committed artifact against THIS run's result. The expected refusal was
the evidence-hash mismatch (`cb685e0e...` is not `d2ab3feb...`). What fired was earlier:

```
python3 -m research.kalshi.frankie_raw_mbo_benchmark.native_staging read-back \
  --artifact research/kalshi/frankie_raw_mbo_benchmark/principal_runs/33605852433/frankie_principal_findings.json \
  --result <fetched copy>/sunday_ledgers/calculation_result.json \
  --out <fetched copy>/staging/read_back_attempt.json \
  --delivery-receipt <fetched copy>/sunday_ledgers/FRANKIE_LEDGER_DELIVERY_RECEIPT.json --no-report
```

**Exit 1.** stdout, verbatim:

```
REFUSED: calculation result at <fetched copy>/sunday_ledgers/calculation_result.json declares result_hash d2ab3feba0115a60088ae2a0efa8d2c173be4f911da85f82bbc0ed3375e9b3d9 and recomputes to ceaca0666b95bd6f98ab5bd65c71f507f3d803a16025cb733037cae9e35f7132; a result that does not hash to itself is tampered or partial and cannot receive findings
```

Nothing was written under `--out`. The result is neither tampered nor partial: it is the
byte-verified file the box wrote (sha256 `58e8aef5...` = the box's `PLAIN_SHA256SUMS`, step 1).

**Finding F-feed-6 (HIGH; owners: the launcher - `native_a_arm_launch.py`, D88's canonical
launcher, in the clocks persona's driver area - and the outputs persona for the read-back's
expectation).** The declared `result_hash` is computed INSIDE the runner,
`native_calculation_runner.py:920` (`result["result_hash"] = canonical_hash(result)` at the
end of `finalize()`, over `schema`, `verdict`, `completion_status`, `failed_gates`, `gates`
AS A LIST of gate dicts, `isolation`, `layers`, `partial_promotion_permitted`,
`verdict_note`). The launcher then mutates the result after `result = driver.finalize()`
(`native_a_arm_launch.py:539`) and never re-hashes: `:544` adds `ledger_retention`; **`:549`
REPLACES `result["gates"]` with a three-key dict** (`registry_gate`, `pre_call_layer_gate`,
`rt_surface_gate` - the file's `gates` is that dict); `:553` adds `evidence_identity`; `:554`
adds `slice`. Because the hashed `gates` list no longer exists in the file, NO recompute can
reproduce `d2ab3feb...`: tested by execution - omitting every subset of the eight candidate
top-level keys (256 combinations, 68 s) and expanding the aliased companion rows both fail to
reproduce it. Consequences: `native_staging.read_back` (`:518-519`) and the runner's own
`attach_principal_findings_to_result` (`native_calculation_runner.py:521-525`) REFUSE EVERY
LAUNCHER-WRITTEN RESULT, so the read-back wired at S121 cannot accept a real run's result
and never could; the tests pass because they build results through the runner and never
through the launcher - exactly the "wired, never fed" shape this feed exists to find. Also
noted: `evidence_identity.result_hash` (`752baa73...`) is the sha256 of the evidence dict
(`:490`), not of the result, under a name that says otherwise. **Not fixed here**: the
one-line re-hash after `:554` changes the identity every downstream record, spawn request
and render cites, and where the hash is taken (and whether `gates` should be replaced at
all) is the owner's decision under D60.

## 8. Step 8 - the closing table

| wired piece | fed on real data? | outcome | finding for the owner |
|---|---|---|---|
| `fetch_frankie_ledgers fetch` (delivery with receipt) | YES - the whole delivery, 12.35 GB | 3 ledgers VERIFIED, 5 objects VERIFIED, receipt `a27c8aa3...`, 180 s, 46 MB | F-feed-1, F-feed-2 (minor, coordinator): a digest witness not consulted for `calculation_result.json`; `source_manifest.json` receipted by the box, not delivered |
| `native_causal_stream` (the causal stream, per-group receipts, the registry validator) | YES - all 43,569 groups, 10.6 GB, first full pass ever | exit 0, complete, 569 s, 259 MB; member ledger delivered byte-identical (`0fd3bbce...`); 0 refusals; receipt `6a188eab...` | F-feed-7 (clocks persona, the F-20 target list): 109,532 of 377,454 lifecycle rows withheld - 43,569 mirror rows with no own clock, 65,960 STREAM_END, 3 beyond the last cutoff; F-feed-9: 1,399 groups share a cutoff nanosecond |
| `native_clocks.causal_clock_layers_from_legacy_clocks` (the seven clocks on pre-S121 rows) | YES - on every row | 3 derived, 4 declared NOT_ON_THIS_ROW on 43,569 of 43,569 groups; 0 row-own | F-feed-5 (clocks persona, observation): `clock_model_evaluation` declared absent although `clocks.decision_ts_recv_ns` + `decision_basis` are on the row |
| `report_ledger_size` | YES | exit 0; 191,567 bytes per record; `book_full` ~92.7% (sampled); 88,071 change points FED | none |
| `verify_ledger_size_witness` | YES | CONFIRMED on all three ledgers, denominator and content; exit 0 | none (vocabulary is CONFIRMED, not WITNESSED) |
| `native_layer_crosswalk` with receipts (`crosswalk`, `observed_carriers`, `gate_applicable_inputs`, `render_crosswalk_table`) | YES - delivery + stream receipts, both arms, gate enforced | A_MEMORY: 77 inputs, 9 DELIVERED, 68 not (45 RECEIPTED_CARRIER_ABSENT, 14 BOUND, 8 PRODUCED_NOT_DELIVERED, 1 NO_PRODUCER); gate exit 3 with 68 offenders; the stream receipt changed no status and raised 10 carrier-claim mismatches | F-feed-4 (HIGH, knowledge persona): member carriers are read only off the result's census, never off the delivered ledger, so 36 of the 45 absences are "no census" while the fields are on every delivered row; F-feed-8: the stream's group-level carrier claims disagree with 10 per-layer declarations; F-feed-10: no arm is read off the result, so the identity mismatch is silent |
| `emit_frankie_spawn` (the spawn emitter with the delivery receipt) | YES - real result and real receipt | REFUSED exit 2 at the mission-hash gate; the bound bytes refused at the 9a gate; unspawnable under any mission state, correctly | F-feed-3 (knowledge persona, observation): gate order masks S121's census refusal; the D88 seed must not route through `emit()` |
| `native_staging read-back` (`read_back`, `load_principal_artifact`, the crosswalk on the report) | NO - no principal artifact exists for this run; no committed fixture | cross-run negative test REFUSED exit 1 on the result's own hash, before the evidence-hash check | F-feed-6 (HIGH, launcher owner + outputs persona): the launcher replaces the hashed `gates` and adds four keys after the runner hashed; every real result fails the read-back's self-hash check |
| `native_principal_outputs` (the output bundle validator) | NO - nothing to validate; reached only through read-back | not exercised | none new (blocked behind F-feed-6) |

**D87 confirmation.** Nothing was written by this persona to either of the two temporary
locations D87 forbids. Every transient file - the fetched ledgers, receipts, logs, crosswalk outputs, the extracted
tarball, the mission bytes at `53c4943`, the record parts - lived under the repo's gitignored
`data/`. One disclosure: the FIRST long command (the fetch) was started through the harness's
background-task facility, which writes its own 22-byte bookkeeping line (`[exited with code
0]`) to a harness-owned path; the command's stdout and stderr were redirected to `data/`, so
that file holds nothing of this work. Every later long command was started with `nohup` in
the foreground shell so no further harness file was created. The session's temporary
directory held 0 entries at every check.

**Deleted at the close** (after the final commit was pushed): the plain and gzipped ledgers
under `data/s122/sunday_ledgers/` - `exact_member_rows.jsonl` (10,630,127,166),
`exact_member_rows.jsonl.gz` (1,673,122,736), `exact_lifecycle_rows.jsonl` (265,048,572),
`exact_lifecycle_rows.jsonl.gz` (22,196,720), `legacy_observable_rows.jsonl` (29,329,182),
`legacy_observable_rows.jsonl.gz` (2,198,595) - **12,622,022,971 bytes freed**. Kept: the
delivery manifest and its listing, `PLAIN_SIZES`, `PLAIN_SHA256SUMS`, `calculation_result.json`,
`small_artifacts.tar.gz`, the delivery receipt, the stream receipt, the crosswalk outputs and
the logs. The presigned URLs in the manifest remain valid until 2026-09-09T18:15:57Z, so the
delivery can be repeated by the same command until then.
