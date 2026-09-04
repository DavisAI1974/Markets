# DROP-IN S128 - THE RESULT HASH, THEN OCT 1, THEN THE REST OF THE ROSTER

Branch `chatgpt/frankie-raw-mbo-benchmark-20260828`. **The branch head is authoritative** - do
not pin to a hash written before the commit that carries it.

    git fetch origin chatgpt/frankie-raw-mbo-benchmark-20260828
    git checkout -B chatgpt/frankie-raw-mbo-benchmark-20260828 origin/chatgpt/frankie-raw-mbo-benchmark-20260828
    git log --oneline -1

Read `research/kalshi/SESSION_HANDOFF_2026-09-04_S127.md` first. It is 193 lines and every
number below is sourced there.

## WHAT CHANGED, AND IT IS THE THING WE HAVE BEEN WAITING FOR

**Frankie ran and filed.** 43,569 of 43,569 groups, all eighteen contract sections computed by
him at twenty turns, a 30-of-30 bundle that validates, **18 findings F-45 through F-62**, F-20
PASS, and an independent raw-DBN traversal whose order-book reconstruction matches the delivered
one at every group. Four served lessons are refuted by his own numbers. 9a is **KEEP
EVERYTHING** over 661 classifications with zero eliminations. The run is frozen under
`principal_runs/frankie-a-memory-rt-33746436209-1/` with a hash manifest.

**S125 section 2 and DROP_IN_S126 item zero are WRONG and are superseded.** Sunday delivered;
all three ledgers verified against the box's own digests. Do not re-run the Sunday traversal.

## ITEM ZERO - THE RESULT DOES NOT HASH TO ITSELF

`read-back` refuses to attach his findings to the run's result:

    declares result_hash c406eee730401de1... and recomputes to 41d980e10e9efc1a...

Five explanations were ruled out by execution (handoff section 6): not delivery corruption - the
file is byte-identical to what the box wrote; not a hashing mismatch - all three
`canonical_hash` implementations agree; not version skew - the launcher at the run's commit is
identical to HEAD; not a serialization artifact - the body round-trips identically; and no
variant of the hashed subset reproduces the declared value.

**This blocks every day, not just Sunday**, because no daily artifact can attach to its run's
result until it is fixed. It is the F-feed-6 shape S122 recorded as fixed. Start here.

**Do not fix it by relaxing the check.** A result that cannot prove it is intact must not
receive findings. Find what the hash was computed over. The suspicion worth testing first is
whether the box ran a launcher whose `code_commit` stamp does not describe the code that ran -
compare the traversal's own `evidence_identity` against the commit it claims.

## ITEM ONE - OCT 1, THEN OCT 4, THEN OCT 5

    glbx-mdp3-20211001.mbo.dbn.zst  1,504,374 records
    glbx-mdp3-20211004.mbo.dbn.zst  1,994,358 records
    glbx-mdp3-20211005.mbo.dbn.zst  2,111,930 records

One complete source object per run; the launcher and emitter refuse multi-source execution.

**Sunday's findings cannot carry until Oct 1 lands.** The carry fired automatically on the push
of Frankie's artifact and refused with `SeedBuildError: A-memory findings for 20211003 arrived
before prior roster day(s) ['20211001']`. That is the gate working as designed. **Do not relax
it.** The loop itself is proven: the workflow fires on the artifact appearing in
`principal_runs/`, with no human in the path.

These days are 26x to 37x Sunday's record count. Before dispatching, fix the cadence (item two)
or a weekday will get the same nineteen arbitrary decision points Sunday got.

## ITEM TWO - THE CADENCE IS A GROUP COUNT, NOT AN EVENT

`native_a_arm_launch` installs `_GroupCadence`, a pure count: the launch workflow computes
`cadence = records * 0.8 / TARGET_SPAWNS` with `TARGET_SPAWNS = 20`, which on Sunday is 2,281,
and every one of the 19 cutoffs is an exact multiple of it. The driver's `CandidateEventCadence`
- which fires on a recognition or a 4.16 change point, and whose docstring says "there is no
clock in here to schedule on" - is built and **not used by the launch path**. 91 candidates were
promoted on Sunday and not one of them caused a decision point (F-51).

Fixing it changes where the decision points fall, so it is a weekday change, never a Sunday
re-run.

## ITEM THREE - STREAM_END EMISSION (D100)

65,962 of 395,447 lifecycle rows are emitted at STREAM_END, and 65,220 of those - 98.9% - are
just lineage (every node) and mirror (whose offers sit PENDING at group close). So **4.13 and
4.4 exist at no decision point**; a real-time principal has them only in the post-mortem. Only
742 are genuinely end-of-stream and correct. A lineage node's parent is knowable when the
successor arrives; a mirror match when its counterpart arrives inside the declared bound. Fix
before the weekdays. **Never by re-running Sunday** - D100.

## ITEM FOUR - HIS OWN CORRECTIONS, WHICH ARE NOT OURS TO OVERRIDE

- **F-61**: his FIFO rule is wrong after a partial fill - a MODIFY restating a residual keeps
  priority. 118 of 87,138 touch comparisons. He scoped the consequence himself. If anyone builds
  on his queue-position numbers, read that finding first.
- **F-53**: five retained fields are defective AS CARRIED. Repair, not removal.
- Four served lessons are REFUTED with numbers (handoff section 4). They are his findings about
  memory, and they supersede the earlier readings on those specific points.

## STANDING CONSTRAINTS - UNCHANGED

- Keys do NOT rotate during the walk. Do not raise it.
- AWS credentials are GitHub-secret scoped: an interactive session resolves NONE. **All S3
  access is a workflow or it is nothing.** Two delivery workflows now exist - ledgers and raw
  sources - both presigning against pinned witnesses.
- D61: `research/ng_exhaustion_mbo_v4_state_adapter_20260820.py` must hash exactly to
  `4a80e3e4b83867046d318ba97d350c2d7aca22e9d182d98399d01eeacc72d3ce`. Restore by WRAPPING.
- D99 input isolation: non-MBO context families are `IGNORE_AS_EVIDENCE` for the four one-day runs.
- D60: nothing dropped without discussing it first.
- **Never hide a worse measurement or relax a gate to obtain green.**
- No emojis or special symbols in anything pushed.
- Develop, commit and push ONLY to `chatgpt/frankie-raw-mbo-benchmark-20260828`. No PR unless
  Greg explicitly asks.

## HOW TO RUN HIM, BECAUSE THIS IS NOW KNOWN

He is an agent session over committed files - no API, no runner doing his calculations. The
sequence that worked:

1. `fetch_frankie_ledgers fetch` with the delivery manifest, which verifies every ledger against
   the box's own digests and writes the delivery receipt.
2. `emit_frankie_spawn` with `--result`, `--delivery-receipt` and `--ledger-dir`. It now builds
   the knowledge delivery itself when `--knowledge-receipt` is absent, writing
   `KNOWLEDGE_BUNDLE.md`, `KNOWLEDGE_RECEIPT.json` and the pre-call receipt beside the prompt.
3. Spawn him against the emitted prompt with the three ledgers, and tell him plainly that the
   runner's `calculation_result.json` is NOT his evidence and the lifecycle ledger's per-section
   rows are the runner's calculation output, not his.
4. Commit and push his outputs AS THEY LAND. He restarted four times; everything survived
   because it was pushed each time.

**Do not hand him conclusions.** Two findings this session were seeded by the coordinator and had
to be attributed or dropped. Line-of-inquiry pointers belong in `confidence_basis`, or the
measurement of how he performs is corrupted.

## OPEN REVIEW ITEMS CARRIED FORWARD

- **O1** - the change-point dispatch rule exists in three copies.
- **O4** - no census off switch; confirm against a re-profile.
- The reviewer's Gap A and Gap B corpus additions to the census differential.
- Nova `plan_retrieval` (D67) - still never wired.
- Save points for a from-raw traversal: `periodic_checkpointer` does not fit, because
  `export_adapter_state` refuses anything that is not a `V4MboAdapter` and conforming would
  couple two reconstructions built to be independent.
