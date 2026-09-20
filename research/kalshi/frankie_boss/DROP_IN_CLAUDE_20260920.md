# Frankie/BOSS drop-in — 2026-09-20

Paste this entire note into the new Claude session. It is the current handoff for the
GitHub branch `codex/frankie-launch-two-cycle-20260919` in `DavisAI1974/Markets`.

## First decision already made

Leave `a9ab5ec4` in place as the failed-run archive. Do not revert it and do not
touch `codex/journal-reduction-stack-20260915`. The branch has already been
reviewed and pushed; first verify the branch tip and read `CLAUDE.md` plus this file
before changing anything.

The GitHub Contents API was used because this attachment directory is not a checkout.
There are no uncommitted local files to clean up and no new files should be written to
the PC's C: or E: drives. Keep durable artifacts in Git and AWS.

## What is on the branch

The latest pre-handoff code tip is `fbbc5ce9fbd399733059e336cced05776bb62b2b`.
That commit fixes the remaining checks-only fixture failure by populating the
canonical attachment hash before the principal adapter is called. The preceding run
on `909c4683` had 1,099 passing, 1 skipped, and 2 helper-test failures caused by
the missing fixture field; this was a test-fixture failure, not evidence of a Frankie
runtime failure.

The branch contains the Pod credential-over-private-SSM implementation (read once in
memory) and the receiver's sealed-absence proof producer. The receiver validation
currently reports 352 passed tests and 234 passed subtests. The two changes unblock
the stage-5 credential path and the configuration path, respectively. The native
runtime code is frozen at `96e26f7d5e8100cca93288d5f44d9550ab5cfd9a`; the receiver
branch is frozen at `7b98617bdbbc2476666db9cf1c018c8efe6878da`.

## Checks and workflow

A checks-only run was dispatched against `fbbc5ce9`:

- Workflow: `frankie_journal_stack.yml`
- Run: `35497249802`
- Ref: `codex/frankie-launch-two-cycle-20260919`
- Inputs: day `20211003`, cycles `2`, `checks_only=true`, `keep_compute=true`

Poll that run before relying on it. Do not confuse the separate noisy
`ng_exhaustion_step1_receipt_count_20260823.yml` failure with this branch's
checks; it is unrelated to the Frankie fixture fix.

A separate successful retained-completion publication run is `35191316986`. It
recovered the historical September 15 completion and is not proof that the current
two-cycle Frankie run produced a new principal/classroom receipt.

## AWS/runtime evidence

The retained AWS prefix is:

`s3://frankie-granite42-568968024170-us-east-1/retained-granite/a7b72cf923f906c791e4a927dc72b7c61fa25f7ac263e66bb154be67056c22d8/migration-ycf4v6lmave6xw-a004983e93b9/`

Current request SHA:
`a7b72cf923f906c791e4a927dc72b7c61fa25f7ac263e66bb154be67056c22d8`

Durable records verified there include startup, start result, run, service-ready,
runtime config, observer, completed outcome, completion cleanup, finished, and stop
acknowledgement. The service-ready record is real (HTTP health 200, 13 model files,
Granite42 smoke model, L40S, context 131072, durable jobs_v1). The durable completion
record has:

- startup SHA `76199b692deeae1cb006baebd04c5f5c70176379f639b1d598d06712a57a83af`
- code commit `96e26f7d5e8100cca93288d5f44d9550ab5cfd9a`
- job `95ceee162e41f58838394706754dfbdf466089f92a2629c33e0cccdbf0837929`
- outcome SHA `c75feffdc10eed5eb63341d66cda2e5b9e7b967623f6fec406ff41128029132c`

That proves durable model-completion metadata exists. It does not prove that the
current two-cycle run produced the initial Frankie principal response, classroom
grade, correction, or downstream configuration receipt. The service-ready record
was written before inference and says `inference_sent:false`; preserve that
distinction.

Both AWS EC2 hosts were last verified `stopped`:
native `i-0e90ee6110ef609aa` in us-east-2 and ingest `i-035994afa8bdf66a5` in
us-east-1. Do not claim they are running. Do not restart them as part of this
handoff.

## Frankie state and the next ordered work

The classroom package and model-visible pre-message exist. There is no verified
initial response/classroom grade/correction receipt yet. The native run previously
reached `boss_reasoning` (cursor 3261, completed 0); do not invent or backfill the
missing text. Preserve the actual talks, feedback, corrections, and timestamps in
Git. The operator context says the model has had roughly six hours of training and
two calculations: early baseline, expected to improve, but no guaranteed result.

The next work must remain ordered:

1. Poll the checks-only run above and record its result in the handoff/run ledger.
2. If an actual two-cycle execution is intentionally launched, use the existing
   AWS-first workflow and record every request/start/ready/inference/finish/cleanup
   receipt under the durable S3 prefix and in Git. Do not import from Bento or
   Databento.
3. Produce the sealed-absence receipt for every absent downstream artifact and make
   the configuration consumer accept only the signed proof.
4. Measure per-record ingest cost before making scale claims. Open item 4 is the
   highest-priority scale question: 37.3 ms/record at about 97% dedication implies
   roughly 4.9 days for four weeks on the small runner. Fewer partitions remove
   per-partition overhead, but there is no measured proof that per-entry work moved.
5. Keep the full 18-section output and all 8 native threads. Use the pilot gate of
   30 scientific ledgers for the first sample; do not add a fixed output cap.

## Do not do these things

- Do not revert `a9ab5ec4`.
- Do not edit `codex/journal-reduction-stack-20260915`.
- Do not import from Bento/Databento or change the AWS-first credential path.
- Do not create artifacts on the local PC C: or E: drives.
- A go to run on Sunday is not, by itself, permission to change a workflow; only
  explicit new authorization permits workflow edits.
- Do not claim Claude or Frankie said something unless the durable transcript or
  receipt contains it.
- Do not claim a future STOP/cleanup result before its receipt is present.
- Do not claim all 19 prefixes are built: the verified source facts are 57,027
  source records, 114,054 input+applied entries, 1,189 target boxes, and the first
  two prefixes verified.

Keep this handoff factual, append new evidence rather than rewriting old receipts,
and commit every durable decision or measured result to this branch.
