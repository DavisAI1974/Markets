# deploy/aws — run the Markets code on a durable AWS box (S90)

The code is meant to live on a DURABLE box, not the ephemeral session containers: the year pull can finish
unattended, the checkout stays current with the trunk, and the daily forecast/trade lifecycle has a real
home. git is still the source of truth for the code; the tick corpus lives on S3 (S89). This kit is the
"prep the deploy kit" path (S90) — you spin up an instance, run one script, fill one secrets file.

## What's here
| file | what it is |
|------|-----------|
| `setup.sh` | one-time idempotent box setup: system + python deps, `/etc/markets/markets.env`, install the systemd units, enable the daily trunk-update timer. |
| `env.template` | secrets/config template -> copy to `/etc/markets/markets.env`, fill, chmod 600. NEVER commit the filled copy. |
| `nymex-pull.service` | the full-raw MBP-10 YEAR pull to S3 (resumable; runs to completion then exits). |
| `markets-update.{service,timer}` + `markets-update.sh` | keep the checkout on the latest trunk daily. |
| `markets-daily.{service,timer}` + `daily_lifecycle.sh` | the daily forecast/trade lifecycle. Timer DISABLED by default (stub until the scorer exists). |

## Recommended AWS shape (least static secrets)
- A small instance (Lightsail $5-10/mo, or a t3.small EC2) in **us-east-2** (same region as the bucket).
- Attach an **IAM instance ROLE** granting S3 access to `bento-568968024170-us-east-2-an` — then boto3 auths
  off the role and the ONLY on-disk secret is the Databento key. This is safer than static keys on a
  long-lived box; rotate the pasted `Claude` IAM key after the migration (S89 standing item).
- ~30 GB disk (a year of gz ~= 25 GB on S3; the box only needs ~2-3 GB scratch at a time — the pull bounds
  local to ~1 day of raw).

## Run it
```bash
# on the box (Ubuntu/Debian), as a sudo-capable user
git clone <the Markets repo> ~/Markets && cd ~/Markets
git checkout claude/kalshi-s79-kickoff-ij8t9o && git pull
sudo bash deploy/aws/setup.sh

# secrets: fill DATABENTO_API_KEY (+ AWS_* only if NO instance role)
sudoedit /etc/markets/markets.env      # already chmod 600

# start the year pull (resumable) + watch it
sudo systemctl start nymex-pull.service
journalctl -u nymex-pull -f

# check the bucket fills (from anywhere with creds)
aws s3 ls s3://bento-568968024170-us-east-2-an/nymex/nymex_cont/ | tail
```

## The daily lifecycle (later)
`markets-daily.timer` is intentionally OFF — a timer into an empty pipeline is premature. Enable it ONLY
once the forecaster emit (per `WEATHER_FORECAST_INTERFACE_S90.md`) + the per-cell scoring script exist:
```bash
sudo systemctl enable --now markets-daily.timer
```
Then `daily_lifecycle.sh` runs the score-tomorrow / recalc-AM / re-check-intraday cycle for the KXHIGH
weather-distribution trade AND the NYMEX path forecast (same daily cadence). See the FORECAST WORKFLOW block
in `KALSHI_TRADING.md`.

## Notes
- Everything is resumable/idempotent: re-run `setup.sh` any time; the pull skips months already in the
  bucket; `markets-update.sh` only pulls when the tree is clean.
- No secret is ever committed — `env.template` holds placeholders; the real env lives only on the box.
