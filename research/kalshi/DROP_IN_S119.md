# DROP-IN S119 - Frankie A-arm raw-MBO benchmark

**Branch = `chatgpt/frankie-raw-mbo-benchmark-20260828`. Tip = `752ac56`. 896 tests green.**
First commands: `git fetch origin chatgpt/frankie-raw-mbo-benchmark-20260828 && git checkout -B
chatgpt/frankie-raw-mbo-benchmark-20260828 origin/chatgpt/frankie-raw-mbo-benchmark-20260828`,
then confirm the tip message is "The size is one field: 94.7 percent of every byte is book_full".

---

## ITEM ZERO - GREG'S STANDING DOUBT. RECHECK THE NUMBERS BEFORE BUILDING ON THEM

**Greg, at S118 close: "i still feel the numbers need to be rechecked but we'll do that in the
next session."** This is an OPEN item, not a closed one, and it is first because everything
below rests on it.

**He is right to hold it.** Four size numbers were produced this session and all four were
wrong the same way - present, typed, plausible, and measuring something other than what their
name implied:

| number | what it actually measured | real value |
|---|---|---|
| 24 KB/record | the canary's artifact AFTER upload-artifact compressed it | 246 KB |
| 215 KB/record | CloudWatch bytes / a record count NOBODY EVER READ | 246 KB, close by luck |
| 9:1 compression | derived FROM the discrepancy it was invoked to explain | circular, no evidence |
| key names 57.3% of a row | a row I INVENTED, not real data | ~0.1% on real rows |

The current figure (246,030 bytes/record) comes from `ledger_retention[*].bytes`, which is the
sink counting its own writes. That is better than the previous four but it is still
SELF-REPORTED. **The recheck must use an INDEPENDENT witness, and one is available:**

1. **S3's own object sizes.** The canary copies its whole packet to
   `nymex/ng_mbo_5y_v0/frankie/raw_mbo_benchmark/a-clean/<sha>/33596898227-1/` uncompressed.
   `aws s3 ls --recursive --summarize` on that prefix gives S3's byte count for the ledger
   files. If it reconciles to 12,301,736,545 the figure is confirmed by a second party that
   has no stake in it. If it does not, the sink is miscounting and everything downstream moves.
2. **Record count cross-check.** The traversal reports 50,001 records / 40,242 groups; the
   manifest reports `mbo_records` per source. Confirm `records_seen` against the manifest sum
   for a bounded slice, so the DENOMINATOR is verified too - that is exactly what was never
   done for the 215 figure.
3. **Do not accept a per-record figure again without naming which two independent quantities
   it divides.** That single discipline would have caught all four errors above.

---

## ITEM ONE - THE BOX IS WEDGED AND THE REBOOT DID NOT FIX IT

**State at 2026-09-02T06:38Z**: unwedge run 33598410974, step 5 at 17m15s and still looping;
job caps at 07:05:35Z. **Check its final state first.**

**The diagnosis, three independent commands and two eliminations:**
- The Sunday dispatch (~20 KB script), the monitor's script, and a FOUR-LINE `/bin/sh -c`
  whose only action is `df` all returned `Failed`, exit 1, **stdout and stderr both empty**.
  The disk probe's own verdict was `PROBE_ITSELF_DID_NOT_RUN`.
- SSM agent **`Online`**, pinging seconds earlier, agent 3.3.4793.0 - so NOT a hung agent.
- Instance **`running`**, System `ok`, Instance `ok`, r6i.2xlarge - so NOT impaired.
- Root volume `vol-05a0b1e56f8c16478`, **300 GB**, full from the killed run's ~232 GB.

**SSM stages its command script to a FILE on the instance**, so a full volume means nothing
executes and no channel that runs on the box can report anything. **A cleanup placed INSIDE
the dispatch cannot work** - that command is itself a file that must be written to the disk it
exists to free. That was my error and it is why the remedy must come from outside.

**One behavioural change worth noting**: before the reboot commands failed in ~2 seconds; after
it, each attempt is slow, i.e. commands sit **Pending** rather than failing fast. That is a
different state and has not been diagnosed.

**Options, cheapest first:**
1. **Detach the volume, attach it to a throwaway t3.micro, delete `/opt/frankie-a-arm-run`,
   reattach.** Costs pennies, nothing permanent. NOT YET TRIED and it is the best option.
2. **SSM Session Manager** rather than RunCommand - it does not stage a command script the
   same way and may work where RunCommand cannot. NOT YET TRIED.
3. **Grow the volume, then reboot** so cloud-init's growpart enlarges the filesystem.
   **Greg authorised this** ("if this doesn't work then grow it") - but he also challenged it
   correctly: *"why would we have to grow a 300gb box by 20 to run a Sunday that isn't even 2"*.
   The grow is NOT for Sunday; it is a bootstrap to unstick the DELETE. It is a permanent cost
   for a transient condition, so it is the last resort, not the first.
   `frankie_box_unwedge_20260902.yml` with `action=grow_and_reboot`, `grow_to_gb=320`.

**Nothing is lost by any of this.** CloudWatch showed 3.5-4.2 MB per 5-minute bucket (idle
noise, no traversal running), and EBS persists, so the killed run's save points survive.

---

## ITEM TWO - THEN RUN SUNDAY. IT IS BUILT AND VERIFIED, IT HAS NEVER RUN

`frankie_a_clean_rt_native_launch_20260828.yml`, **`mode=full`**,
**`traverse_sources=glbx-mdp3-20211003.mbo.dbn.zst`**.

**Greg's ruling: the real full-run path, NOT the canary** - *"the canary doesn't feel right and
things are going to be missed like the calcs"*. Same box, launcher, arm, manifest, three
pre-traversal gates and eight section 6 gates; only the source list is shorter. All four
objects are still fetched and still in the manifest, because the manifest contract requires
exactly four sources at fixed roster positions with a pinned `source_identity_hash`.

**Sunday = 57,027 records = 14.0 GB. It fits the existing 300 GB volume once cleared. Buy
nothing for it.**

**Three defects the RENDERED command exposed, all fixed** (D57: render, never read):
1. The box path never passed `--cadence-groups`, so it took the 250,000 default. One roster
   object is ~45,000 groups, so it would have fired NEVER and **staged not one spawn request** -
   a finished run with nothing for Frankie to be spawned against. Cadence and checkpoint
   interval now scale with the slice, verified by reproducing the full-roster numbers.
2. The disk precheck was a constant from the wrong per-record figure. Now computed per record.
3. `PACKET_DIR` was read from the environment in the step that WRITES it; `$GITHUB_ENV` reaches
   later steps only, so it would have raised `KeyError`.

**The upload no longer needs an IAM change.** Presigned PUTs mirror the presigned GETs already
used for the sources - signed, write-only, one key, expiring, never carrying the secret. Output
names are deterministic, ledgers are gzipped (5 GB cap per PUT), and the sha256 of each PLAIN
file travels in `PLAIN_SHA256SUMS`. The scoped role policy is now tidy-up, not a blocker.

---

## ITEM THREE - FRANKIE'S REPORT, THEN STOP FOR THE REVEAL (D68)

**No run calls Frankie and by design none can.** The launcher produces EVIDENCE and never calls
a model; the traversal stages a spawn request at each lawful cutoff and moves on. A traversal
is ACCEPTED as **evidence only** and gate 8 says so in words - the canary's
`Completion: EVIDENCE_ONLY` confirms it. `attach_principal_findings` is the only route into the
findings layer and no workflow calls it.

So the report is an **agent session** reading the staged request plus the evidence and emitting
a committed artifact, exactly as the blind and refine specialists ran.
`load_principal_artifact` hard-fails on a missing artifact, on findings citing a different
evidence hash, and on an empty findings list, so an unrun spawn cannot be recorded as zero
findings.

**Greg: "a full indepth report from Frankie. on the calcs, on the full raw mbo, all of it. once
that is done we'll stop so we can do the reveal and then go from there."** The stop is part of
the instruction.

**Aim it at `book_full`.** Subject to item zero, the measurement says 94.7% of every byte is
that one field and all sixteen calculations together are ~1.5%. So "which calc is the size" has
the answer "none of them", and the only thing worth Frankie's judgement on cost is the
per-group full book snapshot - which is the thing Greg already ruled must stay: *"do not leave
any of the book data out. it may not seem relevant to you but it may to frankie."*

---

## WHAT IS BUILT AND PUSHED THIS SESSION

- **Per-section and per-field byte attribution** in `native_row_sink` (exact section totals
  that sum to the ledger total; per-field SAMPLED at a prime rate and labelled as estimates).
- **`report_ledger_size.py` + 6 tests** and `frankie_run_size_report_20260902.yml` - renders the
  table from a finished run's `calculation_result.json` on S3, because no interactive session
  resolves AWS credentials.
- **`frankie_box_unwedge_20260902.yml`** - `action` defaults to **`report`** (read-only), since
  three causes give the identical symptom and need different fixes.
- **D67** (nova: two reducers, minification saves ZERO here because the sink already writes that
  form; the value is `plan_retrieval` and declared withholding) and **D68** (Frankie's report,
  then stop for the reveal).
- **`FRANKIE_MEASURED_LEDGER_SIZE_20260902.md`** - the measured table and the four corrections.

**A workflow carrying only `workflow_dispatch` is never registered on a non-default branch and
the dispatch API 404s it.** Both new workflows needed a `push` trigger; where a push could fire
a destructive step, it is additionally guarded on
`github.event_name == 'workflow_dispatch'`.
