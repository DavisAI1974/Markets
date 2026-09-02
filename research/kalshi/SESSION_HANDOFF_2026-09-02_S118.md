# S118 - THE SIZE IS ONE FIELD, FOUR OF MY NUMBERS WERE WRONG, AND THE BOX IS WEDGED

**Branch `chatgpt/frankie-raw-mbo-benchmark-20260828`, tip `752ac56`, 896 tests green
(was 885). Decisions 66 -> 68. THE SUNDAY RUN IS BUILT AND VERIFIED AND HAS NOT RUN.**

## GREG'S STANDING DOUBT, CARRIED FORWARD OPEN

**"i still feel the numbers need to be rechecked but we'll do that in the next session."**
Recorded as item zero of `DROP_IN_S119.md`, not as a closed question. He is right to hold it:
four size numbers were produced this session and all four were wrong in the same way. The
current figure is better evidenced than those four but is still SELF-REPORTED by the sink, and
the drop-in names the independent witness that would settle it - S3's own object sizes for the
canary packet, which reconcile or do not against 12,301,736,545 bytes.

## THE FINDING: 94.7% OF EVERY BYTE IS `book_full`

Measured exactly from `ledger_retention[*].bytes` over 50,001 real records, canary 33596898227:

| | |
|---|---|
| bytes per record | **246,030 (240.3 KiB)** |
| `book_full`, ONE FIELD | **11.64 GB of 12.30 GB = 94.7%** |
| `exact_member_ledger`, ONE LEDGER | 12.11 GB = 98.5% |
| **all sixteen calculations combined** | **~1.5%, about 190 MB** |
| most expensive calculation (`replenishment`) | 0.6% |
| Sunday Oct 3, 57,027 records | **14.0 GB** |
| full roster, 5,667,689 records | **1,394 GB** |

**Greg asked which of the calculations is contributing to the size and what has zero value.
The answer is that none of them is.** Retiring every calculation in the contract would save one
and a half percent. The whole size question has exactly one subject, the per-group full book
snapshot - and that is the thing Greg already ruled must stay: *"do not leave any of the book
data out. it may not seem relevant to you but it may to frankie."* So this is not a drop
proposal; it tells us where Frankie's report should be aimed.

## FOUR NUMBERS, ONE DEFECT, PRODUCED BY THE PERSON LOOKING FOR IT

| number | what it actually measured | truth |
|---|---|---|
| 24 KB/record | the canary artifact AFTER `upload-artifact` compressed it | 246 KB - this filled a 300 GB volume |
| 215 KB/record | CloudWatch bytes / a record count NOBODY EVER READ | close by luck, not method |
| 9:1 compression | derived FROM the discrepancy it explained | circular |
| key names = 57.3% of a row | a row I INVENTED | ~0.1% on real rows |

Every one: present, typed, plausible, measuring something other than what its name implied.
**Greg caught the pattern before I did** - *"it feels like something is wrong with your
numbers"* - and separately caught me reporting elapsed time inferred from poll count rather
than read from a clock (I said 17 minutes; it was 4m26s, and I had already built a conclusion
on it).

**Consequence for D67: nova key aliasing saves essentially nothing here.** The sink already
writes `separators=(",",":")` with `sort_keys`, so `compact_payload` returns a BYTE-IDENTICAL
string, and real rows are dominated by one nested field rather than by key names. The reducer's
value is `plan_retrieval` (which returns `refuse_full_read` on a 12 GB day AND declares the
withheld content) and its rule that silent truncation is forbidden - which is D60 arriving from
the other direction.

## THE BOX IS WEDGED AND THE REBOOT DID NOT FIX IT

Three independent commands - the Sunday dispatch, the monitor's script, and a four-line
`/bin/sh -c` running only `df` - returned `Failed`, exit 1, **both streams empty**. Agent
`Online` and pinging; instance `running` with both EC2 status checks `ok`. So not a dead
machine and not a hung agent: **SSM stages its command script to a file, and the 300 GB volume
is full from the killed run's ~232 GB.**

**My fix was in the wrong place**: the `rm -rf` was placed INSIDE the dispatch, and that command
is itself a file that must be written to the disk it exists to free.

Unwedge run 33598410974 (reboot, no growth) had **not resolved at 06:38Z**, 17m15s into its
recovery loop. Behaviour changed after the reboot - commands now sit **Pending** instead of
failing in two seconds - and that has not been diagnosed. Options in `DROP_IN_S119.md`, cheapest
first: detach/attach to a throwaway instance (untried, best), Session Manager (untried), grow
and reboot (authorised by Greg, but a permanent cost for a transient condition and correctly
challenged by him: *"why would we have to grow a 300gb box by 20 to run a Sunday that isn't
even 2"*).

## BUILT AND PUSHED

- Byte attribution in `native_row_sink` (exact per section, sampled per field at a prime rate,
  labelled) + 5 tests; `report_ledger_size.py` + 6 tests; `frankie_run_size_report_20260902.yml`.
- The single-source run path on the **full-run** workflow per Greg's ruling, with three defects
  the rendered command exposed - the killer being that the box path never passed
  `--cadence-groups`, so at the 250,000 default a one-day run would have **staged not one spawn
  request**: every calculation would run, every gate would pass, and there would be nothing for
  Frankie to be spawned against.
- **Presigned PUT uploads**, which close the S3 write blocker with no IAM change.
- `frankie_box_unwedge_20260902.yml`, defaulting to a read-only `report`.
- D67, D68, and `FRANKIE_MEASURED_LEDGER_SIZE_20260902.md`.

**A workflow carrying only `workflow_dispatch` is never registered on a non-default branch and
the dispatch API 404s it** - both new workflows needed a `push` trigger, and where a push could
reach a destructive step it is additionally guarded on `github.event_name`.
