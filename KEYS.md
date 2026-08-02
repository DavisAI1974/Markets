# KEYS.md — the key inventory (S110). NAMES AND HOLDERS ONLY — never a value, never a fragment.

Rule (standing, learned the hard way in S99): keys live OUTSIDE the repo (`scratchpad/*.env`,
`~/.aws/credentials`, chmod 600), are pasted per-session by Greg, and are NEVER echoed into chat,
a commit, or a log line. Rotation of the compromised pairs happens AFTER the walk (D1).

| key | used by | lives in | state | breaks without it |
|---|---|---|---|---|
| AWS access pair (acct ...4170) | platform_sync, S3 restore/stage, EC2/SSM | scratchpad/aws.env + ~/.aws/credentials | photographed into chat S99 -> ROTATE POST-WALK | S3 restore, staging new groups, box control |
| Databento key | historical pulls + LIVE feed (Standard $179/mo, subscribed S99) | scratchpad/aws.env (DATABENTO_API_KEY) | photographed S99 -> ROTATE POST-WALK | new tape pulls, live collector |
| EIA API key | grid_stack + EIA v2 feeds (incl. step-⑤ winter backfill) | scratchpad/aws.env (EIA_API_KEY) | fine | EIA-930 pulls, feed reruns |
| Kalshi PUBLIC api | kalshi_collector (read-only snapshots) | none needed | fine | nothing (public) |
| **Kalshi DEMO trading pair (key id + RSA private key)** | the paper-trading dock (G0/G1/G2) | **DOES NOT EXIST YET — Greg provisioning (S110)**; destination scratchpad/kalshi.env + PEM file beside it | pending | paper order placement |
| Kalshi PROD trading pair | live money (post-paper) | DOES NOT EXIST | future | live trading |
| GitHub (collector pushes) | GH Actions on the old trunk | repo secrets (account-level) | fine | collector accrual |
| Pyth | pyth collectors | n/a | DEAD — free era ended 2026-07-31; collectors RETIRED (D14) | nothing (gas-only) |

Container trap (standing): cloud containers inject PLACEHOLDER AWS env vars that override
~/.aws/credentials in boto3's precedence — run AWS via `env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY`
or `bash -lc`; `session_bootstrap.py` handles this.
