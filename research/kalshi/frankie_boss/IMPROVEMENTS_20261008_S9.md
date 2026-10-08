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
| 9a | 17:4xZ | **Everything is retained, nothing re-run (Greg)**: the digest render checkpoints only at the END of a pass; a stop inside a pass loses that pass's in-flight work (today ~24 min of the first decode). Fix: per-part durable progress inside a pass (each helper writes its part incrementally with a part checkpoint; the resume continues from the last complete chunk), so a stop anywhere loses at most one helper's current chunk | **DONE (source) 5faef9ef** + I/O priority 3cb0deea: per-part chunk progress in the snapshot and plan passes, stop file honoured at chunk boundaries; loss on a stop <= one chunk per helper (~2 min at 125 MiB/s); 48/48 SIGKILL resumes byte-identical (scratch); RUNTIME-UNVERIFIED on the box |
| 9b | 17:5xZ | brain_stage (frankie_box_brain.write_stage_entry, witness at :82) hashes every source WHOLE, including work/derivation-digest-full.md once it exists: a whole read of the full-depth digest at every root done/reused record. Fix: the brain entry takes the digest's file claim (the ROOT/render writes a claim row when it writes the digest; stat + tail), never re-hashes it | NOW: before the digest render lands on a2 (the next root re-kick after the render would read it whole) |
| 9 | 17:3xZ | Look-ahead audit of teacher / classroom / data-search / scientific teacher / meeting / Jev / end for the same shapes (exact-set, run-size identity, second passes, retry/kill gates, worker literals) - record LOOKAHEAD_SWEEP_20261008_S9.md | fixes landed before ~19:10Z go into one restage with db96f24; later ones cost a cycle each |
| 10 | 17:2xZ | Boundary validate OFF by default (the ROOT's own receipt + claims are the validation; claim/full stay as explicit settings) | the claim mode already costs only minutes; OFF is a usage/clarity gain; stage if ready. SOURCE DONE 7c4837c: `FRANKIE_ROOT_VALIDATE_CHECK=off` skips it at the boundary (validate {check off, basis, receipt_sha256} on handoff.json + log); claim stays the default (parent's call at the kick) |

## LATER (next run / next day; do not stop this run for them)
| # | Seen | Improvement | Saves |
|---|------|-------------|-------|
| 11 | 17:34Z | NEVER downsize a volume mid-day: the 12:08Z downsize of the root volume was still OPTIMIZING at 47% after 5.5 h and AWS refuses a raise while it optimizes; the whole day runs at 125 MiB/s. Raise (or keep) volumes BEFORE a render; downsize only when the box is done | ~10x disk rate for the digest (63 -> ~7 min per decode) and every read stage |
| 12 | 17:0xZ | Digest render alongside the teacher inside the day's own booking (the standalone render refuses CPUs inside a booking; the teacher's wall is host answers, not disk) | ~1-2 h of chain time per day. SOURCE DONE 418005d: `FRANKIE_RENDER_BOOKING=<id>`; the ROOT receipt kept (teacher binds its sha256), record work/digest-render.json; layers by claim + spools from sealed counts (no 497 GB count); pass save points ADOPTED across `.digest-<uuid>` scratches (before, a stopped render never found its own passes.pkl) |
| 13 | 17:3xZ | Two days per box on separate bookings AND separate volumes (root + archive) so two renders do not halve each other | per-day render time on the fleet |
| 14 | 16:4xZ | One-decode digest (today's floor is 2: the dictionary grammar is two-pass) - renderer design change. **NOT BUILT (session 9 source role)**: the cells depend on table-wide facts (column order, keys-once shapes, lengths) no part knows before the whole table is read; exact only by a row copy (refused) or a speculate-and-verify renderer change; reasons and the route in E2E_ONE_DAY_20231018.md "Session 9: render I/O priority, per-part progress, one source read" | ~one decode: 63 min at 125 MiB/s, ~14 min CPU-bound at 1,250 MiB/s on 63 helpers |
| 15 | 16:3xZ | "64 workers": the ledger counts the coordinator (63 + 1 on 64); Greg's literal 64 is one rule change (ingest_workers / day_cpus() - 1) | marginal CPU; Greg's call |
| 16 | 15:0xZ | The CPU watchdog's resize kicks at the OWNER's commit (the old checkout); it should kick at the newest staged checkout | one wrong-code resume per resize. SOURCE DONE 3b4bf8c (newest_staged_checkout; none staged = refused + recorded; both commits on the request) |
| 17 | all day | One read-only `status` probe that prints the whole picture (entry, owner, booking, child cmdline/affinity, receipt, digest progress, disk rate, watchdog) instead of ad-hoc scripts | ~2-5 min per probe, dozens per day. DONE (source): `RUN=<run> DAY=<day> sh deploy/aws/box/frankie_box_day_status.sh` (read-only, POSIX sh + the venv python for JSON; entry/owner/booking, ROOT child flags/affinity/helpers, render, receipt/digest, scratch checkpoints, ROOT log, cpu-watch line, nvme0n1 MiB/s over 3 s, df) |
| 18 | all day | Every restage is ~6 min; batch fixes into one stage per boundary | ~6 min per avoided stage |
| 19 | 17:0xZ | Only data identity (sealed source, pins, counts) in every binding; every run parameter recorded, never compared (the generalisation of #5 across all stages) | one blocker per stage otherwise |

## Standing rules from Greg (2026-10-08, session 9)
- A fleet box keeps the days assigned to it from the first stage to the end: NO box switching, no day migrates to another
  box; the classroom lease only orders which box's day goes next. Apply when the fleet source (frankie_box_fleet.py day
  list / claims) is next touched; not this second.
