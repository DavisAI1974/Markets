# A-clean REAL_TIME_FRANKIE Interim Positive Report

## Retrospective interim provenance

This is a retrospective interim REAL_TIME_FRANKIE analysis produced after runtime completion. Evidence access occurred through read-only inspection of the intact A-clean native raw-MBO event-group ledger at `/workspace/scratch/da00127ac123/a-clean-runtime-33161766927`. The sole carry-forward findings artifact was `ACLEAN_RT_NATIVE_MBO_POSITIVE_DERIVED_FINDINGS_20260828.md`; every structure retained below was independently reproduced from `native-evidence-groups.jsonl.gz` and `source_manifest.json`.

The scientific unit is the distinct F_LAST-closed event group. Its causal availability clock is `ts_recv_ns`. Source/event time, first-component receive time, and group-close receive/availability time remain separate. Counts remain separate by source day, action family, and side sequence.

## Native-ledger verification receipt

| Item | Exact receipt |
|---|---|
| Ledger file SHA-256 | `b7399305906936fb89c5028fe2f32e291aefc2f9be14e421e6afc14b27acd038` |
| Source-manifest file SHA-256 | `24a47eb1631a17ab391eb61ad73051f694b4c564dddec4050518e730efe40767` |
| Canonical embedded manifest hash | `a98a454ef5a88d6f3ee1213370d6df530ab2946ec9cde47171b0d7aa19f4e2ba` |
| October 4 native source SHA-256 | `8ed47cc0a68cf40cae9fde45e158142978076e60d3f9fc7cf940196babfddc0a` |
| October 5 native source SHA-256 | `a4a12f9578da762412884e7f559a123361eaa3a153bec0db59dfb3ba6224a874` |

The independent pass sequentially decompressed all 4,256,603 JSONL event-group envelopes and parsed every held-out October 4–5 group. It recomputed group and raw-record census totals; action strings; side strings; single-price predicates over priced actions; trade/fill size equalities; trade-size partitions; fill-to-cancel and fill-to-modify order-ID continuation; F_LAST closure; native/full provenance flags; source hashes; and every exemplar clock and action field cited below. The 3,094,296 held-out groups all carried `V4_NATIVE_FULL`, `raw_actions_stored_exactly_once=true`, `seconds_collapse_used=false`, and an F_LAST close whose group `ts_recv_ns` equaled the final action receive time.

| Held-out source day | Native records | F_LAST-closed groups | Global group-index span | Closed-group receive span |
|---|---:|---:|---:|---|
| 2021-10-04 | 1,994,358 | 1,506,255 | 1,162,307–2,668,561 | `2021-10-04T00:00:00.000000000Z`–`2021-10-04T23:59:59.955312214Z` |
| 2021-10-05 | 2,111,930 | 1,588,041 | 2,668,562–4,256,602 | `2021-10-05T00:00:00.000000000Z`–`2021-10-05T23:59:59.954928144Z` |

## Positive distinct group families

### Single-fill trade lifecycles

| Family and mechanical structure | 2021-10-04 | 2021-10-05 | Positive order-behavior content |
|---|---:|---:|---|
| `TFCN`: trade, fill, same-ID cancel, neutral F_LAST | 38,510 | 39,766 | Every fill-action order ID reappears in the subsequent cancel. The stream therefore carries an explicit post-fill cancellation lifecycle inside one causally closed group. |
| `TFM`: trade, fill, same-ID modify with F_LAST on modify | 6,173 | 6,605 | Every filled order ID continues into a modification at the same price, directly linking execution to residual-order resizing. |
| `TFMN`: trade, fill, same-ID modify, neutral F_LAST | 1,910 | 1,833 | Every filled order ID continues into a modification, then receives a separate neutral closure message. |

For `TFCN`, 38,490/38,510 October 4 groups and 39,752/39,766 October 5 groups keep every priced action at one price; trade size equals fill size in 38,107 and 39,389 groups; trade size is one in 35,364 and 36,388 groups. Its exact side partitions are:

| Side sequence | Mechanical side structure | 2021-10-04 | 2021-10-05 |
|---|---|---:|---:|
| `ABBN` | trade ask; fill/cancel bid; neutral close | 17,750 | 18,344 |
| `BAAN` | trade bid; fill/cancel ask; neutral close | 17,197 | 18,233 |
| `NNBN` | neutral trade/fill; cancel bid; neutral close | 2,058 | 1,815 |
| `NNAN` | neutral trade/fill; cancel ask; neutral close | 1,485 | 1,360 |
| `BBBN` | trade/fill/cancel bid; neutral close | 12 | 7 |
| `AAAN` | trade/fill/cancel ask; neutral close | 8 | 7 |

For `TFM`, every group is single-price; trade size equals fill size in 6,168/6,173 and 6,603/6,605 groups; trade size is one in 4,583 and 4,897 groups. The complete side partition is `BAA` 2,878/2,707, `ABB` 2,567/3,310, `NNB` 413/304, and `NNA` 315/284 for October 4/5. For `TFMN`, every group is single-price; trade size equals fill size in 1,901/1,910 and 1,824/1,833 groups. Its complete October 4/5 side partition is `BAAN` 908/763, `ABBN` 669/803, `NNBN` 180/145, `NNAN` 149/114, and `BBBN` 4/8.

Together these families positively expose two exact post-fill branches on the same order identity: cancellation (`C`) and residual-size modification (`M`). The neutral `N` variant makes causal completion a distinct received action.

### Multi-fill and repeated trade/fill cascades

| Family and mechanical structure | 2021-10-04 | 2021-10-05 | Positive order-behavior content |
|---|---:|---:|---|
| `TFFCCN`: one trade, two fills, two cancels, neutral close | 7,037 | 7,522 | Every fill-action ID appears among the later cancel IDs: 14,074/14,074 and 15,044/15,044 fill actions. This preserves multi-order execution and later order-identity disposition in one group. |
| `TFTFCCN`: two ordered trade/fill pairs, two cancels, neutral close | 819 | 832 | Every fill-action ID appears among the later cancel IDs: 1,638/1,638 and 1,664/1,664 fill actions. The group retains repeated execution order before post-fill cancellation. |

For `TFFCCN`, every priced action is at one price in 6,554 and 7,132 groups; trade size equals combined fill size in 6,361 and 6,955; trade size is two in 5,464 and 5,986. Its principal mirrored side structures are `BAAAAN` 3,030/3,226 and `ABBBBN` 3,022/3,403 by October 4/5.

For `TFTFCCN`, every priced action is at one price in 142 and 162 groups; combined trade size equals combined fill size in 776 and 804; combined trade size is two in 701 and 724. Its principal mirrored side structures are `BABAAAN` 358/340 and `ABABBBN` 352/349 by October 4/5.

These families positively preserve cascade multiplicity. `TFFCCN` distinguishes a trade split across two fills; `TFTFCCN` distinguishes two received `T→F` pairs. Their raw ordering, individual sizes, prices, sides, and order IDs provide direct inputs for causal queue-consumption and exhaustion-runway reconstruction.

### Trade-only close and elementary queue mutations

| Family | 2021-10-04 | 2021-10-05 | Positive order-behavior content |
|---|---:|---:|---|
| `TN` | 1,901 | 2,204 | A trade action followed by a distinct neutral F_LAST close; bid-side counts are 1,032/1,148 and ask-side counts are 869/1,056. |
| `A` | 590,918 | 615,022 | Atomic resting-order addition. |
| `AN` | 97,879 | 105,958 | Addition followed by a separate neutral close. |
| `C` | 516,259 | 534,916 | Atomic resting-order cancellation. |
| `CN` | 66,469 | 71,149 | Cancellation followed by a separate neutral close. |
| `M` | 145,701 | 166,389 | Atomic resting-order size modification. |
| `MN` | 12,315 | 13,980 | Modification followed by a separate neutral close. |

These primitives supply the causal queue-mutation vocabulary around the trade-linked families. The paired `N` variants also encode the received completion step explicitly, so family availability can be anchored to F_LAST rather than to the first component.

### Session-boundary withdrawal families

| Group | Event time | First receive | F_LAST availability | Ordered structure | Bid/ask cancels | Cancel-size sum |
|---:|---|---|---|---|---:|---:|
| 2,654,677 | `2021-10-04T21:00:00.078569755Z` | `2021-10-04T21:00:00.235943540Z` | `2021-10-04T21:00:00.237256020Z` | 430 `C`, then `N` | 219 / 211 | 796 |
| 4,237,483 | `2021-10-05T21:00:00.078400519Z` | `2021-10-05T21:00:00.226788647Z` | `2021-10-05T21:00:00.228110022Z` | 581 `C`, then `N` | 371 / 210 | 1,179 |

The two exact 21:00 UTC groups positively identify a repeatable session-state transition: hundreds of resting order identities across both sides and many prices are withdrawn inside one F_LAST-closed causal group. They provide deterministic session segmentation and queue-reset anchors for the corrected rerun.

## Exact exemplars and causal timings

| Family | Group | Event/source time | First receive | F_LAST availability | Within-group receive span |
|---|---:|---|---|---|---:|
| `TFCN` | 1,162,308 | `2021-10-04T00:00:00.003850233Z` | `2021-10-04T00:00:00.005907870Z` | `2021-10-04T00:00:00.006000667Z` | 92,797 ns |
| `TFFCCN` | 1,162,432 | `2021-10-04T00:00:51.123013557Z` | `2021-10-04T00:00:51.123677238Z` | `2021-10-04T00:00:51.123730622Z` | 53,384 ns |
| `TFTFCCN` | 1,162,484 | `2021-10-04T00:01:33.704513269Z` | `2021-10-04T00:01:33.706338018Z` | `2021-10-04T00:01:33.706446565Z` | 108,547 ns |
| `TFM` | 1,162,859 | `2021-10-04T00:03:20.924495289Z` | `2021-10-04T00:03:20.924788802Z` | `2021-10-04T00:03:20.924830570Z` | 41,768 ns |
| `TN` | 1,164,696 | `2021-10-04T00:06:18.294285351Z` | `2021-10-04T00:06:18.302738286Z` | `2021-10-04T00:06:18.302881963Z` | 143,677 ns |
| `TFMN` | 1,166,161 | `2021-10-04T00:07:51.633134933Z` | `2021-10-04T00:07:51.633461326Z` | `2021-10-04T00:07:51.633499294Z` | 37,968 ns |
| `TFFCCN` | 2,668,702 | `2021-10-05T00:01:01.119823519Z` | `2021-10-05T00:01:01.120250381Z` | `2021-10-05T00:01:01.120321154Z` | 70,773 ns |
| `TFM` | 2,669,906 | `2021-10-05T00:02:31.506343301Z` | `2021-10-05T00:02:31.506593488Z` | `2021-10-05T00:02:31.506639197Z` | 45,709 ns |
| `TN` | 2,674,145 | `2021-10-05T00:22:45.137772665Z` | `2021-10-05T00:22:45.139642059Z` | `2021-10-05T00:22:45.139786370Z` | 144,311 ns |

The exemplar action ledgers make the lifecycle linkage concrete:

- Group 1,162,308: `T(A,1,5.729,id=786260856050) → F(B,1,5.729,id=786260855382) → C(B,1,5.729,id=786260855382) → N(F_LAST)`.
- Group 1,162,432: `T(B,2,5.734) → F(A,1,id=786260852588) → F(A,1,id=786260856527) → C(A,1,id=786260852588) → C(A,1,id=786260856527) → N(F_LAST)`.
- Group 1,162,484: `T(B,1,5.736) → F(A,1,id=786260837117) → T(B,1,5.736) → F(A,1,id=786260852969) → C(A,1,id=786260837117) → C(A,1,id=786260852969) → N(F_LAST)`.
- Group 1,162,859: `T(A,1,5.741) → F(B,1,id=786260796228) → M(B,2,id=786260796228,F_LAST)`.
- Group 1,166,161: `T(B,2,5.758) → F(A,2,id=786260864394) → M(A,1,id=786260864394) → N(F_LAST)`.
- Group 2,668,702: `T(B,3,5.846) → F(A,1,id=786266093227) → F(A,2,id=786266093162) → C(A,1,id=786266093227) → C(A,2,id=786266093162) → N(F_LAST)`.

Elementary exemplars fix the surrounding queue vocabulary to equally exact clocks: group 1,162,309 is `A(B,1,5.728)` at event `00:00:00.006241107Z` and receive/F_LAST `00:00:00.006422378Z`; group 1,162,310 is `C(B,2,5.700)` at event `00:00:00.007634965Z` and receive/F_LAST `00:00:00.007782846Z`; group 1,162,340 is `A(A,1,5.731)→N` with F_LAST `00:00:03.890121199Z`; group 1,162,346 is `M(A,5,5.751)` with F_LAST `00:00:03.906649164Z`; and group 1,162,347 is `C(A,1,5.731)→N` with F_LAST `00:00:03.908727861Z`.

## Positive exhaustion-research hypotheses

Each item below is explicitly a `RETROSPECTIVE_DISCOVERY_HYPOTHESIS` for the corrected causal rerun.

1. **H1 — post-fill disposition mix.** The exact same-order branching from fill into cancel (`TFCN`) or modification (`TFM`/`TFMN`) can organize local exhaustion state. A causal increase in cancel-linked lifecycles relative to modify-linked lifecycles is hypothesized to mark resting-interest withdrawal, while modify-linked continuation marks retained but resized interest. The rerun will retain family, side sequence, price, size, order ID, event time, first receive, and F_LAST availability for every observation.

2. **H2 — cascade-multiplicity runway.** Local transitions among `TFCN`, `TFFCCN`, and `TFTFCCN` are hypothesized to encode increasing execution fragmentation or repeated queue contact before exhaustion. The corrected rerun will search exact received group order for single-fill → two-fill → repeated-`T→F` motifs, with separate October 4/5 and mirrored-side strata.

3. **H3 — mirrored-side pressure state.** The recurrent `ABBN`/`BAAN`, `ABBBBN`/`BAAAAN`, `ABABBBN`/`BABAAAN`, and `ABB`/`BAA` mirrors provide a native side-resolved basis for opposing-pressure and direction-change research. The rerun will bind pressure hypotheses to the complete side sequence and order lifecycle of each group, then align them to the signed-flow/dipole runway at the same causal cutoff.

4. **H4 — F_LAST formation latency.** The elapsed receive time from first component to neutral or terminal F_LAST is hypothesized to carry information about cascade formation and processing intensity. The rerun will preserve the full per-group latency distribution and exact family identity, enabling precursor, onset, transition, and confirmation clocks to be reconstructed from lawful availability times.

5. **H5 — elementary-mutation context.** Exact `A`/`AN`, `C`/`CN`, and `M`/`MN` incidence around trade-linked lifecycles is hypothesized to distinguish replenishment, withdrawal, and resizing phases of an exhaustion runway. The primitive action groups create a native queue context for each trade cascade while preserving bid/ask identity and F_LAST timing.

6. **H6 — session-withdrawal reset.** The repeatable 21:00 UTC `C…C→N` groups are hypothesized to be deterministic state-reset anchors. The corrected rerun will segment pre-boundary state, the mass-withdrawal group, and post-boundary state as distinct causal phases, carrying the exact 219/211 and 371/210 bid/ask cancel compositions and 796/1,179 cancel-size sums.

## Organization of the full corrected causal rerun

| Rerun layer | Native group families | Positive causal role |
|---|---|---|
| Queue primitives | `A`, `AN`, `C`, `CN`, `M`, `MN` | Reconstruct resting-order addition, withdrawal, and resizing context at exact event/receive/F_LAST clocks. |
| Isolated trade close | `TN` | Preserve a trade-bearing group with explicit causal completion. |
| Single-fill disposition | `TFCN`, `TFM`, `TFMN` | Track exact filled-order identity into cancellation or modification and retain neutral-close variants. |
| Multi-order cascade | `TFFCCN` | Represent one trade distributed across two fills with subsequent ID-linked cancellation actions. |
| Repeated execution cascade | `TFTFCCN` | Represent ordered repeated `T→F` contacts before cancellation and causal close. |
| Session reset | 430`C`→`N`, 581`C`→`N` | Define exact session-boundary withdrawal and queue-state segmentation. |
| Exhaustion runway | H1–H6 on exact group order | Build precursor, onset, transition, persistence, and completion candidates from family- and side-specific causal prefixes. |

The corrected rerun is thereby organized around native event-group identity: separate source days, separate action families, separate side sequences, exact order-ID linkage, exact size and price fields, and separate event, receive, and F_LAST availability clocks. This preserves the mechanical structures that can positively explain how executions, residual-order decisions, queue mutations, cascades, and session resets assemble into exhaustion runways.
