# Strategy Autoresearch 6h/18h Summary

| Window | Trades | Baseline P&L | Top rule | Verdict | Holdout kept | Holdout P&L | Holdout improvement | Warnings |
|---|---:|---:|---|---|---:|---:|---:|---|
| day1_first6 | 2 | $-15.31 | `current_chunk_bps_gt_4` | review | 0/1 | $0.00 | $7.65 | low train coverage, low holdout coverage, rule removes most trades |
| day1_remaining18 | 14 | $-38.55 | `strategy_confidence_ge_0.80` | review | 4/6 | $-9.76 | $10.31 | holdout remains negative |
| day2_first6 | 0 | $0.00 | `baseline_no_filter` | review | 0/0 | $0.00 | $0.00 | low train coverage, low holdout coverage, rule removes most trades |
| day2_remaining18 | 6 | $-22.20 | `present_score_ge_70` | review | 0/3 | $0.00 | $7.27 | low train coverage, low holdout coverage, rule removes most trades |
| day3_first6 | 10 | $-49.91 | `recent_2chunk_bps_gt_2` | review | 2/4 | $0.99 | $1.85 | low train coverage, low holdout coverage |
| day3_remaining18 | 24 | $-26.35 | `present_score_ge_68` | review | 2/10 | $2.72 | $17.16 | low train coverage, low holdout coverage, rule removes most trades |

Read: no rule earned an automatic `keep`; all useful rules remain `review` because sample size/coverage is low. Pressure continuation is now globally disabled, including practice. Default replay posture is profit-first: low-band/scout scenarios stay off and bucket/daily health gates are on by default.
