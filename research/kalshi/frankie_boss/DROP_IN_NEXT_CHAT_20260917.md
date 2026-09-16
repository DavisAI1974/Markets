# Drop-in for the next chat - Frankie/BOSS, after 2026-09-16 (second session of the day)

Paste to Claude Code. Repository `DavisAI1974/Markets`. Run `using-agent-skills` first.
Read first: this file; then `CCODE_REVIEW_DIPOLE_CLASSROOM_INTEGRATION_20260916.md` (on the
classroom integration review branch), then `CCODE_SESSION_20260916_RESTORE_BENCHMARK_COMPACT_SOURCE.md`
and `CCODE_RUNTIME_TOKEN_REVIEW_20260916.md` for the measurements everything today built on.

## Branches

| branch | tip | what |
|---|---|---|
| `ccode/frankie-lawful-recovery-review-20260915` | `030608e3` | THE working branch: block ingestion path (`0090ee07`), ingestion reduction stack (`848ffe0d`), a reverted CI workflow (`0bb3335d` / `030608e3`) |
| `ccode/frankie-dipole-classroom-integration-review-20260916` | `61c73a2d` | the classroom integration tip `cf9e2c87` plus ccode's review commit; the branch Codex integrates from |
| `ccode/frankie-dipole-classroom-review-20260916` | `02306339` | ccode's review of the classroom hardening; ancestor of the above |
| `chatgpt/frankie-dipole-classroom-integration-20260916` | `cf9e2c87` | ChatGPT's explicit-seam integration, with the Codex handoff |
| `claude/kalshi-s79-kickoff-ij8t9o` | | default; PR #10 (idle EC2 guard) merged at `e975a493` |

Worktrees on the workstation: `E:\Markets` (working branch), `E:\Markets-classroom` (classroom
integration review branch). `.github/workflows/boss_frankie_tests.yml` exists UNTRACKED in
`E:\Markets` only; it was pushed once by mistake, cancelled and reverted the same minute. Greg:
"we have to wait for everything to be built and tweaked before we can build a workflow", and
"the build is going to dictate the flow". No workflow until he says.

## Where things stand

- **Codex is integrating** the classroom review branch into the working branch (handoff
  `CODEX_INTEGRATE_DIPOLE_CLASSROOM_20260916.md` on the integration branch). Rules: classroom
  mandatory on every result-bearing path; any benchmark exemption harness-local and fail-closed;
  preserve the recovery and reduction work; no CI gate.
- **Block ingestion path built, measured, not run on the block.** `operations/ingest_block_sources.py`
  replays the four staged day files as one stream straight into the compact container
  (`compact_build_journal.py`, the builder's `__new__` seam); `block_source_scope.py` binds the
  hash-pinned manifest. `--session-policy cme_trading_day` is required (D49): CME's spec, quoted
  in the tool, is Sunday to Friday 6:00 p.m. to 5:00 p.m. ET with a 60-minute break from 5:00 p.m.;
  a session carries the trade date of the afternoon it ends on, Monday's opens Sunday evening,
  Friday's halt, Saturday and pre-open Sunday roll to Monday. Eight calendar cases tested.
- **Reduction stack measured** on 3,000 real Sunday records, nothing else running:
  82 ms/record before today; 19.8 inline; **14.4 ms/record with three encode workers** (70/s).
  Every change pinned byte-identical to the code it replaced (`tests/test_reduction_stack_equivalence.py`).
  The parent is bound by `pack` over the ~4,000 nodes of each book observation (7.3 ms per
  book payload; an inlined fast path measured SLOWER and is not applied) plus 3-4 ms of builder
  work. Block at 14.4 ms: about 26 h single-stream; the builder is sequential by construction.
  Below that means builder changes (review 2.4), Greg's call.
- **Sunday's extraction pin is not reproducible on the workstation**: `dbn_extraction_hash` is in
  every journal row and Sunday hashed binaries this machine no longer has (a5163ad… now vs
  166f6360… then). The both-ways proof therefore compares raw against compact on identical inputs
  and checks the pin-independent identities (record count 57,027, group count 43,569,
  `source_prefix_hash 39270e89…`) against Sunday's receipts; it has NOT been run yet.
- **The reducer stack of the first run** is in `outputs/frankie-boss/20260915/reduction-stack/`:
  the journal stack (compact codec 20.5x, single-pass conformance, one parent plus three
  affinity-bound workers, 715 s for the whole Sunday in GitHub run 34962256086) and the
  model-input reduction `stacked_v1` in the frozen host (929,730 to 92,427 tokens). The 3.37x
  "faster runner" is the single-pass verified reader (`SPEC-verified-journal-reader.md`); the
  ingestion path's completion drain now runs through it, in parallel when workers are given.

## First business next chat

1. **When Codex hands back, the full Frankie audit, with the chat reviewers.** Scopes:
   (a) every feed and input traced source to Frankie on the integrated tree; (b) no silent drop or
   filter anywhere on the ingestion, journal, prefix, context and packet path, row counts
   reconciled at each hop, not sampled; (c) science files byte-identical to the lawful `050c5056`
   (the list used in all three reviews today); (d) **the 99 ingestion layers**: Frankie's own
   registry `native_ingestion_layer_registry.py` in the frozen receiver (commit `342f5728`) pins
   99 union layers (105 before D64), A_CLEAN 96 / A_MEMORY 98, hard minimum 90, policy counts
   19/4/55/9/2/10, id-set sha `fbb79cde…`, fail-closed pre-call receipt. The last honest render,
   `LAYER_CROSSWALK_SUNDAY_33630348943_FED_RENDER_20260903.md`, shows 99 registered, 98 applicable,
   **9 of 77 applicable inputs delivered**, 45 receipted-carrier-absent, 14 bound to an inventory
   document, 8 produced-not-delivered, 10 carrier-claim mismatches (partly superseded by commits
   `e4d576f`/`9f984bf`; no later render exists). Re-render per cycle on the integrated tree against
   the pinned set; that is the countable check. Also: the classroom's audit directory and principal
   artifacts have no entry in `AUTHORITY_MAP.json` (15 stores, none classroom); add them with a
   declared writer before the audit or the audit has nothing to check them against.
2. The on-host DRY `prime_cache` on the retained cycle-1 compact prefix (review §7) is still not
   done; start the host, run it, stop the host.
3. The Sunday both-ways proof (`--sunday --writer both`, session `constant:supplied-source`,
   `--source-object path`); the raw side writes 114,054 fsync'd rows, so run it on C: (NTFS), not E:.
4. The block ingestion itself, on a Linux host, `--workers` set to the cores minus one, after the
   proof. Then the block schedule and prefixes (the Sunday literals 57027 / 19 / 20211003 become
   manifest fields).
5. A test for the parallel completion drain (`ingest(..., workers=2)` through
   `FrankieCompactReader`) was declined once today; ask before adding it.
6. The stalled full-suite process on the workstation (pid 25608, classroom worktree, blocked since
   05:41 after `test_open_run_explicit_completion_still_stops_retained_pod`, no CPU, no children)
   was left alone at Greg's request. The next files in order, `test_granite_retained_lifecycle.py`
   and `test_granite_retained_start_guards.py`, contain wait constructs.

## Greg's standing orders (2026-09-16, both sessions)

1. One more Sunday run by itself first; the 19-cycle run behind his explicit go, `KeepRunning=true`
   for its duration, a declared fixed thread count (8).
2. Then the Oct 4-6 block as one continuous run, Sunday reopen through Wednesday's halt.
3. Everything built for the one day is reused for the block with only the dates changed.
4. Use every reduction in a stack, not ranked one at a time; "if the options are change some files
   or wait 6 days, we'll change some files. just tell me if their behaviors will change."
5. Find and reuse the first run's reducer stack (found; above).
6. No more Windows after the Sunday run; everything built is OS-neutral Python.
7. No workflow until the build is done and tweaked.

## Do not

Run Frankie, Granite, the Pod, or any result-bearing cycle without Greg's go. Modify anything
under `E:\Codex\Frankie-BOSS-20260915` on the workstation (the Sunday DBN copy there is read for
canaries only). Leave the host running idle. Put anything the next session needs in a scratchpad
(D34: git and S3 only). Push a workflow.
