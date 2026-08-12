# Frankie AWS Setup — S117

Frankie is packaged for the existing DavisAI Markets AWS host pattern. This document does not
start the service or create trading authority.

## Components

- `markets-frankie.service` — long-running SQS worker
- `markets-frankie-reflect.service` — one bounded reflection pass
- `markets-frankie-reflect.timer` — daily proposal-generation timer, disabled until explicitly enabled
- `install_frankie.sh` — installs dependencies, state directories, and unit templates; does not start them
- `frankie.env.example` — non-secret settings
- `frankie_iam_policy.example.json` — least-privilege policy template

## Recommended AWS shape

```text
existing collectors / EventBridge rules
        -> SQS frankie-events
             -> redrive policy -> frankie-events-dlq
        -> EC2 systemd worker (first target)
             -> Bedrock in us-east-1
             -> optional OpenAI independent critic
             -> /var/lib/markets/frankie/evidence
             -> S3 frankie/evidence/
        -> nightly bounded reflection
             -> /var/lib/markets/frankie/proposals/pending
```

Use a standard SQS queue, not FIFO, unless a later causal dependency specifically requires ordering.
Every message is independently identified and content-hashed. Configure a DLQ with a low enough
`maxReceiveCount` to surface malformed or repeatedly failing events.

## Install

```bash
cd /opt/markets
sudo bash deploy/aws/install_frankie.sh /opt/markets ubuntu
```

The installer:

- installs Boto3 and the OpenAI SDK;
- creates `/var/lib/markets/frankie/{evidence,outcomes,proposals/pending}`;
- installs all three systemd units;
- writes a deterministic-canary `/etc/markets/frankie.env` only if one does not exist;
- runs `systemctl daemon-reload`;
- does not enable or start anything.

## Initial deterministic canary

Keep:

```bash
FRANKIE_DETERMINISTIC_ONLY=1
```

Validate:

```bash
sudo -u ubuntu bash -lc '
  cd /opt/markets/research/kalshi
  python3 agent_frankie.py health
  python3 agent_frankie.py selftest
'
```

Then start only the worker:

```bash
sudo systemctl enable --now markets-frankie.service
sudo journalctl -u markets-frankie.service -f
```

At this stage Frankie performs deterministic qualification and writes WATCH_ONLY or REJECT evidence.
No model call is made.

## Paper-manifest gate

Do not turn off deterministic-only mode until the exact research-paper links from Greg and Claude's
private session are exported into:

```text
research/kalshi/frankie_paper_manifest.json
```

The file must be reviewed and changed to `status: READY`. A private chat link is not accepted as a
runtime source because another process cannot reliably retrieve, cite, or version it.

## Hybrid SHADOW activation

After the manifest is READY:

1. set an approved Bedrock model or inference profile in `FRANKIE_BEDROCK_MODEL`;
2. set an approved OpenAI model in `FRANKIE_OPENAI_MODEL`;
3. verify both credentials through the canonical `creds.py` path;
4. run one local `evaluate` smoke test;
5. set `FRANKIE_DETERMINISTIC_ONLY=0`;
6. restart the worker.

```bash
sudo systemctl restart markets-frankie.service
```

The strongest result remains SHADOW. There is no order client in the process.

## Nightly self-improvement proposals

Do not enable this timer until at least five decision records have immutable resolved outcomes and
both reasoning backends are stable.

```bash
sudo systemctl enable --now markets-frankie-reflect.timer
systemctl list-timers markets-frankie-reflect.timer
```

The job can only write proposal JSON under `proposals/pending`. It cannot modify code, create a
branch, push a commit, alter `spawn.py`, or touch risk/execution/credential files.

## IAM

Start from `frankie_iam_policy.example.json`, replacing account and model/profile placeholders.
Frankie needs only:

- SQS receive/delete/visibility/attributes on the one queue;
- S3 `PutObject` on the one evidence prefix;
- Bedrock inference on the approved model/profile;
- SSM `GetParameter` on `/markets/*` if the canonical credential fallback is used.

Do not grant:

- Kalshi order permissions;
- brokerage or tastytrade credentials;
- Secrets Manager wildcard access;
- repository write permissions;
- IAM mutation;
- shell/SSM authority to the Frankie process role.

## Operations

Useful checks:

```bash
python3 agent_frankie.py verify-origin
python3 agent_frankie.py health
systemctl status markets-frankie.service
journalctl -u markets-frankie.service --since today
journalctl -u markets-frankie-reflect.service --since '7 days ago'
```

The original spawner must always report the pinned Git blob. A mismatch is a hard stop, not a warning.

## Rollback

```bash
sudo systemctl disable --now markets-frankie-reflect.timer
sudo systemctl disable --now markets-frankie.service
```

Evidence and outcomes remain in `/var/lib/markets/frankie` and the configured S3 prefix. Disabling the
service does not alter or delete them.
