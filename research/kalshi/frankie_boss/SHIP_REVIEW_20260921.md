# /ship review of the launch path since the Pod re-mint (2026-09-21, chat 3)

Scope: `git diff 35f857f0~1..b73c4d06` (22 commits, 20 files, +551/-99): the retained-Pod re-mint to
g7y3g2w1kor4l3, `frankie_box_control.yml`, the host diag / cycle-status probe additions (host CPU, Root
heartbeats, EC2 describe, region input), the Root heartbeat contract, and the handoff docs. Three personas ran in
parallel (code-reviewer, security-auditor, test-engineer); the merge and the decision are below. Nothing in the
range was modified by the review. This is the reviewed base that job 0 (Frankie's harness on his box) builds on.

## Ship Decision: GO (as the base for job 0), with the conditions below carried into job 0

No persona returned a Critical defect in the range. The one High (security) is retired by Greg's option A if the
rewritten task document drops the shared credentials; the two Mediums and the test gaps are queued, not blockers.

### Blockers (must fix before ship)
- None in the range.

### Conditions carried into job 0 (fix in job 0's own commits)
- security-auditor HIGH, `operations/ROOT_CYCLE_00_TASK_20260920.md:7,33-38,85-94`: the task document hands an
  external session the account-wide `Claude` IAM pair (S3/EC2/SSM/Bedrock-full, no boundary, already recorded
  "photographed, rotate post-walk" in KEYS.md) and the DavisAI1974 git identity. Option A moves Frankie's session
  onto the box: it authenticates through the instance profile `Ssm` (a role, no pair leaves AWS) and needs its own
  git credential scoped to `root/*`. The rewrite for the box removes the pair and the shared identity from the
  document. Key rotation stays on Greg's word after the runs (standing rule).
- test-engineer, `operations/day_pipeline.py:315-325`: `stop_compute` stops the ingest runner unconditionally, and
  the ingest runner IS Frankie's box now. Verified: it runs only in `frankie_journal_stack.yml`'s `always()` job
  when `keep_compute` is false; the live dispatch (35555649070) set it true, so the holding run cannot stop the
  box. Condition: every dispatch while the box is Frankie's keeps `keep_compute true`; a code guard that honours
  the `KeepRunning` tag is a recommended fix (below), not a blocker.
- test-engineer: `research/kalshi/frankie_raw_mbo_benchmark/` (eight of the ten producers) is NOT in this tree. It
  lives on origin `ccode/frankie-receiver-feed-20260916` at 2ebb8ce8 (a pinned sibling checkout, not a merge
  target). Job 0 step 2 fetches that ref onto the box and stages its tests with it, or the producers run untested.
  `research/ng_exhaustion_mbo_v4_state_adapter_20260820.py` is present and tested (41 passed, verbatim below).
- test-engineer: every `frankie_boss` test needs `torch` to collect (`__init__` imports `trunk`); the box's
  environment carries the CI pin (`torch==2.11.0` cpu) or the suites will not collect there.

### Recommended fixes (should fix, queued; none changes how Frankie runs)
- code-reviewer + security MEDIUM, `.github/workflows/frankie_box_control.yml:51-62`: the Start step is
  `continue-on-error: true` and the Tag step is gated on the inputs, not the start outcome, so a start that never
  reached `running` still tags KeepRunning=true and the job goes green. Fix: `id: start`, gate Tag and the summary
  on `steps.start.outcome == 'success'` or on the post-check state; restrict `instance`/`region` to a choice of the
  three known boxes.
- security MEDIUM, `.github/workflows/frankie_host_diag.yml:52` (and `frankie_pod_control.yml:50`,
  `frankie_refresh_bootstrap_urls.yml:36`, `frankie_deliver_readiness.yml:57`, `frankie_pod_prepare.yml:72-73`,
  `frankie_journal_stack.yml:87,112-113,179,240-245`): `${{ inputs.* }}` expanded inside `run:` bodies while the
  job env carries the AWS pair (and RunPod key). Move each input to `env:` as `frankie_box_control.yml` already
  does. Workflow files land via the GitHub API on Greg's word and are registered on the trunk.
- code-reviewer REQUIRED, `DROP_IN_CLAUDE_20260921.md:197-205`: the un-timestamped "Where everything is" block
  still names the retired Pod 8vqdacl5t61rjx, INFO_SHA256 6f8efdf9 and branch
  `claude/frankie-launch-verification-lqmv0m`; retitle it as superseded or update it (Greg's "no artifacts lying
  around").
- test-engineer, tests to add (all text/unit, no market data): box control cannot reach stop/resize
  (`options == [status, start]`, verbs literal); `pod_control` refuses to terminate the retained Pod (stub
  `control_call`); the retained identity is declared once (`RETAINED_POD` and the five workflow defaults equal
  `granite_retained_identity.POD_ID` / `JOURNAL_GENERATION`); `pod_prepare.migration_candidate` and
  `granite_retained_host.info_from_journal` overlay the same receipt identically; the heartbeat probe lifted out
  of the YAML heredoc and tested at 14.9/15.0/15.1 min, empty prefix (today: empty = not STALE, a silent-hang
  blind spot), truncated (>4 KiB) and non-JSON bodies; `day_pipeline.stop_compute` honours a KeepRunning tag.
- code-reviewer optional: `frankie_pod_prepare.yml:12` `source_pod` default still ycf4v6lmave6xw (confirm or
  comment); `pod_control` terminate now admits 8vqdacl5t61rjx and ycf4v6lmave6xw (a `RETIRED_PODS` refusal
  unless confirmed would encode Greg's "only on my word"); cycle-status S3 client pinned to us-east-1 while
  `bucket` is free text.
- security LOW: raw S3 key names and `root/*` branch names printed into the Actions log (workflow-command
  surface; print `repr`); heartbeat append-only is a convention, not enforced (versioning + delete deny +
  `--if-none-match`); box public DNS / private IP / profile printed and committed in the handoff; static AWS
  pair in every dispatchable workflow (OIDC per-workflow roles would remove it); boto3/botocore version-pinned,
  not hash-pinned.

### Acknowledged risks (shipping anyway)
- The re-mint's INFO_SHA256 bdad2896 cannot be re-derived offline (the source `pod-info.json` is on S3); the
  handoff records it from the prepare run's artifact, and the live `info_from_journal` read at the HOLD is the
  check. Mitigation: the overlay-agreement test above.
- This session holds an AWS pair in its environment that STS rejects (InvalidClientTokenId); no `aws` CLI. The
  route to the boxes stays `workflow_dispatch` with the repo secrets, as in the last chat. Mitigation: job 0 is
  driven through SSM workflows; the session credential is Greg's to fix.
- `~/.claude/skills/runpod-usage/reference/` is not on this container (the RunPod skills were never committed);
  no Pod action is in job 0, and none is taken before the reference is re-installed (`npx skills add
  runpod/skills`, scratchpad) and read.

### Rollback plan
- Trigger conditions: a job-0 step writes anything onto the native host or the retained run directory; the host
  runner (pid 3828, holding in `frankie_calculation`) stops or its cycle-00 files change; Frankie's box is
  stopped or resized by anything but Greg's word; a `root/*` push carries files that fail the recorder's shape or
  binding checks.
- Rollback procedure: job 0 touches only Frankie's box (i-035994afa8bdf66a5) and new git branches. Undo = the
  box's working directory is removed or the box is stopped on Greg's word (`frankie_box_control.yml` cannot stop
  it; `ec2_host.py stop` from a workflow only on his word); any `root/*` branch is superseded by a new push, never
  rewritten; nothing on the native host is touched, so the HOLD keeps waiting and the recorder path is unchanged.
  Code on this branch: `git revert <sha>` per commit; workflow registrations on the trunk are reverted the same
  way via the GitHub API on Greg's word.
- Recovery time objective: minutes for the branch; one box start (about 1 min to SSM Online) for the box.

### Verification story (verbatim from the personas)
- Re-mint consistency: `8vqdacl5t61rjx` survives only in a comment (`granite_retained_identity.py:10`), prose
  (`active_run_supersede.py:6`) and the deliberate selectable option (`frankie_retained_completion.yml:25`);
  `ycf4v6lmave6xw` only as `HISTORICAL_GENERATION`, usage strings and the `frankie_pod_prepare.yml:12` default;
  the old INFO_SHA256 6f8efdf9 in no `.py/.yml/.json`. All five workflow defaults read g7y3g2w1kor4l3.
- Stop/resize reachability: `frankie_box_control.yml` passes the verbs `status`/`start` literally (lines 49, 54);
  the `action` input reaches only `if:` conditions; inline Python calls only `create_tags`, `describe_instances`,
  `describe_instance_information`. `ec2_host.py` has no terminate action at all.
- Secrets: none in the range (grepped AKIA/ASIA, X-Amz-, rpa_/ghp_/github_pat_, PEM headers). `KEYS.md` is
  names-only across its whole history.
- Tests, with `torch==2.11.0` (cpu) installed to the CI pin:
  `test_lawful_recovery_migration.py test_granite_retained_completion.py test_retained_generation_publication.py
  test_granite_retained_host.py test_host_record_principal_response.py test_day_pipeline.py
  test_granite_runpod_controller.py` -> `42 passed in 5.41s`.
  `research/test_ng_exhaustion_mbo_v4_state_adapter_20260820.py test_reduction_stack_equivalence.py
  test_c15_full_evidence.py test_mbo_resume_state.py` -> `41 passed in 38.83s`.
  Without torch the same files give `6 errors during collection`.
- YAML: the four changed/new workflows parse (`yaml.safe_load`).
- Zero tests today for `pod_control.py`, `pod_prepare.py`, `deploy/aws/ec2_host.py`, `frankie_box_control.yml`,
  `frankie_host_cycle_status.yml/.ps1`, `frankie_host_diag.yml`.
