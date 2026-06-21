# Hindsight missed-winner audit — oracle exit fix (2026-06-21, S31 DATAFIX)

## TL;DR
`live_hindsight_missed_winner_audit_rows.corrected.csv` is the **canonical** audit
file. It fixes the snapshot-clamp bug in the oracle columns. The original
`..._rows.csv` is preserved as the documented bug artifact; the S31 intermediate
`..._rows.relabel_corrected.csv` is **superseded** (renamed `.SUPERSEDED.csv`).

## The bug (root cause, S30)
The original audit computed each row's oracle EXIT by reading `E:\Markets\live_data`
— the ~6h LRU snapshot. The audit ran 2026-05-28 while every trade entered
2026-05-23/24, so every oracle exit clamped to the 05-28 snapshot edge:
`oracle_exit_price`/`oracle_exit_ts_utc` were a single constant per venue and
`oracle_net_bps` was computed against that stale exit. The oracle ENTRY price was
already real and per-row (`bar@ts_utc`); only the EXIT was broken.
Memory: `markets-oracle-audit-snapshot-clamp`.

Verification (this run): original (clamped) hold = `oracle_exit_ts_utc - ts_utc`
had p50 **4.2 days** (min 3.4, max 5.0) — exactly the S30 finding. Corrected hold
is **<= the per-row horizon** (max 21,600 s = 360 min; p50 ~1.8 h).

## The fix (approach — Greg-approved 2026-06-21: per-row ts_utc, uniform)
Each audit row is an independent decision point keyed `ASSET|venue|chunk|side` at its
own `ts_utc`. A chunk pattern recurs at many distinct times (one key spanned 14
decision times over 1.3 days), so a single per-chunk label is the wrong granularity
for this CSV — it mis-anchored 41.7% of "matched" rows in the abandoned relabel-join
path. Instead, **every row is anchored on its own `ts_utc`** and recomputed from the
append-only history archive (`markets_bar_loader.load_closes`, `use_live_snapshot=False`):

- `oracle_entry_price`   = nearest archive close to `ts_utc` (== generator's `bar@ts_utc`)
- horizon                = `oracle_horizon_minutes` (real per-row config; kept verbatim; buy 360 / sell 60)
- best favorable exit    = within `(ts_utc, ts_utc + horizon*60]`; buy: max close, sell: min close
- `oracle_exit_ts_utc`   = timestamp of that argmax/argmin bar  (fills the previously-blank column)
- `oracle_net_bps`       = sign*(exit/entry - 1)*1e4 - 10 bps   (buy +1 / sell -1; 5 bps/side)
- `is_oracle_winner_after_fees` = net_bps > 0
- `oracle_net_pnl_usd`   = net_bps * $1000 / 1e4
- `oracle_incremental_vs_actual_usd` = oracle_net_pnl_usd - actual_realized_pnl_usd

Guardrail (do not reintroduce the bug): exits come ONLY from the history archive,
bounded per trade by `[entry, entry+horizon]`, with the live snapshot disabled and an
explicit global `t_max`, so the current (06-21) snapshot can never leak a far-future exit.

The dipole relabel pool (`_relabel_true_horizon_results.json`, 1 trade/chunk) is a
SEPARATE artifact for the coefficient analysis and was left untouched — the S30 dipole
verdict (real-but-weak gate piece) is unaffected.

## Results
- Rows total: 21,184.  Corrected: **21,182**.  `no_entry_bar`: **2**.
- New oracle-winner split: 17,230 win / 3,952 lose (81.3% win) — vs 11,521 winners
  before. Consistent with the relabel pool's 05-23/24 chunkhash subset (~75.6% best-exit
  win); the relabel headline 22.4% was dragged down by the 14k lose-pool slices from
  05-04/11, which are not in this audit.
- New column `oracle_relabel_status` ∈ {`corrected`, `corrected_horizon_truncated`,
  `no_forward_bars`, `no_entry_bar`}. (This run: 21,182 `corrected`, 2 `no_entry_bar`.)

### Corrected headline aggregates (recomputed from the corrected CSV, excl. 2 `no_entry_bar`)
| metric | corrected | original (clamped) |
|---|---:|---:|
| oracle winner rows after fees | 17,230 | 11,521 |
| oracle winner net PnL (winners) | $178,436.62 | $308,212.47 |
| total oracle net PnL (all rows) | $176,091.73 | — |
| oracle incremental vs actual (all rows) | $118,121.19 | $250,215.17 |

The corrected oracle ceiling is LOWER per winner but spread over MORE winners — expected:
the clamped exit sat ~4 days out and captured multi-day moves, while the corrected oracle
is bounded to each trade's real 1–6 h horizon (smaller per-trade gain, more trades that
move favorably at some point inside the window).

### Classification columns — `miss_type` RECONCILED
`miss_type` was originally assigned from the clamped oracle, so after the oracle fix it
was briefly inconsistent (8,521 corrected winners still read `not_a_hindsight_winner`).
The original labeling rule was recovered from the source CSV — it reproduces the original
`miss_type` exactly (21,184/21,184, 0 mismatch):

```
winner + decision==opened  -> exit_missed_or_fee_leak
winner + decision==skipped -> missed_entry
non-winner                 -> not_a_hindsight_winner
```

It is re-applied to the corrected winner flag in the same generator. **11,331 rows
updated.** `miss_type` is now fully consistent with `is_oracle_winner_after_fees`:

| miss_type | corrected | original (clamped) |
|---|---:|---:|
| missed_entry | 15,987 | 11,398 |
| exit_missed_or_fee_leak | 1,245 | 123 |
| not_a_hindsight_winner | 3,952 | 9,663 |

`decision` (`skipped`/`opened`) and `blocker_reason` are historical facts about what the
live system did (oracle-independent) and are unchanged.

### Aggregate summaries regenerated
`live_hindsight_missed_winner_audit.corrected.json` / `.corrected.md` regenerate the
aggregate summary from the corrected CSV via `_regenerate_audit_summary.py`. Oracle-dependent
fields are recomputed; oracle-independent fields (closed-actual PnL/pace, inputs,
pattern_family `promotion_state`) are carried over from the original 05-28 summary. The
generator's `--validate` mode proves the recompute reproduces the original `.json`'s
oracle-dependent fields exactly (run on the original CSV). The original `.json`/`.md` are
left in place as the documented clamped-run artifact. Corrected headline: oracle winners
11,521 -> 17,232; oracle winner net PnL $308,212 -> $178,455; incremental vs actual
$250,215 -> $120,458. (`captured_net_win_rows` 0 -> 888 is a subset of opened oracle
winners, not a separate partition — see the corrected summary's note.)

### The 2 `no_entry_bar` rows (honest exception, not a bug)
`ETH|coinbase|f5da0fcba42142ca|buy` at 2026-05-24 05:04:37 / 05:04:40 fall inside a
genuine ~7-minute ETH/Coinbase archive gap (05:02:05 -> 05:09:39); nearest bar is
152.8 s away, beyond the 120 s tolerance. Anchoring them would require fabricating an
entry price ("real data only, never synthesize"), so they keep their original values
and are flagged `no_entry_bar`. 2 / 21,184 = 0.009%.

## Files
- Generator: `E:\Markets\_regenerate_audit_oracle.py` (re-runnable; reads the original CSV).
- Run summary + verification: `E:\Markets\_regenerate_audit_oracle_results.json`.
- Canonical output: `live_hindsight_missed_winner_audit_rows.corrected.csv` (this dir).
- Summary generator: `E:\Markets\_regenerate_audit_summary.py` (`--validate` reproduces the original).
- Corrected summaries: `live_hindsight_missed_winner_audit.corrected.json` / `.corrected.md` (this dir).
- Original (bug artifact, preserved): `live_hindsight_missed_winner_audit_rows.csv`, `..._audit.json`, `..._audit.md`.
- Superseded S31 partial: `live_hindsight_missed_winner_audit_rows.relabel_corrected.SUPERSEDED.csv`.

## Not in scope (do not conflate)
The win/lose **provenance confound** (win pool = 05-23/24 missed-winner opportunities;
lose pool = 05-04/11 backtest slices — disjoint in time + pipeline) is a separate,
deeper issue and is NOT addressed here. Memory: `markets-win-lose-pool-provenance-confound`.
