# /ship review, 2026-09-21 chat 6: the three trunk registrations

Change under review: registering `frankie_box_fetch_response.yml`, `frankie_serverless_reading.yml` and
`frankie_box_codecs_ci.yml` on the default branch `claude/kalshi-s79-kickoff-ij8t9o` (workflow_dispatch resolves the
FILE there; the checkout inside each takes the dispatched ref, so scripts come from the working branch). Three personas
ran in parallel (code-reviewer, security-auditor, test-engineer), read-only; every finding below was re-verified
against the files in the main context before a fix was applied. Registration itself stays GREG'S CALL.

## Ship Decision: GO, after the fixes (applied in this chat; nothing left blocking)

- `frankie_box_fetch_response.yml`: GO as it stood. Matches the registered sibling's conventions (SHA-pinned actions,
  repo guard, inputs via env with regex validation, masked presigned URLs, fail-closed exits, `contents: write` only
  where the push needs it), re-derives every recorder check independently of the box. No change made.
- `frankie_box_codecs_ci.yml`: GO. One additive change: the push trigger now also watches the three modules the
  reading and stacked tests import (`granite_context_stacked`, `c15_journal`, `causal_packet`) and runs the new
  endpoint tests. CI command replicated locally on Python 3.11 and 3.13 with only pytest 9.1.1: 41 passed.
- `frankie_serverless_reading.yml` + `serverless_reading_endpoint.py`: NO-GO as it stood, GO after these fixes
  (commits on this branch, this chat):
  1. Six free-form inputs were expanded inside the run block (expression injection with the key in the environment).
     Now: every input in `env:`, a validate step with regexes (as `frankie_box_run.yml`), dry-run proven: defaults
     pass, `x"; env; echo "` refused.
  2. `curl -sSL https://cli.runpod.net | bash` (unpinned, unverified) ran with RUNPOD_API_KEY set job-wide. Now: the
     tagged runpodctl 2.14.0 release binary, sha256 `2e0fd370...38be9` recorded in the file and checked, version
     asserted; the key is in the one step that calls the script.
  3. `create` was not idempotent while `k1sqt0haffm61y` is live and billable, and nothing serialized dispatches. Now:
     `create` lists the account's endpoints (fails closed), refuses a same-name match unless `confirm=create-another`;
     `concurrency: serverless-reading`; workers 1..16 and seqs 1..2 ceilings; a fail-closed `*)` arm.
  4. `ctl()` printed the full argv, which would print `--env HF_TOKEN=<value>` (unreachable from the workflow, which
     never passes `--hf-token-env`). Now: credential-named env values are redacted in the print and covered by the
     echo guard. Prove-It test failed before the fix, passes after.
  Verification: `tests/test_frankie_serverless_reading_endpoint.py` (8 tests, fakes for runpodctl and REST, no
  network), YAML parse, actionlint 1.7.7 clean on all three files, `py_compile`.

## Blockers (must fix before ship)
- None remaining.

## Recommended fixes (should fix; NOT done here, launch-critical rule: everything else waits)
- security-auditor MEDIUM: the static `Claude` IAM pair (S3 + EC2 + SSM + Bedrock full) is job-wide in every
  `frankie_*` workflow. Replace with an OIDC role scoped to `ssm:SendCommand` on the box, `GetCommandInvocation`,
  `DescribeInstanceInformation`, and the two S3 prefixes; then rotate the pair. Pre-existing posture, not this change.
- Presign expiry 3600 s vs the 900 s box step (`fetch_response.yml`): set both to 900.
- A credential-pattern scan of the four box-authored files before `git add` in the delivery path (and in
  `frankie_box_push_response.sh` before upload).
- The recorder's shape/binding checks live three times (workflow heredoc, pusher, adapter); extract and pin equal.
- test-engineer C1/C2/H1-H4 on the codecs: L5 containment is asserted on the legend text (fixture below 4096 B, so L5
  never fires); `digest_text`/`per_second_rows` at 0% coverage; the silent-fallback contract proven on 2 of 5 paths;
  the digest parser accepts Unicode digits and ignores trailing rows beyond the declared count. Renderer never emits
  those, parse-back proof holds; tests to add after cycle 1.
- Artifact uploads carry raw stdout (masking covers the live log only); defensive grep for MAP_URL before upload.

## Acknowledged risks (shipping anyway)
- Dispatch rights: on a public repo only write collaborators can dispatch; a write collaborator already holds the same
  power by pushing a workflow to a branch. The fixes remove the foot-guns, not that trust boundary.
- Artifacts (90-day retention on the serverless run) are downloadable by any logged-in GitHub user; the script prints
  scrubbed JSON only.

## Rollback plan
- Trigger: a registered workflow misbehaves on dispatch (wrong ref, unexpected create, a refused validate).
- Procedure: nothing to roll back on the trunk beyond the three files; `git revert` the registration commit on the
  trunk (never a force-push). A created endpoint is never deleted by any workflow; `runpodctl serverless delete <id>`
  by hand on Greg's word only. The fetch-response route commits to `root/cycle-NN-response` only after independent
  checks; a bad commit there is reverted the same way.
- Recovery time objective: one commit (minutes); no data is touched by any of the three.

## Specialist reports
Delivered in-session (code-reviewer: REQUEST CHANGES, 0 critical / 4 important; security-auditor: 0 critical, 0 high,
2 medium, 5 low, 3 info, scoped leak scan clean; test-engineer: 33 -> 41 tests, codec line coverage 85% overall,
reading_render 72%). The item lists above are the persisted findings; the full prose was not persisted (same as
chat 5's review).
