# CCode pinning packet: a small linked set, with intact parents

Both researchers can pin their work in parallel. Use separate code/output paths and immutable source revisions; combine evidence through explicit joins. There is no need to wait for one researcher to finish.

## Prioritize these five coordinated views

| View | What to pin onto it | What it helps explain |
|---|---|---|
| Whole dipole lifecycle | Original native lean, price, birth label, actual recognition, defined endpoint | How the developing movement evolves through one whole observed lifecycle |
| Fresh activity versus window expiry | Fresh buy/sell, 20-second rolling buy/sell, lots expiring from that window | Active pressure versus an old contribution simply falling out |
| Liquidity response | Original additions, cancellations, fills, modifications, touch depth, quote changes | What supplies or removes resistance as flow changes |
| Event sequence | Family occurrences, pressure signals, raw trades, whole print legs, source group/cursor | What happens first and which observations were already available |
| Continuation and exhaustion | Subsequent movement, first recovery, failed continuation, pauses and reversal | How much ride remains under explicitly named endpoints |

Start with the first chronological SAME, FLIP and NO_PREDECESSOR candidate per date and each candidate's original control1. This is a 24-page coordination packet across four dates, selected by source order rather than outcome. It is a navigational sample, not an estimate of performance or representative prevalence. The full books retain all candidates and both original controls.

## Ready-to-use render packets

| Date | Small pinning packet | Complete lifecycle books | Individual duration render |
|---|---|---|---|
| 20231002 | [6-page PDF](https://github.com/DavisAI1974/markets-data/blob/25e13a8d204f0ce77acfbe22b303f290d7202d10/tasks/family-research-20261022/dipole-render-books/run-42574533079-1/render-20231002/20231002-pinning-starter.pdf) | [All candidates and controls](https://github.com/DavisAI1974/markets-data/blob/25e13a8d204f0ce77acfbe22b303f290d7202d10/tasks/family-research-20261022/dipole-render-books/run-42574533079-1/render-20231002/README.md) | [PNG](https://github.com/DavisAI1974/markets-data/blob/25e13a8d204f0ce77acfbe22b303f290d7202d10/tasks/family-research-20261022/dipole-render-books/run-42574533079-1/render-20231002/20231002-individual-durations.png) |
| 20231003 | [6-page PDF](https://github.com/DavisAI1974/markets-data/blob/25e13a8d204f0ce77acfbe22b303f290d7202d10/tasks/family-research-20261022/dipole-render-books/run-42574533079-1/render-20231003/20231003-pinning-starter.pdf) | [All candidates and controls](https://github.com/DavisAI1974/markets-data/blob/25e13a8d204f0ce77acfbe22b303f290d7202d10/tasks/family-research-20261022/dipole-render-books/run-42574533079-1/render-20231003/README.md) | [PNG](https://github.com/DavisAI1974/markets-data/blob/25e13a8d204f0ce77acfbe22b303f290d7202d10/tasks/family-research-20261022/dipole-render-books/run-42574533079-1/render-20231003/20231003-individual-durations.png) |
| 20231017 | [6-page PDF](https://github.com/DavisAI1974/markets-data/blob/25e13a8d204f0ce77acfbe22b303f290d7202d10/tasks/family-research-20261022/dipole-render-books/run-42574533079-1/render-20231017/20231017-pinning-starter.pdf) | [All candidates and controls](https://github.com/DavisAI1974/markets-data/blob/25e13a8d204f0ce77acfbe22b303f290d7202d10/tasks/family-research-20261022/dipole-render-books/run-42574533079-1/render-20231017/README.md) | [PNG](https://github.com/DavisAI1974/markets-data/blob/25e13a8d204f0ce77acfbe22b303f290d7202d10/tasks/family-research-20261022/dipole-render-books/run-42574533079-1/render-20231017/20231017-individual-durations.png) |
| 20231018 | [6-page PDF](https://github.com/DavisAI1974/markets-data/blob/25e13a8d204f0ce77acfbe22b303f290d7202d10/tasks/family-research-20261022/dipole-render-books/run-42574533079-1/render-20231018/20231018-pinning-starter.pdf) | [All candidates and controls](https://github.com/DavisAI1974/markets-data/blob/25e13a8d204f0ce77acfbe22b303f290d7202d10/tasks/family-research-20261022/dipole-render-books/run-42574533079-1/render-20231018/README.md) | [PNG](https://github.com/DavisAI1974/markets-data/blob/25e13a8d204f0ce77acfbe22b303f290d7202d10/tasks/family-research-20261022/dipole-render-books/run-42574533079-1/render-20231018/20231018-individual-durations.png) |

[Full original figure books](https://github.com/DavisAI1974/markets-data/blob/25e13a8d204f0ce77acfbe22b303f290d7202d10/tasks/family-research-20261022/dipole-render-books/run-42574533079-1/render-archive/README.md). [Render and integrity report](DIPOLE_RENDERS.md).

## Inputs available now

[Whole lifecycle audit and tables](https://github.com/DavisAI1974/markets-data/tree/9e3365f76fb4d34d97eb193d35072aae5f51b709/tasks/family-research-20261022/whole-lifecycles/run-42573465249-1).
All four per-date audit jobs passed before rendering. In each audit-YYYYMMDD folder:

- whole-lifecycles.parquet: one parent per candidate/control instance, original candidate ID, kind, anchor/end labels, actual recognition, source pins, availability and endpoint definition.
- whole-lifecycle-points.parquet: every original second from anchor through the defined endpoint, in order, including undefined observations. Same parent throughout. Fresh/rolling native flow retains its values.
- native-flow-source-clocks.parquet: second labels, exact completion known-by time, completion group/cursor and all source groups/cursor spans contributing within that second.
- component-windows.parquet: original sampled windows linked to parent; their own first/last cut clocks and source row selectors. Explicit flags identify context before/after the defined lifecycle.
- individual-table-catalog.json: original per-date source table paths/hashes/fields and candidate reference checks.
- audit.json and MANIFEST.json: measured coverage and verification.

The original life-path files omitted anchor rows; whole-path records now include them. Two finalization-only candidates now have original-flow lifecycle paths without invented live recognition. Undefined/out-of-coverage observations stay explicit.

[Combined individual event tables](https://github.com/DavisAI1974/markets-data/tree/87dc338f2e74646eb731b3cd6f8968a5a0a653e2/tasks/family-research-20261022/combined-events/run-42571551209-1):

- a-trades / a-price-stretches / a-print-legs: individual prints and complete stretch/leg spans and their member relationships.
- a-family-firsts / a-all-family-occurrences: starts and all actual structural occurrences; a family is not asserted to be a natural event lifecycle.
- a-dipole-clocks / a-trade-dipole-overlaps: actual archived recognitions and exact trade event/receive/known-by/cursor links.
- b-signals / b-quote-episodes / b-delayed-outcomes: signal, whole quote episode and distinct horizon observations.
- c-large-quote-events / c-prior-signal-to-large-move / c-selected-actions-* / c-selected-book-context-*: large movement, recovery and original order evidence.
- cross-study-event-links: shared signal context with family and already-recognized dipole references.

## Which existing renders to use

[Original figure directory](https://github.com/DavisAI1974/markets-data/tree/0487d83b1ddb1abe5e4cfae12e8b88797801f428/tasks/family-research-20261022/native-dipole/20261108-33693e180/agent-pass/figures).
For each date and SAME/FLIP (NO_PREDECESSOR kept separately):

- YYYYMMDD-candidate-ORIENTATION-flow.png
- YYYYMMDD-candidate-ORIENTATION-quotes.png
- YYYYMMDD-candidate-ORIENTATION-actions.png
- YYYYMMDD-all-footprints-ORIENTATION.png

These are collection views. Pin the corresponding individual rows from YYYYMMDD-paths.csv.gz, path-members.csv, first-footprint-events.csv and footprint-endpoint-audit.csv, not image pixels. Birth-to-recognition windows remain components of their whole parent. The new whole-lifecycle books are generated separately and indexed by parent ID and exact PDF page.

## Join contract

Use date/instrument/source population plus source group/cursor or exact timestamps. Native candidates and CCode's independent 839/857/830/890 population are not automatically the same events. Record matched, ambiguous, unmatched and finalization-only dispositions. Do not coerce them to the Native 741/833/741/863 counts.

Keep event timestamp, receive timestamp, completed-group known-by time, birth label and recognition distinct. A completed-second flow label is not the time that value became available. Native action-midpoint classification and wire aggressor side are different measurements; preserve both labels. SAME/FLIP describes predecessor polarity, not a profitable/unprofitable outcome.

The lifecycle endpoint is the recorded third-consecutive-opposite-second research rule (or censoring), not established natural event death. Keep the whole path and full source stream; a later context window may extend past that endpoint. Raw order actions and original event timestamps remain in the verified source publication at 2fd55ea1276d00530f8cdbd1caf5918910494f19.

A sorted-rank shape has an ordinal x-axis, not an event clock. Use its row-to-candidate mapping to recover event time before pinning. Never join rank positions as if they were seconds.
