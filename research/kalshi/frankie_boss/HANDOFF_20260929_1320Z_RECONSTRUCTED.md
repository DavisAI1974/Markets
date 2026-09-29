# HANDOFF 2026-09-29 ~13:20Z (reconstructed): what happened after the 13:05Z handoff

The "Frankie codebase cleanup" chat stopped responding (context exhausted) while writing its handoff. A new chat
rebuilt the state from Greg's screenshots and the GitHub Actions record. The box was NOT probed over SSM, because the
AWS pair could not be installed in the rebuilding container. Read this AFTER, on branch
`claude/frankie-monday-cycle-0-urozez`:
`research/kalshi/frankie_boss/HANDOFF_20260929_TUEWED_DATAPOINTS.md` (its "Update ~13:05Z") and
`DROP_IN_20260929_TUEWED_DATAPOINTS.md` (the work list). This file is only the delta.

## Main box i-035994afa8bdf66a5 (us-east-1, 32 vCPU) at 13:00Z (from the old chat's last probe)
| Day | Progress | Est. finish |
|---|---|---|
| 20221004 | 1,500,000 / 1,640,652 | ~13:09Z |
| 20211013 | 1,000,000 / 1,341,217 | ~13:31Z |
| 20211012 | 1,070,000 / 1,477,942 | ~13:34Z |

- Wed 20211006 and 20221005 had SEALED. Load fell from 38 to 23 on 32 cores (~9 idle).
- All four pairs2 days (20211012/13, 20221004/05) and Wed 20211006 still need their DEFERRED verify:
  `frankie_box_ingest_block.sh ACTION=conform DIRECTORY=<ingest dir>`. Wednesday's conform is ~45 min, and its
  downstream steps (external, root, teacher, classroom, Jev) wait on it.

## Greg's calls after 13:05Z
- **"Yes, if there's spare room, fill it. As 2 leave, 2 enter."** This is rolling admission. Each time two ingests
  finish on a box, start the next two days (a pair out, a pair in). He said yes to both proposals: Wednesday's
  conform, and starting the confirmation pair 20241008/09 on the spare cores.
- No new boxes. The second-box hold still stands, but i-08cee (already set up) is in use for confirmation pairs.
- Billing question (answered in the new chat, see below).

## Dispatches after the 13:05Z handoff (GitHub `frankie_box_run.yml`, all at head 9c46da4b)
| Run | Time | What | Result |
|---|---|---|---|
| 36571845717 | 12:59Z | fetch on i-08cee with the default WORKERS=31 | FAILED: refused, 31 workers > 8 CPUs |
| 36572064486 | 13:01Z | `ingest_block ACTION=fetch WORKERS=7` 20241001/02 on **i-08cee** (us-east-2) | success (fetch done) |
| 36573340372 | 13:11Z | `ingest_block ACTION=fetch WORKERS=8` 20241008/09 on the **main box** | success; files already present ("restored"); receipts `receipts/ingest-fetch-20241008-1790687535.json`, `-20241009-1790687537.json` |
| 36573328607 | 13:11Z | unknown script (log not readable while running) | IN PROGRESS at 13:15Z |
| 36573332238 | 13:11Z | unknown script (log not readable while running) | IN PROGRESS at 13:15Z |

The two unknown runs are most likely the 20241008/09 ingest on the main box plus either Wednesday's conform or the
20241001/02 ingest on i-08cee. **Read both logs (the VARIABLES/COMMENT lines) before dispatching anything.** The
old chat was still dispatching at 13:11Z, after Greg asked for the handoff. Starting a day twice is the known trap
(the duplicate Wednesday earlier today), so confirm the old chat is closed.

Still running from before: GitHub runner ingest **36571235912** (12 discovery days: 20211019/20, 20221011/12,
20221018/19, 20231003/04, 20231010/11, 20231017/18; journals to `s3://bento-568968024170-us-east-2-an/frankie/ingest/`,
pointers on branch `frankie-ingest-pointers`). Status of Databento 36564541947 and free fetch 36557302661: re-check.
Confirmation-day facts `confirm7-20260929-1` are DONE (13 manifests committed in 9c46da4b).

## Confirmation-day wall (flag to Greg, do not resolve)
20241001/02 and 20241008/09 are CONFIRMATION days. Ingest (sealing a journal) is on Greg's word. Nothing past ingest
(external, root, teacher, classroom, Jev, search) runs on a confirmation day until the survivor list is frozen
(experiment-orchestrator section 4). Keep them out of any orchestrator STAGES beyond fetch,ingest.

## Keys
The old container's `~/.config/markets/env` is gone. Greg re-sent the Claude IAM pair as a screenshot. The new
chat's auto-mode permission check refused to write it to disk, so SSM probes from the container need Greg to allow
it (or to paste the pair where a chat may store it). Until then, probe through `frankie_box_run.yml`
(`frankie_box_progress.sh`). Greg: no rotation until the build is done.

## Greg's billing question (answered)
"If we kill the Windows box and get the exact same box for AWS, do I pay the full monthly fee twice, or is it prorated?"
- EC2 on-demand has **no monthly fee**. Compute is billed only for the time an instance runs, so two boxes are never
  charged a month each. The stopped Windows box i-0e90ee6110ef609aa (r7i.4xlarge) costs no compute now.
- What a stopped box still costs: its EBS disks (120 + 250 GB, roughly $30/month at gp3 rates) until they are deleted.
  Terminating removes the volumes marked delete-on-termination. Check the 250 GB data volume separately.
- A Linux box of the same size costs less per hour than Windows (no Windows licence in the rate).
- Exceptions that are real commitments: a Reserved Instance or Savings Plan (billed whether or not a box runs), or a
  Lightsail plan (prorated hourly up to its monthly cap). Check Billing, then Savings Plans / Reservations, if unsure.
- Quota trap: us-east-2 on-demand cap is 16 vCPU. i-08cee (8) is running, so a new 16 vCPU box there would be refused
  unless i-08cee stops or the quota is raised (the Claude user cannot request quotas). The stopped Windows box does
  not count against it.
