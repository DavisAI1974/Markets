# A-memory Forecaster — first native-replay output positive review

Date: 2026-08-28
Arm: **A-memory only**
Run: `frankie-a-memory-rt-c7da7d257fda-1`
Packet: `amemory-rtpkt-4eed0d33d524b7388db5`

## Status and scope

This is a **bounded retrospective output review**, not a full Forecaster run, not a replay, not an order or strategy authorization, and not a scientific lock. It reviews the intact completed first A-memory diagnostic native-MBO replay outputs and the authorized prior lessons/insights/notes package. Step-1, reveal/scoring material, A-clean, other arms, and old reduced market rows were not inspected. No runtime state was mutated.

All replay-derived claims below use `ts_recv_ns` as the causal availability clock. Event time is retained separately where an exact checkpoint supplies it. Daily means are the controller's arithmetic means over that source day's completed event-group observations; the denominators are the source-day `event_groups` shown below. No value in this review is smoothed across source days, families, side structures, cluster identities, or causal phases.

## Exact provenance

### Controlling directive

| Path | SHA-256 |
|---|---|
| `research/kalshi/agents/frankie_native_raw_mbo_forecaster_first_replay_review_20260828.md` | `c9895e296ecd24888aab96d9279f0190401c748d57f0fd7b21ed6bc33da83de4` |

### Canonical completed A-memory runtime outputs

Runtime root: `/workspace/scratch/da00127ac123/a-memory-runtime-c7da7d2`

| Exact path below runtime root | File SHA-256 | Relevant internal identity |
|---|---|---|
| `rt_observations.json` | `764d1e6f006ef6fe35cad22c3a6c202d3596303356d434c7ecd8065564966051` | `observations_hash=dce8b9c3808cf0c5321e53879e0b4d504c267d037c9e0a276875bde6d4ff12ef` |
| `evidence_bundle.json` | `50b2fce744ecdd0b18ba4c7c83603e058c202a55b6769546de470df17392183b` | `bundle_hash=94a32deafdcb580868ba24df829b616edf36a80f84f80b7cd828efea24a13b36` |
| `progress.json` | `b523cea8172c96e156f9c6eba2c4249afee498d1bf216579f2842867ea2fc94c` | checkpoint `07a407f5616a5a65f8345f8f44728506f1ea5c243c3114204ab1f471df92637b` |
| `source_manifest.json` | `24a47eb1631a17ab391eb61ad73051f694b4c564dddec4050518e730efe40767` | `manifest_hash=a98a454ef5a88d6f3ee1213370d6df530ab2946ec9cde47171b0d7aa19f4e2ba` |
| `native-evidence-groups.jsonl.gz` | `bc0788b51a719d39f5024f10007f4c74e96ff3361a21b66d662d9fadf1a67d8f` | 4,256,603 exact closed event groups |
| `launch_receipt.json` | `480daa5f11c7b691c28f739d6e27cae5adef2f87a72e538bc9af5b10ecd3a587` | launch commit `c7da7d257fda2ce9ddccfaee56020ed3e7de8e50` |
| `resume_recovery_receipt.json` | `500548c70b3d72cf06af513e18957eb609d44ac979cd25abca81b879c66702a8` | selected checkpoint sequence 2; closed prefix 1,000,000 records / 759,713 groups |
| `resume-recovery-receipt-000007.json` | `46ab193feb4838538916e40e25c6c0234e35ecd1ae77c12651ec10c108490cef` | selected checkpoint sequence 7; closed prefix 2,500,000 records / 1,863,686 groups |
| `native-evidence-groups.interrupted-tail-after-checkpoint-000002.jsonl.gz` | `2de5b1afc098117e73f830704abf3072d3c203f01e01b874841a7f47384a2874` | quarantined recovery-tail evidence named by receipt |
| `native-evidence-groups.interrupted-tail-after-checkpoint-000007.jsonl.gz` | `a67d31894a7f8c781b1c5de16c3a507c850001adfb751f3a28b372ca21671e89` | quarantined recovery-tail evidence named by receipt |
| `REPLAY_COMMAND.txt` | `0187801dd1adc95df5a90bbcf38d8ccd8510afea3bd6d281e66cfd49bbd8472f` | provenance only; command was not executed in this review |

The canonical non-hidden runtime inventory contains 62 files: the 11 root outputs above plus 17 checkpoint receipts, 17 controller states, and 17 exact adapter states. The exact inventory digest is `32449c33c49ad6ad18cd0e5f5ef883ee53d4262c65b32ab0dd80d51903174095`, defined as SHA-256 of the newline-concatenated `sha256sum` records sorted by absolute path. Sub-inventory digests under `checkpoints/` are:

| Exact path set | Count | Inventory SHA-256 |
|---|---:|---|
| `checkpoint-000000.json` … `checkpoint-000016.json` | 17 | `a1362ddf469f880f416c89b7bbd06568960177713a55d3421988f42772a022ca` |
| `controller-state-000000.json` … `controller-state-000016.json` | 17 | `9f3eeace1f7b048e97c6d245e43d192f6ab6e794faa42ab13498e36c98ef3bd1` |
| `adapter-state-000000.json`, `adapter-state-000001.json.gz` … `adapter-state-000016.json.gz` | 17 | `f41935445d2d605c93b2f6289ed7c2948eb597ed9b07f0e99371b53bcaeabb17` |

Material boundary/final checkpoint files used for exact-book claims are:

| Exact path below runtime root | SHA-256 |
|---|---|
| `checkpoints/adapter-state-000004.json.gz` | `aa4fc4afa43824ffb1dafd2ea4eac9dfdd7bfab984f89caf1624acdb4ee078fc` |
| `checkpoints/adapter-state-000005.json.gz` | `8eb6e53eb3797076d6e7444f342bf7bbb1413329c683381f2eb2006e4425ca29` |
| `checkpoints/adapter-state-000010.json.gz` | `0898d09e076ad6cfe7d8f874e73133339a02fc2879619fddb21494633ce01ce9` |
| `checkpoints/adapter-state-000015.json.gz` | `9df4a301d68af9abcabc846198b0b91788db01d98f53d70311b30bae286d3c48` |
| `checkpoints/adapter-state-000016.json.gz` | `83a8ebe673bd7d3474ad4127b6f8b75b55cb22cc11510d7a1ea946105ff7b024` |
| `checkpoints/controller-state-000016.json` | `02af15ad4ac5f6a08dc0f4b990b00c5bab6e095b4f9d8beb0c33d6987a9b5722` |
| `checkpoints/checkpoint-000016.json` | `3346d018931909f8cde512186ca23629f53a073cfc00504dcdff3a43ddfb89f3` |

### Authorized prior-memory package and packet proof

Authorized prior directory: `research/kalshi/frankie_raw_mbo_benchmark/prior_memory/workmode-32851909748-1/` (16 files; exact sorted-path inventory digest `0d26f94d0fb308f9650236e1fbbe52dccb488c33855924d9115a08daafbbcfdf`).

Authorized packet-proof root: `/workspace/scratch/da00127ac123/a-memory-packet-c7da7d2/memory/` (18 files; exact recursive sorted-path inventory digest `4f4a5cc2e67f384904251827c7b6b6f8154d8c32d9075029685fecfdd8f0e22a`).

| Exact input | SHA-256 / identity |
|---|---|
| `prior_memory/workmode-32851909748-1/ARTIFACT_MANIFEST.json` | `6f3cb63536d12d2bcb136b6698faf47b37c17a6ee3c8f6ee2ed309578bfda70d` |
| `prior_memory/workmode-32851909748-1/RT_OUTPUT.json` | `72a22b5ec0ee5f6ebdcf14d0ff566dd178f31ce2bd6d3f3f85cf9b49a2ac9158` |
| `prior_memory/workmode-32851909748-1/RT_FROZEN_STATE.json` | `18b1573014daa4d7414a63763b883258aeb14505622c7f1f89572395f14b84e0` |
| `prior_memory/workmode-32851909748-1/FORECASTER_OUTPUT.json` | `32131d948790faa56ed130f901bad71b10075919a2e23a78d1ff2c3939de25af` |
| `memory/prior-learned-package.tgz` | `0a5cddbcd971a3e6c2cad88a8e5559b0ab0529a31174c882355a61fe9c680b87` |
| `memory/prior-learned-package-receipt.json` | file `fe66a813ce017b6f2c730320dab90897f833ba7af2155005f2898066002589d8`; internal receipt `e7d8cbc54f354a4902ab72792e379033a25f5f28102fcf9d4bb82dda1d7e8435` |
| `memory/prior-memory-repository-verification.json` | file `b748e6d50e8b20769d128c2dd44107d866a1d4f5c30170a006506bcc708f166f`; internal receipt `9c5847e33f4014eac12e8da67c2f97e55280545f67ea0d7899fa1c914d39683b` |

The packet proof identifies the learned package as pre-existing, answer-wall sealed, and containing lessons/insights/notes rather than old reduced rows. The packet's `learned-output-chain/` bytes match the authorized repository copies by SHA-256.

### Native source population

| Date | Role | Native MBO records | Completed event groups | Last causal `ts_recv_ns` (UTC) | Source SHA-256 |
|---|---|---:|---:|---|---|
| 2021-10-01 | `WARMUP_DEVELOPMENT` | 1,504,374 | 1,118,738 | `1633122000253186799` (`2021-10-01T21:00:00.253186799Z`) | `e6b4ec01bd9b34d57cb22c770b5d49c756e7f41a658f081823d923004a0121b2` |
| 2021-10-03 | `WARMUP_DEVELOPMENT` | 57,027 | 43,569 | `1633305596372071705` (`2021-10-03T23:59:56.372071705Z`) | `4380bd9ba83a5badc4839e12785aa464817b87e3fac11176b951e7b474446d88` |
| 2021-10-04 | `HELD_OUT_BLIND` | 1,994,358 | 1,506,255 | `1633391999955312214` (`2021-10-04T23:59:59.955312214Z`) | `8ed47cc0a68cf40cae9fde45e158142978076e60d3f9fc7cf940196babfddc0a` |
| 2021-10-05 | `HELD_OUT_BLIND` | 2,111,930 | 1,588,041 | `1633478399954928144` (`2021-10-05T23:59:59.954928144Z`) | `a4a12f9578da762412884e7f559a123361eaa3a153bec0db59dfb3ba6224a874` |
| **Total** | source-day strata kept separate below | **5,667,689** | **4,256,603** | final clock above | manifest `a98a454ef5a88d6f3ee1213370d6df530ab2946ec9cde47171b0d7aa19f4e2ba` |

The evidence bundle binds all 5,667,689 records to native DBN MBO, exact-once raw actions, full-depth/FIFO reconstructability, and the causal clock `ts_recv_ns`. Its progress denominator is `HASH_BOUND_NATIVE_MBO_RECORD_COUNT`.

## Required daily averaged-book surface

Cell order is **first / last / min / max / arithmetic mean**. Each row is a separate source-day stratum; `n` is completed event groups and is the arithmetic-mean denominator. Values are copied from `rt_observations.json` and independently match `checkpoints/controller-state-000016.json`.

### Spread and full-depth imbalance

| Date / role | n | Spread: F / L / min / max / mean | Full-depth imbalance: F / L / min / max / mean |
|---|---:|---|---|
| 2021-10-01 / warmup | 1,118,738 | 0.003000 / 0.023000 / 0.001000 / 0.023000 / **0.002598022057** | 0.092566 / 0.078886 / -0.098496 / 0.206649 / **0.056964193979** |
| 2021-10-03 / warmup | 43,569 | 0.023000 / 0.002000 / -0.060000 / 0.056000 / **0.005698019234** | 0.078886 / 0.058007 / -0.021145 / 0.171484 / **0.065535499357** |
| 2021-10-04 / held out | 1,506,255 | 0.002000 / 0.003000 / 0.001000 / 0.090000 / **0.002263498544** | 0.058007 / 0.210909 / -0.191528 / 0.326687 / **0.121055981003** |
| 2021-10-05 / held out | 1,588,041 | 0.003000 / 0.003000 / -0.033000 / 0.043000 / **0.002218552921** | 0.210909 / 0.315686 / 0.012240 / 0.492340 / **0.221155479523** |

### Full bid/ask depth

| Date / role | n | Bid depth: F / L / min / max / mean | Ask depth: F / L / min / max / mean |
|---|---:|---|---|
| 2021-10-01 / warmup | 1,118,738 | 1,139 / 465 / 465 / 1,916 / **1,573.438556** | 946 / 397 / 397 / 1,831 / **1,405.284423** |
| 2021-10-03 / warmup | 43,569 | 465 / 1,067 / 465 / 1,121 / **952.287934** | 397 / 950 / 397 / 1,001 / **837.974248** |
| 2021-10-04 / held out | 1,506,255 | 1,067 / 999 / 556 / 1,819 / **1,485.381443** | 950 / 651 / 326 / 1,663 / **1,162.396758** |
| 2021-10-05 / held out | 1,588,041 | 999 / 1,342 / 672 / 2,553 / **1,809.886708** | 651 / 698 / 253 / 1,744 / **1,156.145675** |

### Full bid/ask order count

| Date / role | n | Bid orders: F / L / min / max / mean | Ask orders: F / L / min / max / mean |
|---|---:|---|---|
| 2021-10-01 / warmup | 1,118,738 | 449 / 154 / 154 / 871 / **669.550067** | 336 / 90 / 90 / 743 / **511.643446** |
| 2021-10-03 / warmup | 43,569 | 154 / 451 / 154 / 461 / **383.908169** | 90 / 354 / 90 / 382 / **288.008768** |
| 2021-10-04 / held out | 1,506,255 | 451 / 394 / 169 / 804 / **621.512480** | 354 / 272 / 87 / 743 / **489.025180** |
| 2021-10-05 / held out | 1,588,041 | 394 / 469 / 225 / 929 / **723.814827** | 272 / 293 / 78 / 759 / **510.783739** |

### Full bid/ask price-level count

| Date / role | n | Bid levels: F / L / min / max / mean | Ask levels: F / L / min / max / mean |
|---|---:|---|---|
| 2021-10-01 / warmup | 1,118,738 | 311 / 121 / 121 / 458 / **377.411874** | 225 / 76 / 76 / 357 / **295.212059** |
| 2021-10-03 / warmup | 43,569 | 121 / 304 / 121 / 329 / **287.215015** | 76 / 240 / 76 / 262 / **219.899401** |
| 2021-10-04 / held out | 1,506,255 | 304 / 272 / 125 / 469 / **358.664069** | 240 / 197 / 74 / 355 / **270.885952** |
| 2021-10-05 / held out | 1,588,041 | 272 / 314 / 162 / 480 / **390.580283** | 197 / 197 / 58 / 325 / **257.847192** |

For clarity, `mean(depth_imbalance_full)` and `imbalance(mean bid depth, mean ask depth)` are different lawful summaries of the same source-day population because imbalance is nonlinear. The paired values are 0.056964 vs 0.056452 (Oct-01), 0.065535 vs 0.063853 (Oct-03), 0.121056 vs 0.121983 (Oct-04), and 0.221155 vs 0.220409 (Oct-05). This is a **`COMPLEMENTARY_SCOPE_DIFFERENCE`**, not a contradiction; the controller's mean-of-group-imbalances remains the authoritative reported mean.

## Other same-arm diagnostic channels

### Raw actions, sides, grouping, and snapshot scale

Action labels and side labels are kept literal; no B/A side label is promoted here to an aggressor-direction claim.

| Date | A | C | M | T | F | N | R | B-side | A-side | N-side | Groups | Records/group | Max group actions |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2021-10-01 | 507,115 | 506,871 | 140,793 | 69,424 | 93,878 | 186,292 | 1 | 658,568 | 646,540 | 199,266 | 1,118,738 | 1.344706 | 786 |
| 2021-10-03 | 20,249 | 19,444 | 4,939 | 2,028 | 2,411 | 7,955 | 1 | 24,874 | 23,780 | 8,373 | 43,569 | 1.308889 | 245 |
| 2021-10-04 | 692,258 | 691,592 | 168,303 | 86,248 | 118,507 | 237,449 | 1 | 896,553 | 841,180 | 256,625 | 1,506,255 | 1.324051 | 806 |
| 2021-10-05 | 724,424 | 723,662 | 191,251 | 90,233 | 127,536 | 254,823 | 1 | 967,136 | 871,452 | 273,342 | 1,588,041 | 1.329896 | 667 |

Positive mechanics/integrity information:

- For every source day, `A - C` equals the exact live order-object count at the source boundary: 244, 805, 666, and 762. Boundary adapter states independently decompose those objects as B/A = 154/90, 451/354, 394/272, and 469/293, respectively. This binds aggregate lifecycle totals to the exact FIFO book state.
- Each source has exactly one `R`. Its reported maximum group-action count equals `1 + first bid orders + first ask orders`: Oct-01 `1+449+336=786`; Oct-03 `1+154+90=245`; Oct-04 `1+451+354=806`; Oct-05 `1+394+272=667`. Exact evidence group 0 on Oct-01 (`group_hash=6114565181610bd7403d4d7ae2365b0970b550d5ad29d17c7c703c7054e1d43a`, records `[0,786)`, `ts_recv_ns=1633046400000000000`) is the reset-plus-snapshot group. Therefore these maxima are initialization/snapshot scale, a useful guard against treating them as predictive intraday flow bursts.
- T actions per completed group are source-day-specific: 0.062056 (Oct-01), 0.046547 (Oct-03), 0.057260 (Oct-04), and 0.056820 (Oct-05). M actions per group are 0.125850, 0.113360, 0.111736, and 0.120432. These are compact activity-regime covariates suitable for later same-day, same-session stratification.
- The literal B-minus-A message-side share, divided by B+A messages, rises across the two held-out source days from 3.1865% on Oct-04 to 5.2042% on Oct-05. This independently aligns with the stronger bid-side depth/order/level composition while retaining side-label semantics.

### Checkpoint/recovery chain

The 17 checkpoint receipts form sequences 0 through 16 from `PRE_CALL_RT_NATIVE` to `RT_NATIVE_REPLAY_COMPLETE`. The final checkpoint binds 5,667,689 records, 100.0% progress, a closed event group, final adapter-state hash `8d0c9cacb7d02212e6b13198b99ea240a7d2dd42e47c7e9c2a6422d560ee603a`, and final controller-state hash `25aa739837aab845810b11b1f13c6012154ebd6fb5468dfb3a0817014cebab3d`.

The two recovery receipts identify closed causal prefixes at 1,000,000 and 2,500,000 records, quarantine their interrupted tails, and set `uncheckpointed_tail_used=false`. The later receipt additionally fixes the per-source group prefix as `[1,118,738, 43,569, 701,379, 0]`. This makes controller-state sequence 7's Oct-04 partial population (701,379 groups) exactly auditable without replaying the DBNs.

## Positive forecasting findings and useful hypotheses

### 1. Oct-05 is a distinctly stronger bid-heavy held-out source-day regime

The two held-out source days are compared as separate populations, not averaged together:

- Mean full-depth imbalance increases from 0.121055981003 on Oct-04 (`n=1,506,255`) to 0.221155479523 on Oct-05 (`n=1,588,041`): absolute change `+0.100099498520`, relative change `+82.6886%`.
- Mean bid depth increases 21.8466% (1,485.381443 to 1,809.886708), while mean ask depth changes -0.5378% (1,162.396758 to 1,156.145675).
- Mean bid order count increases 16.4602%, versus 4.4494% on ask; mean bid level count increases 8.8986%, while ask level count changes -4.8134%.
- The ratio of mean bid/ask depth increases from 1.277861 to 1.565449; order-count ratio from 1.270921 to 1.417067; level-count ratio from 1.324041 to 1.514774.
- Mean spread remains in the same narrow scale and changes from 0.002263499 to 0.002218553 (-1.9857%). Thus stronger displayed bid composition did not require a wider mean source-day spread.
- Oct-05 full-depth imbalance stays positive across the controller's complete source-day extrema: min 0.012240, mean 0.221155, max 0.492340, last 0.315686. This is a useful regime-conditioning fact, distinct from an outcome or direction forecast.

**Hypothesis H1:** In subsequent same-family, same-session work, persistent positive full-depth imbalance accompanied by rising bid order/level participation and a stable narrow spread is a valuable conditioning regime. Test future price/flow response separately for durable bid replenishment, passive absorption, and transient displayed support.

### 2. Similar closing imbalance can arise from different exact book mechanics

Oct-04 moves from imbalance 0.058007 to 0.210909 while bid depth changes 1,067 to 999 (-6.3730%) and ask depth changes 950 to 651 (-31.4737%). Its closing bid-heaviness is therefore associated mainly with greater ask-depth contraction.

Oct-05 starts at the exact carried boundary imbalance 0.210909 and finishes at 0.315686 while bid depth changes 999 to 1,342 (+34.3343%) and ask depth changes 651 to 698 (+7.2197%). Its additional bid-heaviness is associated mainly with bid-depth growth.

This is a positive mechanism distinction, not cross-day smoothing. A single imbalance value can encode either ask withdrawal or bid accumulation; the full bid/ask depth, order-count, and level-count channels should remain coequal inputs.

**Hypothesis H2:** Condition any imbalance-based forecast on its decomposition. Ask-withdrawal-led imbalance and bid-accumulation-led imbalance are separate mechanism strata and may have different persistence and price-delivery behavior.

### 3. The exact Oct-05 close is relatively stronger but absolutely thinner than its daily scale

At final causal clock `ts_recv_ns=1633478399954928144` (`2021-10-05T23:59:59.954928144Z`), adapter state 16 contains the exact FIFO book:

| Exact final state | Bid | Ask | Bid/ask ratio |
|---|---:|---:|---:|
| Depth | 1,342 | 698 | 1.922636 |
| Live orders | 469 | 293 | 1.600683 |
| Price levels | 314 | 197 | 1.593909 |

The exact depth calculation is `(1342-698)/(1342+698)=0.315686274510`, matching the controller's final imbalance. Against the Oct-05 daily means, final bid depth is 25.85% lower and final ask depth is 39.63% lower, while the final depth ratio 1.922636 exceeds the ratio of daily mean depths 1.565449.

This is a **`COMPLEMENTARY_SCOPE_DIFFERENCE`**: absolute closing liquidity is thinner on both sides, yet relative closing composition is more bid-heavy. It positively sharpens H1: a high late imbalance should be paired with absolute liquidity scale, because the same ratio can reflect thick bid accumulation, thin ask withdrawal, or both.

### 4. Exact native trailing activity refines the authorized prior-memory balance-cross motif

The authorized prior-memory output retained a reduced-surface Oct-05 final-window motif over `[2021-10-05T23:45:00Z, 2021-10-06T00:00:00Z)`: 41 trades, bid depth 1,354 to 1,342, ask depth 700 to 698, full-depth imbalance 0.318403 to 0.315686, signed aggressor imbalance -0.111111 over the full window, early/late halves -0.36/+0.20, and trade-price drift 6.333 to 6.329 (-0.004). Its positive research hypothesis was a weakening sell-flow / late buy-side balance cross against persistent bid-heavy displayed depth.

The exact adapter's retained trailing activity covers `ts_recv_ns` 1633478101810943767 through 1633478399954928144 (`2021-10-05T23:55:01.810943767Z` to `23:59:59.954928144Z`), 298.143984377 seconds. It contains 310 exact lifecycle actions: 106 A, 128 C, 27 M, 8 T, 10 F, and 31 N; 74 are marked top-touch and all 27 M actions are marked priority-lost. The eight exact T actions total 9 units, with printed prices spanning 6.325 to 6.330 and ending at 6.329. From the first T print the last price is +0.002; from the first side-resolved T print it is +0.004. The final exact book remains 1,342 bid depth versus 698 ask depth.

The reduced 15-minute -0.004 drift and exact trailing approximately-five-minute +0.002/+0.004 subwindow are a **`COMPLEMENTARY_SCOPE_DIFFERENCE`**: the broader window preserves delivered sell pressure, while the nested exact tail supplies a small positive price response during the retained late-flow cross. This does not settle a future path; it raises the value of the prior memory's conditional stabilization/absorption branch and gives it exact native-MBO clocks, lifecycle context, and a direct falsifier.

**Hypothesis H3:** A research-grade balance-cross candidate strengthens when (a) the broader causal window has negative delivered flow/price coupling, (b) a nested exact trailing window turns non-negative in price, and (c) bid-heavy depth persists through exact queue activity. Falsify on renewed negative exact price/flow coupling, bid-side cancellation that removes the relative-depth advantage, or failure to recur in a prospectively fixed same-session population.

### 5. Snapshot-aware group interpretation prevents a false burst signal

The daily maximum group-action counts exactly equal reset-plus-first-book order counts, and Oct-01 exact group 0 proves the construction. Therefore `max_group_actions` is valuable as a source-initialization scale and replay-integrity check. It should not be used as an intraday burst feature unless the snapshot/reset group is first excluded within the same source day and session.

**Hypothesis H4:** After excluding source reset/snapshot groups, the distribution of exact non-snapshot group sizes, top-touch participation, priority loss, and side-specific lifecycle actions may reveal queue stress hidden by daily averages. Preserve family/session identity and `ts_recv_ns`; do not pool across source days.

## Calculation ledger

| Claim | Exact calculation | Population / denominator / clock |
|---|---|---|
| Oct-05 vs Oct-04 imbalance change | `0.221155479523 - 0.121055981003 = 0.100099498520`; ratio change `=82.6886%` | separate day means; n=1,588,041 and 1,506,255 completed groups; `ts_recv_ns` |
| Oct-05 vs Oct-04 mean bid depth | `1809.886708 / 1485.381443 - 1 = 21.8466%` | same separate source-day strata |
| Oct-05 vs Oct-04 mean spread | `0.002218552921 / 0.002263498544 - 1 = -1.9857%` | same separate source-day strata |
| Oct-04 endpoint mechanism | bid `999/1067-1=-6.3730%`; ask `651/950-1=-31.4737%`; imbalance `0.210909-0.058007=+0.152902` | first/last completed group observations within Oct-04 source day; `ts_recv_ns` |
| Oct-05 endpoint mechanism | bid `1342/999-1=+34.3343%`; ask `698/651-1=+7.2197%`; imbalance `0.315686-0.210909=+0.104777` | first/last completed group observations within Oct-05 source day; `ts_recv_ns` |
| Exact final imbalance | `(1342-698)/(1342+698)=0.315686274510` | one exact final FIFO book; causal clock `1633478399954928144` |
| Final vs Oct-05 daily absolute scale | bid `1342/1809.886708-1=-25.85%`; ask `698/1156.145675-1=-39.63%` | one exact final book vs n=1,588,041-group source-day means; `COMPLEMENTARY_SCOPE_DIFFERENCE` |
| Held-out literal B/A message-side shift | Oct-04 `(896553-841180)/(896553+841180)=3.1865%`; Oct-05 `(967136-871452)/(967136+871452)=5.2042%` | exact raw-action side totals, separate days; no aggressor reinterpretation |
| Trailing exact activity duration | `(1633478399954928144-1633478101810943767)/1e9=298.143984377 s` | exact retained adapter activity, final checkpoint, `ts_recv_ns` |
| Snapshot group identity | `max_group_actions = 1 + first_bid_orders + first_ask_orders` on all four days | source-start reset/snapshot stratum, exact first/controller values |

## Positive knowledge capsule candidates

1. **Held-out regime context:** Oct-05 is a stronger bid-heavy source day than Oct-04: mean full-depth imbalance 0.221155 vs 0.121056, mean bid depth +21.85%, mean ask depth -0.54%, with mean spread 0.002219 vs 0.002263. Keep the days separate and condition on mechanism.
2. **Closing scale rule:** The Oct-05 exact close is bid-heavy (1,342/698 depth; imbalance 0.315686) but both sides are below daily mean depth. Treat relative imbalance and absolute liquidity as coequal; their valid difference is `COMPLEMENTARY_SCOPE_DIFFERENCE`.
3. **Mechanism rule:** Ask-withdrawal-led imbalance (Oct-04 close) and bid-accumulation-led imbalance (Oct-05 close) are distinct strata; retain bid/ask depth, order count, and level count rather than forecasting from imbalance alone.
4. **Native refinement of prior motif:** The authorized 15-minute negative-drift/late balance-cross motif contains a nested exact last-298.144-second price rebound (+0.002 from first T print; +0.004 from first side-resolved T print) while the final book remains bid-heavy. Use as a conditional stabilization/absorption hypothesis with exact queue-durability falsifiers, not as a locked direction.
5. **Snapshot guard:** Daily `max_group_actions` equals reset plus initial snapshot orders on every source day. Exclude reset/snapshot groups before using group size as an intraday burst feature.
