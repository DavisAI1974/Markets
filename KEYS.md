# KEYS.md — the key inventory (S110). NAMES AND HOLDERS ONLY — never a value, never a fragment.

**THE CANONICAL LOCATION (S113 creds.py, confirmed live S114): `~/.config/markets/env`, chmod 600,
outside the repo.** One file, `NAME=VALUE` lines, holding AWS_ACCESS_KEY_ID +
AWS_SECRET_ACCESS_KEY + DATABENTO_API_KEY + EIA_API_KEY. Greg pastes/drops the values per-session
(the container is ephemeral - no file survives it); the session installs them there, plus
`~/.aws/credentials` as the boto3 fallback. `creds.py` resolves process env ->
`~/.config/markets/env` -> legacy `scratchpad/aws.env` (with a warning), ignores the container's
`proxy-injected` placeholder vars, and `creds.aws_client(service, region)` is the ONLY way to build
a boto3 client. This paragraph is the answer to "which env file" - it is the one a handoff should
point at.

Rule (standing, learned the hard way in S99): keys live OUTSIDE the repo, are pasted per-session
by Greg, and are NEVER echoed into chat, a commit, or a log line. Rotation of the compromised
pairs happens AFTER the walk (D1).

| key | used by | lives in | state | breaks without it |
|---|---|---|---|---|
| AWS access pair (acct ...4170) | platform_sync, S3 restore/stage, EC2/SSM | `~/.config/markets/env` + `~/.aws/credentials` (both 600) | photographed into chat S99 -> ROTATE POST-WALK | S3 restore, staging new groups, box control |
| Databento key | historical pulls + LIVE feed (Standard $179/mo, subscribed S99) | `~/.config/markets/env` (DATABENTO_API_KEY) | photographed S99 -> ROTATE POST-WALK | new tape pulls, live collector, the mbp-1 L1 book writer (S114) |
| EIA API key | grid_stack + EIA v2 feeds (incl. step-⑤ winter backfill) | scratchpad/aws.env (EIA_API_KEY) | fine | EIA-930 pulls, feed reruns |
| Kalshi PUBLIC api | kalshi_collector (read-only snapshots) | none needed | fine | nothing (public) |
| **Kalshi DEMO trading pair (key id + RSA private key)** | the paper-trading dock (G0/G1/G2) | **DOES NOT EXIST YET — Greg provisioning (S110)**; destination scratchpad/kalshi.env + PEM file beside it | pending | paper order placement |
| Kalshi PROD trading pair | live money (post-paper) | DOES NOT EXIST | future | live trading |
| GitHub (collector pushes) | GH Actions on the old trunk | repo secrets (account-level) | fine | collector accrual |
| Pyth | pyth collectors | n/a | DEAD — free era ended 2026-07-31; collectors RETIRED (D14) | nothing (gas-only) |

Container trap (standing): cloud containers inject PLACEHOLDER AWS env vars that override
~/.aws/credentials in boto3's precedence — run AWS via `env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY`
or `bash -lc`; `session_bootstrap.py` handles this.



## S115 — THE PASTE RITUAL ENDS: MARKETS_ environment variables (one-time setup)

**THE PROBLEM S114 HALVED AND S115 CLOSES.** SSM took the paste from four values to two, but the
AWS bootstrap pair still had to be hand-dropped every session, and every fresh session opened with
a false "no keys" alarm. Root cause: the container injects `proxy-injected` PLACEHOLDERS under the
bare `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` names, so the real values could never ride the
process environment - the one channel that DOES survive into every fresh container (the Claude
Code ENVIRONMENT configuration injects its variables at session start).

**THE FIX: a name that cannot collide.** `creds.py` now resolves `MARKETS_<NAME>` FIRST, for every
key. The placeholders live under the bare names; the prefixed names are ours alone.

**GREG'S ONE-TIME STEP (this is the whole setup):** in the Claude Code environment settings for
this environment (claude.ai -> Code -> environment -> environment variables), add:

    MARKETS_AWS_ACCESS_KEY_ID     = <the access key id>
    MARKETS_AWS_SECRET_ACCESS_KEY = <the secret>

After that, every fresh session: the SessionStart hook detects the pair by EFFECTIVE resolution
(creds.py, not file presence), restores the NG data plane automatically, and SSM supplies
DATABENTO_API_KEY + EIA_API_KEY on first ask. Zero pasting, zero manual steps.

**VERIFIED S115, both directions (NC-3):** with ONLY `MARKETS_` vars set (env file and
`~/.aws/credentials` both removed): STS PASS account tail 4170, SSM retrieval PASS (lengths 32/40),
status reports every key resolvable. With nothing set: the hook's loud no-op branch fires.
`creds.aws_client()` now passes the RESOLVED pair to boto3 explicitly, so `~/.aws/credentials` is
no longer needed at all; `restore_substrate.py`'s bare `boto3.client` (which only worked when that
file happened to exist) was fixed to `creds.aws_client()` the same session.

**SECURITY POSTURE UNCHANGED:** the values live in the environment configuration (outside the
repo), never in git, never echoed. Rotation: update the two environment variables, re-run
`creds.py --sync-ssm`. D1 (no rotation during the walk) stands until go-live.

## S114 — DURABLE RETRIEVAL: SSM Parameter Store (SecureString)

**THE PROBLEM.** `~/.config/markets/env` is the canonical home and is correct — chmod 600, outside
the repo. But it lives in an **EPHEMERAL CONTAINER and does not survive the session**, and secrets
can never go into git (this file's own standing rule; AWS kills keys it finds on GitHub, and these
were photographed into chat at S99). So every key had to be re-pasted by hand, every session, all
four.

**THE FIX, in our own AWS account, KMS-encrypted:**

| parameter | type | holds |
|---|---|---|
| `/markets/DATABENTO_API_KEY` | SecureString | the Databento key |
| `/markets/EIA_API_KEY` | SecureString | the EIA key |

`creds.get()` now falls back to SSM automatically, so a session that has the AWS pair retrieves the
other two with no action. **The per-session paste drops from four values to two.**

**THE AWS PAIR IS DELIBERATELY NOT STORED THERE, and the distinction is the whole design:** it is
the BOOTSTRAP — you need it to read SSM at all. Storing it in the thing it unlocks would be
circular. Greg pastes the AWS pair; everything else follows.

**AFTER ANY PASTE OR ROTATION:** `python research/kalshi/creds.py --sync-ssm`. It pushes and then
**verifies by reading back** (D47 — a store is not updated until a read-back proves it), and prints
lengths and match booleans only, never a value.

**ROTATION IS UNAFFECTED.** Same keys, same account. D1 still stands: they do not rotate during the
walk. When we go live and rotate, re-paste and re-run `--sync-ssm`.

## S114 VERIFICATION — all four keys confirmed live from the one env file

Checked at S114 close, by NAME only, values never printed:

| name | resolves from | proven by |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | `~/.config/markets/env` | `sts.get_caller_identity()` -> account tail 4170 |
| `AWS_SECRET_ACCESS_KEY` | `~/.config/markets/env` | same call |
| `DATABENTO_API_KEY` | `~/.config/markets/env` | mbp-1 L1 pull, 9 sessions, $0.00 in-sub |
| `EIA_API_KEY` | `~/.config/markets/env` | eia_surprise + storage_regional rebuilds |

**THE CONTAINER PLACEHOLDER IS STILL LIVE AND STILL SHADOWS THE REAL PAIR.** `creds.status()`
reports `AWS_ACCESS_KEY_ID  CONTAINER PLACEHOLDER (ignored)` because the harness injects
`proxy-injected...` into the process env, where boto3's own precedence would prefer it over
`~/.aws/credentials`. `creds.py` detects and ignores it. **This is why `creds.aws_client()` is the
only sanctioned way to build a client** — a bare `boto3.client()` picks up the placeholder and
fails with `InvalidClientTokenId` on a known-good key, which is the trap that cost an hour in S100.

The env file is written with a header saying it must never be committed, echoed or pasted, and is
re-chmod'ed to 600 whenever it is touched.
