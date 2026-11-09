# Family replication completed

The remaining three-date family study is complete and published. User steering was to finish this before timestamp assembly or paper setup; neither was started during this work.

- [Published evidence](https://github.com/DavisAI1974/markets-data/tree/7b50d634f94ea4777d1e772ac2b916b001019582/tasks/family-research-20261022/family-replication/run-42566535537-1), markets-data commit `7b50d634f94ea4777d1e772ac2b916b001019582`.
- [Successful hosted run 42566535537](https://github.com/DavisAI1974/markets-data/actions/runs/42566535537).
- [Analysis source](https://github.com/DavisAI1974/Markets/blob/59195f9339c48cfcbd4a6bf9916a935a4da4fb1d/agent-pass/replication/finish_family_replication.py).
- 96 manifested output files, 12,575,413 measured bytes, plus four manifests and RUN_STATUS.json. Per-date receipts, manifests, reference comparisons and workflow conclusion were read back from the publication.

## Completed scope

The original family four-arm comparison (baseline, flow, book, both), family prebirth controls at 1/5/20/60 seconds, primer next-price-change and 1/5/25/100/250/500 ms and 1/5/20 s responses, plus quote-age/control-reuse sensitivities now cover October 2, 3 and 17. October 18's original 749-family reference reproduces eight four-arm tables; the missing-value fix also reproduces all three previously saved reference primer tables.

The four-arm method is unchanged: ridge alpha 10, train-only scaling, expanding 40/60/80% chronological splits, horizon purge and 600-second embargo, five response horizons (1/5/20/60/300 seconds), signed and absolute targets. All arms use identical eligible rows within each fit. These are the archived explanatory models, not new shape fitting or trading admission rules. No original input values or time paths were adjusted.

| Date | Retained families | Four-arm eligible | Fits | Prebirth case rows | No eligible primer prequote |
|---|---:|---:|---:|---:|---:|
| Oct 2 | 796 | 510 | 120 | 3,184 | 2 |
| Oct 3 | 849 | 535 | 120 | 3,396 | 4 |
| Oct 17 | 824 | 517 | 120 | 3,296 | 2 |
| Oct 18 original reference | 749 | 437 | 120 | 2,996 | 0 |

All families remain in opportunities and prebirth cases. Model eligibility and response availability are reported separately. In the receipt, `primer_missing_prior` and the primer-disposition label `no_strict_pre_group` mean the original method did not supply an **eligible** prequote; this includes invalid quotes, not only an absent earlier source group. Each new date has exactly one family with no earlier source group. No replacement quote or invented clock was supplied.

## Population and source verification

The exact original structural-descriptor function was recovered at producer commit `2ebb8ce8ef4834545ad99a4ecdff50c18c5b3134`; its SHA256 and dependent source pins are retained. Applying it to saved raw action groups reproduced all 749 original October 18 family IDs, first receive clocks, source ordinals, close cursors and occurrence counts. The full observed October 18 universe has 764 IDs, including 15 outside the old catalog. That full inventory is preserved in the [preflight publication](https://github.com/DavisAI1974/markets-data/tree/54e1b1be98ae6defff25ccfe7e1c3498e8f569f9/tasks/family-research-20261022/family-replication/run-42564821790-1/family-preflight).

The other dates follow the existing direct-ROOT first-observation convention: all structural IDs observed on that date. They are not forced into October 18's selected 749-ID catalog. A first observed structural family is not asserted to be a natural market-event birth.

| Date | Completed ROOT rows | Verified compressed parts | Verified decompressed bytes | Extracted strict-pre snapshots |
|---|---:|---:|---:|---:|
| Oct 2 | 600,291 | 211 | 520,064,232,895 | 795 |
| Oct 3 | 653,912 | 236 | 572,726,375,854 | 848 |
| Oct 17 | 635,170 | 243 | 581,067,333,483 | 823 |

Every archive part and the full decompressed SHA256, byte count and row count passed. Selected frames matched original receive clocks and cursors; first-family descriptors and strict-pre full-book depth sums/best quotes reconciled. Saved coordinates include byte offsets and row hashes. Subsequent checks passed for strict information availability, family conservation, equal model denominators and embargo separation.

The initial extraction run preserved these successful source checks but failed during primer application: absent/invalid prequotes were CSV blanks while that module expected NaN. The correction only converts this missing-value representation, records the disposition, and resumes from the immutable verified extraction. The initial failure remains recorded; it is not relabeled a successful run. The successful follow-up rechecked source receipts and unchanged October 18 results.

## Agreement, differences and unresolved comparisons

- **Agrees:** the same structural definition and the same analysis pipeline apply to all three new dates. For matched family cases, the archived one-second classified-activity contrast (`total1`) at 1/5/20-second leads is positive on October 2, 17 and the October 18 reference. This is a recorded diagnostic, not proof of a whole-path shape or a trading edge.
- **Differs:** October 3's all-pair `total1` contrasts are negative at those leads. At the one-second lead, its mean difference is -0.523 lots, but becomes +0.281 when reused controls receive equal weight. October 18's one-second fresh-quote subset changes from +0.226 to -0.178 under equal-control weighting. Both versions and every case remain saved. Population sizes, available history and model errors also differ; no result was filtered to force agreement.
- **Unresolved:** timestamp joins to individual dipole paths/raw MBO and Desktop's layer have not been assembled in this task. The selected October 18 family catalog and the other dates' full observed populations differ, so pooled differences cannot be assigned solely to the trading date. The older 99-field/13-external-point study, targeted family/lifecycle overlaps and original Family A runway identities are separate scopes, not certified by this completion. Event duration, exhaustion and execution timing still require the planned joined evidence and paper setup.

The recovered family input gap is closed for this four-arm/prebirth/primer scope. Existing dipole A–E/M1/M2/shape work and continuous extensions remain complete as recorded in FOUR_DAY_REPLICATION.md. No desktop calculation, market producer rerun, external-researcher merge, simulator order or live-money action occurred. PR15 remains draft and unmerged.
