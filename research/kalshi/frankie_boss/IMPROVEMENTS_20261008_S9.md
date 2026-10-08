# Improvements seen along the way (started 2026-10-08, session 9; Greg: "save improvements we are seeing along the way to
# adjust after. Some we might have to stop and fix though.")

One line per item: when seen, what it costs, DONE / NOW (stop-and-fix before the chain reaches it) / LATER (next run),
and the time it saves. The rule of thumb from today: a blocker hit live costs ~25-45 min of chain time (diagnose, fix,
stage 6 min, restart, work in flight lost); a fix staged while the box is busy on something else costs 0.

## Done today (in the staged checkout db96f24 or earlier)
| # | Seen | Improvement | Saves |
|---|------|-------------|-------|
| 1 | 15:0xZ | File claims survive a reboot (st_dev out of the identity, fs UUID in; V1 rows taken on a tail match, rewritten V2) - 5bf723f4 | ~1.2 TB whole reads per resume (hours at the baseline rate) |
| 2 | 16:3xZ | The ROOT resume reopens the five legacy spools from sealed counts + claims (no line count of the 497 GB frames spool) - 2aed2f0e | ~63 min per resume at 125 MiB/s |
| 3 | 16:48Z | `grow` printout crashed after the ledger write (KeyError 'grown') - 1b4c909 | one false "GROW NOT DONE" stop |
| 4 | 16:53Z | A retained booking GROWN before its resume is taken over by its owner (subset + grown records) - 0e2a568 | the resume waited forever |
| 5 | 17:02Z | data_workers (31 -> 63) is a run-size rebind, not an identity refusal; the Session sizes from this run - 1c59623 | the resume died; a from-scratch attempt was minted |
| 6 | 17:1xZ | Queue repoint tool: re-point a day to an existing attempt on a retained booking of a given size (no hand edits) - 1c59623 | ~20 min of state surgery per incident |
| 7 | 17:2xZ | Boundary validator takes the file claims (stat + 64 KiB tail), incl. rows for the digest and the INPUT container - 48d31e5, db96f24 | the 1.2 TB second pass at the boundary (~20 min raised, ~2.5 h baseline) |
| 8 | 17:2xZ | An owned day is never retried from scratch; an identity refusal on resume is a visible 'refused' with resume-refused.json - 2ce40e8 | a from-scratch ROOT on 32 CPUs (hours) and the operator's kill |

## NOW (stop-and-fix candidates while the render runs; staged before SAVED they cost 0)
| # | Seen | Improvement | Call |
|---|------|-------------|------|
| 9a | 17:4xZ | **Everything is retained, nothing re-run (Greg)**: the digest render checkpoints only at the END of a pass; a stop inside a pass loses that pass's in-flight work (today ~24 min of the first decode). Fix: per-part durable progress inside a pass (each helper writes its part incrementally with a part checkpoint; the resume continues from the last complete chunk), so a stop anywhere loses at most one helper's current chunk | top of the NOW list: before the next render starts |
| 9 | 17:3xZ | Look-ahead audit of teacher / classroom / data-search / scientific teacher / meeting / Jev / end for the same shapes (exact-set, run-size identity, second passes, retry/kill gates, worker literals) - record LOOKAHEAD_SWEEP_20261008_S9.md | fixes landed before ~19:10Z go into one restage with db96f24; later ones cost a cycle each |
| 10 | 17:2xZ | Boundary validate OFF by default (the ROOT's own receipt + claims are the validation; claim/full stay as explicit settings) | the claim mode already costs only minutes; OFF is a usage/clarity gain; stage if ready |

## LATER (next run / next day; do not stop this run for them)
| # | Seen | Improvement | Saves |
|---|------|-------------|-------|
| 11 | 17:34Z | NEVER downsize a volume mid-day: the 12:08Z downsize of the root volume was still OPTIMIZING at 47% after 5.5 h and AWS refuses a raise while it optimizes; the whole day runs at 125 MiB/s. Raise (or keep) volumes BEFORE a render; downsize only when the box is done | ~10x disk rate for the digest (63 -> ~7 min per decode) and every read stage |
| 12 | 17:0xZ | Digest render alongside the teacher inside the day's own booking (the standalone render refuses CPUs inside a booking; the teacher's wall is host answers, not disk) | ~1-2 h of chain time per day |
| 13 | 17:3xZ | Two days per box on separate bookings AND separate volumes (root + archive) so two renders do not halve each other | per-day render time on the fleet |
| 14 | 16:4xZ | One-decode digest (today's floor is 2: the dictionary grammar is two-pass) - renderer design change | ~half the digest time |
| 15 | 16:3xZ | "64 workers": the ledger counts the coordinator (63 + 1 on 64); Greg's literal 64 is one rule change (ingest_workers / day_cpus() - 1) | marginal CPU; Greg's call |
| 16 | 15:0xZ | The CPU watchdog's resize kicks at the OWNER's commit (the old checkout); it should kick at the newest staged checkout | one wrong-code resume per resize |
| 17 | all day | One read-only `status` probe that prints the whole picture (entry, owner, booking, child cmdline/affinity, receipt, digest progress, disk rate, watchdog) instead of ad-hoc scripts | ~2-5 min per probe, dozens per day |
| 18 | all day | Every restage is ~6 min; batch fixes into one stage per boundary | ~6 min per avoided stage |
| 19 | 17:0xZ | Only data identity (sealed source, pins, counts) in every binding; every run parameter recorded, never compared (the generalisation of #5 across all stages) | one blocker per stage otherwise |
