# S60 EXIT NOTES — Piece 2 round-by-round record (2026-07-03/04)

The durable log of the EXIT piece (Piece 2). Same discipline as S58_ENTRY_NOTES.md: one round =
one defined test; update this file EVERY round; read the mistakes ledger before building; the
agent fleet runs per AGENT_PLAYBOOK_PIECES.md (exit translation).

GREG'S S60 CALLS AT OPEN: (1) he did NOT click Run workflow on the Kraken book collectors —
first cron tick is 00:00Z Jul 4 (workflow landed on default 22:01Z Jul 3; 0 runs at check);
(2) FULL FLEET on exit round 1; (3) nothing changes priorities — sequencing = Code's call
(kickoff order kept: Kraken backfill launched first, exit fleet runs while it pulls).

SCORING FRAME (inherited): always-in-market mid-band flip machine (`odcore/entry_coinbase.py`
armed_midband_flips, registry shapes, NAIVE k0, entry held FIXED), mid fills at confirms, $5k
flat, fee columns cb_entry 40 / cb_early 10 / cb_real 8 / cb_scale 3 / kr_mk0 0 (maker-both-
sides; kr taker 10 where taker legs appear). Tapes: 30d x 4-coin Binance spot bins (instrument)
+ Coinbase books (deploy venue; thin — shape only). ETH stays dropped. Controls: reversed,
shuffle, per-week, truncation-invariance leakage.

BASELINE EXIT = flip-at-next-confirm (the promoted machine's own exit; leg = confirm k ->
confirm k+1). CANDIDATE 1 = R8 lean-collapse (`swing_maker` lean_exit=(arm_hi, exit_lo),
with-ride lean armed at arm_hi, closed at collapse to exit_lo; measured basis S55 R8: 765
zz150 exits, ~28bp giveback vs 151bp theta-exit — SCALE-LOCALITY: zz150 numbers do NOT
pre-authorize theta 80/100; that is this round's question).

PER-LEG BUDGET INHERITED (S59): surviving entry configs gross +5.6..+9.3 bp/leg vs 16bp RT
cb_real (deficit -1.4..-4 $/hr); paper-positive at kr_mk0. The exit's job: cut giveback
without killing the winners' tails.

## MISTAKES CAUGHT (append-only; S58 ledger items 1-4 carry — tuple order, mode-0 deadlock,
## thin books, pkill)

(none yet this session)

## SESSION LOG (append per round)
- 22:3x Z: branch reconciled (S60 designated branch was cut from default/crons AGAIN — third
  session running; reset --hard to canonical 396d534, pushed).
- 22:4x Z: Kraken 30d backfill x5 launched sequential (/tmp/kraken_backfill, SOLUSD first).
  Binance 30d bins x5 launched parallel (/tmp/binance_bins). Coinbase books x5 restored from
  data branches (btc 47MB / doge 23MB / eth 53MB / sol 51MB / xrp 36MB).
- 22:5x Z: scrap-heap miners A (S38-S52 handoffs + strategy docs) + B (S53-S59 + code sweep)
  launched in parallel, exit charter per playbook.
- Kraken book collectors: 0 runs (expected — cron ticks 00/06/12/18Z; landed 22:01Z).
