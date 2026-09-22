# Spec: trading-day-ingest (module 1 of CAPABILITY_MAP_TRADING_DAY_20260922.md)

Greg's go: "Lets rerun cyc 0" (02:2xZ 09-22); the rerun is the CME trading day, Sunday 18:00 ET open to Monday 17:00 ET
halt, 23 hours; the Monday hours come from the block already staged in S3; the count is measured; no Databento pull.

## Objective
Produce ONE compact container of the staged block (bucket `bento-568968024170-us-east-2-an`, prefix
`frankie/block_20211004_20211006/sources/`, four members, 6,471,475 MBO records) ingested as one continuous stream under the
`cme_trading_day` session policy (already in `operations/ingest_block_sources.py`, 2026-09-16), so that the trading day
2021-10-04 (Sunday 22:00Z open through the Monday 21:00Z halt) is a SESSION inside it, its record count measured and
receipted, the container pinned by sha256 in S3, ready for the schedule module. Success = the schedule module can read
the trading day's records by session identity from a pinned container without touching Databento or the raw archive again.

Why the whole block and not two members: the tool replays the members in manifest order with no gap and labels every
record with its trading day; the halt boundary closes an F_LAST group; the later members (Tuesday, Wednesday) become the
next trading days' sessions in the same container at no extra design cost. The trading-day count is then a query, not a
second ingest. (If Greg prefers a two-member manifest, `stage_block_sources.py --days 20211003 20211004` stages it; the
rest of this spec is unchanged.)

## Tech stack
Python 3.12 on Frankie's Linux box (i-035994afa8bdf66a5, 32 CPUs, 256 GB, 178 GB free, venv `/opt/frankie-box/venv`
with databento-dbn 0.62.0, zstandard, numpy); `operations/ingest_block_sources.py` (compact writer, `--workers`);
`compact_build_journal.py`; the box reached only by `frankie_box_run.yml` (one committed `deploy/aws/box/*.sh` over SSM,
sources by presigned GET through MAP_URL, the box's role reads nothing in S3).

## Commands
    # canary first (Greg's incremental-validation rule): rate only, no completion claim, receipt canary-receipt.json
    python research/kalshi/frankie_boss/operations/ingest_block_sources.py --manifest research/kalshi/frankie_boss/blocks/BLOCK_20211004_20211006_SOURCE_MANIFEST.json \
        --sources-dir /opt/frankie-box/data/block_20211004_20211006 --output-dir /opt/frankie-box/work/ingest-canary \
        --session-policy cme_trading_day --canary-records 20000 --workers 8
    # the ingest (one run; the receipt claims completion only when every member's count is reconciled)
    python research/kalshi/frankie_boss/operations/ingest_block_sources.py --manifest ... --sources-dir ... \
        --output-dir /opt/frankie-box/work/ingest-block_20211004_20211006 --session-policy cme_trading_day --workers 24
    # tests
    python -m pytest -q -p no:cacheprovider research/kalshi/frankie_boss/tests/test_ingest_block_sources.py research/kalshi/frankie_boss/tests/test_block_source_scope.py research/kalshi/frankie_boss/tests/test_compact_build_journal.py tests/test_frankie_box_ingest_block.py
Both box invocations are wrapped by ONE committed script, `deploy/aws/box/frankie_box_ingest_block.sh` (ACTION=fetch |
canary | ingest | status | publish), dispatched by `frankie_box_run.yml` with `presign=` the four member keys (fetch) and,
for publish, a presigned PUT (see Boundaries: ask first).

## Project structure
    research/kalshi/frankie_boss/operations/ingest_block_sources.py   the ingest (exists; unchanged unless a defect)
    research/kalshi/frankie_boss/blocks/BLOCK_20211004_20211006_SOURCE_MANIFEST.json   the staged block (exists)
    deploy/aws/box/frankie_box_ingest_block.sh                        NEW: the box wrapper (fetch by map, canary, ingest, status, publish)
    tests/test_frankie_box_ingest_block.py                            NEW: the wrapper's text contract (pins, never-overwrite, no keys)
    research/kalshi/frankie_boss/tests/test_ingest_block_sources.py   exists; gains the trading-day count query test if a query helper is added
    /opt/frankie-box/data/block_20211004_20211006/                    the four members on the box (pinned by the manifest's sha256s)
    /opt/frankie-box/work/ingest-block_20211004_20211006/             journal.compact.sqlite + ingestion receipt + canary receipt
    s3://bento-568968024170-us-east-2-an/frankie/block_20211004_20211006/compact/   the published container + receipt (publish step)

## Code style
The house style (one committed script, refuse-not-guess, every move receipted, no key ever printed):
    if os.path.exists(dest) and sha(dest) != want:
        raise SystemExit('a different file is already at ' + dest + '; not overwritten (move it aside with a receipt first)')
The trading day is the tool's own `cme_trading_day` rule (a record before the 21:00Z halt belongs to its date, at or after
it to the next); nothing in the wrapper re-derives a date.

## Testing strategy
- The tool's existing suites (block scope, ingest, compact journal) stay green; zero synthetic market data (fixtures are the
  tool's own journal-shaped fixture, never fabricated trades).
- The wrapper is text-contract tested (pins, the refusal strings, no boto3 on the box, no `rm` of data).
- On the box: the canary (20,000 records) BEFORE the ingest; its receipt's rate decides the worker count and the expected wall
  time, reported to Greg before the full run (his go per step).
- Completion = the tool's own reconciliation (every member's `mbo_records` equals the ingested count per member; the
  receipt's `completion_claimed` true), plus the trading-day session's count read back from the container.

## Boundaries
- Always: canary before the ingest; receipts for every step; the container's sha256 recorded before publish; report the
  trading-day count to Greg as a measurement (57,027 stays the Sunday slice's one measurement).
- Ask first: the publish route (the box's role writes nothing in S3: a presigned PUT added to `frankie_box_run.yml`
  (`presign_put=` input, the runner signs, the box `curl -T`s) versus S3 rights on the box's instance profile; both are
  Greg's AWS decisions); the worker count above 8; any change to `ingest_block_sources.py`.
- Never: pull from Databento; print or copy a key; delete or overwrite a member, a container or a receipt; run the ingest
  while the cycle unit runs on the box; claim completion from the canary.

## Success criteria
1. `canary-receipt.json` on the box with a measured rate; Greg has the rate and the projected wall time.
2. `journal.compact.sqlite` for the block with `completion_claimed: true`, per-member counts equal to the manifest's, sha256
   recorded in the ingestion receipt.
3. The trading-day session 2021-10-04 read back: first record at the Sunday 22:00Z open, last record before the Monday
   21:00Z halt, its record count reported (a number greater than 57,027; the exact value is the measurement).
4. The container and both receipts published to the S3 prefix above (or the publish route Greg chooses), pinned by sha256
   in a committed manifest (`blocks/BLOCK_20211004_20211006_COMPACT_MANIFEST.json`), `ingested: true` recorded.
5. Nothing on the box deleted or overwritten; the four members still present with the manifest's sha256s.

## Open questions (Greg)
1. Whole block (recommended, one ingest, four trading days labelled) or a two-member manifest?
2. The publish route: presigned PUT through the run workflow (no role change, no key on the box) or S3 rights on the box?
3. Worker count on the 32-CPU box after the canary's measured rate.
