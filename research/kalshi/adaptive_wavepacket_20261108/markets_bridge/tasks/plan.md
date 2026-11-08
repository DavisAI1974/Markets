# Standalone NG shadow discovery

## Repository handoff

Use the `codex/ng-shadow-discovery-20261108` branch in `DavisAI1974/Markets` and record the commit in each handoff. Keep original evidence, manifests, decisions, receipts, plans and code in Git. Continue in a repository-backed workspace without a dependency on C:, E:, or the desktop. Regenerate caches, dependencies and temporary fixtures in that workspace. Use targeted reads at pinned revisions. Keep the component standalone, with simulation only and no AWS, broker credentials, merge or deployment.

Evidence base is audit branch `codex/ng-wavepacket-audit-20261108` at `f6af02144`, with the original PR #12 snapshot pinned at `994b79a`. See the [independent audit](../../CODEX_INDEPENDENT_NG_AUDIT_20261108.md), [paired pilot](../october18_book_entropy_pilot/october18_book_entropy_pilot.md), [standalone receipt](../october18_book_entropy_pilot/october18_solo.md), and [four-arm receipt](../october18_book_entropy_pilot/october18_stack.md).

The shadow runner evaluates every registered rule on its own eligible opportunities. It emits observations and reasons, with separate records for market outcomes, the paper-test queue, and simulated orders. This is a proposed design. Each variant's broad status remains `NOT_ENOUGH_INFO`.

## What the existing ledgers show

The October 18, 2023 window contains 22,194 consecutive saved books for instrument 150611. Three pilot ledgers and their source hashes were checked against the pinned Git inputs. The stack and paired pilot retain the same 2,850 falling-touch signal rows and exact source coordinates. The solo ledger retains 1,978 dispositions, including 81 ambiguous print groups.

| Fixed rule | Ask / long calls | Bid / short calls |
| --- | ---: | ---: |
| Falling touch | 1,412 | 1,438 |
| Entropy decline alone | 132 | 125 |
| Directional prior-touch print alone | 615 | 544 |
| Falling touch + entropy decline | 520 | 453 |
| Falling touch + same-group print | 171 | 155 |
| Falling touch + both | 59 | 50 |

The table uses each rule's full observed scope. The four-arm matched comparison restricts the baseline to 990 ask and 931 bid opportunities with a usable entropy decision. Within that scope the print arm takes 111 ask and 96 bid calls. On the ask at 1 second, the full stack records 27 agreements, 11 oppositions and 21 flats. At 5 seconds the same stack records 24 agreements and 25 oppositions. The standalone bid entropy rule has 29 agreements, 39 oppositions and 57 flats at 1 second. The receipts keep the adverse, flat and censored outcomes at every horizon.

| Standalone pair | Same group and direction | Same group, opposite direction pairs |
| --- | ---: | ---: |
| Falling touch and entropy | 15 | 12 |
| Falling touch and directional print | 302 | 20 |
| Entropy and directional print | 5 | 5 |

The same-direction counts include the one three-way agreement, bid/short at group 241500, cursor 314654, book line 12300, with original print 11556. Its baseline call also qualified for all four stack arms. Across all standalone calls there were 3,819 distinct native groups, 126 with both long and short calls. These counts use the same committed window and are descriptive. Nearby groups can share feature inputs or outcome intervals. Keep every rule decision and treat a shared group as one market observation.

## Candidate register

Use a stable rule ID, version and side per variant. Keep the rule text, source links, observed and fresh instance IDs, testability requirements, research status and paper status. The six fixed rule families above seed twelve side-specific variants.

- **Falling touch.** At a completed group, the last three consecutive same-side best prices match, the three sizes are nonincreasing with a strict decline across the path, and the latest size is greater than one. Call at the first qualifying close in each consecutive run. A failed qualification resets the latch. Ask calls long, bid calls short. Later thinning is an outcome annotation.
- **Entropy alone.** Compare same-side fixed-bin touch-size entropy at the closes of two consecutive ready, nonoverlapping 60-group blocks after calibration. Strict decline calls long on ask and short on bid. The pilot used its first 92 blocks to freeze bins. Freeze block anchor, calibration cutoff and bin version before a fresh trial. Warm-up and incomplete blocks get explicit dispositions. Computing entropy follows the fixed feature definition and keeps all original sizes.
- **Directional prior-touch print alone.** At a completed group with verified prints and a verified adjacent prior book, all prints at the prior ask call long, and all at the prior bid call short. Preserve every print, even equal-timestamp prints. Mixed prices, off-touch prices and ambiguous prior quotes get explicit dispositions. The observed price relationship supplies a direction convention.
- **Falling touch + entropy.** At the baseline close, use the latest two complete post-calibration blocks already known by that coordinate. Reuse the baseline direction. Keep prior/latest feature endpoints, values and feature age. A block closing at the same group can qualify when its full inputs are already known.
- **Falling touch + same-group print.** At the baseline close, require any reconciled print from that group with availability time and cursor at or before the decision. Reuse baseline direction even if the standalone print is ambiguous or points the other way. Zero prints requires verified group membership coverage.
- **Falling touch + both.** Apply the preceding two predicates to the same baseline opportunity. Preserve each component disposition as well as the combined decision. For parity with the pinned stack, missing usable entropy yields an unknown arm value even if the print condition is false.

Keep earlier observed rule families in the register as separate evidence-linked entries for each side. These include size-one onset and retreat to the previous second level. For size-one, register standing shrink and changed best with/without a same-group print, and the observed falling/flat standing-path variants with/without a print at onset. A changed best can be annotated as a retreat or improvement when known. Later retreat, recovery, improvement and whether they occur by eligible entry are outcome classes for these premises. [Earlier replay and per-case links](../../../../../artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1/historical-paper-replay-v1/README.md)

Use separate research entries for fresh preceding-second flow, rolling flow and algebraic dipole timing. The exact-close availability pass found four usable flow cases per side, with five nonzero rolling cases without a fresh print and two fresh/rolling sign oppositions. All eight records and their outcomes stay linked, including unmatched inputs and the absence of any exact-close full dipole match. A testable directional or timing variant gets its own frozen ID once its predicate and timing requirements are specified. Keep new observed singleton, weak, adverse and contradictory variants on the same register. A description that uses a later outcome stays as an annotation until there is an as-of predicate.

## Data and decision contract

1. **Ingest.** Start with the pinned saved-window adapter. Require source identity and SHA-256, source row IDs, instrument/session, group ordinals, event/receive/known-by nanoseconds, and native input cursors. Validate sequence and coverage. Retain every native observation. Use a declared segment boundary at gaps, corrections, resets, contract/session changes or unusable coverage. Reset adjacent-book state and entropy windows at boundaries, and document when new warm-up starts. Incomplete records produce coverage dispositions. A later correction can link a new record to the original decision.
2. **Evaluate at each verified completed group.** Key the market observation by source/session, instrument, group, known-by ns and cursor. Keep a decision per rule version and side, with its evaluation coordinate and exact source dependencies. Separate rule scope, data readiness and predicate result. Example states are out of scope, warming up, inputs missing, ambiguous, eligible/no signal and triggered. Include review reasons and retain partial evidence for unknown predicates. Evaluate both sides and all applicable arms before any queue decision.
3. **Join and score separately.** After decisions are sealed, attach first subsequent eligible quote at least 1 ms after the decision and the first later eligible completed quote at least 1, 5 or 30 seconds after that entry. Use the existing signed twice-midpoint change and retain exact integer observations, agreements, oppositions, flats, missing inputs and entry/exit censoring. Censor at the declared segment/window end. Score the common-support stack on the same baseline rows and report full rule scopes separately. Preserve original historical execution-assumption fields in the archived ledger. Use no synthetic market observations, fees, smoothing, averaging or replacement of original rows in market research.
4. **Relate the decisions.** Log shared group, same-side co-fires, opposite directions, nested arms, reused input blocks and overlapping outcome intervals. Use stable observation and decision IDs for idempotent reruns. Include source, rules and calibration hashes in the run receipt. A selector that learns which rule to apply by context is a separate candidate. Freeze its features, abstention, tie handling and evaluation protocol, then evaluate prospectively on fresh observations alongside the fixed rules.

## Paper-test queue and capture

Keep every defined rule with an observed eligible instance. Record occurrence count for scheduling. Keep a lane for rare cases and a linked targeted Replay task when that exact setup is accessible. Replay can establish recognition and simulated execution mechanics. Another replay of the same market moment links to the same observation ID. Fresh market instances get separate IDs, including ones missed by the operator. Queue states can distinguish mechanics pending, coverage hold, setup approval pending, ready for simulation, and observed. An opposed direction or missed opportunity stays in the ledger.

Tradovate NGZ6 SuperDOM and Time & Sales visibility were verified in November 6 Replay. That is a separate environment and instrument/session from the October 18 evidence. Use user-operated Android Chrome and the simulation interface. First run a no-order capture of a short Replay interval, recording what can be observed and the displayed timestamps, order of changes, prior touch and individual prints. Tag the UI's actual resolution, missing group identities and unknown membership or completeness. Treat a UI observation as a separately labeled mechanics record if native group membership, cursor or completeness cannot be verified. The native 1 ms benchmark and 60 native group feature require their corresponding data coverage.

Before the first simulator order for any variant, agree on its exact trigger, order type, size and exit. A paper ticket also needs the variant version, instrument, session, source coordinate and simulator mode. Keep actual operator decision, submit/ack timestamps, missed, rejected, unfilled and partial orders, fill prices/quantities, exit and any contradictory outcomes in a separate execution ledger joined to the shadow ID. The shadow runner has a local input and ledger interface only.

## First run and open work

Recover and verify October 18 full-session coverage before generating new market scores. Keep the saved window and original receipts as provenance and use its cases for source reconciliation. Use group 241500 as the overlap check, group 229205 at cursor 297873 as the directional disagreement check and group 229253 at cursor 297953 as the ambiguous print check. The last group includes print 10862. Once source coverage passes, reconcile the archived window against the recovered stream and compare identical raw prefixes with different real suffix lengths. Record availability differences and censoring as outcomes of coverage. Start operator capture in November 6 Replay only as a separate no-order mechanics check.

Keep BuildMap scanner/viewer and the algebraic five-step, Level 2 and predictive geometry work in the component. Log their inputs, run receipts and holds independently. The fixed-bin book pilot leaves full flow and algebraic runs open. October 18 full flow requires verified contiguous native records, original trade identities, native timing and complete-window availability, strictly earlier calibration, disjoint raw spans, valid settle segmentation and the audit's null and leakage controls. Review current donor averaging and dispersion before admitting a geometry result. Frankie integration follows a later handoff.

## October 18 coverage gate

The original AWS tape was unavailable when this gate was set. The Git redownload passed the source checks below. The pinned native adapter replayed both complete sessions. The October 3 opening order count and session counts matched its original receipt. The archived book-value comparison is available for October 18. The opening resting order count and all 22,194 archived book values checked at their original closes matched. Full calculation scoring still requires the complete pinned inputs and independent calculation checks. The Git projection contains 22,194 consecutive completed books for instrument 150611, groups 229201 through 251394, from 13:07:12.293731473 to 13:19:12.020583540 UTC. All adjacent group numbers and increasing cursors were checked. This window is 3.8% of the 583,688 completed groups in the sealed-session receipt. Sparse book views, the 30,739 original trade links and the 8,088 saved flow-second rows remain evidence. They do not reconstruct the remaining consecutive book and flow history. The 13-data-point external attachment remains linked separately.

The smaller recovery route is the two exact raw MBO members:

| Original file | Bytes | SHA-256 |
| --- | ---: | --- |
| `glbx-mdp3-20231017.mbo.dbn.zst` | 14,484,156 | `189f85d015131362092a5f1e5cf023d27c3b89adecbb54752a1dff5b3b87221b` |
| `glbx-mdp3-20231018.mbo.dbn.zst` | 12,867,663 | `bc6cf8dff8662d540e36f1b73579bf97c8eb597cd9fdc8f83723dd6d35d68d7f` |

The pinned sealed journal is the other recovery route. It is 8,824,270,848 bytes with SHA-256 `46ca9fa0f046c3c22c958c66f4a3bfdfc3876a4d7bc2c010b9f163003f6c0319`. The original raw pair, journal and exact opening-book size did not match any locally available Git blobs at the time of the initial check. The source manifest and pointer supply expected values. [Raw source manifest](https://github.com/DavisAI1974/Markets/blob/93895487c199b1e486d5407f9e103a0964903d2d/research/kalshi/frankie_boss/blocks/BLOCK_20231018_SOURCE_MANIFEST.json) · [Sealed journal pointer](https://github.com/DavisAI1974/Markets/blob/c28a4de13263b6354662cd376fecc7733b47a991/ingest_pointers/20231018-gh-36571235912-1.json)

Verify the bytes and opening state. The raw route applies the first 841,601 October 17 records to opening state, then journals the 17,375-record October 17 tail plus the first 754,412 October 18 records. Reconcile 771,787 source records and 583,688 completed groups, exact instrument, native group continuity, clocks and cursors. Compare overlapping original saved books and prints, and keep any disagreements visible. Audit observed zero versus unavailable flow and require the as-of timing and strictly earlier calibration inputs before admitting full-flow results. Only run new discovery scores after coverage is verified.

## Databento fallback for both sessions

The pinned acquisition used `GLBX.MDP3`, continuous symbol `NG.v.0` (volume rank zero), `mbo`, DBN encoding, zstd compression and daily splitting. Request only the two windows below. [Original acquisition workflow](https://github.com/DavisAI1974/Markets/blob/93895487c199b1e486d5407f9e103a0964903d2d/.github/workflows/ng_historical_mbo_5y_to_s3_20260820.yml) · [Databento batch download](https://databento.com/docs/portal/batch-download)

| Session | Inclusive UTC start | Exclusive UTC end | Daily members |
| --- | --- | --- | --- |
| October 3 | 2023-10-02 00:00 | 2023-10-04 00:00 | October 2 and 3 |
| October 18 | 2023-10-17 00:00 | 2023-10-19 00:00 | October 17 and 18 |

The prior UTC day provides opening-state warm-up and the first part of each target session. Check the signed-in portal estimate before submitting. Preserve request metadata, condition and symbol mapping with the files. The four files were re-downloaded for a reported total of $0.31. Check any subsequent source against the pinned manifests. If the new batch differs, record its own provenance and verify contract mapping, native timestamps, sequence and session boundaries plus replay reconciliation before admitting it as a new source version. Keep requests and verification in Git. Store tape in a repository-backed location consistent with its distribution rights. [October 3 manifest](https://github.com/DavisAI1974/Markets/blob/93895487c199b1e486d5407f9e103a0964903d2d/research/kalshi/frankie_boss/blocks/BLOCK_20231003_SOURCE_MANIFEST.json) · [Databento request parameters](https://databento.com/docs/api-historical/batch)

## Verification of the Git redownload

Read the four daily DBN files at `1d15dc6f1b5bbb1fabb6389d18e8bedba2b77202` on `ccr-017c4996-ywi3tm`. All four compressed sizes, SHA-256 values and decoded record counts match the new manifest. Each file starts with snapshot records at UTC midnight and contains only instrument 150611, identified in the source README as NGX3. No receive-time reversals were found. All four compressed hashes differ from the corresponding older archive hashes. Keep this redownload as a separately pinned source version. [Git tape and manifest](https://github.com/DavisAI1974/Markets/tree/1d15dc6f1b5bbb1fabb6389d18e8bedba2b77202/data/nymex_mbo/ng_v0_oct2023)

| Trading session | Records used to warm the opening book | Records in the trading session | Native completed groups |
| --- | ---: | ---: | ---: |
| October 3 | 808,453 | 879,830 | 653,912 |
| October 18 | 841,601 | 771,787 | 583,688 |

Both session cuts and completed-group counts match the old sealed receipts. See the [native replay receipt](book-replay-receipt.json). On October 18, all 30,739 native trade rows match the archived trade links by source cursor, group-close cursor, event, receive and availability clocks, instrument, raw price and size. All 22,194 archived book closes match the original group ordinal, cursor, event and receive clocks, and instrument. The subsequent native replay also checked each archived close's exact touch price, touch size and order count, top-ten depth, full depth and price-level counts on both sides. All comparisons passed.

Keep the four daily files intact and decode their native records in session order. Warm the opening book from the previous UTC member and apply native snapshots at their recorded positions across the midnight seam. Continuous rule state follows the verified trading session and each rule's declared reset boundaries. If a future file is split for storage, reassemble it byte for byte and verify the original hash before decoding. Chunk boundaries have no trading-session meaning.

## Complete pinned calculation scope

Resolve the [ROOT and inherited calculation audit](root-calculation-audit.md) before admitting expanded market inputs. Rebuild the eligible feature matrix from the original source observations and role contracts. Verify calculations against independently derived source values. Use historical equality to test reproduction and record any original errors separately. Preserve the frozen V3 matrix for historical comparison.

Run the complete pinned input set together for each requested session. Storage limits cannot remove observations, reduce book depth, omit a plane, shorten a required history, or change calculation definitions. Use lossless compression or restore and verify every byte of any storage chunks before reading them. Keep the raw and external sources, mappings, code, coverage and results pinned. Measure runtime scratch space and durable output size separately before choosing storage for the full outputs.

The 99-entry inventory covers raw inputs, calculations, clocks, knowledge, controls, arms, sealed answers, shadows and outputs. Each must be accounted for in its documented role with the source revision, consumer, units and availability. Include the full tape and book with FIFO and order lineage, native and ROOT calculations, the complete confirmed second set, external histories behind all 13 bindings, and the original knowledge and dipole evidence. Apply the recorded as-of and scope rules. The October 18 second-set source members are preserved in Git. Both external attachments have verified source receipts. Availability and equivalence for every full input and consumer on both days still need to be established. Verify the full reconstructed books and all required inputs before starting the complete calculation. [Full-context acceptance](../../../../../tasks/family-research-20261022/full-context-coverage-spec.md) · [99-plane registry](../../../../../artifacts/sqlite-triage/20261022/families/descriptive-v1/plane_registry.csv)

## October 3 and October 18 discovery evidence

October 3, 2023 is a Tuesday trading session. The pinned tape includes the opening segment after the Monday, October 2 21:00 UTC halt. Earlier records reconstruct the opening state. Obtain and verify the pinned sealed journal or both original raw tape members before running October 3. Check SHA-256, opening state, continuity and session cuts. The original manifests and journal pointer are in Git. The new Git source passed the coverage checks below. [October 3 source recovery](../../../../../artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1/other-30-day-local-liquidity-readiness-20261107.md)

Both days have a day-keyed `day-external.json` attachment for the 13 historical data points, including weather, storage, curve, power, positioning and calendar context. The recovery receipt records a complete hash match for each original file, with 288,095 source rows for October 3 and 329,647 for October 18. Keep both attachments linked. Treat publication and availability separately and preserve unknowns. The fixed liquidity rules keep their original inputs and context-dependent variants receive separate rule versions. [October 3 attachment](../../../../../artifacts/sqlite-triage/20261022/families/full-context-audit/brain-manifests/20231003-external--MANIFEST.json.json) · [October 18 attachment](../../../../../artifacts/sqlite-triage/20261022/families/full-context-audit/brain-manifests/20231018-external--MANIFEST.json.json) · [Hash verification receipt](../../../../../artifacts/sqlite-triage/20261022/families/full-context-audit/external_history_recovery.json)

October 3 and October 18 both inform paper discovery. Apply the same rule definitions, timing checks, outcome horizons and evidence retention on both dates. Use the same fixed-bin calibration protocol with causally available inputs. Keep the session ledgers distinct and compare recurrence by rule version and side. Register recurring and day-specific testable candidates from either date, including singletons and adverse, weak or contradictory cases. Keep ambiguous and unscorable observations. A rule derived or revised on these days needs later fresh evaluation under its frozen definition.

Finish the October 3 comparison before any simulator paper order. Use findings from either or both days in the paper queue, with the trigger, order type, size and exit agreed before the first order for each variant. No-order Replay capture can proceed independently.
