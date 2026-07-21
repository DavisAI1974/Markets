# Live NG collector and desk — build status

Branch: `chatgpt/rt-ng-mbp10-collector`

## Built

- One Databento live session for `NG.v.0` on `GLBX.MDP3`.
- Mixed raw DBN archive: MBO, MBP-10, trades, TBBO, definition, statistics, status.
- Atomic local health snapshot at `/var/lib/markets/ng_live/health.json`.
- S3 archive target: `s3://bento-568968024170-us-east-2-an/nymex/live/ng/YYYY/MM/DD/`.
- Automatic Databento reconnect policy.
- Daily session rotation and clean archive upload.
- Recovery upload for DBN files left by abrupt exits.
- systemd boot persistence and restart-on-failure.
- One-minute health watchdog that restarts only the live collector.
- HTMX desk at `127.0.0.1:8091`, wired to live feed/depth health.
- Credential-free GitHub CI for Python, shell and systemd validation.

## Deliberately untouched

- Running one-year L1 historical collection.
- Previously collected MBP history.
- Historical Databento request code and services.
- Kalshi execution.
- CME ECNG/ECH order routing.

## Activation

After placing a rotated Databento key in `/etc/markets/markets.env`:

```bash
cd /opt/markets
MARKETS_CODE_BRANCH=chatgpt/rt-ng-mbp10-collector \
  bash deploy/aws/install-ng-live.sh
```

The installer enables the collector, watchdog, local desk and daily code updater across logout and reboot.

## View the desk securely

Use AWS Systems Manager port forwarding from a trusted machine:

```bash
aws ssm start-session \
  --target i-08cee7171c0a76a04 \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["8091"],"localPortNumber":["8091"]}'
```

Then open `http://127.0.0.1:8091` locally.

## Next implementation slice

1. Compute multi-horizon dipole features from the live trades stream.
2. Add MBO cancel/add/modify and queue-survival features.
3. Collect active CME ECNG/ECH definitions and books when venue access is selected.
4. Add strike/time/VWAP fair-value and follower-lag cards.
5. Keep CME event contracts in SHADOW until net-of-fee forward-live gates pass.
