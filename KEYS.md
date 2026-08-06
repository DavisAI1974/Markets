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
