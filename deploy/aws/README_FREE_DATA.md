# Free NG public-data collectors

The free collector is independent of every Databento historical and live service.

## Install and start

```bash
cd /opt/markets
MARKETS_CODE_BRANCH=chatgpt/rt-ng-mbp10-collector bash deploy/aws/install-free-ng.sh
```

The installer enables `markets-free-ng.timer`, runs the collector immediately, verifies the snapshot, and leaves it running every 30 minutes across logout and reboot.

## Outputs

- Local: `/var/lib/markets/free_ng/latest.json`
- S3: `s3://bento-568968024170-us-east-2-an/drivers/free_ng/latest.json`

## Cost

- NOAA/NWS API: free, rate limited.
- EIA API: free; `DEMO_KEY` is suitable for validation, while a registered EIA key is recommended for durable use.
- AWS: only the existing box runtime, requests and small JSON storage.

## Inspect

```bash
systemctl status markets-free-ng.timer
journalctl -u markets-free-ng.service -n 100 --no-pager
python -m json.tool /var/lib/markets/free_ng/latest.json | head -100
```
