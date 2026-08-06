# forecasts/ — the committed per-group forecast record (S95)

Every group's forecast is saved HERE (committed to git), never in ephemeral scratchpad — the reason G3/4/5
were lost. Each record carries BOTH the guess curve and the reasoning, both saved (Greg S95).

One file per group: `grpN.json`
```
{
 "group": 6, "tag": "g6", "brain_version": "s92.6",
 "anchor": {"date": "20251021", "price": 2.92, "last_hour_dir": "up"},
 "days": [
   {
    "date": "20251022", "dow": "Wed", "group": 6,
    "archetype": "...",                         # day classification
    "reasoning": "...",                          # WHY this call (day-into-day: how it flows from the prior
                                                 #   day's close, which plays fired, the block-open lean).
                                                 #   This is the per-day reasoning; it lives here, and is
                                                 #   PROMOTED into the brain (reasoning_method / plays) only
                                                 #   when it generalizes - never a memorized day in the brain.
    "guess_curve": [[20,0],[22,..],...],         # continuous cum-$ from this day's flowed-open (2-hourly ET)
    "overnight_gap_usd": 0,                       # guessed open gap from prior day's GUESSED close
    "guessed_net_usd": 0
   }
 ]
}
```

The REFINE step writes its refined reasoning back here (per day) alongside the original, so the record is the
audit trail of how a forecast was made AND how the reasoning was corrected. General lessons then merge into
`knowledge/ng_brain.json` (the brain). Guess curve and reasoning are kept as distinct fields but the same
record. PER-EVENT, never averaged.
