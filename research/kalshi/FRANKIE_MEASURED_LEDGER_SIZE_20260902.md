# THE SIZE IS ONE FIELD: 94.7% OF EVERY BYTE IS `book_full` (measured 2026-09-02)

**Greg's question was "which of our fifteen or sixteen calcs is contributing to the size,
and what has zero value". The measurement answers it, and the answer is: NONE OF THEM.**

Exact, from the sink's own byte count over its own file, 50,001 real records, canary run
33596898227. No inference anywhere in these figures.

| | |
|---|---|
| bytes per record | **246,030 (240.3 KiB)** |
| `book_full`, ONE FIELD | **~11.64 GB of 12.30 GB = 94.7%** |
| `exact_member_ledger`, ONE LEDGER | 12.11 GB = 98.5% |
| **all sixteen calculations combined** | **~1.5%, about 190 MB** |
| Sunday Oct 3, 57,027 records | **14.0 GB** |
| full roster, 5,667,689 records | **1,394 GB** |

**So there is nothing to gain by dropping a calculation.** Retiring the single most expensive
one - `replenishment`, at 0.6% - would save 69 MB in 12.3 GB. Retiring all sixteen would save
1.5%. The entire size question has exactly one subject, and it is the per-group full book
snapshot.

**That subject is the one Greg already ruled on**: *"do not leave any of the book data out.
it may not seem relevant to you but it may to frankie."* So this is not a drop proposal. It
is the statement that the D60 conversation, when it happens, is about `book_full` and about
nothing else - and that Frankie's report should be aimed there.

## Four numbers of mine that this correct, and they were all wrong the same way

1. **24 KB/record** - taken from the canary's UPLOADED ARTIFACT, which `upload-artifact`
   compresses at level 6. Measured raw: **246 KB**. Off by 10x. This one cost a run and a
   filled 300 GB volume.
2. **215 KB/record** - quoted as measured; it was 232 GB of CloudWatch writes divided by a
   record count NOBODY EVER READ, inferred by applying a GitHub runner's throughput to an
   r6i.2xlarge. It happened to land close, which is luck and not method.
3. **9:1 compression** - invoked to explain error 1, and derived FROM the discrepancy it was
   explaining. Circular.
4. **"key names are 57.3% of a row"** - measured on a row I INVENTED, not on real data. On
   real rows key names are ~0.1%. **So nova key aliasing saves essentially nothing here**,
   and D67 must be read with that correction: the reducer's value is `plan_retrieval` and
   declared withholding, not compression.

Every one is the same defect: present, typed, plausible, and measuring something other than
what its name implied. It is the failure this branch exists to catch, produced four times by
the person looking for it.

## What follows for the plan

- **A day at a time is right and Sunday fits today.** 14.0 GB on a 300 GB volume, once the
  volume is cleared. No growth is needed for Sunday and none should be bought for it.
- **The full roster needs ~1.4 TB** unless `book_full` changes. That is now a measurement
  rather than an estimate.
- **The per-record constant in the box disk precheck is wrong** (`KIB_PER_RECORD = 215`).
  It should be 246, or better, read from this measurement.
- `Completion: EVIDENCE_ONLY` on the canary confirms what D68 records: no run calls Frankie,
  so the findings half is still an agent session over the staged request.

---

## Where the bytes went

- Verdict: **ACCEPTED** (failed gates: none)
- Completion: EVIDENCE_ONLY
- Groups / records: 40,242 / 50,001
- Save points: 2
- Source traversed: `glbx-mdp3-20211001.mbo.dbn.zst`
- Source traversed: `glbx-mdp3-20211003.mbo.dbn.zst`
- Source traversed: `glbx-mdp3-20211004.mbo.dbn.zst`
- Source traversed: `glbx-mdp3-20211005.mbo.dbn.zst`

- Exact ledger rows: **280,508**
- Exact ledger bytes: **12,301,736,545**
- Bytes **per record**: **246,030** (240.3 KiB)

  This is the figure that was wrong by 9x and cost a run: it was taken from a COMPRESSED artifact and called a disk requirement.

### By ledger (exact)

| ledger | rows | bytes | share |
|---|---:|---:|---:|
| exact_member_ledger | 40,242 | 12,113,675,715 | 98.5% |
| exact_lifecycle_and_runway_ledger | 226,411 | 169,866,829 | 1.4% |
| legacy_observable_rows | 13,855 | 18,194,001 | 0.1% |

### By emitting section (exact, merged across ledgers)

Merged across ledgers on purpose: reported per file, a section spread over three ledgers ranks below a smaller one concentrated in a single ledger.

| section | rows | bytes | share | bytes/record |
|---|---:|---:|---:|---:|
| exact_member_ledger | 40,242 | 12,113,675,715 | 98.5% | 242,269 |
| replenishment | 65,765 | 69,034,587 | 0.6% | 1,381 |
| absorption | 40,242 | 33,093,418 | 0.3% | 662 |
| ladder | 39,056 | 23,783,512 | 0.2% | 476 |
| queue | 19,229 | 23,732,971 | 0.2% | 475 |
| legacy_observable_rows | 13,855 | 18,194,001 | 0.1% | 364 |
| recurrence | 40,242 | 12,101,734 | 0.1% | 242 |
| lineage | 21,321 | 7,011,316 | 0.1% | 140 |
| episode | 140 | 826,335 | 0.0% | 17 |
| response | 276 | 134,180 | 0.0% | 3 |
| exhaustion | 70 | 88,029 | 0.0% | 2 |
| candidate | 70 | 60,747 | 0.0% | 1 |

### By field (SAMPLED, 1 row in 97) - these are ESTIMATES

Scaled from 2,890 sampled rows. Exact section totals are above; these are not exact and must not be quoted as if they were. They exist because the expensive thing is usually one field rather than one section.

| field | bytes (estimated) | share of ledger bytes (estimated) |
|---|---:|---:|
| book_full | ~11,644,347,637 | ~94.7% |
| book | ~197,474,152 | ~1.6% |
| activity | ~102,519,688 | ~0.8% |
| structure | ~43,390,816 | ~0.4% |
| activity_full | ~41,815,342 | ~0.3% |
| clocks | ~9,196,182 | ~0.1% |
| episodes | ~8,874,045 | ~0.1% |
| emitting_section | ~7,336,983 | ~0.1% |
| runs | ~6,907,176 | ~0.1% |
| family_id | ~6,461,364 | ~0.1% |
| emitted_on | ~6,396,180 | ~0.1% |
| source_role | ~6,130,012 | ~0.0% |
| capture_observations | ~5,973,066 | ~0.0% |
| session_phase | ~5,632,984 | ~0.0% |
| continuity_segment | ~4,638,928 | ~0.0% |
| instrument_id | ~4,304,472 | ~0.0% |
| source_day | ~4,141,900 | ~0.0% |
| adapter_revision | ~3,721,308 | ~0.0% |
| price_relation_basis | ~3,266,960 | ~0.0% |
| clock | ~3,181,794 | ~0.0% |
| price_relations | ~2,872,364 | ~0.0% |
| refill_attribution | ~2,572,731 | ~0.0% |
| closed_recv_ns | ~2,469,620 | ~0.0% |
| opened_recv_ns | ~2,469,620 | ~0.0% |
| recv_ns | ~2,462,733 | ~0.0% |
| self_restoration_policy | ~2,327,709 | ~0.0% |
| touch_state | ~2,250,012 | ~0.0% |
| side | ~2,153,788 | ~0.0% |
| interpretation_domain | ~1,847,268 | ~0.0% |
| schema | ~1,766,952 | ~0.0% |
| liquidity_kind_basis | ~1,751,626 | ~0.0% |
| census_view | ~1,725,824 | ~0.0% |
| causal_availability_clock | ~1,686,636 | ~0.0% |
| group_index | ~1,674,705 | ~0.0% |
| event_to_receive_latency_ns | ~1,673,153 | ~0.0% |
| disposition | ~1,657,536 | ~0.0% |
| same_side_replacement_quantity | ~1,613,498 | ~0.0% |
| opposite_side_retreat_quantity | ~1,613,304 | ~0.0% |
| runway_id | ~1,512,618 | ~0.0% |
| order_id | ~1,510,775 | ~0.0% |

Nothing here is a recommendation to drop anything. D60: a row is USED, or RETAINED and counted, or REFUSED loudly, and what to drop is discussed before it is done. This says only what each thing costs.

---

## S119 ADDENDUM: THE FIGURE IS CONFIRMED BY AN INDEPENDENT WITNESS (2026-09-02)

**Greg held the numbers open at S118 close - "i still feel the numbers need to be rechecked" -
and he was right to. The table above is measured, but by the SINK COUNTING ITS OWN WRITES.**
That is one party, not two.

**The second party is S3.** It recorded a `ContentLength` for every object of run 33596898227 at
PUT time, and it has no stake in the answer. The canary path copies the packet UNCOMPRESSED
(only the full-run path gzips), so those lengths are directly comparable.

| what was compared | result |
|---|---|
| every ledger object's S3 size vs `ledger_retention[*].bytes` | **equal, all three** |
| `layers.identity_receipt.total_mbo_records` | 50,001 |
| `traversal.records_seen` | 50,001 |
| `layers.identity_receipt.coverage.records_seen` | 50,001 |
| smallest ledger DOWNLOADED, sha256 vs the receipt's | **match** (`6ff73abc10faf65c...`) |
| **verdict** | **CONFIRMED** |

**Bytes per record: 246,030 (240.3 KiB), unchanged.** Numerator: S3 `ContentLength` summed over
every ledger object. Denominator: `traversal.records_seen`, agreeing with the manifest total and
the coverage receipt. Neither quantity is the sink's own tally. Evidence: workflow run
33602694575.

**So Sunday is still 14.0 GB and the full roster is still ~1.4 TB.** Nothing downstream moves.

### And the witness's first live run confirmed the wrong run

Worth more than the confirmation. Its default lookup took the NEWEST `calculation_result.json`
under the a-clean tree, which was a push-CI canary at run 33599514613, not the 50,001-record run
whose figure was in question. Every step passed. The verdict was green. **Nothing on the page
said which run had been examined**, so a green would have been read as item zero settled.

That is the fifth instance of the same defect on this branch, produced by the tool built to catch
the first four. The repairs are in D69; the transferable one is that **a verdict with no subject
is not a verdict**, and it is why the report now names the run and the record count in its own
heading, derived from the S3 keys rather than passed in by whoever asked the question.
