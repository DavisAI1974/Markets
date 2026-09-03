# DROP-IN S126 - RECOVER SUNDAY, THEN THE THREE WEEKDAYS

Branch `chatgpt/frankie-raw-mbo-benchmark-20260828`. Start from tip `7b7400b`.

    git fetch origin chatgpt/frankie-raw-mbo-benchmark-20260828
    git checkout -B chatgpt/frankie-raw-mbo-benchmark-20260828 origin/chatgpt/frankie-raw-mbo-benchmark-20260828
    git log --oneline -1     # must be 7b7400b or later

Read `research/kalshi/SESSION_HANDOFF_2026-09-03_S125.md` first. It is 179 lines and every
number below is sourced there.

## ITEM ZERO - GREG'S, NOT A SESSION'S

**Sunday run 33746436209 traversed and uploaded nothing.** Every object at its prefix is
timestamped at staging; `ledgers/`, `calculation_result.json`, `small_artifacts.tar.gz` and
`PLAIN_SHA256SUMS` are absent. The cause on record is that the box instance role has NO S3
write access - `research/kalshi/FRANKIE_A_ARM_FULL_DISPATCH_BLOCKER_20260830.md` carries the
scoped policy, written and not applied. **Granting an account-level role new permissions is
Greg's call.**

**Before re-running anything, check the box's 300 GB volume for the ledgers.** A completed
traversal sitting on a disk is an UNDELIVERED run, not a failed one, and re-running it burns
the spend twice. SSM command id `9c8fc423-16b7-4435-bab8-b6368424b691`.

## ITEM ONE - F-20 ON SUNDAY

Once the ledgers are retrievable, dispatch
`.github/workflows/frankie_stream_receipt_20260903.yml` with the Sunday prefix and
**`subdir: ROOT`** (a box run writes at the prefix root; only a canary writes under `canary/`).
It gunzips, verifies against `PLAIN_SHA256SUMS`, prints F-20 and persists the receipt beside
the ledgers.

F-20 PASSED on the canary - `withheld_no_own_clock` 0 and `withheld_close_occasion` 0 against
43,569 and 65,960 before the wiring - but it is owed on Sunday.

## ITEM TWO - THE THREE WEEKDAYS, ONE AT A TIME

    glbx-mdp3-20211001.mbo.dbn.zst  1,504,374 records
    glbx-mdp3-20211004.mbo.dbn.zst  1,994,358 records
    glbx-mdp3-20211005.mbo.dbn.zst  2,111,930 records

One complete source object per run. The launcher and emitter refuse multi-source execution;
never pass more than one `--source`.

**The carry gate is not a defect.** While Oct 1's artifact is `MISSING`, `build_finding_memory`
raises `SeedBuildError` for any later day. Do not relax it to get a run to go green.

## ITEM THREE - RE-PROFILE BEFORE ANY MORE OPTIMISATION

**Do not quote the 1.04x parallel ceiling.** It was measured when the census was 78% of the
traversal; the census is now 11.98x faster and at HEAD the ceiling is roughly 4.3x. About 26%
of the run was never attributed to any bucket and was never decomposed. Run
`.github/workflows/frankie_traversal_profile_20260903.yml` and read the new shape before
proposing anything.

Order-book reconstruction is genuinely serial and no core count helps it.

## STANDING CONSTRAINTS - UNCHANGED

- Keys do NOT rotate during the walk. Do not raise it.
- AWS credentials are GitHub-secret scoped: an interactive session resolves NONE. **All S3
  access is a workflow or it is nothing.**
- D61: `research/ng_exhaustion_mbo_v4_state_adapter_20260820.py` must hash exactly to
  `4a80e3e4b83867046d318ba97d350c2d7aca22e9d182d98399d01eeacc72d3ce`. Restore by WRAPPING,
  never by editing it.
- D99 input isolation: non-MBO context families are `IGNORE_AS_EVIDENCE` for the four one-day
  runs. Do not infer, fabricate, backfill or retrieve them.
- D60: nothing dropped without discussing it first.
- **Never hide a worse measurement or relax a gate to obtain green.**
- No emojis or special symbols in anything pushed.
- Develop, commit and push ONLY to `chatgpt/frankie-raw-mbo-benchmark-20260828`. No PR unless
  Greg explicitly asks.

## THREE WORKFLOW GOTCHAS THAT COST HALF AN HOUR EACH

1. An empty workflow input NEVER arrives - GitHub substitutes the input's own `default:`.
2. `a && b || c` cannot carry a falsy value; `X && '' || Y` yields `Y`.
3. So translate a sentinel like `ROOT` in BASH, never in the expression.

## OPEN REVIEW ITEMS

- **O1** - the change-point dispatch rule exists in three copies (canary bash, box-dispatch
  heredoc, regression test). Three copies is how a polarity bug survives a fix at one site.
- **O4** - no census off switch; likely closeable now, but confirm against a re-profile.
- The reviewer's Gap A and Gap B corpus additions to
  `tests/test_native_mbo_field_census_differential.py`.

## WHAT LANDED IN S125

Canary ACCEPTED, 0 failed gates, 18 of 18 sections fed - the first traversal ever completed on
this lineage. All four falsifiers answered (F-20 PASS, F-30 PRESENT, F-26 PRESENT, 4.16 = 51
tracks). Census 1.00x -> 11.98x, byte-identical, pinned by a differential against a reference
implementation over 25 adversarial shapes. Three new workflows: canary result read, stream
receipt, traversal profile. One real bug found and fixed (an empty list invented a field), one
almost-shipped (`--emit-change-points` does not exist), and the starting tip repinned.
