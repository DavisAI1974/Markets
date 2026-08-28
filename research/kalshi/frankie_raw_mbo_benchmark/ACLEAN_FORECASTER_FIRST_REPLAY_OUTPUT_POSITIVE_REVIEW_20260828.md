# A-clean Forecaster — First-Replay Output Positive Review

## Status and bounded scope

This is a `BOUNDED_RETROSPECTIVE_OUTPUT_REVIEW` of the intact first A-clean native replay. It is not a full Forecaster run, a native-DBN replay, a scientific lock, an order recommendation, or an amendment to the frozen first lock. The review was read-only. It used only the authorized A-clean runtime outputs and the three authorized positive-only A-clean reports. No Step-1, reveal, scoring, A-memory, or other-arm material was used.

The useful result is positive: the first replay already contains two coequal forecasting surfaces without another full run.

1. The per-source-day post-F_LAST book summaries identify day-scale liquidity, sidedness, spread, and terminal-state regimes.
2. The exact event-group ledger, positive derivations, and FIFO checkpoints identify order lifecycles, cascade multiplicity, same-order depletion, recurrence, session resets, and lawful recognition clocks hidden by daily averages.

Differences between these surfaces are labeled `COMPLEMENTARY_SCOPE_DIFFERENCE`; they are not pooled across days, families, side structures, sessions, phases, or clock definitions.

## Exact provenance

### Review inputs

| Evidence tag | Exact path | SHA-256 |
|---|---|---|
| `DIRECTIVE` | `/workspace/scratch/b2678c426534/Markets/research/kalshi/agents/frankie_native_raw_mbo_forecaster_first_replay_review_20260828.md` | `c9895e296ecd24888aab96d9279f0190401c748d57f0fd7b21ed6bc33da83de4` |
| `SUMS` | `/workspace/scratch/da00127ac123/a-clean-runtime-33161766927/FINAL_FILE_SHA256SUMS` | `d1994ce1449144fd48e2e87930c59727da32d85cc1c9b2cc770d77781c4c6415` |
| `OBS` | `/workspace/scratch/da00127ac123/a-clean-runtime-33161766927/rt_observations.json` | `92961836fae2fa1e5b718cdcfcd81cd0f7e5dcc41e42b9a5f378f40b372f8d97` |
| `BUNDLE` | `/workspace/scratch/da00127ac123/a-clean-runtime-33161766927/evidence_bundle.json` | `50b2fce744ecdd0b18ba4c7c83603e058c202a55b6769546de470df17392183b` |
| `MANIFEST` | `/workspace/scratch/da00127ac123/a-clean-runtime-33161766927/source_manifest.json` | `24a47eb1631a17ab391eb61ad73051f694b4c564dddec4050518e730efe40767` |
| `PROGRESS` | `/workspace/scratch/da00127ac123/a-clean-runtime-33161766927/progress.json` | `0522890a504eca224039acdb016eb30d3263730b54ebb6c2018d093e00e32851` |
| `LAUNCH` | `/workspace/scratch/da00127ac123/a-clean-runtime-33161766927/launch_receipt.json` | `3f73f30e575736f567beb60f57abe9489017d25a9e818a590739e3ee57792537` |
| `LOCK` | `/workspace/scratch/da00127ac123/a-clean-runtime-33161766927/RT_FIRST_LOCK.json` | `67fcee21fcf1c42cbf1ae6bb9cd6534eb3699e23c2e52c65afe8dd25e00a2b4c` |
| `FREEZE` | `/workspace/scratch/da00127ac123/a-clean-runtime-33161766927/RT_FREEZE_RECEIPT.json` | `5d0aa44f5e953d411a04c48cf138a0d3c8cf9a417411cd0b69fd9712cf4802f9` |
| `LEDGER` | `/workspace/scratch/da00127ac123/a-clean-runtime-33161766927/native-evidence-groups.jsonl.gz` | `b7399305906936fb89c5028fe2f32e291aefc2f9be14e421e6afc14b27acd038` |
| `CHECKPOINTS` | `/workspace/scratch/da00127ac123/a-clean-runtime-33161766927/checkpoints/{adapter-state,checkpoint,controller-state}-000000..000017` | Every exact file hash is enumerated by `SUMS`; 18 files exist in each series. |
| `DERIVED+` | `/workspace/scratch/b2678c426534/Markets/research/kalshi/frankie_raw_mbo_benchmark/ACLEAN_RT_NATIVE_MBO_POSITIVE_DERIVED_FINDINGS_20260828.md` | `8c67fdbf5d2995657a0020200632def3fe1b2d70f1b4573c906b3a124959f8af` |
| `INTERIM+` | `/workspace/scratch/b2678c426534/Markets/research/kalshi/frankie_raw_mbo_benchmark/ACLEAN_RT_ACTUAL_FRANKIE_INTERIM_POSITIVE_REPORT_20260828.md` | `f09c94a7453ecf1faa756d255969ad9258ec766f9115d2452caa76408bdc9987` |
| `OPPORTUNITIES+` | `/workspace/scratch/b2678c426534/Markets/research/kalshi/frankie_raw_mbo_benchmark/ACLEAN_RT_ACTUAL_FRANKIE_NONAVERAGED_EXTRACTION_OPPORTUNITIES_20260828.md` | `52c17005a947586def2dea79a579e48f80524264e970a50b08fce21340eea046` |
| `METRIC_CODE` | `/workspace/scratch/b2678c426534/Markets/research/kalshi/frankie_raw_mbo_benchmark/a_clean_rt_replay_20260828.py` | `0bb2c89ec0acb80d5725e574e521c0844962d9f66b4b60077956bb5cb1cb2c8e` |
| `STATE_CODE` | `/workspace/scratch/b2678c426534/Markets/research/ng_exhaustion_mbo_v4_state_adapter_20260820.py` | `4a80e3e4b83867046d318ba97d350c2d7aca22e9d182d98399d01eeacc72d3ce` |

The runtime identity is run `frankie-a-clean-rt-33161766927-1`, packet `aclean-rtpkt-be26a48cef30ad9abe9e`, canonical manifest hash `a98a454ef5a88d6f3ee1213370d6df530ab2946ec9cde47171b0d7aa19f4e2ba`, observation hash `3a87835b9b9961ac8402a7d3442dfd9c21cd61279bd0095c84d2cde3963efa2b`, first-lock hash `ef728adf5ae2064c242f0e72acbf95f1d5b586a3f1845bed9ac9577ea998dd42`, and locked checkpoint `2e10b3f2534aaf697129831608a8e65fd9c4ac8ca92ec171c2a012fe8593b384`. `[LOCK; FREEZE; PROGRESS]`

### Canonical native inputs and source strata

| Source day | Role | Canonical source name | Bytes | Native records | F_LAST-closed groups | Source SHA-256 |
|---|---|---|---:|---:|---:|---|
| 2021-10-01 | `WARMUP_DEVELOPMENT` | `glbx-mdp3-20211001.mbo.dbn.zst` | 25,628,861 | 1,504,374 | 1,118,738 | `e6b4ec01bd9b34d57cb22c770b5d49c756e7f41a658f081823d923004a0121b2` |
| 2021-10-03 | `WARMUP_DEVELOPMENT` | `glbx-mdp3-20211003.mbo.dbn.zst` | 973,355 | 57,027 | 43,569 | `4380bd9ba83a5badc4839e12785aa464817b87e3fac11176b951e7b474446d88` |
| 2021-10-04 | `HELD_OUT_BLIND` | `glbx-mdp3-20211004.mbo.dbn.zst` | 34,300,424 | 1,994,358 | 1,506,255 | `8ed47cc0a68cf40cae9fde45e158142978076e60d3f9fc7cf940196babfddc0a` |
| 2021-10-05 | `HELD_OUT_BLIND` | `glbx-mdp3-20211005.mbo.dbn.zst` | 36,192,430 | 2,111,930 | 1,588,041 | `a4a12f9578da762412884e7f559a123361eaa3a153bec0db59dfb3ba6224a874` |

Totals are 5,667,689 native records and 4,256,603 closed event groups; held-out totals are 4,106,288 records and 3,094,296 groups. The progress denominator is `HASH_BOUND_NATIVE_MBO_RECORD_COUNT`; completion is 100%, the terminal group is closed, full-depth FIFO state is reconstructed, and raw actions are preserved exactly once. `[MANIFEST; BUNDLE; PROGRESS; LOCK]`

## Population, metric, denominator, and clock contract

- Scientific unit for the exact ledger: one distinct F_LAST-closed native event group.
- Availability/causal clock: group-close `ts_recv_ns`, equal to the final action receive time for all 3,094,296 held-out groups in the authorized independent positive verification. Event/source time, first-component receive time, and F_LAST availability remain separate. `[INTERIM+]`
- Daily summary population: one post-group full-book snapshot per closed event group in exactly one source file/day. `METRIC_CODE` increments each metric after a completed frame and divides its sum by its own `n`; all eight emitted metrics have `n = event_groups` in these outputs.
- `spread`: emitted `best_ask - best_bid` in raw price units. `depth_imbalance_full = (bid_depth_full - ask_depth_full) / (bid_depth_full + ask_depth_full)`. Full depths sum resting size; full order counts count resting order identities; full price-level counts count occupied prices. `[STATE_CODE]`
- `first`, `last`, `min`, and `max` are exact within-source-day values on the post-F_LAST snapshot stream. `mean` is the arithmetic mean over that day's closed-group snapshots; it is not a time-weighted mean.
- Every exact family/subfamily calculation below stays within source day and exact content definition. No count or mean is pooled across days, mirrored sides, sessions, phases, or clocks.

## Complete daily averaged-book channel

### Spread and full-depth imbalance

Values are exact output bytes rounded here to nine decimal places for display. Denominator `n` is the day's event-group count in the source table above.

| Day | Role | Metric | First | Last | Min | Max | Arithmetic mean | `n` |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 2021-10-01 | warmup | spread | 0.003000000 | 0.023000000 | 0.001000000 | 0.023000000 | 0.002598022 | 1,118,738 |
| 2021-10-01 | warmup | full-depth imbalance | 0.092565947 | 0.078886311 | -0.098496241 | 0.206649283 | 0.056964194 | 1,118,738 |
| 2021-10-03 | warmup | spread | 0.023000000 | 0.002000000 | -0.060000000 | 0.056000000 | 0.005698019 | 43,569 |
| 2021-10-03 | warmup | full-depth imbalance | 0.078886311 | 0.058006941 | -0.021144920 | 0.171483622 | 0.065535499 | 43,569 |
| 2021-10-04 | held-out | spread | 0.002000000 | 0.003000000 | 0.001000000 | 0.090000000 | 0.002263499 | 1,506,255 |
| 2021-10-04 | held-out | full-depth imbalance | 0.058006941 | 0.210909091 | -0.191527715 | 0.326687117 | 0.121055981 | 1,506,255 |
| 2021-10-05 | held-out | spread | 0.003000000 | 0.003000000 | -0.033000000 | 0.043000000 | 0.002218553 | 1,588,041 |
| 2021-10-05 | held-out | full-depth imbalance | 0.210909091 | 0.315686275 | 0.012240250 | 0.492340042 | 0.221155480 | 1,588,041 |

### Full depth, order count, and occupied-price count

| Day | Metric | First | Last | Min | Max | Arithmetic mean | `n` |
|---|---|---:|---:|---:|---:|---:|---:|
| 2021-10-01 | bid depth | 1,139 | 465 | 465 | 1,916 | 1,573.439 | 1,118,738 |
| 2021-10-01 | ask depth | 946 | 397 | 397 | 1,831 | 1,405.284 | 1,118,738 |
| 2021-10-01 | bid orders | 449 | 154 | 154 | 871 | 669.550 | 1,118,738 |
| 2021-10-01 | ask orders | 336 | 90 | 90 | 743 | 511.643 | 1,118,738 |
| 2021-10-01 | bid levels | 311 | 121 | 121 | 458 | 377.412 | 1,118,738 |
| 2021-10-01 | ask levels | 225 | 76 | 76 | 357 | 295.212 | 1,118,738 |
| 2021-10-03 | bid depth | 465 | 1,067 | 465 | 1,121 | 952.288 | 43,569 |
| 2021-10-03 | ask depth | 397 | 950 | 397 | 1,001 | 837.974 | 43,569 |
| 2021-10-03 | bid orders | 154 | 451 | 154 | 461 | 383.908 | 43,569 |
| 2021-10-03 | ask orders | 90 | 354 | 90 | 382 | 288.009 | 43,569 |
| 2021-10-03 | bid levels | 121 | 304 | 121 | 329 | 287.215 | 43,569 |
| 2021-10-03 | ask levels | 76 | 240 | 76 | 262 | 219.899 | 43,569 |
| 2021-10-04 | bid depth | 1,067 | 999 | 556 | 1,819 | 1,485.381 | 1,506,255 |
| 2021-10-04 | ask depth | 950 | 651 | 326 | 1,663 | 1,162.397 | 1,506,255 |
| 2021-10-04 | bid orders | 451 | 394 | 169 | 804 | 621.512 | 1,506,255 |
| 2021-10-04 | ask orders | 354 | 272 | 87 | 743 | 489.025 | 1,506,255 |
| 2021-10-04 | bid levels | 304 | 272 | 125 | 469 | 358.664 | 1,506,255 |
| 2021-10-04 | ask levels | 240 | 197 | 74 | 355 | 270.886 | 1,506,255 |
| 2021-10-05 | bid depth | 999 | 1,342 | 672 | 2,553 | 1,809.887 | 1,588,041 |
| 2021-10-05 | ask depth | 651 | 698 | 253 | 1,744 | 1,156.146 | 1,588,041 |
| 2021-10-05 | bid orders | 394 | 469 | 225 | 929 | 723.815 | 1,588,041 |
| 2021-10-05 | ask orders | 272 | 293 | 78 | 759 | 510.784 | 1,588,041 |
| 2021-10-05 | bid levels | 272 | 314 | 162 | 480 | 390.580 | 1,588,041 |
| 2021-10-05 | ask levels | 197 | 197 | 58 | 325 | 257.847 | 1,588,041 |

All values in the two tables are from `OBS#/source_metrics`; source roles and denominators bind them to `MANIFEST` and `BUNDLE`.

## Positive information in the averaged channel

### A1 — held-out October 5 is a more bid-supported full-book regime

For the October 4 and October 5 held-out populations kept separate by day:

| Derived metric | 2021-10-04 (`n=1,506,255`) | 2021-10-05 (`n=1,588,041`) | October 5 minus October 4 |
|---|---:|---:|---:|
| Mean full-depth imbalance | 0.121056 | 0.221155 | +0.100099, or +10.010 percentage points |
| Mean bid depth | 1,485.381 | 1,809.887 | +324.505 (+21.847%) |
| Mean ask depth | 1,162.397 | 1,156.146 | -6.251 (-0.538%) |
| Bid/ask depth ratio of means | 1.277861 | 1.565449 | +0.287588 |
| Mean bid orders | 621.512 | 723.815 | +102.302 (+16.460%) |
| Mean ask orders | 489.025 | 510.784 | +21.759 (+4.449%) |
| Bid/ask order-count ratio of means | 1.270921 | 1.417067 | +0.146146 |
| Mean bid levels | 358.664 | 390.580 | +31.916 (+8.899%) |
| Mean ask levels | 270.886 | 257.847 | -13.039 (-4.813%) |
| Bid/ask level-count ratio of means | 1.324041 | 1.514774 | +0.190733 |
| Mean spread | 0.002263499 | 0.002218553 | -0.000044946 (-1.986%) |

Calculations are `October5_mean - October4_mean`, relative change `100 * (October5_mean / October4_mean - 1)`, and explicitly labeled ratios of daily means—not means of per-group ratios. This is a day-regime comparison, not a pooled estimator. `[OBS]`

The sign envelope is also informative: October 4 full-depth imbalance spans `[-0.191528, 0.326687]`, while October 5 spans `[0.012240, 0.492340]`. Thus every emitted October 5 post-group full-depth snapshot remains bid-positive by this metric. The corresponding endpoint evolution is `0.058007 → 0.210909` on October 4 (+0.152902) and `0.210909 → 0.315686` on October 5 (+0.104777). `[OBS#/source_metrics/2..3/depth_imbalance_full]`

**Forecasting hypothesis A1.** Within a future fixed day/session/phase, jointly high full-depth imbalance, bid/ask depth ratio, bid/ask order ratio, and bid/ask level ratio should define a stronger bid-supported liquidity regime than any single feature alone. A useful falsifier is an exact same-stratum transition in which those four measures rise but causal signed execution/cancel flow and later price response move persistently in the opposite direction.

### A2 — spread scale and transient spread states are separate information

The held-out mean spread is close across days (0.002263499 versus 0.002218553), while the exact within-day extrema are much wider: October 4 max 0.090000, 39.761 times its mean; October 5 max 0.043000, 19.382 times its mean, and its minimum is -0.033000. October 3 also carries a negative minimum (-0.060000). `[OBS]`

**Forecasting hypothesis A2.** Treat ordinary spread scale and wide/crossed transient states as separate causal phases. The daily mean is a scale prior; exact extrema and their future ledger-resolved group references are transition candidates. The hypothesis is falsified for a candidate family when spread excursions do not persist beyond the triggering F_LAST or do not change executable queue conditions in that same session/phase.

### A3 — source boundaries preserve exact book-state anchors

For all eight book metrics, each next source's `first` equals the preceding source's `last`: October 1→3, October 3→4, and October 4→5. For example, the October 4 terminal tuple `(spread, imbalance, bid depth, ask depth, bid orders, ask orders, bid levels, ask levels)` is `(0.003, 0.210909091, 999, 651, 394, 272, 272, 197)`, exactly the October 5 initial tuple. `[OBS]`

This is useful for deterministic boundary attribution: source-day means remain separate, while the exact inherited boundary state can seed next-source causal analysis. No cross-day arithmetic smoothing is implied.

### A4 — message-side incidence aligns with the held-out depth regime

Action totals equal native-record totals on every source day, a positive accounting identity. `actions per group = native records / event groups`. Side skew below is `(B - A) / (B + A)`, and modify share is `M / native records`. `[OBS; MANIFEST]`

| Day | Groups | Records/actions | Actions/group | Max group actions | Side A / B / N | Nonneutral side skew | Modify share |
|---|---:|---:|---:|---:|---|---:|---:|
| 2021-10-01 | 1,118,738 | 1,504,374 | 1.344706 | 786 | 646,540 / 658,568 / 199,266 | +0.922% B | 9.359% |
| 2021-10-03 | 43,569 | 57,027 | 1.308889 | 245 | 23,780 / 24,874 / 8,373 | +2.249% B | 8.661% |
| 2021-10-04 | 1,506,255 | 1,994,358 | 1.324051 | 806 | 841,180 / 896,553 / 256,625 | +3.187% B | 8.439% |
| 2021-10-05 | 1,588,041 | 2,111,930 | 1.329896 | 667 | 871,452 / 967,136 / 273,342 | +5.204% B | 9.056% |

October 5's nonneutral B-side message skew exceeds October 4 by 2.018 percentage points while mean full-depth imbalance exceeds it by 10.010 points. Modify share rises 0.617 point. Add/cancel counts remain closely balanced but net positive: `692,258 - 691,592 = 666` on October 4 and `724,424 - 723,662 = 762` on October 5. Each source also contains exactly one `R` action. `[OBS]`

This is a paired regime clue rather than a cross-day correlation estimate: within future fixed strata, message-side skew, modify intensity, and full-book state should be tested together at the same F_LAST cutoff.

## Positive information in controller, checkpoint, and FIFO channels

### C1 — checkpoint chain supplies exact causal state cuts

The 18 runtime checkpoints progress from sequence 0 at zero records through interval and raw-file boundaries to sequence 15 at the October 5 boundary, sequence 16 `PRE_CALL_RT_FREEZE`, and sequence 17 `POST_CALL_RT_FREEZE`. The terminal three adapter states have the identical canonical state hash `8d0c9cacb7d02212e6b13198b99ea240a7d2dd42e47c7e9c2a6422d560ee603a` at 5,667,689 records and 4,256,603 groups, while the runtime checkpoint hashes remain chained through distinct phases. The locked checkpoint is sequence 17. `[CHECKPOINTS; BUNDLE; PROGRESS; LOCK; SUMS]`

All held-out adapter cuts below are exact F_LAST-closed `ts_recv_ns` states. B/A values are derived directly by enumerating the snapshot's resting `orders`; level counts enumerate `levels.B/A`; the activity tail is the resident causally ordered window.

| Seq | Receive watermark UTC | Records | Closed groups | Orders B/A | Depth B/A | Levels B/A | Activity members | Canonical adapter-state hash |
|---:|---|---:|---:|---:|---:|---:|---:|---|
| 5 | 2021-10-03 23:59:56.372071705 | 1,561,401 | 1,162,307 | 451 / 354 | 1,067 / 950 | 304 / 240 | 417 | `9e9e0809dfef23124b9ffd15559b85685edbe8b6d2abdee2bbebd4152eaa3165` |
| 6 | 2021-10-04 13:00:15.378984279 | 2,000,000 | 1,504,074 | 661 / 372 | 1,593 / 1,015 | 408 / 231 | 20,961 | `1345e460fd612f9a6eb64ec392c3f9f0fed812cfabcc2c209ce8c85856e4bcf5` |
| 7 | 2021-10-04 14:24:33.968703925 | 2,500,000 | 1,863,686 | 701 / 523 | 1,659 / 1,143 | 389 / 269 | 31,205 | `7f2d6ffc3f67744d1dfc0ca9587be30a3e9d398ba377fc4dbfe77901c17df675` |
| 8 | 2021-10-04 16:03:20.010017707 | 3,000,001 | 2,238,465 | 695 / 442 | 1,651 / 1,061 | 392 / 248 | 11,352 | `2dbfe51546a95cdd264801fca522385f3bdf8deb38efb0d82e153ac0a4ff295c` |
| 9 | 2021-10-04 20:00:50.092318691 | 3,500,000 | 2,625,154 | 589 / 448 | 1,479 / 1,222 | 334 / 241 | 4,229 | `06b555967349f6bd35f088957edd91db2949eae057e72067aa6ef0fd37bead0c` |
| 10 | 2021-10-04 23:59:59.955312214 | 3,555,759 | 2,668,562 | 394 / 272 | 999 / 651 | 272 / 197 | 549 | `cb5e43b2e4583610fe95386c70f6000e1e990ca8c217c8d548bd9154310ded4f` |
| 11 | 2021-10-05 12:27:13.386623062 | 4,000,000 | 3,024,930 | 702 / 383 | 1,659 / 891 | 393 / 233 | 15,346 | `e7d13b5e406a4afa4dabda00cffa0f414347c717ba5aad4e928e731f79cdef75` |
| 12 | 2021-10-05 14:14:37.613182023 | 4,500,000 | 3,388,782 | 746 / 626 | 1,862 / 1,283 | 405 / 298 | 26,010 | `11baa5bc4f3071cc0378f59e7dd11fc7b1ac6ec28e9dfb20de32a16a80234d24` |
| 13 | 2021-10-05 16:58:10.609617777 | 5,000,000 | 3,760,999 | 758 / 543 | 1,942 / 1,246 | 406 / 257 | 20,808 | `59bb52d2eb2ba2c8e54114ef8351161329a4d171c5bf8bbe9e33fe159c6bfaeb` |
| 14 | 2021-10-05 18:37:59.625368811 | 5,500,000 | 4,127,880 | 783 / 556 | 1,933 / 1,291 | 402 / 232 | 10,964 | `914573fa90b77c4e0b74ffc153f9249856994e1c1cd3a67ec66b22919ee2e1f6` |
| 15 | 2021-10-05 23:59:59.954928144 | 5,667,689 | 4,256,603 | 469 / 293 | 1,342 / 698 | 314 / 197 | 310 | `8d0c9cacb7d02212e6b13198b99ea240a7d2dd42e47c7e9c2a6422d560ee603a` |

Each resident order preserves side, raw price, size, order ID, `priority_recv_ns`, `priority_sequence`, and `last_update_recv_ns`; each level preserves FIFO order IDs; each activity member preserves action, side, price, size, size delta, priority-loss flag, missing-reference flag, touch flag, and receive clock. The observed activity spans at these cuts are about 296.189–299.984 seconds, making the snapshot and its recent causal flow jointly available. `[CHECKPOINTS; OPPORTUNITIES+]`

**Forecasting hypothesis C1.** Within one checkpoint/day/side/price-level/activity-family stratum, combine exact volume ahead and priority age with arithmetic companions for order size, age, action size, and size delta. This can distinguish large displayed depth that is concentrated in a few orders from depth dispersed across many FIFO members. A falsifier for a queue-runway hypothesis is exact member survival or replenishment inconsistent with its claimed depletion stage.

### C2 — the controller summaries expose both typical state and burst envelope

Source-day maximum group sizes are 786, 245, 806, and 667 actions for October 1, 3, 4, and 5 respectively. These maxima coexist with 1.309–1.345 actions per group, proving a heavy multiplicity tail in the first-run channel. Exact held-out burst members already characterized in `OPPORTUNITIES+` contain 253 actions at group 1,754,546 and 274 at group 3,829,652, with 5,684,808 ns and 8,961,789 ns formation times. Those exemplars are not asserted to be the per-day maxima; they are exact content-rich members inside the burst envelope.

**Forecasting hypothesis C2.** Preserve large groups as exact clusters, then compute averages only among identical action-string, side-string, day, session, phase, and clock strata. Burst action count, number of touched prices/orders, and first-receive-to-F_LAST formation time are candidate processing-intensity and absorption features.

## Coequal exact event-group information

### E1 — reproducible post-fill disposition families

| Exact family | Mechanical definition | 2021-10-04 count / incidence | 2021-10-05 count / incidence | Positive invariant |
|---|---|---:|---:|---|
| `TFCN` | trade, fill, same-ID cancel, neutral close | 38,510 / 2.5567% | 39,766 / 2.5041% | 78,276/78,276 groups preserve fill ID into cancel |
| `TFM` + `TFMN` | trade, fill, same-ID modify, optional neutral close | 8,083 / 0.5366% | 8,438 / 0.5313% | 16,521/16,521 groups preserve fill ID into modify |
| `TFFCCN` | one trade, two fills, two matching cancels, neutral close | 7,037 / 0.4672% | 7,522 / 0.4737% | 29,118/29,118 fill actions map into later cancels |
| `TFTFCCN` | two ordered trade/fill pairs, two matching cancels, neutral close | 819 / 0.0544% | 832 / 0.0524% | 3,302/3,302 fill actions map into later cancels |

Incidence is `family_count / that day's F_LAST-closed groups`; it is not pooled across days. Within the restricted three-family post-fill denominator `TFCN + TFM + TFMN`, the cancel branch is 38,510/46,593 = 82.6519% on October 4 and 39,766/48,204 = 82.4952% on October 5. This restricted branch mix is strikingly stable and is not asserted to cover every trade/fill family. `[DERIVED+; INTERIM+]`

`TFCN` is single-price in 38,490/38,510 = 99.9481% and 39,752/39,766 = 99.9648%; trade size equals fill size in 38,107/38,510 = 98.9535% and 39,389/39,766 = 99.0520%. Exact mirrored side partitions remain separate. `TFM` rotates from `ABB/BAA = 2,567/2,878 = 0.8919` on October 4 to `3,310/2,707 = 1.2228` on October 5, a side-specific disposition clue hidden by the stable combined rate. `[INTERIM+]`

**Forecasting hypothesis E1.** In one exact side/session/phase stratum, a rising cancel-linked share relative to modify-linked continuation should mark withdrawal of residual interest; the opposite should mark retained but resized interest. A falsifier is a claimed withdrawal regime in which exact same-order modifications and subsequent queue survival dominate cancels.

### E2 — the open-world taxonomy carries scalable and mixed cascades

| Fixed exact family class | 2021-10-04 | 2021-10-05 | Per-day incidence October 4 / 5 |
|---|---:|---:|---:|
| Terminal-close `TFC` | 7,950 | 8,268 | 0.5278% / 0.5206% |
| Three-/four-/five-fill extensions (`TFFFCCCN` + `TFFFFCCCCN` + `TFFFFFCCCCCN`) | 3,064 | 3,506 | 0.2034% / 0.2208% |
| Mixed cancel/modify (`TFFCM` + `TFFCMN` + `TFTFCMN`) | 900 | 970 | 0.0598% / 0.0611% |
| Add-interleaved (`TFACN` + `TFCAN`) | 857 | 887 | 0.0569% / 0.0559% |

The exact family counts and ID-linkage rules come from the complete held-out ledger census in `OPPORTUNITIES+`; incidences are calculated here using each day's group denominator. These content classes preserve execution fragmentation, split terminal disposition, and replenishment/withdrawal order that a daily book mean cannot encode.

### E3 — recurrence turns isolated families into causal runways

Exact same-side recurrence counts on October 4/5 include `TFCN/BAAN → TFCN/BAAN` 564/518, `TFCN/ABBN → TFCN/ABBN` 506/502, `TFM/BAA → TFM/BAA` 381/375, and `TFM/ABB → TFM/ABB` 371/497. Mirrored cascade contraction includes `TFFCCN/BAAAAN → TFCN/BAAN` 77/73 and `TFFCCN/ABBBBN → TFCN/ABBN` 67/92. Exact longest runs reach 4 `TFCN`, 8 `TFM`, 7/3 `TFMN`, 5/6 `TN`, and 83/86 atomic `C` groups on October 4/5. `[OPPORTUNITIES+]`

These are distinct day/family/side populations. Their useful averaged companions are within-edge or within-run arithmetic means of inter-group gap, duration, quantity, price displacement, and F_LAST formation time, with exact member rosters retained.

### E4 — one exact order already exhibits a complete depletion runway

Order `786260864394`, ask side at 5.758 on October 4, provides this exact causal chain: group 1,166,147 `AN` adds size 3 and closes at `00:07:47.336003229Z`; group 1,166,161 `TFMN` fills 2 and modifies the residual to 1, closing at `00:07:51.633499294Z`; group 1,166,162 `TFCN` begins 20,400 ns later and completes the residual, closing 90,964 ns after the first depletion close. The add's lawful availability leads the first-fill event by 4.297131704 s and first-fill receive by 4.297458097 s. `[OPPORTUNITIES+]`

This exact pre-contact → partial depletion/resizing → residual completion chain is directly useful as a content-derived template. Future arithmetic companions must use only identical same-order lifecycle strata and retain birth, first-contact, residual, inter-group, and completion clocks.

### E5 — 21:00 UTC withdrawal and restart is a repeatable session anchor

| Day / exact group | F_LAST availability | Cancel actions B/A | Cancel-size sum | Next close gap | First five restart sides |
|---|---|---:|---:|---:|---|
| 2021-10-04 / 2,654,677 | 21:00:00.237256020Z | 219 / 211 | 796 | 2,706.354043253 s | B, B, A, A, A adds |
| 2021-10-05 / 4,237,483 | 21:00:00.228110022Z | 371 / 210 | 1,179 | 2,705.898771115 s | B, B, B, A, A adds |

The quiet-interval difference is only -0.455272138 s. October 5 has 581 versus 430 cancel actions (+35.116%), cancel-size 1,179 versus 796 (+48.116%), and bid share 371/581 = 63.855% versus 219/430 = 50.930% (+12.925 percentage points). Each day remains its own session population. `[INTERIM+; OPPORTUNITIES+]`

**Forecasting hypothesis E5.** The exact `C…C→N` group, ensuing quiet interval, and ordered add restart should be treated as separate pre-boundary, withdrawal, quiet, and restart phases. A useful falsifier for transfer to another session is a boundary without the corresponding mass-withdrawal/order-survival change or without a causally distinct restart.

## `COMPLEMENTARY_SCOPE_DIFFERENCE` register

| Averaged view | Exact view | Why both are valuable |
|---|---|---|
| October 5 mean imbalance 0.221155 over 1,588,041 post-group states | Exact 21:00 withdrawal is bid-cancel-heavy, 371/581 | Whole-day stored-liquidity sidedness and a single boundary withdrawal answer different questions. `COMPLEMENTARY_SCOPE_DIFFERENCE`. |
| Stable restricted post-fill cancel share, 82.652%/82.495% by day | `TFM` mirrored-side ratio rotates 0.892→1.223 | Aggregate branch stability can coexist with side-specific rotation. `COMPLEMENTARY_SCOPE_DIFFERENCE`. |
| Mean spread near 0.0022 on both held-out days | Exact extrema reach 0.090 and -0.033 | Typical scale and transient spread state are different causal phases. `COMPLEMENTARY_SCOPE_DIFFERENCE`. |
| Daily means summarize every F_LAST book state | Order `786260864394` has a three-group, 4.297-second lifecycle | Regime context and exact order depletion are complementary granularities. `COMPLEMENTARY_SCOPE_DIFFERENCE`. |
| 1.324/1.330 actions per group on held-out days | Controller maxima are 806/667 actions; exact characterized bursts contain 253/274 | Typical multiplicity and burst-cluster structure require separate estimands. `COMPLEMENTARY_SCOPE_DIFFERENCE`. |

## Highest-value output-only follow-up calculations

All are `RETROSPECTIVE_DISCOVERY_HYPOTHESIS` work, not scientific locks.

1. For each exact family and mirrored side, retain member group IDs and calculate within-day/session/phase F_LAST-aligned arithmetic means of pre/post full-depth imbalance, depth, order count, level count, spread, and formation latency.
2. Use the resident checkpoint before each candidate to enumerate exact FIFO volume ahead, priority age, same-order survival, activity-tail signed flow, and subsequent depletion/replenishment; retain the checkpoint state hash and watermark.
3. Build exact family-edge and maximal-run rosters, then calculate within-identical-edge distributions of inter-group gap, quantity, price displacement, and completion latency.
4. Segment each day at the exact 21:00 withdrawal group and 21:45 restart; calculate within-session-phase, within-side, within-family companions only.
5. For day-regime features, require agreement or an explicitly registered `COMPLEMENTARY_SCOPE_DIFFERENCE` among averaged full-book state, exact message-side flow, family mix, and FIFO member behavior.

## Positive knowledge capsule candidates

1. **Causal rule:** A-clean exact evidence becomes available only at F_LAST on `ts_recv_ns`; retain event, first-receive, and close clocks separately, and never smooth across day/family/side/session/phase identities.
2. **Day-regime clue:** October 5 is more bid-supported than October 4: mean full-depth imbalance 0.221155 vs 0.121056, mean bid depth +21.847%, bid orders +16.460%, bid levels +8.899%, and nonneutral B-side message skew 5.204% vs 3.187%.
3. **Disposition rule:** In the restricted `TFCN + TFM + TFMN` population, cancel-linked share is stable at 82.652%/82.495% by held-out day, while mirrored-side `TFM` composition rotates; retain aggregate branch mix and side partition as coequal.
4. **Lifecycle template:** Same order `786260864394` exhibits `AN → TFMN → TFCN`: birth, partial fill/residual resize, then residual completion, with exact lawful clocks and a 20,400 ns inter-group gap.
5. **Session rule:** Exact 21:00 UTC mass-withdrawal groups followed by approximately 2,706-second quiet intervals and add-only restart prefixes are deterministic phase anchors; October 5's withdrawal is larger and more bid-cancel-heavy.
6. **Parallel-view rule:** Daily means provide regime/scale; exact groups, orders, FIFO queues, transitions, and checkpoints provide causal mechanism. Valid differences are `COMPLEMENTARY_SCOPE_DIFFERENCE`, never contradictions or pooled averages.

## Review classification

`BOUNDED_RETROSPECTIVE_OUTPUT_REVIEW`; A-clean only; read-only; no native DBN run/replay; no full Forecaster run; no scientific lock.
