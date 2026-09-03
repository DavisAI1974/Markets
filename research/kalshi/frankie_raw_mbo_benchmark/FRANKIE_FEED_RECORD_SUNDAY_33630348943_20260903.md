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

## 2. Step 2 - the causal stream on the real ledgers (`native_causal_stream`)

(In progress at this commit: this section is written when the step completes.)

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

(In progress at this commit: this section is written when the step completes.)

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

(In progress at this commit: this section is written when the step completes.)

## 8. Step 8 - the closing table

(In progress at this commit: this section is written when the step completes.)
