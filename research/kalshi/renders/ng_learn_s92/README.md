# NG learn-set renders (S92)

Reference renders for the NG intraday-shape forecaster learn pass (Greg S92).

- `ng_learn_12days_grid.png` - the 12 usable learn days (Tue-Fri; Mondays were corrupt->re-downloaded),
  raw-tick full-session trade-price curves, ET, one panel per day, organized by weekday so the
  day-of-week shape separation is visible. Each panel has its own price scale (never normalized/averaged).
- `ng_curve_20250715_sample.png` - single-day style reference (trade-price curve, time x / price $/MMBtu y).

Regenerate from the raw S3 tape via event_move_baseline.load_cont_day(root, day, source="s3") + a
1-min/raw resample; see the session log. Same-ticks-as-the-leg-detector (month_characterize.scan_moves)
so shapes match the analysis.
