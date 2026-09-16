# Drop-in for the next chat - Frankie/BOSS, after 2026-09-16

Paste to Claude Code. Repository `DavisAI1974/Markets`. Run `using-agent-skills` first.
Read first: `research/kalshi/frankie_boss/CCODE_SESSION_20260916_RESTORE_BENCHMARK_COMPACT_SOURCE.md`
(what was measured and built), then `CCODE_RUNTIME_TOKEN_REVIEW_20260916.md` (the ranked
runtime/token review), then `SPEC_PREPARED_SOURCE_ONCE_20260916.md`.

## Branches

| branch | what |
|---|---|
| `ccode/frankie-lawful-recovery-review-20260915` | THE working branch, on top of ChatGPT's `58d6c023`; tip in `git log` |
| `claude/kalshi-s79-kickoff-ij8t9o` | default; PR #10 (idle EC2 guard) merged at `e975a493` |

## Live state

- Native host `i-0e90ee6110ef609aa` (r7i.4xlarge Windows, us-east-2b) STOPPED. Its volumes persist
  across stop/start; E: (vol-05c3d967e07b2d61f) holds the verified restore, torch 2.9.1+cpu and
  numpy 2.3.5 in `C:\Python313`, and `E:\bench` with the benchmark and profile results. An EBS
  snapshot of E: was taken after this session (`python deploy/aws/ec2_host.py --instance
  i-0e90ee6110ef609aa --env-file scratchpad/aws.env snapshots`).
- Start/stop: `python deploy/aws/ec2_host.py --instance i-0e90ee6110ef609aa --env-file scratchpad/aws.env start|stop|status`.
  About $1.80/h running. Stop it between steps; the idle guard also stops it at the six-hourly check.
- Restore set complete on S3 (`frankie/sunday_20260915_restore/`) plus addendum
  `RESTORATION_MANIFEST_ADDENDUM_20260916.json` in git. Rerunning the restore is idempotent (~50 s):
  presign with `deploy/aws/presign_restore_set.py` (writes the gitignored
  `deploy/aws/_frankie_host_restore_presigned.ps1`), then `deploy/aws/ssm_run_ps1.py`.
- Block Oct 4-6 sources staged: `frankie/block_20211004_20211006/sources/` on S3, manifest
  `blocks/BLOCK_20211004_20211006_SOURCE_MANIFEST.json`. NOTHING ingested, scheduled or prefixed.

## First business next chat

1. Start the host, run a DRY `prime_cache` on the retained cycle-1 compact prefix through the
   compact-source host (no training step), stop the host. This is the on-host proof of the cycle-1
   fix (review §7); everything else about that fix is measured and green on the workstation.
2. The architecture reviewer (Claude Desktop) has the review document; its questions are in §0/§7
   (block-level re-pin vs full re-drain), §1.1 (pinned witness vs runtime scan) and §3 (packet
   recipes). Land nothing from §8's after-Sunday list before the Sunday run.
3. Branch hygiene: the dual-compute branches must rebase onto this branch's reader fix (§7).
4. `.github/workflows/boss_frankie_tests.yml` is written and UNCOMMITTED on the workstation,
   pending Greg settling the flow (`SPEC_UNATTENDED_DAILY_PIPELINE_20260916.md`) and the result of
   a full local suite run, which was not completed this session.
5. Block Oct 4-6: sources staged with seam and halt checks clean (manifest hash `75c7134d…`);
   the ingestion path must be built per review §2 before any ingestion; session identity (§2.7)
   is a decision for Greg.

## Greg's standing orders from 2026-09-16

1. One more Sunday run by itself first. The 19-cycle run stays behind his explicit go; when it
   runs, the host carries `KeepRunning=true` for its duration and a declared, fixed thread count
   (recommend 8; 8 and 16 threads produce different result hashes).
2. Then the Oct 4-6 block as one continuous run, Sunday reopen through Wednesday's halt, so that
   cycles straddling the 17:00-18:00 ET halt can be seen. The block's data plane (ingestion,
   schedule, prefixes) may be brought in before the Sunday run is done; nothing that runs it.
3. Everything built for the one day is reused for the block with only the dates changed. The
   hard-coded Sunday literals (57027, 19, 20211003) listed in the session record become manifest fields.
4. Shrink runtime and tokens: the review document ranks the changes; the token reducer stack
   (static prefix, delta packet, rows per window) is what compounds over multi-day runs.
5. No more Windows after the Sunday run; everything built is OS-neutral Python.

## Do not

Run Frankie, Granite, the Pod, or any result-bearing cycle without Greg's go. Modify anything
under `E:\Codex\Frankie-BOSS-20260915` on the workstation. Leave the host running idle. Put
anything the next session needs in a scratchpad (D34: git and S3 only).
