# Dipole renders and whole-instance integrity

All four dates retain separate candidate, control, trade, structural instance and event populations. Whole lifecycle records are authoritative; sampled windows are linked components, not replacements for the parent.


Completed and visually checked 2026-11-09. [Successful render run](https://github.com/DavisAI1974/markets-data/actions/runs/42574533079). Data publication: 25e13a8d204f0ce77acfbe22b303f290d7202d10. Code: 9275d915fd7d2b0f46cfc74a3699902fb965eb14.

Start with the four small pinning packets (24 pages total):

| Date | Small pinning packet | Complete lifecycle books | Individual duration render |
|---|---|---|---|
| 20231002 | [6-page PDF](https://github.com/DavisAI1974/markets-data/blob/25e13a8d204f0ce77acfbe22b303f290d7202d10/tasks/family-research-20261022/dipole-render-books/run-42574533079-1/render-20231002/20231002-pinning-starter.pdf) | [All candidates and controls](https://github.com/DavisAI1974/markets-data/blob/25e13a8d204f0ce77acfbe22b303f290d7202d10/tasks/family-research-20261022/dipole-render-books/run-42574533079-1/render-20231002/README.md) | [PNG](https://github.com/DavisAI1974/markets-data/blob/25e13a8d204f0ce77acfbe22b303f290d7202d10/tasks/family-research-20261022/dipole-render-books/run-42574533079-1/render-20231002/20231002-individual-durations.png) |
| 20231003 | [6-page PDF](https://github.com/DavisAI1974/markets-data/blob/25e13a8d204f0ce77acfbe22b303f290d7202d10/tasks/family-research-20261022/dipole-render-books/run-42574533079-1/render-20231003/20231003-pinning-starter.pdf) | [All candidates and controls](https://github.com/DavisAI1974/markets-data/blob/25e13a8d204f0ce77acfbe22b303f290d7202d10/tasks/family-research-20261022/dipole-render-books/run-42574533079-1/render-20231003/README.md) | [PNG](https://github.com/DavisAI1974/markets-data/blob/25e13a8d204f0ce77acfbe22b303f290d7202d10/tasks/family-research-20261022/dipole-render-books/run-42574533079-1/render-20231003/20231003-individual-durations.png) |
| 20231017 | [6-page PDF](https://github.com/DavisAI1974/markets-data/blob/25e13a8d204f0ce77acfbe22b303f290d7202d10/tasks/family-research-20261022/dipole-render-books/run-42574533079-1/render-20231017/20231017-pinning-starter.pdf) | [All candidates and controls](https://github.com/DavisAI1974/markets-data/blob/25e13a8d204f0ce77acfbe22b303f290d7202d10/tasks/family-research-20261022/dipole-render-books/run-42574533079-1/render-20231017/README.md) | [PNG](https://github.com/DavisAI1974/markets-data/blob/25e13a8d204f0ce77acfbe22b303f290d7202d10/tasks/family-research-20261022/dipole-render-books/run-42574533079-1/render-20231017/20231017-individual-durations.png) |
| 20231018 | [6-page PDF](https://github.com/DavisAI1974/markets-data/blob/25e13a8d204f0ce77acfbe22b303f290d7202d10/tasks/family-research-20261022/dipole-render-books/run-42574533079-1/render-20231018/20231018-pinning-starter.pdf) | [All candidates and controls](https://github.com/DavisAI1974/markets-data/blob/25e13a8d204f0ce77acfbe22b303f290d7202d10/tasks/family-research-20261022/dipole-render-books/run-42574533079-1/render-20231018/README.md) | [PNG](https://github.com/DavisAI1974/markets-data/blob/25e13a8d204f0ce77acfbe22b303f290d7202d10/tasks/family-research-20261022/dipole-render-books/run-42574533079-1/render-20231018/20231018-individual-durations.png) |

[All 337 original renders in five PDF books](https://github.com/DavisAI1974/markets-data/blob/25e13a8d204f0ce77acfbe22b303f290d7202d10/tasks/family-research-20261022/dipole-render-books/run-42574533079-1/render-archive/README.md). The complete new collection contains 9,530 individual parent pages across 102 volumes; each whole lifecycle fits on a single page. Both original controls remain available. The small starter packets are additional selections, not replacements.

## Audit completed before rendering

[Audit publication](https://github.com/DavisAI1974/markets-data/tree/9e3365f76fb4d34d97eb193d35072aae5f51b709/tasks/family-research-20261022/whole-lifecycles/run-42573465249-1).

| Date | Candidate parents | Control parents | Whole path points | Component windows |
|---|---:|---:|---:|---:|
| Oct 2 | 741 | 1,482 | 92,779 | 2,223 |
| Oct 3 | 833 | 1,664 | 106,478 | 2,496 |
| Oct 17 | 741 | 1,480 | 88,801 | 2,220 |
| Oct 18 | 863 | 1,726 | 109,757 | 2,589 |

Total: 3,178 candidate parents, 6,352 original matched-control parents and 397,815 whole-path points. The audit checked 9,524,329 candidate references in 166 per-date tables, every original path window's sampled source cursor, and the complete original sequence of lifecycle seconds. A separate cross-date audit checked all 37 cross-date source tables and their candidate references. Trade checks cover 143,270 individual prints, 23,615 complete directional legs and their original source clocks/memberships. Pressure-event outcomes resolve to their individual signal parents.

Corrections: original lifecycle point tables began one second after the anchor; whole-path exports now include the anchor. The two finalization-only candidates have full paths recovered from the original flow, while live recognition stays missing. Thirteen October 18 control instances fall outside native-flow coverage and remain explicitly unavailable. All candidates retain a parent and an observed original-flow sequence.

The one whole parent is identified by date:candidate_id:kind. Each component keeps its own clocks and original source selector. Event, receive, completed-second known-by and actual recognition times remain distinct integer nanoseconds; raw action provenance remains linked through source groups/cursors. A sample can extend before or after its parent's operational lifecycle and is explicitly labelled context.

The endpoint remains the existing third-consecutive-opposite-second rule or censoring. This is not an established natural market-event death. Undefined lean does not split a lifecycle; it stays a gap inside the same parent. Structural families and fitted shape groups remain different relationships, not fabricated event lifecycles.

## Reading the renders

Each lifecycle occupies one complete PDF page; 100-page PDF volumes only package separate events. No lifecycle is cut between pages or stopped at recognition. Each page includes original native flow, original bid/ask, fresh classified lots, displayed touch lots, parent ID and exact anchor/recognition/end/known-by timestamps. The full source observations remain in the audit tables.

The original 337 figures remain available as full-width images embedded in PDF books, with tall pages where required to preserve legibility. Each links to its original full-resolution PNG and its immutable source manifest. These collection plots retain their original populations, control definitions and plotted scopes; they are not relabelled full lifecycle plots. Sorted-rank curves retain ordinal x-axes. The new complete lifecycle books include every candidate, including cases outside an old figure's plotted subset.

New duration renders retain one plotted observation per available individual record, with a companion ID/clock-linked point table; unavailable/censored records remain in that table. Regression checks verify that isolated finite observations are visible and no line bridges missing values.

## Small packet for CCode

See [DIPOLE_PINNING_PACKET.md](DIPOLE_PINNING_PACKET.md). The recommended five coordinated views are whole lifecycle, fresh versus expiring flow, liquidity response, event sequence, and continuation/exhaustion.

The starter packet contains six pages per date: first chronological NO_PREDECESSOR, SAME and FLIP candidates, each with its original control1. Selection is by source order, not outcome; the packet is for navigation and joining, not a representative performance sample. CCode can attach its own work concurrently, using separate immutable outputs and explicit source/ID/time joins.

Paper readiness/configuration remains a separate outstanding task. The 99 layers and 13 external points remain deferred.
