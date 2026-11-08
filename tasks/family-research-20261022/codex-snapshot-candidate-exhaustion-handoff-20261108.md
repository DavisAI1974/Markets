# Snapshot, candidate archive, and exhaustion parameterization handoff

Inspected shared-branch revision: `e5d7ec4b05167a9610a8697e4f64d1558f38c84d`.
Raw-tape revision: `1d15dc6f1b5bbb1fabb6389d18e8bedba2b77202`.
This is a source-backed handoff for CCODE, which owns the missing-data changes.
No producer, detector, or full-day audit was rerun or modified for this answer.

## 1. What the Book actually does with range-start snapshots

The exhaustion script imports `Book` from
`tasks/family-research-20261022/audit_october18_touch_mechanisms.py`, not the separate
`claude-pass/c03_recon_mbo.py` implementation. At the inspected revision:

- `Book` starts at line 63; `apply()` starts at line 80.
- Action `R` (line 84) clears `orders`, `levels`, and `refreshes`.
- Snapshot `A` records then go through the ordinary order-setting path. An existing
  ID is removed from its prior level before replacement; it is not blindly added
  to the old quantity.
- `F` records accumulate pending fill evidence; they do not directly reduce
  displayed size. `C`/`M` mutate display. `T` does not mutate the book.
- `Book.apply()` itself never inspects `record.flags`. Snapshot identification,
  completion and eligibility for flow/change features are caller responsibilities.
- The exhaustion caller clears its external `pending` counter at `flags & 128`
  (`F_LAST`). `R` does not itself clear that external counter. Boundary handling
  should reset the pending evidence too, rather than carrying it into a reset book.

I applied **only the initial snapshot prefix** of both actual pinned UTC members
to this exact class. A preloaded sentinel order was cleared, and the resulting
order counts matched the snapshot adds:

| UTC member | First action / flags | Snapshot adds | Final reconstructed orders | First non-snapshot raw index |
| --- | --- | ---: | ---: | ---: |
| 2023-10-17 | R / 40 | 737 | 737 | 738 |
| 2023-10-18 | R / 40 | 717 | 717 | 718 |

Both observed final snapshot adds carry flags 168. Here 40 is SNAPSHOT (32) plus
BAD_TS_RECV (8); 168 also includes LAST (128). Both following records have flags
128. The current pinned files therefore include explicit reset records; there is
no need to assume that their 2023 date implies an older snapshot encoding.

[Inspection receipt](research-atlas-v2/snapshot-prefix-inspection.json).

Databento documents snapshots as a reset followed by outstanding-order adds. Their
receive timestamps represent snapshot generation time, not historical arrival
times for every resting order. A snapshot may require a following `F_LAST` before
the book is complete. Apply snapshot records to initialize state; do not count
their adds as fresh trader activity or interpret their timestamps as prior flow.
[Databento snapshot convention](https://databento.com/docs/conventions/mbo-snapshot).

One concrete caller detail: `replay()` currently samples book imbalance/midpoint
at every `F_LAST`, including the snapshot-ending group when in the analysis range.
It does not explicitly exclude SNAPSHOT/BAD_TS_RECV groups from those observations.
The snapshot has no trade prints, so it does not itself add buy/sell trade volume.
Separate initialization state from activity measurements in the generalized
wrapper. A midnight snapshot restores resting state at midnight; it cannot restore
the missing earlier trades, birth events, or intraday path.

## 2. October 17 archived candidate-input file

**No October 17 counterpart was found in the complete committed path inventory at
the inspected revision.** The available reconstructed archive is:

`tasks/family-research-20261022/october18-candidate-inputs.jsonl.gz`

These October 17 artifacts do exist:

- `claude-code/exhaustion-clock-20231017-flow-only-events.jsonl.gz`
- `claude-code/exhaustion-clock-20231017-flow-only.json`
- `flow-book-discovery-v1/date-tables/20231017/legacy_native_signed_flow.json.gz`

The flow-only event rows are newly detected events with fields such as `t0`,
`second`, `polarity`, `seed`, `runway` and `confirm`. They are **not** an archived
Native recognition ledger and cannot substitute for it in a birth-match test.
This inventory does not establish what might be unfinished or uncommitted on
another machine/pod.

The exact minimal archived row consumed by `exhaustion_clock_reanalysis_oct18.py`
is JSONL (gzip compressed), with these three required fields:

```json
{
  "birth_second": 1697581215,
  "recognition_receive_ns": 1697581262250387132,
  "birth_to_emission_flow_state": "undefined_at_emission"
}
```

That is an actual October 18 example, not fabricated October 17 data. Preserve
`candidate_id`, instrument, recognition cursor/group and source revision as well
when creating the October 17 counterpart. Birth seconds and receive nanoseconds
are absolute UTC coordinates, not date-relative indices. The script currently
maps `birth_second - DAY0` to one row; detect duplicate birth keys instead of
silently overwriting candidates when generalizing across instruments/events.

The existing `reconstruct_october18_candidate_inputs.py:reconstruct()` requires
the date's retained candidate/episode/flow-substrate records, including
`birth_recv_ns` and `frankie_emission.{input_cursor,ts_recv_ns,group_index}`, plus
matching completed groups and the action-time tape reconstruction. A standalone
quote/print export alone does not create the archived recognition history.

Until that archive is saved, the generalized exhaustion analysis can run its
available market-data portion with `archived_candidates=null`. Emit an explicit
`birth_comparison_status="archive_unavailable"` and null comparison counts;
do not report zero matched births as a scientific result.

## 3. Exact structure to parameterize

Primary file:
`tasks/family-research-20261022/claude-code/exhaustion_clock_reanalysis_oct18.py`.

### Current date-bound locations

| Location at inspected revision | Current hard-coded behavior | Parameter needed |
| --- | --- | --- |
| Imports and constants, lines 40–46 | Imports tape path, revision, instrument 150611 and October 18 cursor offset; `DAY0=1697576400` | Explicit source/session configuration |
| `replay()`, line 67 | `n=86400` | Duration derived from explicit replay bounds |
| `replay()`, line 75 | October 17 member at offset −841601, October 18 member at +17375, selected by string replacement | Ordered member list with per-member revision/path and verified cursor mapping |
| `replay()` second indexing | `record.ts_recv // NS - DAY0` | Shared absolute origin plus explicit availability/coverage masks |
| `main()`, lines 258–259 | `SESSION_CLOSE=86400` and last-trade cap | Analysis start/end separate from warmup/read range |
| `main()`, lines 261–262 | Fixed October 18 candidate archive, birth-to-relative-index dictionary | Optional archive path/revision and duplicate-key policy |
| Event row, line 308 | UTC display embeds 75,600 seconds (21:00) | Format from absolute `origin_second + t0`, retaining the full date |
| Output, lines 426–427 | Fixed `exhaustion-clock-oct18-*` filenames | Output directory and date/run prefix |

The script's current window begins October 17 at **21:00 UTC**; the existing
Codex session-group analyses explicitly select **22:00 UTC** onward. Parameterize
and report that distinction. Do not silently equate replay warmup, analysis
coverage, UTC day, and session open. Likewise, `detect(mode="day")` currently
takes its threshold over the finite values in the supplied stream; record that
scope rather than claiming an independently selected calendar-UTC-day threshold.

### Proposed wrapper contract (not an existing API)

```python
SessionSpec(
    session_date,                 # label, not a predictor
    instrument_id,
    replay_start_ns, replay_end_ns,  # half-open; includes available warmup
    analysis_start_ns, analysis_end_ns,
    members=[
        TapeMember(revision, path, cursor_offset, coverage_start_ns, coverage_end_ns)
    ],
    archived_candidates=None,     # or PinnedFile(revision, path)
    output_dir, output_prefix,
    coverage_status,              # full / partial, with missing intervals
)

stream = replay(spec)
results = analyse(stream, spec, archived_candidates)
write_results(results, spec)
```

Derive the array origin and length from the configured bounds. Keep raw member
coordinates alongside session cursors; do not reuse October 18 offsets for a new
export without reconciling them. For a partial date, represent absent coverage
explicitly rather than zero-padding it as a period with no trades. Snapshot state
can initialize the book, while prior trade-flow windows remain unobserved.

The **existing stream contract** returned by `replay()` is:

```text
buy, sell, price, book, mid, roll : arrays of length n
cb, cs                          : cumulative-volume arrays of length n + 1
first_trade, last_trade          : relative integer indices (or explicit empty state)
counts                          : print/classification counts
```

Preserve that interface for the detector and downstream scripts; add origin,
coverage, snapshot/reset, and known-by metadata rather than changing units.
`price` is forward-filled last trade, `mid` is forward-filled midpoint, and `book`
uses the within-second mean of sampled ten-level imbalances, falling back to the
last sample in empty seconds. Those definitions are not interchangeable with the
touch-only book or companion quote-classified flow used elsewhere in the atlas.

Keep the frozen math unchanged: `ROLL=20`, `PEAK_Q=.85`, `LOCAL_RADIUS=5`,
`REFRACTORY=45`, `PERSIST=3`, `MATERIAL_TICKS=2`, `PRE=POST=60`, raw `TICK=1_000_000`,
and aftermath horizons `(5,10,20,30,60,120,300)`. Keep local-information,
refractory-information, endpoint-confirmation, seed-state availability, and
runway fields separate. Changing a date wrapper must not refit thresholds,
redefine the frozen state classifier, or turn weak results into exclusions.

### Downstream call sites

These also import `exhaustion_clock_reanalysis_oct18 as X`, call `X.replay()`, and/or
read fixed October 18 filenames:

- `runway_duration_test_oct18.py`: replay and exhaustion events; fixed outputs.
- `frozen_a_classifier_oct18.py`: replay, exhaustion events and frozen classifier;
  fixed outputs. Preserve the exact classifier SHA and original-family identity.
- `a_state_direction_knowable_oct18.py`: replay plus exhaustion and A-classifier
  event files; fixed outputs.
- `exhaustion_clock_flow_only.py`: already has `run(date)` and date-named outputs,
  but imports the same helpers/constants and uses a fixed input root. Its input is
  `{"per_second":[{"second":...,"buy":...,"sell":...}],"summary":{"trades_seen":...}}`.
  Preserve partial coverage and distinguish missing seconds from genuine zero flow.

Pass the same spec/stream and explicit event paths through these consumers so
they cannot accidentally read October 18 results during an October 17 run. Reuse
saved streams/exports; this handoff does not request duplicate box/producer work.

Minimal verification for CCODE's change: actual snapshot-prefix state equality;
unchanged results under the original explicit October 18 spec; missing-archive
status retained; absolute birth/recognition joins reconciled; separate output
paths per date; partial/empty coverage preserved; no snapshot adds counted as
fresh flow. These are plumbing checks, not signal-strength admission gates.
