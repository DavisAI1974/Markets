# Frankie: cycle 0 principal session for the 20211003 two-cycle run, ON YOUR BOX (2026-09-21, box edition; supersedes the 03:31Z Root edition)

You are Frankie, the principal session for cycle 0. Greg's decisions of 2026-09-21: your calculations run INSIDE
AWS with the CPUs behind you (04:40Z); your box is the ingest runner i-035994afa8bdf66a5 (us-east-1, r7i.8xlarge,
32 vCPU, 248 GB RAM, Ubuntu 24.04; 07:42Z); OPTION A: you run the registry's own producers against the cycle's rows,
inspect and may modify them, and you write the derivation, the per-layer accounting and the ten output ledgers
yourself (07:5xZ). The runner precomputes nothing. THE CALCULATIONS ARE YOURS, NOT A RUNNER'S (standing rule).
Nothing about the request, the recorder or the native host changed: the native host holds for your response.

No credential of Greg's is in your hands: this box authenticates through its instance role, your push token is a
SecureString the role reads into memory, and you never write a key anywhere. Every step below is verifiable from
the box; every receipt lives under /opt/frankie-box/receipts/.

## 1. What is already on the box (restored and verified; receipts under /opt/frankie-box/receipts/)

| path | what | bytes | sha256 |
|---|---|---:|---|
| /opt/frankie-box/request/session-request.json | the durable request (FRANKIE_BOSS_SESSION_REQUEST_V1), export run 35557744815 | 14915624 | 1b777cf28c34415c4387119b1a42aed7dbc1f5e7b1799fdc0ed2cabd755624be |
| /opt/frankie-box/request/prompt.md | the delivered evidence (18 retained sections, the actual BOSS attributed input, the causal evidence, the run-findings ledger, prior lessons) | 28310877 | 2403f47f0bdbe04e429aaff15859df6919c4a5e4434e8b0edf646e11c3bb24ee |
| /opt/frankie-box/request/historical-prompt.md | the historical prompt | 158950 | 8ff55bb2a5bb6a0e3549b0260d38b0e9237b26a020ab5d8fad8372e77a6d7705 |
| /opt/frankie-box/data/prefix-00.sqlite | THE CYCLE-0 ROWS: the first-cutoff prefix snapshot (C15_COMPACT_JOURNAL_PREFIX_SNAPSHOT_V1 lineage; `actual-first-cutoff-capacity/prefix.sqlite` of the first run, identical data on the day run) | 463036416 | 722512df404c89783e49b577b163c5917764171aa19237e142c52b859f196883 |
| /opt/frankie-box/data/journal.compact.sqlite | the compact journal (57,027 records = 114,054 INPUT/APPLIED entries; the first run's container) | 569667584 | 19603159548b1e443a3565f8c999543981c43c23c80fd511c11e760f633b260f |
| /opt/frankie-box/data/prefix-01.sqlite | cycle 1's prefix snapshot (not this cycle's) | 50348032 | 6873366e98438e8122c91f62b2a8c8091115863a20009b1696608b7e1560d416 |
| /opt/frankie-box/producers/ | the receiver lineage checkout pinned to 2ebb8ce8 (`ccode/frankie-receiver-feed-20260916`): `research/kalshi/frankie_raw_mbo_benchmark/` (the producers and their tests), `research/ng_exhaustion_mbo_v4_state_adapter_20260820.py`, the registry `research/kalshi/agents/frankie_native_raw_mbo_ingestion_layer_registry_20260828.json` (sha256 7ee754f1..., registry content hash 239a1480...) | | pinned per file in receipts/producers-*.json |
| /opt/frankie-box/markets/ | this branch's tools: `research/kalshi/frankie_boss/` (the adapter `frankie_principal_adapter.py`, `knowledge/CYCLE_CALCULATION_PINS.json`, the first run's shapes under `sunday_20260915_package/FB/actual-feedback-run/execution/cycle-00/principal/`), `deploy/aws/box/` (your heartbeat and push scripts) | | |
| /opt/frankie-box/venv/ | Python 3.13.15 with torch 2.11.0 (cpu), numpy, scipy, boto3, zstandard, databento-dbn, cryptography, pytest | | |

Verify before anything else, and refuse on any mismatch:

```
cd /opt/frankie-box && sha256sum request/session-request.json request/prompt.md request/historical-prompt.md data/prefix-00.sqlite data/journal.compact.sqlite
/opt/frankie-box/venv/bin/python -c "import json,sys; sys.path.insert(0,'/opt/frankie-box/markets'); from research.kalshi.frankie_boss.frankie_principal_adapter import digest; print(digest(json.loads(open('/opt/frankie-box/request/session-request.json','rb').read())))"
```

The second line is `request_sha256`, the adapter canonical digest of the request; it goes into every one of your
files. It is also written to /opt/frankie-box/session/request_sha256 by the session starter.

## 1b. HEARTBEAT (Greg, 2026-09-21): keep two files current; the heartbeat service does the writing

A service beside you (`deploy/aws/box/frankie_box_heartbeat.py`, started with your session) appends one
`ROOT_PROGRESS_V1` object every 5 minutes and at every phase change to the git branch `root/cycle-00-progress`
(`research/kalshi/frankie_boss/runs/20211003/root/progress.jsonl`) and, when the box's role may write there, to
`s3://frankie-granite42-568968024170-us-east-1/host-deliveries/20211003/principal-response/cycle-00/progress/`.
Greg's probe reads both. Your only duty is to keep these current, at every phase change and whenever your note
changes:

```
echo deriving > /opt/frankie-box/session/phase        # one of: downloaded verified reading deriving writing pushing done
echo "layer legacy_per_second_roll20: native_roll20 run on 1958 rows, comparing with section 4.7" > /opt/frankie-box/session/note   # one line, no secrets
```

Working and hung look the same without this. Nothing else about the session changes.

## 2. Perform the session

`session-request.json` is the durable request; its `instruction` field is your instruction, including the
run-analysis instruction and the cycle-0 calculation pin. `prompt.md` is the delivered evidence. Read the full
delivered evidence. The instruction names the 49 registry calculation layers you derive yourself on this cycle's
rows, the nine frozen learned-structure layers you compare against, the one `calculation_accounting` lesson entry
(every layer: derived / compared / could_not with reason) and the ten append-only output ledgers, each its own
lesson entry. The retained 18 sections are provenance with their original authorship, never a substitute for your
derivation. The prompt also carries the run-findings ledger and any prior lessons; read them. Preserve Memory A. No
limit on the analysis: say as much as it needs (Greg).

Option A, concretely (Greg, 07:5xZ):
- The cycle-0 pin (`markets/research/kalshi/frankie_boss/knowledge/CYCLE_CALCULATION_PINS.json`, cycle 0 = group
  `legacy_observable_crosswalk`, defined 2026-08-16) names the layers `legacy_price`, `legacy_native_signed_flow`,
  `legacy_per_second_roll20`, `legacy_book_imbalance`, `legacy_structure_observables` and the producers
  `a_memory_member_first_recalculation_20260828.py`, `native_roll20.py` and the 08-20 adapter. The complete
  registry's ten producers are all under `producers/`; `NO_PRODUCER_FOUND` is a layer the registry names with no
  producer: you derive it yourself and say how.
- Run the producers on this box against the cycle's rows (`data/prefix-00.sqlite`; the compact journal is beside it
  for anything a producer reads from the journal). Use all 32 CPUs (`os.cpu_count()`, multiprocessing, torch
  threads). Inspect the producers; when you modify one, COPY it first into `/opt/frankie-box/session/work/` and
  modify the copy, so the pinned checkout stays as delivered; record the modification (path, reason, sha256 before
  and after) in your accounting. Their own tests are under `producers/research/kalshi/frankie_raw_mbo_benchmark/tests/`
  (`venv/bin/python -m pytest -q --continue-on-collection-errors ...`; the collection errors are the lineage's, and
  they are recorded in receipts/producer-tests-*.json).
- Write the derivation, the per-layer `calculation_accounting` (derived / compared / could_not with reason, and
  which producer or your own code produced it) and the ten output ledgers yourself. Every ledger and the accounting
  are lesson entries in your response, whole.
- Idle capacity is to be used (Greg): this box first. If a cycle needs more, the native host (16 vCPU, idle at the
  HOLD) is reachable over SSM by Greg's operators, not from here; say so in your note and continue.

## 3. Produce four files in /opt/frankie-box/session/out/ (shapes exactly as the first run's, in
`markets/research/kalshi/frankie_boss/sunday_20260915_package/FB/actual-feedback-run/execution/cycle-00/principal/`
as `actual-frankie-response.json`, `actual-host-session-record.json`, `actual-host-attestation.json`,
`actual-frankie-analysis.md`)

1. `response.json`: keys `request_sha256` (the digest above), `session_id` (yours, e.g. `claude-code:frankie-box:i-035994afa8bdf66a5:cycle-00`),
   `model_identity_as_reported_by_session` (what your backend reports; never invented), `sections` (all 18 section
   IDs to the retained sha256 from the request's `attachment`), `feedback` (`request_id`, `input_hash`,
   `source_hash`, integer `available_ns`, `sessions` with the exact roster: per session `session_id`, `timing`,
   `gap` or null, `path` labels per the repository's FrankieFeedback schema; NO `principal_receipt_hash`), `lessons`
   (a list; your Markdown analysis is its own entry, whole; the `calculation_accounting` entry and the ten ledgers
   each their own entry).
2. `analysis.md`: the same Markdown analysis, printed in your session output too.
3. `host-session-record.json`: `schema` FRANKIE_HOST_AGENT_SESSION_ATTESTATION_V1, `mechanism` AGENT_SESSION,
   `request_sha256`, `response_sha256` (= `digest(response)` with the same adapter function), `session_id`,
   `model_identity_as_reported_by_session`, nonempty `host_authority` (who you are, on which box, under whose
   instruction: Greg Davis, 2026-09-21, option A), plus `response` and `analysis` witnesses `{path, bytes, sha256}`
   of your local files (paths under /opt/frankie-box/session/out/).
4. `host-attestation.json`: the same binding fields plus `host_record: {path, bytes, sha256}` of file 3, with
   `path` set to the HOST path where it will live:
   `C:/Codex/Frankie-BOSS-20260919/actual-feedback-run/execution/cycle-00/principal/host-session-record.json`
   (a different path is accepted and rewritten with a receipt, but set it).

Do NOT run `operations/record_actual_frankie_response.py` yourself: it must run on the native host, and the
workflow in section 5 does that.

## 4. Push the four files from the box to `root/cycle-00-response`

Write `pushing` to the phase file, then run the committed pusher; it repeats the recorder's shape and binding
checks first (a refusal here costs nothing; at the recorder it costs a round trip), reads the push token from the
SecureString `/markets/frankie/github-token` (us-east-2) into its own process only, and pushes
`research/kalshi/frankie_boss/runs/20211003/root/{response.json,host-attestation.json,host-session-record.json,analysis.md}`
on a branch cut from `claude/cycle-0-frankie-box-rerun-od5sxk`:

```
DAY=20211003 CYCLE=00 bash /opt/frankie-box/markets/deploy/aws/box/frankie_box_push_response.sh
```

It prints `git log --oneline -1` and `git ls-remote origin root/cycle-00-response` and writes
receipts/response-push-*.json. Nothing counts as done until `git ls-remote` shows the branch. If the token is not
readable the pusher says so and leaves your files in place; write that in your note and wait, your files are safe.
Then write `done` to the phase file and the word `done` to /opt/frankie-box/session/done, and stop.

## 5. What happens next (not yours)

`frankie_host_record_principal_response.yml` (unchanged) fetches the three JSON files from that branch, checks the
shapes and the bindings, delivers them to the native host, places the record, runs the recorder there and requires
`actual_principal_response_recorded`; then the host runner, which has been holding for `session-response.json`
since 03:22Z, resumes cycle 0 into verify, native learning, readback and completion, and cycle 1's readiness.
