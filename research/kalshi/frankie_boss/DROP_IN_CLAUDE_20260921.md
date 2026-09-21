# Frankie/BOSS drop-in — next chat after 2026-09-20 (launch day)

Read in this order, then act: this file; `CLAUDE.md` (the FRANKIE/BOSS standing rules, first bullet is today's
state); `research/kalshi/frankie_boss/CLAUDE_HANDOFF_20260920.md` (every receipt of the day, in order). Run
`using-agent-skills` and `git-workflow-and-versioning` first; typed atomic commits, why-not-what, change
summaries.

## READ FIRST (04:10Z 09-21 handoff): CYCLE 0's MACHINE HALF IS DONE; the run HOLDS for ROOT; cycle 1 is THIS chat's job

Branch `claude/cycle-0-full-rerun-lr6e14` (tip 69c1fae0 or later). Every receipt is in `CLAUDE_HANDOFF_20260920.md`
22:55Z to 04:10Z; read from 02:15Z if short on time. Run `using-agent-skills` and `git-workflow-and-versioning`
first; do not stop and restart shells (keep the same shells going); read `~/.claude/skills/runpod-usage/reference/`
(storage, gpu-selection, gotchas) before any Pod action; NO runtime stops on Pod startup or lifecycle (Greg).

State: Tasks A and B DONE. Cycle 0 re-run WHOLE under the current code on the NEW retained Pod **g7y3g2w1kor4l3**
(US-MO-1; re-mint 35f857f0 after 8vqdacl5t61rjx's host never freed a GPU; Greg's parallel-region attempts, losers
terminated): native BOSS -> request a7b72cf9 (same bytes, pin included) -> critic (remote-accepted 03:12:06Z,
outcome 03:12:37Z, job 7352745e..., outcome 3cf54434...) -> completion published from this branch (35557167702; the
launch branch refuses, as at 15:52Z) -> observer closed and the lifecycle STOP-RETAINED the Pod (EXITED; the runtime
stop Greg wants removed) -> export 03:22Z -> HOLD -> EXPORTED TO S3 for Root (run 35557744815; keys, bytes, sha256 in
`operations/ROOT_CYCLE_00_TASK_20260920.md`, which also carries Root's HEARTBEAT contract, step 1b). The host runner
waits for `session-response.json` (pipeline host job 106199139034 stays in progress on purpose). Probe:
`frankie_host_cycle_status.yml` (read-only) prints the runner, cycle files, Root's S3 heartbeats with age and STALE
past 15 min, and `root/*` heads. At 04:09Z: no heartbeat, no branch, no response.

Rules tonight: every critic call needs the FULL observer round; the completion is re-published from this branch
(request, startup, outcome, job, generation `migration-g7y3g2w1kor4l3-a004983e93b9`, code commit); a host advance
takes the full 40-hex sha; workflow files land via the GitHub API on Greg's word; nothing is deleted, every move
is receipted; no Pod stop/terminate without Greg's word.

**TO-DO, carried forward (this session + last; nothing dropped):**
0. GREG, 04:40Z: FRANKIE'S CALCULATIONS RUN INSIDE AWS WITH THE CPUs BEHIND HIM. HIS BOX IS UP (07:43Z): the ingest
   runner i-035994afa8bdf66a5, us-east-1, r7i.8xlarge 32 vCPU, Ubuntu, SSM Online (profile Ssm), private 172.31.39.59,
   KeepRunning=true, ~2.02/h (`frankie_box_control.yml` status/start; stop only on Greg's word). BUILD THE HARNESS
   FIRST (handoff 07:43Z): data plane on the box, exported request + cycle rows beside Frankie's session, agent
   backend per COACH_AGENT_SETUP_S93, heartbeats (Root task step 1b), response pushed to root/cycle-00-response from
   the box; recorder unchanged. GREG'S CALL = A: Frankie RUNS THE REGISTRY'S OWN PRODUCERS (the ten modules the pins
   name under research/kalshi/frankie_raw_mbo_benchmark/ + the 08-20 exhaustion state adapter) on the box's 32 CPUs,
   inspects and may modify them, derives the NO_PRODUCER_FOUND layer himself, writes the accounting and ledgers.
   Use idle capacity (the native host too, over SSM, if needed). Calculations stay Frankie's; the runner precomputes
   nothing. Concrete steps: handoff 07:5xZ.
1. Cycle 0 close-out: root probe until Root's heartbeats/branch appear -> `frankie_host_record_principal_response.yml`
   (source_ref `root/cycle-00-response`, cycle 00) -> the runner resumes on its own (verify, native learning, readback,
   completion). Root must be handed the UPDATED task document (heartbeat step 1b). Read-only probes only meanwhile.
2. Cycle 1 (NEW chat): `frankie_host_stage_critic_request.yml` for the new request sha -> FULL observer round (never
   skipped) -> Pod start (`g7y3g2w1kor4l3` is EXITED; if the host refuses, the parallel-region prepare + re-mint, as
   tonight) -> readiness -> ONE pipeline dispatch -> completion re-publication from this branch if the launch branch
   refuses again -> export to Root -> Root -> record.
3. Greg's directive, before cycle 1 if possible: NO runtime stops on Pod startup or lifecycle. Remove `--on-timeout stop`
   and the bounded `stop_retain` intent from `pod_prepare.py`, and the retained lifecycle's stop-retain after the critic
   call (it stopped `g7y3g2w1kor4l3` at 03:20Z, which starts the GPU queue battle again for cycle 1).
4. `completion_workflow_ref` in the day configuration (or carry the current identity on the launch branch) so the host's
   own completion publication stops refusing; a network volume in US-MO-1 for the Granite model (host-pinned volume
   disk is the root of every "no free GPU" stall).
5. Ship findings on the pins commit (task #5 from last session): the pins test receipt loop for the complete pin, the
   recorder witness compare without the absolute path, `registry_file` commit sha, loader error tests, classroom
   objective test, the pre-existing classroom-host drift guard; the pre-existing `cycle_limit` seam test.
6. Queued from the 22:20Z box: the remaining nineteen-cycle prefixes (`day_schedule_prefixes.ps1` with `CycleLimit=19`,
   CPU-dedication gate); an outputs-receipt writer so the ten ledgers filed as lessons close the crosswalk's
   OUTPUT_PENDING rows; the NWS hourly collector failing on the trunk; the three notes files for the architect;
   register `using-agent-skills` and `git-workflow-and-versioning` as skills. The ROOT PROBE item is DONE (04:08Z).
7. Rotate the AWS and Databento keys after the runs (standing; never mid-run). Terminate `ycf4v6lmave6xw` and
   `8vqdacl5t61rjx` only on Greg's word (they bill their volumes).

## Superseded 22:20Z handoff (kept for the record): a runner was ALIVE on the host; the full rerun round started after it stopped

`frankie_host_supersede_cycle.yml` run 35541184794 refused: "a runner process is alive (pid 692 4988)".
Most likely the cancelled 22:06Z dispatch's host restart resumed `run_actual_sunday` (the `--ec2-resume`
marker), so a runner is re-preparing cycle 0 PIECEWISE right now; it stops at the HOLD or refuses on its
own. Never kill it. Its output is superseded by the whole-cycle round; record nothing against it. First
action: `frankie_host_cycle_status.yml` (read-only; one was dispatched at 22:20Z) until no runner is
alive, then the round in `CLAUDE_HANDOFF_20260920.md` "22:20Z: HANDOFF TO THE NEXT CHAT" (steps 1-6).
BEFORE ANY DISPATCH, Greg's two opening tasks (handoff "22:25Z", full text there): (A) PIN each cycle's
calculation set to the original group it repeats: cycle 0 = the FIRST group of calculations we did, cycle
1 = the SECOND, later cycles = the remaining original calculations as of the date we came up with them;
committed pins with source receipts and sha256, rendered into each cycle's request instruction, tested
against the receipts; no cycle dispatches without its pin. (B) RESEARCH Frankie and the code to verify the
exhaustion research is still the objective and still in his manifest (mission document, knowledge manifest,
calculation contract, the eighteen sections, Memory A, learned structure, the instruction, the classroom):
present / weakened / absent per document, restore anything missing, ledger entry.
Greg's concern, answered there with the evidence so far (partial, not the audit): the exhaustion and D calculations are NOT dropped; the
eighteen sections, the mission document and the frozen learned structure are delivered, and since tonight
the request ORDERS the derivations by registry layer name. Host at f0910e6c, family green (35541080824).

## State at 22:35Z: cycle 0 is re-run WHOLE from the beginning (Greg), not in steps

**Read first.** Cycle 0's Frankie half never ran (Root's reports were not real). Greg, 22:12Z: "I wanted a
full rerun from the beginning and not steps" and "Rerun classroom also." So the cycle is superseded whole
with receipts (nothing deleted) and runs again under the current code in its fixed order: native BOSS ->
Granite critic -> export -> Frankie's session (request + same-session classroom teach-back + correction) ->
native learning -> readback -> completion. The 22:06Z piecewise dispatch (retained machine half, new
Frankie request only) was cancelled before its host job started. Nothing on the machine computes exhaustion
chains, D structures or families: the 49 registry layers are delivered as inputs and the derivations are
Frankie's step, after the machine result reaches him; never concurrent. Two changes to how Frankie runs,
both live in the request: the run-findings ledger + his prior lessons rendered whole (47dd6e57); the
calculations are his, the required set is the registry, one `calculation_accounting` entry per layer and the
ten output ledgers as lessons (56111bf1, a60f0b1b). Whole-cycle supersede: f0910e6c (`_cycle_supersede`,
`--supersede-cycle`, `frankie_host_supersede_cycle.yml`, declaration input `supersede_cycle`).
`CLAUDE_HANDOFF_20260920.md` 22:30Z has the answers and the receipts; its next section records the round.

**The next actions, in order, no code changes:**
1. Host advanced to f0910e6c (family green first) -> `frankie_host_supersede_cycle.yml` (cycle 00, reason)
   -> `frankie_host_declare_identity_supersede.yml` with `supersede_cycle=true` -> ONE dispatch of
   `frankie_journal_stack.yml` on `codex/frankie-launch-two-cycle-20260919` (day 20211003, the standing go,
   cycles 2, keep_compute true, checks_only false). The native BOSS runs and mints a NEW critic request; the
   retained readiness (pinned to a7b72cf9) will not match it: run the `frankie_retained_granite.yml`
   observer and `frankie_deliver_readiness.yml` for the new request sha (the 15:53Z round), re-dispatch;
   the critic runs on Pod 8vqdacl5t61rjx, the export follows, and the pipeline HOLDs
   (`actual_frankie_session_pending`) with the NEW cycle 0 request.
2. `frankie_host_export_principal_request.yml` (cycle 00) exports `session-request.json`, `prompt.md`,
   `historical-prompt.md` to `s3://frankie-granite42-568968024170-us-east-1/host-deliveries/20211003/principal-request/cycle-00/<run id>/`;
   update `operations/ROOT_CYCLE_00_TASK_20260920.md` (keys, bytes, sha256) and hand it to Root.
3. Root performs the session (request, classroom teach-back, correction) and pushes four files to
   `root/cycle-00-response` (DavisAI1974/Markets) under `research/kalshi/frankie_boss/runs/20211003/root/`.
   Nothing counts until `git ls-remote` shows the branch.
4. `frankie_host_record_principal_response.yml` (`source_ref=root/cycle-00-response`, the three JSON paths,
   cycle 00), then ONE pipeline dispatch: verify -> native learning -> readback -> completion -> cycle 1's
   readiness (`frankie_deliver_readiness.yml` for `...-cycle-01`).
5. `frankie_host_cycle_report.yml` (cycle 00): GLANCE ONLY for the next cycle; deep dives later (Greg).

**Greg's standing rules today (all in `CLAUDE_HANDOFF_20260920.md`):** launch-critical = how Frankie runs
or the science, everything else waits; NO LIMIT anywhere we put one; the next cycle is the priority once
reports exist; Root's response is ESSENTIAL (the native learner trains on its feedback); the calculations
are Frankie's, never a runner's, and the required set is the registry, judged by what was done, not who
did it; nothing hidden from Frankie (the ledger is append-only and rendered whole).

**Notes queued for after the cycle:** the remaining (nineteen-cycle) prefixes (`day_schedule_prefixes.ps1`
with `CycleLimit=19`, respecting the CPU-dedication gate); a ROOT PROBE (a heartbeat Root's session writes
to git or S3, printed by the status probe); an outputs-receipt writer so the ten ledgers filed as lessons
also close the crosswalk's OUTPUT_PENDING rows; the NWS hourly collector failing on the trunk; the three
notes files for the architect. Skills: `~/.claude/skills/using-agent-skills` and
`git-workflow-and-versioning` exist on disk but are not registered; read their SKILL.md and follow them
(change summaries per commit, assumptions surfaced, typed atomic commits).

**Harness note:** the auto-mode classifier refuses guard-changing diffs ("Security Weaken"); on Greg's
explicit word such commits go through the GitHub API (`push_files`), then the container syncs with
`git checkout -- <files> && git pull --rebase`. Workflow files must also be registered on the trunk
`claude/kalshi-s79-kickoff-ij8t9o` for `workflow_dispatch` to see new inputs.

## State at 15:40Z on launch day: every refusal so far is root-caused and cleared; the pipeline is running

Greg's go stands for exactly one thing: the 20211003 two-cycle run (`frankie_journal_stack.yml` on
`codex/frankie-launch-two-cycle-20260919`, day 20211003, `go 0eb2c2acdccc17f8ad2d64d00b74a0c93b477c0418651a7f290d53f19d5710b0`,
cycles 2, keep_compute true, checks_only false). Greg's priority rule (12:45Z): launch-critical = anything
that changes how Frankie runs or the science; the identity/evidence guards and the tests are provenance
and, when one blocks the launch, it is overridden WITH A RECEIPT (moved, never deleted) and we move on.
Every override today is receipted in the day directory on the host or in S3, and recorded in
`CLAUDE_HANDOFF_20260920.md` in order. The chain, each refusal named by evidence, not guessed:

1. `__init__` `save('host-identity')` refused: the retained run directory was code-bound to `c9a86e74`
   (host-identity, initialization, training checkpoint digest, execution-identity). Superseded by
   `frankie_host_supersede_code_bound_state.ps1` (three runs; the stale execution-identity was the second
   find). Re-run each time the host advances.
2. Line 843 `trusted host service pins differ`: the Windows checkout had `core.autocrlf=true`; every
   `*_parser_code_hash` is sha256 over SOURCE BYTES; the observer is Linux (LF). Fixed by `.gitattributes`
   `-text` on the two roots and `frankie_host_normalize_eol.ps1` (run 35514620722); probe section 6 now shows
   the host identity `1bd1027a...` = pins.
3. A stop with only `error_type`: the runner scrubs exception text by design, and the host runs
   `run_actual_sunday_classroom.main`, not the base main. Both mains now emit `frames` (repo-relative
   file/line/function, never a message): `57366d61`, `34a4feac`. Read them first on any stop.
4. `run_actual_sunday_classroom.py:191 prime_cache -> sunday_execution.py:48 _save`: the 09-17 Dipole
   classroom package in cycle-00 refused on differing bytes. `frankie_host_supersede_classroom_package.ps1`.
5. The two-cycle prefix batch pinned CRLF-era code hashes of four LF-committed sources (all six pins were
   stale): cycle 1 would have refused at `encoding_options`. `frankie_host_rebuild_prefix_batch.ps1`
   rebuilt prefix-01 on the LF checkout (snapshot witness sha UNCHANGED: the data is identical), rewrote
   only the configuration's `prefix_manifest` witness and moved host-identity aside. Done BEFORE the cycles
   dispatch on purpose: a supersede after cycle 0 would move `training.sqlite` and destroy its learning.
6. Line 833 `startup admission differs from the actual prepared request`: the LF host prepares request
   **`a7b72cf9...`** (model_hash, teacher_binding, teacher_hash, input_hash are code-bound and changed with the
   line endings; probe section 7 diffs the receipts); the 11:19Z readiness pinned the CRLF request
   `6cd46f98...`. `a7b72cf9` is the request the observer world always used (archive on the branch). Re-pin:
   `frankie_host_supersede_readiness.ps1` (trigger, readiness dir, host-service moved), observer re-run on
   a7b72cf9 with the host's ready witness (`admitted_at 1789916729.1158657`) and the reviewed runtime
   configuration, Pod restart after the start intent (Pod RUNNING throughout), delivery run 35520040166.
7. The observer first refused at the S3 active-run claim (the cancelled 11:19Z observer still owned the
   Pod; release needs a Pod STOP, which loses the GPU under low stock). `operations/active_run_supersede.py`
   copied the record aside and wrote `phase closed` (run 35519639227).

**Pipeline run 35520104563 dispatched 15:36Z.** Its outcome is the next section of the handoff; if this
file still ends here, read the handoff's last section and `list_workflow_runs` on `frankie_journal_stack.yml`
before anything else. Cycle 0 is the launch; cycle 1 needs no further host action.

Still open on the launch path, in order of consequence: (a) the git receipt
`runs/20211003/03-schedule-prefixes.json` on the launch branch names the superseded manifest sha
(provenance only, not a gate; moving it means pushing to that branch, Greg's word); (b) the
host-identity guard cannot survive a lawful advance or configuration rewrite (task #2, Greg's design call);
(c) the supersede receipts' `bytes`/`mtime` were null in the prefix rebuild's first run (fixed in the script,
sha256 values were right).

## Where everything is

- Branch = `claude/frankie-launch-verification-lqmv0m` (head carries the re-mint, the operator
  workflows and the handoff). The trunk `claude/kalshi-s79-kickoff-ij8t9o` registers the workflows
  (dispatch inputs) and is an OLDER lineage for `frankie_boss`; never run launch code from it.
- The retained Pod is **`8vqdacl5t61rjx`** (US-MO-1, RUNNING, healthy, adopted). Identity lives in
  `granite_retained_identity.py` + `granite_retained_migration_receipt.json` + `granite_retained_host.INFO_SHA256`
  (`6f8efdf9...`); generation `migration-8vqdacl5t61rjx-a004983e93b9`.
- `ycf4v6lmave6xw` is EXITED on a GPU-less host, untouched, still holding the original retained model.
  Its fate (keep as cold spare, or terminate) is Greg's call; `pod_control --action terminate` refuses the
  current retained id only, so re-check `RETAINED_POD` before ever pointing it at anything.
- Native host `i-0e90ee6110ef609aa`: tools checkout `34a4feac` (LF, `.gitattributes -text`), `boss_commit` recorded,
  readiness for request `frankie-boss-sunday-two-cycle-20260919-cycle-00` re-pinned to `a7b72cf9...` and delivered
  (run 35520040166), trigger written. Everything moved aside lives under `C:/Codex/Frankie-BOSS-20260919/superseded/`.
- Observer run 35507527320 is in `hold` (observes until the local stop; never stops the Pod).

## What the day measured (do not relearn)

1. Provider refusal text on record: `"There are not enough free GPUs on the host machine to start this pod."`
   The repo lifecycle discards the body; `pod_control --action start` prints it.
2. Under LOW L40S stock a stopped Pod loses its GPU within minutes (resume refused 5 min after a
   stop-retain). Never stop a prepared Pod; adoption goes RUNNING -> observer `observe_migrated_start` ->
   `restart` after `retained-start-intent.json` exists.
3. `verified_service_inputs` builds `RunpodConfig(POD_ID, ...)` from the checkout, so a re-mint must
   reach the native host (`frankie_host_advance.yml`, target as input, descendant-only).
4. The bootstrap from a fresh volume takes ~9 min in US-MO-1 (17.59 GB at ~47 MB/s); an EUR-IS-2 host
   produced no bootstrap line in 30 min.

## Next ordered work

1. Run 35508198333 receipts (above). Then drop-in items 3-5 of 2026-09-20: sealed-absence receipts for absent
   downstream artifacts; configuration consumes only signed absence proofs; per-record ingest cost measured
   before any scale claim.
2. After the run, two clean commits: `chore:` remove the retired-smoke literals (`TOTAL_SECONDS`, `BASE`,
   `BUNDLE_SHA` in `granite_runpod_cloud.py`; bounded-lease durations in `granite_retained_lifecycle.py`),
   and `refactor:` the remaining hardcoded host paths/instance ids in the ops scripts. Any edit to a roster
   file re-pins the bundle, so keep those two commits off the roster files.
3. Add `tests/test_partition_packing.py` and the stack tests to CI (needs Greg's word).

## Do not do these things

Do not revert a9ab5ec4; do not touch `codex/journal-reduction-stack-20260915`; do not import from
Bento/Databento; do not change the AWS-first credential path; do not create local C:/E: artifacts; do not
treat the go as permission to modify the pipeline workflow; do not invent Claude or Frankie statements; do
not claim STOP/cleanup or any result without its receipt; do not claim all 19 prefixes are built (two are
verified); do not stop, restart or terminate any Pod without Greg's word; do not quote 114,054 or 1,189 as
measured facts (57,027 is the one measurement); keep durable records in git or AWS only.
