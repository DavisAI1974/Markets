# Lightsail setup — from zero (beginner guide)

Goal: run the heavy OD coeff discovery (BTC/ETH across coinbase/kraken/bybit_perp + the alts) on a cheap
cloud box instead of the box/container, then get the results back into git. Lightsail = "a computer you rent
by the month," billed hourly. We do the SIMPLEST path first (no Docker, no ECR, no S3) — just a Linux box
that pulls its own data, runs the script, and pushes the coeff index back. Graduate to the packaged
Docker+S3 path (DEPLOY_AWS.md) later only if you want scheduled/repeatable jobs.

> Money safety (read first): a Lightsail instance is billed for as long as it EXISTS — stopping it does NOT
> stop charges (unlike EC2). To stop paying, you DELETE it (Part 6). The plans we use are ~$0.02-0.05/hour
> (~$12-24/month if left on); a discovery run is hours, so a single run costs cents-to-a-dollar. Smallest
> plans are often free for the first 3 months.

---

## Part 0 — finish account setup
1. Go to **https://lightsail.aws.amazon.com** and sign in with your AWS account.
2. If it asks to "get started" / enable Lightsail, accept — that finishes the Lightsail-side setup.
3. If billing isn't set: AWS console -> top-right account menu -> **Billing** -> add a payment method.
4. Pick a **region** (top-right of the Lightsail console). Use **N. Virginia (us-east-1)** — it matches the
   live-trading co-region plan and keeps everything in one place. (Region does NOT affect discovery speed;
   it only matters later for S3/live latency.)

Tell me when you're signed in and on us-east-1, and I'll walk you through the rest live.

---

## Part 1 — create the instance (the cloud computer)
1. Lightsail console -> **Create instance**.
2. **Instance location**: confirm us-east-1 (any AZ, e.g. us-east-1a).
3. **Blueprint**: choose **OS Only -> Ubuntu 22.04 LTS** (not an app blueprint — we just want a plain Linux box).
4. **Size/plan**: pick **4 GB RAM / 2 vCPU / 80 GB SSD** (~$24/mo, ~$0.033/hr). The discovery itself is light,
   but the 21-day backfill of 15 cells uses some RAM+disk; 4 GB is comfortable. (2 GB works if you do fewer
   cells at a time.)
5. **Name** it e.g. `od-discovery`.
6. **Create instance**. It boots in ~1 minute.

---

## Part 2 — connect (browser SSH, no keys to manage)
- On the instance card click the **terminal / "Connect using SSH"** button. A black terminal opens in your
  browser. That's the box. Everything below is typed there.

Sanity check:
```bash
python3 --version && nproc && free -h && df -h /
```

---

## Part 3 — simplest run (no Docker / no S3)
The box will: install deps -> get the code -> pull its own market data -> run discovery -> push results to git.

### 3.1 install dependencies
```bash
sudo apt update && sudo apt install -y python3-pip git
pip3 install numpy scipy
```

### 3.2 get the code (private repo — needs a GitHub token)
Create a GitHub **Personal Access Token** (github.com -> Settings -> Developer settings -> Personal access
tokens -> Fine-grained -> repo `DavisAI1974/Markets`, Contents: Read and write). Then on the box:
```bash
git clone https://<YOUR_TOKEN>@github.com/DavisAI1974/Markets.git
cd Markets
git checkout claude/crypto-backfill-validation-31tubb
git config user.email noreply@anthropic.com && git config user.name Claude   # keep commits verified
```

### 3.3 pull the market data (no auth — public exchange dumps)
The backfill scripts download public trade data and build 1-second bins into `realbins/`. Each is per-symbol;
the bins-path MUST be `realbins/{coin}_{venue}_bins.json` (that's what discovery looks for).
```bash
mkdir -p realbins

# bybit_perp — all 5 coins, 21 days (the clean multi-regime set; public daily dumps, fast):
for pair in btc:BTCUSDT eth:ETHUSDT sol:SOLUSDT doge:DOGEUSDT xrp:XRPUSDT; do
  coin=${pair%%:*}; sym=${pair##*:}
  python3 backfill_bybit.py --symbol $sym --days 21 --bins-path realbins/${coin}_bybit_perp_bins.json
done

# coinbase spot — BTC/ETH (REST walk-back; can be gappy/slower, has a ~5h budget + resume cursor):
for pair in btc:BTC-USD eth:ETH-USD; do
  coin=${pair%%:*}; prod=${pair##*:}
  python3 backfill_coinbase_spot.py --product $prod --days 21 --bins-path realbins/${coin}_coinbase_bins.json
done

# kraken spot — BTC/ETH (NOTE: Kraken BTC pair = XBTUSD, not BTCUSD):
for pair in btc:XBTUSD eth:ETHUSD; do
  coin=${pair%%:*}; p=${pair##*:}
  python3 backfill_kraken_spot.py --pair $p --days 21 --bins-path realbins/${coin}_kraken_bins.json
done

ls -lh realbins/    # confirm the bins files exist and look sized (tens of MB each)
```
(Per S39: bybit_perp gives clean contiguous 21-day history; coinbase/kraken are REST-rate-limited so they may
be gappier / take longer — that's expected, re-running resumes via the cursor.)

### 3.4 label winners + discover coeffs
```bash
# label winners per (asset, venue) — example for BTC/ETH across the 3 venues:
for v in coinbase kraken bybit_perp; do
  for a in BTC ETH; do
    coin=$(echo $a | tr A-Z a-z)
    python3 _build_alt_winner_labels.py --bins-path realbins/${coin}_${v}_bins.json \
      --asset $a --venue $v --sides buy,sell
  done
done
# (alts already have label files committed; re-label them the same way if you re-pulled their bins.)

# discover all coeffs (cap 100/cell) + persist the FNO training pairs:
python3 _run_alt_coeffs.py --cap 100 --save-embeds
```
Output: `_alt_labels/coeffs/alt_coeff_index.json.gz` (the committed fingerprint) and
`alt_train_pairs.json.gz` (gitignored, the FNO training X+y).

### 3.5 push the results back to git
```bash
git add _alt_labels/coeffs/alt_coeff_index.json.gz
git commit -m "coeffs: BTC/ETH + alts 1-sec deterministic basis (Lightsail run)"
git push origin claude/crypto-backfill-validation-31tubb
```
The `alt_train_pairs.json.gz` is gitignored on purpose (too big). For the FNO step, either keep it on the box
for training there, or upload it to S3/Lightsail object storage later.

---

## Part 4 — keep it running after you close the browser
Backfill + discovery can take a while. So the SSH window closing doesn't kill the job, run it under `tmux`:
```bash
sudo apt install -y tmux
tmux new -s od            # start a session
# ...run the Part 3 commands...
# detach: press Ctrl-b then d.  Reattach later: tmux attach -t od
```

---

## Part 5 — (later) the packaged, repeatable path
Once the one-off run works, `DEPLOY_AWS.md` covers the Docker image + S3 storage + AWS Batch for
scheduled/repeatable discovery, and the SageMaker/EC2-g5 GPU path for training the production FNO decoder
(Lightsail has NO GPU, so training does not run here).

---

## Part 6 — STOP PAYING when done
- To pause cheaply but keep the box: **Stop** the instance — BUT you are still billed while it exists.
- To stop all charges: instance card -> **Delete**. (Push anything you need to git first — the disk is wiped.)
- Check spend anytime: AWS console -> Billing -> Cost Explorer.

---

## Troubleshooting
- `git clone` 403 -> token missing the repo or Contents:write scope.
- backfill network errors -> retry; public dumps occasionally rate-limit. Re-running resumes.
- out of memory during backfill -> do fewer coins/venues per run, or use the 8 GB plan.
- "command not found: python" -> use `python3` (Ubuntu).
