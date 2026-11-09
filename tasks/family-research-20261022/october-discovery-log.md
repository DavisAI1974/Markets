# October NG discovery and paper-test log

October 2, 3, 17, and 18, 2023 are four equal discovery dates for NGX3
(instrument 150611). October 2 and 17 use the available spans starting at
the UTC midnight snapshots. October 3 and 18 have full-session tape coverage.
Each date gets its own observed signals, including opposing calls, flats,
misses and unavailable inputs. Keep original group and cursor coordinates.

Use the [trade chart and signal research guide](reading-trade-charts-and-signals.md) to interpret event sequences, measure the moves that follow, and define replay and paper-test comparisons.

This is the shared findings index and research handoff for all four dates. Start with the [common evidence and research goals](#shared-research-handoff-for-codex-and-claude).

## What to watch across all four dates

Describe the ordered behavior at the touch and link the observations that
show it. Record the prior state, the sequence of changes, what was visible
at the decision close, and what happened afterward. Keep exact prices,
sizes, and ratios with their source coordinates. Use them to reconstruct
the sequence. Any numerical condition in a candidate belongs to that
versioned rule and needs its own evidence before reuse across setups.

- For a thinning touch, track whether the price held as displayed size fell,
  then record recovery at that price, replenishment, or retreat separately.
- For prints, record where they occurred relative to the immediately prior
  quote and how the book changed around them. Attribute depletion to a fill
  or cancel only where the original actions support that link.
- For absorption and entropy, keep the underlying updates and their order.
  Trace fill and display changes by order and price for absorption. For
  entropy, inspect the touch-size observations in both blocks that produced
  the change. Keep similar sequences with different outcomes side by side.

Keep three parts of each observation linked:

- **Behavior.** Record the ordered book updates and prints. Ratios can
  characterize that behavior, such as order-linked fills relative to
  displayed reductions. Keep the numerator, denominator, and observation
  span so the ratio remains interpretable.
- **Measured move.** Keep exact prices and timestamps at the relevant
  starting, decision, and later observations. Report signed percentage
  change from a defined nonzero starting price, with raw changes and ticks
  where available. Retain elapsed time and the quote side or midpoint used
  for the measurement. Compare the distribution of moves at consistent
  horizons across recurring market events and conditions, including flat
  and opposing moves. Use the event and its context to define the pattern.
- **Option contract context.** When evaluating a particular option, map the
  move to that contract's specified underlying reference, strike, call or
  put, expiry, and settlement terms. Keep the underlying's distance to
  strike and time to expiry at the observation. Record the option premium
  separately when it is observed. The same underlying move can have
  different implications for two contracts.

Use timestamps to locate events, establish their order and availability,
and measure elapsed time. Time of day, session phase, and trading weekday
can group comparable observations and show when behavior tends to recur.
Treat recurrence within a time bucket as an association. If the pattern
clusters around a session transition or scheduled release, record the
observable event and compare it with similar cases. Keep the time label
as context for that comparison.

Treat a specific price level as a separate strike-concentration hypothesis
when contemporaneously available options data show a concentration there.
Bind the observation to the matching underlying and expiry, record how the
concentration was measured, and compare behavior near that strike with
comparable levels without that concentration. Keep open interest and traded
volume separate if both are available.

## October 18 observations

The full-session standalone input export covers 583,688 completed groups and
30,739 prints. The candidate counts below come from the previously studied
22,194 consecutive book closes, groups 229201–251394. These counts describe
the window that produced the hypotheses. The full-session touch and print decision pass is below. The remaining
variants and separate scoring admission are pending.

| Candidate family | Ask / long | Bid / short |
| --- | ---: | ---: |
| Falling touch | 1,412 | 1,438 |
| Touch-size entropy decline | 132 | 125 |
| Directional prior-touch print | 615 | 544 |
| Falling touch with entropy decline | 520 | 453 |
| Falling touch with same-group print | 171 | 155 |
| Falling touch with both | 59 | 50 |

Use the frozen candidate definitions and the original per-call ledgers for
rule versions, clocks, dispositions and matched outcomes.
[Candidate register](../../research/kalshi/adaptive_wavepacket_20261108/markets_bridge/tasks/plan.md#candidate-register)
· [Standalone pilot and per-call ledger](../../research/kalshi/adaptive_wavepacket_20261108/markets_bridge/october18_book_entropy_pilot/october18_solo.md)
· [Stack pilot and per-call ledger](../../research/kalshi/adaptive_wavepacket_20261108/markets_bridge/october18_book_entropy_pilot/october18_stack.md)

| Observation ID | What was visible | Research disposition |
| --- | --- | --- |
| NGX3-20231018-G241500 | Bid/short agreement across falling touch, entropy decline, and prior-touch print. Cursor 314654, book line 12300, original print 11556. | One shared observation. Retain the three rule decisions and all stack-arm decisions. |
| NGX3-20231018-G229205 | Directional disagreement at cursor 297873. | Retain the independent side calls and the group context. |
| NGX3-20231018-G229253 | Ambiguous prior-touch print at cursor 297953, including original print 10862. | Retain the prints and an ambiguous disposition. |
| NGX3-20231018-G230690 | The standing bid at 3.154 shrank from two units to one. The displayed bid recovered at that price after the eligible entry. | Counterexample to treating size-one onset as a guaranteed retreat. Original trade 10924. |
| NGX3-20231018-G232857 | The standing bid at 3.154 shrank from four units to one. It retreated to 3.153 after the eligible entry. | Compare with G230690. Both onset groups closed at 3.154/3.155. Original trade 11048. |

The full stack's ask calls had 27 agreements, 11 oppositions and 21 flats at
one second, then 24 agreements and 25 oppositions at five seconds. In the
separate historical spread-crossing diagnostic, 846 of 1,012 size-one onset
scenarios were negative at one second before fees. Keep the research status
of these candidates at `NOT_ENOUGH_INFO`.
[Historical diagnostics and source cases](../../artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1/historical-paper-replay-v1/README.md)

### Why the two one-contract bids diverged

The original tape and reconstructed touch agree on both paths. Cursor
ranges below are inclusive and use the standalone session coordinates.
In the October 18 UTC member, subtract 17,375 to obtain the zero-based
record position. Elapsed times use the receive clocks of completed groups.
[Pinned October 18 tape](https://github.com/DavisAI1974/Markets/blob/1d15dc6f1b5bbb1fabb6389d18e8bedba2b77202/data/nymex_mbo/ng_v0_oct2023/NG_v0_mbo_20231018.dbn.zst)
· [Reconstructed touches and prints](../../research/kalshi/adaptive_wavepacket_20261108/markets_bridge/tasks/root-bounded-replay/retained/october18-standalone-inputs/groups.jsonl.gz)

| Case | Visible by the onset close | What changed afterward |
| --- | --- | --- |
| G230690, recovered | Two contracts traded at the bid. One resting order was removed. The other, order 788701282962, had a one-lot fill followed by a modify that left one lot displayed. The bid went from two displayed contracts to one at 3.154. Cursors 299869–299874. | The surviving order took another one-lot fill and still displayed one. A separate one-lot bid joined at 3.154, restoring displayed size to two. Cursors 299885–299890. Recovery was visible 152.307 ms after onset. |
| G232857, retreated | Order 788701291949 had already taken a one-lot fill and retained one displayed lot at the same price 2.889 ms before the onset close. At onset a three-lot fill removed the other bid order at 3.154, leaving one displayed contract. Cursors 302816–302828. | The final one-lot bid filled and its book update removed it. No replacement was present at 3.154 at the completed group. The bid moved to the already displayed 3.153 level and the ask stayed at 3.155. Cursors 302833–302836. The retreat was visible 14.686 ms after onset. |

The recovery came from an observed same-order refresh followed by a
distinct new bid. The retreat came from execution removing the final
displayed bid. Both surviving orders had shown replenishment before the
outcome, so a prior refresh alone leaves both paths possible. At the
decision, compare the recent pace and sequence of fills, whether the
surviving order was hit in the onset group, and whether other bids had
already joined or withdrawn at the touch or next level. Evaluate those
features on comparable cases across all four dates. The later refresh,
new bid, and final fill explain the outcomes and belong on the outcome
side of that test. The tape leaves remaining hidden quantity and trader
motives unresolved.

The [cohort mechanism audit](why-october18-touch-behaved-differently.md) extends this comparison to all 1,012 saved size-one episodes and maps the related 99-plane and 13-data-point evidence.

## October 18 full-session touch and print decisions

The decision pass read all 583,688 group rows and 30,739 prints from the
existing export. It evaluated 583,595 eligible group closes. It excluded
92 halt groups from signal state and reset state at the one snapshot/reset
boundary. The three-close falling-touch definition uses the three actual
observations. The print rule uses the immediately preceding eligible quote.
The stack uses any print in the same group and takes direction from the
falling-touch rule.

| Versioned candidate | Ask / long | Bid / short |
| --- | ---: | ---: |
| `falling-touch.v1` | 31,399 | 32,680 |
| `prior-touch-print.v1` | 14,001 | 13,828 |
| `falling-touch+print.v1` | 4,175 | 3,947 |

The ledger has 101,998 rows, including 1,968 ambiguous prior-touch print
decisions. Across all three rules, 83,286 distinct groups had at least one
candidate. Both directions fired in 1,189 of those groups. At G229205,
the falling-touch rule fired on both sides and the prior-touch print called
ask/long. Keep both observations. These are rule calls and ambiguity
dispositions. Returns, entropy-dependent variants, and simulator fills are
separate work.

The saved-window comparison reproduced 2,850 falling-touch calls and all
1,240 print decisions, with exact group, cursor, known-by time and direction.
The print comparison also matched original print ordinals and ambiguity.
Those counts come from the comparison input. The full run reads to the end
of its available session.

[Full-session decision ledger](october18-touch-print-decisions.jsonl.gz)
· [Decision runner](../../research/kalshi/adaptive_wavepacket_20261108/markets_bridge/discovery_touch_print.py)
· [Standalone inputs](../../research/kalshi/adaptive_wavepacket_20261108/markets_bridge/tasks/root-bounded-replay/retained/october18-standalone-inputs/groups.jsonl.gz)

## Shared research handoff for Codex and Claude

Use this log as the single Markdown home for findings across all four dates. Add new observations, negative results, counterexamples, unresolved hypotheses, paper outcomes, and links to the supporting rows here. Keep code, source tables, and machine-readable research artifacts in Git with their revisions. Older writeups document the original analyses and methods. Bring their findings forward here and use this file for future updates.

Codex and Claude should study the **same cases and the same pinned inputs independently**. Keep weak, surprising, conflicting, and apparently unrelated ideas in the queue and test them when the inputs support a comparison. Look for positive and inverse relationships, direction changes by setup, interactions, different lead and lag orders, thresholds, nonlinear behavior, and useful absences. A finding from one layer may explain a gap in another. Record both interpretations when they differ and specify the observation that would distinguish them.

For each pattern, ask **how it happened and why that explanation fits**. Rebuild the sequence of adds, fills, cancels, reprices, replenishment, spread and depth changes, trades and later outcomes. Identify which orders or feeds carried the change and which inputs were observable before the decision. Compare cases with the same starting condition and different outcomes, and cases with similar outcomes reached through different mechanisms. Distinguish an observed mechanism, a plausible explanation, an association, and missing evidence. Keep price levels as measurements of movement and retain the contract context when testing strike concentration. Use timestamps to align behavior and group cases. Keep the ratio and its operands together.

The first paper phase asks what works, what fails, under what conditions and why. Keep every version and result so the orchestrator can later evaluate each idea against the conditions and evidence available at the decision. A miss is one observation. A noise judgment needs a defined scope and evidence that survives relevant comparisons. Keep discovery candidates, scoring admission, and executable simulator rules separate. All four dates remain discovery.

### Common starting materials

- **Retained October 18 evidence.** Both reviews start from Git revision `d25fc3f7e59c2a1cb51ec943cd91ff34e176a72a`. Use the group export and the original lifecycle tables together. Join by instrument, candidate ID, source cursor and completed-group receive clock where those fields are available. The archive contains candidate emissions, episode rows, flow substrate, trade-to-path links, and retained layer and external coverage. [Pinned October 18 group export](https://github.com/DavisAI1974/Markets/blob/d25fc3f7e59c2a1cb51ec943cd91ff34e176a72a/research/kalshi/adaptive_wavepacket_20261108/markets_bridge/tasks/root-bounded-replay/retained/october18-standalone-inputs/groups.jsonl.gz) · [Pinned lifecycle tables](https://github.com/DavisAI1974/Markets/tree/d25fc3f7e59c2a1cb51ec943cd91ff34e176a72a/artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1)
- **Raw tape and detector semantics.** The two UTC DBN files span the October 18 trading session and its preceding book context. The reference producer defines group-close binning and the historical peak detector. [Pinned raw tape directory](https://github.com/DavisAI1974/Markets/tree/1d15dc6f1b5bbb1fabb6389d18e8bedba2b77202/data/nymex_mbo/ng_v0_oct2023) · [Pinned producer source](https://github.com/DavisAI1974/Markets/tree/2ebb8ce8ef4834545ad99a4ecdff50c18c5b3134/research/kalshi/frankie_raw_mbo_benchmark)
- **99 planes and 13 data-point inputs.** Begin with the full inventories. Classify relationships as shared input or derived transform, plausible market transmission, context or interaction, alternative measurement, outcome, or unresolved. A `closest` mapping in the crosswalk is a proposed analogy. Test sign, lead or lag, coverage, and what changes after accounting for shared inputs or a common driver. [99-plane registry](../../artifacts/sqlite-triage/20261022/families/descriptive-v1/plane_registry.csv) · [13 data-point bindings](../../artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1/all-13-input-bindings.json) · [External provenance](../../artifacts/sqlite-triage/20261022/families/descriptive-v1/external_point_provenance.csv)

### Where to find the four dates

| October 2023 date | Tape coverage | Shared evidence |
| --- | --- | --- |
| 2 | Partial from the UTC snapshot (600,291 groups to the halt); session = Sunday prefix member `20231001` (cursor 0) + `20231002` (cursor 0); tape sha256 in markets-data `MANIFEST.json` (tape commit `1d15dc6f`, prefix `603c4def`) | ROOT, Native and standalone sealed November 8 (`replay-comparison/README.md`). Group export and touch/print decisions: markets-data `replay-artifacts/20231002/standalone-inputs/groups.jsonl.gz`, `standalone-decisions/decisions.jsonl.gz` (commit `968fa11`); ROOT frames: markets-data archive tier `replay-artifacts/20231002/root-frames/` (S3 publication). Archived Native candidates: `replay-comparison/20231002/candidate-inputs.jsonl.gz` (741 rows, 741 live recognitions) with `research-atlas-v2/`, `flow-book-discovery-v1/` and `summary.json`. First-observed family index: markets-data `7b50d634` `family-replication/run-42566535537-1/family-20231002/chronological-instance-index.csv` (795 families). Claude per-event rows: `claude-code/*-oct02-*` (exhaustion clock, runway duration and clock v2, frozen A classifier, A-state direction, beyond-direction prebirth, next-burst forecast, stack direction sources, first-family four arm, dipole post-recognition, size-one episodes, orders and tape, chain play filter, divergent pairs; `claude-october-discovery-20261108.md` sections 15 to 25); 99-layer pin ledgers markets-data `claude-code-pins/ninety-nine-pins-oct02.jsonl.gz` (`5c94c64`) and `ninety-nine-pins-tier1-oct02.jsonl.gz` (`67b7a6a`); case rows `claude-code-cases/*-oct02*` (`ea137b6`). Tier 2, Tier 3 and dipole cohort tables, detector ledgers and the four-day side-by-side: `claude-pass-3day/tables/20231002/`, `claude-pass/tables/20231002/`, `claude-pass-3day/tables/dipole/20231002/`, `claude-pass-3day/crossday/` (branch `claude/three-day-dipole-20261108`). Discovery date, partial. |
| 3 | Full session (653,912 groups); session = evening member `20231002` (cursor -808453) + `20231003` (cursor 4889); tape sha256 in markets-data `MANIFEST.json` (tape commit `1d15dc6f`) | ROOT, Native and standalone sealed November 8 (`replay-comparison/README.md`). Group export and touch/print decisions: markets-data `replay-artifacts/20231003/standalone-inputs/groups.jsonl.gz`, `standalone-decisions/decisions.jsonl.gz` (commit `968fa11`); ROOT frames: markets-data archive tier `replay-artifacts/20231003/root-frames/` (S3 publication). Archived Native candidates: `replay-comparison/20231003/candidate-inputs.jsonl.gz` (833 rows: 832 live recognitions and one finalization-only candidate `dip-19633-1696366763`, kept as unavailable) with `research-atlas-v2/`, `flow-book-discovery-v1/` and `summary.json`. First-observed family index: markets-data `7b50d634` `family-replication/run-42566535537-1/family-20231003/chronological-instance-index.csv` (848 families). Claude per-event rows: `claude-code/*-oct03-*` (same set as October 2; `claude-october-discovery-20261108.md` sections 15 to 25); 99-layer pin ledgers markets-data `claude-code-pins/ninety-nine-pins-oct03.jsonl.gz` (`5c94c64`) and `ninety-nine-pins-tier1-oct03.jsonl.gz` (`67b7a6a`); case rows `claude-code-cases/*-oct03*` (`ea137b6`). Tier 2, Tier 3 and dipole cohort tables, detector ledgers and the four-day side-by-side: `claude-pass-3day/tables/20231003/`, `claude-pass/tables/20231003/`, `claude-pass-3day/tables/dipole/20231003/`, `claude-pass-3day/crossday/` (branch `claude/three-day-dipole-20261108`). Discovery date, full session. |
| 17 | Partial from the UTC snapshot (635,170 groups to the halt); session = evening member `20231016` (cursor 0, prefix) + `20231017` (cursor 0); tape sha256 in markets-data `MANIFEST.json` (tape commit `1d15dc6f`, prefix `603c4def`) | ROOT, Native and standalone sealed November 8 (`replay-comparison/README.md`). Group export and touch/print decisions: markets-data `replay-artifacts/20231017/standalone-inputs/groups.jsonl.gz`, `standalone-decisions/decisions.jsonl.gz` (commit `968fa11`); ROOT frames: markets-data archive tier `replay-artifacts/20231017/root-frames/` (S3 publication). Archived Native candidates: `replay-comparison/20231017/candidate-inputs.jsonl.gz` (741 rows: 740 live recognitions and one finalization-only candidate `dip-19647-1697576378`, kept as unavailable) with `research-atlas-v2/`, `flow-book-discovery-v1/` and `summary.json`. First-observed family index: markets-data `7b50d634` `family-replication/run-42566535537-1/family-20231017/chronological-instance-index.csv` (824 rows, 823 families with an earlier group). Claude per-event rows: `claude-code/*-oct17-*` (same set as October 2 plus the no-prefix pass in `no-prefix-oct17/`; `claude-october-discovery-20261108.md` sections 14 to 26, index of the October 17 artifacts in 14.6); 99-layer pin ledgers markets-data `claude-code-pins/ninety-nine-pins-oct17.jsonl.gz` (`5c94c64`) and `ninety-nine-pins-tier1-oct17.jsonl.gz`; case rows `claude-code-cases/*-oct17*` (`ea137b6`). Tier 1, Tier 2, Tier 3 and dipole cohort tables, detector ledgers and the four-day side-by-side: `claude-pass-3day/tables/20231017/`, `claude-pass/tables/20231017/`, `claude-pass-3day/tables/dipole/20231017/`, `claude-pass-3day/crossday/` (branch `claude/three-day-dipole-20261108`). Discovery date, partial. |
| 18 | Full session | Group export, touch and print decisions, historical lifecycle tables, and the candidate input reconstruction linked here. |

Publish each date's compact standalone exports, comparison tables suitable for Git, and research updates on `codex/ng-shadow-discovery-20261108` as they become available. Keep a link or exact location here for bulk tables retained under `/opt/frankie-box/replay-control` in the original RunPod trade-date folder. Record coverage, stage, and revision with the path. Update each date independently. Read the existing tables directly and carry both clocks and original source coordinates into comparisons. [RunPod execution record](runpod/discovery-execution-20261108.md)

## October 18 candidate input reconstruction

**NGX3-20231018-DIPOLE-INPUTS.** The reconstruction rebuilt the book from the raw MBO feed, aligned every saved group close and all 30,739 print records, and reproduced the original trade classification and rolling flow operands at all 4,849 retained active-session seconds. It matched the magnitude, direction, baseline, threshold, finite observation count and threshold history span for all 863 saved recognitions. Of those, 42 have a separately retained candidate emission and matching later operands. The others use the candidate operands carried by the later episode records as historical comparison evidence. The reconstruction reads the separate recognition row for its actual clock and cursor. The 863 recognition IDs include 862 paths in the supporting-trade overlap table.

The saved threshold, prominence and window parameters describe this detector version. The candidate ledger preserves the reconstructed inputs at birth, immediately before birth, and at the last closed second at recognition. The study reconstructs saved selections and does not inventory rejected peaks or estimate their outcome rates. [Reconstruction script](reconstruct_october18_candidate_inputs.py) · [Counts and cross-tabs](october18-candidate-input-summary.json) · [Per-candidate inputs](october18-candidate-inputs.jsonl.gz)

| Clock used for the same 17,845 historical overlaps | Links | Distinct prints |
| --- | ---: | ---: |
| Any temporal overlap with a supporting path | 17,845 | 14,699 |
| Nominal candidate availability second before the print | 6,639 | 5,426 |
| Actual recognition close before the print and available by its previous eligible group close | 6,304 | 5,117 |
| Recognition emitted at the print group's close | 102 | 102 |
| Full path available by the previous eligible group close | 0 | 0 |

The nominal bin overstated the strict-prior overlap by 335 links. Median delay from bin start to the emission close was 2.407 seconds. The largest delay was 87.368 seconds. Seconds become complete when a later group advances the clock, so quiet gaps can delay actual recognition. An overlap says when a candidate was visible relative to a print. To estimate predictive value, compare all eligible opportunities, including groups with no subsequent print.

### What the dipole tracked at a high level

Think of the dipole as a way to follow **how a burst of directional trade pressure relates to the previous detected burst, what happens to that pressure next, and how liquidity and the quote respond along the way**. The detector starts from a peak in normalized 20-second signed flow and recognizes it at a later completed group. The episode's `SAME` or `FLIP` label compares its birth direction with the previous accepted candidate in the same continuity segment. On October 18, 472 repeated the predecessor's direction, 390 flipped, and one had no predecessor. These labels describe the relation between candidate births. The separate recognition comparison asks whether flow still had its own birth direction by the time the episode became visible.

Once open, the path follows rolling signed lots, bid and ask depth, order and level counts, and midpoint through persistence, reversal or censoring. Reversal here is a sequence of opposite **flow** readings under the archived detector definition. A quote can move with flow, move against it, or stay flat. Fresh trades, old trades aging out of the rolling window, cancellations and new limit orders can each change a different part of that picture. When comparing stages, preserve the actual book observation clock. In the archived 54,042-stage audit, aligning the book strictly as of the stage's labeled time changed the recorded price coupling in 671 of 862 paths, with 117 switching directly between positive and negative. Keep the producer's clock for reconstruction and an explicit as-of book for claims about what was observable at a given time. [Pinned episode tracker](https://github.com/DavisAI1974/Markets/blob/2ebb8ce8ef4834545ad99a4ecdff50c18c5b3134/research/kalshi/frankie_raw_mbo_benchmark/native_candidate_adapter.py) · [Stage clock and coupling audit](../../artifacts/sqlite-triage/20261022/families/dipole-book-clock-audit-v1/coupling_comparisons.csv)

**One instance and what it illustrates.** In DIP-1697625921, a buy-heavy birth was followed by a sell-heavy rolling window at recognition. The midpoint nevertheless finished above its prebirth level, with an improved bid visible in the intervening orders. The broader question is where aggressive flow moves the quote and where passive book changes lead, absorb, or offset it. Keep the aggregate and the contrasting examples together, including the 56 of 217 late-flow flips where the midpoint still moved in the birth direction. The individual orders explain one observed path. The cohort tells us how often to look for that kind of explanation, and the other cases may have different mechanisms.

For future entries, pair each case with the behavior it illustrates, the cohort and denominator, alternative or inverse paths, and what should transfer across prices and dates. Start broad with persistence, fading, reversal, and the book response. Narrow to a specific threshold, exact level, or order signature when the evidence separates it from nearby alternatives.


### Flow, quote response, and order-level explanations

| Rolling flow by actual recognition | Cases | Midpoint in the birth direction | Midpoint opposite | Midpoint flat |
| --- | ---: | ---: | ---: | ---: |
| Same direction as birth | 275 | 155 | 65 | 55 |
| Opposite direction | 217 | 56 | 127 | 34 |
| Balanced with classified volume | 26 | 12 | 13 | 1 |
| Undefined with zero classified volume | 345 | 159 | 73 | 113 |

Midpoint change runs from the last group before the birth second through the recognition close. The table describes behavior observed by recognition. Of 863 birth windows, 332 held only one classified lot and 548 had no fresh print in the birth second itself. A saturated ratio can come from a single earlier lot. Of 345 undefined windows at recognition, 342 had no print in the latest 20 completed seconds. Three had prints with zero classified volume. A quiet window, balanced classified flow, and opposing new flow describe different paths.

- **NGX3-20231018-DIP-1697581215 and DIP-1697583021.** Both births had a buy ratio of 1 from one lot and no fresh print in the birth second. Both rolling windows were empty by recognition. The first midpoint returned to its starting level after eight intervening ask price changes. In the second, a later three-lot buy filled three separate ask orders at 3.067. The matching book reductions cleared that level and exposed 3.068, while the bid held at 3.066. That trade occurred between birth and recognition and had aged out of the latest window. Compare cursors 3266–3411 with 7611–7726, including the trade, fills and linked reductions at 7683–7690.
- **NGX3-20231018-DIP-1697625921.** The birth window had one classified buy lot. By recognition the latest window had 14 buy and 39 sell lots, while the midpoint was above the prebirth midpoint. A new one-lot bid entered above the prior bid at cursor 141114 and that price was still the best bid at recognition. A new three-lot offer entered at 3.087 at cursor 141146, tightening the offer from 3.088 just before recognition. These book changes explain how the midpoint could finish higher over the interval despite sell-dominant late flow. Compare with DIP-1697607905, where 4 buy and 25 sell lots were present in the later window and both sides of the book ended below their prebirth prices.
- **Plane 47 and quote-source comparison.** On this date, classifying against the action-time midpoint and against the prior eligible close midpoint gave the same label for all 30,739 prints. Wire side still disagreed on 174 prints where both methods gave a direction and was unspecified on 2,408 prints classified directionally by the midpoint. All 1,052 midpoint prints had a directional wire side. Keep these measures as separate hypotheses. Their agreement and disagreement can be tested by quote update order, spread and execution location.

### Earlier October 18 lifecycle findings carried forward

- **Quote mechanism.** Across 1,012 size-one episodes, 548 recovered at the original price, 461 retreated and 3 improved. Most recoveries began with a new order at that price (534 of 548). Retreats included 272 fill-linked last reductions, 187 cancellations with no matched fill, and 2 reprices away. The contrast between fills and other reductions at onset weakened among episodes still open at the assumed paper entry. Distinguish the end mechanism from a predictor observable at entry. [Original order-lineage analysis](why-october18-touch-behaved-differently.md)
- **Prebirth and next print.** With a print already present in the decision group, the next-group print rate was 19.91% with falling touch and 16.00% without. Without a current print, the same comparison was 4.35% and 4.48%. The cohorts share a date and activity clusters. Compare within similar spread, activity and clock strata before attributing the difference to touch thinning. [Original prebirth analysis](october18-prebirth-and-exhaustion-log.md)
- **Exhaustion.** Widening gaps between all prior print groups went with fewer ask retreats and more bid retreats. When the history was restricted to known aggressor flow pressing the same side at the touch price, both gaps shrank substantially. Ask retreat rates were 46.7% versus 48.7%, and bid rates were 43.5% in both groups. Keep passive withdrawal, opposite flow, weakening price response and recovery of displayed liquidity as separate mechanisms. [Original exhaustion analysis](october18-prebirth-and-exhaustion-log.md)
- **External timing.** The original 1,012-episode sample contained no retained non-curve declared publication clocks during the onset-to-first-end intervals. A traded-curve update fell in 77 intervals, including 59 retreats, 17 recoveries, and 1 improvement. Curve legs may share activity with the tape. Check independent leg timing and compare with similarly active intervals before assigning an external explanation. [Original external comparison](why-october18-touch-behaved-differently.md#which-of-the-13-data-points-might-explain-context)

### Flow stacked with displayed depth

Across the same 863 recognized candidates, compare the sign of displayed bid size minus ask size at the last close before the birth second with the direction of birth-window flow. When they aligned, the midpoint moved in the birth direction by recognition in **222 of 416 cases (53.4%)**. When they opposed, it did so in **124 of 343 (36.2%)**. The same ordering appeared with one classified lot (85/161 aligned versus 35/125 opposed) and with multiple lots (137/255 versus 89/218). Equal displayed depth gave 36/104. Flat and opposite moves stay in each denominator. This is a retrospective comparison of selected episodes ending at recognition. Test the book and flow sequence against all eligible opportunities and separate continuation from passive liquidity changes before treating this as a forecast.

### What the first SQLite runs add

- **The first clock reconstruction gives us the join backbone.** It linked all 749 first-observed family starts, 583,688 groups, 771,787 second-set records, 30,739 trades, the 99 registry roles and the 13 inputs across 20 tables. It preserved original offsets and clocks. A first-observed family is a separate anchor from the birth of an individual order, dipole, or trade. Reuse those keys and strict pre-event cutoffs to link cases with different anchors. [First combined clock result](../../artifacts/sqlite-triage/20261022/families/family-clock-results.txt)
- **The original flow stack already has contrast cases.** The saved screen found 50 of 749 first-observed families with buy-heavy 60-second flow, sell-heavy 5- and 1-second flow, and larger total displayed bid depth. Case 375 moved down 0.0055 in the first second and 0.0125 by five minutes. Case 391 moved down 0.0015 in the first second and was up 0.0070 by five minutes. The cases overlap the same broader market episode. The similar stack with different paths gives us a way to look for differences in fixed-price bid removal, queue age, refills and nearby liquidity. Compare all 50 with their inverse stack and same-activity controls. [Original 375 and 391 comparison](../../artifacts/sqlite-triage/20261022/families/instance-market-review-20261023/instance-375-review.md) · [50 original matches](../../artifacts/sqlite-triage/20261022/families/instance-market-review-20261023/candidate-flow-transition-instances.csv)
- **Conditioning can change the sign of an observed interaction.** The early partial-input review found sufficient support for 101 of 626 selected pair contrasts. For pair 18, recent change in total bid ladder depth and change in native near-depth imbalance had a negative pooled interaction contrast for one-second absolute midpoint change and a positive contrast in the strict pre-start subset. Preserve both strata, the four corner counts and overlapping context IDs. No exact supported pair repeated across multiple folds in that review. The expanded run likewise found only 43 of 629 saved contrasts with at least ten observations in every corner and no repeated support-qualified exact pair across folds. Its supported candidates included queue age with deeper queue age, and book size or queue concentration with curve-trade activity. These are distinct hypotheses about where to look in the tape. [Early pair and contradiction register](../../artifacts/sqlite-triage/20261022/families/layer-review-v1/contradiction_research_registry.csv) · [Expanded interaction support](../../artifacts/sqlite-triage/20261022/families/final-model-analysis-20261023/full-model-perspectives.md#deep-structure-and-interactions-the-expanded-book-changes-what-we-can-inspect)
- **The combination may explain size and path differently from direction.** In the expanded refits, removing book, depth and queue increased 20-second absolute-move error by 1.29%, while removing flow and structure increased it by 0.48%. Removing book, depth and queue reduced five-minute signed-move error by 4.44%. Each effect had the same direction in the three folds of this one day. These are separate block removals. A joint four-arm comparison can ask what flow and book each add and whether their combination changes the result. The expanded run had 125 of 126 shallow or deeper tree fits use fields beyond depth rank 10. Scope, source overlap, and unresolved semantic coverage still apply. [Expanded model and removal results](../../artifacts/sqlite-triage/20261022/families/final-model-analysis-20261023/full-model-perspectives.md)
- **Dipole relationships need several definitions.** The original audit reproduced 69 native classroom claims under its archived definition and logged 225 overlapping conflict flags, including 69 endpoint-versus-step differences and 60 sign changes across chronological quarters. Check positive and inverse relationships at each lifecycle stage using both endpoint and adjacent-step views. Keep float precision, missing-group bridges, paired observations and source clocks attached. The original review retained 441 external claims pending separate reconstruction. [Native claim comparison](../../artifacts/sqlite-triage/20261022/families/dipole-audit-v1/native_classroom_claim_checks.csv) · [Dipole contradiction register](../../artifacts/sqlite-triage/20261022/families/dipole-audit-v1/dipole_contradiction_research_registry.csv)

### How to build the knowledge base from these cases

Use an append-only set of case and hypothesis entries in this log with machine-readable Git tables for many rows. Start from the existing SQLite keys and source coordinates. A case can link to several family, dipole, quote and trade events. A hypothesis can link to supporting, opposing, complementary, untested, and unavailable cases. Preserve shared sources so repeated descriptions of the same orders or publications count once when comparing evidence.

For each stack, record the anchor and as-of boundary, each layer and its raw operands, the sequence of observable changes, the measured outcome and horizon, the mechanism and plausible alternatives, and the comparison that could tell them apart. Record separate outcomes for arrival, direction, move size, intrahorizon path and paper execution. Keep scope, missingness, support in each comparison cell and the identity of overlapping cases. Give each interpretation and candidate version a stable ID so the orchestrator can retrieve it by conditions and the two reviewers can disagree about the same case without losing either explanation.

For the next flow-and-liquidity comparison use four arms on the same eligible opportunities, a baseline, flow alone, book behavior alone, and both. Compare agreement and opposition, then add candidate phase, queue and external context one at a time. Track where the extra layer changes the interpretation and where it simply repeats information already present. Start by tracing the 375 and 391 contrast and the opposing dipole examples back to the original order messages.


### Market psychology as an explanation layer

Record behavioral explanations alongside order flow, book structure, external information, and mechanical trading constraints. Start with a condition, a possible human response, the observable sequence it could produce, and a competing explanation. A useful layer can describe where a pattern is stronger or weaker even if the underlying feeling remains unobserved. Assign its weight only after measuring what it adds in context.

| Hypothesis | How it could appear in NG and what to compare |
| --- | --- |
| **Urgency and attention.** A salient release, price move, or uncertainty can focus attention and create a rush to act. Barber and Odean found attention-linked buying in retail equity accounts. | Use genuinely available storage surprises or forecast revisions as event anchors. Compare changes in print arrival, aggressive share, depth withdrawal, and time to replenish with similarly active non-release intervals and both surprise directions. Shared fundamental information and automated reactions can generate the same clustering. [Barber and Odean](https://doi.org/10.1093/RFS/HHM079) |
| **Loss sensitivity, regret, and attempts to break even.** Reference-dependent risk taking can differ in gains and losses. Odean studied asymmetric realization in equity accounts. Coval and Shumway observed more afternoon risk taking after morning losses among CBOT proprietary traders. | Test asymmetry after comparable directional moves, including delayed exits, renewed pressure, and sharp reversals. Position and cost-basis data would distinguish break-even behavior from ordinary rebalancing. The session open or a prior extreme can organize the comparison while individual entry prices remain unknown. [Kahneman and Tversky](https://web.mit.edu/curhan/www/docs/Articles/15341_Readings/Behavioral_Decision_Theory/Kahneman_Tversky_1979_Prospect_theory.pdf) · [Odean](https://doi.org/10.1111/0022-1082.00072) · [Coval and Shumway](https://doi.org/10.1111/j.1540-6261.2005.00723.x) |
| **Social imitation, fear of missing a move, and reputational incentives.** Participants may follow earlier activity because they infer information from it or face incentives to act like peers. | Look for sequential same-side bursts, widening participation where evidence exists, and follow-through after an initial impulse. Compare with common reactions to an external event, same-source order slicing, and arbitrage across maturities. Order IDs identify orders. Participant-level evidence would be needed to distinguish copying from common incentives. [Scharfstein and Stein](https://stein.scholars.harvard.edu/publications/herd-behavior-and-investment) |
| **Confidence, anchoring, and expectation revision.** Persistent conviction can produce continuation while belief correction can produce reversal. A remembered price or a known contract reference can organize orders when there is evidence that traders or execution rules use it. | Compare the order of forecast revision, response, renewed pressure, loss of price response, and reversal. Compare crossed levels with nearby matched levels and require independent evidence of clustered orders or positions before assigning importance to an exact price. A delivery-month move consistent with a new demand outlook is a competing mechanism. [Daniel, Hirshleifer and Subrahmanyam](https://doi.org/10.1111/0022-1082.00077) |
| **Protective stops, liquidation, and funding pressure.** Both discretion and mechanical constraints can create directional feedback. Stop execution, depleted depth, and risk limits can amplify the original move. | Compare fast depth loss through multiple levels, continued prints, curve and expiry context, and whether liquidity returns after pressure eases. Keep stop, liquidation, margin, and quote withdrawal explanations separate. Stop flags, position records, margin data or contemporaneous rule changes would help identify the source. [Osler](https://www.newyorkfed.org/research/staff_reports/sr150.html) · [Brunnermeier and Pedersen](https://doi.org/10.1093/RFS/HHN098) |
| **Uncertainty, hedging, and the return of liquidity.** A producer, consumer, market maker, and short-horizon speculator can respond differently to the same weather, storage, or curve information. | Test whether spread, cancellations, replenishment, intermonth price response, and flow direction differ around known information or roll events. Distinguish physical exposure and inventory control from caution, relief, or overreaction. Storage and weather have direct supply and demand channels in this market. [EIA natural gas fundamentals](https://www.eia.gov/energyexplained/natural-gas/factors-affecting-natural-gas-prices.php) · [EIA natural gas futures](https://www.eia.gov/todayinenergy/detail.php?id=62605) |

Log the October 18 examples first with observed order actions and timing. The three-lot ask sweep and improved bid are evidence of different ways to move a quote. Add an urgency or attention interpretation only with an independently observable context and a comparison that can challenge it. The candidate ledger records the behaviors. Account P&L, private intent, undisplayed stop instructions, and complete participant identity are unavailable there. Keep those fields unknown. Test any behavior proxy against the same flow and liquidity baseline before asking the orchestrator to use it.


### Open relationship and mechanism studies

| Study | Test and competing explanations |
| --- | --- |
| Prebirth and candidate selection | Separate birth, recognition, active phase and completion. Compare accepted peaks with time- and activity-matched unselected peaks, eligible groups without prints, and repeat prints after a burst. Test whether early queue loss, new orders, ratios with adequate denominators, and quote response add information beyond recent prints and spread. Count candidates and opportunities separately. |
| Signed flow, depth and liquidity | Connect plane 47 to the raw trades, fills, order identity, queue and depletion or recovery planes. Test same-direction transmission, inverse response from replenishment or withdrawal, and no response. Follow fixed-price orders and distinguish changes at the standing level from new prices becoming best. Match on starting depth, spread, order count and classified volume. |
| Dipole lifecycle and exhaustion | Compare same, opposed and undefined flow across lifecycle stages with raw pressure at the touch, fill-linked depth changes, repeated adds, and midpoint movement per unit of flow. Seek pairs with equal ratios and different lot counts, and equal flows with different quote responses. Use completion labels for outcomes and keep the predictor clocks separate. |
| Positioning and roll | Points 1, 3, and 4 reuse a NYMEX positioning history. Point 8 covers ICE LD1. Test shared versus independent regime information, including inverse responses during unwind. Compare point 6 with observed expiry and delivery-month context. One carried value cannot identify an intraday effect. |
| Weather, power and stocks | Test forecast HDD and model disagreement (2 and 9), realized weather (10), wind and estimated gas burn (5 and 7), and carry-in stocks and release surprises (11 and 12). Separate forecast revisions, shared source inputs, publication surprises and baseline context. Keep demand and power channels open in both directions and compare event-time paths only with defensible first-available vintages. |
| Curve and options | For point 13, check each delivery month's trade and settlement clocks and whether the front leg reuses the same tape. Compare spreads, lead-lag and reversals after removing that mechanical overlap. Strike concentration needs separate as-of option evidence for the same underlying and expiry. |
| Cross-layer combinations | Test intra-plane, inter-plane and plane-to-data-point pairings, then combinations with a plausible transmission path. Include timing shifts, inverse signs, availability gaps, nonlinear responses and condition-specific effects. Keep the number of comparisons, coverage, repeated source dependencies, session blocks and missing data visible. Use future discovery dates to seek contrary evidence and new conditions. |


## Paper discovery register

Keep every idea and every result in the register. Use the paper phase to
learn how behavior, timing, market conditions and execution interact.

| Keep | Record |
| --- | --- |
| Discovery, finding, signal or strategy hypothesis | Stable ID and version, original observation and source links, the behavior it describes, and the conditions where it might apply |
| Each historical or paper instance | Date, contract, setup, exact decision and available evidence, later market path, simulator action and fill, miss or rejection |
| Interpretation | What worked, what failed, why the evidence supports that explanation, rival explanations, and what still needs checking |
| Orchestrator decision | Which candidates it considered, which present conditions matched, unavailable inputs, and the reason it selected, deferred or skipped a test |
| Noise judgment | Defined scope, comparison and controls, evidence supporting the judgment, and the preserved original history |

Distinguish candidate status from an individual outcome. Adverse, flat,
ambiguous and execution-limited tests stay attached to the same version.
Compare the idea again when its conditions recur. A noise finding applies
to the scope supported by the evidence and stays in the log. This register
feeds the orchestrator's contextual selection. The paper-test queue
records the agreed trigger, side, order type, size, exit and environment
before a simulator test.

## Paper-test queue

The logged signals are historical discovery candidates. The Git evidence
shows no platform entry or approved simulator ticket for these candidates.
`direction.book_contrarian` is a separate provisional hypothesis. It uses
resting-book imbalance when flow is flat or ambiguous. The needed inputs were
unavailable for its original trigger in this replay, so it remains unscored.
[Original hypothesis and contrary audit](../../artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1/local-liquidity-v1/README.md)

After the four dates run through the standalone component, record a candidate
as a paper rule when its version, exact trigger, side, order type, size,
exit and simulator environment are agreed. Log any later platform entry
and simulator observation separately from the historical discovery row.
