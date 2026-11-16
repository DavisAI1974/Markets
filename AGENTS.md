# AGENTS.md - DavisAI Markets

Read `CLAUDE.md` first; it is the project's instruction file for every agent, not only Claude.

## Data rule (Greg, 2026-11-16)

**This repository is CODE ONLY. Data and results go to `DavisAI1974/markets-data`.**

- Commit every data file, table, workbook, CSV/parquet/gz/tar part, render, export, receipt
  bundle, research result, handoff evidence and task output to `markets-data` (start at its
  `MARKET_DATA_INDEX.md`), never here. Raw tick tape goes to S3.
- `artifacts/` and `tasks/` are gitignored here. Never `git add -f` them.
- If a script writes output under this repo, point it at a markets-data checkout or S3 instead.
- The repo reached about 5.9 GB because `artifacts/` and `tasks/` were pushed here after this rule
  was given, and GitHub now warns it is near its size quota.

## Four trade days only (Greg, 2026-11-16)

**ROOT rebuild: only ticks inside trade days Oct 2, 3, 17 and 18, 2023 (18:00 ET to 17:00 ET) enter any
calculation that feeds research, analysis or trade strategies.**

- Data from outside them may be used for one thing: seating the order book so it is complete on the four
  trade days. Nothing else, and nothing is commingled.
- Any other use of data from outside the four trade days is put to Greg first, before it is built.
- In code: calculations receive ticks only through `root/tape.py` `for_calculations()`, live in `root/calcs/`,
  and never read the tape themselves. Full wording is in `CLAUDE.md` under "The trading rules".

## Other standing rules

- Trunk: `claude/kalshi-s79-kickoff-ij8t9o`. Check `git log --oneline -1` first (stale-tip trap).
- Launch is HOLD: no Frankie, Granite, Pod, EC2 or result-bearing action without Greg's explicit go.
- Trading research rules (trade day, gross only, no bitcoin-era rules, leakage gate, per-cell and
  per-trade, zero synthetic data) are in `CLAUDE.md` under "The trading rules".
