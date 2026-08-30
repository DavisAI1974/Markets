# The A-clean full-roster run is blocked on ONE thing: the box has no S3 access

Written 2026-08-30, mid-session, because the blocker needs Greg and the container will not
survive to ask. Everything else on the path to a full run is now measured and working.

## The blocker, measured by the box itself

The remote command's own probe, from run 33306101129:

```
A_ARM_IDENTITY=arn:aws:sts::568968024170:assumed-role/Ssm/i-08cee7171c0a76a04
A_ARM_CAN_READ_SOURCES=no
A_ARM_CAN_READ_PACKET=no
```

The instance role `Ssm` on `i-08cee7171c0a76a04` has **no access to
`bento-568968024170-us-east-2-an` at all** - not the DBN sources it must read, not the prefix
it must write its ledgers to. `/etc/markets/coach.env` holds no credentials, and an SSM shell
is not a login shell, so the CLI falls through to the instance profile every time. That is why
every dispatch died with `403 on HeadObject` and why sourcing the env file changed nothing.

**This is not only a read problem.** The traversal uploads its exact ledgers at the END of a
run measured near fourteen hours. A role that cannot write loses the entire output at the last
line, after the compute is already spent.

## The two ways to fix it, and why the choice is Greg's

**(a) A scoped policy on the role.** One inline policy, `FrankieAArmBucketAccess`, on the role
behind the instance profile:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {"Sid": "FrankieObjects", "Effect": "Allow",
     "Action": ["s3:GetObject", "s3:PutObject", "s3:AbortMultipartUpload",
                "s3:ListMultipartUploadParts"],
     "Resource": "arn:aws:s3:::bento-568968024170-us-east-2-an/nymex/*"},
    {"Sid": "FrankieList", "Effect": "Allow",
     "Action": ["s3:ListBucket", "s3:GetBucketLocation"],
     "Resource": "arn:aws:s3:::bento-568968024170-us-east-2-an"}
  ]
}
```

Attached from the runner with `aws iam put-role-policy`, which the GitHub-secret `Claude` user
may or may not be permitted to call - untested, because this is where the session's own
guardrail stopped it. **It is a privilege change to an account-level role, so it is Greg's
call, not a session's.** It solves reads and writes together and needs nothing else.

**(b) No new permission at all.** Written and left in the working tree, unpushed:

- the manifest travels **inline**, base64 in the SSM command, so the box gets the runner's
  byte-identical file rather than regenerating a second opinion about the roster;
- the four DBN objects travel as **presigned GET URLs**, fetched with `curl -sSfL`, each
  verified against the same sha256 the runner checks. A presigned URL carries a signature and
  never the secret key, is read-only, names one object, and expires in six hours;
- the final upload is **attempted and its failure is not fatal**, marked
  `A_ARM_RESULTS_UPLOADED=yes` or `A_ARM_RESULTS_ON_BOX=/opt/frankie-a-arm-run`. Fourteen hours
  of finished traversal must never be thrown away because the results could not be moved; they
  sit on the 300 GB volume until the role is granted or presigned PUTs are issued per file.
  **A run reporting `A_ARM_RESULTS_ON_BOX` is NOT durable and is not finished** - D34 says data
  lives on S3.

**What was NOT done and must not be:** exporting the runner's long-lived keys into the SSM
command. It would work. SSM command parameters are readable by anyone with SSM read, and this
workflow's own failure branch prints the invocation, so the keys would land in a GitHub log.

## Everything else on the path is done and measured

| | state |
|---|---|
| Canary, eight section 6 gates | **ACCEPTED** on the real roster, 50,001 records / 40,242 groups, run 33304995387 |
| Every section 4.6 to 4.16 | **fed**; 4.15 excluded under D5 |
| Box volume | grown 200 -> 300 GB; **224.8 GiB free**, measured need 127.2 GiB |
| Partition / filesystem | grown on the box; `growpart` NOCHANGE, `resize2fs` nothing to do |
| Exact-commit checkout on the box | works: `HEAD is now at 8502104d` |
| SSM execution timeout | 172800s. `--timeout-seconds` is DELIVERY only; `executionTimeout` defaults to 3600 and would have killed a 14-hour run at hour one |
| Throughput | 8.8 ms/record with 4.6 fed (440s for 50,001), so **~13.9 hours** for 5,667,689 |
| Ledger size | 24 KB/record, so **~136 GB** of exact ledgers - a DISK figure, not the armed 128 GiB memory one |

## Five defects found today, none of which surfaced as a failure

1. The box was told to read sources and a manifest out of a directory it had just created
   empty. The dispatch had never fired, so it had never been wrong out loud.
2. `--timeout-seconds 43200` is the delivery timeout. The one that stops the script is
   `executionTimeout`, default 3600 - a green dispatch and a run killed at hour one.
3. The dispatch discarded the SSM invocation on failure, so the only evidence was the word
   "Failed".
4. The volume was too small by a margin nobody had measured: 128.1 GiB free against 127.2 GiB
   needed, a 0.7% margin.
5. **Acceptance is not survival.** A dispatch reported `InProgress` two seconds in and the job
   went green; the box monitor forty seconds later showed no `python3` process and memory
   untouched. The command had been accepted and had then died in staging, leaving a green job
   and no evidence anywhere. The dispatch now watches three minutes and prints the box's own
   stdout and stderr either way.

Every one of them was invisible until something actually ran, which is the same lesson as the
session's opening finding arriving from the other direction.

## What the next session must do first

Path (b) is **committed and fully verified to the D57 standard**: the YAML parses, `bash -n`
passes on every run block, `ast.parse` passes on every embedded heredoc, and the **rendered
remote command was written out and run through `bash -n`** rather than read. It needs no new
permission and has been dispatched.

What is still Greg's, and what path (b) cannot settle: **the upload**. If the box still cannot
write, the run ends with `A_ARM_RESULTS_ON_BOX=/opt/frankie-a-arm-run` and about 136 GB of
exact ledgers sit on the volume rather than on S3. That is a finished traversal and an
UNFINISHED run - D34 says data lives on S3. Path (a) fixes it in one policy; the alternative is
presigned PUTs issued once the output file names are known, which needs a second dispatch after
the traversal ends.
