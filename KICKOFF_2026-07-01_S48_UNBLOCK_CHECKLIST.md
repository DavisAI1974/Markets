# S48 UNBLOCK CHECKLIST — Greg's one-click actions to get the 2nd window + auto-accrual flowing

Status as of S48 open (2026-06-30). The 2nd-window gate (the thing that lets us size for real) is the only
hard blocker, and every fix needs a click or an auth I (the integration token) cannot do.

## 1. Data flow — collection IS alive, just lagged (no panic, but two clicks help)
Diagnosis (from the GitHub Actions API, read-only): `book_collectors_durable.yml` cron **is firing** on the
default branch (`claude/new-session-o3vnm`):
- a scheduled run is **in_progress** (started 06-29 19:54Z) and another is **pending** (03:27Z);
- each run collects for **5h50m** and force-pushes the cumulative book **only at the end**, so the alt book
  branches still show the last completed push (**06-29 23:29Z** = S46/S47's window). A fresh window arrives
  when the in-progress run completes and pushes — it is coming, just delayed by run length + GHA queue.
- one `workflow_dispatch` run **failed** at 06-29 12:12Z (worth a glance at its log if the next push is late).

ACTIONS (optional, to force a fresh window sooner):
- [ ] Actions tab → **"Book Collectors (durable)"** → **Run workflow** (the in-progress run already covers a
      post-23:29 window; let it finish, or kick a fresh short run with a smaller `duration_seconds` to push a
      new window quickly). My token gets **403** on dispatch — this must be your click.
- [ ] Same for **"BTC Collectors (durable)"** if you want btc off the stale 06-22→06-24 window.

## 2. Activate the paper-trade cron (so the forward ledger auto-accrues = the real multi-window test)
`scripts/paper_trade.py` + `.github/workflows/paper_trade.yml` exist on the dev branch, but GitHub only fires
`schedule:` triggers from the **default** branch. Until the workflow is on default, the ledger only grows when
someone runs the script.
- [ ] Place `.github/workflows/paper_trade.yml` on **`claude/new-session-o3vnm`** (the default). Then it
      self-fires 30 min after each book cron, runs `paper_trade.py`, and commits `paper_ledger.jsonl` — the
      forward, deduped, out-of-sample record accrues on its own.

## 3. Durable off-git storage (the real fix — removes the 6h-run-length + 100 MiB-cap friction entirely)
Off-git storage gives clean independent windows on demand and is the durable answer. Still **blocked on cloud
auth** this session: Render MCP returns 400 (`list_workspaces`), no AWS connector present.
- [ ] Connect the **Render workspace** (then I can deploy a `virginia`/us-east-1 collector + KV/Postgres sink),
      **or** provide AWS creds/IaC for an S3 sink.

## What I am NOT doing until #1 lands
Per the standing rule (*never tune off one window*): no sizing-for-real and no conviction→size wiring until the
two-factor lift + net-of-fee survival **reproduce on a genuinely new book window.** This session's code work
(cutting the taker rate) is execution mechanics — a structural improvement measured on the existing window, not
a generalization claim — so it is safe to do now and will simply carry forward to the fresh window when it lands.
